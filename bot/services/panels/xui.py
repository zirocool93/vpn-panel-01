"""
Р РЋР ВµРЎР‚Р Р†Р С‘РЎРѓ Р Т‘Р В»РЎРЏ РЎР‚Р В°Р В±Р С•РЎвЂљРЎвЂ№ РЎРѓ API 3X-UI Р С—Р В°Р Р…Р ВµР В»Р С‘.

Р С›Р В±Р ВµРЎРѓР С—Р ВµРЎвЂЎР С‘Р Р†Р В°Р ВµРЎвЂљ:
- Р С’Р Р†РЎвЂљР С•РЎР‚Р С‘Р В·Р В°РЎвЂ Р С‘РЎР‹ РЎвЂЎР ВµРЎР‚Р ВµР В· РЎРѓР ВµРЎРѓРЎРѓР С‘Р С‘
- Р Р€Р С—РЎР‚Р В°Р Р†Р В»Р ВµР Р…Р С‘Р Вµ Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР В°Р СР С‘ (РЎРѓР С•Р В·Р Т‘Р В°Р Р…Р С‘Р Вµ, РЎС“Р Т‘Р В°Р В»Р ВµР Р…Р С‘Р Вµ, Р С•Р В±Р Р…Р С•Р Р†Р В»Р ВµР Р…Р С‘Р Вµ)
- Р СџР С•Р В»РЎС“РЎвЂЎР ВµР Р…Р С‘Р Вµ РЎРѓРЎвЂљР В°РЎвЂљР С‘РЎРѓРЎвЂљР С‘Р С”Р С‘ РЎвЂљРЎР‚Р В°РЎвЂћР С‘Р С”Р В°
- Р Р€Р С—РЎР‚Р В°Р Р†Р В»Р ВµР Р…Р С‘Р Вµ inbound-Р С—Р С•Р Т‘Р С”Р В»РЎР‹РЎвЂЎР ВµР Р…Р С‘РЎРЏР СР С‘
"""

import aiohttp
import asyncio
import logging
import json
import re
import uuid
import time
import urllib.parse
from typing import Optional, Dict, Any, List
from config import RETRY_CONFIG

logger = logging.getLogger(__name__)

API_PROFILE_LEGACY = "legacy_inbounds"
API_PROFILE_CLIENTS = "clients_api"
BOT_API_TOKEN_NAME = "YadrenoVPN Bot"
JSON_INBOUND_FIELDS = ("settings", "streamSettings", "sniffing")
SETTING_BASE_LEGACY = "/panel/setting"
SETTING_BASE_API = "/panel/api/setting"


from .base import BaseVPNClient, VPNAPIError


class StaleAPIProfileError(Exception):
    """Р СџР В°Р Р…Р ВµР В»РЎРЉ РЎРѓР СР ВµР Р…Р С‘Р В»Р В° Р С—РЎР‚Р С•РЎвЂћР С‘Р В»РЎРЉ API; Р С•Р С—Р ВµРЎР‚Р В°РЎвЂ Р С‘РЎР‹ Р Р…РЎС“Р В¶Р Р…Р С• Р Р†РЎвЂ№Р В±РЎР‚Р В°РЎвЂљРЎРЉ Р В·Р В°Р Р…Р С•Р Р†Р С•."""


class XUIClient(BaseVPNClient):
    """
    Р С™Р В»Р С‘Р ВµР Р…РЎвЂљ Р Т‘Р В»РЎРЏ РЎР‚Р В°Р В±Р С•РЎвЂљРЎвЂ№ РЎРѓ API 3X-UI Р С—Р В°Р Р…Р ВµР В»Р С‘.
    
    Р ВРЎРѓР С—Р С•Р В»РЎРЉР В·РЎС“Р ВµРЎвЂљ РЎРѓР ВµРЎРѓРЎРѓР С‘Р С•Р Р…Р Р…РЎС“РЎР‹ Р В°РЎС“РЎвЂљР ВµР Р…РЎвЂљР С‘РЎвЂћР С‘Р С”Р В°РЎвЂ Р С‘РЎР‹ (cookie-based).
    Р вЂ™Р С’Р вЂ“Р СњР С›: Р вЂќР В»РЎРЏ 3X-UI Р С”РЎС“Р С”Р С‘ Р СР С•Р С–РЎС“РЎвЂљ Р В±РЎвЂ№РЎвЂљРЎРЉ Р С—РЎР‚Р С‘Р Р†РЎРЏР В·Р В°Р Р…РЎвЂ№ Р С” IP, Р С—Р С•РЎРЊРЎвЂљР С•Р СРЎС“ Р С‘РЎРѓР С—Р С•Р В»РЎРЉР В·РЎС“Р ВµР С unsafe=True Р Т‘Р В»РЎРЏ CookieJar.
    """
    
    def __init__(self, server: dict):
        """
        Р ВР Р…Р С‘РЎвЂ Р С‘Р В°Р В»Р С‘Р В·Р В°РЎвЂ Р С‘РЎРЏ Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР В°.

        Args:
            server: Р РЋР В»Р С•Р Р†Р В°РЎР‚РЎРЉ РЎРѓ Р Т‘Р В°Р Р…Р Р…РЎвЂ№Р СР С‘ РЎРѓР ВµРЎР‚Р Р†Р ВµРЎР‚Р В° Р С‘Р В· Р вЂР вЂќ
        """
        self.server = server
        self.server_id = server.get('id')
        self.host = server['host']
        self.port = server['port']
        self.protocol = server.get('protocol', 'https')
        # Р вЂњР В°РЎР‚Р В°Р Р…РЎвЂљР С‘РЎР‚РЎС“Р ВµР С, РЎвЂЎРЎвЂљР С• Р С—РЎС“РЎвЂљРЎРЉ Р Р…Р В°РЎвЂЎР С‘Р Р…Р В°Р ВµРЎвЂљРЎРѓРЎРЏ РЎРѓР С• РЎРѓР В»Р ВµРЎв‚¬Р В°, Р Р…Р С• Р СњР вЂў Р В·Р В°Р С”Р В°Р Р…РЎвЂЎР С‘Р Р†Р В°Р ВµРЎвЂљРЎРѓРЎРЏ Р С‘Р С
        # strip('/') РЎС“Р В±Р С‘РЎР‚Р В°Р ВµРЎвЂљ РЎРѓР В»Р ВµРЎв‚¬Р С‘ Р С‘ РЎРѓ Р Р…Р В°РЎвЂЎР В°Р В»Р В°, Р С‘ РЎРѓ Р С”Р С•Р Р…РЎвЂ Р В°
        path = server.get('web_base_path', '').strip('/')
        # Р СћР ВµР С—Р ВµРЎР‚РЎРЉ Р Т‘Р С•Р В±Р В°Р Р†Р В»РЎРЏР ВµР С Р С•Р Т‘Р С‘Р Р… РЎРѓР В»Р ВµРЎв‚¬ Р Р† Р Р…Р В°РЎвЂЎР В°Р В»Р С• (Р ВµРЎРѓР В»Р С‘ Р С—РЎС“РЎвЂљРЎРЉ Р Р…Р Вµ Р С—РЎС“РЎРѓРЎвЂљР С•Р в„–)
        path = f"/{path}" if path else ""

        self.base_url = f"{self.protocol}://{self.host}:{self.port}{path}"

        self.session: Optional[aiohttp.ClientSession] = None
        self.is_authenticated = False

        # Р СџР С•Р Т‘Р Т‘Р ВµРЎР‚Р В¶Р С”Р В° РЎР‚Р В°Р В·Р Р…РЎвЂ№РЎвЂ¦ Р С—Р С•Р С”Р С•Р В»Р ВµР Р…Р С‘Р в„– 3x-ui.
        # auth_mode/panel_mode:
        #   legacy = v2.x cookie; csrf = v3.0+ cookie + X-CSRF-Token;
        #   bearer = v3.0+ РЎвЂЎР ВµРЎР‚Р ВµР В· Authorization: Bearer Р Т‘Р В»РЎРЏ /panel/api/*.
        # api_profile:
        #   legacy_inbounds = РЎРѓРЎвЂљР В°РЎР‚РЎвЂ№Р Вµ client-Р С•Р С—Р ВµРЎР‚Р В°РЎвЂ Р С‘Р С‘ РЎвЂЎР ВµРЎР‚Р ВµР В· /panel/api/inbounds/*
        #   clients_api = first-class clients API Р С‘Р В· 3x-ui v3.1.0+.
        self.panel_mode: Optional[str] = None
        self.auth_mode: Optional[str] = None
        self.cookie_authenticated = False
        self.csrf_token: Optional[str] = None
        self.api_token: Optional[str] = server.get('api_token') or None
        self.panel_version: Optional[str] = server.get('panel_version') or None
        self.api_profile: Optional[str] = server.get('panel_api_profile') or None
        self._profile_verified = False
        self.api_token_diagnostic: Optional[str] = None

        # Р С™Р ВµРЎв‚¬ Р Р…Р В°РЎРѓРЎвЂљРЎР‚Р С•Р ВµР С” Р С—Р В°Р Р…Р ВµР В»Р С‘ (subPort/subPath/subDomain/...) Р С‘Р В· /panel/setting/all.
        # Р ВРЎРѓР С—Р С•Р В»РЎРЉР В·РЎС“Р ВµРЎвЂљРЎРѓРЎРЏ build_subscription_url() РІР‚вЂќ Р В·Р В° РЎРѓР ВµРЎРѓРЎРѓР С‘РЎР‹ Р В·Р В°Р С—РЎР‚Р В°РЎв‚¬Р С‘Р Р†Р В°Р ВµРЎвЂљРЎРѓРЎРЏ Р С•Р Т‘Р С‘Р Р… РЎР‚Р В°Р В·.
        self._panel_settings: Optional[Dict[str, Any]] = None

        logger.debug(
            f"Р ВР Р…Р С‘РЎвЂ Р С‘Р В°Р В»Р С‘Р В·Р С‘РЎР‚Р С•Р Р†Р В°Р Р… XUIClient Р Т‘Р В»РЎРЏ {server['name']}: {self.base_url} "
            f"(api_token={'Р ВµРЎРѓРЎвЂљРЎРЉ' if self.api_token else 'Р Р…Р ВµРЎвЂљ'})"
        )
    
    async def _ensure_session(self) -> aiohttp.ClientSession:
        """Р РЋР С•Р В·Р Т‘Р В°РЎвЂРЎвЂљ РЎРѓР ВµРЎРѓРЎРѓР С‘РЎР‹ Р ВµРЎРѓР В»Р С‘ Р ВµРЎвЂ Р Р…Р ВµРЎвЂљ."""
        if self.session is None or self.session.closed:
            # Unsafe=True Р Р†Р В°Р В¶Р Р…Р С• Р Т‘Р В»РЎРЏ IP-Р В°Р Т‘РЎР‚Р ВµРЎРѓР С•Р Р† Р С‘ РЎРѓР В°Р СР С•Р С—Р С•Р Т‘Р С—Р С‘РЎРѓР В°Р Р…Р Р…РЎвЂ№РЎвЂ¦ РЎРѓР ВµРЎР‚РЎвЂљР С‘РЎвЂћР С‘Р С”Р В°РЎвЂљР С•Р Р†
            connector = aiohttp.TCPConnector(ssl=False)
            jar = aiohttp.CookieJar(unsafe=True)
            timeout = aiohttp.ClientTimeout(total=5)
            self.session = aiohttp.ClientSession(connector=connector, cookie_jar=jar, timeout=timeout)
            self.is_authenticated = False
            self.cookie_authenticated = False
            logger.debug(f"Р РЋР С•Р В·Р Т‘Р В°Р Р…Р В° Р Р…Р С•Р Р†Р В°РЎРЏ РЎРѓР ВµРЎРѓРЎРѓР С‘РЎРЏ Р Т‘Р В»РЎРЏ {self.server['name']}")
        return self.session
    
    async def _reset_session(self) -> None:
        """
        Р РЋР В±РЎР‚Р В°РЎРѓРЎвЂ№Р Р†Р В°Р ВµРЎвЂљ РЎвЂљР ВµР С”РЎС“РЎвЂ°РЎС“РЎР‹ РЎРѓР ВµРЎРѓРЎРѓР С‘РЎР‹.

        Р вЂ™РЎвЂ№Р В·РЎвЂ№Р Р†Р В°Р ВµРЎвЂљРЎРѓРЎРЏ Р С—РЎР‚Р С‘ Р С•РЎв‚¬Р С‘Р В±Р С”Р В°РЎвЂ¦ Р С—Р С•Р Т‘Р С”Р В»РЎР‹РЎвЂЎР ВµР Р…Р С‘РЎРЏ Р Т‘Р В»РЎРЏ Р С—Р ВµРЎР‚Р ВµРЎРѓР С•Р В·Р Т‘Р В°Р Р…Р С‘РЎРЏ РЎРѓР ВµРЎРѓРЎРѓР С‘Р С‘.
        CSRF-РЎвЂљР С•Р С”Р ВµР Р… Р С•РЎвЂЎР С‘РЎвЂ°Р В°Р ВµРЎвЂљРЎРѓРЎРЏ РІР‚вЂќ Р С•Р Р… Р С—РЎР‚Р С‘Р Р†РЎРЏР В·Р В°Р Р… Р С” РЎРѓР ВµРЎР‚Р Р†Р ВµРЎР‚Р Р…Р С•Р в„– РЎРѓР ВµРЎРѓРЎРѓР С‘Р С‘.
        panel_mode Р С‘ api_token Р СњР вЂў РЎРѓР В±РЎР‚Р В°РЎРѓРЎвЂ№Р Р†Р В°РЎР‹РЎвЂљРЎРѓРЎРЏ РІР‚вЂќ РЎРЊРЎвЂљР С• Р С—Р С•Р В»Р С‘РЎвЂљР С‘Р С”Р В°, Р В° Р Р…Р Вµ РЎРѓР ВµРЎРѓРЎРѓР С‘Р С•Р Р…Р Р…Р С•Р Вµ
        РЎРѓР С•РЎРѓРЎвЂљР С•РЎРЏР Р…Р С‘Р Вµ. Р ВРЎвЂ¦ Р С•РЎвЂљР Т‘Р ВµР В»РЎРЉР Р…Р С• РЎРѓР В±РЎР‚Р В°РЎРѓРЎвЂ№Р Р†Р В°Р ВµРЎвЂљ _invalidate_api_token() Р С—РЎР‚Р С‘ РЎР‚Р С•РЎвЂљР В°РЎвЂ Р С‘Р С‘
        РЎвЂљР С•Р С”Р ВµР Р…Р В° Р Р† Р С—Р В°Р Р…Р ВµР В»Р С‘.
        """
        if self.session and not self.session.closed:
            try:
                await self.session.close()
            except Exception as e:
                logger.debug(f"Р С›РЎв‚¬Р С‘Р В±Р С”Р В° Р С—РЎР‚Р С‘ Р В·Р В°Р С”РЎР‚РЎвЂ№РЎвЂљР С‘Р С‘ РЎРѓР ВµРЎРѓРЎРѓР С‘Р С‘: {e}")
        self.session = None
        self.is_authenticated = False
        self.cookie_authenticated = False
        self.csrf_token = None
        logger.debug(f"Р РЋР ВµРЎРѓРЎРѓР С‘РЎРЏ РЎРѓР В±РЎР‚Р С•РЎв‚¬Р ВµР Р…Р В° Р Т‘Р В»РЎРЏ {self.server['name']}")

    async def _invalidate_api_token(self) -> None:
        """
        Р РЋР В±РЎР‚Р В°РЎРѓРЎвЂ№Р Р†Р В°Р ВµРЎвЂљ Bearer-РЎвЂљР С•Р С”Р ВµР Р… (Р С—РЎР‚Р С‘ РЎР‚Р С•РЎвЂљР В°РЎвЂ Р С‘Р С‘ Р Р† Р С—Р В°Р Р…Р ВµР В»Р С‘ Р С‘Р В»Р С‘ 404 Р Р…Р В° Bearer-Р В·Р В°Р С—РЎР‚Р С•РЎРѓР Вµ).

        Р С›РЎвЂЎР С‘РЎвЂ°Р В°Р ВµРЎвЂљ РЎвЂљР С•Р С”Р ВµР Р… Р Р† Р вЂР вЂќ (РЎвЂЎР ВµРЎР‚Р ВµР В· update_server_api_token), РЎвЂЎРЎвЂљР С•Р В±РЎвЂ№ Р С—РЎР‚Р С‘ РЎРѓР В»Р ВµР Т‘РЎС“РЎР‹РЎвЂ°Р ВµР С
        Р В·Р В°Р С—РЎС“РЎРѓР С”Р Вµ Р В±Р С•РЎвЂљ Р Р…Р Вµ Р С—РЎвЂ№РЎвЂљР В°Р В»РЎРѓРЎРЏ Р С‘РЎРѓР С—Р С•Р В»РЎРЉР В·Р С•Р Р†Р В°РЎвЂљРЎРЉ Р Р…Р ВµР Р†Р В°Р В»Р С‘Р Т‘Р Р…РЎвЂ№Р в„– РЎвЂљР С•Р С”Р ВµР Р….
        """
        if self.api_token is None:
            return
        self.api_token = None
        # panel_mode Р С—Р ВµРЎР‚Р ВµРЎРѓР С•Р В·Р Т‘Р В°РЎРѓРЎвЂљРЎРѓРЎРЏ Р С—РЎР‚Р С‘ РЎРѓР В»Р ВµР Т‘РЎС“РЎР‹РЎвЂ°Р ВµР С login() РІР‚вЂќ Р СР С•Р В¶Р ВµРЎвЂљ Р С•Р С”Р В°Р В·Р В°РЎвЂљРЎРЉРЎРѓРЎРЏ 'csrf'
        # (Р ВµРЎРѓР В»Р С‘ РЎвЂљР С•Р С”Р ВµР Р… Р С—РЎР‚Р С•РЎвЂљРЎС“РЎвЂ¦, Р Р…Р С• Р С—Р В°Р Р…Р ВµР В»РЎРЉ Р Р†РЎРѓРЎвЂ Р ВµРЎвЂ°РЎвЂ v3.0+) Р В»Р С‘Р В±Р С• 'bearer' РЎРѓР Р…Р С•Р Р†Р В° (Р ВµРЎРѓР В»Р С‘
        # РЎвЂћР С•Р Р…Р С•Р Р†РЎвЂ№Р в„– login РЎС“РЎРѓР С—Р ВµР ВµРЎвЂљ Р Р†РЎвЂ№РЎвЂљРЎРЏР Р…РЎС“РЎвЂљРЎРЉ Р Р…Р С•Р Р†РЎвЂ№Р в„– РЎвЂљР С•Р С”Р ВµР Р…).
        self.panel_mode = None
        self.auth_mode = None
        if self.server_id is not None:
            try:
                from database.db_servers import update_server_api_token
                update_server_api_token(self.server_id, None)
            except Exception as e:
                logger.warning(f"Р СњР Вµ РЎС“Р Т‘Р В°Р В»Р С•РЎРѓРЎРЉ Р С•РЎвЂЎР С‘РЎРѓРЎвЂљР С‘РЎвЂљРЎРЉ api_token Р Р† Р вЂР вЂќ Р Т‘Р В»РЎРЏ server_id={self.server_id}: {e}")

    @staticmethod
    def _load_json_field(value: Any, default: Optional[Any] = None) -> Any:
        """Р вЂ™Р С•Р В·Р Р†РЎР‚Р В°РЎвЂ°Р В°Р ВµРЎвЂљ dict/list Р С‘Р В· JSON-РЎРѓРЎвЂљРЎР‚Р С•Р С”Р С‘ Р С‘Р В»Р С‘ РЎС“Р В¶Р Вµ РЎР‚Р В°РЎРѓР С—Р В°Р С”Р С•Р Р†Р В°Р Р…Р Р…Р С•Р С–Р С• Р В·Р Р…Р В°РЎвЂЎР ВµР Р…Р С‘РЎРЏ."""
        if default is None:
            default = {}
        if value in (None, ""):
            return default.copy() if isinstance(default, (dict, list)) else default
        if isinstance(value, str):
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                return default.copy() if isinstance(default, (dict, list)) else default
        if isinstance(value, (dict, list)):
            return value
        return default.copy() if isinstance(default, (dict, list)) else default

    @staticmethod
    def _json_field_to_text(value: Any, empty: str = "{}") -> str:
        """Р СњР С•РЎР‚Р СР В°Р В»Р С‘Р В·РЎС“Р ВµРЎвЂљ JSON-Р С—Р С•Р В»Р Вµ inbound Р С” РЎРѓРЎвЂљРЎР‚Р С•Р С”Р Вµ Р Т‘Р В»РЎРЏ РЎРѓРЎвЂљР В°РЎР‚Р С•Р в„– Р В»Р С•Р С–Р С‘Р С”Р С‘ Р В±Р С•РЎвЂљР В°."""
        if value in (None, ""):
            return empty
        if isinstance(value, str):
            return value
        try:
            return json.dumps(value, ensure_ascii=False)
        except (TypeError, ValueError):
            return empty

    @classmethod
    def _normalize_inbound(cls, inbound: Dict[str, Any]) -> Dict[str, Any]:
        """Р СџРЎР‚Р С‘Р Р†Р С•Р Т‘Р С‘РЎвЂљ inbound v3.1.0 РЎРѓ nested JSON Р С” legacy-РЎвЂћР С•РЎР‚Р СР Вµ РЎРѓР С• РЎРѓРЎвЂљРЎР‚Р С•Р С”Р В°Р СР С‘."""
        if not isinstance(inbound, dict):
            return inbound
        normalized = dict(inbound)
        for field in JSON_INBOUND_FIELDS:
            normalized[field] = cls._json_field_to_text(normalized.get(field), "{}")
        return normalized

    @staticmethod
    def _normalize_tg_id(value: Any) -> int:
        """3x-ui v3.1.0 РЎвЂ¦РЎР‚Р В°Р Р…Р С‘РЎвЂљ tgId Р С”Р В°Р С” int64; Р С—РЎС“РЎРѓРЎвЂљРЎвЂ№Р Вµ Р С‘ Р СРЎС“РЎРѓР С•РЎР‚Р Р…РЎвЂ№Р Вµ Р В·Р Р…Р В°РЎвЂЎР ВµР Р…Р С‘РЎРЏ = 0."""
        if value in (None, ""):
            return 0
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _client_identifier_from_entry(client: Dict[str, Any]) -> str:
        """Р вЂ™Р С•Р В·Р Р†РЎР‚Р В°РЎвЂ°Р В°Р ВµРЎвЂљ РЎвЂљР ВµРЎвЂ¦Р Р…Р С‘РЎвЂЎР ВµРЎРѓР С”Р С‘Р в„– Р С‘Р Т‘Р ВµР Р…РЎвЂљР С‘РЎвЂћР С‘Р С”Р В°РЎвЂљР С•РЎР‚ Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР В° Р Т‘Р В»РЎРЏ РЎРѓРЎвЂљР В°РЎР‚РЎвЂ№РЎвЂ¦ update/delete."""
        if not isinstance(client, dict):
            return ""
        return client.get("id") or client.get("password") or client.get("auth") or ""

    def _save_api_token(self, token: str) -> None:
        """Р РЋР С•РЎвЂ¦РЎР‚Р В°Р Р…РЎРЏР ВµРЎвЂљ Bearer-РЎвЂљР С•Р С”Р ВµР Р… Р Р† Р С•Р В±РЎР‰Р ВµР С”РЎвЂљР Вµ Р С‘ Р вЂР вЂќ."""
        self.api_token = token
        self.server["api_token"] = token
        if self.server_id is not None:
            try:
                from database.db_servers import update_server_api_token
                update_server_api_token(self.server_id, token)
            except Exception as e:
                logger.warning(f"Р СњР Вµ РЎС“Р Т‘Р В°Р В»Р С•РЎРѓРЎРЉ РЎРѓР С•РЎвЂ¦РЎР‚Р В°Р Р…Р С‘РЎвЂљРЎРЉ api_token Р Р† Р вЂР вЂќ: {e}")

    def _save_panel_info(self) -> None:
        """Р РЋР С•РЎвЂ¦РЎР‚Р В°Р Р…РЎРЏР ВµРЎвЂљ Р С•Р С—РЎР‚Р ВµР Т‘Р ВµР В»РЎвЂР Р…Р Р…РЎвЂ№Р Вµ version/profile Р С—Р В°Р Р…Р ВµР В»Р С‘ Р Р† Р С•Р В±РЎР‰Р ВµР С”РЎвЂљР Вµ Р С‘ Р вЂР вЂќ."""
        self.server["panel_version"] = self.panel_version
        self.server["panel_api_profile"] = self.api_profile
        if self.server_id is None:
            return
        try:
            from database.db_servers import update_server_panel_info
            update_server_panel_info(self.server_id, self.panel_version, self.api_profile)
        except Exception as e:
            logger.debug(f"Р СњР Вµ РЎС“Р Т‘Р В°Р В»Р С•РЎРѓРЎРЉ РЎРѓР С•РЎвЂ¦РЎР‚Р В°Р Р…Р С‘РЎвЂљРЎРЉ Р Т‘Р С‘Р В°Р С–Р Р…Р С•РЎРѓРЎвЂљР С‘Р С”РЎС“ Р С—Р В°Р Р…Р ВµР В»Р С‘ Р Р† Р вЂР вЂќ: {e}")

    def _build_client_payload_from_record(
        self,
        record: Dict[str, Any],
        fallback_email: Optional[str] = None,
        fallback_uuid: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Р СџРЎР‚Р ВµР С•Р В±РЎР‚Р В°Р В·РЎС“Р ВµРЎвЂљ ClientRecord/get_inbounds client Р Р† model.Client payload v3.1.0.

        Р вЂ™ Р С•РЎвЂљР Р†Р ВµРЎвЂљР Вµ /clients/get Р С—Р С•Р В»Р Вµ id РІР‚вЂќ РЎвЂЎР С‘РЎРѓР В»Р С•Р Р†Р С•Р в„– ID Р В·Р В°Р С—Р С‘РЎРѓР С‘ Р вЂР вЂќ, Р В° UUID Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР В°
        Р В»Р ВµР В¶Р С‘РЎвЂљ Р Р† uuid. Р вЂ™ payload update Р С—Р С•Р В»Р Вµ id Р Т‘Р С•Р В»Р В¶Р Р…Р С• Р В±РЎвЂ№РЎвЂљРЎРЉ Р С‘Р СР ВµР Р…Р Р…Р С• UUID.
        """
        if not isinstance(record, dict):
            record = {}

        uuid_value = record.get("uuid")
        record_id = record.get("id")
        if not uuid_value and isinstance(record_id, str):
            uuid_value = record_id
        if not uuid_value and fallback_uuid:
            uuid_value = fallback_uuid

        payload: Dict[str, Any] = {
            "email": record.get("email") or fallback_email or "",
            "security": record.get("security", "auto"),
            "limitIp": record.get("limitIp", 1),
            "totalGB": record.get("totalGB", 0),
            "expiryTime": record.get("expiryTime", 0),
            "enable": record.get("enable", True),
            "tgId": self._normalize_tg_id(record.get("tgId", 0)),
            "subId": record.get("subId", ""),
            "comment": record.get("comment", ""),
            "reset": record.get("reset", 0),
        }

        if uuid_value:
            payload["id"] = uuid_value
        for field in ("password", "auth", "flow"):
            value = record.get(field)
            if value:
                payload[field] = value
        reverse = record.get("reverse")
        if reverse:
            payload["reverse"] = reverse
        return {k: v for k, v in payload.items() if v != ""}

    @staticmethod
    def _split_clients_api_record(record: Dict[str, Any]) -> tuple:
        """Р вЂ™Р С•Р В·Р Р†РЎР‚Р В°РЎвЂ°Р В°Р ВµРЎвЂљ (client, inboundIds) Р С‘Р В· Р С•РЎвЂљР Р†Р ВµРЎвЂљР В° /panel/api/clients/get/:email."""
        if not isinstance(record, dict):
            return {}, []
        if isinstance(record.get("client"), dict):
            client = dict(record["client"])
            inbound_ids = record.get("inboundIds") or client.get("inboundIds") or []
        else:
            client = dict(record)
            inbound_ids = record.get("inboundIds") or []
        if not isinstance(inbound_ids, list):
            inbound_ids = []
        return client, [int(i) for i in inbound_ids if str(i).isdigit()]

    @staticmethod
    def _version_tuple(version: Optional[str]) -> tuple:
        if not version:
            return ()
        parts = []
        for part in str(version).strip().lstrip("vV").split("."):
            match = re.match(r"(\d+)", part)
            if not match:
                break
            parts.append(int(match.group(1)))
        return tuple(parts)

    @classmethod
    def _version_at_least(cls, version: Optional[str], minimum: tuple) -> bool:
        parts = cls._version_tuple(version)
        if not parts:
            return False
        max_len = max(len(parts), len(minimum))
        return parts + (0,) * (max_len - len(parts)) >= minimum + (0,) * (max_len - len(minimum))

    def _setting_bases(self) -> List[str]:
        if self._version_at_least(self.panel_version, (3, 3, 0)):
            return [SETTING_BASE_API, SETTING_BASE_LEGACY]
        return [SETTING_BASE_LEGACY, SETTING_BASE_API]

    def _setting_endpoints(self, suffix: str) -> List[str]:
        suffix = suffix.lstrip("/")
        return [f"{base}/{suffix}" for base in self._setting_bases()]

    async def _raw_json_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
    ) -> tuple:
        """Raw-Р В·Р В°Р С—РЎР‚Р С•РЎРѓ Р В±Р ВµР В· login/_request, РЎвЂЎРЎвЂљР С•Р В±РЎвЂ№ probes Р Р…Р Вµ Р В·Р В°РЎвЂ Р С‘Р С”Р В»Р С‘Р Р†Р В°Р В»Р С‘РЎРѓРЎРЉ."""
        session = await self._ensure_session()
        url = f"{self.base_url}{endpoint}"
        try:
            async with session.request(method, url, json=data, headers=headers or {}) as resp:
                text = await resp.text()
                try:
                    body = json.loads(text) if text else {}
                except json.JSONDecodeError:
                    body = {}
                return resp.status, body
        except aiohttp.ClientError as e:
            logger.debug(f"Raw API Р В·Р В°Р С—РЎР‚Р С•РЎРѓ {method} {endpoint} РЎС“Р С—Р В°Р В»: {e}")
            return 0, {}

    async def _fetch_panel_version(self) -> Optional[str]:
        """Р С›Р С—РЎР‚Р ВµР Т‘Р ВµР В»РЎРЏР ВµРЎвЂљ Р Р†Р ВµРЎР‚РЎРѓР С‘РЎР‹ Р С—Р В°Р Р…Р ВµР В»Р С‘ РЎвЂЎР ВµРЎР‚Р ВµР В· server/status РЎРѓ fallback Р Р…Р В° updateInfo."""
        headers = self._build_headers("GET")

        status, data = await self._raw_json_request(
            "GET",
            "/panel/api/server/status",
            headers=headers,
        )
        if status == 200 and isinstance(data, dict):
            obj = data.get("obj")
            if isinstance(obj, dict):
                for key in ("panelVersion", "version", "currentVersion"):
                    value = obj.get(key)
                    if isinstance(value, str) and value:
                        return value

        status, data = await self._raw_json_request(
            "GET",
            "/panel/api/server/getPanelUpdateInfo",
            headers=headers,
        )
        if status == 200 and isinstance(data, dict):
            obj = data.get("obj")
            if isinstance(obj, dict):
                for key in ("currentVersion", "panelVersion", "version"):
                    value = obj.get(key)
                    if isinstance(value, str) and value:
                        return value
        return None

    async def _detect_api_profile(self) -> str:
        """Feature-probe: v3.1.0+ Р С‘Р СР ВµР ВµРЎвЂљ /panel/api/clients/list/paged."""
        headers = self._build_headers("GET")
        status, data = await self._raw_json_request(
            "GET",
            "/panel/api/clients/list/paged",
            headers=headers,
        )
        if status == 200 and isinstance(data, dict) and data.get("success"):
            return API_PROFILE_CLIENTS
        return API_PROFILE_LEGACY

    async def _refresh_panel_metadata(self, force: bool = False) -> None:
        """Р С›Р В±Р Р…Р С•Р Р†Р В»РЎРЏР ВµРЎвЂљ version/profile Р С—Р В°Р Р…Р ВµР В»Р С‘ Р С‘ Р С—Р С‘РЎв‚¬Р ВµРЎвЂљ Р С”Р ВµРЎв‚¬ Р Р† servers."""
        if not force and self.api_profile in (API_PROFILE_LEGACY, API_PROFILE_CLIENTS):
            if self.panel_version:
                return

        version = await self._fetch_panel_version()
        profile = await self._detect_api_profile()

        if version:
            self.panel_version = version
        self.api_profile = profile
        self._profile_verified = True
        self._save_panel_info()

    async def _ensure_api_profile(self) -> str:
        """Р вЂњР В°РЎР‚Р В°Р Р…РЎвЂљР С‘РЎР‚РЎС“Р ВµРЎвЂљ, РЎвЂЎРЎвЂљР С• Р Р†РЎвЂ№Р В±РЎР‚Р В°Р Р… Р С—РЎР‚Р С•РЎвЂћР С‘Р В»РЎРЉ API Р Т‘Р В»РЎРЏ Р С•Р С—Р ВµРЎР‚Р В°РЎвЂ Р С‘Р в„– РЎРѓ Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР В°Р СР С‘."""
        if not self.is_authenticated:
            await self.login()
        if self.api_profile in (API_PROFILE_LEGACY, API_PROFILE_CLIENTS) and self._profile_verified:
            return self.api_profile
        if self.api_profile not in (API_PROFILE_LEGACY, API_PROFILE_CLIENTS) or not self._profile_verified:
            await self._refresh_panel_metadata(force=True)
        return self.api_profile or API_PROFILE_LEGACY

    @staticmethod
    def _is_legacy_client_endpoint(endpoint: str) -> bool:
        """True Р Т‘Р В»РЎРЏ РЎРѓРЎвЂљР В°РЎР‚РЎвЂ№РЎвЂ¦ client endpoints, Р С‘РЎРѓРЎвЂЎР ВµР В·Р Р…РЎС“Р Р†РЎв‚¬Р С‘РЎвЂ¦ Р Р† 3x-ui v3.1.0+."""
        if endpoint == "/panel/api/inbounds/addClient":
            return True
        if endpoint == "/panel/api/inbounds/onlines":
            return True
        if endpoint.startswith("/panel/api/inbounds/updateClient/"):
            return True
        if endpoint.startswith("/panel/api/inbounds/") and "/delClient/" in endpoint:
            return True
        if endpoint.startswith("/panel/api/inbounds/") and "/resetClientTraffic/" in endpoint:
            return True
        return False

    async def _raise_if_stale_legacy_profile(self, endpoint: str) -> None:
        """
        Р СџРЎР‚Р С‘ 404 Р Р…Р В° РЎРѓРЎвЂљР В°РЎР‚Р С•Р С client endpoint Р С—Р ВµРЎР‚Р ВµР С—РЎР‚Р С•Р Р†Р ВµРЎР‚РЎРЏР ВµРЎвЂљ Р С—РЎР‚Р С•РЎвЂћР С‘Р В»РЎРЉ API.

        Р вЂўРЎРѓР В»Р С‘ Р С—Р В°Р Р…Р ВµР В»РЎРЉ РЎС“Р В¶Р Вµ v3.1.0+ Р С‘ Р С—Р С•Р Т‘Р Т‘Р ВµРЎР‚Р В¶Р С‘Р Р†Р В°Р ВµРЎвЂљ clients_api, РЎвЂљР ВµР С”РЎС“РЎвЂ°Р С‘Р в„– Р В·Р В°Р С—РЎР‚Р С•РЎРѓ Р Р…Р ВµР В»РЎРЉР В·РЎРЏ
        РЎР‚Р ВµРЎвЂљРЎР‚Р В°Р С‘РЎвЂљРЎРЉ РЎвЂљР ВµР С Р В¶Р Вµ URL: Р Р†РЎвЂ№Р В·РЎвЂ№Р Р†Р В°РЎР‹РЎвЂ°Р В°РЎРЏ Р С•Р С—Р ВµРЎР‚Р В°РЎвЂ Р С‘РЎРЏ Р Т‘Р С•Р В»Р В¶Р Р…Р В° Р В·Р В°Р Р…Р С•Р Р†Р С• Р Р†РЎвЂ№Р В±РЎР‚Р В°РЎвЂљРЎРЉ endpoint.
        """
        if self.api_profile != API_PROFILE_LEGACY:
            return
        if not self._is_legacy_client_endpoint(endpoint):
            return

        old_version = self.panel_version or "unknown"
        logger.info(
            f"Legacy client endpoint Р Р†Р ВµРЎР‚Р Р…РЎС“Р В» 404 Р Р…Р В° {self.server['name']}; "
            f"Р С—Р ВµРЎР‚Р ВµР С—РЎР‚Р С•Р Р†Р ВµРЎР‚РЎРЏР ВµР С Р С—РЎР‚Р С•РЎвЂћР С‘Р В»РЎРЉ API Р С—Р В°Р Р…Р ВµР В»Р С‘"
        )
        await self._refresh_panel_metadata(force=True)
        if self.api_profile == API_PROFILE_CLIENTS:
            logger.info(
                f"Р СџР В°Р Р…Р ВµР В»РЎРЉ {self.server['name']} Р С—Р ВµРЎР‚Р ВµР С”Р В»РЎР‹РЎвЂЎР С‘Р В»Р В°РЎРѓРЎРЉ "
                f"{old_version}/{API_PROFILE_LEGACY} РІвЂ вЂ™ "
                f"{self.panel_version or 'unknown'}/{API_PROFILE_CLIENTS}; "
                f"Р С—Р С•Р Р†РЎвЂљР С•РЎР‚РЎРЏР ВµР С Р С•Р С—Р ВµРЎР‚Р В°РЎвЂ Р С‘РЎР‹ РЎвЂЎР ВµРЎР‚Р ВµР В· clients API"
            )
            raise StaleAPIProfileError("Р СџРЎР‚Р С•РЎвЂћР С‘Р В»РЎРЉ API Р С—Р В°Р Р…Р ВµР В»Р С‘ Р С‘Р В·Р СР ВµР Р…Р С‘Р В»РЎРѓРЎРЏ Р Р…Р В° clients_api")

    async def _run_with_stale_profile_retry(self, operation):
        """Р С›Р Т‘Р С‘Р Р… РЎР‚Р В°Р В· Р С—Р С•Р Р†РЎвЂљР С•РЎР‚РЎРЏР ВµРЎвЂљ Р С•Р С—Р ВµРЎР‚Р В°РЎвЂ Р С‘РЎР‹, Р ВµРЎРѓР В»Р С‘ 404 Р С—Р С•Р С”Р В°Р В·Р В°Р В» Р В°Р С—Р С–РЎР‚Р ВµР в„–Р Т‘ API Р С—РЎР‚Р С•РЎвЂћР С‘Р В»РЎРЏ."""
        try:
            return await operation()
        except StaleAPIProfileError:
            return await operation()

    async def _get_clients_api_record(self, email: str, log_error: bool = False) -> Optional[Dict[str, Any]]:
        """Р вЂ™Р С•Р В·Р Р†РЎР‚Р В°РЎвЂ°Р В°Р ВµРЎвЂљ Р В·Р В°Р С—Р С‘РЎРѓРЎРЉ Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР В° v3.1.0 Р С—Р С• email Р С‘Р В»Р С‘ None."""
        encoded_email = urllib.parse.quote(email, safe="")
        try:
            result = await self._request(
                "GET",
                f"/panel/api/clients/get/{encoded_email}",
                retry=False,
                log_error=log_error,
            )
        except VPNAPIError:
            return None
        obj = result.get("obj")
        return obj if isinstance(obj, dict) else None

    async def _find_panel_client(
        self,
        inbound_id: Optional[int] = None,
        client_uuid: Optional[str] = None,
        email: Optional[str] = None,
    ) -> tuple:
        """Р ВРЎвЂ°Р ВµРЎвЂљ Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР В° Р Р† /inbounds/list Р С‘ Р Р†Р С•Р В·Р Р†РЎР‚Р В°РЎвЂ°Р В°Р ВµРЎвЂљ (inbound, client)."""
        inbounds = await self.get_inbounds()
        for inbound in inbounds:
            if inbound_id is not None and inbound.get("id") != inbound_id:
                continue
            settings = self._load_json_field(inbound.get("settings", "{}"))
            for client in settings.get("clients", []):
                if email and client.get("email") == email:
                    return inbound, client
                if client_uuid and self._client_identifier_from_entry(client) == client_uuid:
                    return inbound, client
        return None, None
    
    async def _detect_panel_version(self) -> tuple:
        """
        Р С›Р С—РЎР‚Р ВµР Т‘Р ВµР В»РЎРЏР ВµРЎвЂљ Р Р†Р ВµРЎР‚РЎРѓР С‘РЎР‹ Р С—Р В°Р Р…Р ВµР В»Р С‘ РЎвЂЎР ВµРЎР‚Р ВµР В· probe GET /csrf-token.

        - HTTP 200 + JSON.obj РІвЂ вЂ™ v3.0+ (CSRF middleware Р В°Р С”РЎвЂљР С‘Р Р†Р ВµР Р…).
        - HTTP 404 РІвЂ вЂ™ v2.x (endpoint Р Р…Р Вµ РЎРѓРЎС“РЎвЂ°Р ВµРЎРѓРЎвЂљР Р†РЎС“Р ВµРЎвЂљ).
        - Р вЂєРЎР‹Р В±Р В°РЎРЏ Р Т‘РЎР‚РЎС“Р С–Р В°РЎРЏ Р С•РЎв‚¬Р С‘Р В±Р С”Р В° РІвЂ вЂ™ РЎРѓРЎвЂЎР С‘РЎвЂљР В°Р ВµР С legacy (Р В±Р ВµР В·Р С•Р С—Р В°РЎРѓР Р…РЎвЂ№Р в„– РЎвЂћР С•Р В»Р В±РЎРЊР С”).

        Р вЂ”Р В°Р С—РЎР‚Р С•РЎРѓ Р С‘Р Т‘РЎвЂРЎвЂљ Р Р…Р В°Р С—РЎР‚РЎРЏР СРЎС“РЎР‹ РЎвЂЎР ВµРЎР‚Р ВµР В· session, Р В±Р ВµР В· _request, РЎвЂЎРЎвЂљР С•Р В±РЎвЂ№ Р Р…Р Вµ Р В·Р В°РЎвЂ Р С‘Р С”Р В»Р С‘РЎвЂљРЎРЉРЎРѓРЎРЏ.

        Returns:
            Р С™Р С•РЎР‚РЎвЂљР ВµР В¶ (mode, csrf_token): ('csrf', '<token>') Р С‘Р В»Р С‘ ('legacy', None).
        """
        session = await self._ensure_session()
        url = f"{self.base_url}/csrf-token"
        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    try:
                        data = await resp.json()
                        token = data.get('obj') if isinstance(data, dict) else None
                        if isinstance(token, str) and token:
                            logger.info(f"Р С›Р В±Р Р…Р В°РЎР‚РЎС“Р В¶Р ВµР Р…Р В° 3x-ui v3.0+ Р Р…Р В° {self.server['name']} (CSRF Р В°Р С”РЎвЂљР С‘Р Р†Р ВµР Р…)")
                            return ('csrf', token)
                    except (json.JSONDecodeError, aiohttp.ContentTypeError):
                        pass
                # 404 Р С‘Р В»Р С‘ Р С—РЎР‚Р С•РЎвЂЎР ВµР Вµ РІР‚вЂќ РЎРѓРЎвЂЎР С‘РЎвЂљР В°Р ВµР С v2.x
                logger.debug(f"Probe /csrf-token Р Р†Р ВµРЎР‚Р Р…РЎС“Р В» {resp.status}, РЎРѓРЎвЂЎР С‘РЎвЂљР В°Р ВµР С v2.x legacy РЎР‚Р ВµР В¶Р С‘Р С")
                return ('legacy', None)
        except aiohttp.ClientError as e:
            logger.debug(f"Probe /csrf-token РЎС“Р С—Р В°Р В» ({e}), РЎРѓРЎвЂЎР С‘РЎвЂљР В°Р ВµР С v2.x legacy РЎР‚Р ВµР В¶Р С‘Р С")
            return ('legacy', None)

    async def _fetch_api_token(self) -> Optional[str]:
        """
        Р СћРЎРЏР Р…Р ВµРЎвЂљ Bearer-РЎвЂљР С•Р С”Р ВµР Р… РЎРѓ Р С—Р В°Р Р…Р ВµР В»Р С‘ v3.0+.

        Р СњР В° v3.0.2+/v3.1.0 Р С‘РЎРѓР С—Р С•Р В»РЎРЉР В·РЎС“Р ВµРЎвЂљ /panel/setting/apiTokens:
        - Р В±Р ВµРЎР‚РЎвЂРЎвЂљ enabled token РЎРѓ Р С‘Р СР ВµР Р…Р ВµР С YadrenoVPN Bot;
        - Р ВµРЎРѓР В»Р С‘ РЎвЂљР С•Р С”Р ВµР Р…Р В° Р Р…Р ВµРЎвЂљ, РЎРѓР С•Р В·Р Т‘Р В°РЎвЂРЎвЂљ Р ВµР С–Р С•;
        - Р ВµРЎРѓР В»Р С‘ РЎвЂљР С•Р С”Р ВµР Р… Р Р…Р В°Р в„–Р Т‘Р ВµР Р… disabled, Р Р…Р Вµ Р Р†Р С”Р В»РЎР‹РЎвЂЎР В°Р ВµРЎвЂљ Р ВµР С–Р С• Р С•Р В±РЎР‚Р В°РЎвЂљР Р…Р С• Р С‘ Р С•РЎРѓРЎвЂљР В°РЎвЂРЎвЂљРЎРѓРЎРЏ CSRF.

        Р СњР В° v3.0.0 Р С—Р В°Р Т‘Р В°Р ВµРЎвЂљ Р С•Р В±РЎР‚Р В°РЎвЂљР Р…Р С• Р Р…Р В° РЎРѓРЎвЂљР В°РЎР‚РЎвЂ№Р в„– /panel/setting/getApiToken.

        Returns:
            Р СћР С•Р С”Р ВµР Р… Р С‘Р В»Р С‘ None Р ВµРЎРѓР В»Р С‘ Р С—Р С•Р В»РЎС“РЎвЂЎР С‘РЎвЂљРЎРЉ Р Р…Р Вµ РЎС“Р Т‘Р В°Р В»Р С•РЎРѓРЎРЉ.
        """
        if self.csrf_token is None:
            logger.debug("Р СњР ВµР Р†Р С•Р В·Р СР С•Р В¶Р Р…Р С• Р Р†РЎвЂ№РЎвЂљРЎРЏР Р…РЎС“РЎвЂљРЎРЉ api_token: csrf_token Р Р…Р Вµ РЎС“РЎРѓРЎвЂљР В°Р Р…Р С•Р Р†Р В»Р ВµР Р…")
            return None

        headers = self._build_headers("GET", force_cookie=True, include_csrf_for_get=True)

        # Р СњР С•Р Р†РЎвЂ№Р в„– API РЎвЂљР С•Р С”Р ВµР Р…Р С•Р Р† Р С—Р С•РЎРЏР Р†Р С‘Р В»РЎРѓРЎРЏ Р С—Р С•РЎРѓР В»Р Вµ v3.0.0 Р С‘ Р В°Р С”РЎвЂљРЎС“Р В°Р В»Р ВµР Р… Р Т‘Р В»РЎРЏ v3.1.0+.
        status, data = await self._raw_json_request(
            "GET",
            "/panel/setting/apiTokens",
            headers=headers,
        )
        if status == 200 and isinstance(data, dict) and data.get("success"):
            rows = data.get("obj") or []
            if isinstance(rows, dict):
                rows = rows.get("items") or rows.get("rows") or rows.get("tokens") or []
            if isinstance(rows, list):
                for row in rows:
                    if not isinstance(row, dict) or row.get("name") != BOT_API_TOKEN_NAME:
                        continue
                    enabled = row.get("enabled", row.get("isEnabled", True))
                    if enabled is False or enabled == 0:
                        self.api_token_diagnostic = (
                            f"API-РЎвЂљР С•Р С”Р ВµР Р… '{BOT_API_TOKEN_NAME}' Р Р…Р В°Р в„–Р Т‘Р ВµР Р…, Р Р…Р С• Р С•РЎвЂљР С”Р В»РЎР‹РЎвЂЎРЎвЂР Р… Р Р† Р С—Р В°Р Р…Р ВµР В»Р С‘. "
                            "Р вЂР С•РЎвЂљ Р С•РЎРѓРЎвЂљР В°РЎвЂРЎвЂљРЎРѓРЎРЏ Р Р† РЎР‚Р ВµР В¶Р С‘Р СР Вµ cookie+CSRF."
                        )
                        logger.warning(self.api_token_diagnostic)
                        return None
                    token = row.get("token") or row.get("apiToken")
                    if isinstance(token, str) and token:
                        self._save_api_token(token)
                        return token

            create_headers = self._build_headers("POST", force_cookie=True, include_csrf_for_get=True)
            status, data = await self._raw_json_request(
                "POST",
                "/panel/setting/apiTokens/create",
                data={"name": BOT_API_TOKEN_NAME},
                headers=create_headers,
            )
            if status == 200 and isinstance(data, dict) and data.get("success"):
                obj = data.get("obj")
                if isinstance(obj, dict):
                    token = obj.get("token") or obj.get("apiToken")
                    if isinstance(token, str) and token:
                        self._save_api_token(token)
                        return token
                token = data.get("obj")
                if isinstance(token, str) and token:
                    self._save_api_token(token)
                    return token
            logger.debug(f"Р СњР Вµ РЎС“Р Т‘Р В°Р В»Р С•РЎРѓРЎРЉ РЎРѓР С•Р В·Р Т‘Р В°РЎвЂљРЎРЉ api_token РЎвЂЎР ВµРЎР‚Р ВµР В· /apiTokens/create: HTTP {status}, data={data}")
            return None

        if status not in (0, 404, 405):
            logger.debug(f"GET /panel/setting/apiTokens Р Р†Р ВµРЎР‚Р Р…РЎС“Р В» HTTP {status}, fallback getApiToken")

        # Р РЋРЎвЂљР В°РЎР‚РЎвЂ№Р в„– endpoint v3.0.0.
        headers = self._build_headers("GET", force_cookie=True, include_csrf_for_get=True)
        try:
            status, data = await self._raw_json_request(
                "GET",
                "/panel/setting/getApiToken",
                headers=headers,
            )
            if status != 200:
                logger.debug(f"GET /panel/setting/getApiToken Р Р†Р ВµРЎР‚Р Р…РЎС“Р В» {status}")
                return None
            if not isinstance(data, dict) or not data.get('success'):
                return None
            token = data.get('obj')
            if not isinstance(token, str) or not token:
                return None
            self._save_api_token(token)
            return token
        except Exception as e:
            logger.debug(f"Р С›РЎв‚¬Р С‘Р В±Р С”Р В° Р С—РЎР‚Р С‘ Р Р†РЎвЂ№РЎвЂљРЎРЏР С–Р С‘Р Р†Р В°Р Р…Р С‘Р С‘ api_token: {e}")
            return None

    async def _try_bearer_validate(self) -> bool:
        """
        Р вЂєРЎвЂР С–Р С”Р С‘Р в„– probe-Р В·Р В°Р С—РЎР‚Р С•РЎРѓ Р Т‘Р В»РЎРЏ Р С—РЎР‚Р С•Р Р†Р ВµРЎР‚Р С”Р С‘ Р В°Р С”РЎвЂљРЎС“Р В°Р В»РЎРЉР Р…Р С•РЎРѓРЎвЂљР С‘ Bearer-РЎвЂљР С•Р С”Р ВµР Р…Р В°.

        Р вЂќР ВµР В»Р В°Р ВµРЎвЂљ GET /panel/api/server/status РЎРѓ Authorization: Bearer.
        - 200 РІвЂ вЂ™ РЎвЂљР С•Р С”Р ВµР Р… Р Р†Р В°Р В»Р С‘Р Т‘Р ВµР Р…, Р С—Р ВµРЎР‚Р ВµРЎвЂ¦Р С•Р Т‘Р С‘Р С Р Р† РЎР‚Р ВµР В¶Р С‘Р С 'bearer'.
        - 404/401 РІвЂ вЂ™ РЎвЂљР С•Р С”Р ВµР Р… Р Р…Р ВµР Р†Р В°Р В»Р С‘Р Т‘Р ВµР Р… (РЎР‚Р С•РЎвЂљР С‘РЎР‚Р С•Р Р†Р В°Р В»Р С‘ Р Р† Р С—Р В°Р Р…Р ВµР В»Р С‘).
        - Р СџРЎР‚Р С•РЎвЂЎР ВµР Вµ РІвЂ вЂ™ РЎРѓРЎвЂЎР С‘РЎвЂљР В°Р ВµР С Р Р…Р ВµР Р†Р В°Р В»Р С‘Р Т‘Р Р…РЎвЂ№Р С.

        Returns:
            True Р ВµРЎРѓР В»Р С‘ РЎвЂљР С•Р С”Р ВµР Р… РЎР‚Р В°Р В±Р С•РЎвЂљР В°Р ВµРЎвЂљ.
        """
        if not self.api_token:
            return False
        headers = {
            "Accept": "application/json",
            "X-Requested-With": "XMLHttpRequest",
            "Authorization": f"Bearer {self.api_token}",
        }
        status, _ = await self._raw_json_request(
            "GET",
            "/panel/api/server/status",
            headers=headers,
        )
        if status == 200:
            return True
        logger.info(f"Bearer-РЎвЂљР С•Р С”Р ВµР Р… Р Р…Р ВµР Р†Р В°Р В»Р С‘Р Т‘Р ВµР Р… (HTTP {status}), Р Р…РЎС“Р В¶Р Р…Р С• Р С•Р В±Р Р…Р С•Р Р†Р С‘РЎвЂљРЎРЉ")
        return False

    def _build_headers(
        self,
        method: str,
        force_cookie: bool = False,
        include_csrf_for_get: bool = False,
    ) -> Dict[str, str]:
        """
        Р РЋР С•Р В±Р С‘РЎР‚Р В°Р ВµРЎвЂљ HTTP-Р В·Р В°Р С–Р С•Р В»Р С•Р Р†Р С”Р С‘ Р Р† Р В·Р В°Р Р†Р С‘РЎРѓР С‘Р СР С•РЎРѓРЎвЂљР С‘ Р С•РЎвЂљ panel_mode.

        - legacy: РЎвЂљР С•Р В»РЎРЉР С”Р С• Р В±Р В°Р В·Р С•Р Р†РЎвЂ№Р Вµ AJAX-Р В·Р В°Р С–Р С•Р В»Р С•Р Р†Р С”Р С‘.
        - csrf: Р Т‘Р С•Р В±Р В°Р Р†Р В»РЎРЏР ВµРЎвЂљ X-CSRF-Token Р Т‘Р В»РЎРЏ unsafe-Р СР ВµРЎвЂљР С•Р Т‘Р С•Р Р†.
        - bearer: Р Т‘Р С•Р В±Р В°Р Р†Р В»РЎРЏР ВµРЎвЂљ Authorization: Bearer (CSRF Р Р…Р Вµ Р Р…РЎС“Р В¶Р ВµР Р…).
        - force_cookie: Р Т‘Р В»РЎРЏ /panel/setting/* Bearer Р Р…Р Вµ Р С—Р С•Р Т‘РЎвЂ¦Р С•Р Т‘Р С‘РЎвЂљ, Р Р…РЎС“Р В¶Р ВµР Р… cookie+CSRF.
        """
        headers = {
            "Accept": "application/json",
            "X-Requested-With": "XMLHttpRequest",
        }
        if not force_cookie and self.panel_mode == 'bearer' and self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        elif self.csrf_token and (
            include_csrf_for_get or method.upper() not in ('GET', 'HEAD', 'OPTIONS')
        ):
            headers["X-CSRF-Token"] = self.csrf_token
        return headers

    async def _request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Dict] = None,
        retry: bool = True,
        log_error: bool = True
    ) -> Dict[str, Any]:
        """
        Р вЂ™РЎвЂ№Р С—Р С•Р В»Р Р…РЎРЏР ВµРЎвЂљ HTTP-Р В·Р В°Р С—РЎР‚Р С•РЎРѓ Р С” API.
        
        Args:
            method: HTTP Р СР ВµРЎвЂљР С•Р Т‘ (GET, POST)
            endpoint: Р С›РЎвЂљР Р…Р С•РЎРѓР С‘РЎвЂљР ВµР В»РЎРЉР Р…РЎвЂ№Р в„– Р С—РЎС“РЎвЂљРЎРЉ (Р Р…Р В°РЎвЂЎР С‘Р Р…Р В°Р ВµРЎвЂљРЎРѓРЎРЏ РЎРѓ /panel/... Р С‘Р В»Р С‘ /login)
            data: Р вЂќР В°Р Р…Р Р…РЎвЂ№Р Вµ Р Т‘Р В»РЎРЏ POST Р В·Р В°Р С—РЎР‚Р С•РЎРѓР В°
            retry: Р СџР С•Р Р†РЎвЂљР С•РЎР‚РЎРЏРЎвЂљРЎРЉ Р В»Р С‘ Р С—РЎР‚Р С‘ Р С•РЎв‚¬Р С‘Р В±Р С”Р В°РЎвЂ¦
            
        Returns:
            Р С›РЎвЂљР Р†Р ВµРЎвЂљ API Р Р† Р Р†Р С‘Р Т‘Р Вµ РЎРѓР В»Р С•Р Р†Р В°РЎР‚РЎРЏ
            
        Raises:
            VPNAPIError: Р СџРЎР‚Р С‘ Р С•РЎв‚¬Р С‘Р В±Р С”Р Вµ Р В·Р В°Р С—РЎР‚Р С•РЎРѓР В°
        """
        # URL = https://ip:port/secret_path/panel/...
        url = f"{self.base_url}{endpoint}"

        attempts = RETRY_CONFIG["max_attempts"] if retry else 1
        delays = RETRY_CONFIG["delays"]
        is_setting_route = endpoint.startswith("/panel/setting/")

        for attempt in range(attempts):
            try:
                # Р СџР С•Р В»РЎС“РЎвЂЎР В°Р ВµР С Р В°Р С”РЎвЂљРЎС“Р В°Р В»РЎРЉР Р…РЎС“РЎР‹ РЎРѓР ВµРЎРѓРЎРѓР С‘РЎР‹ (Р Р†Р В°Р В¶Р Р…Р С•, РЎвЂљР В°Р С” Р С”Р В°Р С” Р С•Р Р…Р В° Р СР С•Р В¶Р ВµРЎвЂљ Р В±РЎвЂ№РЎвЂљРЎРЉ Р С—Р ВµРЎР‚Р ВµРЎРѓР С•Р В·Р Т‘Р В°Р Р…Р В° Р Р† _reset_session)
                session = await self._ensure_session()

                # Р вЂўРЎРѓР В»Р С‘ Р Р…РЎС“Р В¶Р Р…Р В° Р В°Р Р†РЎвЂљР С•РЎР‚Р С‘Р В·Р В°РЎвЂ Р С‘РЎРЏ Р С‘ Р СРЎвЂ№ Р Р…Р Вµ Р В°Р Р†РЎвЂљР С•РЎР‚Р С‘Р В·Р С•Р Р†Р В°Р Р…РЎвЂ№ (Р С‘ РЎРЊРЎвЂљР С• Р Р…Р Вµ Р В·Р В°Р С—РЎР‚Р С•РЎРѓ Р В»Р С•Р С–Р С‘Р Р…Р В°)
                if not self.is_authenticated and endpoint != "/login":
                    await self.login()

                if is_setting_route and endpoint != "/login":
                    await self._ensure_cookie_auth()

                # Р вЂ”Р В°Р С–Р С•Р В»Р С•Р Р†Р С”Р С‘ РЎРѓР С•Р В±Р С‘РЎР‚Р В°РЎР‹РЎвЂљРЎРѓРЎРЏ Р СџР С›Р РЋР вЂєР вЂў login() РІР‚вЂќ РЎвЂљР В°Р С Р С•Р С—РЎР‚Р ВµР Т‘Р ВµР В»РЎРЏР ВµРЎвЂљРЎРѓРЎРЏ panel_mode
                # Р С‘ РЎС“РЎРѓРЎвЂљР В°Р Р…Р В°Р Р†Р В»Р С‘Р Р†Р В°РЎР‹РЎвЂљРЎРѓРЎРЏ csrf_token/api_token, Р Р…РЎС“Р В¶Р Р…РЎвЂ№Р Вµ Р Т‘Р В»РЎРЏ _build_headers.
                headers = self._build_headers(
                    method,
                    force_cookie=is_setting_route,
                    include_csrf_for_get=is_setting_route,
                )

                logger.debug(f"API Р В·Р В°Р С—РЎР‚Р С•РЎРѓ: {method} {url} (mode={self.panel_mode})")

                async with session.request(method, url, json=data, headers=headers) as response:
                    text = await response.text()

                    # Bearer Р С—РЎР‚Р С•РЎвЂљРЎС“РЎвЂ¦ (РЎР‚Р С•РЎвЂљР С‘РЎР‚Р С•Р Р†Р В°Р В»Р С‘ Р Р† Р С—Р В°Р Р…Р ВµР В»Р С‘) РІР‚вЂќ Р С•Р В±Р Р…РЎС“Р В»РЎРЏР ВµР С РЎвЂљР С•Р С”Р ВµР Р…, Р С—Р ВµРЎР‚Р ВµР В»Р С•Р С–Р С‘Р Р…Р С‘Р Р†Р В°Р ВµР СРЎРѓРЎРЏ
                    if response.status == 401 and self.panel_mode == 'bearer' and not is_setting_route:
                        logger.warning(
                            f"HTTP 401 Р Р† РЎР‚Р ВµР В¶Р С‘Р СР Вµ bearer РІР‚вЂќ РЎвЂљР С•Р С”Р ВµР Р… Р Р…Р ВµР Р†Р В°Р В»Р С‘Р Т‘Р ВµР Р…, "
                            f"Р С—Р ВµРЎР‚Р ВµР С”Р В»РЎР‹РЎвЂЎР В°Р ВµР СРЎРѓРЎРЏ Р Р…Р В° Р С•Р В±РЎвЂ№РЎвЂЎР Р…РЎвЂ№Р в„– Р В»Р С•Р С–Р С‘Р Р…"
                        )
                        await self._invalidate_api_token()
                        await self._reset_session()
                        if attempt < attempts - 1:
                            continue

                    # CSRF-РЎвЂљР С•Р С”Р ВµР Р… РЎС“РЎРѓРЎвЂљР В°РЎР‚Р ВµР В» (РЎР‚Р ВµРЎРѓРЎвЂљР В°РЎР‚РЎвЂљ Р С—Р В°Р Р…Р ВµР В»Р С‘ Р С‘ РЎвЂљ.Р С—.) РІР‚вЂќ Р С—Р ВµРЎР‚Р ВµР С—Р С•Р Т‘РЎвЂљРЎРЏР Р…РЎС“РЎвЂљРЎРЉ Р С‘ Р С—Р С•Р Р†РЎвЂљР С•РЎР‚Р С‘РЎвЂљРЎРЉ
                    if response.status == 403 and (self.panel_mode == 'csrf' or is_setting_route):
                        logger.info("HTTP 403 РІР‚вЂќ Р С—Р ВµРЎР‚Р ВµР С—Р С•Р Т‘РЎвЂљРЎРЏР С–Р С‘Р Р†Р В°Р ВµР С CSRF-РЎвЂљР С•Р С”Р ВµР Р…")
                        mode, token = await self._detect_panel_version()
                        if mode == 'csrf':
                            self.csrf_token = token
                            if attempt < attempts - 1:
                                continue

                    # Р С›Р В±РЎР‚Р В°Р В±Р С•РЎвЂљР С”Р В° РЎРѓРЎвЂљР В°РЎвЂљРЎС“РЎРѓР С•Р Р†
                    if response.status == 200:
                        try:
                            result = json.loads(text)
                            if result.get("success"):
                                return result
                            
                            # Р вЂРЎвЂ№Р Р†Р В°Р ВµРЎвЂљ success=False Р Р…Р С• Р ВµРЎРѓРЎвЂљРЎРЉ msg
                            if "msg" in result and not result["success"]:
                                msg = result["msg"].lower()
                                # Р СџРЎР‚Р С•Р Р†Р ВµРЎР‚РЎРЏР ВµР С Р Р…Р В° Р С—РЎР‚Р С‘Р В·Р Р…Р В°Р С”Р С‘ Р С‘РЎРѓРЎвЂљР ВµРЎвЂЎР ВµР Р…Р С‘РЎРЏ РЎРѓР ВµРЎРѓРЎРѓР С‘Р С‘
                                if any(x in msg for x in ["login", "auth", "session", "token"]):
                                    logger.warning(f"Р РЋР ВµРЎРѓРЎРѓР С‘РЎРЏ Р Р†Р С•Р В·Р СР С•Р В¶Р Р…Р С• Р С‘РЎРѓРЎвЂљР ВµР С”Р В»Р В° (msg='{result['msg']}'), Р С—Р ВµРЎР‚Р ВµРЎРѓР С•Р В·Р Т‘Р В°РЎвЂР С...")
                                    await self._reset_session()
                                    if attempt < attempts - 1:
                                        # Р РЋР ВµРЎРѓРЎРѓР С‘РЎРЏ Р В±РЎС“Р Т‘Р ВµРЎвЂљ Р С—Р ВµРЎР‚Р ВµРЎРѓР С•Р В·Р Т‘Р В°Р Р…Р В° Р С—РЎР‚Р С‘ РЎРѓР В»Р ВµР Т‘РЎС“РЎР‹РЎвЂ°Р ВµР С Р В·Р В°Р С—РЎР‚Р С•РЎРѓР Вµ
                                        continue
                                        
                                raise VPNAPIError(result["msg"])
                            return result
                        except json.JSONDecodeError:
                            # Р ВР Р…Р С•Р С–Р Т‘Р В° Р Р†Р С•Р В·Р Р†РЎР‚Р В°РЎвЂ°Р В°Р ВµРЎвЂљ HTML Р С—РЎР‚Р С‘ РЎР‚Р ВµР Т‘Р С‘РЎР‚Р ВµР С”РЎвЂљР Вµ Р Р…Р В° Р В»Р С•Р С–Р С‘Р Р…
                            if "login" in text.lower():
                                logger.warning("Р РЋР ВµРЎРѓРЎРѓР С‘РЎРЏ Р С‘РЎРѓРЎвЂљР ВµР С”Р В»Р В° (РЎР‚Р ВµР Т‘Р С‘РЎР‚Р ВµР С”РЎвЂљ Р Р…Р В° Р В»Р С•Р С–Р С‘Р Р…), Р С—Р ВµРЎР‚Р ВµРЎРѓР С•Р В·Р Т‘Р В°РЎвЂР С...")
                                await self._reset_session()
                                if attempt < attempts - 1:
                                    # Р РЋР ВµРЎРѓРЎРѓР С‘РЎРЏ Р В±РЎС“Р Т‘Р ВµРЎвЂљ Р С—Р ВµРЎР‚Р ВµРЎРѓР С•Р В·Р Т‘Р В°Р Р…Р В° Р С—РЎР‚Р С‘ РЎРѓР В»Р ВµР Т‘РЎС“РЎР‹РЎвЂ°Р ВµР С Р В·Р В°Р С—РЎР‚Р С•РЎРѓР Вµ
                                    continue
                            logger.error(f"Р СњР ВµР Р†Р В°Р В»Р С‘Р Т‘Р Р…РЎвЂ№Р в„– JSON: {text[:100]}")
                            raise VPNAPIError("Р СњР ВµР С”Р С•РЎР‚РЎР‚Р ВµР С”РЎвЂљР Р…РЎвЂ№Р в„– Р С•РЎвЂљР Р†Р ВµРЎвЂљ РЎРѓР ВµРЎР‚Р Р†Р ВµРЎР‚Р В°")
                    elif response.status == 404:
                         await self._raise_if_stale_legacy_profile(endpoint)
                         # Р СњР ВµР С”Р С•РЎвЂљР С•РЎР‚РЎвЂ№Р Вµ Р Р†Р ВµРЎР‚РЎРѓР С‘Р С‘ X-UI Р Р†Р С•Р В·Р Р†РЎР‚Р В°РЎвЂ°Р В°РЎР‹РЎвЂљ 404 Р ВµРЎРѓР В»Р С‘ РЎРѓР ВµРЎРѓРЎРѓР С‘РЎРЏ Р С‘РЎРѓРЎвЂљР ВµР С”Р В»Р В°
                         # Р СџРЎвЂ№РЎвЂљР В°Р ВµР СРЎРѓРЎРЏ Р С—Р ВµРЎР‚Р ВµРЎРѓР С•Р В·Р Т‘Р В°РЎвЂљРЎРЉ РЎРѓР ВµРЎРѓРЎРѓР С‘РЎР‹
                         logger.warning(f"HTTP 404 (Endpoint not found) Р Т‘Р В»РЎРЏ {url}, РЎРѓР ВµРЎРѓРЎРѓР С‘РЎРЏ Р Р†Р С•Р В·Р СР С•Р В¶Р Р…Р С• Р С‘РЎРѓРЎвЂљР ВµР С”Р В»Р В°. Р СџР С•Р С—РЎвЂ№РЎвЂљР С”Р В° {attempt+1}/{attempts}")
                         await self._reset_session()
                         if attempt < attempts - 1:
                             continue
                         
                         if log_error:
                             logger.error(f"Endpoint not found Р С—Р С•РЎРѓР В»Р Вµ {attempts} Р С—Р С•Р С—РЎвЂ№РЎвЂљР С•Р С”: {url}")
                         raise VPNAPIError("Р С›РЎв‚¬Р С‘Р В±Р С”Р В° API: Р СљР ВµРЎвЂљР С•Р Т‘ Р Р…Р Вµ Р Р…Р В°Р в„–Р Т‘Р ВµР Р… (404). Р СџРЎР‚Р С•Р Р†Р ВµРЎР‚РЎРЉРЎвЂљР Вµ Р Р…Р В°РЎРѓРЎвЂљРЎР‚Р С•Р в„–Р С”Р С‘ РЎРѓР ВµРЎР‚Р Р†Р ВµРЎР‚Р В°.")
                    elif response.status == 401:
                        logger.warning("HTTP 401, Р С—Р ВµРЎР‚Р ВµРЎРѓР С•Р В·Р Т‘Р В°РЎвЂР С РЎРѓР ВµРЎРѓРЎРѓР С‘РЎР‹...")
                        await self._reset_session()
                        if attempt < attempts - 1:
                            continue
                    
                    raise VPNAPIError(f"HTTP {response.status}: {text[:100]}")
                    
            except aiohttp.ClientError as e:
                logger.warning(f"Р С›РЎв‚¬Р С‘Р В±Р С”Р В° Р С—Р С•Р Т‘Р С”Р В»РЎР‹РЎвЂЎР ВµР Р…Р С‘РЎРЏ (Р С—Р С•Р С—РЎвЂ№РЎвЂљР С”Р В° {attempt+1}): {e}")
                # Р РЋР В±РЎР‚Р В°РЎРѓРЎвЂ№Р Р†Р В°Р ВµР С РЎРѓР ВµРЎРѓРЎРѓР С‘РЎР‹ Р С—РЎР‚Р С‘ Р С•РЎв‚¬Р С‘Р В±Р С”Р В°РЎвЂ¦ Р С—Р С•Р Т‘Р С”Р В»РЎР‹РЎвЂЎР ВµР Р…Р С‘РЎРЏ, РЎвЂЎРЎвЂљР С•Р В±РЎвЂ№ Р С—Р ВµРЎР‚Р ВµРЎРѓР С•Р В·Р Т‘Р В°РЎвЂљРЎРЉ Р ВµРЎвЂ
                await self._reset_session()
                if attempt < attempts - 1:
                    await asyncio.sleep(delays[attempt])
                else:
                    raise VPNAPIError(f"Р С›РЎв‚¬Р С‘Р В±Р С”Р В° Р С—Р С•Р Т‘Р С”Р В»РЎР‹РЎвЂЎР ВµР Р…Р С‘РЎРЏ: {e}")
            except StaleAPIProfileError:
                raise
            except VPNAPIError:
                raise
            except Exception as e:
                logger.error(f"Р СњР ВµР С•Р В¶Р С‘Р Т‘Р В°Р Р…Р Р…Р В°РЎРЏ Р С•РЎв‚¬Р С‘Р В±Р С”Р В°: {e}")
                raise VPNAPIError(f"Р СњР ВµР С•Р В¶Р С‘Р Т‘Р В°Р Р…Р Р…Р В°РЎРЏ Р С•РЎв‚¬Р С‘Р В±Р С”Р В°: {e}")
        
        raise VPNAPIError("Р СџРЎР‚Р ВµР Р†РЎвЂ№РЎв‚¬Р ВµР Р…Р С• Р С”Р С•Р В»Р С‘РЎвЂЎР ВµРЎРѓРЎвЂљР Р†Р С• Р С—Р С•Р С—РЎвЂ№РЎвЂљР С•Р С”")

    async def _login_with_cookie(self, fetch_token: bool = True) -> bool:
        """
        Р С›Р В±РЎвЂ№РЎвЂЎР Р…РЎвЂ№Р в„– login РЎвЂЎР ВµРЎР‚Р ВµР В· cookie. Р вЂќР В»РЎРЏ v3.0+ Р Т‘Р С•Р В±Р В°Р Р†Р В»РЎРЏР ВµРЎвЂљ CSRF.

        fetch_token=True Р С‘РЎРѓР С—Р С•Р В»РЎРЉР В·РЎС“Р ВµРЎвЂљРЎРѓРЎРЏ Р С•РЎРѓР Р…Р С•Р Р†Р Р…РЎвЂ№Р С login(), РЎвЂЎРЎвЂљР С•Р В±РЎвЂ№ Р С—Р С•РЎРѓР В»Р Вµ cookie-Р В»Р С•Р С–Р С‘Р Р…Р В°
        Р С—Р С•Р В»РЎС“РЎвЂЎР С‘РЎвЂљРЎРЉ Bearer. Р вЂќР В»РЎРЏ /panel/setting/* fetch_token=False, РЎвЂЎРЎвЂљР С•Р В±РЎвЂ№ Р Р…Р Вµ Р Р†РЎвЂ№Р В·Р Р†Р В°РЎвЂљРЎРЉ
        РЎР‚Р ВµР С”РЎС“РЎР‚РЎРѓР С‘РЎР‹ Р С—РЎР‚Р С‘ Р С•Р В±РЎРѓР В»РЎС“Р В¶Р С‘Р Р†Р В°Р Р…Р С‘Р С‘ setting routes.
        """
        mode, csrf_token = await self._detect_panel_version()
        self.panel_mode = mode
        self.auth_mode = mode
        self.csrf_token = csrf_token

        session = await self._ensure_session()
        url = f"{self.base_url}/login"
        login_headers = {
            "Accept": "application/json",
            "X-Requested-With": "XMLHttpRequest",
        }
        if mode == 'csrf' and csrf_token:
            login_headers["X-CSRF-Token"] = csrf_token

        try:
            async with session.post(
                url,
                json={
                    "username": self.server["login"],
                    "password": self.server["password"],
                },
                headers=login_headers,
            ) as resp:
                text = await resp.text()
                if resp.status == 200:
                    data = json.loads(text)
                    if data.get("success"):
                        self.is_authenticated = True
                        self.cookie_authenticated = True
                        logger.info(f"РІСљвЂ¦ Р Р€РЎРѓР С—Р ВµРЎв‚¬Р Р…Р В°РЎРЏ Р В°Р Р†РЎвЂљР С•РЎР‚Р С‘Р В·Р В°РЎвЂ Р С‘РЎРЏ Р Р…Р В° {self.server['name']} (РЎР‚Р ВµР В¶Р С‘Р С={mode})")
                    else:
                        raise VPNAPIError(f"Р С›РЎв‚¬Р С‘Р В±Р С”Р В° Р В»Р С•Р С–Р С‘Р Р…Р В°: {data.get('msg')}")
                elif resp.status == 404:
                    raise VPNAPIError(f"Р СџР В°Р Р…Р ВµР В»РЎРЉ Р Р…Р ВµР Т‘Р С•РЎРѓРЎвЂљРЎС“Р С—Р Р…Р В° Р С—Р С• Р С—РЎС“РЎвЂљР С‘ {self.server['web_base_path']}")
                elif resp.status == 403:
                    raise VPNAPIError("Р С›РЎв‚¬Р С‘Р В±Р С”Р В° CSRF Р С—РЎР‚Р С‘ Р В»Р С•Р С–Р С‘Р Р…Р Вµ (HTTP 403). Р вЂ™Р С•Р В·Р СР С•Р В¶Р Р…Р С•, Р С—Р В°Р Р…Р ВµР В»РЎРЉ v3.0+ РЎвЂљРЎР‚Р ВµР В±РЎС“Р ВµРЎвЂљ X-CSRF-Token")
                else:
                    raise VPNAPIError(f"HTTP {resp.status} Р С—РЎР‚Р С‘ Р В»Р С•Р С–Р С‘Р Р…Р Вµ")
        except aiohttp.ClientConnectorError:
            raise VPNAPIError(
                f"Р СњР Вµ РЎС“Р Т‘Р В°Р В»Р С•РЎРѓРЎРЉ Р С—Р С•Р Т‘Р С”Р В»РЎР‹РЎвЂЎР С‘РЎвЂљРЎРЉРЎРѓРЎРЏ Р С” {self.server.get('protocol', 'https')}://"
                f"{self.server['host']}:{self.server['port']}"
            )
        except asyncio.TimeoutError:
            raise VPNAPIError("Р СћР В°Р в„–Р СР В°РЎС“РЎвЂљ Р С—РЎР‚Р С‘ Р В»Р С•Р С–Р С‘Р Р…Р Вµ")
        except json.JSONDecodeError:
            raise VPNAPIError("Р СњР ВµР С”Р С•РЎР‚РЎР‚Р ВµР С”РЎвЂљР Р…РЎвЂ№Р в„– Р С•РЎвЂљР Р†Р ВµРЎвЂљ Р С—РЎР‚Р С‘ Р В»Р С•Р С–Р С‘Р Р…Р Вµ")

        if mode == 'csrf' and fetch_token:
            token = await self._fetch_api_token()
            if token:
                self.panel_mode = 'bearer'
                self.auth_mode = 'bearer'
                logger.info(
                    f"СЂСџвЂќвЂ Р вЂ™РЎвЂ№РЎвЂљРЎРЏР Р…РЎС“РЎвЂљ api_token РЎРѓ {self.server['name']}, "
                    f"Р С—Р ВµРЎР‚Р ВµР С”Р В»РЎР‹РЎвЂЎР В°Р ВµР СРЎРѓРЎРЏ Р Р…Р В° Bearer-РЎР‚Р ВµР В¶Р С‘Р С (v3.0+)"
                )
            else:
                logger.info(
                    f"Р СњР Вµ РЎС“Р Т‘Р В°Р В»Р С•РЎРѓРЎРЉ Р Р†РЎвЂ№РЎвЂљРЎРЏР Р…РЎС“РЎвЂљРЎРЉ api_token РЎРѓ {self.server['name']}, "
                    f"Р С•РЎРѓРЎвЂљР В°РЎвЂР СРЎРѓРЎРЏ Р Р† РЎР‚Р ВµР В¶Р С‘Р СР Вµ csrf (cookie + X-CSRF-Token)"
                )

        return True

    async def _ensure_cookie_auth(self) -> bool:
        """Р вЂњР В°РЎР‚Р В°Р Р…РЎвЂљР С‘РЎР‚РЎС“Р ВµРЎвЂљ cookie-РЎРѓР ВµРЎРѓРЎРѓР С‘РЎР‹ Р Т‘Р В»РЎРЏ /panel/setting/* Р Т‘Р В°Р В¶Р Вµ Р Р† Bearer-РЎР‚Р ВµР В¶Р С‘Р СР Вµ."""
        if self.cookie_authenticated and self.session is not None and not self.session.closed:
            return True
        bearer_token = self.api_token
        was_bearer = self.panel_mode == 'bearer' and bool(bearer_token)
        await self._login_with_cookie(fetch_token=False)
        if was_bearer and bearer_token:
            self.api_token = bearer_token
            self.panel_mode = 'bearer'
            self.auth_mode = 'bearer'
            self.is_authenticated = True
        return True

    async def login(self) -> bool:
        """
        Р С’Р Р†РЎвЂљР С•РЎР‚Р С‘Р В·Р В°РЎвЂ Р С‘РЎРЏ Р Р† Р С—Р В°Р Р…Р ВµР В»Р С‘ 3X-UI РЎРѓ Р В°Р Р†РЎвЂљР С•-Р С•Р С—РЎР‚Р ВµР Т‘Р ВµР В»Р ВµР Р…Р С‘Р ВµР С auth/API Р С—РЎР‚Р С•РЎвЂћР С‘Р В»РЎРЏ.

        Р С’Р В»Р С–Р С•РЎР‚Р С‘РЎвЂљР С:
        1. Р вЂўРЎРѓР В»Р С‘ Р ВµРЎРѓРЎвЂљРЎРЉ РЎРѓР С•РЎвЂ¦РЎР‚Р В°Р Р…РЎвЂР Р…Р Р…РЎвЂ№Р в„– api_token РІР‚вЂќ Р С—РЎР‚Р С•Р В±РЎС“Р ВµР С Bearer-Р Р†Р В°Р В»Р С‘Р Т‘Р В°РЎвЂ Р С‘РЎР‹ (Р В±Р ВµР В· Р В»Р С•Р С–Р С‘Р Р…Р В°).
           Р СњР В° РЎС“РЎРѓР С—Р ВµРЎвЂ¦Р Вµ РЎРѓРЎвЂљР В°Р Р†Р С‘Р С panel_mode='bearer' Р С‘ Р С—РЎР‚Р С•Р Р†Р ВµРЎР‚РЎРЏР ВµР С version/profile.
        2. Probe GET /csrf-token РІвЂ вЂ™ 200 Р В·Р Р…Р В°РЎвЂЎР С‘РЎвЂљ v3.0+, 404 Р В·Р Р…Р В°РЎвЂЎР С‘РЎвЂљ v2.x.
        3. Р СњР В° v3.0+: Р В»Р С•Р С–Р С‘Р Р…Р С‘Р СРЎРѓРЎРЏ РЎРѓ X-CSRF-Token, Р В·Р В°РЎвЂљР ВµР С РЎвЂљРЎРЏР Р…Р ВµР С/РЎРѓР С•Р В·Р Т‘Р В°РЎвЂР С api_token.
        4. Р СњР В° v2.x: Р С•Р В±РЎвЂ№РЎвЂЎР Р…РЎвЂ№Р в„– POST /login Р В±Р ВµР В· CSRF.

        Returns:
            True Р С—РЎР‚Р С‘ РЎС“РЎРѓР С—Р ВµРЎв‚¬Р Р…Р С•Р в„– Р В°Р Р†РЎвЂљР С•РЎР‚Р С‘Р В·Р В°РЎвЂ Р С‘Р С‘

        Raises:
            VPNAPIError: Р СџРЎР‚Р С‘ Р С•РЎв‚¬Р С‘Р В±Р С”Р Вµ Р В°Р Р†РЎвЂљР С•РЎР‚Р С‘Р В·Р В°РЎвЂ Р С‘Р С‘
        """
        logger.info(f"Р С’Р Р†РЎвЂљР С•РЎР‚Р С‘Р В·Р В°РЎвЂ Р С‘РЎРЏ Р Р…Р В° {self.server['name']}...")

        if self.api_token:
            if await self._try_bearer_validate():
                self.panel_mode = 'bearer'
                self.auth_mode = 'bearer'
                self.is_authenticated = True
                self.cookie_authenticated = False
                await self._refresh_panel_metadata(force=True)
                logger.info(f"РІСљвЂ¦ Р С’Р Р†РЎвЂљР С•РЎР‚Р С‘Р В·Р В°РЎвЂ Р С‘РЎРЏ РЎвЂЎР ВµРЎР‚Р ВµР В· Bearer-РЎвЂљР С•Р С”Р ВµР Р… (v3.0+) Р Р…Р В° {self.server['name']}")
                return True
            await self._invalidate_api_token()

        await self._login_with_cookie(fetch_token=True)
        await self._refresh_panel_metadata(force=True)
        return True

    async def get_inbounds(self) -> List[Dict[str, Any]]:
        """
        Р СџР С•Р В»РЎС“РЎвЂЎР В°Р ВµРЎвЂљ РЎРѓР С—Р С‘РЎРѓР С•Р С” Р С—Р С•Р Т‘Р С”Р В»РЎР‹РЎвЂЎР ВµР Р…Р С‘Р в„– (Inbounds).
        
        Returns:
            Р РЋР С—Р С‘РЎРѓР С•Р С” inbound-Р С—Р С•Р Т‘Р С”Р В»РЎР‹РЎвЂЎР ВµР Р…Р С‘Р в„–
        """
        result = await self._request("GET", "/panel/api/inbounds/list")
        obj = result.get("obj", [])
        if not isinstance(obj, list):
            return []
        return [self._normalize_inbound(inbound) for inbound in obj if isinstance(inbound, dict)]
    
    async def get_server_status(self) -> Dict[str, Any]:
        """
        Р СџР С•Р В»РЎС“РЎвЂЎР В°Р ВµРЎвЂљ РЎРѓРЎвЂљР В°РЎвЂљРЎС“РЎРѓ РЎРѓР ВµРЎР‚Р Р†Р ВµРЎР‚Р В° (CPU, Р С—Р В°Р СРЎРЏРЎвЂљРЎРЉ, uptime).
        
        Returns:
            Р РЋР В»Р С•Р Р†Р В°РЎР‚РЎРЉ РЎРѓР С• РЎРѓРЎвЂљР В°РЎвЂљРЎС“РЎРѓР С•Р С РЎРѓР ВµРЎР‚Р Р†Р ВµРЎР‚Р В°
        """
        try:
            result = await self._request("GET", "/panel/api/server/status")
            return result.get("obj", {})
        except VPNAPIError:
            # Р СњР ВµР С”Р С•РЎвЂљР С•РЎР‚РЎвЂ№Р Вµ Р Р†Р ВµРЎР‚РЎРѓР С‘Р С‘ 3X-UI Р Р…Р Вµ Р С‘Р СР ВµРЎР‹РЎвЂљ РЎРЊРЎвЂљР С•Р С–Р С• endpoint
            return {}

    async def get_stats(self) -> Dict[str, Any]:
        """
        Р СџР С•Р В»РЎС“РЎвЂЎР В°Р ВµРЎвЂљ РЎРѓРЎвЂљР В°РЎвЂљР С‘РЎРѓРЎвЂљР С‘Р С”РЎС“ РЎРѓР ВµРЎР‚Р Р†Р ВµРЎР‚Р В°.
        
        Returns:
            Р РЋР В»Р С•Р Р†Р В°РЎР‚РЎРЉ РЎРѓР С• РЎРѓРЎвЂљР В°РЎвЂљР С‘РЎРѓРЎвЂљР С‘Р С”Р С•Р в„–:
            - total_clients: Р С›Р В±РЎвЂ°Р ВµР Вµ Р С”Р С•Р В»Р С‘РЎвЂЎР ВµРЎРѓРЎвЂљР Р†Р С• Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР С•Р Р†
            - active_clients: Р С™Р С•Р В»Р С‘РЎвЂЎР ВµРЎРѓРЎвЂљР Р†Р С• Р В°Р С”РЎвЂљР С‘Р Р†Р Р…РЎвЂ№РЎвЂ¦ Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР С•Р Р† (enable=True)
            - total_traffic_bytes: Р С›Р В±РЎвЂ°Р С‘Р в„– РЎвЂљРЎР‚Р В°РЎвЂћР С‘Р С” (up + down)
            - cpu_percent: Р вЂ”Р В°Р С–РЎР‚РЎС“Р В·Р С”Р В° CPU (Р ВµРЎРѓР В»Р С‘ Р Т‘Р С•РЎРѓРЎвЂљРЎС“Р С—Р Р…Р С•)
            - online: True Р ВµРЎРѓР В»Р С‘ РЎРѓР ВµРЎР‚Р Р†Р ВµРЎР‚ Р Т‘Р С•РЎРѓРЎвЂљРЎС“Р С—Р ВµР Р…
        """
        try:
            inbounds = await self.get_inbounds()
            
            total_clients = 0
            active_clients = 0
            total_traffic = 0
            
            for inbound in inbounds:
                # Р СџР В°РЎР‚РЎРѓР С‘Р С Р Р…Р В°РЎРѓРЎвЂљРЎР‚Р С•Р в„–Р С”Р С‘ Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР С•Р Р†
                settings = self._load_json_field(inbound.get("settings", "{}"))
                clients = settings.get("clients", [])
                total_clients += len(clients)

                for client in clients:
                    if client.get("enable", True):
                        active_clients += 1
                
                # Р СћРЎР‚Р В°РЎвЂћР С‘Р С” inbound
                total_traffic += inbound.get("up", 0)
                total_traffic += inbound.get("down", 0)
            
            # Р СџРЎР‚Р С•Р В±РЎС“Р ВµР С Р С—Р С•Р В»РЎС“РЎвЂЎР С‘РЎвЂљРЎРЉ РЎРѓРЎвЂљР В°РЎвЂљРЎС“РЎРѓ РЎРѓР ВµРЎР‚Р Р†Р ВµРЎР‚Р В° (CPU)
            cpu_percent = None
            try:
                status = await self.get_server_status()
                if status:
                    raw_cpu = status.get("cpu")
                    if raw_cpu is not None:
                        try:
                            cpu_percent = int(float(raw_cpu))
                        except (ValueError, TypeError):
                            pass
            except VPNAPIError:
                pass
            
            return {
                "total_clients": total_clients,
                "active_clients": active_clients,
                "online_clients": await self.get_online_clients_count(),
                "total_traffic_bytes": total_traffic,
                "cpu_percent": cpu_percent,
                "online": True
            }
            
        except VPNAPIError as e:
            logger.warning(f"Р С›РЎв‚¬Р С‘Р В±Р С”Р В° Р С—Р С•Р В»РЎС“РЎвЂЎР ВµР Р…Р С‘РЎРЏ РЎРѓРЎвЂљР В°РЎвЂљР С‘РЎРѓРЎвЂљР С‘Р С”Р С‘: {e}")
            return {
                "total_clients": 0,
                "active_clients": 0,
                "online_clients": 0,
                "total_traffic_bytes": 0,
                "cpu_percent": None,
                "online": False,
                "error": str(e)
            }

    async def get_online_clients_count(self) -> int:
        return await self._run_with_stale_profile_retry(
            self._get_online_clients_count_impl
        )

    async def _get_online_clients_count_impl(self) -> int:
        """
        Р СџР С•Р В»РЎС“РЎвЂЎР В°Р ВµРЎвЂљ Р С”Р С•Р В»Р С‘РЎвЂЎР ВµРЎРѓРЎвЂљР Р†Р С• Р С—Р С•Р В»РЎРЉР В·Р С•Р Р†Р В°РЎвЂљР ВµР В»Р ВµР в„– Р С•Р Р…Р В»Р В°Р в„–Р Р….
        
        Returns:
            Р С™Р С•Р В»Р С‘РЎвЂЎР ВµРЎРѓРЎвЂљР Р†Р С• Р С—Р С•Р В»РЎРЉР В·Р С•Р Р†Р В°РЎвЂљР ВµР В»Р ВµР в„– Р С•Р Р…Р В»Р В°Р в„–Р Р…
        """
        try:
            profile = await self._ensure_api_profile()
            endpoint = (
                "/panel/api/clients/onlines"
                if profile == API_PROFILE_CLIENTS
                else "/panel/api/inbounds/onlines"
            )
            response = await self._request("POST", endpoint, retry=False, log_error=False)
            if response.get("success") and response.get("obj"):
                return len(response["obj"])
        except StaleAPIProfileError:
            raise
        except VPNAPIError:
            pass
        except Exception as e:
            logger.debug(f"Р С›РЎв‚¬Р С‘Р В±Р С”Р В° Р С—Р С•Р В»РЎС“РЎвЂЎР ВµР Р…Р С‘РЎРЏ online Р С—Р С•Р В»РЎРЉР В·Р С•Р Р†Р В°РЎвЂљР ВµР В»Р ВµР в„–: {e}")
        return 0

    async def add_client(
        self,
        inbound_id: int,
        email: str,
        total_gb: int = 0,
        expire_days: int = 30,
        limit_ip: int = 1,
        enable: bool = True,
        tg_id: str = "",
        flow: str = "",
        sub_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        return await self._run_with_stale_profile_retry(
            lambda: self._add_client_impl(
                inbound_id=inbound_id,
                email=email,
                total_gb=total_gb,
                expire_days=expire_days,
                limit_ip=limit_ip,
                enable=enable,
                tg_id=tg_id,
                flow=flow,
                sub_id=sub_id,
            )
        )

    async def _add_client_impl(
        self,
        inbound_id: int,
        email: str,
        total_gb: int = 0,
        expire_days: int = 30,
        limit_ip: int = 1,
        enable: bool = True,
        tg_id: str = "",
        flow: str = "",
        sub_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Р вЂќР С•Р В±Р В°Р Р†Р В»РЎРЏР ВµРЎвЂљ Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР В° Р Р† inbound.

        Args:
            inbound_id: ID inbound-Р С—Р С•Р Т‘Р С”Р В»РЎР‹РЎвЂЎР ВµР Р…Р С‘РЎРЏ
            email: Р Р€Р Р…Р С‘Р С”Р В°Р В»РЎРЉР Р…РЎвЂ№Р в„– Р С‘Р Т‘Р ВµР Р…РЎвЂљР С‘РЎвЂћР С‘Р С”Р В°РЎвЂљР С•РЎР‚ Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР В° (Р С‘РЎРѓР С—Р С•Р В»РЎРЉР В·РЎС“Р ВµР С user_{id})
            total_gb: Р вЂєР С‘Р СР С‘РЎвЂљ РЎвЂљРЎР‚Р В°РЎвЂћР С‘Р С”Р В° Р Р† Р вЂњР вЂ (0 = Р В±Р ВµР В· Р В»Р С‘Р СР С‘РЎвЂљР В°)
            expire_days: Р РЋРЎР‚Р С•Р С” Р Т‘Р ВµР в„–РЎРѓРЎвЂљР Р†Р С‘РЎРЏ Р Р† Р Т‘Р Р…РЎРЏРЎвЂ¦ (0 = Р В±Р ВµРЎРѓРЎРѓРЎР‚Р С•РЎвЂЎР Р…Р С•)
            limit_ip: Р С›Р С–РЎР‚Р В°Р Р…Р С‘РЎвЂЎР ВµР Р…Р С‘Р Вµ Р С—Р С• IP (1 = 1 РЎС“РЎРѓРЎвЂљРЎР‚Р С•Р в„–РЎРѓРЎвЂљР Р†Р С•)
            enable: Р С’Р С”РЎвЂљР С‘Р Р†Р ВµР Р… Р В»Р С‘ Р С”Р В»Р С‘Р ВµР Р…РЎвЂљ
            tg_id: Telegram ID Р Т‘Р В»РЎРЏ РЎС“Р Р†Р ВµР Т‘Р С•Р СР В»Р ВµР Р…Р С‘Р в„– Р С—Р В°Р Р…Р ВµР В»Р С‘
            flow: Р СџР В°РЎР‚Р В°Р СР ВµРЎвЂљРЎР‚ flow (Р Р…Р В°Р С—РЎР‚. 'xtls-rprx-vision' Р Т‘Р В»РЎРЏ VLESS Reality/TLS TCP)
            sub_id: Subscription ID. Р вЂўРЎРѓР В»Р С‘ Р С—Р ВµРЎР‚Р ВµР Т‘Р В°Р Р… РІР‚вЂќ Р С‘РЎРѓР С—Р С•Р В»РЎРЉР В·РЎС“Р ВµРЎвЂљРЎРѓРЎРЏ Р С”Р В°Р С” Р ВµРЎРѓРЎвЂљРЎРЉ (Р Т‘Р В»РЎРЏ
                РЎР‚Р ВµР В¶Р С‘Р СР В° subscription, Р С–Р Т‘Р Вµ Р С•Р Т‘Р С‘Р Р… subId Р Т‘Р С•Р В»Р В¶Р ВµР Р… Р В±РЎвЂ№РЎвЂљРЎРЉ Р Р…Р В° Р Р†РЎРѓР ВµРЎвЂ¦ Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР В°РЎвЂ¦
                РЎРѓ Р С•Р Т‘Р Р…Р С‘Р С email). Р вЂўРЎРѓР В»Р С‘ None РІР‚вЂќ Р С–Р ВµР Р…Р ВµРЎР‚Р С‘РЎР‚РЎС“Р ВµРЎвЂљРЎРѓРЎРЏ Р Р…Р С•Р Р†РЎвЂ№Р в„– uuid.

        Returns:
            Р РЋР В»Р С•Р Р†Р В°РЎР‚РЎРЉ РЎРѓ Р Т‘Р В°Р Р…Р Р…РЎвЂ№Р СР С‘ РЎРѓР С•Р В·Р Т‘Р В°Р Р…Р Р…Р С•Р С–Р С• Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР В°

        Raises:
            ValueError: Р вЂўРЎРѓР В»Р С‘ expire_days <= 0
        """
        if expire_days <= 0:
            raise ValueError("Р РЋРЎР‚Р С•Р С” Р Т‘Р ВµР в„–РЎРѓРЎвЂљР Р†Р С‘РЎРЏ Р С”Р В»РЎР‹РЎвЂЎР В° Р Т‘Р С•Р В»Р В¶Р ВµР Р… Р В±РЎвЂ№РЎвЂљРЎРЉ Р В±Р С•Р В»РЎРЉРЎв‚¬Р Вµ 0 Р Т‘Р Р…Р ВµР в„–")
        profile = await self._ensure_api_profile()

        # Р С›Р С—РЎР‚Р ВµР Т‘Р ВµР В»РЎРЏР ВµР С Р С—РЎР‚Р С•РЎвЂљР С•Р С”Р С•Р В» inbound Р Т‘Р В»РЎРЏ Р С—РЎР‚Р В°Р Р†Р С‘Р В»РЎРЉР Р…Р С•Р в„– РЎРѓРЎвЂљРЎР‚РЎС“Р С”РЎвЂљРЎС“РЎР‚РЎвЂ№ Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР В°
        protocol = ""
        method = ""
        try:
            inbounds = await self.get_inbounds()
            for ib in inbounds:
                if ib['id'] == inbound_id:
                    protocol = ib.get('protocol', '')
                    settings = self._load_json_field(ib.get('settings', '{}'))
                    method = settings.get('method', '')
                    break
        except Exception:
            pass

        client_uuid = str(uuid.uuid4())
        
        # Р вЂќР В»РЎРЏ Shadowsocks 2022 РЎвЂљРЎР‚Р ВµР В±РЎС“Р ВµРЎвЂљРЎРѓРЎРЏ base64 Р С—Р В°РЎР‚Р С•Р В»РЎРЉ Р С•Р С—РЎР‚Р ВµР Т‘Р ВµР В»Р ВµР Р…Р Р…Р С•Р в„– Р Т‘Р В»Р С‘Р Р…РЎвЂ№
        if protocol == 'shadowsocks':
            import base64
            import os
            if method.startswith('2022-'):
                if '128' in method:
                    client_uuid = base64.b64encode(os.urandom(16)).decode('utf-8')
                else:
                    client_uuid = base64.b64encode(os.urandom(32)).decode('utf-8')
            else:
                # Р вЂќР В»РЎРЏ Р С•Р В±РЎвЂ№РЎвЂЎР Р…Р С•Р С–Р С• SS Р В»РЎС“РЎвЂЎРЎв‚¬Р Вµ РЎвЂљР С•Р В¶Р Вµ Р С‘РЎРѓР С—Р С•Р В»РЎРЉР В·Р С•Р Р†Р В°РЎвЂљРЎРЉ base64 (Р Р…Р В°Р Т‘Р ВµР В¶Р Р…Р ВµР Вµ, РЎвЂЎР ВµР С uuid РЎРѓ Р Т‘Р ВµРЎвЂћР С‘РЎРѓР В°Р СР С‘)
                client_uuid = base64.urlsafe_b64encode(os.urandom(16)).decode('utf-8').rstrip('=')

        # Р вЂ™РЎР‚Р ВµР СРЎРЏ Р С‘РЎРѓРЎвЂљР ВµРЎвЂЎР ВµР Р…Р С‘РЎРЏ (timestamp Р Р† Р СРЎРѓ)
        expire_time = int((time.time() + expire_days * 86400) * 1000) if expire_days > 0 else 0
        
        # Р вЂєР С‘Р СР С‘РЎвЂљ РЎвЂљРЎР‚Р В°РЎвЂћР С‘Р С”Р В° (Р В±Р В°Р в„–РЎвЂљРЎвЂ№)
        total_bytes = total_gb * 1024 * 1024 * 1024 if total_gb > 0 else 0
        
        # Р вЂР В°Р В·Р С•Р Р†Р В°РЎРЏ РЎРѓРЎвЂљРЎР‚РЎС“Р С”РЎвЂљРЎС“РЎР‚Р В° Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР В°
        client_entry = {
            "email": email,
            "limitIp": limit_ip,
            "totalGB": total_bytes,
            "expiryTime": expire_time,
            "enable": enable,
            "tgId": tg_id,
            "subId": sub_id if sub_id else uuid.uuid4().hex,
            "reset": 0,
        }
        
        # Р СџРЎР‚Р С•РЎвЂљР С•Р С”Р С•Р В»-Р В·Р В°Р Р†Р С‘РЎРѓР С‘Р СРЎвЂ№Р Вµ Р С—Р С•Р В»РЎРЏ
        if protocol == 'trojan':
            # Trojan Р С‘РЎРѓР С—Р С•Р В»РЎРЉР В·РЎС“Р ВµРЎвЂљ password Р Р†Р СР ВµРЎРѓРЎвЂљР С• id
            client_entry["password"] = client_uuid
            client_entry["flow"] = flow
        elif protocol == 'shadowsocks':
            # Shadowsocks РІР‚вЂќ Р С”Р В»Р С‘Р ВµР Р…РЎвЂљРЎвЂ№ Р Р…Р В°РЎРѓР В»Р ВµР Т‘РЎС“РЎР‹РЎвЂљ password/method Р С‘Р В· inbound
            client_entry["password"] = client_uuid
            client_entry["method"] = ""
        else:
            # VLESS / VMess РІР‚вЂќ Р С‘РЎРѓР С—Р С•Р В»РЎРЉР В·РЎС“РЎР‹РЎвЂљ id (UUID)
            client_entry["id"] = client_uuid
            client_entry["flow"] = flow
        
        # Р РЋРЎвЂљРЎР‚РЎС“Р С”РЎвЂљРЎС“РЎР‚Р В° Р Т‘Р В»РЎРЏ 3X-UI
        client_data = {
            "id": inbound_id,
            "settings": json.dumps({
                "clients": [client_entry]
            })
        }

        if profile == API_PROFILE_CLIENTS:
            record = await self._get_clients_api_record(email)
            if record:
                existing_client, inbound_ids = self._split_clients_api_record(record)
                if inbound_id not in inbound_ids:
                    encoded_email = urllib.parse.quote(email, safe="")
                    await self._request(
                        "POST",
                        f"/panel/api/clients/{encoded_email}/attach",
                        data={"inboundIds": [inbound_id]},
                    )
                existing_uuid = (
                    existing_client.get("uuid")
                    or self._client_identifier_from_entry(existing_client)
                    or client_uuid
                )
                return {
                    "uuid": existing_uuid,
                    "email": email,
                    "inbound_id": inbound_id,
                    "expire_time": existing_client.get("expiryTime", expire_time),
                    "total_gb": total_gb,
                    "sub_id": existing_client.get("subId") or client_entry["subId"],
                }

            api_client_entry = dict(client_entry)
            api_client_entry["tgId"] = self._normalize_tg_id(tg_id)
            await self._request(
                "POST",
                "/panel/api/clients/add",
                data={"client": api_client_entry, "inboundIds": [inbound_id]},
            )
        else:
            await self._request("POST", "/panel/api/inbounds/addClient", data=client_data)

        return {
            "uuid": client_uuid,
            "email": email,
            "inbound_id": inbound_id,
            "expire_time": expire_time,
            "total_gb": total_gb,
            "sub_id": client_entry["subId"],
        }
    
    async def get_inbound_flow(self, inbound_id: int) -> str:
        """
        Р С›Р С—РЎР‚Р ВµР Т‘Р ВµР В»РЎРЏР ВµРЎвЂљ Р Р…РЎС“Р В¶Р Р…Р С•Р Вµ Р В·Р Р…Р В°РЎвЂЎР ВµР Р…Р С‘Р Вµ flow Р Т‘Р В»РЎРЏ inbound.
        Flow = 'xtls-rprx-vision' Р Р…РЎС“Р В¶Р ВµР Р… РЎвЂљР С•Р В»РЎРЉР С”Р С• Р Т‘Р В»РЎРЏ VLESS + TCP + (Reality Р С‘Р В»Р С‘ TLS).
        """
        try:
            inbounds = await self.get_inbounds()
            for inbound in inbounds:
                if inbound['id'] == inbound_id:
                    protocol = inbound.get('protocol', '')
                    if protocol != 'vless':
                        return ""
                    
                    stream_raw = inbound.get('streamSettings', '{}')
                    if isinstance(stream_raw, str):
                        stream = json.loads(stream_raw)
                    else:
                        stream = stream_raw
                    
                    network = stream.get('network', 'tcp')
                    security = stream.get('security', 'none')
                    
                    # Flow Р Р…РЎС“Р В¶Р ВµР Р… РЎвЂљР С•Р В»РЎРЉР С”Р С• Р Т‘Р В»РЎРЏ VLESS + TCP + (reality | tls)
                    if network == 'tcp' and security in ('reality', 'tls'):
                        return 'xtls-rprx-vision'
                    return ""
        except Exception as e:
            logger.warning(f"Error determining flow for inbound {inbound_id}: {e}")
        return ""
    
    async def get_client_stats(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Р СџР С•Р В»РЎС“РЎвЂЎР В°Р ВµРЎвЂљ РЎРѓРЎвЂљР В°РЎвЂљР С‘РЎРѓРЎвЂљР С‘Р С”РЎС“ РЎвЂљРЎР‚Р В°РЎвЂћР С‘Р С”Р В° Р С‘ Р С—РЎР‚Р С•РЎвЂљР С•Р С”Р С•Р В» Р С”Р С•Р Р…Р С”РЎР‚Р ВµРЎвЂљР Р…Р С•Р С–Р С• Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР В°.
        
        Args:
            email: Email/Р С‘Р Т‘Р ВµР Р…РЎвЂљР С‘РЎвЂћР С‘Р С”Р В°РЎвЂљР С•РЎР‚ Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР В°
            
        Returns:
            Р РЋР В»Р С•Р Р†Р В°РЎР‚РЎРЉ РЎРѓР С• РЎРѓРЎвЂљР В°РЎвЂљР С‘РЎРѓРЎвЂљР С‘Р С”Р С•Р в„– Р С‘Р В»Р С‘ None:
            - up: Р СћРЎР‚Р В°РЎвЂћР С‘Р С” Р В·Р В° Р Р†РЎРѓРЎвЂ Р Р†РЎР‚Р ВµР СРЎРЏ (up) Р В±Р В°Р в„–РЎвЂљ
            - down: Р СћРЎР‚Р В°РЎвЂћР С‘Р С” Р В·Р В° Р Р†РЎРѓРЎвЂ Р Р†РЎР‚Р ВµР СРЎРЏ (down) Р В±Р В°Р в„–РЎвЂљ
            - total: Р вЂєР С‘Р СР С‘РЎвЂљ РЎвЂљРЎР‚Р В°РЎвЂћР С‘Р С”Р В° (Р В±Р В°Р в„–РЎвЂљ)
            - protocol: Р СџРЎР‚Р С•РЎвЂљР С•Р С”Р С•Р В» РЎРѓР С•Р ВµР Т‘Р С‘Р Р…Р ВµР Р…Р С‘РЎРЏ (vless, vmess Р С‘ РЎвЂљ.Р Т‘.)
        """
        try:
            profile = await self._ensure_api_profile()
            if profile == API_PROFILE_CLIENTS:
                encoded_email = urllib.parse.quote(email, safe="")
                result = await self._request(
                    "GET",
                    f"/panel/api/clients/traffic/{encoded_email}",
                    retry=False,
                    log_error=False,
                )
                traffic = result.get("obj")
                if isinstance(traffic, dict):
                    protocol = "vless"
                    remark = ""
                    try:
                        inbound, _ = await self._find_panel_client(email=email)
                        if inbound:
                            protocol = inbound.get("protocol", protocol)
                            remark = inbound.get("remark", "")
                    except Exception:
                        pass
                    return {
                        "up": traffic.get("up", 0),
                        "down": traffic.get("down", 0),
                        "total": traffic.get("total", 0),
                        "protocol": protocol,
                        "remark": remark,
                        "expiry_time": traffic.get("expiryTime", 0),
                    }

            inbounds = await self.get_inbounds()
            for inbound in inbounds:
                client_stats = inbound.get("clientStats", [])
                for stats in client_stats:
                    if stats.get("email") == email:
                        return {
                            "up": stats.get("up", 0),
                            "down": stats.get("down", 0),
                            "total": stats.get("total", 0),
                            "protocol": inbound.get("protocol", "vless"),
                            "remark": inbound.get("remark", ""),
                            "expiry_time": stats.get("expiryTime", 0)
                        }
        except Exception as e:
            logger.warning(f"Р С›РЎв‚¬Р С‘Р В±Р С”Р В° Р С—Р С•Р В»РЎС“РЎвЂЎР ВµР Р…Р С‘РЎРЏ РЎРѓРЎвЂљР В°РЎвЂљР С‘РЎРѓРЎвЂљР С‘Р С”Р С‘ Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР В° {email}: {e}")
        return None
    
    async def delete_client(self, inbound_id: int, client_uuid: str) -> bool:
        return await self._run_with_stale_profile_retry(
            lambda: self._delete_client_impl(inbound_id, client_uuid)
        )

    async def _delete_client_impl(self, inbound_id: int, client_uuid: str) -> bool:
        """
        Р Р€Р Т‘Р В°Р В»РЎРЏР ВµРЎвЂљ Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР В° Р С‘Р В· inbound.

        Args:
            inbound_id: ID inbound-Р С—Р С•Р Т‘Р С”Р В»РЎР‹РЎвЂЎР ВµР Р…Р С‘РЎРЏ
            client_uuid: UUID Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР В°

        Returns:
            True Р С—РЎР‚Р С‘ РЎС“РЎРѓР С—Р ВµРЎв‚¬Р Р…Р С•Р С РЎС“Р Т‘Р В°Р В»Р ВµР Р…Р С‘Р С‘
        """
        profile = await self._ensure_api_profile()
        if profile == API_PROFILE_CLIENTS:
            _, client = await self._find_panel_client(inbound_id=inbound_id, client_uuid=client_uuid)
            email = client.get("email") if isinstance(client, dict) else None
            if not email:
                email = client_uuid
            record = await self._get_clients_api_record(email, log_error=False)
            encoded_email = urllib.parse.quote(email, safe="")
            if record:
                _, inbound_ids = self._split_clients_api_record(record)
                if len(inbound_ids) > 1:
                    await self._request(
                        "POST",
                        f"/panel/api/clients/{encoded_email}/detach",
                        data={"inboundIds": [inbound_id]},
                    )
                    return True
            await self._request("POST", f"/panel/api/clients/del/{encoded_email}")
            return True

        encoded_uuid = urllib.parse.quote(client_uuid, safe='')
        await self._request("POST", f"/panel/api/inbounds/{inbound_id}/delClient/{encoded_uuid}")
        return True

    async def delete_clients_by_email_on_server(self, email: str) -> int:
        return await self._run_with_stale_profile_retry(
            lambda: self._delete_clients_by_email_on_server_impl(email)
        )

    async def _delete_clients_by_email_on_server_impl(self, email: str) -> int:
        """
        Р Р€Р Т‘Р В°Р В»РЎРЏР ВµРЎвЂљ Р вЂ™Р РЋР вЂўР Тђ Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР С•Р Р† РЎРѓ РЎС“Р С”Р В°Р В·Р В°Р Р…Р Р…РЎвЂ№Р С email Р Р†Р С• Р Р†РЎРѓР ВµРЎвЂ¦ inbound РЎРѓР ВµРЎР‚Р Р†Р ВµРЎР‚Р В°.

        Р ВРЎРѓР С—Р С•Р В»РЎРЉР В·РЎС“Р ВµРЎвЂљРЎРѓРЎРЏ Р Р† РЎР‚Р ВµР В¶Р С‘Р СР Вµ subscription Р С—РЎР‚Р С‘ Р В·Р В°Р СР ВµР Р…Р Вµ Р С”Р В»РЎР‹РЎвЂЎР В°, РЎС“Р Т‘Р В°Р В»Р ВµР Р…Р С‘Р С‘ Р С”Р В»РЎР‹РЎвЂЎР В°
        Р С‘ Р С—РЎР‚Р С‘ Р С—Р ВµРЎР‚Р ВµР С”Р В»РЎР‹РЎвЂЎР ВµР Р…Р С‘Р С‘ Р Р…Р В° РЎР‚Р ВµР В¶Р С‘Р С keys (Р В·Р В°РЎвЂЎР С‘РЎРѓРЎвЂљР С”Р В° Р Т‘РЎС“Р В±Р В»Р С‘Р С”Р В°РЎвЂљР С•Р Р†).

        Args:
            email: Email/Р С‘Р Т‘Р ВµР Р…РЎвЂљР С‘РЎвЂћР С‘Р С”Р В°РЎвЂљР С•РЎР‚ Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР В°

        Returns:
            Р С™Р С•Р В»Р С‘РЎвЂЎР ВµРЎРѓРЎвЂљР Р†Р С• РЎвЂћР В°Р С”РЎвЂљР С‘РЎвЂЎР ВµРЎРѓР С”Р С‘ РЎС“Р Т‘Р В°Р В»РЎвЂР Р…Р Р…РЎвЂ№РЎвЂ¦ Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР С•Р Р†
        """
        profile = await self._ensure_api_profile()
        if profile == API_PROFILE_CLIENTS:
            record = await self._get_clients_api_record(email, log_error=False)
            if not record:
                return 0
            _, inbound_ids = self._split_clients_api_record(record)
            encoded_email = urllib.parse.quote(email, safe="")
            await self._request("POST", f"/panel/api/clients/del/{encoded_email}")
            return max(1, len(inbound_ids))

        inbounds = await self.get_inbounds()
        deleted = 0
        for inbound in inbounds:
            try:
                settings = self._load_json_field(inbound.get('settings', '{}'))
            except TypeError:
                continue
            for client in settings.get('clients', []):
                if client.get('email') != email:
                    continue
                cid = client.get('id') or client.get('password')
                if not cid:
                    continue
                try:
                    await self.delete_client(inbound['id'], cid)
                    deleted += 1
                except VPNAPIError as e:
                    logger.warning(
                        f"Р СњР Вµ РЎС“Р Т‘Р В°Р В»Р С•РЎРѓРЎРЉ РЎС“Р Т‘Р В°Р В»Р С‘РЎвЂљРЎРЉ Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР В° {email} Р С‘Р В· inbound {inbound['id']}: {e}"
                    )
        return deleted

    async def set_clients_enabled_by_email(self, email: str, enable: bool) -> int:
        return await self._run_with_stale_profile_retry(
            lambda: self._set_clients_enabled_by_email_impl(email, enable)
        )

    async def _set_clients_enabled_by_email_impl(self, email: str, enable: bool) -> int:
        """
        Р вЂ™Р С”Р В»РЎР‹РЎвЂЎР В°Р ВµРЎвЂљ/Р С•РЎвЂљР С”Р В»РЎР‹РЎвЂЎР В°Р ВµРЎвЂљ Р вЂ™Р РЋР вЂўР Тђ Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР С•Р Р† РЎРѓ РЎС“Р С”Р В°Р В·Р В°Р Р…Р Р…РЎвЂ№Р С email Р Р†Р С• Р Р†РЎРѓР ВµРЎвЂ¦ inbound РЎРѓР ВµРЎР‚Р Р†Р ВµРЎР‚Р В°.

        Р ВРЎРѓР С—Р С•Р В»РЎРЉР В·РЎС“Р ВµРЎвЂљРЎРѓРЎРЏ Р С—РЎР‚Р С‘ Р С‘РЎРѓРЎвЂљР ВµРЎвЂЎР ВµР Р…Р С‘Р С‘ РЎвЂљРЎР‚Р В°РЎвЂћР С‘Р С”Р В° Р С‘Р В»Р С‘ РЎРѓРЎР‚Р С•Р С”Р В° Р Т‘Р ВµР в„–РЎРѓРЎвЂљР Р†Р С‘РЎРЏ Р Р† РЎР‚Р ВµР В¶Р С‘Р СР Вµ subscription:
        Р С—Р В°Р Р…Р ВµР В»РЎРЉ РЎРѓР В°Р СР В° Р Р…Р Вµ Р С•РЎвЂљР С”Р В»РЎР‹РЎвЂЎР В°Р ВµРЎвЂљ Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР В° Р С—Р С• Р Р…Р В°РЎв‚¬Р ВµР СРЎС“ РЎРѓРЎвЂЎРЎвЂРЎвЂљРЎвЂЎР С‘Р С”РЎС“ (РЎвЂљР С•Р В»РЎРЉР С”Р С• Р С—Р С• РЎРѓР Р†Р С•Р ВµР СРЎС“ totalGB),
        Р С—Р С•РЎРЊРЎвЂљР С•Р СРЎС“ Р С•РЎвЂљР С”Р В»РЎР‹РЎвЂЎР В°Р ВµР С Р Р†РЎР‚РЎС“РЎвЂЎР Р…РЎС“РЎР‹.

        Args:
            email: Email Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР В°
            enable: True РІР‚вЂќ Р Р†Р С”Р В»РЎР‹РЎвЂЎР С‘РЎвЂљРЎРЉ, False РІР‚вЂќ Р С•РЎвЂљР С”Р В»РЎР‹РЎвЂЎР С‘РЎвЂљРЎРЉ

        Returns:
            Р С™Р С•Р В»Р С‘РЎвЂЎР ВµРЎРѓРЎвЂљР Р†Р С• Р С•Р В±Р Р…Р С•Р Р†Р В»РЎвЂР Р…Р Р…РЎвЂ№РЎвЂ¦ Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР С•Р Р†
        """
        profile = await self._ensure_api_profile()
        if profile == API_PROFILE_CLIENTS:
            record = await self._get_clients_api_record(email, log_error=False)
            if not record:
                return 0
            client, inbound_ids = self._split_clients_api_record(record)
            if client.get("enable", True) == enable:
                return 0
            payload = self._build_client_payload_from_record(client, fallback_email=email)
            payload["enable"] = enable
            payload["reset"] = 0
            encoded_email = urllib.parse.quote(email, safe="")
            await self._request("POST", f"/panel/api/clients/update/{encoded_email}", data=payload)
            return max(1, len(inbound_ids))

        inbounds = await self.get_inbounds()
        count = 0
        for inbound in inbounds:
            try:
                settings = self._load_json_field(inbound.get('settings', '{}'))
            except TypeError:
                continue
            for cl in settings.get('clients', []):
                if cl.get('email') != email:
                    continue
                if cl.get('enable', True) == enable:
                    continue
                cid = cl.get('id') or cl.get('password')
                if not cid:
                    continue
                # Р РЋР С•РЎвЂ¦РЎР‚Р В°Р Р…РЎРЏР ВµР С Р Р†РЎРѓР Вµ Р С—Р С•Р В»РЎРЏ Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР В°, Р СР ВµР Р…РЎРЏР ВµР С РЎвЂљР С•Р В»РЎРЉР С”Р С• enable
                updated_client = dict(cl)
                updated_client['enable'] = enable
                data = {
                    "id": inbound['id'],
                    "settings": json.dumps({"clients": [updated_client]}),
                }
                try:
                    encoded = urllib.parse.quote(cid, safe='')
                    await self._request(
                        "POST",
                        f"/panel/api/inbounds/updateClient/{encoded}",
                        data=data,
                    )
                    count += 1
                except VPNAPIError as e:
                    action = "Р Р†Р С”Р В»РЎР‹РЎвЂЎР С‘РЎвЂљРЎРЉ" if enable else "Р С•РЎвЂљР С”Р В»РЎР‹РЎвЂЎР С‘РЎвЂљРЎРЉ"
                    logger.warning(
                        f"Р СњР Вµ РЎС“Р Т‘Р В°Р В»Р С•РЎРѓРЎРЉ {action} Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР В° {email} Р Р† inbound {inbound['id']}: {e}"
                    )
        return count

    async def get_panel_settings(self, force_refresh: bool = False) -> Optional[Dict[str, Any]]:
        """Gets panel settings from legacy or 3x-UI 3.3+ setting namespace."""
        if not force_refresh and self._panel_settings is not None:
            return self._panel_settings

        last_error = None
        for endpoint in self._setting_endpoints("all"):
            try:
                resp = await self._request("POST", endpoint)
            except Exception as e:
                last_error = e
                logger.debug(f"get_panel_settings: {endpoint} failed: {e}")
                continue
            if not isinstance(resp, dict) or not resp.get("success"):
                logger.debug(f"get_panel_settings: {endpoint} returned without success: {resp}")
                continue
            obj = resp.get("obj")
            if isinstance(obj, dict):
                self._panel_settings = obj
                return obj

        if last_error:
            logger.warning(f"get_panel_settings: request failed: {last_error}")
        else:
            logger.warning("get_panel_settings: panel returned no usable settings")
        return None


    async def build_subscription_url(self, sub_id: str) -> Optional[str]:
        """
        Р вЂ™Р С•Р В·Р Р†РЎР‚Р В°РЎвЂ°Р В°Р ВµРЎвЂљ HTTP-URL Р С—Р С•Р Т‘Р С—Р С‘РЎРѓР С”Р С‘ Р Т‘Р В»РЎРЏ Р С—Р С•Р В»РЎРЉР В·Р С•Р Р†Р В°РЎвЂљР ВµР В»РЎРЏ, РЎРѓР С•Р В±РЎР‚Р В°Р Р…Р Р…РЎвЂ№Р в„– Р С—Р С• Р Р…Р В°РЎРѓРЎвЂљРЎР‚Р С•Р в„–Р С”Р В°Р С
        subscription-server Р С‘Р В· API Р С—Р В°Р Р…Р ВµР В»Р С‘ (subDomain/subPort/subPath/subURI).

        Р СњР вЂў РЎС“Р С–Р В°Р Т‘РЎвЂ№Р Р†Р В°Р ВµРЎвЂљ Р С—Р С•РЎР‚РЎвЂљ/Р С—РЎС“РЎвЂљРЎРЉ Р С—Р С• host:port API РІР‚вЂќ Р В±Р ВµРЎР‚РЎвЂРЎвЂљ РЎР‚Р ВµР В°Р В»РЎРЉР Р…РЎвЂ№Р Вµ Р В·Р Р…Р В°РЎвЂЎР ВµР Р…Р С‘РЎРЏ РЎРѓ Р С—Р В°Р Р…Р ВµР В»Р С‘.
        Р вЂўРЎРѓР В»Р С‘ РЎС“ Р С—Р В°Р Р…Р ВµР В»Р С‘ subEnable=false Р С‘Р В»Р С‘ Р Р…Р В°РЎРѓРЎвЂљРЎР‚Р С•Р в„–Р С”Р С‘ Р С—Р С•Р В»РЎС“РЎвЂЎР С‘РЎвЂљРЎРЉ Р Р…Р Вµ РЎС“Р Т‘Р В°Р В»Р С•РЎРѓРЎРЉ РІР‚вЂќ Р Р†Р С•Р В·Р Р†РЎР‚Р В°РЎвЂ°Р В°Р ВµРЎвЂљ
        None: Р С—РЎС“РЎРѓРЎвЂљРЎРЉ Р Р†РЎвЂ№Р В·РЎвЂ№Р Р†Р В°РЎР‹РЎвЂ°Р С‘Р в„– Р С”Р С•Р Т‘ Р С—Р С•Р С”Р В°Р В¶Р ВµРЎвЂљ Р С—Р С•Р В»РЎРЉР В·Р С•Р Р†Р В°РЎвЂљР ВµР В»РЎР‹ Р С•РЎРѓР СРЎвЂ№РЎРѓР В»Р ВµР Р…Р Р…РЎС“РЎР‹ Р С•РЎв‚¬Р С‘Р В±Р С”РЎС“, Р В° Р Р…Р Вµ
        Р Р†РЎвЂ№Р Т‘Р В°РЎРѓРЎвЂљ Р В±Р С‘РЎвЂљРЎвЂ№Р в„– URL.

        Args:
            sub_id: Subscription ID Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР В°

        Returns:
            Р СџР С•Р В»Р Р…РЎвЂ№Р в„– URL Р Р†Р С‘Р Т‘Р В° 'https://host:2096/sub/{sub_id}' Р С‘Р В»Р С‘ None.
        """
        settings = await self.get_panel_settings()
        if not settings:
            logger.warning(
                f"build_subscription_url: Р Р…Р Вµ РЎС“Р Т‘Р В°Р В»Р С•РЎРѓРЎРЉ Р С—Р С•Р В»РЎС“РЎвЂЎР С‘РЎвЂљРЎРЉ Р Р…Р В°РЎРѓРЎвЂљРЎР‚Р С•Р в„–Р С”Р С‘ Р С—Р В°Р Р…Р ВµР В»Р С‘ "
                f"{self.server.get('name', self.server_id)}; URL Р Р…Р Вµ РЎРѓРЎвЂљРЎР‚Р С•Р С‘РЎвЂљРЎРѓРЎРЏ."
            )
            return None

        # Р СџР С•Р Т‘Р С—Р С‘РЎРѓР С”Р В° Р Р†Р С•Р С•Р В±РЎвЂ°Р Вµ Р Р†Р С”Р В»РЎР‹РЎвЂЎР ВµР Р…Р В°?
        if not settings.get("subEnable"):
            logger.warning(
                f"build_subscription_url: Р Р…Р В° Р С—Р В°Р Р…Р ВµР В»Р С‘ {self.server.get('name', self.server_id)} "
                f"subscription Р С•РЎвЂљР С”Р В»РЎР‹РЎвЂЎР ВµР Р…Р В° (subEnable=false). Р вЂ™Р С”Р В»РЎР‹РЎвЂЎР С‘РЎвЂљР Вµ Р ВµРЎвЂ Р Р† Р Р…Р В°РЎРѓРЎвЂљРЎР‚Р С•Р в„–Р С”Р В°РЎвЂ¦ 3X-UI."
            )
            return None

        # Р вЂўРЎРѓР В»Р С‘ Р В°Р Т‘Р СР С‘Р Р… Р В·Р В°Р Т‘Р В°Р В» Р С”Р В°РЎРѓРЎвЂљР С•Р СР Р…РЎвЂ№Р в„– subURI РІР‚вЂќ РЎРЊРЎвЂљР С• Р С–Р С•РЎвЂљР С•Р Р†РЎвЂ№Р в„– Р С—РЎР‚Р ВµРЎвЂћР С‘Р С”РЎРѓ, Р Т‘Р С•Р В±Р В°Р Р†Р В»РЎРЏР ВµР С РЎвЂљР С•Р В»РЎРЉР С”Р С• sub_id.
        sub_uri = (settings.get("subURI") or "").strip()
        if sub_uri:
            if not sub_uri.endswith("/"):
                sub_uri = sub_uri + "/"
            return f"{sub_uri}{sub_id}"

        # Р РЋР С•Р В±Р С‘РЎР‚Р В°Р ВµР С URL Р С‘Р В· Р С”Р С•Р СР С—Р С•Р Р…Р ВµР Р…РЎвЂљ.
        from urllib.parse import urlparse
        sub_domain = (settings.get("subDomain") or "").strip()
        if not sub_domain:
            # Р вЂР ВµРЎР‚РЎвЂР С РЎвЂ¦Р С•РЎРѓРЎвЂљ Р С—Р В°Р Р…Р ВµР В»Р С‘ (Р В±Р ВµР В· http://)
            parsed = urlparse(self.base_url)
            sub_domain = parsed.hostname or self.host

        sub_port = settings.get("subPort") or 0
        try:
            sub_port = int(sub_port)
        except (TypeError, ValueError):
            sub_port = 0

        # Р СџРЎС“РЎвЂљРЎРЉ: 3X-UI Р С”Р В»Р В°Р Т‘РЎвЂРЎвЂљ Р ВµР С–Р С• Р С”Р В°Р С” '/sub/' Р С‘Р В»Р С‘ 'sub/' РІР‚вЂќ Р Р…Р С•РЎР‚Р СР В°Р В»Р С‘Р В·РЎС“Р ВµР С.
        sub_path = settings.get("subPath") or "/"
        if not sub_path.startswith("/"):
            sub_path = "/" + sub_path
        if not sub_path.endswith("/"):
            sub_path = sub_path + "/"

        # Р РЋРЎвЂ¦Р ВµР СР В°: HTTPS Р ВµРЎРѓР В»Р С‘ РЎС“ sub-server Р В·Р В°Р Т‘Р В°Р Р… РЎРѓР ВµРЎР‚РЎвЂљР С‘РЎвЂћР С‘Р С”Р В°РЎвЂљ, Р С‘Р Р…Р В°РЎвЂЎР Вµ HTTP.
        # subKeyFile + subCertFile Р Р†Р СР ВµРЎРѓРЎвЂљР Вµ Р С•Р В·Р Р…Р В°РЎвЂЎР В°РЎР‹РЎвЂљ TLS Р Р…Р В° sub-port.
        cert_file = (settings.get("subCertFile") or "").strip()
        key_file = (settings.get("subKeyFile") or "").strip()
        scheme = "https" if (cert_file and key_file) else "http"

        port_part = f":{sub_port}" if sub_port and sub_port not in (80 if scheme == "http" else 443,) else ""
        return f"{scheme}://{sub_domain}{port_part}{sub_path}{sub_id}"


    async def update_client_traffic_limit(
        self,
        inbound_id: int,
        client_uuid: str,
        email: str,
        total_gb: int
    ) -> bool:
        return await self._run_with_stale_profile_retry(
            lambda: self._update_client_traffic_limit_impl(
                inbound_id=inbound_id,
                client_uuid=client_uuid,
                email=email,
                total_gb=total_gb,
            )
        )

    async def _update_client_traffic_limit_impl(
        self,
        inbound_id: int,
        client_uuid: str,
        email: str,
        total_gb: int
    ) -> bool:
        """
        Р С›Р В±Р Р…Р С•Р Р†Р В»РЎРЏР ВµРЎвЂљ Р В»Р С‘Р СР С‘РЎвЂљ РЎвЂљРЎР‚Р В°РЎвЂћР С‘Р С”Р В° РЎРѓРЎС“РЎвЂ°Р ВµРЎРѓРЎвЂљР Р†РЎС“РЎР‹РЎвЂ°Р ВµР С–Р С• Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР В°.
        
        Args:
            inbound_id: ID inbound-Р С—Р С•Р Т‘Р С”Р В»РЎР‹РЎвЂЎР ВµР Р…Р С‘РЎРЏ
            client_uuid: UUID Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР В°
            email: Email/Р С‘Р Т‘Р ВµР Р…РЎвЂљР С‘РЎвЂћР С‘Р С”Р В°РЎвЂљР С•РЎР‚ Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР В°
            total_gb: Р СњР С•Р Р†РЎвЂ№Р в„– Р В»Р С‘Р СР С‘РЎвЂљ РЎвЂљРЎР‚Р В°РЎвЂћР С‘Р С”Р В° Р Р† Р вЂњР вЂ (0 = Р В±Р ВµР В· Р В»Р С‘Р СР С‘РЎвЂљР В°)
            
        Returns:
            True Р С—РЎР‚Р С‘ РЎС“РЎРѓР С—Р ВµРЎв‚¬Р Р…Р С•Р С Р С•Р В±Р Р…Р С•Р Р†Р В»Р ВµР Р…Р С‘Р С‘
        """
        profile = await self._ensure_api_profile()
        if profile == API_PROFILE_CLIENTS:
            return await self.update_client_limit(
                inbound_id=inbound_id,
                client_uuid=client_uuid,
                email=email,
                total_gb_bytes=total_gb * 1024 * 1024 * 1024 if total_gb > 0 else 0,
            )

        # Р СџР С•Р В»РЎС“РЎвЂЎР В°Р ВµР С РЎвЂљР ВµР С”РЎС“РЎвЂ°Р С‘Р Вµ Р Т‘Р В°Р Р…Р Р…РЎвЂ№Р Вµ Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР В°
        inbounds = await self.get_inbounds()
        target_inbound = None
        target_client = None
        
        for inbound in inbounds:
            if inbound.get('id') == inbound_id:
                target_inbound = inbound
                settings = self._load_json_field(inbound.get('settings', '{}'))
                clients = settings.get('clients', [])
                
                for client in clients:
                    if client.get('id') == client_uuid:
                        target_client = client
                        break
                break
        
        if not target_inbound or not target_client:
            raise VPNAPIError(f"Р С™Р В»Р С‘Р ВµР Р…РЎвЂљ {email} Р Р…Р Вµ Р Р…Р В°Р в„–Р Т‘Р ВµР Р… Р Р† inbound {inbound_id}")
        
        # Р С›Р В±Р Р…Р С•Р Р†Р В»РЎРЏР ВµР С Р В»Р С‘Р СР С‘РЎвЂљ РЎвЂљРЎР‚Р В°РЎвЂћР С‘Р С”Р В°
        total_bytes = total_gb * 1024 * 1024 * 1024 if total_gb > 0 else 0
        target_client['totalGB'] = total_bytes
        
        # Р В¤Р С•РЎР‚Р СР С‘РЎР‚РЎС“Р ВµР С Р Т‘Р В°Р Р…Р Р…РЎвЂ№Р Вµ Р Т‘Р В»РЎРЏ Р С•Р В±Р Р…Р С•Р Р†Р В»Р ВµР Р…Р С‘РЎРЏ
        update_data = {
            "id": inbound_id,
            "settings": json.dumps({
                "clients": [{
                    "id": target_client.get('id'),
                    "email": target_client.get('email'),
                    "limitIp": target_client.get('limitIp', 1),
                    "totalGB": total_bytes,
                    "expiryTime": target_client.get('expiryTime', 0),
                    "enable": target_client.get('enable', True),
                    "tgId": target_client.get('tgId', ''),
                    "subId": target_client.get('subId', ''),
                    "reset": target_client.get('reset', 0)
                }]
            })
        }
        
        encoded_uuid = urllib.parse.quote(client_uuid, safe='')
        await self._request("POST", f"/panel/api/inbounds/updateClient/{encoded_uuid}", data=update_data)
        logger.info(f"Р С›Р В±Р Р…Р С•Р Р†Р В»Р ВµР Р… Р В»Р С‘Р СР С‘РЎвЂљ РЎвЂљРЎР‚Р В°РЎвЂћР С‘Р С”Р В° Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР В° {email}: {total_gb} Р вЂњР вЂ")
        return True

    async def disable_reset_for_all_clients(self) -> int:
        return await self._run_with_stale_profile_retry(
            self._disable_reset_for_all_clients_impl
        )

    async def _disable_reset_for_all_clients_impl(self) -> int:
        """
        Р С›РЎвЂљР С”Р В»РЎР‹РЎвЂЎР В°Р ВµРЎвЂљ Р В°Р Р†РЎвЂљР С•Р С—РЎР‚Р С•Р Т‘Р В»Р ВµР Р…Р С‘Р Вµ (РЎРѓР В±РЎР‚Р С•РЎРѓ РЎвЂљРЎР‚Р В°РЎвЂћР С‘Р С”Р В°/Р Т‘Р Р…Р ВµР в„–) Р С—РЎР‚Р С‘ Р Р…Р В°РЎРѓРЎвЂљРЎС“Р С—Р В»Р ВµР Р…Р С‘Р С‘ 1-Р С–Р С• РЎвЂЎР С‘РЎРѓР В»Р В° Р СР ВµРЎРѓРЎРЏРЎвЂ Р В° Р Т‘Р В»РЎРЏ Р Р†РЎРѓР ВµРЎвЂ¦ Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР С•Р Р†.
        Р Р€РЎРѓРЎвЂљР В°Р Р…Р В°Р Р†Р В»Р С‘Р Р†Р В°Р ВµРЎвЂљ Р С—Р С•Р В»Р Вµ reset = 0 Р Т‘Р В»РЎРЏ Р Р†РЎРѓР ВµРЎвЂ¦ Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР С•Р Р† Р Р†Р С• Р Р†РЎРѓР ВµРЎвЂ¦ inbounds.
        
        Returns:
            Р С™Р С•Р В»Р С‘РЎвЂЎР ВµРЎРѓРЎвЂљР Р†Р С• Р С•Р В±Р Р…Р С•Р Р†Р В»Р ВµР Р…Р Р…РЎвЂ№РЎвЂ¦ Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР С•Р Р†.
        """
        profile = await self._ensure_api_profile()
        if profile == API_PROFILE_CLIENTS:
            updated_count = 0
            try:
                result = await self._request("GET", "/panel/api/clients/list", retry=False, log_error=False)
                rows = result.get("obj") or []
            except Exception:
                rows = []
            if not isinstance(rows, list):
                return 0
            for row in rows:
                if not isinstance(row, dict) or row.get("reset", 0) == 0:
                    continue
                email = row.get("email")
                if not email:
                    continue
                payload = self._build_client_payload_from_record(row, fallback_email=email)
                payload["reset"] = 0
                try:
                    encoded_email = urllib.parse.quote(email, safe="")
                    await self._request(
                        "POST",
                        f"/panel/api/clients/update/{encoded_email}",
                        data=payload,
                    )
                    updated_count += 1
                except Exception as e:
                    logger.error(f"Р С›РЎв‚¬Р С‘Р В±Р С”Р В° Р С—РЎР‚Р С‘ Р С•РЎвЂљР С”Р В»РЎР‹РЎвЂЎР ВµР Р…Р С‘Р С‘ Р В°Р Р†РЎвЂљР С•Р С—РЎР‚Р С•Р Т‘Р В»Р ВµР Р…Р С‘РЎРЏ Р Т‘Р В»РЎРЏ Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР В° {email}: {e}")
            return updated_count

        updated_count = 0
        inbounds = await self.get_inbounds()
        
        for inbound in inbounds:
            settings = self._load_json_field(inbound.get('settings', '{}'))
            clients = settings.get('clients', [])
            
            for client in clients:
                if client.get('reset', 0) != 0:  # РЎвЂљР С•Р В»РЎРЉР С”Р С• Р ВµРЎРѓР В»Р С‘ reset Р Р…Р Вµ 0
                    
                    # clientId РІР‚вЂќ РЎРЊРЎвЂљР С• id(uuid) Р Т‘Р В»РЎРЏ vless/vmess, password Р Т‘Р В»РЎРЏ trojan/shadowsocks
                    client_id = client.get('id') or client.get('password')
                    
                    if client_id:
                        # Р В¤Р С•РЎР‚Р СР С‘РЎР‚РЎС“Р ВµР С Р С—РЎР‚Р В°Р Р†Р С‘Р В»РЎРЉР Р…РЎС“РЎР‹ РЎРѓРЎвЂљРЎР‚РЎС“Р С”РЎвЂљРЎС“РЎР‚РЎС“ Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР В° Р Т‘Р В»РЎРЏ Р С•Р В±Р Р…Р С•Р Р†Р В»Р ВµР Р…Р С‘РЎРЏ, РЎРѓР С•РЎвЂ¦РЎР‚Р В°Р Р…РЎРЏРЎРЏ Р Р…РЎС“Р В¶Р Р…РЎвЂ№Р Вµ Р С—Р С•Р В»РЎРЏ
                        updated_client = {
                            "id": client.get('id', ''),
                            "password": client.get('password', ''),
                            "flow": client.get('flow', ''),
                            "email": client.get('email', ''),
                            "limitIp": client.get('limitIp', 1),
                            "totalGB": client.get('totalGB', 0),
                            "expiryTime": client.get('expiryTime', 0),
                            "enable": client.get('enable', True),
                            "tgId": client.get('tgId', ''),
                            "subId": client.get('subId', ''),
                            "reset": 0  # Р РЋР В±РЎР‚Р В°РЎРѓРЎвЂ№Р Р†Р В°Р ВµР С reset
                        }
                        
                        # Р Р€Р Т‘Р В°Р В»РЎРЏР ВµР С Р С—РЎС“РЎРѓРЎвЂљРЎвЂ№Р Вµ Р С—Р С•Р В»РЎРЏ (Р Р†Р В°Р В¶Р Р…Р С• Р Т‘Р В»РЎРЏ РЎР‚Р В°Р В·Р Р…РЎвЂ№РЎвЂ¦ Р С—РЎР‚Р С•РЎвЂљР С•Р С”Р С•Р В»Р С•Р Р†)
                        updated_client = {k: v for k, v in updated_client.items() if v != ''}
                        
                        client_data = {
                            "id": inbound['id'],
                            "settings": json.dumps({"clients": [updated_client]})
                        }
                        
                        try:
                            # Р вЂ™ 3x-ui Р СРЎвЂ№ Р С•РЎвЂљР С—РЎР‚Р В°Р Р†Р В»РЎРЏР ВµР С POST /panel/api/inbounds/updateClient/:clientId
                            # Р С’ Р Р† РЎвЂљР ВµР В»Р Вµ Р В·Р В°Р С—РЎР‚Р С•РЎРѓР В° Р С—Р ВµРЎР‚Р ВµР Т‘Р В°Р ВµР С id Р С‘Р Р…Р В±Р В°РЎС“Р Р…Р Т‘Р В° Р С‘ Р Р…Р С•Р Р†РЎвЂ№Р в„– Р С•Р В±РЎР‰Р ВµР С”РЎвЂљ clients
                            # Р С™Р С•Р Т‘Р С‘РЎР‚РЎС“Р ВµР С ID/Р С—Р В°РЎР‚Р С•Р В»РЎРЉ Р Т‘Р В»РЎРЏ URL, РЎвЂЎРЎвЂљР С•Р В±РЎвЂ№ РЎРѓР В»Р ВµРЎв‚¬Р С‘ Р Р† base64 (Shadowsocks) Р Р…Р Вµ Р В»Р С•Р СР В°Р В»Р С‘ HTTP-Р СР В°РЎР‚РЎв‚¬РЎР‚РЎС“РЎвЂљР С‘Р В·Р В°РЎвЂ Р С‘РЎР‹
                            encoded_id = urllib.parse.quote(client_id, safe='')
                            await self._request(
                                "POST",
                                f"/panel/api/inbounds/updateClient/{encoded_id}",
                                data=client_data
                            )
                            updated_count += 1
                            logger.info(f"Р С›РЎвЂљР С”Р В»РЎР‹РЎвЂЎР ВµР Р…Р С• Р В°Р Р†РЎвЂљР С•Р С—РЎР‚Р С•Р Т‘Р В»Р ВµР Р…Р С‘Р Вµ (reset=0) Р Т‘Р В»РЎРЏ Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР В° {client.get('email', client_id)}")
                        except StaleAPIProfileError:
                            raise
                        except Exception as e:
                            logger.error(f"Р С›РЎв‚¬Р С‘Р В±Р С”Р В° Р С—РЎР‚Р С‘ Р С•РЎвЂљР С”Р В»РЎР‹РЎвЂЎР ВµР Р…Р С‘Р С‘ Р В°Р Р†РЎвЂљР С•Р С—РЎР‚Р С•Р Т‘Р В»Р ВµР Р…Р С‘РЎРЏ Р Т‘Р В»РЎРЏ Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР В° {client.get('email', client_id)}: {e}")
                            
        return updated_count

    async def update_client_full(
        self,
        inbound_id: int,
        client_uuid: str,
        email: str,
        expiry_time_ms: int,
        total_gb_bytes: int,
        enable: Optional[bool] = None,
        sub_id: Optional[str] = None,
    ) -> bool:
        return await self._run_with_stale_profile_retry(
            lambda: self._update_client_full_impl(
                inbound_id=inbound_id,
                client_uuid=client_uuid,
                email=email,
                expiry_time_ms=expiry_time_ms,
                total_gb_bytes=total_gb_bytes,
                enable=enable,
                sub_id=sub_id,
            )
        )

    async def _update_client_full_impl(
        self,
        inbound_id: int,
        client_uuid: str,
        email: str,
        expiry_time_ms: int,
        total_gb_bytes: int,
        enable: Optional[bool] = None,
        sub_id: Optional[str] = None,
    ) -> bool:
        """
        Р С›Р В±Р Р…Р С•Р Р†Р В»РЎРЏР ВµРЎвЂљ Р вЂ™Р РЋР вЂў Р С—Р В°РЎР‚Р В°Р СР ВµРЎвЂљРЎР‚РЎвЂ№ Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР В° Р Р…Р В° Р С—Р В°Р Р…Р ВµР В»Р С‘ Р Т‘Р В°Р Р…Р Р…РЎвЂ№Р СР С‘ Р С‘Р В· Р Р…Р В°РЎв‚¬Р ВµР в„– Р вЂР вЂќ.
        Р вЂўР Т‘Р С‘Р Р…РЎРѓРЎвЂљР Р†Р ВµР Р…Р Р…Р В°РЎРЏ РЎвЂћРЎС“Р Р…Р С”РЎвЂ Р С‘РЎРЏ Р В·Р В°Р С—Р С‘РЎРѓР С‘ Р Р…Р В° Р С—Р В°Р Р…Р ВµР В»РЎРЉ (Р С”РЎР‚Р С•Р СР Вµ РЎРѓР С•Р В·Р Т‘Р В°Р Р…Р С‘РЎРЏ/РЎС“Р Т‘Р В°Р В»Р ВµР Р…Р С‘РЎРЏ).
        
        Р СџРЎР‚Р С•РЎвЂљР С•Р С”Р С•Р В»РЎРЉР Р…РЎвЂ№Р Вµ Р С—Р С•Р В»РЎРЏ (flow, limitIp, tgId) РЎвЂЎР С‘РЎвЂљР В°РЎР‹РЎвЂљРЎРѓРЎРЏ РЎРѓ Р С—Р В°Р Р…Р ВµР В»Р С‘,
        Р Р…Р С• expiryTime, totalGB, enable Р С‘ subId Р С—РЎР‚Р С‘ РЎРЏР Р†Р Р…Р С•Р в„– Р С—Р ВµРЎР‚Р ВµР Т‘Р В°РЎвЂЎР Вµ Р В±Р ВµРЎР‚РЎС“РЎвЂљРЎРѓРЎРЏ
        Р С‘Р В· Р С—Р В°РЎР‚Р В°Р СР ВµРЎвЂљРЎР‚Р С•Р Р† (Р С‘Р В· Р Р…Р В°РЎв‚¬Р ВµР в„– Р вЂР вЂќ).
        
        Args:
            inbound_id: ID inbound-Р С—Р С•Р Т‘Р С”Р В»РЎР‹РЎвЂЎР ВµР Р…Р С‘РЎРЏ
            client_uuid: UUID Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР В°
            email: Email/Р С‘Р Т‘Р ВµР Р…РЎвЂљР С‘РЎвЂћР С‘Р С”Р В°РЎвЂљР С•РЎР‚ Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР В°
            expiry_time_ms: Р РЋРЎР‚Р С•Р С” Р Т‘Р ВµР в„–РЎРѓРЎвЂљР Р†Р С‘РЎРЏ Р Р† Р СР С‘Р В»Р В»Р С‘РЎРѓР ВµР С”РЎС“Р Р…Р Т‘Р В°РЎвЂ¦ (Р С‘Р В· Р Р…Р В°РЎв‚¬Р ВµР в„– Р вЂР вЂќ, 0 = Р В±Р ВµРЎРѓРЎРѓРЎР‚Р С•РЎвЂЎР Р…РЎвЂ№Р в„–)
            total_gb_bytes: Р вЂєР С‘Р СР С‘РЎвЂљ РЎвЂљРЎР‚Р В°РЎвЂћР С‘Р С”Р В° Р Р† Р В±Р В°Р в„–РЎвЂљР В°РЎвЂ¦ (Р С‘Р В· Р Р…Р В°РЎв‚¬Р ВµР в„– Р вЂР вЂќ, 0 = Р В±Р ВµР В·Р В»Р С‘Р СР С‘РЎвЂљ)
            enable: Р Р‡Р Р†Р Р…РЎвЂ№Р в„– РЎРѓРЎвЂљР В°РЎвЂљРЎС“РЎРѓ Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР В°. None = РЎРѓР С•РЎвЂ¦РЎР‚Р В°Р Р…Р С‘РЎвЂљРЎРЉ РЎвЂљР ВµР С”РЎС“РЎвЂ°Р ВµР Вµ Р В·Р Р…Р В°РЎвЂЎР ВµР Р…Р С‘Р Вµ Р С—Р В°Р Р…Р ВµР В»Р С‘
            sub_id: Р Р‡Р Р†Р Р…РЎвЂ№Р в„– subscription ID. None = РЎРѓР С•РЎвЂ¦РЎР‚Р В°Р Р…Р С‘РЎвЂљРЎРЉ РЎвЂљР ВµР С”РЎС“РЎвЂ°Р ВµР Вµ Р В·Р Р…Р В°РЎвЂЎР ВµР Р…Р С‘Р Вµ Р С—Р В°Р Р…Р ВµР В»Р С‘
            
        Returns:
            True Р С—РЎР‚Р С‘ РЎС“РЎРѓР С—Р ВµРЎв‚¬Р Р…Р С•Р С Р С•Р В±Р Р…Р С•Р Р†Р В»Р ВµР Р…Р С‘Р С‘
        """
        profile = await self._ensure_api_profile()
        if profile == API_PROFILE_CLIENTS:
            record = await self._get_clients_api_record(email, log_error=False)
            target_client = None
            if record:
                target_client, _ = self._split_clients_api_record(record)
            if not target_client:
                _, target_client = await self._find_panel_client(
                    inbound_id=inbound_id,
                    client_uuid=client_uuid,
                    email=email,
                )
            if not target_client:
                raise VPNAPIError(f"Р С™Р В»Р С‘Р ВµР Р…РЎвЂљ {email} Р Р…Р Вµ Р Р…Р В°Р в„–Р Т‘Р ВµР Р… Р Р† clients API")

            updated_client = self._build_client_payload_from_record(
                target_client,
                fallback_email=email,
                fallback_uuid=client_uuid,
            )
            updated_client["email"] = email
            updated_client["totalGB"] = total_gb_bytes
            updated_client["expiryTime"] = expiry_time_ms
            updated_client["enable"] = updated_client.get("enable", True) if enable is None else enable
            updated_client["subId"] = updated_client.get("subId", "") if sub_id is None else sub_id
            updated_client["reset"] = 0

            encoded_email = urllib.parse.quote(email, safe="")
            await self._request(
                "POST",
                f"/panel/api/clients/update/{encoded_email}",
                data=updated_client,
            )

            from datetime import datetime
            expiry_str = datetime.fromtimestamp(expiry_time_ms / 1000).strftime('%Y-%m-%d %H:%M') if expiry_time_ms > 0 else 'РІв‚¬С›'
            limit_str = f"{total_gb_bytes / 1024**3:.1f} Р вЂњР вЂ" if total_gb_bytes > 0 else 'РІв‚¬С›'
            logger.info(
                f"Р С›Р В±Р Р…Р С•Р Р†Р В»РЎвЂР Р… Р С”Р В»Р С‘Р ВµР Р…РЎвЂљ {email} РЎвЂЎР ВµРЎР‚Р ВµР В· clients API: expiry={expiry_str}, "
                f"limit={limit_str}, enable={updated_client.get('enable')}"
            )
            return True

        # Р В§Р С‘РЎвЂљР В°Р ВµР С РЎвЂљР ВµР С”РЎС“РЎвЂ°Р С‘Р Вµ Р Т‘Р В°Р Р…Р Р…РЎвЂ№Р Вµ Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР В° РЎРѓ Р С—Р В°Р Р…Р ВµР В»Р С‘ РІР‚вЂќ РЎвЂљР С•Р В»РЎРЉР С”Р С• Р Т‘Р В»РЎРЏ Р С—РЎР‚Р С•РЎвЂљР С•Р С”Р С•Р В»РЎРЉР Р…РЎвЂ№РЎвЂ¦ Р С—Р С•Р В»Р ВµР в„–
        inbounds = await self.get_inbounds()
        target_client = None
        
        for inbound in inbounds:
            if inbound.get('id') == inbound_id:
                settings = self._load_json_field(inbound.get('settings', '{}'))
                clients = settings.get('clients', [])
                
                for client in clients:
                    if client.get('id') == client_uuid or client.get('password') == client_uuid:
                        target_client = client
                        break
                break
        
        if not target_client:
            raise VPNAPIError(f"Р С™Р В»Р С‘Р ВµР Р…РЎвЂљ {email} Р Р…Р Вµ Р Р…Р В°Р в„–Р Т‘Р ВµР Р… Р Р† inbound {inbound_id}")
        
        # Р В¤Р С•РЎР‚Р СР С‘РЎР‚РЎС“Р ВµР С Р Т‘Р В°Р Р…Р Р…РЎвЂ№Р Вµ: expiryTime Р С‘ totalGB Р С‘Р В· Р СџР С’Р В Р С’Р СљР вЂўР СћР В Р С›Р вЂ™ (Р Р…Р В°РЎв‚¬Р ВµР в„– Р вЂР вЂќ),
        # Р С•РЎРѓРЎвЂљР В°Р В»РЎРЉР Р…Р С•Р Вµ РІР‚вЂќ Р С‘Р В· РЎвЂљР ВµР С”РЎС“РЎвЂ°Р С‘РЎвЂ¦ Р Т‘Р В°Р Р…Р Р…РЎвЂ№РЎвЂ¦ Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР В° Р Р…Р В° Р С—Р В°Р Р…Р ВµР В»Р С‘
        updated_client = {
            "id": target_client.get('id', ''),
            "password": target_client.get('password', ''),
            "flow": target_client.get('flow', ''),
            "email": target_client.get('email', email),
            "limitIp": target_client.get('limitIp', 1),
            "totalGB": total_gb_bytes,          # РІвЂ С’ Р ВР В· Р Р…Р В°РЎв‚¬Р ВµР в„– Р вЂР вЂќ!
            "expiryTime": expiry_time_ms,        # РІвЂ С’ Р ВР В· Р Р…Р В°РЎв‚¬Р ВµР в„– Р вЂР вЂќ!
            "enable": target_client.get('enable', True) if enable is None else enable,
            "tgId": target_client.get('tgId', ''),
            "subId": target_client.get('subId', '') if sub_id is None else sub_id,
            "reset": 0  # Р СњР Вµ Р С‘РЎРѓР С—Р С•Р В»РЎРЉР В·РЎС“Р ВµР С auto-reset Р С—Р В°Р Р…Р ВµР В»Р С‘
        }
        
        # Р Р€Р Т‘Р В°Р В»РЎРЏР ВµР С Р С—РЎС“РЎРѓРЎвЂљРЎвЂ№Р Вµ РЎРѓРЎвЂљРЎР‚Р С•Р С”Р С•Р Р†РЎвЂ№Р Вµ Р С—Р С•Р В»РЎРЏ (Р Т‘Р В»РЎРЏ РЎР‚Р В°Р В·Р Р…РЎвЂ№РЎвЂ¦ Р С—РЎР‚Р С•РЎвЂљР С•Р С”Р С•Р В»Р С•Р Р†)
        updated_client = {k: v for k, v in updated_client.items() if v != ''}
        
        update_data = {
            "id": inbound_id,
            "settings": json.dumps({"clients": [updated_client]})
        }
        
        encoded_uuid = urllib.parse.quote(client_uuid, safe='')
        await self._request("POST", f"/panel/api/inbounds/updateClient/{encoded_uuid}", data=update_data)
        
        from datetime import datetime
        expiry_str = datetime.fromtimestamp(expiry_time_ms / 1000).strftime('%Y-%m-%d %H:%M') if expiry_time_ms > 0 else 'РІв‚¬С›'
        limit_str = f"{total_gb_bytes / 1024**3:.1f} Р вЂњР вЂ" if total_gb_bytes > 0 else 'РІв‚¬С›'
        logger.info(
            f"Р С›Р В±Р Р…Р С•Р Р†Р В»РЎвЂР Р… Р С”Р В»Р С‘Р ВµР Р…РЎвЂљ {email}: expiry={expiry_str}, "
            f"limit={limit_str}, enable={updated_client.get('enable')}"
        )
        return True

    async def extend_client_expiry(
        self,
        inbound_id: int,
        client_uuid: str,
        email: str,
        days: int
    ) -> bool:
        return await self._run_with_stale_profile_retry(
            lambda: self._extend_client_expiry_impl(
                inbound_id=inbound_id,
                client_uuid=client_uuid,
                email=email,
                days=days,
            )
        )

    async def _extend_client_expiry_impl(
        self,
        inbound_id: int,
        client_uuid: str,
        email: str,
        days: int
    ) -> bool:
        """
        Р СџРЎР‚Р С•Р Т‘Р В»Р ВµР Р†Р В°Р ВµРЎвЂљ РЎРѓРЎР‚Р С•Р С” Р Т‘Р ВµР в„–РЎРѓРЎвЂљР Р†Р С‘РЎРЏ Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР В° Р Р…Р В° РЎС“Р С”Р В°Р В·Р В°Р Р…Р Р…Р С•Р Вµ Р С”Р С•Р В»Р С‘РЎвЂЎР ВµРЎРѓРЎвЂљР Р†Р С• Р Т‘Р Р…Р ВµР в„–.
        Р вЂўРЎРѓР В»Р С‘ РЎРѓРЎР‚Р С•Р С” РЎС“Р В¶Р Вµ Р С‘РЎРѓРЎвЂљР ВµР С”, Р С—РЎР‚Р С‘Р В±Р В°Р Р†Р В»РЎРЏР ВµРЎвЂљ Р Т‘Р Р…Р С‘ Р С” РЎвЂљР ВµР С”РЎС“РЎвЂ°Р ВµР СРЎС“ Р Р†РЎР‚Р ВµР СР ВµР Р…Р С‘.
        
        Args:
            inbound_id: ID inbound-Р С—Р С•Р Т‘Р С”Р В»РЎР‹РЎвЂЎР ВµР Р…Р С‘РЎРЏ
            client_uuid: UUID Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР В°
            email: Email/Р С‘Р Т‘Р ВµР Р…РЎвЂљР С‘РЎвЂћР С‘Р С”Р В°РЎвЂљР С•РЎР‚ Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР В°
            days: Р С™Р С•Р В»Р С‘РЎвЂЎР ВµРЎРѓРЎвЂљР Р†Р С• Р Т‘Р Р…Р ВµР в„– Р Т‘Р В»РЎРЏ Р С—РЎР‚Р С•Р Т‘Р В»Р ВµР Р…Р С‘РЎРЏ
            
        Returns:
            True Р С—РЎР‚Р С‘ РЎС“РЎРѓР С—Р ВµРЎв‚¬Р Р…Р С•Р С Р С•Р В±Р Р…Р С•Р Р†Р В»Р ВµР Р…Р С‘Р С‘
        """
        import time

        profile = await self._ensure_api_profile()
        if profile == API_PROFILE_CLIENTS:
            record = await self._get_clients_api_record(email, log_error=False)
            target_client = None
            if record:
                target_client, _ = self._split_clients_api_record(record)
            if not target_client:
                _, target_client = await self._find_panel_client(
                    inbound_id=inbound_id,
                    client_uuid=client_uuid,
                    email=email,
                )
            if not target_client:
                raise VPNAPIError(f"Р С™Р В»Р С‘Р ВµР Р…РЎвЂљ {email} Р Р…Р Вµ Р Р…Р В°Р в„–Р Т‘Р ВµР Р… Р Р† clients API")

            current_time_ms = int(time.time() * 1000)
            current_expiry = target_client.get('expiryTime', 0)
            extension_ms = days * 86400 * 1000
            if current_expiry == 0:
                new_expiry = 0
            elif current_expiry < current_time_ms:
                new_expiry = current_time_ms + extension_ms
            else:
                new_expiry = current_expiry + extension_ms

            await self.update_client_full(
                inbound_id=inbound_id,
                client_uuid=client_uuid,
                email=email,
                expiry_time_ms=new_expiry,
                total_gb_bytes=target_client.get('totalGB', 0),
                enable=target_client.get('enable', True),
                sub_id=target_client.get('subId', ''),
            )
            logger.info(f"Р СџРЎР‚Р С•Р Т‘Р В»Р ВµР Р… Р С”Р В»РЎР‹РЎвЂЎ Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР В° {email} РЎвЂЎР ВµРЎР‚Р ВµР В· clients API Р Р…Р В° {days} Р Т‘Р Р…Р ВµР в„–. Р СњР С•Р Р†РЎвЂ№Р в„– expiry: {new_expiry}")
            return True
        
        # Р СџР С•Р В»РЎС“РЎвЂЎР В°Р ВµР С РЎвЂљР ВµР С”РЎС“РЎвЂ°Р С‘Р Вµ Р Т‘Р В°Р Р…Р Р…РЎвЂ№Р Вµ Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР В°
        inbounds = await self.get_inbounds()
        target_inbound = None
        target_client = None
        
        for inbound in inbounds:
            if inbound.get('id') == inbound_id:
                target_inbound = inbound
                settings = self._load_json_field(inbound.get('settings', '{}'))
                clients = settings.get('clients', [])
                
                for client in clients:
                    if client.get('id') == client_uuid or client.get('password') == client_uuid:
                        target_client = client
                        break
                break
                
        if not target_inbound or not target_client:
            raise VPNAPIError(f"Р С™Р В»Р С‘Р ВµР Р…РЎвЂљ {email} Р Р…Р Вµ Р Р…Р В°Р в„–Р Т‘Р ВµР Р… Р Р† inbound {inbound_id}")
            
        current_time_ms = int(time.time() * 1000)
        current_expiry = target_client.get('expiryTime', 0)
        
        # Р В Р В°РЎРѓРЎвЂЎР ВµРЎвЂљ Р Р…Р С•Р Р†Р С•Р С–Р С• Р Р†РЎР‚Р ВµР СР ВµР Р…Р С‘ Р С‘РЎРѓРЎвЂљР ВµРЎвЂЎР ВµР Р…Р С‘РЎРЏ
        extension_ms = days * 86400 * 1000
        if current_expiry == 0:
            # Р вЂР ВµРЎРѓР С”Р С•Р Р…Р ВµРЎвЂЎР Р…РЎвЂ№Р в„– Р С”Р В»РЎР‹РЎвЂЎ Р С•РЎРѓРЎвЂљР В°Р ВµРЎвЂљРЎРѓРЎРЏ Р В±Р ВµРЎРѓР С”Р С•Р Р…Р ВµРЎвЂЎР Р…РЎвЂ№Р С
            new_expiry = 0
        elif current_expiry < current_time_ms:
            # Р вЂўРЎРѓР В»Р С‘ Р С”Р В»РЎР‹РЎвЂЎ РЎС“Р В¶Р Вµ Р С‘РЎРѓРЎвЂљР ВµР С”, Р С—РЎР‚Р С‘Р В±Р В°Р Р†Р В»РЎРЏР ВµР С Р С” РЎвЂљР ВµР С”РЎС“РЎвЂ°Р ВµР СРЎС“ Р СР С•Р СР ВµР Р…РЎвЂљРЎС“
            new_expiry = current_time_ms + extension_ms
        else:
            # Р вЂўРЎРѓР В»Р С‘ Р ВµРЎвЂ°Р Вµ Р В°Р С”РЎвЂљР С‘Р Р†Р ВµР Р…, Р С—РЎР‚Р С‘Р В±Р В°Р Р†Р В»РЎРЏР ВµР С Р С” РЎвЂљР ВµР С”РЎС“РЎвЂ°Р ВµР СРЎС“ РЎРѓРЎР‚Р С•Р С”РЎС“ Р С•Р С”Р С•Р Р…РЎвЂЎР В°Р Р…Р С‘РЎРЏ
            new_expiry = current_expiry + extension_ms
            
        target_client['expiryTime'] = new_expiry
        
        # Р В¤Р С•РЎР‚Р СР С‘РЎР‚РЎС“Р ВµР С Р Т‘Р В°Р Р…Р Р…РЎвЂ№Р Вµ Р Т‘Р В»РЎРЏ Р С•Р В±Р Р…Р С•Р Р†Р В»Р ВµР Р…Р С‘РЎРЏ
        update_data = {
            "id": inbound_id,
            "settings": json.dumps({
                "clients": [{
                    "id": target_client.get('id', ''),
                    "password": target_client.get('password', ''),
                    "flow": target_client.get('flow', ''),
                    "email": target_client.get('email', ''),
                    "limitIp": target_client.get('limitIp', 1),
                    "totalGB": target_client.get('totalGB', 0),
                    "expiryTime": new_expiry,
                    "enable": target_client.get('enable', True),
                    "tgId": target_client.get('tgId', ''),
                    "subId": target_client.get('subId', ''),
                    "reset": target_client.get('reset', 0)
                }]
            })
        }
        
        # Р Р€Р Т‘Р В°Р В»РЎРЏР ВµР С Р С—РЎС“РЎРѓРЎвЂљРЎвЂ№Р Вµ Р С—Р С•Р В»РЎРЏ (Р Р†Р В°Р В¶Р Р…Р С• Р Т‘Р В»РЎРЏ РЎР‚Р В°Р В·Р Р…РЎвЂ№РЎвЂ¦ Р С—РЎР‚Р С•РЎвЂљР С•Р С”Р С•Р В»Р С•Р Р†, Р С–Р Т‘Р Вµ id Р С‘Р В»Р С‘ password Р СР С•Р С–РЎС“РЎвЂљ Р С•РЎвЂљРЎРѓРЎС“РЎвЂљРЎРѓРЎвЂљР Р†Р С•Р Р†Р В°РЎвЂљРЎРЉ)
        clients_array = json.loads(update_data["settings"])["clients"][0]
        clients_array = {k: v for k, v in clients_array.items() if v != ''}
        update_data["settings"] = json.dumps({"clients": [clients_array]})
        
        encoded_uuid = urllib.parse.quote(client_uuid, safe='')
        await self._request("POST", f"/panel/api/inbounds/updateClient/{encoded_uuid}", data=update_data)
        logger.info(f"Р СџРЎР‚Р С•Р Т‘Р В»Р ВµР Р… Р С”Р В»РЎР‹РЎвЂЎ Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР В° {email} Р Р…Р В° {days} Р Т‘Р Р…Р ВµР в„–. Р СњР С•Р Р†РЎвЂ№Р в„– expiry: {new_expiry}")
        return True

    async def get_client_config(self, email: str) -> Optional[Dict[str, Any]]:
        """
        Р СџР С•Р В»РЎС“РЎвЂЎР В°Р ВµРЎвЂљ Р С—Р С•Р В»Р Р…РЎС“РЎР‹ Р С”Р С•Р Р…РЎвЂћР С‘Р С–РЎС“РЎР‚Р В°РЎвЂ Р С‘РЎР‹ Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР В° Р Т‘Р В»РЎРЏ Р С—Р С•Р Т‘Р С”Р В»РЎР‹РЎвЂЎР ВµР Р…Р С‘РЎРЏ.
        
        Args:
            email: Email/Р С‘Р Т‘Р ВµР Р…РЎвЂљР С‘РЎвЂћР С‘Р С”Р В°РЎвЂљР С•РЎР‚ Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР В°
            
        Returns:
            Р РЋР В»Р С•Р Р†Р В°РЎР‚РЎРЉ РЎРѓ Р Р…Р В°РЎРѓРЎвЂљРЎР‚Р С•Р в„–Р С”Р В°Р СР С‘ Р С—Р С•Р Т‘Р С”Р В»РЎР‹РЎвЂЎР ВµР Р…Р С‘РЎРЏ Р С‘Р В»Р С‘ None
        """
        try:
            inbounds = await self.get_inbounds()
            for inbound in inbounds:
                settings = self._load_json_field(inbound.get("settings", "{}"))
                clients = settings.get("clients", [])
                
                target_client = None
                for client in clients:
                    if client.get("email") == email:
                        target_client = client
                        break
                
                if target_client:
                    # Р СњР В°РЎв‚¬Р В»Р С‘ Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР В°, Р Р†Р С•Р В·Р Р†РЎР‚Р В°РЎвЂ°Р В°Р ВµР С Р С”Р С•Р Р…РЎвЂћР С‘Р С–РЎС“РЎР‚Р В°РЎвЂ Р С‘РЎР‹
                    stream_settings = self._load_json_field(inbound.get("streamSettings", "{}"))
                    protocol = inbound.get("protocol", "vless")
                    
                    # DEBUG: Р В»Р С•Р С–Р С‘РЎР‚РЎС“Р ВµР С stream_settings Р Т‘Р В»РЎРЏ Р С•РЎвЂљР В»Р В°Р Т‘Р С”Р С‘ Reality-Р С—Р В°РЎР‚Р В°Р СР ВµРЎвЂљРЎР‚Р С•Р Р†
                    logger.debug(f"Stream settings for {email}: {json.dumps(stream_settings, ensure_ascii=False)}")
                    if stream_settings.get("security") == "reality":
                        reality = stream_settings.get("realitySettings", {})
                        logger.info(f"Reality settings for {email}: pbk={reality.get('publicKey')}, sni={reality.get('serverName')}, fp={reality.get('fingerprint')}, shortIds={reality.get('shortIds')}")
                    
                    result = {
                        "uuid": target_client.get("id", ""),
                        "email": target_client.get("email", ""),
                        "port": inbound["port"],
                        "protocol": protocol,
                        "host": self.server["host"],
                        "stream_settings": stream_settings,
                        "inbound_name": inbound.get("remark", "VPN"),
                        "sub_id": target_client.get("subId", ""),
                        "flow": target_client.get("flow", "")
                    }
                    
                    # Р СџРЎР‚Р С•РЎвЂљР С•Р С”Р С•Р В»-РЎРѓР С—Р ВµРЎвЂ Р С‘РЎвЂћР С‘РЎвЂЎР Р…РЎвЂ№Р Вµ Р С—Р С•Р В»РЎРЏ
                    if protocol == 'trojan':
                        result["password"] = target_client.get("password", target_client.get("id", ""))
                    elif protocol == 'shadowsocks':
                        # Р вЂќР В»РЎРЏ Shadowsocks method РЎвЂ¦РЎР‚Р В°Р Р…Р С‘РЎвЂљРЎРѓРЎРЏ Р Р† inbound settings,
                        # Р В° Р С—Р В°РЎР‚Р С•Р В»РЎРЉ РЎС“ Р С”Р В°Р В¶Р Т‘Р С•Р С–Р С• Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР В° РЎРѓР Р†Р С•Р в„– (РЎРѓ fallback Р Р…Р В° Р С•Р В±РЎвЂ°Р С‘Р Вµ)
                        result["method"] = settings.get("method", "aes-256-gcm")
                        result["password"] = target_client.get("password", settings.get("password", ""))
                        result["server_password"] = settings.get("password", "")
                    elif protocol == 'vmess':
                        result["security_method"] = target_client.get("security", "auto")
                    
                    return result
        except Exception as e:
            logger.error(f"Error getting client config for {email}: {e}")
        return None

    async def get_subscription_link(self, sub_id: str) -> Optional[str]:
        """
        Р СџР С•Р В»РЎС“РЎвЂЎР В°Р ВµРЎвЂљ VLESS-РЎРѓРЎРѓРЎвЂ№Р В»Р С”РЎС“ РЎвЂЎР ВµРЎР‚Р ВµР В· endpoint Р С—Р С•Р Т‘Р С—Р С‘РЎРѓР С”Р С‘.
        
        Args:
            sub_id: Subscription ID Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР В°
            
        Returns:
            Р вЂњР С•РЎвЂљР С•Р Р†Р В°РЎРЏ VLESS-РЎРѓРЎРѓРЎвЂ№Р В»Р С”Р В° Р С‘Р В»Р С‘ None Р ВµРЎРѓР В»Р С‘ Р Р…Р Вµ РЎС“Р Т‘Р В°Р В»Р С•РЎРѓРЎРЉ Р С—Р С•Р В»РЎС“РЎвЂЎР С‘РЎвЂљРЎРЉ
        """
        try:
            profile = await self._ensure_api_profile()
            if profile == API_PROFILE_CLIENTS:
                encoded_sub_id = urllib.parse.quote(sub_id, safe="")
                result = await self._request(
                    "GET",
                    f"/panel/api/clients/subLinks/{encoded_sub_id}",
                    retry=False,
                    log_error=False,
                )
                links = result.get("obj")
                if isinstance(links, list):
                    clean_links = [str(link).strip() for link in links if str(link).strip()]
                    if clean_links:
                        return "\n".join(clean_links)
                if isinstance(links, str) and links.strip():
                    return links.strip()
        except Exception as e:
            logger.debug(f"clients API subLinks Р Р…Р Вµ РЎРѓРЎР‚Р В°Р В±Р С•РЎвЂљР В°Р В» Р Т‘Р В»РЎРЏ {sub_id}: {e}")

        session = await self._ensure_session()
        
        # Р РЋРЎвЂљРЎР‚Р С•Р С‘Р С РЎРѓР С—Р С‘РЎРѓР С•Р С” URL Р С”Р В°Р Р…Р Т‘Р С‘Р Т‘Р В°РЎвЂљР С•Р Р†
        # 1. Р РЋ base_path
        # 2. Р вЂР ВµР В· base_path
        # 3. /subscribe/ Р Р†Р СР ВµРЎРѓРЎвЂљР С• /sub/ (Р С‘Р Р…Р С•Р С–Р Т‘Р В° Р В±РЎвЂ№Р Р†Р В°Р ВµРЎвЂљ)
        
        from urllib.parse import urlparse
        parsed = urlparse(self.base_url)
        host_url = f"{parsed.scheme}://{parsed.netloc}"
        
        candidates = [
            f"{self.base_url}/sub/{sub_id}",
            f"{host_url}/sub/{sub_id}",
            f"{self.base_url}/subscribe/{sub_id}",
            f"{host_url}/subscribe/{sub_id}"
        ]
        
        for url in candidates:
            try:
                # Р вЂ™Р В°Р В¶Р Р…Р С•: Р СњР Вµ Р С‘РЎРѓР С—Р С•Р В»РЎРЉР В·РЎС“Р ВµР С _request, РЎвЂљР В°Р С” Р С”Р В°Р С” РЎРЊРЎвЂљР С• Р С—РЎС“Р В±Р В»Р С‘РЎвЂЎР Р…РЎвЂ№Р в„– endpoint
                async with session.get(url, ssl=False) as response:
                    logger.info(f"Sub URL probe: {url} -> {response.status}")

                    if response.status == 200:
                        text = await response.text()
                        text = text.strip()

                        # Р вЂўРЎРѓР В»Р С‘ Р Р†Р ВµРЎР‚Р Р…РЎС“Р В» VLESS
                        if text.startswith("vless://") or text.startswith("vmess://") or text.startswith("trojan://"):
                            return text

                        # Р вЂўРЎРѓР В»Р С‘ Р Р†Р ВµРЎР‚Р Р…РЎС“Р В» base64
                        try:
                            import base64
                            # Р вЂќР С•Р В±Р В°Р Р†Р В»РЎРЏР ВµР С Р С—Р В°Р Т‘Р Т‘Р С‘Р Р…Р С– Р ВµРЎРѓР В»Р С‘ Р Р…РЎС“Р В¶Р Р…Р С•
                            missing_padding = len(text) % 4
                            if missing_padding:
                                text += '=' * (4 - missing_padding)
                            decoded = base64.b64decode(text).decode('utf-8').strip()
                            if decoded.startswith("vless://") or decoded.startswith("vmess://") or decoded.startswith("trojan://"):
                                return decoded
                        except:
                            # Р вЂєР С•Р С–Р С‘РЎР‚РЎС“Р ВµР С, Р ВµРЎРѓР В»Р С‘ РЎРЊРЎвЂљР С• РЎвЂЎРЎвЂљР С•-РЎвЂљР С• РЎРѓРЎвЂљРЎР‚Р В°Р Р…Р Р…Р С•Р Вµ
                            if len(text) < 200:
                                logger.debug(f"Unknown response text: {text}")
                            pass
            except Exception as e:
                logger.warning(f"Р С›РЎв‚¬Р С‘Р В±Р С”Р В° Р С—Р С•Р В»РЎС“РЎвЂЎР ВµР Р…Р С‘РЎРЏ Р С—Р С•Р Т‘Р С—Р С‘РЎРѓР С”Р С‘ ({url}): {e}")

        return None

    async def get_database_backup(self) -> bytes:
        """
        Р РЋР С”Р В°РЎвЂЎР С‘Р Р†Р В°Р ВµРЎвЂљ РЎР‚Р ВµР В·Р ВµРЎР‚Р Р†Р Р…РЎС“РЎР‹ Р С”Р С•Р С—Р С‘РЎР‹ Р В±Р В°Р В·РЎвЂ№ Р Т‘Р В°Р Р…Р Р…РЎвЂ№РЎвЂ¦ Р С—Р В°Р Р…Р ВµР В»Р С‘.
        
        Endpoint: GET /panel/api/server/getDb (Р С‘Р В»Р С‘ РЎвЂћР С•Р В»Р В±РЎРЊР С”Р С‘)
        
        Returns:
            Р вЂР С‘Р Р…Р В°РЎР‚Р Р…РЎвЂ№Р Вµ Р Т‘Р В°Р Р…Р Р…РЎвЂ№Р Вµ РЎвЂћР В°Р в„–Р В»Р В° x-ui.db
            
        Raises:
            VPNAPIError: Р СџРЎР‚Р С‘ Р С•РЎв‚¬Р С‘Р В±Р С”Р Вµ РЎРѓР С”Р В°РЎвЂЎР С‘Р Р†Р В°Р Р…Р С‘РЎРЏ
        """
        session = await self._ensure_session()

        # Р С’Р Р†РЎвЂљР С•РЎР‚Р С‘Р В·РЎС“Р ВµР СРЎРѓРЎРЏ Р ВµРЎРѓР В»Р С‘ Р Р…РЎС“Р В¶Р Р…Р С•
        if not self.is_authenticated:
            await self.login()

        headers = {
            "Accept": "application/octet-stream",
            "X-Requested-With": "XMLHttpRequest"
        }
        # Р СњР В° v3.0+ РЎвЂЎР ВµРЎР‚Р ВµР В· Bearer РІР‚вЂќ Р С•Р В±РЎвЂ¦Р С•Р Т‘Р С‘Р С Р Р…Р ВµР С•Р В±РЎвЂ¦Р С•Р Т‘Р С‘Р СР С•РЎРѓРЎвЂљРЎРЉ Р Р† cookie + CSRF
        if self.panel_mode == 'bearer' and self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"

        # Р В Р В°Р В·Р Р…РЎвЂ№Р Вµ Р Р†Р ВµРЎР‚РЎРѓР С‘Р С‘ X-UI / 3X-UI Р С‘РЎРѓР С—Р С•Р В»РЎРЉР В·РЎС“РЎР‹РЎвЂљ РЎР‚Р В°Р В·Р Р…РЎвЂ№Р Вµ Р С—РЎС“РЎвЂљР С‘ Р Т‘Р В»РЎРЏ РЎРѓР С”Р В°РЎвЂЎР С‘Р Р†Р В°Р Р…Р С‘РЎРЏ Р вЂР вЂќ
        endpoints = [
            "/panel/api/server/getDb",
            "/panel/setting/getDb",
            "/panel/api/getDb",
            "/server/getDb"
        ]
        
        last_status = None
        for endpoint in endpoints:
            url = f"{self.base_url}{endpoint}"
            endpoint_headers = dict(headers)
            if endpoint.startswith("/panel/setting/"):
                await self._ensure_cookie_auth()
                session = await self._ensure_session()
                endpoint_headers = {
                    "Accept": "application/octet-stream",
                    "X-Requested-With": "XMLHttpRequest",
                }
                if self.csrf_token:
                    endpoint_headers["X-CSRF-Token"] = self.csrf_token
            try:
                async with session.get(url, headers=endpoint_headers) as response:
                    last_status = response.status
                    if response.status == 200:
                        data = await response.read()
                        
                        # Р СџРЎР‚Р С•Р Р†Р ВµРЎР‚РЎРЏР ВµР С, РЎвЂЎРЎвЂљР С• РЎРѓР С”Р В°РЎвЂЎР В°Р В»РЎРѓРЎРЏ Р Т‘Р ВµР в„–РЎРѓРЎвЂљР Р†Р С‘РЎвЂљР ВµР В»РЎРЉР Р…Р С• SQLite РЎвЂћР В°Р в„–Р В»
                        # SQLite РЎвЂћР В°Р в„–Р В»РЎвЂ№ Р Р†РЎРѓР ВµР С–Р Т‘Р В° Р Р…Р В°РЎвЂЎР С‘Р Р…Р В°РЎР‹РЎвЂљРЎРѓРЎРЏ РЎРѓ Р В±Р В°Р в„–РЎвЂљР С•Р Р† 'SQLite format 3\000'
                        if data.startswith(b'SQLite format 3\x00'):
                            logger.info(f"Р РЋР С”Р В°РЎвЂЎР В°Р Р… Р В±РЎРЊР С”Р В°Р С— Р вЂР вЂќ Р С—Р В°Р Р…Р ВµР В»Р С‘ ({endpoint}): {len(data)} Р В±Р В°Р в„–РЎвЂљ")
                            return data
                        else:
                            text = data[:100].decode(errors='ignore')
                            logger.debug(f"Endpoint {endpoint} Р Р†Р ВµРЎР‚Р Р…РЎС“Р В» Р Р…Р Вµ Р вЂР вЂќ, Р В°: {text}...")
            except aiohttp.ClientError as e:
                logger.debug(f"Р С›РЎв‚¬Р С‘Р В±Р С”Р В° HTTP Р С—РЎР‚Р С‘ Р С—РЎР‚Р С•Р Р†Р ВµРЎР‚Р С”Р Вµ {endpoint}: {e}")
                
        raise VPNAPIError(f"Р С›РЎв‚¬Р С‘Р В±Р С”Р В° РЎРѓР С”Р В°РЎвЂЎР С‘Р Р†Р В°Р Р…Р С‘РЎРЏ Р В±РЎРЊР С”Р В°Р С—Р В°: Р Р…Р С‘ Р С•Р Т‘Р С‘Р Р… endpoint Р Р…Р Вµ Р Р†Р ВµРЎР‚Р Р…РЎС“Р В» РЎвЂћР В°Р в„–Р В» Р вЂР вЂќ. Р СџР С•РЎРѓР В»Р ВµР Т‘Р Р…Р С‘Р в„– HTTP РЎРѓРЎвЂљР В°РЎвЂљРЎС“РЎРѓ: {last_status}")

    async def reset_client_traffic(self, inbound_id: int, email: str) -> bool:
        return await self._run_with_stale_profile_retry(
            lambda: self._reset_client_traffic_impl(inbound_id, email)
        )

    async def _reset_client_traffic_impl(self, inbound_id: int, email: str) -> bool:
        """
        Р РЋР В±РЎР‚Р В°РЎРѓРЎвЂ№Р Р†Р В°Р ВµРЎвЂљ РЎРѓРЎвЂЎРЎвЂРЎвЂљРЎвЂЎР С‘Р С”Р С‘ РЎвЂљРЎР‚Р В°РЎвЂћР С‘Р С”Р В° (up/down) Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР В° Р Р…Р В° Р С—Р В°Р Р…Р ВµР В»Р С‘.
        
        Endpoint: POST /panel/api/inbounds/{inbound_id}/resetClientTraffic/{email}
        
        Args:
            inbound_id: ID inbound-Р С—Р С•Р Т‘Р С”Р В»РЎР‹РЎвЂЎР ВµР Р…Р С‘РЎРЏ
            email: Email/Р С‘Р Т‘Р ВµР Р…РЎвЂљР С‘РЎвЂћР С‘Р С”Р В°РЎвЂљР С•РЎР‚ Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР В°
            
        Returns:
            True Р С—РЎР‚Р С‘ РЎС“РЎРѓР С—Р ВµРЎв‚¬Р Р…Р С•Р С РЎРѓР В±РЎР‚Р С•РЎРѓР Вµ
        """
        profile = await self._ensure_api_profile()
        encoded_email = urllib.parse.quote(email, safe='')
        if profile == API_PROFILE_CLIENTS:
            await self._request("POST", f"/panel/api/clients/resetTraffic/{encoded_email}")
        else:
            await self._request(
                "POST",
                f"/panel/api/inbounds/{inbound_id}/resetClientTraffic/{encoded_email}"
            )
        logger.info(f"Р РЋР В±РЎР‚Р С•РЎв‚¬Р ВµР Р… РЎвЂљРЎР‚Р В°РЎвЂћР С‘Р С” Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР В° {email} (inbound {inbound_id})")
        return True

    async def update_client_limit(
        self,
        inbound_id: int,
        client_uuid: str,
        email: str,
        total_gb_bytes: int
    ) -> bool:
        return await self._run_with_stale_profile_retry(
            lambda: self._update_client_limit_impl(
                inbound_id=inbound_id,
                client_uuid=client_uuid,
                email=email,
                total_gb_bytes=total_gb_bytes,
            )
        )

    async def _update_client_limit_impl(
        self,
        inbound_id: int,
        client_uuid: str,
        email: str,
        total_gb_bytes: int
    ) -> bool:
        """
        Р С›Р В±Р Р…Р С•Р Р†Р В»РЎРЏР ВµРЎвЂљ Р В»Р С‘Р СР С‘РЎвЂљ РЎвЂљРЎР‚Р В°РЎвЂћР С‘Р С”Р В° (totalGB) Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР В° Р Р…Р В° Р С—Р В°Р Р…Р ВµР В»Р С‘.
        
        Args:
            inbound_id: ID inbound-Р С—Р С•Р Т‘Р С”Р В»РЎР‹РЎвЂЎР ВµР Р…Р С‘РЎРЏ
            client_uuid: UUID Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР В°
            email: Email/Р С‘Р Т‘Р ВµР Р…РЎвЂљР С‘РЎвЂћР С‘Р С”Р В°РЎвЂљР С•РЎР‚ Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР В°
            total_gb_bytes: Р СњР С•Р Р†РЎвЂ№Р в„– Р В»Р С‘Р СР С‘РЎвЂљ Р Р† Р В±Р В°Р в„–РЎвЂљР В°РЎвЂ¦
            
        Returns:
            True Р С—РЎР‚Р С‘ РЎС“РЎРѓР С—Р ВµРЎв‚¬Р Р…Р С•Р С Р С•Р В±Р Р…Р С•Р Р†Р В»Р ВµР Р…Р С‘Р С‘
        """
        profile = await self._ensure_api_profile()
        if profile == API_PROFILE_CLIENTS:
            record = await self._get_clients_api_record(email, log_error=False)
            target_client = None
            if record:
                target_client, _ = self._split_clients_api_record(record)
            if not target_client:
                _, target_client = await self._find_panel_client(
                    inbound_id=inbound_id,
                    client_uuid=client_uuid,
                    email=email,
                )
            if not target_client:
                raise VPNAPIError(f"Р С™Р В»Р С‘Р ВµР Р…РЎвЂљ {email} Р Р…Р Вµ Р Р…Р В°Р в„–Р Т‘Р ВµР Р… Р Р† clients API")

            return await self.update_client_full(
                inbound_id=inbound_id,
                client_uuid=client_uuid,
                email=email,
                expiry_time_ms=target_client.get('expiryTime', 0),
                total_gb_bytes=total_gb_bytes,
                enable=target_client.get('enable', True),
                sub_id=target_client.get('subId', ''),
            )

        # Р СџР С•Р В»РЎС“РЎвЂЎР В°Р ВµР С РЎвЂљР ВµР С”РЎС“РЎвЂ°Р С‘Р Вµ Р Т‘Р В°Р Р…Р Р…РЎвЂ№Р Вµ Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР В°
        inbounds = await self.get_inbounds()
        target_client = None
        
        for inbound in inbounds:
            if inbound.get('id') == inbound_id:
                settings = self._load_json_field(inbound.get('settings', '{}'))
                clients = settings.get('clients', [])
                
                for client in clients:
                    if client.get('id') == client_uuid or client.get('password') == client_uuid:
                        target_client = client
                        break
                break
        
        if not target_client:
            raise VPNAPIError(f"Р С™Р В»Р С‘Р ВµР Р…РЎвЂљ {email} Р Р…Р Вµ Р Р…Р В°Р в„–Р Т‘Р ВµР Р… Р Р† inbound {inbound_id}")
        
        # Р С›Р В±Р Р…Р С•Р Р†Р В»РЎРЏР ВµР С totalGB
        target_client['totalGB'] = total_gb_bytes
        
        # Р В¤Р С•РЎР‚Р СР С‘РЎР‚РЎС“Р ВµР С Р Т‘Р В°Р Р…Р Р…РЎвЂ№Р Вµ Р Т‘Р В»РЎРЏ Р С•Р В±Р Р…Р С•Р Р†Р В»Р ВµР Р…Р С‘РЎРЏ
        updated_client = {
            "id": target_client.get('id', ''),
            "password": target_client.get('password', ''),
            "flow": target_client.get('flow', ''),
            "email": target_client.get('email', ''),
            "limitIp": target_client.get('limitIp', 1),
            "totalGB": total_gb_bytes,
            "expiryTime": target_client.get('expiryTime', 0),
            "enable": target_client.get('enable', True),
            "tgId": target_client.get('tgId', ''),
            "subId": target_client.get('subId', ''),
            "reset": target_client.get('reset', 0)
        }
        
        # Р Р€Р Т‘Р В°Р В»РЎРЏР ВµР С Р С—РЎС“РЎРѓРЎвЂљРЎвЂ№Р Вµ РЎРѓРЎвЂљРЎР‚Р С•Р С”Р С•Р Р†РЎвЂ№Р Вµ Р С—Р С•Р В»РЎРЏ (Р Р†Р В°Р В¶Р Р…Р С• Р Т‘Р В»РЎРЏ РЎР‚Р В°Р В·Р Р…РЎвЂ№РЎвЂ¦ Р С—РЎР‚Р С•РЎвЂљР С•Р С”Р С•Р В»Р С•Р Р†)
        updated_client = {k: v for k, v in updated_client.items() if v != ''}
        
        update_data = {
            "id": inbound_id,
            "settings": json.dumps({"clients": [updated_client]})
        }
        
        encoded_uuid = urllib.parse.quote(client_uuid, safe='')
        await self._request("POST", f"/panel/api/inbounds/updateClient/{encoded_uuid}", data=update_data)
        
        limit_gb = total_gb_bytes / (1024**3)
        logger.info(f"Р С›Р В±Р Р…Р С•Р Р†Р В»РЎвЂР Р… Р В»Р С‘Р СР С‘РЎвЂљ Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР В° {email}: {limit_gb:.1f} Р вЂњР вЂ")
        return True

    async def close(self):
        """Р вЂ”Р В°Р С”РЎР‚РЎвЂ№Р Р†Р В°Р ВµРЎвЂљ РЎРѓР ВµРЎРѓРЎРѓР С‘РЎР‹."""
        if self.session:
            await self.session.close()
            self.session = None


# ============================================================================
# Р вЂњР В»Р С•Р В±Р В°Р В»РЎРЉР Р…РЎвЂ№Р в„– Р С”РЎРЊРЎв‚¬ Р С”Р В»Р С‘Р ВµР Р…РЎвЂљР С•Р Р† Р С‘ Р Р†РЎРѓР С—Р С•Р СР С•Р С–Р В°РЎвЂљР ВµР В»РЎРЉР Р…РЎвЂ№Р Вµ РЎвЂћРЎС“Р Р…Р С”РЎвЂ Р С‘Р С‘
# ============================================================================
