"""Private social workflow: real disposable stores, no provider publication."""
import os

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

from src.services.social_service import SocialDraft, channel_text, validate_ready

TOKEN = "isolated-editor-test-credential-1234567890"


@pytest.mark.parametrize("change", [
    {"title": "   "}, {"caption": "\n "}, {"platforms": ["instagram", "instagram"]},
    {"platforms": ["unknown"]}, {"image_url": "javascript:alert(1)"},
    {"image_url": "https://user:password@example.test/image.jpg"},
    {"captions": {"unexpected": "text"}}, {"captions": {"whatsapp": "x" * 4001}},
])
def test_invalid_social_drafts_are_rejected(change):
    with pytest.raises(ValidationError):
        SocialDraft.model_validate({"title": "Post", "caption": "Contenido", "platforms": ["whatsapp"], **change})


def test_channel_variants_and_instagram_media_requirements():
    from fastapi import HTTPException
    draft = SocialDraft(title="Post", caption="x" * 3000, platforms=["instagram", "facebook", "whatsapp"]).model_dump()
    with pytest.raises(HTTPException, match="wymaga zdjęcia"):
        validate_ready(draft)
    draft["image_url"] = "https://example.test/image.jpg"
    with pytest.raises(HTTPException, match="2200"):
        validate_ready(draft)
    draft["captions"] = {"instagram": "Versión breve", "whatsapp": "  "}
    validate_ready(draft)
    assert channel_text(draft, "instagram") == "Versión breve"
    assert len(channel_text(draft, "whatsapp")) == 3000


def test_social_routes_require_login_before_any_database_access():
    from src.api.v1.studio import router
    from src.core.auth import authentication
    app = FastAPI()
    app.middleware("http")(authentication)
    app.include_router(router)
    with TestClient(app, base_url="https://editor.test") as client:
        assert client.get("/api/studio/social/drafts").status_code == 401
        assert client.post("/api/studio/social/drafts", json={}).status_code == 401
        assert client.post("/api/studio/social/drafts/invalid/actions", json={}).status_code == 401


@pytest.mark.skipif(not (os.getenv("CC_SQL_TEST_URL") or os.getenv("CC_SQL_TEST_DATABASE_URL")), reason="Disposable CI databases required")
def test_social_draft_persistence_conflict_approval_and_history():
    from app import app
    with TestClient(app, base_url="https://editor.test") as client:
        assert client.post("/auth/login", json={"token": TOKEN}).status_code == 200
        payload = {"title": "Tiempo test", "caption": "Contenido " * 300,
                   "platforms": ["instagram", "facebook", "whatsapp"], "captions": {"instagram": "En Canarias"}}
        created = client.post("/api/studio/social/drafts", json=payload)
        assert created.status_code == 201, created.text
        draft = created.json()
        assert draft["id"] and draft["version"] == 1 and draft["status"] == "draft"
        identifier = draft["id"]
        listed = client.get("/api/studio/social/drafts").json()
        assert listed["publishing_connected"] is False and listed["delivery_mode"] == "manual"
        item = next(d for d in listed["drafts"] if d["id"] == identifier)
        assert item["caption"] == payload["caption"], "long saved captions must not be truncated by database browsing"

        def act(action, version, platform=None):
            return client.post(f"/api/studio/social/drafts/{identifier}/actions", json={"action": action, "version": version, "platform": platform})

        assert act("ready", 1).status_code == 422
        assert act("confirm-published", 1, "whatsapp").status_code == 422
        updated = client.put(f"/api/studio/social/drafts/{identifier}", json={**payload, "image_url": "https://example.test/one.jpg", "version": 1})
        assert updated.status_code == 200, updated.text
        assert updated.json()["version"] == 2
        assert client.put(f"/api/studio/social/drafts/{identifier}", json={**payload, "version": 1}).status_code == 409
        assert act("ready", 1).status_code == 409
        approved = act("ready", 2)
        assert approved.status_code == 200, approved.text
        assert approved.json()["history"] == [], "approval is not publication"
        assert act("confirm-published", 3).status_code == 422
        delivered = act("confirm-published", 3, "whatsapp")
        assert delivered.status_code == 200, delivered.text
        history = delivered.json()["history"]
        assert history[0]["caption"] == payload["caption"] and history[0]["confirmation"] == "owner"
        assert act("confirm-published", 4, "whatsapp").status_code == 409
        assert act("archive", 4).status_code == 200
        assert client.put(f"/api/studio/social/drafts/{identifier}", json={**payload, "version": 5}).status_code == 409
        restored = act("restore", 5)
        assert restored.json()["status"] == "draft" and restored.json()["history"] == history
        edited = client.put(f"/api/studio/social/drafts/{identifier}", json={**payload, "caption": "Contenido actualizado", "version": 6})
        assert edited.json()["status"] == "draft" and edited.json()["history"] == history
        assert edited.json()["caption"] == "Contenido actualizado"
