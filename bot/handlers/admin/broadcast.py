"""
РћР±СЂР°Р±РѕС‚С‡РёРєРё СЂР°Р·РґРµР»Р° В«Р Р°СЃСЃС‹Р»РєР°В» РІ Р°РґРјРёРЅ-РїР°РЅРµР»Рё.

Р¤СѓРЅРєС†РёРѕРЅР°Р»:
- Р Р°СЃСЃС‹Р»РєР° СЃРѕРѕР±С‰РµРЅРёР№ РІСЃРµРј РїРѕР»СЊР·РѕРІР°С‚РµР»СЏРј СЃ С„РёР»СЊС‚СЂР°РјРё
- РќР°СЃС‚СЂРѕР№РєР° Р°РІС‚РѕСѓРІРµРґРѕРјР»РµРЅРёР№ РѕР± РёСЃС‚РµС‡РµРЅРёРё РєР»СЋС‡РµР№
"""
import json
import asyncio
import logging
from aiogram import Router, F, Bot
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.exceptions import TelegramBadRequest

from config import ADMIN_IDS
from database.requests import (
    get_setting, set_setting, mark_user_bot_blocked,
    get_users_for_broadcast, count_users_for_broadcast
)
from bot.states.admin_states import AdminStates
from bot.utils.admin import is_admin
from bot.utils.delivery import is_bot_blocked_error
from bot.keyboards.admin import (
    broadcast_main_kb, broadcast_confirm_kb,
    broadcast_notifications_kb, broadcast_back_kb,
    broadcast_notify_back_kb, home_only_kb,
    BROADCAST_FILTERS
)

logger = logging.getLogger(__name__)

from bot.utils.text import safe_edit_or_send

router = Router()


# ============================================================================
# Р’РЎРџРћРњРћР“РђРўР•Р›Р¬РќР«Р• Р¤РЈРќРљР¦РР
# ============================================================================




def get_broadcast_message() -> dict | None:
    """
    РџРѕР»СѓС‡Р°РµС‚ СЃРѕС…СЂР°РЅС‘РЅРЅРѕРµ СЃРѕРѕР±С‰РµРЅРёРµ РґР»СЏ СЂР°СЃСЃС‹Р»РєРё.
    
    Returns:
        РЎР»РѕРІР°СЂСЊ СЃ РєР»СЋС‡Р°РјРё 'text' Рё 'photo_file_id' РёР»Рё None
    """
    msg_json = get_setting('broadcast_message')
    if msg_json:
        try:
            return json.loads(msg_json)
        except json.JSONDecodeError:
            return None
    return None


def save_broadcast_message(text: str, photo_file_id: str | None = None) -> None:
    """РЎРѕС…СЂР°РЅСЏРµС‚ СЃРѕРѕР±С‰РµРЅРёРµ РґР»СЏ СЂР°СЃСЃС‹Р»РєРё."""
    data = {'text': text, 'photo_file_id': photo_file_id}
    set_setting('broadcast_message', json.dumps(data, ensure_ascii=False))


def is_broadcast_in_progress() -> bool:
    """РџСЂРѕРІРµСЂСЏРµС‚, РёРґС‘С‚ Р»Рё СЂР°СЃСЃС‹Р»РєР° СЃРµР№С‡Р°СЃ."""
    return get_setting('broadcast_in_progress', '0') == '1'


def set_broadcast_in_progress(value: bool) -> None:
    """РЈСЃС‚Р°РЅР°РІР»РёРІР°РµС‚ С„Р»Р°Рі СЂР°СЃСЃС‹Р»РєРё."""
    set_setting('broadcast_in_progress', '1' if value else '0')


# ============================================================================
# Р“Р›РђР’РќР«Р™ Р­РљР РђРќ Р РђРЎРЎР«Р›РљР
# ============================================================================

@router.callback_query(F.data == "admin_broadcast")
async def show_broadcast_menu(callback: CallbackQuery, state: FSMContext):
    """РџРѕРєР°Р·С‹РІР°РµС‚ РіР»Р°РІРЅС‹Р№ СЌРєСЂР°РЅ СЂР°Р·РґРµР»Р° СЂР°СЃСЃС‹Р»РєРё."""
    if not is_admin(callback.from_user.id):
        await callback.answer("в›” Р”РѕСЃС‚СѓРї Р·Р°РїСЂРµС‰С‘РЅ", show_alert=True)
        return
    
    await state.set_state(AdminStates.broadcast_menu)
    
    # РџРѕР»СѓС‡Р°РµРј РґР°РЅРЅС‹Рµ РґР»СЏ РѕС‚РѕР±СЂР°Р¶РµРЅРёСЏ
    msg_data = get_broadcast_message()
    has_message = msg_data is not None and msg_data.get('text')
    
    current_filter = get_setting('broadcast_filter', 'all')
    in_progress = is_broadcast_in_progress()
    user_count = count_users_for_broadcast(current_filter)
    
    text = (
        "рџ“ў <b>Р Р°СЃСЃС‹Р»РєР°</b>\n\n"
        "РћС‚РїСЂР°РІСЊС‚Рµ СЃРѕРѕР±С‰РµРЅРёРµ РІСЃРµРј РїРѕР»СЊР·РѕРІР°С‚РµР»СЏРј Р±РѕС‚Р°.\n\n"
        "1пёЏвѓЈ РћС‚СЂРµРґР°РєС‚РёСЂСѓР№С‚Рµ СЃРѕРѕР±С‰РµРЅРёРµ\n"
        "2пёЏвѓЈ Р’С‹Р±РµСЂРёС‚Рµ С„РёР»СЊС‚СЂ РїРѕР»СѓС‡Р°С‚РµР»РµР№\n"
        "3пёЏвѓЈ РќР°Р¶РјРёС‚Рµ В«РќР°С‡Р°С‚СЊ СЂР°СЃСЃС‹Р»РєСѓВ»"
    )
    
    await safe_edit_or_send(callback.message, 
        text,
        reply_markup=broadcast_main_kb(has_message, current_filter, in_progress, user_count)
    )
    await callback.answer()


@router.callback_query(F.data == "noop")
async def noop_callback(callback: CallbackQuery):
    """РџСѓСЃС‚РѕР№ РѕР±СЂР°Р±РѕС‚С‡РёРє РґР»СЏ СЂР°Р·РґРµР»РёС‚РµР»СЏ."""
    if not is_admin(callback.from_user.id):
        await callback.answer()
        return
    await callback.answer()


# ============================================================================
# Р Р•Р”РђРљРўРР РћР’РђРќРР• РЎРћРћР‘Р©Р•РќРРЇ
# ============================================================================

@router.callback_query(F.data == "broadcast_edit_message")
async def broadcast_edit_message(callback: CallbackQuery, state: FSMContext):
    """РќР°С‡РёРЅР°РµС‚ СЂРµРґР°РєС‚РёСЂРѕРІР°РЅРёРµ СЃРѕРѕР±С‰РµРЅРёСЏ РґР»СЏ СЂР°СЃСЃС‹Р»РєРё."""
    if not is_admin(callback.from_user.id):
        await callback.answer("в›” Р”РѕСЃС‚СѓРї Р·Р°РїСЂРµС‰С‘РЅ", show_alert=True)
        return
    
    await state.set_state(AdminStates.broadcast_waiting_message)
    
    text = (
        "вњ‰пёЏ <b>Р РµРґР°РєС‚РёСЂРѕРІР°РЅРёРµ СЃРѕРѕР±С‰РµРЅРёСЏ</b>\n\n"
        "РћС‚РїСЂР°РІСЊС‚Рµ РјРЅРµ СЃРѕРѕР±С‰РµРЅРёРµ, РєРѕС‚РѕСЂРѕРµ С…РѕС‚РёС‚Рµ СЂР°Р·РѕСЃР»Р°С‚СЊ.\n\n"
        "РњРѕР¶РЅРѕ РѕС‚РїСЂР°РІРёС‚СЊ:\n"
        "вЂў РўРµРєСЃС‚ (СЃ С„РѕСЂРјР°С‚РёСЂРѕРІР°РЅРёРµРј)\n"
        "вЂў Р¤РѕС‚Рѕ СЃ РїРѕРґРїРёСЃСЊСЋ\n\n"
        "рџ’Ў РЎРѕРѕР±С‰РµРЅРёРµ Р±СѓРґРµС‚ РѕС‚РїСЂР°РІР»РµРЅРѕ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏРј РІ С‚РѕС‡РЅРѕСЃС‚Рё РєР°Рє РІС‹ РµРіРѕ РїСЂРёСЃР»Р°Р»Рё."
    )
    
    await safe_edit_or_send(callback.message, 
        text,
        reply_markup=broadcast_back_kb()
    )
    await callback.answer()


@router.message(AdminStates.broadcast_waiting_message)
async def broadcast_save_message(message: Message, state: FSMContext):
    """РЎРѕС…СЂР°РЅСЏРµС‚ СЃРѕРѕР±С‰РµРЅРёРµ РґР»СЏ СЂР°СЃСЃС‹Р»РєРё."""
    if not is_admin(message.from_user.id):
        return
    
    from bot.utils.text import get_message_text_for_storage, safe_edit_or_send
    
    text = None
    photo_file_id = None
    
    if message.photo:
        photo_file_id = message.photo[-1].file_id
        text = get_message_text_for_storage(message, 'html')
    elif message.text:
        text = get_message_text_for_storage(message, 'html')
    else:
        await safe_edit_or_send(message,
            "вќЊ РџРѕРґРґРµСЂР¶РёРІР°СЋС‚СЃСЏ С‚РѕР»СЊРєРѕ С‚РµРєСЃС‚ РёР»Рё С„РѕС‚Рѕ СЃ РїРѕРґРїРёСЃСЊСЋ.",
            reply_markup=broadcast_back_kb()
        )
        return
    
    save_broadcast_message(text, photo_file_id)
    
    await safe_edit_or_send(message,
        "вњ… <b>РЎРѕРѕР±С‰РµРЅРёРµ СЃРѕС…СЂР°РЅРµРЅРѕ!</b>\n\n"
        "РўРµРїРµСЂСЊ РјРѕР¶РµС‚Рµ РїРѕСЃРјРѕС‚СЂРµС‚СЊ РїСЂРµРІСЊСЋ РёР»Рё РЅР°С‡Р°С‚СЊ СЂР°СЃСЃС‹Р»РєСѓ."
    )
    
    # Р’РѕР·РІСЂР°С‰Р°РµРјСЃСЏ РІ РјРµРЅСЋ СЂР°СЃСЃС‹Р»РєРё
    await state.set_state(AdminStates.broadcast_menu)
    
    msg_data = get_broadcast_message()
    has_message = msg_data is not None
    current_filter = get_setting('broadcast_filter', 'all')
    in_progress = is_broadcast_in_progress()
    user_count = count_users_for_broadcast(current_filter)
    
    text = (
        "рџ“ў <b>Р Р°СЃСЃС‹Р»РєР°</b>\n\n"
        "РћС‚РїСЂР°РІСЊС‚Рµ СЃРѕРѕР±С‰РµРЅРёРµ РІСЃРµРј РїРѕР»СЊР·РѕРІР°С‚РµР»СЏРј Р±РѕС‚Р°.\n\n"
        "1пёЏвѓЈ РћС‚СЂРµРґР°РєС‚РёСЂСѓР№С‚Рµ СЃРѕРѕР±С‰РµРЅРёРµ\n"
        "2пёЏвѓЈ Р’С‹Р±РµСЂРёС‚Рµ С„РёР»СЊС‚СЂ РїРѕР»СѓС‡Р°С‚РµР»РµР№\n"
        "3пёЏвѓЈ РќР°Р¶РјРёС‚Рµ В«РќР°С‡Р°С‚СЊ СЂР°СЃСЃС‹Р»РєСѓВ»"
    )
    
    await safe_edit_or_send(message,
        text,
        reply_markup=broadcast_main_kb(has_message, current_filter, in_progress, user_count),
        force_new=True
    )


# ============================================================================
# РџР Р•Р’Р¬Р® РЎРћРћР‘Р©Р•РќРРЇ
# ============================================================================

@router.callback_query(F.data == "broadcast_preview")
async def broadcast_preview(callback: CallbackQuery):
    """РџРѕРєР°Р·С‹РІР°РµС‚ РїСЂРµРІСЊСЋ СЃРѕРѕР±С‰РµРЅРёСЏ РґР»СЏ СЂР°СЃСЃС‹Р»РєРё."""
    if not is_admin(callback.from_user.id):
        await callback.answer("в›” Р”РѕСЃС‚СѓРї Р·Р°РїСЂРµС‰С‘РЅ", show_alert=True)
        return
    
    msg_data = get_broadcast_message()
    
    if not msg_data or not msg_data.get('text'):
        await callback.answer("вќЊ РЎРѕРѕР±С‰РµРЅРёРµ РЅРµ Р·Р°РґР°РЅРѕ", show_alert=True)
        return
    
    await callback.answer("рџ“¤ РћС‚РїСЂР°РІР»СЏСЋ РїСЂРµРІСЊСЋ...")
    
    # РћС‚РїСЂР°РІР»СЏРµРј РїСЂРµРІСЊСЋ РєР°Рє РѕС‚РґРµР»СЊРЅРѕРµ СЃРѕРѕР±С‰РµРЅРёРµ
    if msg_data.get('photo_file_id'):
        await safe_edit_or_send(callback.message,
            photo=msg_data['photo_file_id'],
            text=msg_data.get('text', ''),
            force_new=True
        )
    else:
        await safe_edit_or_send(callback.message,
            text=msg_data['text'],
            force_new=True
        )


# ============================================================================
# Р¤РР›Р¬РўР Р«
# ============================================================================

@router.callback_query(F.data.startswith("broadcast_filter:"))
async def broadcast_set_filter(callback: CallbackQuery):
    """РЈСЃС‚Р°РЅР°РІР»РёРІР°РµС‚ С„РёР»СЊС‚СЂ РїРѕР»СѓС‡Р°С‚РµР»РµР№."""
    if not is_admin(callback.from_user.id):
        await callback.answer("в›” Р”РѕСЃС‚СѓРї Р·Р°РїСЂРµС‰С‘РЅ", show_alert=True)
        return
    
    filter_key = callback.data.split(":")[1]
    
    if filter_key not in BROADCAST_FILTERS:
        await callback.answer("вќЊ РќРµРёР·РІРµСЃС‚РЅС‹Р№ С„РёР»СЊС‚СЂ", show_alert=True)
        return
    
    set_setting('broadcast_filter', filter_key)
    
    # РћР±РЅРѕРІР»СЏРµРј СЌРєСЂР°РЅ
    msg_data = get_broadcast_message()
    has_message = msg_data is not None and msg_data.get('text')
    in_progress = is_broadcast_in_progress()
    user_count = count_users_for_broadcast(filter_key)
    
    text = (
        "рџ“ў <b>Р Р°СЃСЃС‹Р»РєР°</b>\n\n"
        "РћС‚РїСЂР°РІСЊС‚Рµ СЃРѕРѕР±С‰РµРЅРёРµ РІСЃРµРј РїРѕР»СЊР·РѕРІР°С‚РµР»СЏРј Р±РѕС‚Р°.\n\n"
        "1пёЏвѓЈ РћС‚СЂРµРґР°РєС‚РёСЂСѓР№С‚Рµ СЃРѕРѕР±С‰РµРЅРёРµ\n"
        "2пёЏвѓЈ Р’С‹Р±РµСЂРёС‚Рµ С„РёР»СЊС‚СЂ РїРѕР»СѓС‡Р°С‚РµР»РµР№\n"
        "3пёЏвѓЈ РќР°Р¶РјРёС‚Рµ В«РќР°С‡Р°С‚СЊ СЂР°СЃСЃС‹Р»РєСѓВ»"
    )
    
    await safe_edit_or_send(callback.message, 
        text,
        reply_markup=broadcast_main_kb(has_message, filter_key, in_progress, user_count)
    )
    await callback.answer(f"Р¤РёР»СЊС‚СЂ: {BROADCAST_FILTERS[filter_key]}")


# ============================================================================
# Р—РђРџРЈРЎРљ Р РђРЎРЎР«Р›РљР
# ============================================================================

@router.callback_query(F.data == "broadcast_start")
async def broadcast_start(callback: CallbackQuery):
    """РџРѕРєР°Р·С‹РІР°РµС‚ РїРѕРґС‚РІРµСЂР¶РґРµРЅРёРµ СЂР°СЃСЃС‹Р»РєРё."""
    if not is_admin(callback.from_user.id):
        await callback.answer("в›” Р”РѕСЃС‚СѓРї Р·Р°РїСЂРµС‰С‘РЅ", show_alert=True)
        return
    
    # РџСЂРѕРІРµСЂСЏРµРј, РЅРµ РёРґС‘С‚ Р»Рё СѓР¶Рµ СЂР°СЃСЃС‹Р»РєР°
    if is_broadcast_in_progress():
        await callback.answer("вЏі Р Р°СЃСЃС‹Р»РєР° СѓР¶Рµ РёРґС‘С‚!", show_alert=True)
        return
    
    # РџСЂРѕРІРµСЂСЏРµРј РЅР°Р»РёС‡РёРµ СЃРѕРѕР±С‰РµРЅРёСЏ
    msg_data = get_broadcast_message()
    if not msg_data or not msg_data.get('text'):
        await callback.answer("вќЊ РЎРЅР°С‡Р°Р»Р° Р·Р°РґР°Р№С‚Рµ СЃРѕРѕР±С‰РµРЅРёРµ!", show_alert=True)
        return
    
    current_filter = get_setting('broadcast_filter', 'all')
    user_count = count_users_for_broadcast(current_filter)
    
    if user_count == 0:
        await callback.answer("вќЊ РќРµС‚ РїРѕР»СЊР·РѕРІР°С‚РµР»РµР№ РґР»СЏ СЂР°СЃСЃС‹Р»РєРё!", show_alert=True)
        return
    
    filter_name = BROADCAST_FILTERS.get(current_filter, 'Р’СЃРµ')
    
    text = (
        "рџљЂ <b>РџРѕРґС‚РІРµСЂР¶РґРµРЅРёРµ СЂР°СЃСЃС‹Р»РєРё</b>\n\n"
        f"<b>Р¤РёР»СЊС‚СЂ:</b> {filter_name}\n"
        f"<b>РџРѕР»СѓС‡Р°С‚РµР»РµР№:</b> {user_count} С‡РµР».\n\n"
        "РќР°С‡Р°С‚СЊ СЂР°СЃСЃС‹Р»РєСѓ?"
    )
    
    await safe_edit_or_send(callback.message, 
        text,
        reply_markup=broadcast_confirm_kb(user_count)
    )
    await callback.answer()


@router.callback_query(F.data == "broadcast_in_progress")
async def broadcast_in_progress_callback(callback: CallbackQuery):
    """РЈРІРµРґРѕРјР»РµРЅРёРµ Рѕ С‚РѕРј, С‡С‚Рѕ СЂР°СЃСЃС‹Р»РєР° СѓР¶Рµ РёРґС‘С‚."""
    if not is_admin(callback.from_user.id):
        await callback.answer("в›” Р”РѕСЃС‚СѓРї Р·Р°РїСЂРµС‰С‘РЅ", show_alert=True)
        return
    await callback.answer("вЏі Р Р°СЃСЃС‹Р»РєР° СѓР¶Рµ РёРґС‘С‚, РґРѕР¶РґРёС‚РµСЃСЊ Р·Р°РІРµСЂС€РµРЅРёСЏ", show_alert=True)


@router.callback_query(F.data == "broadcast_confirm")
async def broadcast_confirm(callback: CallbackQuery, bot: Bot):
    """Р—Р°РїСѓСЃРєР°РµС‚ СЂР°СЃСЃС‹Р»РєСѓ."""
    if not is_admin(callback.from_user.id):
        await callback.answer("в›” Р”РѕСЃС‚СѓРї Р·Р°РїСЂРµС‰С‘РЅ", show_alert=True)
        return
    
    # РџСЂРѕРІРµСЂСЏРµРј РµС‰С‘ СЂР°Р·
    if is_broadcast_in_progress():
        await callback.answer("вЏі Р Р°СЃСЃС‹Р»РєР° СѓР¶Рµ РёРґС‘С‚!", show_alert=True)
        return
    
    msg_data = get_broadcast_message()
    if not msg_data:
        await callback.answer("вќЊ РЎРѕРѕР±С‰РµРЅРёРµ РЅРµ Р·Р°РґР°РЅРѕ!", show_alert=True)
        return
    
    current_filter = get_setting('broadcast_filter', 'all')
    user_ids = get_users_for_broadcast(current_filter)
    
    if not user_ids:
        await callback.answer("вќЊ РќРµС‚ РїРѕР»СѓС‡Р°С‚РµР»РµР№!", show_alert=True)
        return
    
    # РЈСЃС‚Р°РЅР°РІР»РёРІР°РµРј С„Р»Р°Рі
    set_broadcast_in_progress(True)
    
    total = len(user_ids)
    sent = 0
    blocked = 0
    failed = 0

    await safe_edit_or_send(callback.message,
        f"📤 <b>Рассылка запущена</b>\n\n"
        f"Отправлено: 0/{total}\n"
        f"🚫 Заблокировали бота: 0\n"
        f"⚠️ Ошибки: 0"
    )
    await callback.answer()

    text = msg_data.get("text", "")
    photo_file_id = msg_data.get("photo_file_id")

    for i, user_id in enumerate(user_ids):
        try:
            if photo_file_id:
                await bot.send_photo(
                    chat_id=user_id,
                    photo=photo_file_id,
                    caption=text,
                    parse_mode="HTML",
                )
            else:
                await bot.send_message(
                    chat_id=user_id,
                    text=text,
                    parse_mode="HTML",
                )
            sent += 1
        except TelegramBadRequest as e:
            logger.warning(f"Broadcast send error for {user_id}: {e}")
            failed += 1
        except Exception as e:
            if is_bot_blocked_error(e):
                mark_user_bot_blocked(user_id)
                blocked += 1
            else:
                logger.error(f"Unexpected broadcast send error for {user_id}: {e}")
                failed += 1

        if (i + 1) % 10 == 0 or (i + 1) == total:
            try:
                await safe_edit_or_send(callback.message,
                    f"📤 <b>Рассылка в процессе...</b>\n\n"
                    f"Отправлено: {sent}/{total}\n"
                    f"🚫 Заблокировали бота: {blocked}\n"
                    f"⚠️ Ошибки: {failed}"
                )
            except TelegramBadRequest:
                pass

        await asyncio.sleep(0.5)

    # РЎР±СЂР°СЃС‹РІР°РµРј С„Р»Р°Рі
    set_broadcast_in_progress(False)
    
    # РС‚РѕРіРѕРІС‹Р№ РѕС‚С‡С‘С‚
    await safe_edit_or_send(callback.message,
        f"✅ <b>Рассылка завершена!</b>\n\n"
        f"📤 Отправлено: {sent}\n"
        f"🚫 Заблокировали бота: {blocked}\n"
        f"⚠️ Ошибки: {failed}",
        reply_markup=home_only_kb()
    )


# ============================================================================
# РќРђРЎРўР РћР™РљР РђР’РўРћРЈР’Р•Р”РћРњР›Р•РќРР™
# ============================================================================

@router.callback_query(F.data == "broadcast_notifications")
async def broadcast_notifications(callback: CallbackQuery, state: FSMContext):
    """РџРѕРєР°Р·С‹РІР°РµС‚ РЅР°СЃС‚СЂРѕР№РєРё Р°РІС‚РѕСѓРІРµРґРѕРјР»РµРЅРёР№."""
    if not is_admin(callback.from_user.id):
        await callback.answer("в›” Р”РѕСЃС‚СѓРї Р·Р°РїСЂРµС‰С‘РЅ", show_alert=True)
        return
    
    days = int(get_setting('notification_days', '3'))
    
    text = (
        "вЏ° <b>РђРІС‚РѕСѓРІРµРґРѕРјР»РµРЅРёСЏ</b>\n\n"
        "Р‘РѕС‚ Р°РІС‚РѕРјР°С‚РёС‡РµСЃРєРё РЅР°РїРѕРјРёРЅР°РµС‚ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏРј РѕР± РёСЃС‚РµС‡РµРЅРёРё VPN-РєР»СЋС‡РµР№.\n\n"
        f"рџ“… РЈРІРµРґРѕРјР»СЏС‚СЊ Р·Р° <b>{days}</b> РґРЅРµР№ РґРѕ РёСЃС‚РµС‡РµРЅРёСЏ\n"
        "рџ“ќ РўРµРєСЃС‚ СѓРІРµРґРѕРјР»РµРЅРёСЏ РЅР°СЃС‚СЂР°РёРІР°РµС‚СЃСЏ РѕС‚РґРµР»СЊРЅРѕ"
    )
    
    await safe_edit_or_send(callback.message, 
        text,
        reply_markup=broadcast_notifications_kb(days)
    )
    await callback.answer()


@router.callback_query(F.data == "broadcast_notify_days")
async def broadcast_notify_days(callback: CallbackQuery, state: FSMContext):
    """РќР°С‡РёРЅР°РµС‚ РІРІРѕРґ РєРѕР»РёС‡РµСЃС‚РІР° РґРЅРµР№."""
    if not is_admin(callback.from_user.id):
        await callback.answer("в›” Р”РѕСЃС‚СѓРї Р·Р°РїСЂРµС‰С‘РЅ", show_alert=True)
        return
    
    await state.set_state(AdminStates.broadcast_waiting_notify_days)
    
    current_days = get_setting('notification_days', '3')
    
    text = (
        "рџ“… <b>Р—Р° СЃРєРѕР»СЊРєРѕ РґРЅРµР№ СѓРІРµРґРѕРјР»СЏС‚СЊ?</b>\n\n"
        f"РўРµРєСѓС‰РµРµ Р·РЅР°С‡РµРЅРёРµ: <b>{current_days}</b> РґРЅРµР№\n\n"
        "Р’РІРµРґРёС‚Рµ С‡РёСЃР»Рѕ РѕС‚ 1 РґРѕ 30:"
    )
    
    await safe_edit_or_send(callback.message, 
        text,
        reply_markup=broadcast_notify_back_kb()
    )
    await callback.answer()


@router.message(AdminStates.broadcast_waiting_notify_days)
async def broadcast_save_notify_days(message: Message, state: FSMContext):
    """РЎРѕС…СЂР°РЅСЏРµС‚ РєРѕР»РёС‡РµСЃС‚РІРѕ РґРЅРµР№ РґР»СЏ СѓРІРµРґРѕРјР»РµРЅРёСЏ."""
    if not is_admin(message.from_user.id):
        return
    
    if not message.text or not message.text.isdigit():
        await safe_edit_or_send(message,
            "вќЊ Р’РІРµРґРёС‚Рµ С‡РёСЃР»Рѕ!",
            reply_markup=broadcast_notify_back_kb()
        )
        return
    
    days = int(message.text)
    if not 1 <= days <= 30:
        await safe_edit_or_send(message,
            "вќЊ Р§РёСЃР»Рѕ РґРѕР»Р¶РЅРѕ Р±С‹С‚СЊ РѕС‚ 1 РґРѕ 30!",
            reply_markup=broadcast_notify_back_kb()
        )
        return
    
    set_setting('notification_days', str(days))
    
    await safe_edit_or_send(message,
        f"вњ… РўРµРїРµСЂСЊ СѓРІРµРґРѕРјР»РµРЅРёСЏ Р±СѓРґСѓС‚ РѕС‚РїСЂР°РІР»СЏС‚СЊСЃСЏ Р·Р° <b>{days}</b> РґРЅРµР№ РґРѕ РёСЃС‚РµС‡РµРЅРёСЏ."
    )
    
    # Р’РѕР·РІСЂР°С‰Р°РµРјСЃСЏ РІ РЅР°СЃС‚СЂРѕР№РєРё СѓРІРµРґРѕРјР»РµРЅРёР№
    await state.set_state(AdminStates.broadcast_menu)
    
    text = (
        "вЏ° <b>РђРІС‚РѕСѓРІРµРґРѕРјР»РµРЅРёСЏ</b>\n\n"
        "Р‘РѕС‚ Р°РІС‚РѕРјР°С‚РёС‡РµСЃРєРё РЅР°РїРѕРјРёРЅР°РµС‚ РїРѕР»СЊР·РѕРІР°С‚РµР»СЏРј РѕР± РёСЃС‚РµС‡РµРЅРёРё VPN-РєР»СЋС‡РµР№.\n\n"
        f"рџ“… РЈРІРµРґРѕРјР»СЏС‚СЊ Р·Р° <b>{days}</b> РґРЅРµР№ РґРѕ РёСЃС‚РµС‡РµРЅРёСЏ\n"
        "рџ“ќ РўРµРєСЃС‚ СѓРІРµРґРѕРјР»РµРЅРёСЏ РЅР°СЃС‚СЂР°РёРІР°РµС‚СЃСЏ РѕС‚РґРµР»СЊРЅРѕ"
    )
    
    await safe_edit_or_send(message,
        text,
        reply_markup=broadcast_notifications_kb(days),
        force_new=True
    )


@router.callback_query(F.data == "broadcast_notify_text")
async def broadcast_notify_text(callback: CallbackQuery, state: FSMContext):
    """РџРѕРєР°Р·С‹РІР°РµС‚/СЂРµРґР°РєС‚РёСЂСѓРµС‚ С‚РµРєСЃС‚ СѓРІРµРґРѕРјР»РµРЅРёСЏ С‡РµСЂРµР· СѓРЅРёРІРµСЂСЃР°Р»СЊРЅС‹Р№ СЂРµРґР°РєС‚РѕСЂ."""
    if not is_admin(callback.from_user.id):
        await callback.answer("в›” Р”РѕСЃС‚СѓРї Р·Р°РїСЂРµС‰С‘РЅ", show_alert=True)
        return
    
    from bot.handlers.admin.message_editor import show_message_editor
    
    await show_message_editor(
        callback.message, state,
        key='notification_text',
        back_callback='broadcast_notifications',
        help_text=(
            "рџ“ќ <b>РЎРїСЂР°РІРєР°: РўРµРєСЃС‚ СѓРІРµРґРѕРјР»РµРЅРёСЏ РѕР± РёСЃС‚РµС‡РµРЅРёРё</b>\n\n"
            "РџРµСЂРµРјРµРЅРЅС‹Рµ:\n"
            "вЂў <code>%РґРЅРµР№%</code> вЂ” РєРѕР»РёС‡РµСЃС‚РІРѕ РґРЅРµР№ РґРѕ РёСЃС‚РµС‡РµРЅРёСЏ\n"
            "вЂў <code>%РёРјСЏРєР»СЋС‡Р°%</code> вЂ” РёРјСЏ РєР»СЋС‡Р°"
        ),
        allowed_types=['text', 'photo'],
    )
    await callback.answer()
