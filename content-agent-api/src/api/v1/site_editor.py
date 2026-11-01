"""Local authenticated bridge to the Canarias Cerca editorial API.

The public website database stays behind its backend. Credentials never reach
the browser, and only the specific Studio paths can be proxied.
"""
import re

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, Response

from src.api.v1.studio import require_local
from src.core.config import settings

router = APIRouter(dependencies=[Depends(require_local)])
ALLOWED = re.compile(r"^(?:assets/(?:studio\.js|studio\.css|editorialText\.js)|api/(?:options|records|draft|media|documents/[0-9a-f-]+/(?:publish|history|restore|rebase)))$")


@router.api_route("/site/", methods=["GET"])
@router.api_route("/site/{path:path}", methods=["GET", "POST", "PUT"])
async def site_editor(request: Request, path: str = ""):
    if path and not ALLOWED.fullmatch(path):
        raise HTTPException(404, "Unknown Studio endpoint")
    if not settings.canarias_api_url or not settings.canarias_editor_token:
        raise HTTPException(503, "Ustaw CANARIAS_API_URL i CANARIAS_EDITOR_TOKEN w konfiguracji Studia. Możesz też otworzyć panel /studio/ bezpośrednio w backendzie Canarias Cerca.")
    if int(request.headers.get("content-length", "0")) > 7_100_000:
        raise HTTPException(413, "File too large")
    body = await request.body()
    if len(body) > 7_100_000:
        raise HTTPException(413, "File too large")
    target = settings.canarias_api_url.rstrip("/") + "/studio/" + path
    headers = {"Authorization": f"Bearer {settings.canarias_editor_token.get_secret_value()}", "Content-Type": request.headers.get("content-type", "application/json")}
    async with httpx.AsyncClient(timeout=65, follow_redirects=False) as client:
        try:
            result = await client.request(request.method, target, params=request.query_params, content=body, headers=headers)
        except httpx.RequestError:
            raise HTTPException(502, "Nie można połączyć się z backendem strony. Spróbuj ponownie po wybudzeniu Render.")
    return Response(result.content, status_code=result.status_code, media_type=result.headers.get("content-type", "application/json").split(";")[0], headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"})
