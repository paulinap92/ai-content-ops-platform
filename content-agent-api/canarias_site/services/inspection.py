"""Authenticated, bounded reads of canonical data. No arbitrary SQL or writes."""
from contextlib import asynccontextmanager
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID
import re

from fastapi import HTTPException
from sqlalchemy import text, select, func, or_, inspect
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.exc import DBAPIError

from canarias_site.services.studio_auth import database_url, writer_engine
from canarias_site.services import sql_editor
from canarias_site.repositories.explore_entity import ExploreEntityRepository
from canarias_site.models.design_db import ContentItem, CalendarEvent, CalendarEventMonth, LiveSnapshot, ClimateObservation, StatisticalSnapshot, SeismicEvent, VolcanicReport
from canarias_site.utils.islands import VALID_ISLANDS


@asynccontextmanager
async def readonly_scope():
    async with writer_engine(database_url()).connect() as connection:
        async with connection.begin():
            await connection.execute(text("SET TRANSACTION READ ONLY"))
            await connection.execute(text("SET LOCAL statement_timeout = '6000ms'"))
            await connection.execute(text("SET LOCAL lock_timeout = '1000ms'"))
            async with async_sessionmaker(bind=connection, expire_on_commit=False)() as session:
                yield session


def clean(value, key="", depth=0):
    if any(k in key.lower() for k in ("password", "secret", "token", "credential", "api_key", "authorization")):
        return "[ukryte]"
    if depth > 10:
        return "[zagnieżdżone dane]"
    if isinstance(value, dict):
        return {str(k):clean(v,str(k),depth+1) for k,v in value.items()}
    if isinstance(value,(list,tuple)):
        result=[clean(v,"",depth+1) for v in value[:100]]
        return result + ([{"_note":f"Podgląd: 100 z {len(value)} elementów"}] if len(value)>100 else [])
    if isinstance(value,(datetime,date)):return value.isoformat()
    if isinstance(value,(UUID,Decimal)):return str(value)
    if isinstance(value,bytes):return f"[dane binarne: {len(value)} B]"
    if isinstance(value,str) and len(value)>12000:return value[:12000]+"… [skrócony podgląd komórki]"
    return value


def quote(name):
    return '"'+name.replace('"','""')+'"'


async def tables(session):
    rows=(await session.execute(text("""SELECT t.table_name, coalesce(c.reltuples,-1)::bigint AS estimated_rows
        FROM information_schema.tables t
        LEFT JOIN pg_namespace n ON n.nspname=t.table_schema
        LEFT JOIN pg_class c ON c.relnamespace=n.oid AND c.relname=t.table_name
        WHERE t.table_schema='design' AND t.table_type='BASE TABLE'
        ORDER BY t.table_name"""))).mappings().all()
    return [{"name":r["table_name"],"estimated_rows":max(-1,int(r["estimated_rows"]))} for r in rows
        if not re.search(r"secret|credential|password|token|session|^cc_worker|^cc_job|alembic",r["table_name"],re.I)]


async def table_rows(session, name, *, offset=0, limit=25, q="", column=None, sort=None, direction="asc", filters=None):
    allowed={r["name"] for r in await tables(session)}
    if name not in allowed:raise HTTPException(404,"Tabela nie jest dostępna w przeglądarce bazy strony.")
    columns=list((await session.execute(text("""SELECT column_name,data_type,udt_name,is_nullable
        FROM information_schema.columns WHERE table_schema='design' AND table_name=:name ORDER BY ordinal_position"""),{"name":name})).mappings())
    names={r["column_name"] for r in columns}
    if column and column not in names or sort and sort not in names:raise HTTPException(400,"Nieznana kolumna.")
    types={r["column_name"]:r["udt_name"] for r in columns}
    clauses=[];params={"limit":limit,"offset":offset}
    for i,(key,value) in enumerate((filters or {}).items()):
        if key not in names:raise HTTPException(400,"Nieznana kolumna filtra.")
        clauses.append(f"{quote(key)}=CAST(:filter_{i} AS uuid)" if types[key]=="uuid" else f"CAST({quote(key)} AS text)=:filter_{i}");params[f"filter_{i}"]=str(value)
    if q:
        column=column or next((r["column_name"] for r in columns if r["data_type"] in {"text","character varying"}),columns[0]["column_name"])
        clauses.append(f"CAST({quote(column)} AS text) ILIKE :q");params['q']='%'+q.replace('\\','\\\\').replace('%','\\%').replace('_','\\_')+'%'
    where=' WHERE '+' AND '.join(clauses) if clauses else ''
    primary=list((await session.execute(text("""SELECT a.attname FROM pg_index i
        JOIN pg_class t ON t.oid=i.indrelid JOIN pg_namespace n ON n.oid=t.relnamespace
        JOIN unnest(i.indkey) WITH ORDINALITY AS k(attnum,ord) ON true
        JOIN pg_attribute a ON a.attrelid=t.oid AND a.attnum=k.attnum
        WHERE n.nspname='design' AND t.relname=:name AND i.indisprimary ORDER BY k.ord"""),{"name":name})).scalars())
    order=[sort] if sort else primary or [columns[0]['column_name']]
    order += [key for key in primary if key not in order]
    order_sql=', '.join(quote(key)+(' DESC' if direction=='desc' else ' ASC')+' NULLS LAST' for key in order)
    selected=', '.join((f"left(ST_AsGeoJSON({quote(r['column_name'])},5),12000) AS {quote(r['column_name'])}" if r['udt_name']=='geometry' else quote(r['column_name'])) for r in columns)
    table='design.'+quote(name)
    count=int(await session.scalar(text('SELECT count(*) FROM '+table+where),params))
    rows=(await session.execute(text('SELECT '+selected+' FROM '+table+where+' ORDER BY '+order_sql+' LIMIT :limit OFFSET :offset'),params)).mappings().all()
    return {"schema":"design","table":name,"columns":[{"name":r['column_name'],"type":r['udt_name'],"nullable":r['is_nullable']=='YES'} for r in columns],"count":count,"offset":offset,"limit":limit,"rows":[clean(dict(r)) for r in rows],"readonly":True}


async def island_ids(session):
    importer=sql_editor.ExploreImporter(session)
    return {island:await importer.island_id(island) for island in VALID_ISLANDS}


async def coverage(session):
    ids=await island_ids(session);slugs={v:k for k,v in ids.items()}
    repo=ExploreEntityRepository(session);explore={}
    for catalog,count in await repo.find_catalog_stats():
        resource=catalog.removeprefix('explore_').replace('_','-')
        explore[resource]={"total":count,"islands":await repo.get_catalog_island_counts(catalog)}
    guide={}
    rows=(await session.execute(select(ContentItem.section,ContentItem.island_entity_id,ContentItem.publication_status,func.count()).where(ContentItem.module=='guide').group_by(ContentItem.section,ContentItem.island_entity_id,ContentItem.publication_status))).all()
    for section,island,status,count in rows:
        entry=guide.setdefault(section,{"total":0,"islands":{},"published":0,"hidden":0})
        entry['total']+=count;entry['islands'][slugs.get(island,'canarias')]=entry['islands'].get(slugs.get(island,'canarias'),0)+count
        if status in entry:entry[status]+=count
    calendar=[{"island":slugs.get(i,'canarias'),"month":m,"count":int(c)} for i,m,c in (await session.execute(select(CalendarEvent.island_entity_id,CalendarEventMonth.month,func.count()).join(CalendarEventMonth,CalendarEventMonth.calendar_event_id==CalendarEvent.id).group_by(CalendarEvent.island_entity_id,CalendarEventMonth.month).order_by(CalendarEventMonth.month.desc()))).all()]
    live=[{"resource":r.resource,"island":r.target,"available":r.available,"status":r.status,"updated_at":r.source_updated_at or r.ingested_at} for r in (await session.scalars(select(LiveSnapshot).order_by(LiveSnapshot.resource,LiveSnapshot.target))).all()]
    climate=[{"resource":r,"island":slugs.get(i,'canarias'),"count":int(c),"first":a,"last":b} for r,i,c,a,b in (await session.execute(select(ClimateObservation.resource,ClimateObservation.island_entity_id,func.count(),func.min(ClimateObservation.observed_at),func.max(ClimateObservation.observed_at)).group_by(ClimateObservation.resource,ClimateObservation.island_entity_id))).all()]
    statistics=[{"dataset":r.dataset,"island":r.target,"updated_at":r.source_updated_at or r.ingested_at} for r in (await session.scalars(select(StatisticalSnapshot))).all()]
    return clean({"islands":list(VALID_ISLANDS),"explore":explore,"guide":guide,"calendar":calendar,"live":live,"climate":climate,"statistics":statistics,"tables":await tables(session),"notes":"Liczby oznaczają rekordy w bazie, również ukryte. Zero nie jest błędem wczytywania ani potwierdzeniem kompletności źródeł."})


async def data_rows(session, section, resource, island, offset=0, limit=25, metric=None):
    if island not in (*VALID_ISLANDS,'global','canarias'):raise HTTPException(400,'Nieznana wyspa.')
    ids=await island_ids(session);island_id=ids.get(island);filters={}
    if section=='live':
        if resource=='air-quality':table='climate_observations';filters['resource']='air-quality'
        elif resource=='seismic':table='seismic_events'
        elif resource=='volcanic':table='volcanic_reports'
        else:
            table='live_snapshots';filters['resource']='beaches' if resource=='live-beaches' else resource
            if island_id:filters['target']=island
    elif section=='datos':
        if resource=='climate':table='climate_observations'
        elif resource=='geology':table='volcanic_reports' if metric=='volcanic' else 'seismic_events'
        else:table='statistical_snapshots'
    elif section=='explore':
        table={'titsa-stops':'cc_titsa_stops','titsa-routes':'cc_titsa_routes','tilp-routes':'cc_tilp_snapshot','airports':'places','ports':'places','ferries':'routes'}.get(resource)
        if not table:raise HTTPException(404,'Brak źródła odczytu.')
        if resource in {'airports','ports'}:filters['place_kind']='airport' if resource=='airports' else 'port'
        if resource=='ferries':filters['route_kind']='ferry'
    else:raise HTTPException(404,'Nieznany obszar danych.')
    available={x['name'] for x in await tables(session)}
    if table not in available:return {"table":table,"columns":[],"rows":[],"count":0,"readonly":True,"reason":"Brak tabeli źródłowej w bazie."}
    if table in {'climate_observations','seismic_events','statistical_snapshots'} and island_id:filters['island_entity_id']=island_id
    if table=='climate_observations' and metric:filters['resource']=metric
    if table=='statistical_snapshots':
        # All actual datasets stay visible; owner can inspect available targets,
        # rather than receiving a guessed or fabricated dataset name.
        datasets=list((await session.scalars(select(StatisticalSnapshot.dataset).where(StatisticalSnapshot.dataset.startswith(resource+':')).distinct().order_by(StatisticalSnapshot.dataset))).all())
        if not datasets:return {'table':table,'columns':[],'rows':[],'count':0,'readonly':True,'reason':'Ten dział nie ma jeszcze zasilonego zestawu danych w bazie. Nie jest to błąd wczytywania.'}
        if metric and metric not in datasets:raise HTTPException(400,'Nieznany zestaw dla tej sekcji.')
        filters['dataset']=metric or datasets[0]
    columns={r for r in (await session.execute(text("SELECT column_name FROM information_schema.columns WHERE table_schema='design' AND table_name=:name"),{'name':table})).scalars()}
    sort=next((key for key in ('observed_at','occurred_at','source_updated_at','last_seen_at','ingested_at') if key in columns),None)
    result=await table_rows(session,table,filters=filters,sort=sort,direction='desc',offset=offset,limit=limit)
    if table=='climate_observations':
        stmt=select(ClimateObservation.resource).distinct()
        if island_id:stmt=stmt.where(ClimateObservation.island_entity_id==island_id)
        result['metrics']=list((await session.scalars(stmt.order_by(ClimateObservation.resource))).all())
    if table=='statistical_snapshots':result['metrics']=datasets;result['metric']=filters['dataset']
    if section=='datos' and resource=='geology':result['metrics']=['seismic','volcanic']
    result['reason']='' if result['count'] else 'Brak rekordów dla wybranego źródła i wyspy. Zobacz Kompletność danych lub pełną tabelę w Bazie danych.'
    return result
