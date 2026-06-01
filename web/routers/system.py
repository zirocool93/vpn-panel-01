from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from starlette.responses import FileResponse, RedirectResponse

from bot.utils.git_utils import check_for_updates, get_current_branch, get_current_commit
from services import host_diagnostics_service
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
    return templates.TemplateResponse(
        request,
        "system/logs.html",
        template_context(
            request,
            title="Система",
            current_commit=get_current_commit(),
            current_branch=get_current_branch(),
            update_check=None,
            log_tail=log_tail,
        ),
    )


@router.get("/diagnostics")
async def system_diagnostics(request: Request):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    diagnostics = host_diagnostics_service.get_host_diagnostics()
    return templates.TemplateResponse(
        request,
        "system/diagnostics.html",
        template_context(request, title="Диагностика системы", diagnostics=diagnostics),
    )


@router.get("/services")
async def system_services(request: Request):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    services = host_diagnostics_service.get_services_info()
    return templates.TemplateResponse(
        request,
        "system/services.html",
        template_context(request, title="Сервисы", services=services),
    )


@router.get("/network")
async def system_network(request: Request):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    network = host_diagnostics_service.get_network_info()
    return templates.TemplateResponse(
        request,
        "system/network.html",
        template_context(request, title="Сеть", network=network),
    )


@router.get("/database")
async def system_database(request: Request):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    database = host_diagnostics_service.get_database_info()
    return templates.TemplateResponse(
        request,
        "system/database.html",
        template_context(request, title="База данных", database=database),
    )


@router.post("/check-github")
async def check_github(request: Request):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    network = host_diagnostics_service.get_network_info()
    result = network.get("github_https", {})
    _audit(request, "system.github.check", {"ok": result.get("ok"), "stderr": result.get("stderr")})
    flash(request, _command_message("GitHub", result), "success" if result.get("ok") else "danger")
    return RedirectResponse("/admin/system/network", status_code=303)


@router.post("/check-telegram")
async def check_telegram(request: Request):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    network = host_diagnostics_service.get_network_info()
    result = network.get("telegram_https", {})
    _audit(request, "system.telegram.check", {"ok": result.get("ok"), "stderr": result.get("stderr")})
    flash(request, _command_message("Telegram API", result), "success" if result.get("ok") else "danger")
    return RedirectResponse("/admin/system/network", status_code=303)


@router.post("/check-database")
async def check_database(request: Request):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    database = host_diagnostics_service.get_database_info()
    ok = database.get("available") and database.get("integrity_check") == "ok"
    _audit(request, "system.database.check", {"ok": ok, "integrity_check": database.get("integrity_check"), "error": database.get("error")})
    message = f"SQLite integrity_check: {database.get('integrity_check') or database.get('error')}"
    flash(request, message, "success" if ok else "danger")
    return RedirectResponse("/admin/system/database", status_code=303)


@router.post("/check-updates")
async def check_updates(request: Request):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    success, commits_behind, log_text, has_blocking, blocking_commit, is_beta_only = check_for_updates()
    _audit(
        request,
        "system.updates.check",
        {
            "success": success,
            "commits_behind": commits_behind,
            "has_blocking": has_blocking,
            "blocking_commit": blocking_commit,
            "is_beta_only": is_beta_only,
        },
    )
    flash(request, log_text, "success" if success else "danger")
    return RedirectResponse("/admin/system", status_code=303)


@router.post("/restart-bot")
async def restart_bot(request: Request):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    result = host_diagnostics_service.restart_service("yadreno-vpn")
    _audit(request, "system.service.restart", {"service": "yadreno-vpn", "ok": result.get("ok"), "stderr": result.get("stderr")})
    flash(request, _command_message("yadreno-vpn restart", result), "success" if result.get("ok") else "danger")
    return RedirectResponse("/admin/system/services", status_code=303)


@router.post("/restart-web")
async def restart_web(request: Request):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    result = host_diagnostics_service.restart_service("yadreno-vpn-web")
    _audit(request, "system.service.restart", {"service": "yadreno-vpn-web", "ok": result.get("ok"), "stderr": result.get("stderr")})
    flash(request, _command_message("yadreno-vpn-web restart", result), "success" if result.get("ok") else "danger")
    return RedirectResponse("/admin/system/services", status_code=303)


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
    _audit(request, "system.log.clear", {"file": "bot.log"})
    flash(request, "Лог очищен", "warning")
    return RedirectResponse("/admin/system", status_code=303)


def _audit(request: Request, action: str, details: dict):
    admin = security.get_current_admin(request)
    log_admin_action(admin["admin_user_id"], action, "system", None, details, request)


def _command_message(label: str, result: dict) -> str:
    output = result.get("stdout") or result.get("stderr") or ""
    status = "ok" if result.get("ok") else "error"
    return f"{label}: {status}" + (f"\n{output}" if output else "")
