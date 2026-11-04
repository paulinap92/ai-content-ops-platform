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
from canarias_site.models.studio import StudioDocument, StudioRevision, StudioAsset
from canarias_site.services import studio
from canarias_site.services.site_settings import empty_settings, published_settings

URL=os.getenv("CC_SQL_TEST_DATABASE_URL") or os.getenv("CC_SQL_TEST_URL")
pytestmark=pytest.mark.skipif(not URL,reason="Disposable PostgreSQL required")


@pytest.fixture
async def session():
    engine=create_async_engine(URL,poolclass=NullPool)
    async with engine.begin() as connection:
        await connection.run_sync(lambda c:Base.metadata.create_all(c,tables=[StudioDocument.__table__,StudioRevision.__table__,StudioAsset.__table__]))
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


@pytest.mark.asyncio
async def test_live_point_requires_publish_then_preserves_history_when_disabled(session):
    identity=dict(kind='live-point',island='tenerife',resource='weather',record_key='new:'+uuid4().hex)
    payload=dict(name='Private draft location',latitude=28.46,longitude=-16.25,hidden=False)
    draft=await studio.save_draft(session,identity,payload,0,studio.fingerprint(None))
    assert not await studio.canonical_value(session,identity)
    active=await studio.publish(session,draft['id'],draft['version'])
    assert active['published']['id'].startswith('custom-')
    assert active['published']['island']=='tenerife'
    payload['hidden']=True
    changed=await studio.save_draft(session,active['identity'],payload,active['version'],active['base_fingerprint'])
    assert not changed['published']['hidden']
    disabled=await studio.publish(session,changed['id'],changed['version'])
    assert disabled['published']['hidden'] and len((await studio.history(session,disabled['id']))['items'])>=4
    with pytest.raises(ValueError):studio.validate_payload(identity,dict(name='Bad point',latitude=52,longitude=16))

@pytest.mark.asyncio
async def test_uploaded_photo_persists_in_sql_without_r2_and_deduplicates(session,monkeypatch):
    import base64
    from canarias_site.services import studio_media
    for key in studio_media.R2_KEYS:monkeypatch.delenv(key,raising=False)
    data=b'\xff\xd8\xffisolated-photo-test'
    image=await studio_media.upload(session,'tenerife','own.jpg',base64.b64encode(data).decode(),'My landscape','Owner')
    assert '/api/media/' in image['url'] and image['alt']=='My landscape'
    digest=image['url'].rsplit('/',1)[1]
    assert (await session.get(StudioAsset,digest)).data==data
    downloaded,mime=await studio_media.download(session,image['url'])
    assert downloaded==data and mime=='image/jpeg'
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as missing:
        await studio_media.download(session,'https://external.example/not-in-library.jpg')
    assert missing.value.status_code==404
    again=await studio_media.upload(session,'tenerife','duplicate.jpg',base64.b64encode(data).decode())
    assert again['url']==image['url']

@pytest.mark.asyncio
async def test_chart_city_metric_dates_and_real_gaps(session):
    from datetime import datetime,timezone,date
    from canarias_site.services import analytics
    from canarias_site.models.design_db import ClimateObservation
    island=await studio.sql_editor.ExploreImporter(session).island_id('tenerife')
    point='chart-test-'+uuid4().hex
    for index,(day,value) in enumerate([(1,10),(1,14),(3,20)]):
        session.add(ClimateObservation(id=1900000000+index,resource='weather',island_entity_id=island,point_id=point,observed_at=datetime(2026,1,day,index,tzinfo=timezone.utc),latitude=28.46,longitude=-16.25,source='Synthetic test',payload={'name':'Test city','temperature':value},ingested_at=datetime.now(timezone.utc)))
    await session.flush()
    options=await analytics.options(session,'tenerife')
    assert any(p['point_id']==point and p['name']=='Test city' for p in options['points'])
    result=await analytics.series(session,'tenerife','weather','temperature',point,date(2026,1,1),date(2026,1,3))
    assert [r['value'] for r in result['rows']]==[12,20] # Jan 2 must stay absent.
    assert (await analytics.series(session,'tenerife','weather','humidity',point,date(2026,1,1),date(2026,1,3)))['rows'][0]['value'] is None
    with pytest.raises(HTTPException):await analytics.series(session,'tenerife','weather','unknown',point)


@pytest.mark.asyncio
async def test_passenger_chart_reports_missing_sources_without_fabricating_city_data(session):
    from canarias_site.services.analytics import passengers
    result=await passengers(session,'la-graciosa')
    assert result['rows']==[] and result['reason'] and result['resolution']=='month'
    with pytest.raises(HTTPException):await passengers(session,'tenerife',series='not-allowed')


@pytest.mark.asyncio
async def test_passenger_series_uses_real_months_and_keeps_more_than_100_values(session):
    from datetime import datetime,timezone,date
    from canarias_site.services import analytics
    from canarias_site.models.design_db import StatisticalSnapshot
    row=await session.scalar(select(StatisticalSnapshot).where(StatisticalSnapshot.dataset=='tourism:air-passengers',StatisticalSnapshot.target=='tenerife'))
    payload={'source':'Synthetic test','history':[{'period':f'{2010+i//12}-{i%12+1:02d}','value':i+100} for i in range(150)],'flight_types':{'history':[{'period':'2022-01','foreign':12,'peninsular':8,'interinsular':3}]}}
    if row:row.payload=payload
    else:session.add(StatisticalSnapshot(id=1910000000,dataset='tourism:air-passengers',target='tenerife',payload=payload,ingested_at=datetime.now(timezone.utc)))
    await session.flush()
    result=await analytics.passengers(session,'tenerife')
    assert len(result['rows'])==150 and result['rows'][-1]['value']==249
    result=await analytics.passengers(session,'tenerife',date_from=date(2022,1,1),date_to=date(2022,3,31))
    assert [r['value'] for r in result['rows']]==[244,245,246]
    assert (await analytics.passengers(session,'tenerife',series='foreign'))['rows'][0]['value']==12
