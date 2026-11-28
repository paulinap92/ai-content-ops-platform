"""Studio monitor proxy. No database connection, importer, polling or scheduler."""

import json, os
from pathlib import Path
from urllib.parse import urlsplit, quote
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, ConfigDict
import httpx
from src.core.auth import require_editor


def authorize(request: Request):
    require_editor(request)


router = APIRouter(tags=["data-monitor"], dependencies=[Depends(authorize)])
ASSETS = Path(__file__).resolve().parents[1] / "studio"


def backend():
    if os.getenv("CC_LOCAL_6G") != "1":
        raise HTTPException(503, "Monitor local no configurado")
    value = os.getenv("CC_MONITOR_API_ORIGIN", "")
    u = urlsplit(value)
    if (
        u.scheme != "http"
        or u.hostname not in ("localhost", "127.0.0.1", "cc-backend")
        or u.path not in ("", "/")
        or u.username
        or u.password
        or u.query
        or u.fragment
    ):
        raise HTTPException(503, "El monitor requiere un backend local explícito")
    token = os.getenv("CC_DATA_OPERATOR_TOKEN", "")
    if len(token) < 32:
        raise HTTPException(503, "Credencial de monitor no configurada")
    return value.rstrip("/"), token


async def proxy(path="", method="GET", body=None):
    base, token = backend()
    # Only predefined routes and validated IDs reach this internal proxy.
    try:
        async with httpx.AsyncClient(timeout=15, trust_env=False, follow_redirects=False) as client:
            async with client.stream(
                method,
                base + "/api/regions/canarias/data/v1/monitoring" + path,
                headers={"Authorization": "Bearer " + token},
                json=body,
            ) as response:
                chunks = []
                size = 0
                async for part in response.aiter_bytes():
                    size += len(part)
                    if size > 512 * 1024:
                        raise HTTPException(502, "Respuesta del monitor fuera del presupuesto")
                    chunks.append(part)
                if response.status_code >= 300:
                    raise HTTPException(
                        response.status_code
                        if response.status_code in (403, 404, 409, 422)
                        else 503,
                        "Monitor no disponible o acción no autorizada",
                    )
                data = json.loads(b"".join(chunks))
                if os.getenv("CC_MONITOR_MANUAL_ENABLED") != "1":
                    for item in data.get("items", []):
                        item["manual_available"] = False
                    if isinstance(data.get("job"), dict):
                        data["job"]["manual_available"] = False
                return data
    except HTTPException:
        raise
    except (httpx.HTTPError, ValueError):
        raise HTTPException(503, "No se puede consultar el monitor SQL local") from None


@router.get("/site/monitor", include_in_schema=False)
async def page():
    return FileResponse(ASSETS / "data-monitor.html", headers={"Cache-Control": "no-store"})


@router.get("/site/api/data-monitor")
async def overview():
    return await proxy()


@router.get("/site/api/data-monitor/capacity")
async def capacity():
    return await proxy("/capacity")


@router.get("/site/api/data-monitor/jobs/{job_id}")
async def detail(job_id: str):
    if not 1 <= len(job_id) <= 180:
        raise HTTPException(422, "Job inválido")
    return await proxy("/jobs/" + quote(job_id, safe=""))


class Manual(BaseModel):
    model_config = ConfigDict(extra="forbid")
    idempotency_key: str = Field(min_length=1, max_length=180)


@router.post("/site/api/data-monitor/jobs/{job_id}/requests", status_code=202)
async def run(job_id: str, body: Manual):
    if os.getenv("CC_MONITOR_MANUAL_ENABLED") != "1":
        raise HTTPException(403, "Ejecución manual desactivada")
    if not 1 <= len(job_id) <= 180:
        raise HTTPException(422, "Job inválido")
    return await proxy("/jobs/" + quote(job_id, safe="") + "/requests", "POST", body.model_dump())
