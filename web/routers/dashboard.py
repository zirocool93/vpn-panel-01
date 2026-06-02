from __future__ import annotations

from fastapi import APIRouter, Request

from services.dashboard_service import get_dashboard_data
from web import security
from web.deps import template_context, templates


router = APIRouter(prefix="/admin")


@router.get("")
@router.get("/")
async def dashboard(request: Request):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        template_context(request, title="Dashboard", dashboard=get_dashboard_data()),
    )
