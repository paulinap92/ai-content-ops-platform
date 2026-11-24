from contextlib import asynccontextmanager
from types import SimpleNamespace
from uuid import uuid4
import json
import os
import socket

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from canarias_site.services import news_desk as desk, news_fetch, studio
from canarias_site.models.design_db import NewsItem
from canarias_site.models.studio import StudioDocument
from canarias_site.api.noticias import router
from canarias_site.services.studio_auth import studio_session
from src.core.auth import authentication
from src.services import canarias_publisher
from src.domain.schemas import CanariasPublishRequest
from tests.test_site_sql import session


def test_source_extraction_rss_atom_and_html_are_review_material_only():
    rss=b'<rss><channel><item><title>Nuevo transporte</title><link>https://example.com/news/1</link><description>&lt;p&gt;Material RSS&lt;/p&gt;</description></item><item><title>Duplicate</title><link>https://example.com/news/1</link></item></channel></rss>'
    rows=desk.candidates({'url':'https://example.com/feed','html':rss,'content_type':'application/rss+xml'})
    assert rows==[{'title':'Nuevo transporte','source_url':'https://example.com/news/1','excerpt':'Material RSS'}]
    atom=b'<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Noticias de cultura</title><link href="https://example.com/culture"/><summary>Texto</summary></entry></feed>'
    assert desk.candidates({'url':'https://example.com/feed','html':atom,'content_type':'application/atom+xml'})[0]['title']=='Noticias de cultura'
    page={'url':'https://example.com/news','html':'<main><h1>Titulo</h1><script>SECRET</script><p>Un texto para preparar una noticia.</p><h2><a href="/detail">Otro titular importante</a></h2><h2><a href="http://127.0.0.1/private">Private</a></h2></main>','content_type':'text/html'}
    assert 'SECRET' not in desk.extract(page)['material']
    assert desk.candidates(page)[0]['source_url']=='https://example.com/detail'
    with pytest.raises(ValueError):desk.candidates({'url':'https://example.com/','html':b'<!DOCTYPE rss [<!ENTITY x "bad">]><rss/>','content_type':'application/xml'})


@pytest.mark.parametrize('url',['http://127.0.0.1/','http://[::1]/','http://169.254.169.254/latest','https://user:pass@example.com/','file:///etc/passwd','https://foo.internal/','https://example.com:5432/'])
def test_private_urls_are_not_fetchable(url):
    with pytest.raises(ValueError):news_fetch.public_url(url)


def test_fetch_pins_validated_address_and_checks_redirects(monkeypatch):
    monkeypatch.setattr(socket,'getaddrinfo',lambda *a,**k:[(socket.AF_INET,socket.SOCK_STREAM,6,'',('127.0.0.1',443))])
    with pytest.raises(ValueError):news_fetch.public_address('evil.example',443)
    calls=[]
    class Response:
        status=302
        def getheader(self,key,default=None):return 'http://127.0.0.1/private' if key=='Location' else default
    class Connection:
        def __init__(self,*a,**k):pass
        def request(self,*a,**k):calls.append(a)
        def getresponse(self):return Response()
        def close(self):pass
    monkeypatch.setattr(news_fetch,'PinnedHTTPS',Connection)
    with pytest.raises(ValueError):news_fetch.fetch_page('https://example.com/news')
    assert len(calls)==1


def test_https_connection_uses_validated_ip_and_original_tls_name(monkeypatch):
    calls=[]
    monkeypatch.setattr(news_fetch,'public_address',lambda host,port:'93.184.216.34')
    fake_socket=object()
    monkeypatch.setattr(socket,'create_connection',lambda address,timeout:(calls.append(address) or fake_socket))
    connection=news_fetch.PinnedHTTPS('example.com',timeout=12)
    connection._context=SimpleNamespace(wrap_socket=lambda sock,server_hostname:(calls.append(server_hostname) or sock))
    connection.connect()
    assert calls==[('93.184.216.34',443),'example.com']


def test_news_desk_endpoints_require_the_existing_login(monkeypatch):
    monkeypatch.setenv('EDITOR_TOKEN','isolated-editor-test-credential-1234567890')
    app=FastAPI();app.middleware('http')(authentication);app.include_router(router)
    app.dependency_overrides[studio_session]=lambda:None
    with TestClient(app,base_url='https://editor.example') as client:
        for path in ['options','sources','queue']:
            assert client.get('/site/api/noticias/'+path).status_code==401
        for path in ['draft','discover','extract','sources']:
            assert client.post('/site/api/noticias/'+path,json={}).status_code==401
        token={'Authorization':'Bearer isolated-editor-test-credential-1234567890'}
        assert client.get('/site/api/noticias/options',headers=token).status_code==200
        assert client.post('/site/api/noticias/discover',json={'url':'https://example.com/','query':'test'},headers=token).status_code==422


@pytest.mark.asyncio
@pytest.mark.skipif(not os.getenv('CC_SQL_TEST_URL'),reason='Disposable PostgreSQL required')
async def test_discover_manual_draft_publication_visibility_and_deduplication(session,monkeypatch):
    url='https://example.com/news/'+uuid4().hex
    monkeypatch.setattr(desk,'fetch_page',lambda value:{'url':value,'html':f'<rss><channel><item><title>Una noticia propia</title><link>{url}</link><description>Material para redactar</description></item></channel></rss>'.encode(),'content_type':'application/rss+xml'})
    source=await desk.save_source(session,'Custom source',url,'tenerife')
    assert source['version']==1 and source['active']
    source=await desk.save_source(session,'Custom source',url,'tenerife',False,1)
    assert source['version']==2 and not source['active']
    assert any(r['id']==source['id'] for r in (await desk.sources(session))['items'])
    proposal=(await desk.discover(url=url,island='tenerife'))['items'][0]
    assert await session.scalar(select(NewsItem).where(NewsItem.url==url)) is None
    inputs={'title':proposal['title'],'description':'## Información\n\nUna noticia escrita por la redacción.','summary':'Nuestro resumen.','source_url':url,'island':'tenerife','category':'transport','request_id':uuid4()}
    saved=await desk.create_draft(session,**inputs)
    assert saved['record']['published'] is None
    again=await desk.create_draft(session,**{**inputs,'description':'Do not overwrite'})
    assert again['existing'] and again['record']['id']==saved['record']['id']
    assert again['record']['draft']['description']==inputs['description']
    pub=await studio.publish(session,saved['record']['id'],saved['record']['version'])
    key=pub['identity']['record_key']
    assert pub['published']['description']==inputs['description']
    assert '_studio_news_origin' not in pub['published']
    assert pub['published']['url']=='' and pub['published']['source_url']==url
    assert pub['published']['cc_studio_links']['links'][0]['url']==url
    assert (await desk.create_draft(session,**inputs))['record']['identity']['record_key']==key
    hidden=await studio.save_draft(session,pub['identity'],{**pub['draft'],'hidden':True},pub['version'],pub['base_fingerprint'])
    hidden=await studio.publish(session,hidden['id'],hidden['version'])
    assert hidden['published']['hidden']
    rows=(await desk.queue(session,'tenerife','hidden'))['items']
    assert any(r['id']==pub['id'] for r in rows)
    assert not (await desk.queue(session,'el-hierro'))['items']


@pytest.mark.asyncio
@pytest.mark.skipif(not os.getenv('CC_SQL_TEST_URL'),reason='Disposable PostgreSQL required')
async def test_ai_draft_cannot_publish_empty_material_and_delivers_into_noticias(session,tmp_path,monkeypatch):
    saved=(await desk.create_draft(session,title='Noticia con AI',description='',summary='',source_url='',island='canarias',category='science',request_id=uuid4()))['record']
    with pytest.raises(ValueError,match='treść'):await studio.publish(session,saved['id'],saved['version'])
    package={'type':'news','island':'tenerife','category':'news','slug':'ai-noticia','sources':[],'public_content':{'es':{'title':'Título revisado','summary':'Resumen verificado','body_markdown':'Cuerpo para revisar.'}}}
    path=tmp_path/'news.json';path.write_text(json.dumps(package))
    @asynccontextmanager
    async def scope():yield session
    monkeypatch.setattr(canarias_publisher,'session_scope',scope)
    monkeypatch.setattr(canarias_publisher,'settings',SimpleNamespace(canarias_publish_enabled=True,content_language_codes=('es',)))
    target={'identity':saved['identity'],'payload':saved['draft'],'version':saved['version'],'base_fingerprint':saved['base_fingerprint']}
    result=await canarias_publisher.CanariasPublisherService().publish_file(file_path=str(path),request=CanariasPublishRequest(section='nature'),site_target=target)
    row=result.backend_response
    assert row['identity']['kind']=='news' and row['identity']['island']=='canarias' and row['published'] is None
    assert row['draft']['title']=='Título revisado' and row['draft']['category']=='science'
    assert row['draft']['description']=='Cuerpo para revisar.'
    published=await studio.publish(session,row['id'],row['version'])
    assert published['published']['title']=='Título revisado'
