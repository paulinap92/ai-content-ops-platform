"""Restart, persistence and isolation checks using disposable CI services."""
import json
import os
import time
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage

URL=os.getenv('CC_SQL_TEST_URL') or os.getenv('CC_SQL_TEST_DATABASE_URL')
pytestmark=pytest.mark.skipif(not URL,reason='Disposable PostgreSQL/Mongo services required')
TOKEN='isolated-editor-test-credential-1234567890'


def test_langgraph_review_resumes_after_restart_and_exports_survive_file_loss(tmp_path,monkeypatch):
    from src.agent import nodes
    from src.core import config
    from src.domain.schemas import ContentCreateRequest
    from app import app
    languages={lang:{'title':'Papas test','summary':'A test','body_markdown':'## Verified test'} for lang in ('es','en','pl')}
    package={'type':'guide','island':'tenerife','category':'food','slug':'restart-'+uuid4().hex,'sources':[], 'public_content':languages}
    responses=iter(['Verified facts','## Proposed article',json.dumps(package)])
    class Model:
        def invoke(self,messages): return AIMessage(content=next(responses))
    monkeypatch.setattr(nodes,'create_model',lambda *args,**kwargs:Model())
    configured=config.settings.model_copy(update={'output_dir':str(tmp_path)})
    monkeypatch.setattr(nodes,'settings',configured)
    monkeypatch.setattr(config,'settings',configured)
    def wait(client,thread,status):
        for _ in range(100):
            result=client.get('/api/v1/content/'+thread)
            assert result.status_code==200,result.text
            data=result.json()
            if data['status']==status:return data
            assert data['status']!='error',data
            time.sleep(.05)
        raise AssertionError('Graph did not reach '+status)
    with TestClient(app,base_url='https://editor.test') as client:
        assert client.get('/health/ready').json()=={'status':'ok'}
        assert client.get('/api/v1/content').status_code==401
        assert client.post('/auth/login',json={'token':TOKEN}).status_code==200
        started=client.post('/api/v1/content',json={'topic':'Restart test','source_text':'Trusted source facts'})
        assert started.status_code==202,started.text
        thread=started.json()['thread_id']
        assert wait(client,thread,'awaiting_review')['outline']
    # New application lifespan, new pool and new checkpointer.
    with TestClient(app,base_url='https://editor.test') as client:
        assert client.get('/health/ready').status_code==200
        assert client.post('/auth/login',json={'token':TOKEN}).status_code==200
        assert wait(client,thread,'awaiting_review')['outline']
        result=client.post('/api/v1/content/'+thread+'/decision',json={'action':'approve'})
        assert result.status_code==202,result.text
        data=wait(client,thread,'ready')
        if data.get('file_path'):Path(data['file_path']).unlink(missing_ok=True)
        exported=client.get('/api/v1/content/'+thread+'/file')
        assert exported.status_code==200,exported.text
        assert exported.json()['slug']==package['slug']
        delivered=client.post('/api/v1/content/'+thread+'/publish-to-canarias',json={'section':'food','language':'es'})
        assert delivered.status_code==200,delivered.text
        assert delivered.json()['backend_response']['status']=='draft'
        records=client.get('/site/api/records',params={'kind':'guide','island':'tenerife','resource':'food','q':package['slug']})
        item=next(r for r in records.json()['items'] if r['draft'].get('slug')==package['slug'])
        assert item['published'] is None
        assert client.get('/site/api/options').json()['sections']['datos']=='Datos'
        assert client.get('/api/v1/events/sources').status_code==200
        assert client.get('/api/studio/database/collections').status_code==200
    # The public-site application and refresh workers are not imported or started.
    import sys
    assert 'app.main' not in sys.modules
    assert not any('data_refresh_scheduler' in m for m in sys.modules)


@pytest.mark.asyncio
async def test_private_postgres_documents_filter_sort_conflict_and_durability():
    from src.core.config import settings
    if settings.editor_storage!='postgres':pytest.skip('Mongo uses the existing Beanie persistence')
    from src.core import document_store as store
    from src.domain.documents import ContentDocument
    from src.services.exceptions import ConflictException
    await store.initialize(URL)
    thread=str(uuid4())
    try:
        doc=ContentDocument(thread_id=thread,topic='Persistence test')
        await doc.insert()
        stale=await ContentDocument.find_one(ContentDocument.thread_id==thread)
        doc.status='awaiting_review';await doc.save_changes()
        stale.status='wrong'
        with pytest.raises(ConflictException):await stale.save()
        values=await ContentDocument.find({'thread_id':thread}).sort([('created_at',-1)]).limit(1).to_list()
        assert values[0].status=='awaiting_review'
    finally:await store.shutdown()
    await store.initialize(URL)
    try:
        persisted=await ContentDocument.find_one(ContentDocument.thread_id==thread)
        assert persisted.status=='awaiting_review'
        await persisted.delete()
        assert await ContentDocument.find_one(ContentDocument.thread_id==thread) is None
    finally:await store.shutdown()
