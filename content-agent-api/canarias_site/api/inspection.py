"""Private inspection routes use an enforced read-only SQL transaction."""
from datetime import date
from fastapi import APIRouter, Depends, Query, Request, HTTPException
from sqlalchemy.exc import DBAPIError
from src.core.auth import require_editor
from canarias_site.services import inspection

router=APIRouter(prefix='/site/api',tags=['editor-inspection'])

async def session(request:Request):
    require_editor(request)
    try:
        async with inspection.readonly_scope() as db:yield db
    except DBAPIError as exc:
        raise HTTPException(503,'Odczyt danych przekroczył limit lub baza jest chwilowo niedostępna. Zawęź filtr i spróbuj ponownie.') from exc

@router.get('/database/tables')
async def tables(db=Depends(session)):
    return {'schema':'design','tables':await inspection.tables(db),'readonly':True}

@router.get('/database/tables/{name}')
async def rows(name:str,offset:int=Query(0,ge=0,le=10000000),limit:int=Query(25,ge=1,le=100),q:str=Query('',max_length=200),column:str|None=None,sort:str|None=None,direction:str=Query('asc',pattern='^(asc|desc)$'),db=Depends(session)):
    return await inspection.table_rows(db,name,offset=offset,limit=limit,q=q,column=column,sort=sort,direction=direction)

@router.get('/coverage')
async def coverage(db=Depends(session)):
    return await inspection.coverage(db)

@router.get('/data')
async def data(section:str,resource:str,island:str='global',offset:int=Query(0,ge=0,le=10000000),limit:int=Query(25,ge=1,le=100),metric:str|None=Query(None,max_length=200),db=Depends(session)):
    return await inspection.data_rows(db,section,resource,island,offset,limit,metric)


@router.get('/analytics/options')
async def analytics_options(island:str='global',db=Depends(session)):
    from canarias_site.services import analytics
    return await analytics.options(db,island)

@router.get('/analytics/series')
async def analytics_series(island:str='global',resource:str='weather',metric:str='temperature',point_id:str=Query('',max_length=200),date_from:date|None=None,date_to:date|None=None,resolution:str=Query('day',pattern='^(day|hour)$'),db=Depends(session)):
    from canarias_site.services import analytics
    return await analytics.series(db,island,resource,metric,point_id,date_from,date_to,resolution)
