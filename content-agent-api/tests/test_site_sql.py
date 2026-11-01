"""Editorial lifecycle against CI's disposable PostgreSQL, never hosted data."""
import os
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from canarias_site.db.base import Base
from canarias_site.models.design_db import ContentItem, NewsItem
from canarias_site.models.studio import StudioDocument, StudioRevision
from canarias_site.services import studio
from canarias_site.services.site_settings import empty_settings, published_settings

URL=os.getenv("CC_SQL_TEST_DATABASE_URL") or os.getenv("CC_SQL_TEST_URL")
pytestmark=pytest.mark.skipif(not URL,reason="Disposable PostgreSQL required")


@pytest.fixture
async def session():
    engine=create_async_engine(URL,poolclass=NullPool)
    async with engine.begin() as connection:
        await connection.run_sync(lambda c:Base.metadata.create_all(c,tables=[StudioDocument.__table__,StudioRevision.__table__]))
    async with engine.connect() as connection:
        transaction = await connection.begin()
        async with async_sessionmaker(bind=connection,expire_on_commit=False,join_transaction_mode="create_savepoint")() as session:
            session.info["studio_atomic"]=True
            yield session
        await transaction.rollback()
    await engine.dispose()


@pytest.mark.asyncio
async def test_guide_draft_publish_conflict_hide_and_restore(session):
    slug="studio-test-"+uuid4().hex
    identity={"kind":"guide","island":"tenerife","resource":"food","record_key":"new:"+slug}
    payload={"name":"Studio SQL test","slug":slug,"description":"First body","editor_notes":["PRIVATE"],"hidden":False}
    draft=await studio.save_draft(session,identity,payload,0,studio.fingerprint(None))
    assert await session.scalar(select(ContentItem).where(ContentItem.slug==slug)) is None
    with pytest.raises(HTTPException) as exc:
        await studio.save_draft(session,identity,{**payload,"name":"Stale"},0,studio.fingerprint(None))
    assert exc.value.status_code==409


    await session.rollback()
    published=await studio.publish(session,draft["id"],draft["version"])
    item=await session.scalar(select(ContentItem).where(ContentItem.slug==slug))
    assert item.publication_status=="published" and item.body=="First body"
    assert "editor_notes" not in item.metadata_json
    hidden=await studio.save_draft(session,published["identity"],{**payload,"hidden":True},published["version"],published["base_fingerprint"])
    assert item.publication_status=="published"
    hidden=await studio.publish(session,hidden["id"],hidden["version"])
    await session.refresh(item)
    assert item.publication_status=="hidden"
    restored=await studio.restore(session,hidden["id"],1,hidden["version"])
    await session.refresh(item)
    assert restored["status"]=="draft" and item.publication_status=="hidden"
    restored=await studio.publish(session,restored["id"],restored["version"])
    await session.refresh(item)
    assert item.publication_status=="published"
    revisions=await studio.history(session,draft["id"])
    assert len(revisions["items"])==6


@pytest.mark.asyncio
async def test_regional_news_remains_separate_from_island_news(session):
    identity = {"kind": "news", "island": "canarias", "resource": "news", "record_key": "new:" + uuid4().hex}
    payload = {"title": "Regional editorial test", "summary": "Across the archipelago", "url": "https://example.com/" + uuid4().hex}
    draft = await studio.save_draft(session, identity, payload, 0, studio.fingerprint(None))
    published = await studio.publish(session, draft["id"], draft["version"])
    row = await session.scalar(select(NewsItem).where(NewsItem.news_key == payload["url"]))
    assert row.island_entity_id is None and row.editorial_override
    regional = await studio.canonical_items(session, "news", "canarias", "news")
    tenerife = await studio.canonical_items(session, "news", "tenerife", "news")
    assert published["identity"]["record_key"] in dict(regional)
    assert published["identity"]["record_key"] not in dict(tenerife)
    hidden = await studio.save_draft(session, published["identity"], {**published["draft"], "hidden": True}, published["version"], published["base_fingerprint"])
    await studio.publish(session, hidden["id"], hidden["version"])
    await session.refresh(row)
    assert row.hidden


@pytest.mark.asyncio
async def test_canonical_change_blocks_stale_publication(session):
    identity={"kind":"guide","island":"tenerife","resource":"food","record_key":"new:"+uuid4().hex}
    payload={"name":"Conflict test","slug":"conflict-"+uuid4().hex}
    initial=await studio.save_draft(session,identity,payload,0,studio.fingerprint(None))
    published=await studio.publish(session,initial["id"],initial["version"])
    identity=published["identity"]
    current=await studio.canonical_value(session,identity)
    row=await session.scalar(studio.document_query(identity))
    draft=await studio.save_draft(session,identity,{**current,"description":"My correction"},row.version if row else 0,studio.fingerprint(current))
    await session.execute(text("UPDATE design.content_items SET title='Concurrent change' WHERE id=CAST(:id AS uuid)"),{"id":identity["record_key"]})
    await session.commit()
    with pytest.raises(HTTPException) as exc:
        await studio.publish(session,draft["id"],draft["version"])
    assert exc.value.status_code==409


@pytest.mark.asyncio
async def test_settings_are_invisible_until_published_and_inherit_by_island(session):
    identity={"kind":"settings","island":"global","resource":"site","record_key":"site"}
    existing=await session.scalar(studio.document_query(identity))
    current=(await studio.canonical_items(session,"settings","global","site"))[0][1]
    data={"global":{"sections":{"news":False},"features":{"guide.food":False},"copy":{"home.title":"Edited headline"}},"islands":{"tenerife":{"sections":{"news":True}}}}
    draft=await studio.save_draft(session,identity,data,existing.version if existing else 0,studio.fingerprint(current))
    assert await published_settings(session)==current
    result=await studio.publish(session,draft["id"],draft["version"])
    assert (await published_settings(session))["global"]["sections"]["news"] is False
    await studio.restore(session,draft["id"],1,result["version"])
    assert (await published_settings(session))["global"]["sections"]["news"] is False


@pytest.mark.asyncio
async def test_explore_correction_preserves_identity_and_can_hide(session):
    key,original=(await studio.canonical_items(session,"explore","tenerife","places"))[0]
    identity={"kind":"explore","island":"tenerife","resource":"places","record_key":key}
    payload={**original,"name":"Editorial place", "hidden":True, "latitude":28.25}
    draft=await studio.save_draft(session,identity,payload,0,studio.fingerprint(original))
    published=await studio.publish(session,draft["id"],draft["version"])
    assert published["identity"]["record_key"]==key
    assert published["published"]["hidden"] is True
    assert published["published"]["geometry"]["coordinates"][1]==28.25


@pytest.mark.asyncio
async def test_calendar_date_edit_moves_month_membership(session):
    identity={"kind":"calendar","island":"tenerife","resource":"2026-11","record_key":"new:"+uuid4().hex}
    payload={"title":"Editorial event","start_date":"2026-11-20","end_date":"2026-11-21","all_day":True}
    draft=await studio.save_draft(session,identity,payload,0,studio.fingerprint(None))
    event=await studio.publish(session,draft["id"],draft["version"])
    payload={**event["published"],"start_date":"2026-12-01","end_date":"2027-01-03"}
    draft=await studio.save_draft(session,event["identity"],payload,event["version"],event["base_fingerprint"])
    event=await studio.publish(session,draft["id"],draft["version"])
    assert event["identity"]["resource"]=="2026-12"
    key=event["identity"]["record_key"]
    assert key not in dict(await studio.canonical_items(session,"calendar","tenerife","2026-11"))
    assert key in dict(await studio.canonical_items(session,"calendar","tenerife","2026-12"))
    assert key in dict(await studio.canonical_items(session,"calendar","tenerife","2027-01"))


@pytest.mark.asyncio
async def test_failure_before_history_commit_rolls_back_canonical_publication(session,monkeypatch):
    slug="rollback-"+uuid4().hex
    identity={"kind":"guide","island":"tenerife","resource":"food","record_key":"new:"+slug}
    draft=await studio.save_draft(session,identity,{"name":"Rollback", "slug":slug},0,studio.fingerprint(None))
    async def fail(*args):
        raise RuntimeError("Simulated interrupted publication")
    monkeypatch.setattr(studio,"_revision",fail)
    with pytest.raises(RuntimeError):
        await studio.publish(session,draft["id"],draft["version"])
    await session.rollback()
    assert await session.scalar(select(ContentItem.id).where(ContentItem.slug==slug)) is None
    saved=await session.get(StudioDocument,UUID(draft["id"]))
    assert saved.status=="draft" and saved.version==1


@pytest.mark.asyncio
async def test_ai_improves_bound_article_as_private_draft_and_preserves_identity(session,tmp_path,monkeypatch):
    import json
    from contextlib import asynccontextmanager
    from types import SimpleNamespace
    from src.services import canarias_publisher as publisher
    from src.domain.schemas import CanariasPublishRequest
    slug='bound-'+uuid4().hex
    identity={'kind':'guide','island':'tenerife','resource':'food','record_key':'new:'+slug}
    original={'name':'Original','slug':slug,'description':'Original body','image_url':'https://example.com/photo.jpg'}
    initial=await studio.save_draft(session,identity,original,0,studio.fingerprint(None))
    published=await studio.publish(session,initial['id'],initial['version'])
    package={'type':'guide','island':'tenerife','category':'food','slug':'different-ai-slug','sources':[], 'public_content':{'es':{'title':'AI suggestion','summary':'Summary','body_markdown':'New body'}}}
    path=tmp_path/'package.json';path.write_text(json.dumps(package))
    @asynccontextmanager
    async def scope():yield session
    monkeypatch.setattr(publisher,'session_scope',scope)
    monkeypatch.setattr(publisher,'settings',SimpleNamespace(canarias_publish_enabled=True,content_language_codes=('es',)))
    target={'identity':published['identity'],'payload':published['draft'],'version':published['version'],'base_fingerprint':published['base_fingerprint']}
    result=await publisher.CanariasPublisherService().publish_file(file_path=str(path),request=CanariasPublishRequest(section='food'),site_target=target)
    assert result.slug==slug
    saved=result.backend_response
    assert saved['identity']==published['identity']
    assert saved['draft']['description']=='New body' and saved['draft']['image_url']==original['image_url']
    assert saved['published']['description']=='Original body'
    row=await session.scalar(select(ContentItem).where(ContentItem.slug==slug))
    assert row.title=='Original' and row.body=='Original body'
