"""DB-backed Web admin roles and permission overrides."""
from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from database.connection import get_db


PERMISSION_LABELS = {
    "dashboard.view": "Просмотр Dashboard",
    "audit.view": "Просмотр аудита",
    "servers.view": "Просмотр серверов",
    "servers.create": "Создание серверов",
    "servers.update": "Редактирование серверов",
    "servers.delete": "Удаление серверов",
    "servers.toggle": "Включение/отключение серверов",
    "servers.test": "Проверка серверов",
    "servers.diagnostics": "Диагностика серверов",
    "servers.relogin": "Relogin в 3X-UI",
    "servers.reset_api_token": "Сброс api_token сервера",
    "tariffs.view": "Просмотр тарифов",
    "tariffs.create": "Создание тарифов",
    "tariffs.update": "Редактирование тарифов",
    "tariffs.toggle": "Включение/отключение тарифов",
    "tariffs.delete": "Удаление тарифов",
    "users.view": "Просмотр пользователей",
    "users.ban": "Блокировка пользователей",
    "users.balance": "Изменение баланса",
    "users.assign_tariff": "Назначение тарифа",
    "keys.view": "Просмотр ключей",
    "keys.create": "Создание ключей",
    "keys.update": "Редактирование ключей",
    "keys.delete": "Удаление ключей",
    "keys.extend": "Продление ключей",
    "keys.reset_traffic": "Сброс трафика",
    "keys.sync": "Синхронизация ключей",
    "keys.links": "Ссылки и QR",
    "pages.view": "Просмотр страниц",
    "pages.update": "Редактирование страниц",
    "pages.reset": "Сброс страниц",
    "pages.copy_default_buttons": "Копирование default-кнопок",
    "payments.view": "Просмотр платежей",
    "payments.manage": "Управление платежами",
    "settings.view": "Просмотр настроек",
    "settings.update": "Изменение настроек",
    "system.view": "Просмотр системы",
    "system.diagnostics": "Диагностика системы",
    "system.logs": "Просмотр логов",
    "system.clear_logs": "Очистка логов",
    "system.restart": "Рестарт сервисов",
    "system.backups": "Просмотр бэкапов",
    "system.backup_create": "Создание бэкапов",
    "system.backup_download": "Скачивание бэкапов",
    "system.backup_restore": "Восстановление бэкапов",
    "system.backup_delete": "Удаление бэкапов",
    "admin_users.view": "Просмотр Web-админов",
    "admin_users.create": "Создание Web-админов",
    "admin_users.update": "Редактирование Web-админов",
    "admin_users.disable": "Отключение Web-админов",
    "admin_users.delete": "Удаление Web-админов",
    "admin_users.reset_password": "Сброс пароля Web-админа",
    "admin_users.sessions": "Управление сессиями Web-админов",
    "admin_users.permissions": "Персональные права Web-админов",
    "admin_roles.view": "Просмотр ролей",
    "admin_roles.update": "Редактирование ролей",
}


def list_all_permissions() -> list[dict[str, str]]:
    from web.security import ALL_PERMISSIONS

    rows = []
    for permission in sorted(ALL_PERMISSIONS):
        group = permission.split(".", 1)[0]
        if group == "system" and permission.startswith("system.backup"):
            group = "backups"
        rows.append({"key": permission, "group": group, "label": PERMISSION_LABELS.get(permission, permission)})
    return rows


def grouped_permissions() -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for permission in list_all_permissions():
        grouped[permission["group"]].append(permission)
    return dict(grouped)


def list_roles() -> list[dict[str, Any]]:
    try:
        with get_db() as conn:
            rows = conn.execute("SELECT * FROM admin_roles ORDER BY is_system DESC, role_key").fetchall()
            roles = [dict(row) for row in rows]
    except Exception:
        roles = []
    if roles:
        for role in roles:
            role["permissions"] = _parse_permissions(role.get("permissions_json"))
        return roles
    from web.security import ROLES

    return [{"role_key": key, "label": key.title(), "description": "", "permissions": sorted(value), "is_system": 1, "is_active": 1} for key, value in ROLES.items()]


def get_role(role_key: str) -> dict[str, Any] | None:
    clean = (role_key or "").strip().lower()
    try:
        with get_db() as conn:
            row = conn.execute("SELECT * FROM admin_roles WHERE role_key = ?", (clean,)).fetchone()
        if row:
            role = dict(row)
            role["permissions"] = _parse_permissions(role.get("permissions_json"))
            return role
    except Exception:
        pass
    from web.security import ROLES

    if clean in ROLES:
        return {"role_key": clean, "label": clean.title(), "description": "", "permissions": sorted(ROLES[clean]), "is_system": 1, "is_active": 1}
    return None


def get_role_permissions(role_key: str) -> set[str]:
    role = get_role(role_key)
    if role and role.get("is_active", 1):
        return set(role.get("permissions", []))
    return set()


def update_role_permissions(role_key: str, permissions: list[str], admin_user_id: int | None = None) -> dict[str, Any]:
    from web.security import ALL_PERMISSIONS

    clean = (role_key or "").strip().lower()
    requested = sorted({p for p in permissions if p in ALL_PERMISSIONS})
    if clean == "owner":
        requested = sorted(ALL_PERMISSIONS)
    role = get_role(clean)
    if not role:
        raise ValueError("Role not found")
    if role.get("is_system", 1) and not _is_owner(admin_user_id):
        raise ValueError("Only owner can edit system roles")
    with get_db() as conn:
        conn.execute(
            """
            UPDATE admin_roles
            SET permissions_json = ?, updated_at = CURRENT_TIMESTAMP
            WHERE role_key = ?
            """,
            (json.dumps(requested, ensure_ascii=False), clean),
        )
    return {"role_key": clean, "permissions": requested, "changed_permissions_count": len(requested)}


def _is_owner(admin_user_id: int | None) -> bool:
    if not admin_user_id:
        return False
    try:
        with get_db() as conn:
            row = conn.execute("SELECT role FROM admin_users WHERE id = ? AND is_active = 1", (admin_user_id,)).fetchone()
            return bool(row and row["role"] == "owner")
    except Exception:
        return False


def get_user_permission_overrides(admin_user_id: int) -> list[dict[str, Any]]:
    try:
        with get_db() as conn:
            rows = conn.execute(
                "SELECT * FROM admin_user_permission_overrides WHERE admin_user_id = ? ORDER BY permission",
                (admin_user_id,),
            ).fetchall()
            return [dict(row) for row in rows]
    except Exception:
        return []


def set_user_permission_overrides(admin_user_id: int, overrides: dict[str, str]) -> dict[str, Any]:
    from web.security import ALL_PERMISSIONS

    changed = 0
    with get_db() as conn:
        for permission, effect in overrides.items():
            if permission not in ALL_PERMISSIONS:
                continue
            clean_effect = (effect or "").strip().lower()
            if clean_effect in {"allow", "deny"}:
                conn.execute(
                    """
                    INSERT INTO admin_user_permission_overrides (admin_user_id, permission, effect, updated_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(admin_user_id, permission)
                    DO UPDATE SET effect = excluded.effect, updated_at = CURRENT_TIMESTAMP
                    """,
                    (admin_user_id, permission, clean_effect),
                )
                changed += 1
            else:
                cursor = conn.execute(
                    "DELETE FROM admin_user_permission_overrides WHERE admin_user_id = ? AND permission = ?",
                    (admin_user_id, permission),
                )
                changed += cursor.rowcount
    return {"admin_user_id": admin_user_id, "changed_permissions_count": changed}


def get_effective_permissions(admin: dict[str, Any] | None) -> set[str]:
    if not admin or not admin.get("is_active", 1):
        return set()
    from web.security import ALL_PERMISSIONS, ROLES

    role = (admin.get("role") or "readonly").strip().lower()
    if role == "owner":
        return set(ALL_PERMISSIONS)
    permissions = get_role_permissions(role)
    if not permissions:
        permissions = set(ROLES.get(role, set()))
    for override in get_user_permission_overrides(int(admin.get("admin_user_id") or admin.get("id") or 0)):
        permission = override.get("permission")
        effect = override.get("effect")
        if permission not in ALL_PERMISSIONS:
            continue
        if effect == "allow":
            permissions.add(permission)
        elif effect == "deny":
            permissions.discard(permission)
    return permissions


def _parse_permissions(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    try:
        data = json.loads(value or "[]")
        return [str(item) for item in data if isinstance(item, str)]
    except (TypeError, json.JSONDecodeError):
        return []
