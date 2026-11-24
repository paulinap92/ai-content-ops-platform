"""Discovery creates review material; only explicit Studio publication changes news."""
from __future__ import annotations

import asyncio
import hashlib
import re
from datetime import datetime, timezone
from uuid import UUID, uuid4
from urllib.parse import urljoin, urlsplit
from xml.etree import ElementTree as ET

import httpx
from bs4 import BeautifulSoup
from fastapi import HTTPException
from sqlalchemy import select, text

from canarias_site.models.studio import StudioDocument
from canarias_site.services import studio
from canarias_site.services.news_fetch import public_url, fetch_page
from canarias_site.utils.islands import VALID_ISLANDS
from src.core.config import settings

CATEGORIES = {'transport':'Transport','environment':'Środowisko','culture':'Kultura','science':'Nauka','tourism':'Turystyka','society':'Społeczeństwo','other':'Inne'}
ISLANDS = {'canarias':'Całe Kanary','tenerife':'Tenerife','gran-canaria':'Gran Canaria','lanzarote':'Lanzarote','fuerteventura':'Fuerteventura','la-palma':'La Palma','la-gomera':'La Gomera','el-hierro':'El Hierro','la-graciosa':'La Graciosa'}
BUILTINS = [
    ('Gobierno de Canarias','canarias','https://www3.gobiernodecanarias.org/noticias/feed'),
    ('Webtenerife','tenerife','https://www.webtenerife.com/blogcorporativo/'),
    ('Turismo de Gran Canaria','gran-canaria','https://www.grancanaria.com/turismo/es/area-profesional/noticias/'),
    ('Turismo Lanzarote','lanzarote','https://corporativa.turismolanzarote.com/category/noticias/'),
    ('Visit La Graciosa','la-graciosa','https://www.visitlagraciosa.com/blog/'),
    ('Cabildo de La Palma','la-palma','https://www.cabildodelapalma.es/es/noticias'),
    ('Cabildo de La Gomera','la-gomera','https://www.lagomera.es/noticias/1'),
    ('Cabildo de El Hierro','el-hierro','https://www.elhierro.es/es/noticias'),
    ('Cabildo de Fuerteventura','fuerteventura','https://www.cabildofuer.es/cabildo/noticias/'),
]


def scope(island):
    if island not in VALID_ISLANDS and island != 'canarias':
        raise ValueError('Wybierz wyspę albo całe Kanary.')
    return island


def source_key(url):
    return hashlib.sha256(public_url(url).encode()).hexdigest()


def plain(value, limit=18000):
    return BeautifulSoup(str(value or ''), 'html.parser').get_text(' ', strip=True)[:limit]


def extract(page):
    soup = BeautifulSoup(page['html'], 'html.parser')
    for tag in soup(['script','style','nav','header','footer','aside','form','noscript']):
        tag.decompose()
    title = soup.find('h1') or soup.find('title')
    body = soup.find('article') or soup.find('main') or soup.body or soup
    paragraphs = [p.get_text(' ', strip=True) for p in body.select('h1,h2,h3,p,li')]
    material = '\n\n'.join(p for p in paragraphs if len(p) > 12)[:18000]
    if not material:
        raise ValueError('Nie znaleziono czytelnego tekstu. Wklej materiał ręcznie.')
    return {'title':plain(title.get_text() if title else urlsplit(page['url']).hostname, 250), 'source_url':page['url'], 'material':material}


def candidates(page, limit=10):
    raw = page['html']
    if isinstance(raw, str): raw = raw.encode()
    items = []
    if 'xml' in page['content_type'] or raw.lstrip().startswith((b'<?xml',b'<rss',b'<feed')):
        if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
            raise ValueError('Kanał zawiera niedozwolone deklaracje XML.')
        root = ET.fromstring(raw)
        for entry in root.iter():
            if entry.tag.split('}')[-1] not in {'item','entry'}: continue
            values = {child.tag.split('}')[-1]:child for child in entry}
            link = values.get('link')
            url = link.get('href') or link.text if link is not None else ''
            title = values.get('title')
            excerpt = next((values[k].text for k in ('description','summary','content') if k in values), '')
            items.append({'title':plain(title.text if title is not None else '',250),'source_url':urljoin(page['url'],url or ''),'excerpt':plain(excerpt,1200)})
    else:
        soup = BeautifulSoup(raw,'html.parser')
        article = soup.find('article')
        if article and article.find('h1'):
            material = extract(page)
            items.append({'title':material['title'],'source_url':page['url'],'excerpt':material['material'][:1200]})
        for tag in soup(['nav','header','footer','aside','script','style']):tag.decompose()
        for anchor in soup.select('h2 a[href],h3 a[href],article a[href]'):
            url = urljoin(page['url'],anchor.get('href',''))
            if urlsplit(url).hostname != urlsplit(page['url']).hostname:continue
            title = plain(anchor.get_text(),250)
            if len(title)>=10:items.append({'title':title,'source_url':url,'excerpt':''})
    unique = {}
    for item in items:
        try: item['source_url']=public_url(item['source_url'])
        except ValueError:continue
        if item['title']:unique.setdefault(item['source_url'],item)
    return list(unique.values())[:limit]


async def sources(session):
    values = {source_key(url):{'id':source_key(url),'name':name,'url':url,'island':island,'active':True,'version':0} for name,island,url in BUILTINS}
    rows = (await session.scalars(select(StudioDocument).where(StudioDocument.kind=='news-source'))).all()
    for row in rows:values[row.record_key]={'id':row.record_key,**row.draft,'version':row.version}
    return {'items':sorted(values.values(),key=lambda v:(v['island'],v['name']))}


async def save_source(session, name, url, island, active=True, expected_version=0):
    if not name.strip():raise ValueError('Wpisz nazwę źródła.')
    url=public_url(url);scope(island);key=source_key(url)
    await session.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),{'key':'news-source:'+key})
    row=await session.scalar(select(StudioDocument).where(StudioDocument.kind=='news-source',StudioDocument.record_key==key).with_for_update())
    if row and row.version!=expected_version:raise HTTPException(409,'Źródło zmieniło się. Odśwież listę.')
    if not row:
        if expected_version:raise HTTPException(409,'Odśwież listę źródeł.')
        row=StudioDocument(id=uuid4(),kind='news-source',island='canarias',resource='news',record_key=key,draft={},published=None,version=0,base_fingerprint=studio.fingerprint(None),status='source',updated_at=datetime.now(timezone.utc));session.add(row)
    row.draft={'name':name.strip(),'url':url,'island':island,'active':active};row.version+=1;row.updated_at=datetime.now(timezone.utc)
    await session.flush();await studio._revision(session,row,'news_source_update');await session.commit()
    return {'id':key,**row.draft,'version':row.version}


async def discover(url='', query='', island='canarias', limit=10):
    scope(island)
    if url:
        try:return {'items':candidates(await asyncio.to_thread(fetch_page,public_url(url)),limit),'method':'source'}
        except ET.ParseError as exc:raise ValueError('Nie można odczytać kanału RSS/Atom.') from exc
    if not query.strip():raise ValueError('Podaj temat albo link źródła.')
    if not settings.tavily_api_key:raise HTTPException(503,'Wyszukiwanie internetowe wymaga skonfigurowanego Tavily. Dodawanie ręczne i pobieranie z linku działają niezależnie.')
    async with httpx.AsyncClient(timeout=25) as client:
        try:
            response=await client.post('https://api.tavily.com/search',headers={'Authorization':'Bearer '+settings.tavily_api_key.get_secret_value()},json={'query':query+' '+ISLANDS[island],'max_results':limit,'search_depth':'basic','include_raw_content':False})
            response.raise_for_status();result=response.json()
        except (httpx.HTTPError,ValueError) as exc:raise HTTPException(502,'Wyszukiwanie nie powiodło się. Spróbuj ponownie albo podaj link.') from exc
    items=[]
    for row in result.get('results',[])[:limit]:
        try:url=public_url(row.get('url',''))
        except ValueError:continue
        items.append({'title':plain(row.get('title'),250),'source_url':url,'excerpt':plain(row.get('content'),1200)})
    return {'items':items,'method':'search'}


async def create_draft(session, *, title, description, summary, source_url, island, category, request_id):
    scope(island)
    if category not in CATEGORIES:raise ValueError('Wybierz kategorię wiadomości.')
    if source_url:source_url=public_url(source_url)
    origin=source_key(source_url) if source_url else str(request_id)
    identity={'kind':'news','island':island,'resource':'news','record_key':'new:noticias-'+origin}
    await session.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"),{'key':'noticias:'+island+':'+origin})
    row=await session.scalar(select(StudioDocument).where(StudioDocument.kind=='news',StudioDocument.island==island,StudioDocument.draft['_studio_news_origin'].as_string()==origin))
    if row:return {'record':studio.document_view(row),'existing':True}
    payload={'title':title.strip(),'summary':summary.strip(),'description':description.strip(),'source_url':source_url,'url':'','source':'Canarias Cerca','category':category,'topics':[category],'island':island,'language':'es','hidden':False,'show_links':True,'published_at':datetime.now(timezone.utc).isoformat(),'_studio_news_origin':origin}
    record=await studio.save_draft(session,identity,payload,0,studio.fingerprint(None))
    return {'record':record,'existing':False}


async def queue(session, island='canarias', status='', q='', offset=0):
    scope(island)
    rows=(await session.scalars(select(StudioDocument).where(StudioDocument.kind=='news').order_by(StudioDocument.updated_at.desc()))).all()
    rows=[r for r in rows if (island=='canarias' or r.island==island) and (not status or r.status==status) and (not q or q.casefold() in str(r.draft.get('title','')).casefold())]
    return {'items':[studio.document_view(row) for row in rows[offset:offset+50]],'count':len(rows),'offset':offset}
