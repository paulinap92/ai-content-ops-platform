"""Local monitor-only entrypoint using real Studio auth/assets/proxy.

Does not start editorial agents, persistence or a public-data scheduler. The
regular Studio app includes the exact same monitor router for later integration.
"""

import os
from pathlib import Path
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from src.core.auth import authentication, router as auth_router
from canarias_site.api.data_monitor import router as monitor_router, ASSETS, backend


def create_app():
    backend()  # Reject missing/local-invalid configuration before serving.
    app = FastAPI(title="CanariasCerca Studio · Monitor local")
    app.middleware("http")(authentication)
    app.include_router(auth_router)
    app.include_router(monitor_router)

    @app.get("/")
    async def root():
        return RedirectResponse("/site/monitor")

    @app.get("/site/assets/{name}")
    async def asset(name: str):
        if name not in {
            "data-monitor.js",
            "data-monitor.css",
            "monitor-navigation.js",
            "studio.css",
        }:
            raise HTTPException(404)
        return FileResponse(ASSETS / name)

    return app
