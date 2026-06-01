from __future__ import annotations

from fastapi import APIRouter, Query, Request

from services import payment_service
from web import security
from web.deps import template_context, templates


router = APIRouter(prefix="/admin/payments")


@router.get("")
async def list_payments(
    request: Request,
    user_id: int | None = Query(None),
    status: str = Query(""),
    payment_type: str = Query(""),
):
    redirect = security.require_admin(request)
    if redirect:
        return redirect
    return templates.TemplateResponse(
        request,
        "payments/list.html",
        template_context(
            request,
            title="Платежи",
            payments=payment_service.list_payments(
                user_id=user_id,
                status=status or None,
                payment_type=payment_type or None,
            ),
            stats=payment_service.get_payment_stats(days=30),
            filters={"user_id": user_id, "status": status, "payment_type": payment_type},
        ),
    )
