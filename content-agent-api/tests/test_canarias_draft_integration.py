import json
from types import SimpleNamespace

import httpx
import pytest
from pydantic import SecretStr

from src.domain.schemas import CanariasPublishRequest
from src.services import canarias_publisher


@pytest.mark.asyncio
async def test_ai_package_saves_private_draft_and_never_calls_legacy_publish(tmp_path,monkeypatch):
    package={"type":"guide","island":"tenerife","category":"food","slug":"papas-test","sources":[],"public_content":{"es":{"title":"Papas","summary":"Food","body_markdown":"Body"}}}
    path=tmp_path/"package.json";path.write_text(json.dumps(package))
    monkeypatch.setattr(canarias_publisher,"settings",SimpleNamespace(canarias_publish_enabled=True,canarias_api_url="https://backend.example",canarias_editor_token=SecretStr("isolated-token"),content_language_codes=("es",)))
    calls=[];original=httpx.AsyncClient
    def handler(request):
        calls.append(request)
        if request.method=="GET":return httpx.Response(200,json={"items":[]})
        return httpx.Response(200,json={"id":"private-draft","status":"draft","version":1})
    monkeypatch.setattr(canarias_publisher.httpx,"AsyncClient",lambda **kwargs:original(transport=httpx.MockTransport(handler)))
    result=await canarias_publisher.CanariasPublisherService().publish_file(file_path=str(path),request=CanariasPublishRequest(section="food"))
    assert result.status=="sent_as_draft"
    assert [r.method for r in calls]==["GET","PUT"]
    assert calls[1].url.path=="/studio/api/draft"
    payload=json.loads(calls[1].content)
    assert payload["expected_version"]==0 and payload["identity"]["kind"]=="guide"
    assert payload["payload"]["content_ops_status"]=="draft"
    assert all(r.url.path!="/api/editor/content" for r in calls)
