"""Authenticated Lugares control plane, using the editor's existing session/origin guard."""
from typing import Annotated, Literal
from uuid import UUID
from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession
from canarias_site.services.studio_auth import studio_session
from canarias_site.services import lugares
from canarias_site.api.studio import ASSETS

router = APIRouter(tags=['lugares-editor'])
Session = Annotated[AsyncSession, Depends(studio_session)]


class Source(BaseModel):
    model_config = ConfigDict(extra='forbid')
    url: str = Field(max_length=2048)
    title: str = Field(min_length=1, max_length=500)


class Version(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_fingerprint: str = Field(pattern='^[0-9a-f]{64}$')
    editor: str = Field(min_length=2, max_length=150, pattern=r'.*\S.*')


class Draft(Version):
    short_description: str = Field(min_length=1, max_length=220)
    detailed_description: str = Field(min_length=1, max_length=6000)
    sources: list[Source] = Field(min_length=1, max_length=12)


class Action(Version):
    action: Literal['verify', 'approve', 'publish']
    facts_checked: bool = False
    sources_checked: bool = False
    sentence_count_checked: bool = False
    style_approved: bool = False


@router.get('/site/lugares', include_in_schema=False)
async def page():
    return FileResponse(ASSETS / 'lugares.html', headers={'Cache-Control': 'no-store'})


@router.get('/site/api/lugares')
async def records(session: Session, island: str = Query('', max_length=50), q: str = Query('', max_length=200),
                  state: Literal['', 'blocked', 'published', 'draft', 'approved'] = '',
                  offset: int = Query(0, ge=0), limit: int = Query(50, ge=1, le=50)):
    return await lugares.records(session, island, q, state, offset, limit)


@router.get('/site/api/lugares/{entity_id}/history')
async def history(entity_id: UUID, session: Session):
    return await lugares.history(session, entity_id)


@router.put('/site/api/lugares/{entity_id}')
async def save(entity_id: UUID, payload: Draft, session: Session):
    return await lugares.save(session, entity_id, payload)


@router.post('/site/api/lugares/{entity_id}/actions')
async def action(entity_id: UUID, payload: Action, session: Session):
    return await lugares.action(session, entity_id, payload)
