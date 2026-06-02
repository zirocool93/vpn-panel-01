from __future__ import annotations

from fastapi import APIRouter, Form, Request
from starlette.responses import FileResponse, RedirectResponse

from services import backup_service
from services.audit_service import log_admin_action
from web import security
from web.deps import flash, template_context, templates


router = APIRouter(prefix="/admin/system/backups")


@router.get("")
async def backups_page(request: Request):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    integrity = backup_service.database_integrity_check()
    return templates.TemplateResponse(
        request,
        "system/backups/list.html",
        template_context(
            request,
            title="Бэкапы",
            backups=backup_service.list_backups(),
            integrity=integrity,
            backup_log=backup_service.get_backup_log(50),
        ),
    )


@router.post("/create")
async def create_backup(request: Request, include_logs: str = Form(""), note: str = Form("")):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    admin = security.get_current_admin(request)
    result = backup_service.create_backup(admin["admin_user_id"], include_logs=bool(include_logs), note=note)
    log_admin_action(admin["admin_user_id"], "backup.create", "backup", result["filename"], result, request)
    flash(request, f"Backup создан: {result['filename']}")
    return RedirectResponse("/admin/system/backups", status_code=303)


@router.get("/{filename}/download")
async def download_backup(request: Request, filename: str):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    path = backup_service.get_backup_path(filename)
    admin = security.get_current_admin(request)
    backup_service.log_backup_event(admin["admin_user_id"], "backup.download", filename, True, path.stat().st_size, backup_service.sha256_file(path))
    log_admin_action(admin["admin_user_id"], "backup.download", "backup", filename, {"size": path.stat().st_size}, request)
    return FileResponse(str(path), filename=filename, media_type="application/gzip")


@router.post("/{filename}/verify")
async def verify_backup(request: Request, filename: str):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    result = backup_service.verify_backup(filename)
    admin = security.get_current_admin(request)
    backup_service.log_backup_event(admin["admin_user_id"], "backup.verify", filename, bool(result.get("success")), details=result)
    log_admin_action(admin["admin_user_id"], "backup.verify", "backup", filename, result, request)
    flash(request, result.get("message", "Проверка завершена"), "success" if result.get("success") else "danger")
    return RedirectResponse("/admin/system/backups", status_code=303)


@router.post("/{filename}/delete")
async def delete_backup(request: Request, filename: str):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    admin = security.get_current_admin(request)
    result = backup_service.delete_backup(filename)
    backup_service.log_backup_event(admin["admin_user_id"], "backup.delete", filename, True, result.get("size"), result.get("sha256"))
    log_admin_action(admin["admin_user_id"], "backup.delete", "backup", filename, result, request)
    flash(request, result["message"], "warning")
    return RedirectResponse("/admin/system/backups", status_code=303)


@router.get("/{filename}/restore")
async def restore_backup_page(request: Request, filename: str):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    result = backup_service.verify_backup(filename)
    return templates.TemplateResponse(
        request,
        "system/backups/restore.html",
        template_context(request, title="Restore backup", filename=filename, verification=result),
    )


@router.post("/{filename}/restore")
async def restore_backup(request: Request, filename: str, make_pre_restore_backup: str = Form("1")):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    admin = security.get_current_admin(request)
    result = backup_service.restore_backup(filename, make_pre_restore_backup=bool(make_pre_restore_backup), admin_user_id=admin["admin_user_id"])
    backup_service.log_backup_event(admin["admin_user_id"], "backup.restore", filename, bool(result.get("success")), details=result)
    log_admin_action(admin["admin_user_id"], "backup.restore", "backup", filename, result, request)
    flash(request, result.get("message", "Restore завершён"), "success" if result.get("success") else "danger")
    return RedirectResponse("/admin/system/backups", status_code=303)


@router.post("/integrity-check")
async def integrity_check(request: Request):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    result = backup_service.database_integrity_check()
    admin = security.get_current_admin(request)
    backup_service.log_backup_event(admin["admin_user_id"], "backup.integrity_check", None, bool(result.get("success")), details=result)
    log_admin_action(admin["admin_user_id"], "backup.integrity_check", "database", None, result, request)
    flash(request, f"SQLite integrity_check: {result['integrity_check']}", "success" if result.get("success") else "danger")
    return RedirectResponse("/admin/system/backups", status_code=303)


@router.post("/vacuum")
async def vacuum_database(request: Request):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    result = backup_service.vacuum_database()
    admin = security.get_current_admin(request)
    backup_service.log_backup_event(admin["admin_user_id"], "backup.vacuum", None, True, details=result)
    log_admin_action(admin["admin_user_id"], "backup.vacuum", "database", None, result, request)
    flash(request, result["message"])
    return RedirectResponse("/admin/system/backups", status_code=303)
