import logging

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.utils.text import safe_edit_or_send

logger = logging.getLogger(__name__)

router = Router()


@router.callback_query(F.data == 'buy_key')
async def buy_key_handler(callback: CallbackQuery):
    """Страница покупки ключа из inline-кнопки."""
    await _render_buy_page(callback)


@router.message(Command('buy'))
async def buy_key_command(message: Message):
    """Страница покупки ключа из команды /buy."""
    await _render_buy_page(message)


async def _render_buy_page(target: CallbackQuery | Message):
    from database.requests import (
        create_pending_order,
        get_user_internal_id,
        is_cardlink_configured,
        is_cards_enabled,
        is_crypto_configured,
        is_demo_payment_enabled,
        is_platega_configured,
        is_stars_enabled,
        is_user_banned,
        is_wata_configured,
        is_yookassa_qr_configured,
    )
    from bot.keyboards.admin import home_only_kb
    from bot.utils.page_renderer import render_page

    telegram_id = target.from_user.id
    message = target.message if isinstance(target, CallbackQuery) else target
    force_new = isinstance(target, Message)

    if is_user_banned(telegram_id):
        await safe_edit_or_send(
            message,
            '⛔ <b>Доступ заблокирован</b>\n\nВаш аккаунт заблокирован. Обратитесь в поддержку.',
            reply_markup=home_only_kb(),
            force_new=force_new,
        )
        if isinstance(target, CallbackQuery):
            await target.answer()
        return

    payment_available = any((
        is_crypto_configured(),
        is_stars_enabled(),
        is_cards_enabled(),
        is_yookassa_qr_configured(),
        is_wata_configured(),
        is_platega_configured(),
        is_cardlink_configured(),
        is_demo_payment_enabled(),
    ))

    if not payment_available:
        await safe_edit_or_send(
            message,
            '💳 <b>Купить ключ</b>\n\n😔 Сейчас оплата недоступна.\n\nПопробуйте позже или обратитесь в поддержку.',
            reply_markup=home_only_kb(),
            force_new=force_new,
        )
        if isinstance(target, CallbackQuery):
            await target.answer()
        return

    user_id = get_user_internal_id(telegram_id)
    order_id = None
    if user_id:
        _, order_id = create_pending_order(
            user_id=user_id,
            tariff_id=None,
            payment_type=None,
            vpn_key_id=None,
        )

    await render_page(
        target,
        page_key='prepayment',
        context={
            'order_id': order_id,
            'telegram_id': telegram_id,
        },
        force_new=force_new,
    )
    if isinstance(target, CallbackQuery):
        await target.answer()
