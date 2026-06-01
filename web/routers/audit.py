from __future__ import annotations

from fastapi import APIRouter, Query, Request

from services.audit_service import get_audit_log
from web import security
from web.deps import template_context, templates


router = APIRouter(prefix="/admin/audit")


@router.get("")
async def audit_page(request: Request, action: str = Query("")):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    rows = get_audit_log(limit=200)
    if action:
        rows = [row for row in rows if row.get("action") == action]
    return templates.TemplateResponse(
        request,
        "audit/list.html",
        template_context(request, title="Аудит", rows=rows, action=action),
    )
