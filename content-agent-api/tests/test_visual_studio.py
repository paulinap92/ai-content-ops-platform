"""Real PostGIS publication: existing overlays, media, block, conflicts, restore."""
import base64
import copy
import os
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import text, select

from tests.test_site_sql import session
from tests.sql_test_support import uid
from canarias_site.services import studio, studio_media, visual_studio as visual
from canarias_site.models.studio import StudioDocument
from canarias_site.api.explore_canonical.mappers import to_legacy_geojson_feature
from canarias_site.services import sql_editor

pytestmark=pytest.mark.skipif(not os.getenv('CC_SQL_TEST_URL'),reason='Disposable PostGIS required')


async def place(session,key,island='tenerife'):
    source=uid('places/'+island)
    await session.execute(text("""INSERT INTO design.entities(id,entity_type,canonical_name,slug,lifecycle_status,created_at,updated_at)
      VALUES (:key,'place','Existing released place',:slug,'active',now(),now())"""),{'key':key,'slug':'studio-test-'+str(key)})
    await session.execute(text("""INSERT INTO design.places(entity_id,place_kind) VALUES (:id,'museum')"""),{'id':key})
    await session.execute(text("""INSERT INTO design.entity_territories(entity_id,territory_entity_id,relation_type,is_primary,created_at)
      SELECT :id,territory_entity_id,relation_type,is_primary,now() FROM design.entity_territories WHERE entity_id=:source"""),{'id':key,'source':source})
    await session.execute(text("""INSERT INTO design.entity_geometries(entity_id,geom,geometry_role,is_canonical,source_name,created_at,updated_at)
      SELECT :id,geom,geometry_role,is_canonical,source_name,now(),now() FROM design.entity_geometries WHERE entity_id=:source"""),{'id':key,'source':source})
    for resource in visual.PLACE_RESOURCES:
        await session.execute(text("""INSERT INTO design.entity_catalog_memberships(entity_id,catalog_code,is_active,created_at,updated_at)
          VALUES (:id,:catalog,true,now(),now())"""),{'id':key,'catalog':'explore_'+resource.replace('-','_')})
        await sql_editor.ExploreImporter(session).save_record(UUID(str(key)),'explore_'+resource.replace('-','_'),{
            'type':'Feature','geometry':{'type':'Point','coordinates':[-16.5,28.2]},
            'properties':{'id':'stable-'+str(key),'name':'Existing released place','island':island,'category':'museum',
                          'description':'Existing short.','short_description':'Existing short.','detailed_description':'Existing details.',
                          'cc_lugares_test_release':visual.RELEASE['release_id'],'cc_lugares_revision':2,
                          'cc_lugares_record_sha256':'a'*64,'cc_lugares_source_urls':['https://example.com/source']}
        },editorial=True)
    await session.flush()
    return {'kind':'explore','island':island,'resource':'places','record_key':str(key)}


@pytest.mark.asyncio
async def test_release_editor_media_publish_across_catalogs_conflict_and_restore(session):
    key=next(k for k,v in visual.SELECTED.items() if v['island']=='tenerife')
    identity=await place(session,key)
    initial=await visual.open_record(session,identity)
    assert initial['draft']['short_description']=='Existing short.'
    assert initial['draft']['sources']==[{'url':'https://example.com/source','title':'Fuente'}]
    geometry_before=await session.scalar(text('SELECT ST_AsText(geom) FROM design.entity_geometries WHERE entity_id=:id'),{'id':key})
    image=await studio_media.upload(session,'tenerife','test.png',base64.b64encode(b'\x89PNG\r\n\x1a\nsynthetic-image').decode(),'ALT text','Owner')
    payload={**initial['draft'],'short_description':'New short.','detailed_description':'New detailed copy.',
        'image_url':image['url'],'image_alt':'ALT text','image_credit':'Owner',
        'gallery':[{'url':image['url'],'alt':'Gallery ALT','credit':'Owner','license':'Own'}]}
    draft=await studio.save_draft(session,identity,payload,0,initial['base_fingerprint'])
    assert (await visual.open_record(session,identity))['published']['short_description']=='Existing short.'
    with pytest.raises(HTTPException,match='Potwierdź'):
        await studio.publish(session,draft['id'],draft['version'])
    live=await studio.publish(session,draft['id'],draft['version'],review_confirmed=True)
    for resource in visual.PLACE_RESOURCES:
        features=await sql_editor._explore_features(session,'tenerife',resource)
        props=next(f['properties'] for f in features if f['properties']['canonical_id']==key)
        assert props['short_description']=='New short.' and props['detailed_description']=='New detailed copy.'
        assert props['cc_studio_copy']['canonical_id']==key
        assert props['image_origin']=='studio-library' and props['image_alt']=='ALT text'
        assert props['gallery'][0]['alt']=='Gallery ALT'
        assert props['cc_lugares_record_sha256']=='a'*64
    assert geometry_before==await session.scalar(text('SELECT ST_AsText(geom) FROM design.entity_geometries WHERE entity_id=:id'),{'id':key})
    with pytest.raises(HTTPException) as exc:
        await studio.save_draft(session,identity,payload,0,initial['base_fingerprint'])
    assert exc.value.status_code==409
    restored=await studio.restore(session,live['id'],0,live['version'])
    assert restored['status']=='draft'
    assert (await studio.canonical_value(session,identity))['short_description']=='New short.'
    await studio.publish(session,restored['id'],restored['version'],review_confirmed=True)
    restored_public=await studio.canonical_value(session,identity)
    assert restored_public['short_description']=='Existing short.'
    assert restored_public['image_url']=='' and restored_public['gallery']==[]
    assert len((await studio.history(session,live['id']))['items'])==5


@pytest.mark.asyncio
async def test_eight_withheld_identities_cannot_publish_via_generic_editor(session):
    assert len(visual.SELECTED)==372 and len(visual.WITHHELD)==8
    key=next(k for k,v in visual.WITHHELD.items() if v['island']=='tenerife')
    # Seed source/provider data; no public editorial overlay is created for a withheld record.
    identity=await place(session,key)
    current=await visual.open_record(session,identity)
    assert current['blocked_reason']
    draft=await studio.save_draft(session,identity,current['draft'],0,current['base_fingerprint'])
    with pytest.raises(HTTPException,match='Wstrzymano'):
        await studio.publish(session,draft['id'],draft['version'],review_confirmed=True)
    assert (await studio.canonical_value(session,identity))['short_description']=='Existing short.'


@pytest.mark.asyncio
async def test_media_validation_blocks_unsafe_gallery_before_write(session):
    identity={'kind':'guide','island':'tenerife','resource':'history','record_key':'new:'+uuid4().hex}
    row=await studio.save_draft(session,identity,{'name':'test','slug':'test-'+uuid4().hex,'gallery':[{'url':'javascript:alert(1)'}]},0,studio.fingerprint(None))
    with pytest.raises(ValueError,match='HTTPS'):
        await studio.publish(session,row['id'],row['version'])


@pytest.mark.asyncio
async def test_event_discovery_draft_edit_and_publication_stays_in_same_studio(session,monkeypatch):
    from dataclasses import asdict
    from src.events import nodes
    from src.events.source_catalog import EVENT_SOURCES
    monkeypatch.setattr(nodes,'settings',nodes.settings.model_copy(update={'openai_api_key':None,'anthropic_api_key':None}))
    source=next(s for s in EVENT_SOURCES if s.island.lower()=='tenerife')
    extracted=nodes.extract({'source_id':source.source_id,'source_config':asdict(source),'cleaned_pages':[
        {'url':'https://official.example/event','text':'Official event page','html_fields':{'title':'Fiesta futura','start_at':'2099-11-07T18:00:00','venue':'Santa Cruz'}}]})
    event=extracted['events'][0]
    identity={'kind':'calendar','island':'tenerife','resource':'2099-11','record_key':'new:'+uuid4().hex}
    payload={'title':event['title'],'description':'Discovered draft','start_date':event['start_at'][:10],
             'end_date':event['start_at'][:10],'all_day':False,'location':event['venue'],'source_url':event['source_url'],'url':event['source_url']}
    draft=await studio.save_draft(session,identity,payload,0,studio.fingerprint(None))
    assert await studio.canonical_value(session,identity) is None
    edited=await studio.save_draft(session,identity,{**payload,'description':'Editor reviewed event'},draft['version'],draft['base_fingerprint'])
    live=await studio.publish(session,edited['id'],edited['version'],review_confirmed=True)
    assert live['published']['description']=='Editor reviewed event'
    assert live['identity']['kind']=='calendar'
    assert [x['action'] for x in (await studio.history(session,live['id']))['items']]==['publish','save_draft','save_draft']


@pytest.mark.asyncio
async def test_withheld_catalog_is_read_from_membership_not_guessed_from_name(session):
    key='20628b0f-406c-4be4-a340-b66831f538ae'  # Museo Guanche actually belongs to explore_places.
    await place(session,key)
    await session.execute(text("DELETE FROM design.entity_catalog_memberships WHERE entity_id=:id AND catalog_code<>'explore_places'"),{'id':key})
    await session.execute(text("DELETE FROM design.entity_source_properties WHERE entity_id=:id AND provider='canarias-cerca-editorial'"),{'id':key})
    catalog=await visual.release_catalog(session,q=key)
    assert catalog['items'][0]['resource']=='places'
    assert catalog['items'][0]['state']=='blocked'
