from pathlib import Path
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from canarias_site.api import data_monitor as monitor
from src.core.monitor_local import create_app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("CC_LOCAL_6G", "1")
    monkeypatch.setenv("CC_MONITOR_API_ORIGIN", "http://127.0.0.1:8067")
    monkeypatch.setenv(
        "CC_DATA_OPERATOR_TOKEN", "local-operator-credential-not-production-1234567890"
    )
    monkeypatch.setenv("EDITOR_TOKEN", "local-editor-credential-not-production-1234567890")
    monkeypatch.delenv("CC_MONITOR_MANUAL_ENABLED", raising=False)
    return TestClient(create_app(), base_url="http://127.0.0.1:8068")


@pytest.mark.parametrize(
    "origin",
    [
        "https://ep-any.neon.tech",
        "http://example.com",
        "http://user:secret@127.0.0.1",
        "http://127.0.0.1/private",
        "http://localhost?override=1",
    ],
)
def test_proxy_rejects_cloud_and_ambiguous_origins(client, monkeypatch, origin):
    monkeypatch.setenv("CC_MONITOR_API_ORIGIN", origin)
    with pytest.raises(HTTPException) as error:
        monitor.backend()
    assert error.value.status_code == 503


def test_authentication_and_session_without_ai_or_db(client, monkeypatch):
    async def overview():
        return {"items": [], "summary": {"jobs": 65}}

    monkeypatch.setattr(monitor, "proxy", overview)
    assert client.get("/site/api/data-monitor").status_code == 401
    token = "local-editor-credential-not-production-1234567890"
    assert (
        client.post(
            "/auth/login", json={"token": token}, headers={"Origin": "http://127.0.0.1:8068"}
        ).status_code
        == 200
    )
    assert client.get("/site/api/data-monitor").json()["summary"]["jobs"] == 65
    page = client.get("/site/monitor")
    assert page.status_code == 200 and "Monitor de datos" in page.text
    assert client.get("/site/assets/data-monitor.js").status_code == 200
    assert client.get("/site/assets/private.env").status_code == 404


def test_manual_is_off_and_cross_origin_is_rejected(client):
    headers = {"Authorization": "Bearer local-editor-credential-not-production-1234567890"}
    route = "/site/api/data-monitor/jobs/live-weather/requests"
    assert (
        client.post(route, headers=headers, json={"idempotency_key": "disabled"}).status_code == 403
    )
    assert (
        client.post(
            route,
            headers={**headers, "Origin": "https://untrusted.example"},
            json={"idempotency_key": "disabled"},
        ).status_code
        == 403
    )


def test_proxy_outage_redacted_no_fallback(client, monkeypatch):
    import httpx

    def broken(*args, **kwargs):
        raise httpx.ConnectError("secret local password")

    monkeypatch.setattr(monitor.httpx, "AsyncClient", broken)
    response = client.get(
        "/site/api/data-monitor",
        headers={"Authorization": "Bearer local-editor-credential-not-production-1234567890"},
    )
    assert response.status_code == 503 and "secret" not in response.text


def test_no_polling_source_download_or_operator_token_in_browser():
    script = (Path(__file__).parents[1] / "canarias_site/studio/data-monitor.js").read_text()
    assert "setInterval(" not in script and "CC_DATA_OPERATOR_TOKEN" not in script
    assert "fetch('/site/api/data-monitor" in script
