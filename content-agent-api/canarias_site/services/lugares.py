"""Native Lugares revisions. No provider, name, category or geometry writes.

Every save inserts a new draft; verification and approval are explicit human
attestations, bound to the immutable revision. Publication is separately enabled.
"""
import hashlib
import json
import os
from copy import deepcopy
from datetime import datetime, timezone
from uuid import UUID, uuid4
from urllib.parse import urlsplit

from fastapi import HTTPException
from sqlalchemy import text

FIELDS = """c.*, e.canonical_name AS name, i.slug AS island"""
JOIN = """FROM design.content_items c JOIN design.entities e ON e.id=c.entity_id
          JOIN design.entities i ON i.id=c.island_entity_id"""


def fingerprint(row):
    return hashlib.sha256(json.dumps({k: row[k] for k in (
        'id', 'cc_revision', 'short_description', 'body', 'cc_sources',
        'cc_verification_status', 'cc_review_status', 'publication_status', 'updated_at')},
        sort_keys=True, default=str, ensure_ascii=False).encode()).hexdigest()


def present(row):
    item = dict(row)
    item['fingerprint'] = fingerprint(item)
    item['blocked_reason'] = item['metadata'].get('a3_record', {}).get('editorial_review', {}).get('reason') if blocked(item) else None
    item['publish_enabled'] = os.getenv('STUDIO_LUGARES_PUBLISH_ENABLED', '').lower() == 'true'
    return item


def blocked(row):
    return row['metadata'].get('a3_record', {}).get('editorial_review', {}).get('outcome') == 'blocked'


def url(value):
    try:
        parsed = urlsplit(value)
        if (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password
                or any(c.isspace() for c in value) or len(value) > 2048):
            raise ValueError
    except (TypeError, ValueError):
        raise HTTPException(422, 'Źródło wymaga pełnego adresu HTTPS bez danych logowania.') from None
    return value


def validate_copy(short, body, sources):
    if not short.strip() or len(short.strip()) > 220 or not body.strip():
        raise HTTPException(422, 'Wymagany krótki opis do 220 znaków i opis szczegółowy.')
    if not 1 <= len(sources) <= 12:
        raise HTTPException(422, 'Dodaj od 1 do 12 źródeł.')
    urls = [url(s['url']) for s in sources]
    if len(set(urls)) != len(urls):
        raise HTTPException(422, 'To samo źródło występuje więcej niż raz.')
    if any(not s['title'].strip() for s in sources):
        raise HTTPException(422, 'Podaj nazwy źródeł.')


async def ready(session):
    result = await session.execute(text("""SELECT EXISTS(SELECT FROM information_schema.columns
      WHERE table_schema='design' AND table_name='content_items' AND column_name='cc_revision')"""))
    if not result.scalar():
        raise HTTPException(503, 'Lugares oczekuje na migrację i import zatwierdzonego wydania.')


async def records(session, island, q, state, offset, limit):
    await ready(session)
    sql = """WITH latest AS (SELECT DISTINCT ON (c.entity_id) """ + FIELDS + ' ' + JOIN + """
      WHERE c.module='cc_lugares' AND c.language='es'
      ORDER BY c.entity_id,c.cc_revision DESC)
      SELECT *, count(*) OVER() AS total FROM latest
      WHERE (:island='' OR island=:island) AND (name ILIKE :q OR entity_id::text=:exact)
      AND (:state='' OR :state='blocked' AND cc_verification_status='needs_review'
           OR :state='published' AND publication_status='published'
           OR :state='draft' AND publication_status='draft'
           OR :state='approved' AND cc_review_status='approved')
      ORDER BY name,entity_id LIMIT :limit OFFSET :offset"""
    rows = (await session.execute(text(sql), dict(island=island, q='%'+q+'%', exact=q, state=state, offset=offset, limit=limit))).mappings().all()
    return {'items': [present(r) for r in rows], 'total': rows[0]['total'] if rows else 0}


async def latest(session, entity_id, expected=None):
    # Serialize saves/actions for this identity, including concurrent insert races.
    await session.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"), {'key': 'cc_lugares:studio:'+str(entity_id)})
    result = await session.execute(text('SELECT '+FIELDS+' '+JOIN+"""
        WHERE c.module='cc_lugares' AND c.language='es' AND c.entity_id=:id
        ORDER BY c.cc_revision DESC LIMIT 1 FOR UPDATE OF c"""), {'id': entity_id})
    row = result.mappings().first()
    if row is None:
        raise HTTPException(404, 'Brak opisu Lugares dla tego UUID.')
    if expected is not None and fingerprint(row) != expected:
        raise HTTPException(409, 'Wersja uległa zmianie. Odśwież wpis przed zapisem.')
    return row


async def history(session, entity_id):
    rows = (await session.execute(text('SELECT '+FIELDS+' '+JOIN+"""
        WHERE c.module='cc_lugares' AND c.language='es' AND c.entity_id=:id
        ORDER BY c.cc_revision DESC"""), {'id': entity_id})).mappings().all()
    return {'items': [present(r) for r in rows]}


async def save(session, entity_id, data):
    old = await latest(session, entity_id, data.expected_fingerprint)
    sources = [s.model_dump() for s in data.sources]
    validate_copy(data.short_description, data.detailed_description, sources)
    now = datetime.now(timezone.utc)
    n = old['cc_revision']+1
    meta = deepcopy(old['metadata'])
    meta['studio_revision'] = {'saved_at': now.isoformat(), 'saved_by': data.editor,
                               'supersedes_id': str(old['id']), 'supersedes_fingerprint': fingerprint(old)}
    meta['a3_record'].setdefault('verification', {})['notes'] = ['Studio: content/source changes require explicit human verification.']
    # Historic facts and provenance stay on the old immutable revision. They must
    # not be presented as proof for newly edited prose.
    meta['a3_record']['verified_facts'] = []
    meta['record_sha256'] = hashlib.sha256(json.dumps({'short': data.short_description.strip(),
        'body': data.detailed_description.strip(), 'sources': sources}, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    for source in sources:
        source.update(http_status=None, error='Pending human source verification', checked_at=None)
    changes = dict(id=str(uuid4()), cc_revision=n, content_key=f'cc_lugares:{entity_id}:es:r{n}',
        short_description=data.short_description.strip(), body=data.detailed_description.strip(),
        cc_sources=sources, cc_official_url=None, cc_review_status='draft',
        cc_verification_status='needs_review', cc_last_verified_at=None,
        cc_style_approved=False, cc_reviewed_by=None, cc_reviewed_at=None,
        publication_status='draft', metadata=meta, created_at=now.isoformat(), updated_at=now.isoformat())
    # Reuse the stored native row shape, not an ORM copy missing B1 columns.
    await session.execute(text("""INSERT INTO design.content_items
      SELECT (jsonb_populate_record(NULL::design.content_items,to_jsonb(c)||CAST(:changes AS jsonb))).*
      FROM design.content_items c WHERE c.id=:old_id"""), {'changes': json.dumps(changes, default=str), 'old_id': old['id']})
    result = present(await latest(session, entity_id))
    await session.commit()
    return result


async def action(session, entity_id, data):
    row = await latest(session, entity_id, data.expected_fingerprint)
    now = datetime.now(timezone.utc)
    if data.action == 'verify':
        if row['cc_review_status'] != 'draft' or blocked(row):
            raise HTTPException(409, 'Zablokowany lub zatwierdzony wpis wymaga osobnego rozstrzygnięcia / nowej rewizji.')
        if not data.facts_checked or not data.sources_checked or not data.sentence_count_checked:
            raise HTTPException(422, 'Potwierdź fakty, tożsamość, 2–4 zdania i sprawdzenie wszystkich źródeł.')
        if 'studio_revision' not in row['metadata']:
            raise HTTPException(409, 'Importowane zweryfikowane dane zachowują wynik weryfikacji; zablokowane przypadki wymagają rozstrzygnięcia.')
        sources = deepcopy(row['cc_sources'])
        validate_copy(row['short_description'], row['body'], sources)
        for source in sources:
            source.update(http_status=200, error=None, checked_at=now.isoformat(),
                          check_method='authenticated_editor_attestation', checked_by=data.editor)
        meta = deepcopy(row['metadata'])
        meta['a3_record']['verification']['notes'] = []
        meta['studio_revision']['verification'] = {'actor': data.editor, 'at': now.isoformat(),
            'method': 'manual: editor opened every URL and checked identity, facts and 2–4 sentences'}
        await session.execute(text("""UPDATE design.content_items SET cc_sources=CAST(:sources AS jsonb),
          metadata=CAST(:meta AS jsonb),cc_verification_status='verified',cc_last_verified_at=:now,updated_at=:now
          WHERE id=:id"""), {'sources': json.dumps(sources), 'meta': json.dumps(meta), 'now': now, 'id': row['id']})
    elif data.action == 'approve':
        if (row['cc_verification_status'] != 'verified' or blocked(row)
                or row['cc_review_status'] != 'draft' or not data.style_approved):
            raise HTTPException(409, 'Zatwierdzenie wymaga zweryfikowanego szkicu i akceptacji stylu ES.')
        await session.execute(text("""UPDATE design.content_items SET cc_review_status='approved',
            cc_style_approved=true,cc_reviewed_by=:actor,cc_reviewed_at=:now,updated_at=:now WHERE id=:id"""),
            {'actor': data.editor, 'now': now, 'id': row['id']})
    else:
        if os.getenv('STUDIO_LUGARES_PUBLISH_ENABLED', '').lower() != 'true':
            raise HTTPException(403, 'Publikacja Lugares nie została jeszcze uruchomiona dla tego środowiska.')
        if blocked(row) or row['cc_review_status'] != 'approved' or row['cc_verification_status'] != 'verified':
            raise HTTPException(409, 'Opublikować można wyłącznie zatwierdzoną, zweryfikowaną rewizję.')
        # Database guard validates the full evidence set independently of this API.
        await session.execute(text("UPDATE design.content_items SET publication_status='published',updated_at=:now WHERE id=:id"), {'now': now, 'id': row['id']})
    result = present(await latest(session, entity_id))
    await session.commit()
    return result
