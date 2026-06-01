from __future__ import annotations

from fastapi import APIRouter, Form, Request
from starlette.responses import RedirectResponse

from services import settings_service
from services.audit_service import log_admin_action
from web import security
from web.deps import flash, template_context, templates


router = APIRouter(prefix="/admin/settings")

VISIBLE_SETTINGS = [
    "bot_mode",
    "notification_days",
    "trial_enabled",
    "referral_enabled",
    "monthly_traffic_reset_enabled",
    "cards_enabled",
    "yookassa_qr_enabled",
    "crypto_enabled",
    "wata_enabled",
    "platega_enabled",
    "cardlink_enabled",
    "web_admin_host",
    "web_admin_port",
    "web_session_lifetime_hours",
]


@router.get("")
async def settings_page(request: Request):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    all_settings = settings_service.get_all_settings(mask_secrets=True)
    return templates.TemplateResponse(
        request,
        "settings/index.html",
        template_context(
            request,
            title="Настройки",
            settings={key: all_settings.get(key, "") for key in VISIBLE_SETTINGS},
        ),
    )


@router.post("")
async def update_settings(request: Request):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    form = await request.form()
    values = {key: str(form.get(key, "")) for key in VISIBLE_SETTINGS if key in form}
    settings_service.update_many_settings(values)
    admin = security.get_current_admin(request)
    log_admin_action(admin["admin_user_id"], "settings.update", "settings", None, {"keys": list(values)}, request)
    flash(request, "Настройки обновлены")
    return RedirectResponse("/admin/settings", status_code=303)
