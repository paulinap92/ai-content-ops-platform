import json
from contextlib import asynccontextmanager
from types import SimpleNamespace
import pytest
from src.domain.schemas import CanariasPublishRequest
from src.services import canarias_publisher

@pytest.mark.asyncio
async def test_ai_delivery_is_a_private_draft_in_the_same_editor_not_a_public_http_write(tmp_path,monkeypatch):
 package={"type":"guide","island":"tenerife","category":"food","slug":"papas-test","sources":[],"public_content":{"es":{"title":"Papas","summary":"Food","body_markdown":"Body"}}}
 path=tmp_path/"package.json";path.write_text(json.dumps(package))
 monkeypatch.setattr(canarias_publisher,"settings",SimpleNamespace(canarias_publish_enabled=True,content_language_codes=("es",)))
 calls=[]
 @asynccontextmanager
 async def scope():yield object()
 async def listing(*args):return {"items":[]}
 async def draft(session,identity,payload,version,fingerprint):
  calls.append((identity,payload,version));return {"id":"private-draft","status":"draft"}
 monkeypatch.setattr(canarias_publisher,"session_scope",scope)
 monkeypatch.setattr(canarias_publisher.studio,"list_records",listing)
 monkeypatch.setattr(canarias_publisher.studio,"save_draft",draft)
 result=await canarias_publisher.CanariasPublisherService().publish_file(file_path=str(path),request=CanariasPublishRequest(section="food"))
 assert result.status=="sent_as_draft" and len(calls)==1
 assert calls[0][0]["kind"]=="guide" and calls[0][2]==0
 assert calls[0][1]["content_ops_status"]=="draft"
