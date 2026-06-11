"""
РЎРµСЂРІРёСЃ Р±РёР»Р»РёРЅРіР° вЂ” РѕР±СЂР°Р±РѕС‚РєР° РїР»Р°С‚РµР¶РµР№.

РџСЂРѕРІРµСЂРєР° РїРѕРґРїРёСЃРµР№, СЃРѕР·РґР°РЅРёРµ/РїСЂРѕРґР»РµРЅРёРµ РєР»СЋС‡РµР№ РїРѕСЃР»Рµ РѕРїР»Р°С‚С‹.
РЎРѕР·РґР°РЅРёРµ QR-РїР»Р°С‚РµР¶РµР№ С‡РµСЂРµР· Р®РљР°СЃСЃР° REST API.
Р РµС„РµСЂР°Р»СЊРЅС‹Рµ РЅР°С‡РёСЃР»РµРЅРёСЏ.
"""
import hmac
import hashlib
import logging
import uuid
import base64
import aiohttp
import qrcode
import io
import math
from typing import Optional, Dict, Any, Tuple

from database.requests import (
    find_order_by_order_id, complete_order, is_order_already_paid,
    get_setting,
    get_yookassa_credentials, get_wata_token, get_platega_credentials,
    get_cardlink_credentials,
    is_referral_enabled, get_referral_reward_type, get_active_referral_levels,
    get_user_referrer, get_user_referral_coefficient, get_user_balance,
    add_to_balance, deduct_from_balance, add_days_to_first_active_key,
    update_referral_stat
)
from bot.services.exchange_rate import get_usd_rub_rate

logger = logging.getLogger(__name__)

STAR_TO_USD = 0.013
USDT_TO_USD = 1.0

YOOKASSA_API_URL = "https://api.yookassa.ru/v3/payments"
WATA_API_URL = "https://api.wata.pro/api/h2h"
PLATEGA_API_URL = "https://app.platega.io"
PLATEGA_PAYMENT_METHOD_SBP = 2
CARDLINK_API_URL = "https://cardlink.link"

# РђР»С„Р°РІРёС‚ РґР»СЏ Base62 РєРѕРґРёСЂРѕРІР°РЅРёСЏ
ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"




def encode_base62(data: bytes) -> str:
    """
    РљРѕРґРёСЂСѓРµС‚ Р±РёРЅР°СЂРЅС‹Рµ РґР°РЅРЅС‹Рµ РІ Base62.
    
    РСЃРїРѕР»СЊР·СѓРµС‚СЃСЏ РґР»СЏ С„РѕСЂРјРёСЂРѕРІР°РЅРёСЏ РїРѕРґРїРёСЃРё callback РѕС‚ Ya.Seller.
    
    Args:
        data: Р‘РёРЅР°СЂРЅС‹Рµ РґР°РЅРЅС‹Рµ
        
    Returns:
        РЎС‚СЂРѕРєР° РІ С„РѕСЂРјР°С‚Рµ Base62
    """
    if not data:
        return ""
    
    num = int.from_bytes(data, 'big')
    if num == 0:
        return "0"
    
    res = []
    while num > 0:
        num, rem = divmod(num, 62)
        res.append(ALPHABET[rem])
    
    return "".join(reversed(res))


def verify_crypto_signature(data_part: str, received_signature: str, secret_key: str) -> bool:
    """
    РџСЂРѕРІРµСЂСЏРµС‚ РїРѕРґРїРёСЃСЊ callback РѕС‚ РєСЂРёРїС‚РѕРїСЂРѕС†РµСЃСЃРёРЅРіР° Ya.Seller.
    
    РџРѕРґРїРёСЃСЊ = Base62(HMAC-SHA256(data_part, secret_key)[:11]).
    
    РђР»РіРѕСЂРёС‚Рј СЃРѕРіР»Р°СЃРЅРѕ РґРѕРєСѓРјРµРЅС‚Р°С†РёРё https://yadreno.ru/seller/integration.php:
    1. Р’С‹С‡РёСЃР»СЏРµРј HMAC-SHA256 РѕС‚ data_part СЃ СЃРµРєСЂРµС‚РЅС‹Рј РєР»СЋС‡РѕРј
    2. Р‘РµСЂРµРј РїРµСЂРІС‹Рµ 11 Р±Р°Р№С‚ Р±РёРЅР°СЂРЅРѕРіРѕ СЂРµР·СѓР»СЊС‚Р°С‚Р°
    3. РљРѕРґРёСЂСѓРµРј РІ Base62
    
    Args:
        data_part: Р’СЃРµ СЃРµРіРјРµРЅС‚С‹ РєСЂРѕРјРµ РїРѕСЃР»РµРґРЅРµРіРѕ (РЅР°РїСЂРёРјРµСЂ bill1-aZ1-bY-1-_-1000)
        received_signature: РџРѕР»СѓС‡РµРЅРЅР°СЏ РїРѕРґРїРёСЃСЊ (РїРѕСЃР»РµРґРЅРёР№ СЃРµРіРјРµРЅС‚)
        secret_key: РЎРµРєСЂРµС‚РЅС‹Р№ РєР»СЋС‡ РїСЂРѕРґР°РІС†Р°
        
    Returns:
        True РµСЃР»Рё РїРѕРґРїРёСЃСЊ РІР°Р»РёРґРЅР°
    """
    # Р’С‹С‡РёСЃР»СЏРµРј HMAC-SHA256
    h = hmac.new(
        secret_key.encode('utf-8'),
        data_part.encode('utf-8'),
        hashlib.sha256
    ).digest()
    
    # Р‘РµСЂРµРј РїРµСЂРІС‹Рµ 11 Р±Р°Р№С‚ Рё РєРѕРґРёСЂСѓРµРј РІ Base62
    truncated = h[:11]
    expected = encode_base62(truncated)
    
    # РЎСЂР°РІРЅРёРІР°РµРј РїРѕРґРїРёСЃРё
    is_valid = hmac.compare_digest(expected, received_signature)
    
    if not is_valid:
        logger.warning(f"РќРµРІРµСЂРЅР°СЏ РїРѕРґРїРёСЃСЊ! expected={expected}, received={received_signature}")
    
    return is_valid


def parse_crypto_callback(start_param: str) -> Optional[Dict[str, Any]]:
    """
    РџР°СЂСЃРёС‚ РїР°СЂР°РјРµС‚СЂ start РёР· callback РєСЂРёРїС‚РѕРїСЂРѕС†РµСЃСЃРёРЅРіР°.
    
    Р¤РѕСЂРјР°С‚: bill1-ORDER_ID-ITEM_ID-TARIFF-PROMO-PRICE-SIGNATURE
    
    Args:
        start_param: Р—РЅР°С‡РµРЅРёРµ РїР°СЂР°РјРµС‚СЂР° start РёР· deep link
        
    Returns:
        РЎР»РѕРІР°СЂСЊ СЃ РїРѕР»СЏРјРё: order_id, item_id, tariff, promo, price, signature, data_part
        РёР»Рё None РµСЃР»Рё С„РѕСЂРјР°С‚ РЅРµРІРµСЂРЅС‹Р№
    """
    if not start_param or not start_param.startswith('bill'):
        return None
    
    parts = start_param.split('-')
    
    # РњРёРЅРёРјСѓРј: bill1-ORDER_ID-ITEM_ID-TARIFF-PROMO-PRICE-SIGNATURE (7 С‡Р°СЃС‚РµР№)
    if len(parts) < 7:
        logger.warning(f"РќРµРІРµСЂРЅС‹Р№ С„РѕСЂРјР°С‚ callback: {start_param} (С‡Р°СЃС‚РµР№: {len(parts)})")
        return None
    
    try:
        # РџРѕСЃР»РµРґРЅСЏСЏ С‡Р°СЃС‚СЊ вЂ” РїРѕРґРїРёСЃСЊ
        signature = parts[-1]
        # РћСЃС‚Р°Р»СЊРЅРѕРµ вЂ” РґР°РЅРЅС‹Рµ РґР»СЏ РїСЂРѕРІРµСЂРєРё РїРѕРґРїРёСЃРё
        data_part = start_param.rsplit('-', 1)[0]
        
        return {
            'prefix': parts[0],        # bill1 РёР»Рё bill0
            'order_id': parts[1],      # РЅР°С€ invoice_id
            'item_id': parts[2],       # ID С‚РѕРІР°СЂР° РІ Ya.Seller
            'tariff': parts[3],        # РЅРѕРјРµСЂ С‚Р°СЂРёС„Р° (1-9) РёР»Рё '_'
            'promo': parts[4],         # РїСЂРѕРјРѕРєРѕРґ РёР»Рё '_'
            'price': int(parts[5]) if parts[5] != '_' else 0,  # С†РµРЅР° РІ С†РµРЅС‚Р°С…
            'signature': signature,
            'data_part': data_part
        }
    except (ValueError, IndexError) as e:
        logger.error(f"РћС€РёР±РєР° РїР°СЂСЃРёРЅРіР° callback: {e}")
        return None


async def process_payment_order(order_id: str) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    РЈРЅРёРІРµСЂСЃР°Р»СЊРЅР°СЏ РѕР±СЂР°Р±РѕС‚РєР° СѓСЃРїРµС€РЅРѕРіРѕ РѕСЂРґРµСЂР° (Crypto РёР»Рё Stars).
    Р—Р°РєСЂС‹РІР°РµС‚ РѕСЂРґРµСЂ, РїСЂРѕРґР»РµРІР°РµС‚ РєР»СЋС‡ РёР»Рё СЃРѕР·РґР°С‘С‚ С‡РµСЂРЅРѕРІРёРє.
    
    Returns:
        (success, message_text, order_data)
    """
    from database.requests import (
        is_order_already_paid, find_order_by_order_id, complete_order, 
        create_initial_vpn_key, update_payment_key_id
    )
    
    # 1. РџСЂРѕРІРµСЂРєР° РЅР° РґСѓР±Р»РёРєР°С‚ (РЅР° РІСЃСЏРєРёР№ СЃР»СѓС‡Р°Р№, РµСЃР»Рё РІС‹Р·С‹РІР°СЋС‰РёР№ РЅРµ РїСЂРѕРІРµСЂРёР»)
    if is_order_already_paid(order_id):
        # РџРѕР»СѓС‡Р°РµРј РѕСЂРґРµСЂ С‡С‚РѕР±С‹ РІРµСЂРЅСѓС‚СЊ РєРѕРЅС‚РµРєСЃС‚
        order = find_order_by_order_id(order_id)
        return True, "вњ… Р­С‚РѕС‚ РїР»Р°С‚С‘Р¶ СѓР¶Рµ Р±С‹Р» РѕР±СЂР°Р±РѕС‚Р°РЅ СЂР°РЅРµРµ.", order

    # 2. РџРѕРёСЃРє РѕСЂРґРµСЂР°
    order = find_order_by_order_id(order_id)
    if not order:
        logger.warning(f"РћСЂРґРµСЂ РЅРµ РЅР°Р№РґРµРЅ: {order_id}")
        return False, "вљ пёЏ РћСЂРґРµСЂ РЅРµ РЅР°Р№РґРµРЅ. РћР±СЂР°С‚РёС‚РµСЃСЊ РІ РїРѕРґРґРµСЂР¶РєСѓ.", None
    
    # 3. Р—Р°РєСЂС‹РІР°РµРј РѕСЂРґРµСЂ
    if not complete_order(order_id):
        # Р•СЃР»Рё СЃС‚Р°С‚СѓСЃ СѓР¶Рµ paid, process_payment_order РІС‹Р·РІР°РЅ РїРѕРІС‚РѕСЂРЅРѕ - РѕР±СЂР°Р±Р°С‚С‹РІР°РµРј РєР°Рє СѓСЃРїРµС…
        if order['status'] == 'paid':
             pass
        else:
             return False, "вќЊ РћС€РёР±РєР° РѕР±РЅРѕРІР»РµРЅРёСЏ СЃС‚Р°С‚СѓСЃР° РїР»Р°С‚РµР¶Р°.", order
    
    logger.info(f"Order {order_id} processed (paid)")

    user_internal_id = order['user_id']
    days = order.get('period_days') or order.get('duration_days') or 30

    if order['vpn_key_id']:
        from bot.services.key_lifecycle import renew_key_access
        renew_result = await renew_key_access(
            order['vpn_key_id'],
            days,
            reset_traffic=True,
            tariff_id=order.get('tariff_id'),
        )
        if days and renew_result['db_updated']:
            logger.info(f"РљР»СЋС‡ {order['vpn_key_id']} РїСЂРѕРґР»С‘РЅ РЅР° {days} РґРЅРµР№ (order={order_id})")
            if not renew_result['panel_synced']:
                logger.warning(
                    f"РљР»СЋС‡ {order['vpn_key_id']} РїСЂРѕРґР»С‘РЅ РІ Р‘Р”, РЅРѕ РїР°РЅРµР»СЊ СЃРёРЅС…СЂРѕРЅРёР·РёСЂРѕРІР°РЅР° "
                    f"РЅРµ РїРѕР»РЅРѕСЃС‚СЊСЋ: {renew_result.get('sync_stats')}"
                )

            if order.get('payment_type') == 'crypto':
                await process_referral_reward(user_internal_id, days, order.get('amount_cents', 0), 'crypto')
            
            return True, f"вњ… РћРїР»Р°С‚Р° РїСЂРѕС€Р»Р° СѓСЃРїРµС€РЅРѕ!\n\nР’Р°С€ РєР»СЋС‡ РїСЂРѕРґР»С‘РЅ РЅР° {days} РґРЅРµР№.", order
        else:
            logger.error(f"РќРµ СѓРґР°Р»РѕСЃСЊ РїСЂРѕРґР»РёС‚СЊ РєР»СЋС‡ {order['vpn_key_id']} РїРѕСЃР»Рµ РѕРїР»Р°С‚С‹!")
            return True, "вњ… РћРїР»Р°С‚Р° РїСЂРёРЅСЏС‚Р°!\n\nвљ пёЏ Р’РѕР·РЅРёРєР»Р° РїСЂРѕР±Р»РµРјР° СЃ РїСЂРѕРґР»РµРЅРёРµРј. РњС‹ СЂР°Р·Р±РµСЂС‘РјСЃСЏ.", order
    else:
        if not order.get('tariff_id'):
            logger.error(f"РћСЂРґРµСЂ {order_id}: С‚Р°СЂРёС„ РЅРµ РЅР°Р№РґРµРЅ РёР»Рё РЅРµР°РєС‚РёРІРµРЅ РІ Р‘Р” (received tariff_id could not be resolved).")
            from bot.errors import TariffNotFoundError
            raise TariffNotFoundError()
        
        try:
            days = order.get('period_days') or order.get('duration_days') or 30
            # РџРѕР»СѓС‡Р°РµРј Р»РёРјРёС‚ С‚СЂР°С„РёРєР° РёР· С‚Р°СЂРёС„Р°
            from database.requests import get_tariff_by_id as _get_tariff
            _tariff = _get_tariff(order['tariff_id'])
            traffic_limit_bytes = (_tariff.get('traffic_limit_gb', 0) or 0) * (1024**3) if _tariff else 0
            key_id = create_initial_vpn_key(order['user_id'], order['tariff_id'], days, traffic_limit=traffic_limit_bytes)
            
            update_payment_key_id(order_id, key_id)
            order['vpn_key_id'] = key_id
            
            logger.info(f"РЎРѕР·РґР°РЅ С‡РµСЂРЅРѕРІРёРє РєР»СЋС‡Р° {key_id} РґР»СЏ Р·Р°РєР°Р·Р° {order_id}")
            
            if order.get('payment_type') == 'crypto':
                await process_referral_reward(user_internal_id, days, order.get('amount_cents', 0), 'crypto')
            
            return True, "вњ… РћРїР»Р°С‚Р° РїСЂРѕС€Р»Р° СѓСЃРїРµС€РЅРѕ!", order
            
        except Exception as e:
            logger.error(f"РћС€РёР±РєР° СЃРѕР·РґР°РЅРёСЏ С‡РµСЂРЅРѕРІРёРєР° РєР»СЋС‡Р°: {e}")
            return True, "вњ… РћРїР»Р°С‚Р° РїСЂРёРЅСЏС‚Р°, РЅРѕ РїСЂРѕРёР·РѕС€Р»Р° РѕС€РёР±РєР° РїСЂРё СЃРѕР·РґР°РЅРёРё РєР»СЋС‡Р°. РћР±СЂР°С‚РёС‚РµСЃСЊ РІ РїРѕРґРґРµСЂР¶РєСѓ.", order


async def process_crypto_payment(start_param: str, user_id: Optional[int] = None) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    РћР±СЂР°Р±Р°С‚С‹РІР°РµС‚ РїР»Р°С‚С‘Р¶ РѕС‚ РєСЂРёРїС‚РѕРїСЂРѕС†РµСЃСЃРёРЅРіР° (parse + verify + confirm).
    """
    # РџР°СЂСЃРёРј callback
    parsed = parse_crypto_callback(start_param)
    if not parsed:
        return False, "вќЊ РќРµРІРµСЂРЅС‹Р№ С„РѕСЂРјР°С‚ РїР»Р°С‚С‘Р¶РЅС‹С… РґР°РЅРЅС‹С…", None
    
    # РџРѕР»СѓС‡Р°РµРј СЃРµРєСЂРµС‚РЅС‹Р№ РєР»СЋС‡
    secret_key = get_setting('crypto_secret_key')
    if not secret_key:
        logger.error("РЎРµРєСЂРµС‚РЅС‹Р№ РєР»СЋС‡ РєСЂРёРїС‚РѕРїСЂРѕС†РµСЃСЃРёРЅРіР° РЅРµ РЅР°СЃС‚СЂРѕРµРЅ!")
        return False, "вќЊ РћС€РёР±РєР° РєРѕРЅС„РёРіСѓСЂР°С†РёРё. РћР±СЂР°С‚РёС‚РµСЃСЊ РІ РїРѕРґРґРµСЂР¶РєСѓ.", None
    
    # РџСЂРѕРІРµСЂСЏРµРј РїРѕРґРїРёСЃСЊ
    if not verify_crypto_signature(parsed['data_part'], parsed['signature'], secret_key):
        return False, "вќЊ РќРµРІРµСЂРЅР°СЏ РїРѕРґРїРёСЃСЊ РїР»Р°С‚РµР¶Р°. РџРѕРїСЂРѕР±СѓР№С‚Рµ СЃРЅРѕРІР°.", None
    
    order_id = parsed['order_id']
    
    # --- Р›РћР“РРљРђ РћР‘Р РђР‘РћРўРљР РћР Р”Р•Р РћР’ (Р’РЅРµС€РЅРёРµ/Р’РЅСѓС‚СЂРµРЅРЅРёРµ) ---
    is_internal_order = order_id.startswith("00")
    order = find_order_by_order_id(order_id)
    
    if order:
        # РЎРІРµСЂСЏРµРј СЃСѓРјРјСѓ РїР»Р°С‚РµР¶Р° СЃ С‚Р°СЂРёС„РѕРј
        from database.requests import get_tariff_by_id
        order_tariff = get_tariff_by_id(order['tariff_id'])
        if order_tariff:
            expected_cents = order_tariff['price_cents']
            received_cents = parsed.get('price', 0)
            if received_cents < expected_cents:
                logger.error(f"РћСЂРґРµСЂ {order_id}: РЎСѓРјРјР° РїР»Р°С‚РµР¶Р° РЅРµРґРѕСЃС‚Р°С‚РѕС‡РЅР°. РћР¶РёРґР°Р»РѕСЃСЊ {expected_cents}, РїРѕР»СѓС‡РµРЅРѕ {received_cents}")
                return False, "вќЊ РЎСѓРјРјР° РїР»Р°С‚РµР¶Р° РЅРµ СЃРѕРІРїР°РґР°РµС‚ СЃ С‚Р°СЂРёС„РѕРј.", None
    
    if not order:
        if is_internal_order:
             return False, "вќЊ РћСЂРґРµСЂ РЅРµ РЅР°Р№РґРµРЅ РІ СЃРёСЃС‚РµРјРµ.", None
        
        # Р’РЅРµС€РЅРёР№ РѕСЂРґРµСЂ -> РЎРѕР·РґР°РµРј PAID order РІ Р±Р°Р·Рµ РџР•Р Р•Р” РѕР±СЂР°Р±РѕС‚РєРѕР№
        if not user_id:
             return False, "вљ пёЏ РћС€РёР±РєР° РѕР±СЂР°Р±РѕС‚РєРё РІРЅРµС€РЅРµРіРѕ Р·Р°РєР°Р·Р° (РЅРµС‚ user_id).", None
        
        logger.info(f"РќРѕРІС‹Р№ РІРЅРµС€РЅРёР№ РѕСЂРґРµСЂ: {order_id}")
        
        # Р’РЅРµС€РЅРёР№ РѕСЂРґРµСЂ Р±РµР· С‚Р°СЂРёС„Р° вЂ” РѕС€РёР±РєР°
        logger.error(f"Р’РЅРµС€РЅРёР№ РѕСЂРґРµСЂ {order_id} Р±РµР· РїСЂРёРІСЏР·РєРё Рє С‚Р°СЂРёС„Сѓ!")
        from bot.errors import TariffNotFoundError
        raise TariffNotFoundError()
    
    # Delegate to unified logic
    return await process_payment_order(order_id)


def build_crypto_payment_url(
    item_id: str,
    invoice_id: str,
    price_cents: Optional[int] = None
) -> str:
    """
    Р¤РѕСЂРјРёСЂСѓРµС‚ СЃСЃС‹Р»РєСѓ РЅР° РєСЂРёРїС‚РѕРїСЂРѕС†РµСЃСЃРёРЅРі СЃ РЅР°С€РёРј invoice.
    
    Р¤РѕСЂРјР°С‚: https://t.me/Ya_SellerBot?start=item-{item_id}-{ref}-{promo}-{invoice}-{price}
    
    Args:
        item_id: ID С‚РѕРІР°СЂР° РІ Ya.Seller (РёР· РЅР°СЃС‚СЂРѕРµРє)
        invoice_id: РќР°С€ СѓРЅРёРєР°Р»СЊРЅС‹Р№ invoice (РјР°РєСЃ 8 СЃРёРјРІРѕР»РѕРІ)
        price_cents: Р¦РµРЅР° РІ С†РµРЅС‚Р°С… (РµСЃР»Рё РЅСѓР¶РЅРѕ РїРµСЂРµРѕРїСЂРµРґРµР»РёС‚СЊ)
        
    Returns:
        URL РґР»СЏ РїРµСЂРµС…РѕРґР° РІ РєСЂРёРїС‚РѕРїСЂРѕС†РµСЃСЃРёРЅРі
    """
    # Р¤РѕСЂРјР°С‚: item-{item_id}-{ref_code}-{promo}-{invoice}-{price}
    # РџСѓСЃС‚С‹Рµ РїР°СЂР°РјРµС‚СЂС‹ Р·Р°РјРµРЅСЏРµРј РїСЂРѕС‡РµСЂРєР°РјРё
    
    ref_code = ""  # Р РµС„С„РµСЂР°Р»РєСѓ РЅРµ РёСЃРїРѕР»СЊР·СѓРµРј
    promo = ""     # РџСЂРѕРјРѕРєРѕРґ РЅРµ РёСЃРїРѕР»СЊР·СѓРµРј
    
    parts = [
        "item",
        item_id,
        ref_code,
        promo,
        invoice_id
    ]
    
    # Р”РѕР±Р°РІР»СЏРµРј С†РµРЅСѓ РµСЃР»Рё РЅСѓР¶РЅРѕ Р·Р°С„РёРєСЃРёСЂРѕРІР°С‚СЊ
    if price_cents:
        parts.append(str(price_cents))
    
    start_param = "-".join(parts)
    
    return f"https://t.me/Ya_SellerBot?start={start_param}"


def extract_item_id_from_url(crypto_item_url: str) -> Optional[str]:
    """
    РР·РІР»РµРєР°РµС‚ item_id РёР· СЃСЃС‹Р»РєРё РЅР° С‚РѕРІР°СЂ РІ Ya.Seller.
    
    Р¤РѕСЂРјР°С‚ СЃСЃС‹Р»РєРё: https://t.me/Ya_SellerBot?start=item-{item_id}...
    
    Args:
        crypto_item_url: РџРѕР»РЅР°СЏ СЃСЃС‹Р»РєР° РЅР° С‚РѕРІР°СЂ
        
    Returns:
        item_id РёР»Рё None
    """
    if not crypto_item_url:
        return None
    
    # РС‰РµРј start= РїР°СЂР°РјРµС‚СЂ
    if '?start=' in crypto_item_url:
        start_param = crypto_item_url.split('?start=')[1]
        parts = start_param.split('-')
        if len(parts) >= 2 and parts[0] == 'item':
            return parts[1]
    
    return None


# ============================================================================
# Р®РљРђРЎРЎРђ QR-РћРџР›РђРўРђ (РїСЂСЏРјРѕР№ REST API Р±РµР· Telegram Payments)
# ============================================================================

async def create_yookassa_qr_payment(
    amount_rub: float,
    order_id: str,
    description: str,
    bot_name: str,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    РЎРѕР·РґР°С‘С‚ РїР»Р°С‚С‘Р¶ РІ Р®РљР°СЃСЃР° REST API СЃ РїРѕРґС‚РІРµСЂР¶РґРµРЅРёРµРј С‡РµСЂРµР· QR-РєРѕРґ.

    Р’РѕР·РІСЂР°С‰Р°РµС‚ РёР·РѕР±СЂР°Р¶РµРЅРёРµ QR-РєРѕРґР° (PNG) РїРѕ СЃСЃС‹Р»РєРµ, РєРѕС‚РѕСЂСѓСЋ РјРѕР¶РЅРѕ
    РѕС‚РїСЂР°РІРёС‚СЊ РїРѕР»СЊР·РѕРІР°С‚РµР»СЋ РїСЂСЏРјРѕ РІ Telegram РєР°Рє С„РѕС‚Рѕ.

    Args:
        amount_rub: РЎСѓРјРјР° РІ СЂСѓР±Р»СЏС… (РЅР°РїСЂРёРјРµСЂ, 299.00)
        order_id: РќР°С€ РІРЅСѓС‚СЂРµРЅРЅРёР№ РѕСЂРґРµСЂ (РґР»СЏ metadata)
        description: РћРїРёСЃР°РЅРёРµ РїР»Р°С‚РµР¶Р° (РїРѕРєР°Р·С‹РІР°РµС‚СЃСЏ РІ С„РѕСЂРјРµ РѕРїР»Р°С‚С‹)
        metadata: Р”РѕРїРѕР»РЅРёС‚РµР»СЊРЅС‹Рµ РјРµС‚Р°РґР°РЅРЅС‹Рµ (РЅРµРѕР±СЏР·Р°С‚РµР»СЊРЅРѕ)

    Returns:
        РЎР»РѕРІР°СЂСЊ СЃ РєР»СЋС‡Р°РјРё:
            - yookassa_payment_id: ID РїР»Р°С‚РµР¶Р° РІ СЃРёСЃС‚РµРјРµ Р®РљР°СЃСЃР°
            - qr_image_url: URL РёР·РѕР±СЂР°Р¶РµРЅРёСЏ QR-РєРѕРґР° (PNG)
            - qr_url: РЎСЃС‹Р»РєР°, Р·Р°С€РёС‚Р°СЏ РІ QR (РґР»СЏ РѕС‚РєСЂС‹С‚РёСЏ РІ Р±СЂР°СѓР·РµСЂРµ)

    Raises:
        ValueError: Р•СЃР»Рё СѓС‡С‘С‚РЅС‹Рµ РґР°РЅРЅС‹Рµ РЅРµ РЅР°СЃС‚СЂРѕРµРЅС‹
        aiohttp.ClientError: Р•СЃР»Рё API РЅРµРґРѕСЃС‚СѓРїРµРЅ
        RuntimeError: Р•СЃР»Рё API РІРµСЂРЅСѓР» РѕС€РёР±РєСѓ
    """
    shop_id, secret_key = get_yookassa_credentials()
    if not shop_id or not secret_key:
        raise ValueError("Р®РљР°СЃСЃР°: РЅРµ РЅР°СЃС‚СЂРѕРµРЅС‹ shop_id РёР»Рё secret_key")

    # Р—Р°РіРѕР»РѕРІРѕРє Basic Auth: base64(shop_id:secret_key)
    credentials = base64.b64encode(f"{shop_id}:{secret_key}".encode()).decode()

    # РљР»СЋС‡ РёРґРµРјРїРѕС‚РµРЅС‚РЅРѕСЃС‚Рё вЂ” СѓРЅРёРєР°Р»СЊРЅС‹Р№ РґР»СЏ СЌС‚РѕРіРѕ РѕСЂРґРµСЂР°
    idempotence_key = f"qr-{order_id}-{uuid.uuid4().hex[:8]}"

    payload = {
        "amount": {
            "value": f"{amount_rub:.2f}",
            "currency": "RUB"
        },
        "capture": True,
        "confirmation": {
            "type": "redirect",
            "return_url": "https://t.me"
        },
        "description": description,
        "receipt": {
            "customer": {
                "email": f"user_{order_id}@t.me"
            },
            "items": [
                {
                    "description": description[:128],
                    "quantity": "1.00",
                    "amount": {
                        "value": f"{amount_rub:.2f}",
                        "currency": "RUB"
                    },
                    "vat_code": 1,
                    "payment_mode": "full_prepayment",
                    "payment_subject": "service"
                }
            ]
        },
        "metadata": {
            "order_id": order_id,
            **(metadata or {})
        }
    }

    headers = {
        "Authorization": f"Basic {credentials}",
        "Idempotence-Key": idempotence_key,
        "Content-Type": "application/json"
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            YOOKASSA_API_URL,
            json=payload,
            headers=headers
        ) as response:
            data = await response.json()

            if response.status not in (200, 201):
                error_desc = data.get('description', 'РќРµРёР·РІРµСЃС‚РЅР°СЏ РѕС€РёР±РєР°')
                logger.error(f"Р®РљР°СЃСЃР° API РѕС€РёР±РєР° {response.status}: {error_desc} | payload={payload}")
                raise RuntimeError(f"Р®РљР°СЃСЃР° API РѕС€РёР±РєР°: {error_desc}")

            confirmation = data.get('confirmation', {})
            qr_url = confirmation.get('confirmation_url', '')
            
            if not qr_url:
                logger.error(f"Р®РљР°СЃСЃР° API РЅРµ РІРµСЂРЅСѓР» confirmation_url: {data}")
                raise RuntimeError("Р®РљР°СЃСЃР° API РЅРµ РІРµСЂРЅСѓР» РґР°РЅРЅС‹Рµ РґР»СЏ QR-РєРѕРґР°")

            # Р“РµРЅРµСЂРёСЂСѓРµРј QR-РєРѕРґ РёР· СЃС‚СЂРѕРєРё РѕРїР»Р°С‚С‹ С‡РµСЂРµР· Р»РѕРєР°Р»СЊРЅСѓСЋ Р±РёР±Р»РёРѕС‚РµРєСѓ qrcode
            
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(qr_url)
            qr.make(fit=True)
            
            img = qr.make_image(fill_color="black", back_color="white")
            bio = io.BytesIO()
            img.save(bio, format="PNG")
            qr_image_data = bio.getvalue()

            logger.info(
                f"Р®РљР°СЃСЃР° QR СЃРѕР·РґР°РЅ: payment_id={data['id']}, order_id={order_id}, "
                f"amount={amount_rub} RUB"
            )

            return {
                'yookassa_payment_id': data['id'],
                'qr_image_data': qr_image_data,
                'qr_url': qr_url,
                'status': data.get('status', 'pending')
            }


async def check_yookassa_payment_status(yookassa_payment_id: str) -> str:
    """
    РџСЂРѕРІРµСЂСЏРµС‚ СЃС‚Р°С‚СѓСЃ РїР»Р°С‚РµР¶Р° РІ Р®РљР°СЃСЃР° REST API.

    Args:
        yookassa_payment_id: ID РїР»Р°С‚РµР¶Р° РІ СЃРёСЃС‚РµРјРµ Р®РљР°СЃСЃР°

    Returns:
        РЎС‚СЂРѕРєР° СЃС‚Р°С‚СѓСЃР°: 'pending', 'waiting_for_capture', 'succeeded', 'canceled'

    Raises:
        ValueError: Р•СЃР»Рё СѓС‡С‘С‚РЅС‹Рµ РґР°РЅРЅС‹Рµ РЅРµ РЅР°СЃС‚СЂРѕРµРЅС‹
        aiohttp.ClientError: Р•СЃР»Рё API РЅРµРґРѕСЃС‚СѓРїРµРЅ
        RuntimeError: Р•СЃР»Рё API РІРµСЂРЅСѓР» РѕС€РёР±РєСѓ
    """
    shop_id, secret_key = get_yookassa_credentials()
    if not shop_id or not secret_key:
        raise ValueError("Р®РљР°СЃСЃР°: РЅРµ РЅР°СЃС‚СЂРѕРµРЅС‹ shop_id РёР»Рё secret_key")

    credentials = base64.b64encode(f"{shop_id}:{secret_key}".encode()).decode()
    headers = {
        "Authorization": f"Basic {credentials}",
        "Content-Type": "application/json"
    }

    url = f"{YOOKASSA_API_URL}/{yookassa_payment_id}"

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            data = await response.json()

            if response.status != 200:
                error_desc = data.get('description', 'РќРµРёР·РІРµСЃС‚РЅР°СЏ РѕС€РёР±РєР°')
                logger.error(f"Р®РљР°СЃСЃР° СЃС‚Р°С‚СѓСЃ РѕС€РёР±РєР° {response.status}: {error_desc}")
                raise RuntimeError(f"Р®РљР°СЃСЃР° API РѕС€РёР±РєР°: {error_desc}")

            status = data.get('status', 'pending')
            logger.debug(f"Р®РљР°СЃСЃР° payment {yookassa_payment_id}: status={status}")
            return status


# ============================================================================
# WATA вЂ” РѕРїР»Р°С‚Р° РєР°СЂС‚РѕР№/РЎР‘Рџ С‡РµСЂРµР· REST API (https://wata.pro/api)
# ============================================================================

async def create_wata_payment(
    amount_rub: float,
    order_id: str,
    description: str,
    bot_name: str
) -> Dict[str, Any]:
    """
    РЎРѕР·РґР°С‘С‚ РїР»Р°С‚С‘Р¶РЅСѓСЋ СЃСЃС‹Р»РєСѓ РІ WATA С‡РµСЂРµР· H2H API.

    POST https://api.wata.pro/api/h2h/links/

    Args:
        amount_rub: РЎСѓРјРјР° РІ СЂСѓР±Р»СЏС…
        order_id: РќР°С€ РІРЅСѓС‚СЂРµРЅРЅРёР№ order_id
        description: РћРїРёСЃР°РЅРёРµ РїР»Р°С‚РµР¶Р°
        bot_name: Username Р±РѕС‚Р° (РґР»СЏ РїРѕСЃС‚СЂРѕРµРЅРёСЏ successRedirectUrl)

    Returns:
        РЎР»РѕРІР°СЂСЊ СЃ РєР»СЋС‡Р°РјРё:
            - wata_link_id: ID СЃСЃС‹Р»РєРё РІ СЃРёСЃС‚РµРјРµ WATA
            - qr_image_data: PNG-Р±Р°Р№С‚С‹ QR-РєРѕРґР°
            - qr_url: РЎСЃС‹Р»РєР° РґР»СЏ РѕРїР»Р°С‚С‹ (РєР°СЂС‚С‹/РЎР‘Рџ)
            - status: РЎС‚Р°С‚СѓСЃ РїР»Р°С‚РµР¶Р°

    Raises:
        ValueError: Р•СЃР»Рё JWT-С‚РѕРєРµРЅ РЅРµ РЅР°СЃС‚СЂРѕРµРЅ
        RuntimeError: Р•СЃР»Рё API РІРµСЂРЅСѓР» РѕС€РёР±РєСѓ
    """
    token = get_wata_token()
    if not token:
        raise ValueError("WATA: JWT-С‚РѕРєРµРЅ РЅРµ РЅР°СЃС‚СЂРѕРµРЅ")

    return_url = f"https://t.me/{bot_name}" if bot_name else "https://t.me"

    payload = {
        "amount": round(float(amount_rub), 2),
        "currency": "RUB",
        "description": description[:255],
        "orderId": order_id,
        "successRedirectUrl": return_url,
        "failRedirectUrl": return_url,
    }

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    url = f"{WATA_API_URL}/links/"

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=headers) as response:
            try:
                data = await response.json()
            except Exception:
                text = await response.text()
                logger.error(f"WATA API: РЅРµРІРѕР·РјРѕР¶РЅРѕ СЂР°Р·РѕР±СЂР°С‚СЊ РѕС‚РІРµС‚ ({response.status}): {text}")
                raise RuntimeError("WATA API РІРµСЂРЅСѓР» РЅРµРєРѕСЂСЂРµРєС‚РЅС‹Р№ РѕС‚РІРµС‚")

            if response.status not in (200, 201):
                error_desc = data.get('error') or data.get('message') or data.get('description') or 'РќРµРёР·РІРµСЃС‚РЅР°СЏ РѕС€РёР±РєР°'
                logger.error(f"WATA API РѕС€РёР±РєР° {response.status}: {error_desc} | payload={payload}")
                raise RuntimeError(f"WATA API РѕС€РёР±РєР°: {error_desc}")

            wata_link_id = data.get('id') or data.get('linkId') or data.get('uuid')
            qr_url = data.get('url') or data.get('paymentUrl')

            if not wata_link_id or not qr_url:
                logger.error(f"WATA API РЅРµ РІРµСЂРЅСѓР» id/url: {data}")
                raise RuntimeError("WATA API РЅРµ РІРµСЂРЅСѓР» РґР°РЅРЅС‹Рµ РїР»Р°С‚С‘Р¶РЅРѕР№ СЃСЃС‹Р»РєРё")

            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(qr_url)
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")
            bio = io.BytesIO()
            img.save(bio, format="PNG")
            qr_image_data = bio.getvalue()

            logger.info(
                f"WATA СЃСЃС‹Р»РєР° СЃРѕР·РґР°РЅР°: link_id={wata_link_id}, order_id={order_id}, "
                f"amount={amount_rub} RUB"
            )

            return {
                'wata_link_id': str(wata_link_id),
                'qr_image_data': qr_image_data,
                'qr_url': qr_url,
                'status': str(data.get('status', 'Created')).lower(),
            }


async def check_wata_payment_status(wata_link_id: str) -> str:
    """Checks WATA payment link status by link ID."""
    token = get_wata_token()
    if not token:
        raise ValueError("WATA: JWT-token is not configured")

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }

    url = f"{WATA_API_URL}/links/{wata_link_id}"

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            try:
                data = await response.json(content_type=None)
            except Exception:
                text = await response.text()
                logger.error(f"WATA status: cannot parse response ({response.status}): {text}")
                raise RuntimeError("WATA API returned invalid response")

            if response.status == 429:
                logger.warning(f"WATA rate-limit (429) while checking {wata_link_id}")
                return "pending"

            if response.status != 200:
                error_desc = (
                    data.get("error") or data.get("message") or data.get("description") or "Unknown error"
                ) if isinstance(data, dict) else f"HTTP {response.status}"
                logger.error(f"WATA status error {response.status}: {error_desc}")
                raise RuntimeError(f"WATA API error: {error_desc}")

            status = str(data.get("status", "")).lower() if isinstance(data, dict) else ""
            logger.debug(f"WATA link {wata_link_id}: status={status}")
            if status in ("closed", "paid"):
                return "succeeded"
            if status in ("declined", "expired", "canceled", "cancelled"):
                return "canceled"

            return "pending"


# ============================================================================
# PLATEGA вЂ” РѕРїР»Р°С‚Р° РЎР‘Рџ С‡РµСЂРµР· REST API (https://app.platega.io)
# ============================================================================

async def create_platega_payment(
    amount_rub: float,
    order_id: str,
    description: str,
    bot_name: str
) -> Dict[str, Any]:
    """
    РЎРѕР·РґР°С‘С‚ С‚СЂР°РЅР·Р°РєС†РёСЋ РІ Platega API.

    POST https://app.platega.io/transaction/process

    Args:
        amount_rub: РЎСѓРјРјР° РІ СЂСѓР±Р»СЏС…
        order_id: РќР°С€ РІРЅСѓС‚СЂРµРЅРЅРёР№ order_id
        description: РћРїРёСЃР°РЅРёРµ РїР»Р°С‚РµР¶Р°
        bot_name: Username Р±РѕС‚Р° (РґР»СЏ РїРѕСЃС‚СЂРѕРµРЅРёСЏ returnUrl)

    Returns:
        РЎР»РѕРІР°СЂСЊ СЃ РєР»СЋС‡Р°РјРё:
            - platega_transaction_id: ID С‚СЂР°РЅР·Р°РєС†РёРё РІ СЃРёСЃС‚РµРјРµ Platega
            - qr_image_data: PNG-Р±Р°Р№С‚С‹ QR-РєРѕРґР°
            - qr_url: РЎСЃС‹Р»РєР° РґР»СЏ РѕРїР»Р°С‚С‹ (РЎР‘Рџ)
            - status: РЎС‚Р°С‚СѓСЃ РїР»Р°С‚РµР¶Р°

    Raises:
        ValueError: Р•СЃР»Рё СѓС‡С‘С‚РЅС‹Рµ РґР°РЅРЅС‹Рµ РЅРµ РЅР°СЃС‚СЂРѕРµРЅС‹
        RuntimeError: Р•СЃР»Рё API РІРµСЂРЅСѓР» РѕС€РёР±РєСѓ
    """
    merchant_id, secret = get_platega_credentials()
    if not merchant_id or not secret:
        raise ValueError("Platega: РЅРµ РЅР°СЃС‚СЂРѕРµРЅС‹ merchant_id РёР»Рё secret")

    return_url = f"https://t.me/{bot_name}" if bot_name else "https://t.me"
    fail_url = return_url

    # Platega С‚СЂРµР±СѓРµС‚ id РІ С„РѕСЂРјР°С‚Рµ UUID. РќР°С€ РєРѕСЂРѕС‚РєРёР№ order_id СЃРѕС…СЂР°РЅСЏРµРј РІ payload.
    transaction_uuid = str(uuid.uuid4())

    payload = {
        "paymentMethod": PLATEGA_PAYMENT_METHOD_SBP,
        "id": transaction_uuid,
        "paymentDetails": {
            "amount": round(float(amount_rub), 2),
            "currency": "RUB",
        },
        "description": description[:255],
        "returnUrl": return_url,
        "failedUrl": fail_url,
        "payload": order_id,
    }

    headers = {
        "X-MerchantId": merchant_id,
        "X-Secret": secret,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    url = f"{PLATEGA_API_URL}/transaction/process"

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=headers) as response:
            try:
                data = await response.json()
            except Exception:
                text = await response.text()
                logger.error(f"Platega API: РЅРµРІРѕР·РјРѕР¶РЅРѕ СЂР°Р·РѕР±СЂР°С‚СЊ РѕС‚РІРµС‚ ({response.status}): {text}")
                raise RuntimeError("Platega API РІРµСЂРЅСѓР» РЅРµРєРѕСЂСЂРµРєС‚РЅС‹Р№ РѕС‚РІРµС‚")

            if response.status not in (200, 201):
                error_desc = (
                    data.get('error') or data.get('message') or
                    data.get('description') or 'РќРµРёР·РІРµСЃС‚РЅР°СЏ РѕС€РёР±РєР°'
                )
                logger.error(f"Platega API РѕС€РёР±РєР° {response.status}: {error_desc} | payload={payload}")
                raise RuntimeError(f"Platega API РѕС€РёР±РєР°: {error_desc}")

            transaction_id = data.get('id') or data.get('transactionId') or data.get('uuid')
            qr_url = (
                data.get('redirect') or data.get('redirectUrl') or
                data.get('url') or data.get('paymentUrl')
            )

            if not transaction_id or not qr_url:
                logger.error(f"Platega API РЅРµ РІРµСЂРЅСѓР» id/url: {data}")
                raise RuntimeError("Platega API РЅРµ РІРµСЂРЅСѓР» РґР°РЅРЅС‹Рµ РїР»Р°С‚С‘Р¶РЅРѕР№ СЃСЃС‹Р»РєРё")

            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(qr_url)
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")
            bio = io.BytesIO()
            img.save(bio, format="PNG")
            qr_image_data = bio.getvalue()

            logger.info(
                f"Platega С‚СЂР°РЅР·Р°РєС†РёСЏ СЃРѕР·РґР°РЅР°: id={transaction_id}, order_id={order_id}, "
                f"amount={amount_rub} RUB"
            )

            return {
                'platega_transaction_id': str(transaction_id),
                'qr_image_data': qr_image_data,
                'qr_url': qr_url,
                'status': str(data.get('status', 'PENDING')).upper(),
            }


async def check_platega_payment_status(transaction_id: str) -> str:
    """
    РџСЂРѕРІРµСЂСЏРµС‚ СЃС‚Р°С‚СѓСЃ С‚СЂР°РЅР·Р°РєС†РёРё Platega.

    GET https://app.platega.io/transaction/{transaction_id}

    РЎС‚Р°С‚СѓСЃС‹ Platega:
        - PENDING: РІ РїСЂРѕС†РµСЃСЃРµ РѕРїР»Р°С‚С‹
        - CONFIRMED: СѓСЃРїРµС€РЅРѕ РѕРїР»Р°С‡РµРЅР°
        - CANCELED: РѕС‚РјРµРЅРµРЅР°
        - CHARGEBACKED: РІРѕР·РІСЂР°С‚РЅР°СЏ

    Args:
        transaction_id: ID С‚СЂР°РЅР·Р°РєС†РёРё РІ СЃРёСЃС‚РµРјРµ Platega

    Returns:
        РќРѕСЂРјР°Р»РёР·РѕРІР°РЅРЅС‹Р№ СЃС‚Р°С‚СѓСЃ: 'pending' | 'succeeded' | 'canceled'

    Raises:
        ValueError: Р•СЃР»Рё СѓС‡С‘С‚РЅС‹Рµ РґР°РЅРЅС‹Рµ РЅРµ РЅР°СЃС‚СЂРѕРµРЅС‹
        RuntimeError: Р•СЃР»Рё API РІРµСЂРЅСѓР» РѕС€РёР±РєСѓ
    """
    merchant_id, secret = get_platega_credentials()
    if not merchant_id or not secret:
        raise ValueError("Platega: РЅРµ РЅР°СЃС‚СЂРѕРµРЅС‹ merchant_id РёР»Рё secret")

    headers = {
        "X-MerchantId": merchant_id,
        "X-Secret": secret,
        "Accept": "application/json",
    }

    url = f"{PLATEGA_API_URL}/transaction/{transaction_id}"

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers) as response:
            try:
                data = await response.json()
            except Exception:
                text = await response.text()
                logger.error(f"Platega СЃС‚Р°С‚СѓСЃ: РЅРµРІРѕР·РјРѕР¶РЅРѕ СЂР°Р·РѕР±СЂР°С‚СЊ РѕС‚РІРµС‚ ({response.status}): {text}")
                raise RuntimeError("Platega API РІРµСЂРЅСѓР» РЅРµРєРѕСЂСЂРµРєС‚РЅС‹Р№ РѕС‚РІРµС‚")

            if response.status != 200:
                error_desc = (
                    data.get('error') or data.get('message') or
                    data.get('description') or 'РќРµРёР·РІРµСЃС‚РЅР°СЏ РѕС€РёР±РєР°'
                )
                logger.error(f"Platega СЃС‚Р°С‚СѓСЃ РѕС€РёР±РєР° {response.status}: {error_desc}")
                raise RuntimeError(f"Platega API РѕС€РёР±РєР°: {error_desc}")

            status = str(data.get('status', '')).upper()
            logger.debug(f"Platega transaction {transaction_id}: status={status}")

            if status == 'CONFIRMED':
                return 'succeeded'
            if status in ('CANCELED', 'CANCELLED', 'CHARGEBACKED'):
                return 'canceled'
            return 'pending'


# ============================================================================
# CARDLINK вЂ” РѕРїР»Р°С‚Р° РљР°СЂС‚РѕР№/РЎР‘Рџ С‡РµСЂРµР· REST API (https://cardlink.link)
# ============================================================================

async def create_cardlink_payment(
    amount_rub: float,
    order_id: str,
    description: str,
    bot_name: str
) -> Dict[str, Any]:
    """
    РЎРѕР·РґР°С‘С‚ СЃС‡С‘С‚ (bill) РІ Cardlink API.

    POST https://cardlink.link/api/v1/bill/create

    РўРµР»Рѕ РїРµСЂРµРґР°С‘С‚СЃСЏ РєР°Рє application/x-www-form-urlencoded.
    РђРІС‚РѕСЂРёР·Р°С†РёСЏ С‡РµСЂРµР· Bearer token.

    РћС‚Р»РёС‡РёС‚РµР»СЊРЅР°СЏ РѕСЃРѕР±РµРЅРЅРѕСЃС‚СЊ: РІРјРµСЃС‚Рѕ webhook-Р° РїРѕР»СЊР·РѕРІР°С‚РµР»СЊ РїРѕСЃР»Рµ РѕРїР»Р°С‚С‹
    РІРѕР·РІСЂР°С‰Р°РµС‚СЃСЏ РІ Р±РѕС‚Р° РїРѕ deep-link `https://t.me/{bot}?start=cl_Success`
    (РёР»Рё cl_Fail / cl_Result), С‡С‚Рѕ С‚СЂРёРіРіРµСЂРёС‚ С‚Сѓ Р¶Рµ РїСЂРѕРІРµСЂРєСѓ, С‡С‚Рѕ Рё
    РєРЅРѕРїРєР° В«вњ… РЇ РѕРїР»Р°С‚РёР»В».

    Args:
        amount_rub: РЎСѓРјРјР° РІ СЂСѓР±Р»СЏС…
        order_id: РќР°С€ РІРЅСѓС‚СЂРµРЅРЅРёР№ order_id
        description: РћРїРёСЃР°РЅРёРµ РїР»Р°С‚РµР¶Р° (РЅРµ РёСЃРїРѕР»СЊР·СѓРµС‚СЃСЏ API, РЅРѕ Р»РѕРіРёСЂСѓРµС‚СЃСЏ)
        bot_name: Username Р±РѕС‚Р° (РґР»СЏ РїРѕСЃС‚СЂРѕРµРЅРёСЏ success_url/fail_url)

    Returns:
        РЎР»РѕРІР°СЂСЊ СЃ РєР»СЋС‡Р°РјРё:
            - cardlink_bill_id: ID СЃС‡С‘С‚Р° РІ СЃРёСЃС‚РµРјРµ Cardlink
            - qr_image_data: PNG-Р±Р°Р№С‚С‹ QR-РєРѕРґР°
            - qr_url: РЎСЃС‹Р»РєР° РЅР° СЃС‚СЂР°РЅРёС†Сѓ РѕРїР»Р°С‚С‹
            - status: РЎС‚Р°С‚СѓСЃ РїР»Р°С‚РµР¶Р°

    Raises:
        ValueError: Р•СЃР»Рё СѓС‡С‘С‚РЅС‹Рµ РґР°РЅРЅС‹Рµ РЅРµ РЅР°СЃС‚СЂРѕРµРЅС‹
        RuntimeError: Р•СЃР»Рё API РІРµСЂРЅСѓР» РѕС€РёР±РєСѓ
    """
    shop_id, api_token = get_cardlink_credentials()
    if not shop_id or not api_token:
        raise ValueError("Cardlink: РЅРµ РЅР°СЃС‚СЂРѕРµРЅС‹ shop_id РёР»Рё api_token")

    form = aiohttp.FormData()
    form.add_field("shop_id", shop_id)
    form.add_field("amount", f"{float(amount_rub):.2f}")
    form.add_field("order_id", order_id)
    form.add_field("currency_in", "RUB")
    form.add_field("type", "normal")
    form.add_field("description", description[:255])
    form.add_field("name", description[:100])
    form.add_field("partner_uuid", "6e7e8f22-3410-4224-8b9c-e61430705963")

    headers = {
        "Authorization": f"Bearer {api_token}",
        "Accept": "application/json",
    }

    url = f"{CARDLINK_API_URL}/api/v1/bill/create"

    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=form, headers=headers) as response:
            try:
                data = await response.json(content_type=None)
            except Exception:
                text = await response.text()
                logger.error(f"Cardlink API: РЅРµРІРѕР·РјРѕР¶РЅРѕ СЂР°Р·РѕР±СЂР°С‚СЊ РѕС‚РІРµС‚ ({response.status}): {text}")
                raise RuntimeError("Cardlink API РІРµСЂРЅСѓР» РЅРµРєРѕСЂСЂРµРєС‚РЅС‹Р№ РѕС‚РІРµС‚")

            if response.status not in (200, 201):
                error_desc = 'РќРµРёР·РІРµСЃС‚РЅР°СЏ РѕС€РёР±РєР°'
                validation_details = ''
                if isinstance(data, dict):
                    err = data.get('error')
                    if isinstance(err, dict):
                        error_desc = err.get('description') or err.get('code') or error_desc
                    elif isinstance(err, str):
                        error_desc = err
                    error_desc = (
                        data.get('message')
                        or data.get('description')
                        or error_desc
                    )
                    validation = data.get('validation') or data.get('errors')
                    if validation:
                        validation_details = f" | validation={validation}"
                logger.error(
                    f"Cardlink API РѕС€РёР±РєР° {response.status}: {error_desc} "
                    f"| order_id={order_id} | full_response={data}{validation_details}"
                )
                raise RuntimeError(f"Cardlink API РѕС€РёР±РєР°: {error_desc}")

            # РћС‚РІРµС‚ РјРѕР¶РµС‚ Р±С‹С‚СЊ РІР»РѕР¶РµРЅ РІ РїРѕР»Рµ 'success' (dict) РёР»Рё Р»РµР¶Р°С‚СЊ РІ РєРѕСЂРЅРµ.
            # Р•СЃР»Рё 'success' вЂ” СЌС‚Рѕ С„Р»Р°Рі (СЃС‚СЂРѕРєР°/bool), РёСЃРїРѕР»СЊР·СѓРµРј СЃР°Рј data.
            nested = data.get('success') if isinstance(data, dict) else None
            payload = nested if isinstance(nested, dict) else data

            bill_id = (
                payload.get('bill_id') or payload.get('id') or payload.get('uuid')
                if isinstance(payload, dict) else None
            )
            qr_url = (
                payload.get('link_page_url') or payload.get('url') or payload.get('payment_url')
                if isinstance(payload, dict) else None
            )

            if not bill_id or not qr_url:
                logger.error(f"Cardlink API РЅРµ РІРµСЂРЅСѓР» bill_id/url: {data}")
                raise RuntimeError("Cardlink API РЅРµ РІРµСЂРЅСѓР» РґР°РЅРЅС‹Рµ РїР»Р°С‚С‘Р¶РЅРѕР№ СЃСЃС‹Р»РєРё")

            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(qr_url)
            qr.make(fit=True)

            img = qr.make_image(fill_color="black", back_color="white")
            bio = io.BytesIO()
            img.save(bio, format="PNG")
            qr_image_data = bio.getvalue()

            logger.info(
                f"Cardlink СЃС‡С‘С‚ СЃРѕР·РґР°РЅ: bill_id={bill_id}, order_id={order_id}, "
                f"amount={amount_rub} RUB"
            )

            return {
                'cardlink_bill_id': str(bill_id),
                'qr_image_data': qr_image_data,
                'qr_url': qr_url,
                'status': str(payload.get('status', 'NEW')).upper() if isinstance(payload, dict) else 'NEW',
            }


async def check_cardlink_payment_status(bill_id: str) -> str:
    """
    РџСЂРѕРІРµСЂСЏРµС‚ СЃС‚Р°С‚СѓСЃ СЃС‡С‘С‚Р° Cardlink.

    GET https://cardlink.link/api/v1/bill/status?id={bill_id}

    РЎС‚Р°С‚СѓСЃС‹ Cardlink:
        - NEW / PROCESS / UNDERPAID: РІ РїСЂРѕС†РµСЃСЃРµ
        - SUCCESS / OVERPAID: СѓСЃРїРµС€РЅРѕ РѕРїР»Р°С‡РµРЅРѕ
        - FAIL: РѕС‚РјРµРЅС‘РЅ / РЅРµСѓСЃРїРµС€РЅС‹Р№

    Args:
        bill_id: ID СЃС‡С‘С‚Р° РІ СЃРёСЃС‚РµРјРµ Cardlink

    Returns:
        РќРѕСЂРјР°Р»РёР·РѕРІР°РЅРЅС‹Р№ СЃС‚Р°С‚СѓСЃ: 'pending' | 'succeeded' | 'canceled'

    Raises:
        ValueError: Р•СЃР»Рё СѓС‡С‘С‚РЅС‹Рµ РґР°РЅРЅС‹Рµ РЅРµ РЅР°СЃС‚СЂРѕРµРЅС‹
        RuntimeError: Р•СЃР»Рё API РІРµСЂРЅСѓР» РѕС€РёР±РєСѓ
    """
    shop_id, api_token = get_cardlink_credentials()
    if not shop_id or not api_token:
        raise ValueError("Cardlink: РЅРµ РЅР°СЃС‚СЂРѕРµРЅС‹ shop_id РёР»Рё api_token")

    headers = {
        "Authorization": f"Bearer {api_token}",
        "Accept": "application/json",
    }

    url = f"{CARDLINK_API_URL}/api/v1/bill/status"
    params = {"id": bill_id}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, params=params, headers=headers) as response:
            try:
                data = await response.json(content_type=None)
            except Exception:
                text = await response.text()
                logger.error(f"Cardlink СЃС‚Р°С‚СѓСЃ: РЅРµРІРѕР·РјРѕР¶РЅРѕ СЂР°Р·РѕР±СЂР°С‚СЊ РѕС‚РІРµС‚ ({response.status}): {text}")
                raise RuntimeError("Cardlink API РІРµСЂРЅСѓР» РЅРµРєРѕСЂСЂРµРєС‚РЅС‹Р№ РѕС‚РІРµС‚")

            if response.status != 200:
                error_desc = (
                    (data.get('message') if isinstance(data, dict) else None) or
                    (data.get('error') if isinstance(data, dict) else None) or
                    'РќРµРёР·РІРµСЃС‚РЅР°СЏ РѕС€РёР±РєР°'
                )
                logger.error(f"Cardlink СЃС‚Р°С‚СѓСЃ РѕС€РёР±РєР° {response.status}: {error_desc}")
                raise RuntimeError(f"Cardlink API РѕС€РёР±РєР°: {error_desc}")

            # РћС‚РІРµС‚ РјРѕР¶РµС‚ Р±С‹С‚СЊ РІР»РѕР¶РµРЅ РІ РїРѕР»Рµ 'success' (dict) РёР»Рё Р»РµР¶Р°С‚СЊ РІ РєРѕСЂРЅРµ.
            # Р•СЃР»Рё 'success' вЂ” СЌС‚Рѕ С„Р»Р°Рі (СЃС‚СЂРѕРєР°/bool), РёСЃРїРѕР»СЊР·СѓРµРј СЃР°Рј data.
            nested = data.get('success') if isinstance(data, dict) else None
            payload = nested if isinstance(nested, dict) else data
            status = ''
            if isinstance(payload, dict):
                status = str(payload.get('status', '')).upper()

            logger.debug(f"Cardlink bill {bill_id}: status={status}")

            if status in ('SUCCESS', 'OVERPAID'):
                return 'succeeded'
            if status == 'FAIL':
                return 'canceled'
            return 'pending'


def convert_to_rub_cents(amount_raw: int, payment_type: str, usd_rub_rate: int) -> int:
    """
    РљРѕРЅРІРµСЂС‚РёСЂРѕРІР°С‚СЊ СЃС‹СЂСѓСЋ СЃСѓРјРјСѓ РІ РєРѕРїРµР№РєРё СЂСѓР±Р»РµР№.

    Args:
        amount_raw: СЃС‹СЂР°СЏ СЃСѓРјРјР° (Р·РІС‘Р·РґС‹/С†РµРЅС‚С‹ USDT/РєРѕРїРµР№РєРё СЂСѓР±Р»РµР№)
        payment_type: С‚РёРї РїР»Р°С‚РµР¶Р° ('stars', 'crypto', 'cards', 'yookassa_qr', 'wata', 'platega')
        usd_rub_rate: РєСѓСЂСЃ USD/RUB РІ РєРѕРїРµР№РєР°С…

    Returns:
        РЎСѓРјРјР° РІ РєРѕРїРµР№РєР°С… СЂСѓР±Р»РµР№
    """
    if payment_type == 'stars':
        usd_cents = int(amount_raw * STAR_TO_USD * 100)
        return usd_cents * usd_rub_rate // 100
    elif payment_type == 'crypto':
        usd_cents = amount_raw
        return usd_cents * usd_rub_rate // 100
    else:
        return amount_raw


async def process_referral_reward(
    payer_id: int,
    period_days: int,
    amount_raw: int,
    payment_type: str
) -> None:
    """
    РћР±СЂР°Р±РѕС‚РєР° СЂРµС„РµСЂР°Р»СЊРЅРѕРіРѕ РІРѕР·РЅР°РіСЂР°Р¶РґРµРЅРёСЏ РїСЂРё РѕРїР»Р°С‚Рµ.
    Р’С‹Р·С‹РІР°РµС‚СЃСЏ РџРћРЎР›Р• СѓСЃРїРµС€РЅРѕР№ РѕР±СЂР°Р±РѕС‚РєРё РїР»Р°С‚РµР¶Р°.
    
    Args:
        payer_id: Р’РЅСѓС‚СЂРµРЅРЅРёР№ ID РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ, РєРѕС‚РѕСЂС‹Р№ РѕРїР»Р°С‚РёР»
        period_days: РЎРєРѕР»СЊРєРѕ РґРЅРµР№ РєСѓРїРёР» СЂРµС„РµСЂР°Р»
        amount_raw: РЎР«Р РђРЇ СЃСѓРјРјР°:
            - 'stars': РєРѕР»РёС‡РµСЃС‚РІРѕ Р·РІС‘Р·Рґ (int)
            - 'crypto': С†РµРЅС‚С‹ USDT (int)
            - 'cards': РєРѕРїРµР№РєРё СЂСѓР±Р»РµР№ (int)
            - 'yookassa_qr': РєРѕРїРµР№РєРё СЂСѓР±Р»РµР№ (int)
        payment_type: РўРёРї РїР»Р°С‚РµР¶Р° ('stars', 'crypto', 'cards', 'yookassa_qr')
    
    Note:
        РџСЂРё РѕРїР»Р°С‚Рµ Р±Р°Р»Р°РЅСЃРѕРј СЂРµС„РµСЂР°Р»СЊРЅС‹Рµ РІРѕР·РЅР°РіСЂР°Р¶РґРµРЅРёСЏ РќР• РЅР°С‡РёСЃР»СЏСЋС‚СЃСЏ,
        РїРѕСЌС‚РѕРјСѓ СЌС‚Р° С„СѓРЅРєС†РёСЏ РЅРµ РІС‹Р·С‹РІР°РµС‚СЃСЏ РґР»СЏ РїР»Р°С‚РµР¶РµР№ Р±Р°Р»Р°РЅСЃРѕРј.
    """
    if not is_referral_enabled():
        return
    
    reward_type = get_referral_reward_type()
    levels = get_active_referral_levels()
    
    if not levels:
        return
    
    usd_rub_rate = await get_usd_rub_rate()
    amount_rub_cents = convert_to_rub_cents(amount_raw, payment_type, usd_rub_rate)
    
    current_user_id = payer_id
    
    from bot.services.user_locks import user_locks
    
    for level_num, percent in levels:
        referrer_id = get_user_referrer(current_user_id)
        if not referrer_id:
            break
        
        coefficient = get_user_referral_coefficient(referrer_id)
        
        if reward_type == 'balance':
            base_reward = amount_rub_cents * (percent / 100)
            final_reward = int(base_reward * coefficient)
            final_reward = round(final_reward / 100) * 100
            
            if final_reward > 0:
                async with user_locks[referrer_id]:
                    add_to_balance(referrer_id, final_reward)
            
            reward_days = 0
        else:
            base_days = period_days * (percent / 100)
            final_days = base_days * coefficient
            reward_days = math.ceil(final_days)
            
            if reward_days > 0:
                add_days_to_first_active_key(referrer_id, reward_days)
            
            final_reward = 0
        
        update_referral_stat(
            referrer_id, payer_id, level_num,
            final_reward, reward_days
        )
        
        current_user_id = referrer_id


def calculate_balance_discount(user_id: int, tariff_price_cents: int) -> tuple[int, int]:
    """
    Р Р°СЃСЃС‡РёС‚Р°С‚СЊ СЃРєРёРґРєСѓ СЃ Р±Р°Р»Р°РЅСЃР°. Р‘Р•Р— СЃРїРёСЃР°РЅРёСЏ!
    
    Args:
        user_id: Р’РЅСѓС‚СЂРµРЅРЅРёР№ ID РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ
        tariff_price_cents: Р¦РµРЅР° С‚Р°СЂРёС„Р° РІ РєРѕРїРµР№РєР°С…
    
    Returns:
        РљРѕСЂС‚РµР¶ (remaining_to_pay_cents, to_deduct_cents):
        - remaining_to_pay_cents: СЃРєРѕР»СЊРєРѕ РЅСѓР¶РЅРѕ РѕРїР»Р°С‚РёС‚СЊ РІРЅРµС€РЅРёРј СЃРїРѕСЃРѕР±РѕРј
        - to_deduct_cents: СЃРєРѕР»СЊРєРѕ Р±СѓРґРµС‚ СЃРїРёСЃР°РЅРѕ СЃ Р±Р°Р»Р°РЅСЃР° РџР Р РЈРЎРџР•РЁРќРћР™ РѕРїР»Р°С‚Рµ
    """
    balance = get_user_balance(user_id)
    
    if balance >= tariff_price_cents:
        return 0, tariff_price_cents
    else:
        return tariff_price_cents - balance, balance


async def complete_payment_flow(
    order_id: str,
    message,
    state,
    telegram_id: int,
    payment_type: str,
    referral_amount: int
) -> None:
    """
    Р•РґРёРЅС‹Р№ post-payment РїРѕС‚РѕРє РїРѕСЃР»Рµ РїРѕРґС‚РІРµСЂР¶РґРµРЅРёСЏ РѕРїР»Р°С‚С‹.
    
    Р’С‹РїРѕР»РЅСЏРµС‚:
    1. РћР±СЂР°Р±РѕС‚РєСѓ РѕСЂРґРµСЂР° (process_payment_order)
    2. РЎРїРёСЃР°РЅРёРµ Р±Р°Р»Р°РЅСЃР° (РµСЃР»Рё С‡Р°СЃС‚РёС‡РЅР°СЏ РѕРїР»Р°С‚Р°)
    3. РќР°С‡РёСЃР»РµРЅРёРµ СЂРµС„РµСЂР°Р»СЊРЅРѕРіРѕ РІРѕР·РЅР°РіСЂР°Р¶РґРµРЅРёСЏ
    4. Р¤РёРЅР°Р»РёР·Р°С†РёСЋ UI (РІС‹РґР°С‡Р° РєР»СЋС‡Р° / РїРѕРєР°Р· СЂРµР·СѓР»СЊС‚Р°С‚Р°)
    
    Р’С‹Р·С‹РІР°РµС‚СЃСЏ РёР·:
    - successful_payment_handler (Stars/Cards) вЂ” base.py
    - check_yookassa_payment (QR/РЎР‘Рџ) вЂ” yookassa.py
    
    Args:
        order_id: ID РѕСЂРґРµСЂР°
        message: РЎРѕРѕР±С‰РµРЅРёРµ РґР»СЏ РѕС‚РІРµС‚Р° РїРѕР»СЊР·РѕРІР°С‚РµР»СЋ
        state: FSM-РєРѕРЅС‚РµРєСЃС‚ (РґР»СЏ Р±Р°Р»Р°РЅСЃР° Рё РѕС‡РёСЃС‚РєРё)
        telegram_id: Telegram ID РїРѕР»СЊР·РѕРІР°С‚РµР»СЏ
        payment_type: РўРёРї РїР»Р°С‚РµР¶Р° ('stars', 'cards', 'yookassa_qr')
        referral_amount: РЎС‹СЂР°СЏ СЃСѓРјРјР° РґР»СЏ СЂРµС„РµСЂР°Р»СЊРЅРѕРіРѕ РІРѕР·РЅР°РіСЂР°Р¶РґРµРЅРёСЏ:
            - 'stars': РєРѕР»РёС‡РµСЃС‚РІРѕ Р·РІС‘Р·Рґ
            - 'cards': РєРѕРїРµР№РєРё СЂСѓР±Р»РµР№
            - 'yookassa_qr': РєРѕРїРµР№РєРё СЂСѓР±Р»РµР№
    """
    from bot.handlers.user.payments.base import finalize_payment_ui
    from bot.keyboards.admin import home_only_kb
    from bot.services.user_locks import user_locks
    
    state_data = await state.get_data()
    balance_to_deduct = state_data.get('balance_to_deduct', 0)
    
    try:
        (success, text, order) = await process_payment_order(order_id)
        
        if success and order:
            user_internal_id = order['user_id']
            days = order.get('period_days') or order.get('duration_days') or 30
            
            # РЎРїРёСЃР°РЅРёРµ Р±Р°Р»Р°РЅСЃР° РїСЂРё С‡Р°СЃС‚РёС‡РЅРѕР№ РѕРїР»Р°С‚Рµ
            if balance_to_deduct > 0:
                async with user_locks[user_internal_id]:
                    current_balance = get_user_balance(user_internal_id)
                    actual_deduct = min(balance_to_deduct, current_balance)
                    if actual_deduct > 0:
                        deduct_from_balance(user_internal_id, actual_deduct)
                        logger.info(
                            f'РЎРїРёСЃР°РЅРѕ {actual_deduct} РєРѕРї СЃ Р±Р°Р»Р°РЅСЃР° user '
                            f'{user_internal_id} РїСЂРё С‡Р°СЃС‚РёС‡РЅРѕР№ РѕРїР»Р°С‚Рµ ({payment_type})'
                        )
            
            # РћС‡РёСЃС‚РєР° FSM РґР°РЅРЅС‹С… Рѕ Р±Р°Р»Р°РЅСЃРµ
            await state.update_data(balance_to_deduct=0, remaining_cents=0)
            
            # Р РµС„РµСЂР°Р»СЊРЅРѕРµ РІРѕР·РЅР°РіСЂР°Р¶РґРµРЅРёРµ
            await process_referral_reward(user_internal_id, days, referral_amount, payment_type)

            try:
                from bot.services.notifications import notify_admins_payment
                await notify_admins_payment(message.bot, order)
            except Exception as notify_err:
                logger.warning(f'Ошибка уведомления администраторов об оплате: {notify_err}')
            
            # Р¤РёРЅР°Р»РёР·Р°С†РёСЏ UI
            await finalize_payment_ui(message, state, text, order, user_id=telegram_id)
        else:
            await message.answer(text, reply_markup=home_only_kb(), parse_mode='HTML')
    
    except Exception as e:
        from bot.errors import TariffNotFoundError
        if isinstance(e, TariffNotFoundError):
            from bot.keyboards.user import support_kb
            support_link = get_setting('support_channel_link', 'https://t.me/YadrenoChat')
            await message.answer(str(e), reply_markup=support_kb(support_link), parse_mode='HTML')
        else:
            logger.exception(f'РћС€РёР±РєР° РѕР±СЂР°Р±РѕС‚РєРё {payment_type} РїР»Р°С‚РµР¶Р°: {e}')
            await message.answer('вќЊ РџСЂРѕРёР·РѕС€Р»Р° РѕС€РёР±РєР° РїСЂРё РѕР±СЂР°Р±РѕС‚РєРµ РїР»Р°С‚РµР¶Р°.', parse_mode='HTML')
