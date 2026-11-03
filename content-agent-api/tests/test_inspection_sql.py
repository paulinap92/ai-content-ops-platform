"""Real PostgreSQL inspection against CI fixtures, never the hosted database."""
import os
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from fastapi import HTTPException
from canarias_site.services import inspection

pytestmark=pytest.mark.skipif(not(os.getenv('CC_SQL_TEST_URL') or os.getenv('CC_SQL_TEST_DATABASE_URL')),reason='Disposable PostgreSQL required')

@pytest.mark.asyncio
async def test_browser_is_read_only_and_cannot_choose_sql_identifiers():
    async with inspection.readonly_scope() as db:
        assert await db.scalar(text('SHOW transaction_read_only'))=='on'
        assert 'entities' in {t['name'] for t in await inspection.tables(db)}
        assert not any(t['name'].startswith('cc_worker') for t in await inspection.tables(db))
        first=await inspection.table_rows(db,'entities',limit=2)
        second=await inspection.table_rows(db,'entities',limit=2,offset=2)
        assert first['readonly'] and len(first['rows'])==2 and first['count']>=8
        assert not {r['id'] for r in first['rows']} & {r['id'] for r in second['rows']}
        filtered=await inspection.table_rows(db,'entities',q='SQL test',column='canonical_name',limit=5,sort='canonical_name')
        assert filtered['rows'] and all('SQL test' in r['canonical_name'] for r in filtered['rows'])
        for name in ['entities; DROP TABLE design.entities','cc_worker_fence','pg_authid']:
            with pytest.raises(HTTPException):await inspection.table_rows(db,name)
        with pytest.raises(HTTPException):await inspection.table_rows(db,'entities',sort='id;DROP TABLE x')
        assert (await inspection.table_rows(db,'entities',q="';DROP TABLE design.entities;--",column='canonical_name'))['count']==0
    with pytest.raises(DBAPIError):
        async with inspection.readonly_scope() as db:
            await db.execute(text("UPDATE design.entities SET canonical_name='forbidden' WHERE false"))
    from canarias_site.services.studio_auth import writer_engine,database_url
    async with writer_engine(database_url()).connect() as connection:
        assert await connection.scalar(text('SHOW transaction_read_only'))=='off', 'read-only browsing must not change the write pool session defaults'

@pytest.mark.asyncio
async def test_coverage_and_live_use_canonical_rows_without_geometry_audits():
    async with inspection.readonly_scope() as db:
        data=await inspection.coverage(db)
        assert len(data['islands'])==8
        assert data['explore']['food-producers']['total']>=8
        assert len(data['explore']['food-producers']['islands'])==8
        assert data['guide']['history']['islands']['tenerife']>=1
        assert any(r['resource']=='weather' for r in data['live'])
        live=await inspection.data_rows(db,'live','weather','tenerife')
        assert live['count']==1 and live['rows'][0]['target']=='tenerife' and live['readonly']
        climate=await inspection.data_rows(db,'datos','climate','tenerife')
        assert climate['table']=='climate_observations' and climate['readonly']
        assert (await inspection.data_rows(db,'datos','economy','tenerife'))['count']==0
        with pytest.raises(HTTPException):await inspection.data_rows(db,'datos','climate','unknown')
        with pytest.raises(HTTPException):await inspection.data_rows(db,'not-allowed','weather','tenerife')

def test_inspection_redacts_credentials_but_preserves_identifiers_and_dates():
    from uuid import UUID
    assert inspection.clean({'id':UUID(int=1),'api_key':'private'})=={'id':str(UUID(int=1)),'api_key':'[ukryte]'}
