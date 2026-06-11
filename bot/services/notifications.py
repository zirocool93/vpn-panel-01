"""Admin notifications for successful payments."""
import logging
from typing import Any, Dict

from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from config import ADMIN_IDS
from bot.utils.text import escape_html

logger = logging.getLogger(__name__)

PAYMENT_TYPE_LABELS: Dict[str, str] = {
    'stars': 'Telegram Stars',
    'crypto': 'Crypto USDT',
    'cards': 'TG Payments',
    'yookassa_qr': 'YooKassa QR/SBP',
    'wata': 'WATA',
    'platega': 'Platega SBP',
    'cardlink': 'Cardlink',
    'balance': 'Balance',
    'trial': 'Пробная подписка',
    'demo': 'Демо',
}


def _format_payment_amount(order: Dict[str, Any]) -> str:
    payment_type = order.get('payment_type', '')
    if payment_type == 'crypto':
        usd = (order.get('amount_cents', 0) or 0) / 100
        return f'${usd:g} USDT'
    if payment_type == 'stars':
        return f"{order.get('amount_stars', 0) or 0} ⭐"
    if payment_type == 'trial':
        return 'Бесплатно'

    price_rub = order.get('price_rub', 0) or 0
    if price_rub > 0:
        return f'{price_rub:g} ₽'
    return '-'


def _get_header(order: Dict[str, Any]) -> str:
    if order.get('payment_type') == 'trial':
        return '🎁 <b>Пробная подписка</b>'
    if order.get('vpn_key_id'):
        return '🔄 <b>Продление</b>'
    return '💰 <b>Новая покупка</b>'


async def notify_admins_payment(bot: Bot, order: Dict[str, Any]) -> None:
    """Sends a payment notification to all admins when enabled in settings."""
    try:
        from database.connection import get_db
        from database.requests import get_setting, get_tariff_by_id, get_vpn_key_by_id

        if get_setting('payment_notifications_enabled', '0') != '1':
            return

        telegram_id = None
        username = None
        user_id_internal = order.get('user_id')
        if user_id_internal:
            with get_db() as conn:
                row = conn.execute(
                    "SELECT telegram_id, username FROM users WHERE id = ?",
                    (user_id_internal,),
                ).fetchone()
                if row:
                    telegram_id = row['telegram_id']
                    username = row['username']

        tariff_id = order.get('tariff_id')
        if tariff_id:
            tariff = get_tariff_by_id(tariff_id)
            if tariff:
                order.setdefault('tariff_name', tariff.get('name'))
                order['price_rub'] = tariff.get('price_rub', 0)

        server_name = None
        vpn_key_id = order.get('vpn_key_id')
        if vpn_key_id:
            key = get_vpn_key_by_id(vpn_key_id)
            if key:
                server_name = key.get('server_name')

        payment_type = order.get('payment_type', '-')
        payment_label = PAYMENT_TYPE_LABELS.get(payment_type, payment_type)
        tariff_name = order.get('tariff_name') or '-'

        lines = [_get_header(order), '']
        if telegram_id:
            user_link = f'<a href="tg://user?id={telegram_id}">{telegram_id}</a>'
            if username:
                user_link += f' (@{escape_html(username)})'
            lines.append(f'👤 Пользователь: {user_link}')
        else:
            lines.append(f'👤 Пользователь: ID {user_id_internal or "?"}')

        if server_name:
            lines.append(f'🌐 Хост: {escape_html(server_name)}')
        lines.append(f'🎫 Тариф: {escape_html(str(tariff_name))}')
        lines.append(f'💳 Метод: {escape_html(str(payment_label))}')
        lines.append(f'💵 Сумма: {_format_payment_amount(order)}')

        reply_markup = None
        if telegram_id:
            button_text = f'👤 @{username}' if username else f'👤 {telegram_id}'
            reply_markup = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text=button_text, callback_data=f'admin_user_view:{telegram_id}')
            ]])

        text = '\n'.join(lines)
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(admin_id, text, parse_mode='HTML', reply_markup=reply_markup)
            except Exception as e:
                logger.warning('Failed to send payment notification to admin %s: %s', admin_id, e)
    except Exception as e:
        logger.error('Payment notification failed: %s', e)
