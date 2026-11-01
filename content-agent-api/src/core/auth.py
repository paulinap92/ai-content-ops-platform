"""One authenticated session for the complete standalone Content Editor."""
import base64
import hashlib
import hmac
import os
import time
from collections import defaultdict, deque
from urllib.parse import urlsplit

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

COOKIE = "cc_editor_session"
TTL = 12 * 60 * 60
_attempts = defaultdict(deque)
router = APIRouter()


def configured_token():
    from src.core.config import settings
    token = os.getenv("EDITOR_TOKEN", "") or (settings.editor_token.get_secret_value() if settings.editor_token else "")
    if len(token) < 32:
        raise HTTPException(503, "Skonfiguruj prywatny EDITOR_TOKEN (minimum 32 znaki).")
    return token


def cookie_value(token, issued=None):
    stamp = int(time.time()) if issued is None else issued
    signature = hmac.new(token.encode(), f"editor:{stamp}".encode(), hashlib.sha256).hexdigest()
    return base64.urlsafe_b64encode(f"editor:{stamp}:{signature}".encode()).decode()


def valid_cookie(value, token):
    try:
        scope, stamp, _ = base64.urlsafe_b64decode(value).decode().split(":")
        return scope == "editor" and 0 <= time.time() - int(stamp) < TTL and hmac.compare_digest(value, cookie_value(token, int(stamp)))
    except (ValueError, TypeError, UnicodeError):
        return False


def check_origin(request):
    origin = request.headers.get("origin")
    if origin:
        parsed = urlsplit(origin)
        local = request.url.hostname in {"localhost", "127.0.0.1", "::1"}
        if parsed.netloc != request.url.netloc or parsed.scheme != "https" and not (local and parsed.scheme == "http"):
            raise HTTPException(403, "Cross-origin editor request rejected")


def require_editor(request):
    token = configured_token()
    supplied = request.headers.get("authorization", "").removeprefix("Bearer ")
    if not (supplied and hmac.compare_digest(token, supplied)) and not valid_cookie(request.cookies.get(COOKIE, ""), token):
        raise HTTPException(401, "Zaloguj się do Content Editora.")
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        check_origin(request)


async def authentication(request, call_next):
    public = request.url.path in {"/login", "/auth/login", "/health/live", "/robots.txt"}
    if not public:
        try:
            require_editor(request)
        except HTTPException as exc:
            if exc.status_code == 401 and request.method == "GET" and "text/html" in request.headers.get("accept", ""):
                return RedirectResponse("/login", 303)
            return JSONResponse({"detail": exc.detail}, status_code=exc.status_code, headers={"Cache-Control": "no-store"})
    response = await call_next(request)
    response.headers.update({"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff", "Referrer-Policy": "same-origin", "X-Frame-Options": "SAMEORIGIN", "X-Robots-Tag": "noindex, nofollow"})
    return response


class Login(BaseModel):
    token: str = Field(min_length=1, max_length=512)


@router.get("/login", include_in_schema=False)
async def login_page():
    return FileResponse("static/login.html", headers={"Cache-Control": "no-store", "X-Robots-Tag": "noindex, nofollow"})


@router.post("/auth/login", include_in_schema=False)
async def login(payload: Login, request: Request, response: Response):
    check_origin(request)
    token = configured_token()
    attempts = _attempts[request.client.host if request.client else "unknown"]
    while attempts and attempts[0] < time.monotonic() - 300:
        attempts.popleft()
    if len(attempts) >= 10:
        raise HTTPException(429, "Za dużo prób. Spróbuj za 5 minut.")
    attempts.append(time.monotonic())
    if not hmac.compare_digest(token, payload.token):
        raise HTTPException(401, "Nieprawidłowy klucz Editora.")
    attempts.clear()
    local = request.url.hostname in {"localhost", "127.0.0.1", "::1"}
    response.set_cookie(COOKIE, cookie_value(token), httponly=True, secure=not local, samesite="strict", path="/", max_age=TTL)
    return {"authenticated": True}


@router.post("/auth/logout", include_in_schema=False)
async def logout(request: Request, response: Response):
    check_origin(request)
    response.delete_cookie(COOKIE, path="/")
    return {"authenticated": False}


@router.get("/robots.txt", include_in_schema=False)
async def robots():
    return Response("User-agent: *\nDisallow: /\n", media_type="text/plain")
