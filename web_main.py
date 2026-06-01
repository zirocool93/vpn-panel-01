"""Entrypoint for the FastAPI Web admin."""
from __future__ import annotations

import os

import uvicorn

from database.db_settings import get_setting
from database.migrations import run_migrations
from web.app import create_app


app = create_app()


def main() -> None:
    run_migrations()
    host = os.getenv("WEB_HOST") or get_setting("web_admin_host", "127.0.0.1") or "127.0.0.1"
    port = int(os.getenv("WEB_PORT") or get_setting("web_admin_port", "8080") or "8080")
    uvicorn.run("web_main:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    main()

