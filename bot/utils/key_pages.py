"""РЎР±РѕСЂРєР° HTML-Р±Р»РѕРєРѕРІ РґР»СЏ СЂРµРґР°РєС‚РёСЂСѓРµРјС‹С… СЃС‚СЂР°РЅРёС† РєР»СЋС‡РµР№."""
from __future__ import annotations

from typing import Any, Iterable, Mapping

from bot.utils.text import escape_html
from bot.utils.datetime_format import format_date_for_display


KEY_INFO_PLACEHOLDER = '%РёРЅС„РѕСЂРјР°С†РёСЏРєР»СЋС‡Р°%'
KEY_HISTORY_PLACEHOLDER = '%РёСЃС‚РѕСЂРёСЏРѕРїРµСЂР°С†РёР№%'
SCREEN_DATA_PLACEHOLDER = '%РґР°РЅРЅС‹РµСЌРєСЂР°РЅР°%'
REPLACE_DATA_PLACEHOLDER = '%РґР°РЅРЅС‹РµР·Р°РјРµРЅС‹%'
KEY_DATA_PLACEHOLDER = '%РґР°РЅРЅС‹РµРєР»СЋС‡Р°%'


def _safe(value: Any, fallback: str = 'вЂ”') -> str:
    """Р­РєСЂР°РЅРёСЂСѓРµС‚ РґРёРЅР°РјРёС‡РµСЃРєРѕРµ Р·РЅР°С‡РµРЅРёРµ РґР»СЏ HTML."""
    if value is None or value == '':
        return escape_html(fallback)
    return escape_html(str(value))


def keyboard_rows(markup) -> list:
    """Р’РѕР·РІСЂР°С‰Р°РµС‚ СЂСЏРґС‹ РєРЅРѕРїРѕРє РёР· РіРѕС‚РѕРІРѕР№ InlineKeyboardMarkup."""
    if not markup:
        return []
    return list(getattr(markup, 'inline_keyboard', []) or [])


def build_key_details_replacements(
    key: Mapping[str, Any],
    payments: Iterable[Mapping[str, Any]],
    *,
    status: str,
    traffic_info: str,
    inbound_name: str,
    protocol: str,
    prepend_html: str = '',
) -> dict[str, str]:
    """Р“РѕС‚РѕРІРёС‚ РїР»РµР№СЃС…РѕР»РґРµСЂС‹ РєР°СЂС‚РѕС‡РєРё РєР»СЋС‡Р°."""
    info_lines: list[str] = []
    if prepend_html:
        info_lines.extend([prepend_html, ''])

    server = key.get('server_name') or 'РќРµ РІС‹Р±СЂР°РЅ'
    expires = format_date_for_display(key.get('expires_at'), fallback='вЂ”')
    info_lines.extend([
        f"рџ”‘ <b>{_safe(key.get('display_name'), 'VPN-РєР»СЋС‡')}</b>",
        '',
        f"<b>РЎС‚Р°С‚СѓСЃ:</b> {_safe(status)}",
        f"<b>РЎРµСЂРІРµСЂ:</b> {_safe(server)}",
        f"<b>РџСЂРѕС‚РѕРєРѕР»:</b> {_safe(inbound_name)} ({_safe(protocol)})",
        f"<b>РўСЂР°С„РёРє:</b> {_safe(traffic_info)}",
        f"<b>Р”РµР№СЃС‚РІСѓРµС‚ РґРѕ:</b> {_safe(expires)}",
    ])

    return {
        KEY_INFO_PLACEHOLDER: '\n'.join(info_lines),
        KEY_HISTORY_PLACEHOLDER: build_key_history_block(payments),
    }


def build_key_history_block(payments: Iterable[Mapping[str, Any]]) -> str:
    """РЎРѕР±РёСЂР°РµС‚ Р±Р»РѕРє РёСЃС‚РѕСЂРёРё РѕРїРµСЂР°С†РёР№ РєР»СЋС‡Р°."""
    payment_rows = list(payments or [])
    if not payment_rows:
        return ''

    lines = ['', 'рџ“њ <b>РСЃС‚РѕСЂРёСЏ РѕРїРµСЂР°С†РёР№:</b>']
    for payment in payment_rows:
        date = format_date_for_display(payment.get("paid_at"), fallback="-")
        tariff = payment.get("tariff_name") or "Тариф"
        payment_type = payment.get("payment_type")
        if payment_type == "stars":
            amount = f"{_safe(payment.get('amount_stars') or 0)} ⭐"
        elif payment_type in ("cards", "yookassa_qr", "wata", "platega", "cardlink", "balance"):
            amount_val = payment.get("price_rub") or 0
            amount_str = f"{amount_val:g}".replace(".", ",")
            amount = f"{_safe(amount_str)} ₽"
        else:
            amount_val = (payment.get("amount_cents") or 0) / 100
            amount_str = f"{amount_val:g}".replace(".", ",")
            amount = f"${_safe(amount_str)}"
        lines.append(f"   • {_safe(date)}: {_safe(tariff)} ({amount})")
    return '\n'.join(lines)


def build_replace_server_select_data() -> str:
    """РћРїРёСЃР°РЅРёРµ СЃС‚Р°СЂС‚РѕРІРѕРіРѕ СЌРєСЂР°РЅР° Р·Р°РјРµРЅС‹ РєР»СЋС‡Р°."""
    return (
        "Р’С‹ РјРѕР¶РµС‚Рµ РїРµСЂРµСЃРѕР·РґР°С‚СЊ РєР»СЋС‡ РЅР° РґСЂСѓРіРѕРј РёР»Рё С‚РѕРј Р¶Рµ СЃРµСЂРІРµСЂРµ.\n"
        "РЎС‚Р°СЂС‹Р№ РєР»СЋС‡ Р±СѓРґРµС‚ СѓРґР°Р»С‘РЅ, РЅРѕ СЃСЂРѕРє РґРµР№СЃС‚РІРёСЏ СЃРѕС…СЂР°РЅРёС‚СЃСЏ."
    )


def build_server_screen_data(server: Mapping[str, Any]) -> str:
    """Р“РѕС‚РѕРІРёС‚ Р±Р»РѕРє СЃ РІС‹Р±СЂР°РЅРЅС‹Рј СЃРµСЂРІРµСЂРѕРј."""
    return f"<b>РЎРµСЂРІРµСЂ:</b> {_safe(server.get('name'), 'РќРµ РІС‹Р±СЂР°РЅ')}"


def build_replace_confirm_data(
    key: Mapping[str, Any],
    server: Mapping[str, Any],
    *,
    subscription_mode: bool,
) -> str:
    """Р“РѕС‚РѕРІРёС‚ Р±Р»РѕРє РїРѕРґС‚РІРµСЂР¶РґРµРЅРёСЏ Р·Р°РјРµРЅС‹ РєР»СЋС‡Р°."""
    lines = [
        f"РљР»СЋС‡: <b>{_safe(key.get('display_name'), 'VPN-РєР»СЋС‡')}</b>",
        f"РќРѕРІС‹Р№ СЃРµСЂРІРµСЂ: <b>{_safe(server.get('name'), 'РќРµ РІС‹Р±СЂР°РЅ')}</b>",
        '',
    ]
    if subscription_mode:
        lines.extend([
            "РџРѕРґРїРёСЃРєР° Р±СѓРґРµС‚ РїРµСЂРµСЃРѕР·РґР°РЅР° РЅР° РЅРѕРІРѕРј СЃРµСЂРІРµСЂРµ (СЃРѕ РІСЃРµРјРё РїСЂРѕС‚РѕРєРѕР»Р°РјРё).",
            "РЎС‚Р°СЂР°СЏ СЃСЃС‹Р»РєР° РїРµСЂРµСЃС‚Р°РЅРµС‚ СЂР°Р±РѕС‚Р°С‚СЊ вЂ” РЅСѓР¶РЅРѕ Р±СѓРґРµС‚ РѕР±РЅРѕРІРёС‚СЊ РµС‘ РІ РїСЂРёР»РѕР¶РµРЅРёРё.",
        ])
    else:
        lines.extend([
            "РЎС‚Р°СЂС‹Р№ РєР»СЋС‡ Р±СѓРґРµС‚ СѓРґР°Р»С‘РЅ Рё РїРµСЂРµСЃС‚Р°РЅРµС‚ СЂР°Р±РѕС‚Р°С‚СЊ.",
            "Р’Р°Рј РЅСѓР¶РЅРѕ Р±СѓРґРµС‚ РѕР±РЅРѕРІРёС‚СЊ РЅР°СЃС‚СЂРѕР№РєРё РІ РїСЂРёР»РѕР¶РµРЅРёРё.",
        ])
    return '\n'.join(lines)


def build_key_rename_data(key: Mapping[str, Any]) -> str:
    """Р“РѕС‚РѕРІРёС‚ Р±Р»РѕРє С‚РµРєСѓС‰РµРіРѕ РёРјРµРЅРё РєР»СЋС‡Р° РґР»СЏ РїРµСЂРµРёРјРµРЅРѕРІР°РЅРёСЏ."""
    return f"РўРµРєСѓС‰РµРµ РёРјСЏ: <b>{_safe(key.get('display_name'), 'VPN-РєР»СЋС‡')}</b>"


def build_new_key_server_select_data() -> str:
    """РћРїРёСЃР°РЅРёРµ РІС‹Р±РѕСЂР° СЃРµСЂРІРµСЂР° РїРѕСЃР»Рµ РѕРїР»Р°С‚С‹."""
    return "рџ”‘ РўРµРїРµСЂСЊ РІС‹Р±РµСЂРёС‚Рµ СЃРµСЂРІРµСЂ РґР»СЏ РІР°С€РµРіРѕ РЅРѕРІРѕРіРѕ РєР»СЋС‡Р°."


def build_new_key_server_back_data() -> str:
    """РћРїРёСЃР°РЅРёРµ РІС‹Р±РѕСЂР° СЃРµСЂРІРµСЂР° РїСЂРё РІРѕР·РІСЂР°С‚Рµ СЃРѕ СЃР»РµРґСѓСЋС‰РµРіРѕ С€Р°РіР°."""
    return "рџ”‘ Р’С‹Р±РµСЂРёС‚Рµ СЃРµСЂРІРµСЂ РґР»СЏ РІР°С€РµРіРѕ РЅРѕРІРѕРіРѕ РєР»СЋС‡Р°."
