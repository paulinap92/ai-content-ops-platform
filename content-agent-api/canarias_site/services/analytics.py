"""Bounded time series for the private editor; source values are never altered."""
from datetime import date, datetime, time, timedelta, timezone
from fastapi import HTTPException
from sqlalchemy import text
from canarias_site.services.inspection import island_ids, clean

METRICS={
 'weather':{'temperature':['Temperatura','°C'],'apparent_temperature':['Temperatura odczuwalna','°C'],'humidity':['Wilgotność','%'],'wind_speed':['Wiatr','km/h'],'precipitation':['Opady — średnia zapisanych pomiarów','mm']},
 'air-quality':{'pm10':['PM10','µg/m³'],'pm25':['PM2.5','µg/m³'],'dust':['Pył','µg/m³'],'aod':['AOD','']},
 'seismic':{'magnitude':['Magnituda',''],'depth_km':['Głębokość','km']}}

async def options(db,island):
 ids=await island_ids(db)
 if island not in {*ids,'global','canarias'}:raise HTTPException(400,'Nieznana wyspa.')
 params={};where=''
 if island in ids:where='WHERE island_entity_id=CAST(:island AS uuid)';params['island']=str(ids[island])
 rows=(await db.execute(text(f'''SELECT DISTINCT ON (resource,point_id) resource,point_id,payload->>'name' AS name,observed_at,latitude,longitude
 FROM design.climate_observations {where} ORDER BY resource,point_id,observed_at DESC'''),params)).mappings().all()
 return clean({'points':[dict(r) for r in rows],'metrics':METRICS})

async def series(db,island,resource,metric,point_id='',date_from=None,date_to=None,resolution='day'):
 if resource not in METRICS or metric not in METRICS[resource]:raise HTTPException(400,'Nieznana seria pomiarowa.')
 end=date_to or datetime.now(timezone.utc).date();start=date_from or end-timedelta(days=30)
 if start>end or (end-start).days>3660 or resolution=='hour' and (end-start).days>31:raise HTTPException(400,'Wybierz poprawny zakres: do 10 lat dziennie lub 31 dni godzinowo.')
 ids=await island_ids(db)
 if island not in {*ids,'global','canarias'}:raise HTTPException(400,'Nieznana wyspa.')
 params={'start':datetime.combine(start,time(),timezone.utc),'end':datetime.combine(end+timedelta(days=1),time(),timezone.utc),'metric':metric,'resource':resource,'point':point_id}
 clauses=['observed_at>=:start','observed_at<:end','resource=:resource']
 if island in ids:clauses.append('island_entity_id=CAST(:island AS uuid)');params['island']=str(ids[island])
 if point_id:clauses.append('point_id=:point')
 if resource=='seismic':
  clauses=['occurred_at>=:start','occurred_at<:end']+[c for c in clauses if c.startswith('island_entity_id')]
  if metric=='depth_km':column='depth_km'
  else:column='magnitude'
  sql=f'SELECT occurred_at AS time,{column} AS value,1 AS samples FROM design.seismic_events WHERE '+ ' AND '.join(clauses)+' ORDER BY occurred_at LIMIT 10001'
 else:
  bucket='hour' if resolution=='hour' else 'day'
  sql=f'''SELECT date_trunc('{bucket}',observed_at AT TIME ZONE 'UTC') AT TIME ZONE 'UTC' AS time,
  avg(CASE WHEN jsonb_typeof(payload->:metric)='number' THEN (payload->>:metric)::double precision END) AS value,
  count(*) AS samples FROM design.climate_observations WHERE {' AND '.join(clauses)} GROUP BY 1 ORDER BY 1 LIMIT 10001'''
 rows=(await db.execute(text(sql),params)).mappings().all()
 if len(rows)>10000:raise HTTPException(400,'Zbyt wiele punktów. Zawęź zakres lub wybierz miejscowość.')
 title,unit=METRICS[resource][metric]
 return clean({'resource':resource,'metric':metric,'title':title,'unit':unit,'point_id':point_id,'date_from':start,'date_to':end,'resolution':resolution,'rows':[dict(r) for r in rows],'readonly':True,'aggregation':'Zdarzenia' if resource=='seismic' else 'Średnia zapisanych pomiarów w przedziale UTC. Braki pozostają przerwami; modelowe dane nie są pomiarami stacji.'})
