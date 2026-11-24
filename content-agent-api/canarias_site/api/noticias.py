"""Authenticated Noticias acquisition and private drafts in the existing Studio."""
import asyncio
from uuid import UUID

from fastapi import APIRouter, Query
from pydantic import BaseModel, ConfigDict, Field, model_validator

from canarias_site.api.studio import Session, translate_error
from canarias_site.services import news_desk as service
from canarias_site.services.news_fetch import public_url, fetch_page
from src.core.config import settings

router=APIRouter(prefix='/site/api/noticias',tags=['noticias-studio'])

class Input(BaseModel):
    model_config=ConfigDict(extra='forbid')

class Source(Input):
    name:str=Field(min_length=1,max_length=150)
    url:str=Field(min_length=8,max_length=2048)
    island:str='canarias'
    active:bool=True
    expected_version:int=Field(default=0,ge=0)

class Discover(Input):
    url:str=Field(default='',max_length=2048)
    query:str=Field(default='',max_length=300)
    island:str='canarias'
    limit:int=Field(default=10,ge=1,le=20)
    @model_validator(mode='after')
    def one_input(self):
        if bool(self.url)==bool(self.query.strip()):raise ValueError('Podaj temat albo jeden adres źródła.')
        return self

class Extract(Input):
    url:str=Field(min_length=8,max_length=2048)

class Draft(Input):
    title:str=Field(min_length=1,max_length=250)
    summary:str=Field(default='',max_length=500)
    description:str=Field(default='',max_length=40000)
    source_url:str=Field(default='',max_length=2048)
    island:str='canarias'
    category:str='other'
    request_id:UUID

@router.get('/options')
async def options(session:Session):
    return {'islands':service.ISLANDS,'categories':service.CATEGORIES,'ai_enabled':settings.ai_configured,'search_enabled':bool(settings.tavily_api_key)}

@router.get('/sources')
async def sources(session:Session):
    return await service.sources(session)

@router.post('/sources')
async def source(payload:Source,session:Session):
    try:return await service.save_source(session,**payload.model_dump())
    except Exception as exc:translate_error(exc)

@router.post('/discover')
async def discover(payload:Discover,session:Session):
    try:return await service.discover(**payload.model_dump())
    except Exception as exc:translate_error(exc)

@router.post('/extract')
async def extract(payload:Extract,session:Session):
    try:return service.extract(await asyncio.to_thread(fetch_page,public_url(payload.url)))
    except Exception as exc:translate_error(exc)

@router.post('/draft')
async def draft(payload:Draft,session:Session):
    try:return await service.create_draft(session,**payload.model_dump())
    except Exception as exc:translate_error(exc)

@router.get('/queue')
async def queue(session:Session,island:str='canarias',status:str='',q:str=Query('',max_length=200),offset:int=Query(0,ge=0)):
    try:return await service.queue(session,island,status,q,offset)
    except Exception as exc:translate_error(exc)
