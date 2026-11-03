from fastapi import FastAPI
from fastapi.testclient import TestClient
from canarias_site.api.studio import router
from canarias_site.services.studio_auth import studio_session
from src.core.auth import authentication, router as auth_router, COOKIE, valid_cookie, cookie_value

TOKEN="isolated-editor-test-credential-1234567890"

def test_one_session_protects_the_entire_editor_and_cookie_is_not_shared_with_site():
 app=FastAPI();app.middleware("http")(authentication);app.include_router(auth_router);app.include_router(router)
 app.dependency_overrides[studio_session]=lambda:None
 with TestClient(app,base_url="https://editor.example") as client:
  for path in ["/site/api/options","/api/v1/content","/api/studio/database/collections","/static/app.js","/docs"]:
   assert client.get(path).status_code==401
  assert client.post("/auth/login",json={"token":TOKEN},headers={"Origin":"https://other.example"}).status_code==403
  result=client.post("/auth/login",json={"token":TOKEN},headers={"Origin":"https://editor.example"})
  assert result.status_code==200
  cookie=result.headers["set-cookie"]
  assert "HttpOnly" in cookie and "Secure" in cookie and "SameSite=strict" in cookie and "Path=/" in cookie
  assert client.get("/site/api/options").status_code==200
  assert client.get("/site/api/sql").status_code==404
  assert client.post("/auth/logout").status_code==200
  assert client.get("/site/api/options").status_code==401

def test_local_installation_also_requires_login_and_rejects_tampered_cookie():
 app=FastAPI();app.middleware("http")(authentication);app.include_router(auth_router);app.include_router(router)
 app.dependency_overrides[studio_session]=lambda:None
 with TestClient(app,base_url="http://localhost:8002") as client:
  assert client.get("/site/api/options").status_code==401
  result=client.post("/auth/login",json={"token":TOKEN})
  assert result.status_code==200 and "Secure;" not in result.headers["set-cookie"]
 assert valid_cookie(cookie_value(TOKEN),TOKEN)
 assert not valid_cookie(cookie_value(TOKEN)+"bad",TOKEN)


def test_new_inspection_routes_require_the_existing_private_login():
 from canarias_site.api.inspection import router as inspect_router
 app=FastAPI();app.middleware("http")(authentication);app.include_router(inspect_router)
 with TestClient(app,base_url="https://editor.example") as client:
  for path in ["/site/api/database/tables","/site/api/database/tables/entities","/site/api/coverage","/site/api/data?section=live&resource=weather"]:
   assert client.get(path).status_code==401
