"""FastAPI application factory for the Web admin."""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from database.migrations import run_migrations
from web import security
from web.middleware.security import WebSecurityMiddleware
from web.routers import audit, auth, backups, dashboard, keys, pages, payments, servers, settings, system, tariffs, users


logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    run_migrations()
    app = FastAPI(title="Yadreno VPN Web Admin")
    app.add_middleware(WebSecurityMiddleware)
    app.add_middleware(
        SessionMiddleware,
        secret_key=security.get_secret_key(),
        https_only=security.get_cookie_secure(),
        same_site=security.get_cookie_samesite(),
    )

    static_dir = Path(__file__).resolve().parent / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    app.include_router(auth.router)
    app.include_router(dashboard.router)
    app.include_router(servers.router)
    app.include_router(tariffs.router)
    app.include_router(users.router)
    app.include_router(keys.router)
    app.include_router(pages.router)
    app.include_router(payments.router)
    app.include_router(settings.router)
    app.include_router(system.router)
    app.include_router(backups.router)
    app.include_router(audit.router)
    return app
