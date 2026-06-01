"""Shared Web dependencies and template helpers."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi.templating import Jinja2Templates
from starlette.requests import Request

from web import security


BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def pop_flashes(request: Request) -> list[dict[str, str]]:
    flashes = request.session.pop("flashes", []) if hasattr(request, "session") else []
    return flashes if isinstance(flashes, list) else []


def flash(request: Request, message: str, category: str = "success") -> None:
    if not hasattr(request, "session"):
        return
    flashes = request.session.get("flashes", [])
    flashes.append({"message": message, "category": category})
    request.session["flashes"] = flashes


def template_context(request: Request, **extra: Any) -> dict[str, Any]:
    context = {
        "request": request,
        "admin": security.get_current_admin(request),
        "flashes": pop_flashes(request),
    }
    context.update(extra)
    return context

