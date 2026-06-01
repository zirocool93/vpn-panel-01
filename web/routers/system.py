from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from starlette.responses import FileResponse, RedirectResponse

from bot.utils.git_utils import check_for_updates, get_current_branch, get_current_commit
from services.audit_service import log_admin_action
from web import security
from web.deps import flash, template_context, templates


router = APIRouter(prefix="/admin/system")
PROJECT_ROOT = Path(__file__).resolve().parents[2]
BOT_LOG = PROJECT_ROOT / "logs" / "bot.log"


@router.get("")
async def system_page(request: Request):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    log_tail = ""
    if BOT_LOG.exists():
        lines = BOT_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
        log_tail = "\n".join(lines[-200:])
    success, commits_behind, log_text, has_blocking, blocking_commit, is_beta_only = check_for_updates()
    return templates.TemplateResponse(
        request,
        "system/logs.html",
        template_context(
            request,
            title="Система",
            current_commit=get_current_commit(),
            current_branch=get_current_branch(),
            update_check={
                "success": success,
                "commits_behind": commits_behind,
                "log_text": log_text,
                "has_blocking": has_blocking,
                "blocking_commit": blocking_commit,
                "is_beta_only": is_beta_only,
            },
            log_tail=log_tail,
        ),
    )


@router.get("/download-log")
async def download_log(request: Request):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    if not BOT_LOG.exists():
        flash(request, "bot.log не найден", "warning")
        return RedirectResponse("/admin/system", status_code=303)
    return FileResponse(str(BOT_LOG), filename="bot.log")


@router.post("/clear-log")
async def clear_log(request: Request):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    BOT_LOG.parent.mkdir(parents=True, exist_ok=True)
    BOT_LOG.write_text("", encoding="utf-8")
    admin = security.get_current_admin(request)
    log_admin_action(admin["admin_user_id"], "system.log.clear", "log", "bot.log", request=request)
    flash(request, "Лог очищен", "warning")
    return RedirectResponse("/admin/system", status_code=303)
