"""Adapters for the universal Studio, over the sources the website actually reads.

Release records are an immutable identity/evidence register, never a second public
content store. Drafts/history/media reuse cc_studio_documents/revisions/assets.
"""
from copy import deepcopy
import json
from pathlib import Path
from urllib.parse import urlsplit
from datetime import datetime, timezone

from fastapi import HTTPException
from sqlalchemy import select, text

from canarias_site.models.studio import StudioDocument

RELEASE = json.loads((Path(__file__).resolve().parents[1] / 'studio/lugares-release.json').read_text())
SELECTED = {r['canonical_id']: r for r in RELEASE['selected']}
WITHHELD = {r['canonical_id']: r for r in RELEASE['withheld']}
PLACE_RESOURCES = ('places', 'museums-visits', 'leisure-centers')
COPY_FIELDS = ('short_description', 'detailed_description', 'sources')
MEDIA_FIELDS = ('image_url', 'image_alt', 'image_credit', 'image_source_url', 'image_license', 'image_origin', 'gallery', 'image_removed')


def annotate_record(item):
    key = item['identity']['record_key']
    if item['identity']['kind']=='explore' and item['identity']['resource'] in PLACE_RESOURCES:
        p=item['draft']
        p.setdefault('short_description',p.get('description','')[:220])
        p.setdefault('detailed_description',p.get('description',''))
        p.setdefault('sources',[{'url':u,'title':'Fuente'} for u in p.get('cc_lugares_source_urls',[])])
    if key in WITHHELD:
        item['blocked_reason'] = WITHHELD[key]['reason']
        item['release_state'] = 'blocked'
        if not item['id']:
            # The withdrawn editorial text is only a draft. Keep the actual
            # provider baseline/fingerprint for concurrency checks.
            item['draft'] = {**item['draft'], **{k: WITHHELD[key][k] for k in COPY_FIELDS[:2]}}
    elif key in SELECTED:
        item['release_state'] = 'published'
    return item


def safe_url(value):
    if not isinstance(value, str) or len(value) > 2048 or any(c.isspace() or ord(c)<32 for c in value):
        raise ValueError('Podaj pełny adres HTTPS bez spacji i danych logowania.')
    try:
        u = urlsplit(value)
        if u.scheme != 'https' or not u.hostname or u.username or u.password:
            raise ValueError
    except ValueError:
        raise ValueError('Podaj pełny adres HTTPS bez danych logowania.') from None
    return value


def validate_media(payload):
    images = payload.get('gallery', [])
    if not isinstance(images, list) or len(images)>20:
        raise ValueError('Galeria może zawierać najwyżej 20 zdjęć.')
    for image in images:
        if not isinstance(image, dict) or set(image)-{'url','alt','credit','source_url','license'}:
            raise ValueError('Nieprawidłowy element galerii.')
        safe_url(image.get('url'))
        for key in ('alt','credit','license'):
            if not isinstance(image.get(key,''), str) or len(image.get(key,''))>500:
                raise ValueError('Nieprawidłowy opis zdjęcia.')
        if image.get('source_url'):safe_url(image['source_url'])
    for key in ('image_url','image_source_url'):
        if payload.get(key):safe_url(payload[key])
    if 'image_removed' in payload and type(payload['image_removed']) is not bool:
        raise ValueError('Nieprawidłowa widoczność zdjęcia.')


async def prepare_publication(session, identity, current, payload, version, review_confirmed=False):
    from canarias_site.services import studio
    value = deepcopy(payload)
    if identity['kind']=='settings':return value
    # A restored pre-media revision must clear later cover/gallery assignments.
    for field in ('image_url','image_alt','image_credit','image_source_url','image_license','image_origin'):
        value.setdefault(field,'')
    value.setdefault('gallery',[])
    value.setdefault('image_removed',False)
    validate_media(value)
    key = identity['record_key']
    if identity['kind']=='explore' and key in WITHHELD:
        raise HTTPException(409, 'Wstrzymano publikację: '+WITHHELD[key]['reason'])
    # Uploaded assets have a single authoritative library, including R2 files.
    if value.get('image_url') and value.get('image_url') != (current or {}).get('image_url'):
        media = await session.scalar(select(StudioDocument).where(StudioDocument.kind=='media', StudioDocument.published['url'].as_string()==value['image_url']))
        if media:
            value['image_origin']='studio-library'
            value['image_rights_status']='editor-supplied'
            value['image_removed']=False
    if identity['kind']!='explore' or identity['resource'] not in PLACE_RESOURCES:
        return value
    old = current or {}
    if review_confirmed and value.get('category') != old.get('category'):
        value['cc_studio_category']={'canonical_id':key,'type':value.get('category'),'reviewed_by':'authenticated-editor'}
    if review_confirmed and any(value.get(k)!=old.get(k) for k in ('longitude','latitude','geometry')):
        value['cc_studio_location']={'canonical_id':key,'reviewed_by':'authenticated-editor'}
    # Release hashes/envelopes are server-owned, never editable form fields.
    for field in old:
        if field.startswith('cc_lugares_'):
            value[field]=deepcopy(old[field])
    sensitive = any(value.get(k)!=old.get(k) for k in ('name','category','latitude','longitude','geometry',*COPY_FIELDS))
    if key in SELECTED and sensitive and not review_confirmed:
        raise HTTPException(409, 'Potwierdź sprawdzenie tekstu, źródeł, kategorii i położenia przed publikacją.')
    short = str(value.get('short_description') or value.get('description') or '').strip()
    detail = str(value.get('detailed_description') or value.get('description') or '').strip()
    if short and detail:
        if len(short)>220 or len(detail)>6000:
            raise ValueError('Krótki opis: do 220 znaków. Opis szczegółowy: do 6000 znaków.')
        sources = value.get('sources')
        if sources is None:
            sources = [{'url':u,'title':'Fuente'} for u in old.get('cc_lugares_source_urls',[])]
        if not isinstance(sources,list) or len(sources)>12:
            raise ValueError('Dodaj najwyżej 12 źródeł.')
        sources=[{'url':safe_url(s.get('url')), 'title':str(s.get('title') or 'Fuente')[:500]} for s in sources if isinstance(s,dict)]
        if key in SELECTED and not sources:
            raise ValueError('Opublikowany opis Lugares wymaga źródła.')
        value.update(short_description=short, detailed_description=detail, description=short, sources=sources)
        value['cc_studio_copy'] = {
            'canonical_id':key, 'revision':version, 'short_description':short,
            'detailed_description':detail, 'sources':sources,
            'published_at':datetime.now(timezone.utc).isoformat(),
            'published_by':'authenticated-editor', 'review_method':'editor-confirmed' if review_confirmed else 'existing-evidence',
        }
        # Set the real identity after creating a new canonical object.
        if key.startswith('new:'):value.pop('cc_studio_copy')
    return value


async def propagate_place(session, identity, public):
    from canarias_site.services import sql_editor
    # Description and media are shared across catalog memberships; source-specific
    # categories, geometries and original data remain unchanged in other catalogs.
    changes={k:deepcopy(public[k]) for k in (*COPY_FIELDS,*MEDIA_FIELDS,'description','cc_studio_copy','hidden') if k in public}
    for resource in PLACE_RESOURCES:
        if resource==identity['resource']:continue
        rows=await sql_editor._explore_features(session,identity['island'],resource)
        if any(f['properties']['canonical_id']==identity['record_key'] for f in rows):
            await sql_editor.update_explore(session,identity['island'],resource,identity['record_key'],changes)


async def open_record(session, identity):
    from canarias_site.services import studio
    identity=studio.validate_identity(identity)
    row=await session.scalar(studio.document_query(identity))
    if not row and identity['kind']=='explore' and identity['resource'] in PLACE_RESOURCES:
        row=await session.scalar(select(StudioDocument).where(StudioDocument.kind=='explore',StudioDocument.record_key==identity['record_key'],StudioDocument.island==identity['island'],StudioDocument.resource.in_(PLACE_RESOURCES),StudioDocument.status=='draft').order_by(StudioDocument.updated_at.desc()).limit(1))
    if row:return annotate_record(studio.document_view(row))
    current=studio.json_value(await studio.canonical_value(session,identity))
    if current is None:
        values=await studio.canonical_items(session,identity['kind'],identity['island'],identity['resource'])
        match=next(((key,v) for key,v in values if identity['record_key'] in {str(v.get('id','')),str(v.get('slug',''))}),None)
        if match:
            identity={**identity,'record_key':match[0]}
            return await open_record(session,identity)
    if current is None:raise HTTPException(404,'Element nie istnieje w tym katalogu. Wybierz go w wyszukiwarce.')
    # Make sources and the detailed description ordinary visible editorial fields.
    draft=deepcopy(current)
    if identity['kind']=='explore' and identity['resource'] in PLACE_RESOURCES:
        draft.setdefault('detailed_description',draft.get('description',''))
        draft.setdefault('short_description',draft.get('description','')[:220])
        draft.setdefault('sources',[{'url':u,'title':'Fuente'} for u in draft.get('cc_lugares_source_urls',[])])
    return annotate_record(dict(id=None,identity=identity,version=0,status='published',draft=draft,published=current,base_fingerprint=studio.fingerprint(current)))


async def release_catalog(session, q='', island='', state=''):
    rows=(await session.execute(text("""SELECT p.entity_id::text AS id,p.dataset_code,
        r->'properties' AS props
        FROM design.entity_source_properties p
        CROSS JOIN LATERAL jsonb_array_elements(p.properties->'records') r
        WHERE p.provider='canarias-cerca-editorial'
        AND p.dataset_code IN ('explore_places','explore_museums_visits','explore_leisure_centers')"""))).mappings().all()
    live={}
    for row in rows:
        live.setdefault(row['id'],[]).append(row)
    memberships=(await session.execute(text("""SELECT entity_id::text AS id,catalog_code
        FROM design.entity_catalog_memberships WHERE is_active
        AND entity_id=ANY(CAST(:ids AS uuid[]))
        AND catalog_code IN ('explore_places','explore_museums_visits','explore_leisure_centers')"""),{'ids':list(WITHHELD)})).mappings().all()
    blocked_catalogs={}
    for m in memberships:blocked_catalogs.setdefault(m['id'],[]).append(m['catalog_code'])
    items=[]
    for key,record in {**SELECTED,**WITHHELD}.items():
        blocked=key in WITHHELD
        source=live.get(key,[])
        props=source[0]['props'] if source else {}
        catalogs=[s['dataset_code'] for s in source] or sorted(blocked_catalogs.get(key,[]))
        resource=(catalogs[0] if catalogs else 'explore_places').removeprefix('explore_').replace('_','-')
        item={'canonical_id':key,'name':props.get('name') or record['name'],'island':record['island'],
              'resource':resource,'state':'blocked' if blocked else 'published' if source else 'missing',
              'blocked_reason':record.get('reason'),'catalogs':catalogs,
              'short_description':props.get('short_description') or record['short_description']}
        if (not island or item['island']==island) and (not state or item['state']==state) and q.casefold() in (item['name']+' '+key).casefold():items.append(item)
    items.sort(key=lambda i:i['name'].casefold())
    return {'items':items,'count':len(items),'published':sum(k in live for k in SELECTED),'blocked':len(WITHHELD),
            'overlay_rows':sum(len(live.get(k,[])) for k in SELECTED),'release_id':RELEASE['release_id']}


_manifest_cache = None
_manifest_at = 0
async def site_manifest():
    import time
    import httpx
    global _manifest_cache, _manifest_at
    if _manifest_cache is not None and time.monotonic()-_manifest_at<60:
        return _manifest_cache
    # Fixed origin: this endpoint cannot be used as an arbitrary URL proxy.
    async with httpx.AsyncClient(timeout=45,follow_redirects=False) as client:
        response=await client.get('https://www.canariascerca.es/studio-manifest.json')
        if response.status_code!=200:
            raise HTTPException(503,'Mapa witryny czeka na wdrożenie frontendu. Pozostałe edytory są dostępne.')
        if len(response.content)>1_000_000:raise HTTPException(502,'Mapa witryny przekroczyła limit.')
        value=response.json()
    if value.get('schema_version')!=1 or not isinstance(value.get('routes'),list):
        raise HTTPException(502,'Nieprawidłowa mapa witryny.')
    _manifest_cache=value;_manifest_at=time.monotonic()
    return value
