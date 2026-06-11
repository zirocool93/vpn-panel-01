from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from typing import List, Dict, Any, Optional

from .admin_misc import back_button, home_button, cancel_button

def payments_menu_kb(stars_enabled: bool, crypto_enabled: bool, cards_enabled: bool, qr_enabled: bool=False, monthly_reset_enabled: bool=False, demo_enabled: bool=False, wata_enabled: bool=False, platega_enabled: bool=False, cardlink_enabled: bool=False, notify_enabled: bool=False) -> InlineKeyboardMarkup:
    """
    Р“Р»Р°РІРЅРѕРµ РјРµРЅСЋ СЂР°Р·РґРµР»Р° РѕРїР»Р°С‚.

    Args:
        stars_enabled: Р’РєР»СЋС‡РµРЅС‹ Р»Рё Telegram Stars
        crypto_enabled: Р’РєР»СЋС‡РµРЅС‹ Р»Рё РєСЂРёРїС‚Рѕ-РїР»Р°С‚РµР¶Рё
        cards_enabled: Р’РєР»СЋС‡РµРЅР° Р»Рё РѕРїР»Р°С‚Р° РєР°СЂС‚Р°РјРё (Р®РљР°СЃСЃР° Telegram Payments)
        qr_enabled: Р’РєР»СЋС‡РµРЅР° Р»Рё РїСЂСЏРјР°СЏ QR-РѕРїР»Р°С‚Р° Р®РљР°СЃСЃР°
        monthly_reset_enabled: Р’РєР»СЋС‡С‘РЅ Р»Рё РµР¶РµРјРµСЃСЏС‡РЅС‹Р№ Р°РІС‚РѕСЃР±СЂРѕСЃ С‚СЂР°С„РёРєР°
        demo_enabled: Р’РєР»СЋС‡РµРЅР° Р»Рё РґРµРјРѕ-РѕРїР»Р°С‚Р°
        wata_enabled: Р’РєР»СЋС‡РµРЅР° Р»Рё РѕРїР»Р°С‚Р° С‡РµСЂРµР· WATA
        platega_enabled: Р’РєР»СЋС‡РµРЅР° Р»Рё РѕРїР»Р°С‚Р° С‡РµСЂРµР· Platega
        cardlink_enabled: Р’РєР»СЋС‡РµРЅР° Р»Рё РѕРїР»Р°С‚Р° С‡РµСЂРµР· Cardlink
    """
    builder = InlineKeyboardBuilder()
    stars_status = 'вњ…' if stars_enabled else 'вќЊ'
    builder.row(InlineKeyboardButton(text=f'в­ђ Telegram Stars: {stars_status}', callback_data='admin_payments_toggle_stars'))
    crypto_status = 'вњ…' if crypto_enabled else 'вќЊ'
    builder.row(InlineKeyboardButton(text=f'рџ’° РљСЂРёРїС‚Рѕ-РїР»Р°С‚РµР¶Рё: {crypto_status}', callback_data='admin_payments_toggle_crypto'))
    cards_status = 'вњ…' if cards_enabled else 'вќЊ'
    builder.row(InlineKeyboardButton(text=f'рџ“± TG payments (Р®РљР°СЃСЃР°): {cards_status}', callback_data='admin_payments_cards'))
    qr_status = 'вњ…' if qr_enabled else 'вќЊ'
    builder.row(InlineKeyboardButton(text=f'рџ’і Р®РљР°СЃСЃР° (QR/РЎР‘Рџ): {qr_status}', callback_data='admin_payments_qr'))
    wata_status = 'вњ…' if wata_enabled else 'вќЊ'
    builder.row(InlineKeyboardButton(text=f'рџЊЉ WATA (РљР°СЂС‚Р°/РЎР‘Рџ): {wata_status}', callback_data='admin_payments_wata'))
    platega_status = 'вњ…' if platega_enabled else 'вќЊ'
    builder.row(InlineKeyboardButton(text=f'рџ’ё Platega (РЎР‘Рџ): {platega_status}', callback_data='admin_payments_platega'))
    cardlink_status = 'вњ…' if cardlink_enabled else 'вќЊ'
    builder.row(InlineKeyboardButton(text=f'🔗 Cardlink (Карта/СБП): {cardlink_status}', callback_data='admin_payments_cardlink'))
    demo_status = 'вњ…' if demo_enabled else 'вќЊ'
    builder.row(InlineKeyboardButton(text=f'рџ’і Р”РµРјРѕ РѕРїР»Р°С‚Р° (Р Р¤): {demo_status}', callback_data='admin_payments_toggle_demo'))
    reset_status = 'вњ…' if monthly_reset_enabled else 'вќЊ'
    builder.row(InlineKeyboardButton(text=f'рџ”„ РђРІС‚РѕСЃР±СЂРѕСЃ С‚СЂР°С„РёРєР° 1-РіРѕ С‡РёСЃР»Р°: {reset_status}', callback_data='admin_toggle_monthly_reset'))
    notify_status = '✅' if notify_enabled else '❌'
    builder.row(InlineKeyboardButton(text=f'🔔 Уведомления об оплатах: {notify_status}', callback_data='admin_toggle_payment_notify'))
    builder.row(InlineKeyboardButton(text='рџ“‚ Р“СЂСѓРїРїС‹ С‚Р°СЂРёС„РѕРІ', callback_data='admin_groups'))
    builder.row(InlineKeyboardButton(text='рџ“‹ РўР°СЂРёС„С‹', callback_data='admin_tariffs'))
    builder.row(InlineKeyboardButton(text='рџЋЃ РџСЂРѕР±РЅР°СЏ РїРѕРґРїРёСЃРєР°', callback_data='admin_trial'))
    builder.row(back_button('admin_panel'), home_button())
    return builder.as_markup()


def wata_management_kb(is_enabled: bool) -> InlineKeyboardMarkup:
    """
    РњРµРЅСЋ СѓРїСЂР°РІР»РµРЅРёСЏ РѕРїР»Р°С‚РѕР№ С‡РµСЂРµР· WATA.

    Args:
        is_enabled: Р’РєР»СЋС‡РµРЅР° Р»Рё WATA-РѕРїР»Р°С‚Р° СЃРµР№С‡Р°СЃ
    """
    builder = InlineKeyboardBuilder()
    toggle_text = 'Р’С‹РєР»СЋС‡РёС‚СЊ рџ”ґ' if is_enabled else 'Р’РєР»СЋС‡РёС‚СЊ рџџў'
    builder.row(InlineKeyboardButton(text=toggle_text, callback_data='admin_wata_mgmt_toggle'))
    builder.row(InlineKeyboardButton(text='рџ”‘ РР·РјРµРЅРёС‚СЊ JWT-С‚РѕРєРµРЅ', callback_data='admin_wata_mgmt_edit_token'))
    builder.row(back_button('admin_payments'), home_button())
    return builder.as_markup()


def platega_management_kb(is_enabled: bool) -> InlineKeyboardMarkup:
    """
    РњРµРЅСЋ СѓРїСЂР°РІР»РµРЅРёСЏ РѕРїР»Р°С‚РѕР№ С‡РµСЂРµР· Platega.

    Args:
        is_enabled: Р’РєР»СЋС‡РµРЅР° Р»Рё Platega-РѕРїР»Р°С‚Р° СЃРµР№С‡Р°СЃ
    """
    builder = InlineKeyboardBuilder()
    toggle_text = 'Р’С‹РєР»СЋС‡РёС‚СЊ рџ”ґ' if is_enabled else 'Р’РєР»СЋС‡РёС‚СЊ рџџў'
    builder.row(InlineKeyboardButton(text=toggle_text, callback_data='admin_platega_mgmt_toggle'))
    builder.row(InlineKeyboardButton(text='рџ†” РР·РјРµРЅРёС‚СЊ Merchant ID', callback_data='admin_platega_mgmt_edit_merchant'))
    builder.row(InlineKeyboardButton(text='рџ”ђ РР·РјРµРЅРёС‚СЊ Secret', callback_data='admin_platega_mgmt_edit_secret'))
    builder.row(back_button('admin_payments'), home_button())
    return builder.as_markup()


def cardlink_management_kb(is_enabled: bool) -> InlineKeyboardMarkup:
    """
    РњРµРЅСЋ СѓРїСЂР°РІР»РµРЅРёСЏ РѕРїР»Р°С‚РѕР№ С‡РµСЂРµР· Cardlink.

    Args:
        is_enabled: Р’РєР»СЋС‡РµРЅР° Р»Рё Cardlink-РѕРїР»Р°С‚Р° СЃРµР№С‡Р°СЃ
    """
    builder = InlineKeyboardBuilder()
    toggle_text = 'Р’С‹РєР»СЋС‡РёС‚СЊ рџ”ґ' if is_enabled else 'Р’РєР»СЋС‡РёС‚СЊ рџџў'
    builder.row(InlineKeyboardButton(text=toggle_text, callback_data='admin_cardlink_mgmt_toggle'))
    builder.row(InlineKeyboardButton(text='рџ†” РР·РјРµРЅРёС‚СЊ Shop ID', callback_data='admin_cardlink_mgmt_edit_shop_id'))
    builder.row(InlineKeyboardButton(text='рџ”ђ РР·РјРµРЅРёС‚СЊ API-С‚РѕРєРµРЅ', callback_data='admin_cardlink_mgmt_edit_api_token'))
    builder.row(back_button('admin_payments'), home_button())
    return builder.as_markup()

def crypto_setup_kb(step: int) -> InlineKeyboardMarkup:
    """
    РљР»Р°РІРёР°С‚СѓСЂР° РґР»СЏ С€Р°РіР° РЅР°СЃС‚СЂРѕР№РєРё РєСЂРёРїС‚Рѕ-РїР»Р°С‚РµР¶РµР№.
    
    Args:
        step: РўРµРєСѓС‰РёР№ С€Р°Рі (1 = СЃСЃС‹Р»РєР°, 2 = РєР»СЋС‡)
    """
    builder = InlineKeyboardBuilder()
    buttons = []
    if step > 1:
        buttons.append(InlineKeyboardButton(text='в¬…пёЏ РќР°Р·Р°Рґ', callback_data='admin_crypto_setup_back'))
    buttons.append(InlineKeyboardButton(text='вќЊ РћС‚РјРµРЅР°', callback_data='admin_payments'))
    builder.row(*buttons)
    return builder.as_markup()

def crypto_setup_confirm_kb() -> InlineKeyboardMarkup:
    """РљР»Р°РІРёР°С‚СѓСЂР° РїРѕРґС‚РІРµСЂР¶РґРµРЅРёСЏ РЅР°СЃС‚СЂРѕРµРє РєСЂРёРїС‚Рѕ."""
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text='вњ… РЎРѕС…СЂР°РЅРёС‚СЊ Рё РІРєР»СЋС‡РёС‚СЊ', callback_data='admin_crypto_setup_save'))
    builder.row(InlineKeyboardButton(text='в¬…пёЏ РќР°Р·Р°Рґ', callback_data='admin_crypto_setup_back'), InlineKeyboardButton(text='вќЊ РћС‚РјРµРЅР°', callback_data='admin_payments'))
    return builder.as_markup()

def cards_management_kb(is_enabled: bool) -> InlineKeyboardMarkup:
    """РљР»Р°РІРёР°С‚СѓСЂР° СѓРїСЂР°РІР»РµРЅРёСЏ РѕРїР»Р°С‚РѕР№ РєР°СЂС‚Р°РјРё."""
    builder = InlineKeyboardBuilder()
    toggle_text = 'Р’С‹РєР»СЋС‡РёС‚СЊ рџ”ґ' if is_enabled else 'Р’РєР»СЋС‡РёС‚СЊ рџџў'
    builder.row(InlineKeyboardButton(text=toggle_text, callback_data='admin_cards_mgmt_toggle'))
    builder.row(InlineKeyboardButton(text='рџ”— РР·РјРµРЅРёС‚СЊ Provider Token', callback_data='admin_cards_mgmt_edit_token'))
    builder.row(back_button('admin_payments'), home_button())
    return builder.as_markup()


def edit_crypto_kb(current_param: int, total_params: int) -> InlineKeyboardMarkup:
    """
    РљР»Р°РІРёР°С‚СѓСЂР° СЂРµРґР°РєС‚РёСЂРѕРІР°РЅРёСЏ РєСЂРёРїС‚Рѕ-РЅР°СЃС‚СЂРѕРµРє СЃ РЅР°РІРёРіР°С†РёРµР№.
    
    Args:
        current_param: РРЅРґРµРєСЃ С‚РµРєСѓС‰РµРіРѕ РїР°СЂР°РјРµС‚СЂР°
        total_params: РћР±С‰РµРµ РєРѕР»РёС‡РµСЃС‚РІРѕ РїР°СЂР°РјРµС‚СЂРѕРІ
    """
    builder = InlineKeyboardBuilder()
    nav_buttons = []
    if current_param > 0:
        nav_buttons.append(InlineKeyboardButton(text='в¬…пёЏ РџСЂРµРґ.', callback_data='admin_crypto_edit_prev'))
    else:
        nav_buttons.append(InlineKeyboardButton(text='вЂ”', callback_data='noop'))
    if current_param < total_params - 1:
        nav_buttons.append(InlineKeyboardButton(text='вћЎпёЏ РЎР»РµРґ.', callback_data='admin_crypto_edit_next'))
    else:
        nav_buttons.append(InlineKeyboardButton(text='вЂ”', callback_data='noop'))
    builder.row(*nav_buttons)
    builder.row(InlineKeyboardButton(text='вњ… Р“РѕС‚РѕРІРѕ', callback_data='admin_crypto_edit_done'))
    return builder.as_markup()

def crypto_management_kb(is_enabled: bool) -> InlineKeyboardMarkup:
    """
    РњРµРЅСЋ СѓРїСЂР°РІР»РµРЅРёСЏ РєСЂРёРїС‚Рѕ-РїР»Р°С‚РµР¶Р°РјРё.
    
    Args:
        is_enabled: Р’РєР»СЋС‡РµРЅС‹ Р»Рё РєСЂРёРїС‚Рѕ-РїР»Р°С‚РµР¶Рё СЃРµР№С‡Р°СЃ
    """
    builder = InlineKeyboardBuilder()
    status_text = 'рџџў Р’С‹РєР»СЋС‡РёС‚СЊ' if is_enabled else 'вљЄ Р’РєР»СЋС‡РёС‚СЊ'
    builder.row(InlineKeyboardButton(text=status_text, callback_data='admin_crypto_mgmt_toggle'))
    builder.row(InlineKeyboardButton(text='рџ”— РР·РјРµРЅРёС‚СЊ СЃСЃС‹Р»РєСѓ РЅР° С‚РѕРІР°СЂ', callback_data='admin_crypto_mgmt_edit_url'))
    builder.row(InlineKeyboardButton(text='рџ”ђ РР·РјРµРЅРёС‚СЊ СЃРµРєСЂРµС‚РЅС‹Р№ РєР»СЋС‡', callback_data='admin_crypto_mgmt_edit_secret'))
    builder.row(back_button('admin_payments'), home_button())
    return builder.as_markup()
