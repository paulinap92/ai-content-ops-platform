from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.v1 import site_editor


def test_local_bridge_forwards_only_editor_paths_and_keeps_token_server_side(monkeypatch):
    monkeypatch.setattr(site_editor,"settings",SimpleNamespace(canarias_api_url="https://backend.example",canarias_editor_token=SimpleNamespace(get_secret_value=lambda:"private-studio-key")))
    requests=[]
    original=httpx.AsyncClient
    def handler(request):
        requests.append(request)
        return httpx.Response(200,json={"islands":["tenerife"]})
    monkeypatch.setattr(site_editor.httpx,"AsyncClient",lambda **kwargs:original(transport=httpx.MockTransport(handler)))
    app=FastAPI();app.include_router(site_editor.router)
    with TestClient(app,client=("127.0.0.1",50000)) as client:
        response=client.get("/site/api/options")
        assert response.status_code==200 and response.json()=={"islands":["tenerife"]}
        assert "private-studio-key" not in response.text
        assert requests[0].headers["authorization"]=="Bearer private-studio-key"
        assert client.get("/site/api/admin/sql").status_code==404
        assert len(requests)==1


def test_remote_client_cannot_use_local_editor_bridge():
    app=FastAPI();app.include_router(site_editor.router)
    with TestClient(app,client=("203.0.113.10",50000)) as client:
        assert client.get("/site/api/options").status_code==403
