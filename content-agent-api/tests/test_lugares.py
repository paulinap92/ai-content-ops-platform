"""Native Lugares lifecycle against disposable PostGIS; no hosted writes."""
import json
import os
from copy import deepcopy
from pathlib import Path
from uuid import uuid4
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool
from canarias_site.api.lugares import router, Draft, Action
from canarias_site.services import lugares
from src.core.auth import authentication

URL = os.getenv('CC_SQL_TEST_DATABASE_URL') or os.getenv('CC_SQL_TEST_URL')
FIXTURES = Path(__file__).parent/'fixtures/lugares'


def test_auth_and_cross_origin_guards(monkeypatch):
    app = FastAPI(); app.middleware('http')(authentication); app.include_router(router)
    with TestClient(app, base_url='https://editor.example') as client:
        assert client.get('/site/api/lugares').status_code == 401
        assert client.get('/site/lugares').status_code == 401
        r = client.post('/site/api/lugares/'+str(uuid4())+'/actions',
                        headers={'Authorization': 'Bearer '+os.environ['EDITOR_TOKEN'], 'Origin': 'https://other.example'}, json={})
        assert r.status_code == 403


@pytest.fixture
async def native_session():
    if not URL: pytest.skip('Disposable PostgreSQL required')
    engine = create_async_engine(URL, poolclass=NullPool)
    async with engine.connect() as connection:
        outer = await connection.begin()
        # Contract snapshots copied from backend PR16; DDL is rolled back here.
        for name in ['b1_up.sql', 'publication_up.sql']:
            sql = (FIXTURES/name).read_text().replace('BEGIN;','').replace('COMMIT;','')
            await connection.exec_driver_sql(sql)
        async with async_sessionmaker(bind=connection, expire_on_commit=False, join_transaction_mode='create_savepoint')() as session:
            yield session
        await outer.rollback()
    await engine.dispose()


async def seed(session, *, blocked=False):
    entity = uuid4(); island = (await session.execute(text("SELECT e.id FROM design.entities e JOIN design.islands i ON i.entity_id=e.id WHERE e.slug='tenerife'"))).scalar_one()
    await session.execute(text("INSERT INTO design.entities(id,entity_type,canonical_name,lifecycle_status,created_at,updated_at) VALUES(:id,'place','Synthetic native place','active',now(),now())"), {'id': entity})
    meta = {'a3_record': {'verification': {'notes': []}, 'editorial_review': {'outcome': 'blocked' if blocked else 'closed_unchanged', 'reason': 'Identity requires separate resolution' if blocked else 'Checked'}}}
    sources = [{'url': 'https://example.org/source', 'title': 'Synthetic source', 'http_status': 200, 'error': None, 'checked_at': '2026-11-18T12:00:00Z'}]
    await session.execute(text("""INSERT INTO design.content_items
      (id,entity_id,island_entity_id,module,section,content_key,language,title,short_description,body,featured,publication_status,
       metadata,created_at,updated_at,cc_revision,cc_sources,cc_review_status,cc_verification_status,cc_last_verified_at,cc_availability_status,cc_style_approved)
      VALUES(:row,:id,:island,'cc_lugares','descriptions',:key,'es','Synthetic native place','Texto sintético.','Primera frase. Segunda frase.',false,'draft',
       CAST(:meta AS jsonb),now(),now(),1,CAST(:sources AS jsonb),'draft',:state,now(),'unknown',false)"""),
      {'row': uuid4(), 'id': entity, 'island': island, 'key': f'cc_lugares:{entity}:es:r1', 'meta': json.dumps(meta), 'sources': json.dumps(sources), 'state': 'needs_review' if blocked else 'verified'})
    await session.commit()
    return entity, dict(await lugares.latest(session, entity))


def version(row, **kwargs):
    return dict(expected_fingerprint=lugares.fingerprint(row), editor='Isolated test editor', **kwargs)


async def edit(session, entity, row):
    return await lugares.save(session, entity, Draft(**version(row), short_description='Una nueva descripción.', detailed_description='Un dato contrastado. Otro dato contrastado.', sources=[{'url': 'https://example.org/new', 'title': 'New source'}]))


async def act(session, entity, row, action, **kwargs):
    return await lugares.action(session, entity, Action(**version(row, action=action, **kwargs)))


@pytest.mark.asyncio
async def test_save_verify_approve_publish_history_and_stale_write(native_session, monkeypatch):
    s = native_session
    entity, initial = await seed(s)
    edited = await edit(s, entity, initial)
    assert edited['cc_revision'] == 2 and edited['cc_verification_status'] == 'needs_review'
    assert edited['cc_sources'][0]['checked_at'] is None
    with pytest.raises(HTTPException) as exc: await edit(s, entity, initial)
    assert exc.value.status_code == 409
    with pytest.raises(HTTPException): await act(s, entity, edited, 'approve', style_approved=True)
    checked = await act(s, entity, edited, 'verify', facts_checked=True, sources_checked=True, sentence_count_checked=True)
    assert checked['cc_sources'][0]['check_method'] == 'authenticated_editor_attestation'
    approved = await act(s, entity, checked, 'approve', style_approved=True)
    assert approved['publication_status'] == 'draft' and approved['cc_reviewed_by'] == 'Isolated test editor'
    with pytest.raises(HTTPException) as exc: await act(s, entity, approved, 'publish')
    assert exc.value.status_code == 403
    monkeypatch.setenv('STUDIO_LUGARES_PUBLISH_ENABLED', 'true')
    published = await act(s, entity, approved, 'publish')
    assert published['publication_status'] == 'published'
    next_draft = await edit(s, entity, published)
    history = (await lugares.history(s, entity))['items']
    assert [r['cc_revision'] for r in history] == [3,2,1]
    assert history[1]['body'] == published['body'] and history[1]['publication_status'] == 'published'
    assert history[2]['short_description'] == initial['short_description']
    assert next_draft['publication_status'] == 'draft' and not next_draft['cc_style_approved']
    found = await lugares.records(s, 'tenerife', str(entity), '', 0, 50)
    assert found['total'] == 1 and found['items'][0]['cc_revision'] == 3


@pytest.mark.asyncio
async def test_blocked_identity_cannot_be_verified_or_approved(native_session):
    entity, initial = await seed(native_session, blocked=True)
    edited = await edit(native_session, entity, initial)
    assert edited['blocked_reason'] == 'Identity requires separate resolution'
    for action, flags in [('verify', dict(facts_checked=True, sources_checked=True, sentence_count_checked=True)), ('approve', dict(style_approved=True))]:
        with pytest.raises(HTTPException) as exc: await act(native_session, entity, edited, action, **flags)
        assert exc.value.status_code == 409


def test_source_validation_and_payload_identity_protection():
    for value in ['javascript:alert(1)', 'https://user:secret@example.org', 'file:///tmp/a', 'http://example.org']:
        with pytest.raises(HTTPException): lugares.url(value)
    with pytest.raises(Exception): Draft(expected_fingerprint='a'*64, editor='Test', short_description='x', detailed_description='y', sources=[{'url':'https://example.org','title':'Source'}], geometry={})
    with pytest.raises(HTTPException): lugares.validate_copy('x'*221, 'body', [{'url':'https://example.org','title':'Source'}])
    with pytest.raises(HTTPException): lugares.validate_copy('short', 'body', [{'url':'https://example.org','title':'Source'}]*2)
