"""Create the first Web admin user.

Run:
    python tools/create_web_admin.py
"""
from __future__ import annotations

import getpass
import os
import sqlite3
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database.migrations import run_migrations  # noqa: E402
from services.auth_service import create_admin_user  # noqa: E402


def admin_users_exist() -> bool:
    from database.connection import get_db

    with get_db() as conn:
        row = conn.execute("SELECT COUNT(*) AS count FROM admin_users").fetchone()
        return bool(row and row["count"])


def main() -> int:
    run_migrations()

    skip_if_exists = os.getenv("WEB_ADMIN_SKIP_IF_EXISTS") == "1"
    if skip_if_exists and admin_users_exist():
        print("Web admin already exists; skipping.")
        return 0

    username = (os.getenv("WEB_ADMIN_USERNAME") or "").strip()
    if not username:
        username = input("Username: ").strip()
    if not username:
        print("Ошибка: username не может быть пустым.")
        return 1

    password = os.getenv("WEB_ADMIN_PASSWORD")
    if password is None:
        password = getpass.getpass("Password: ")
        password_confirm = getpass.getpass("Confirm password: ")
    else:
        password_confirm = password
    if password != password_confirm:
        print("Ошибка: пароли не совпадают.")
        return 1
    if len(password) < 8:
        print("Ошибка: пароль должен быть не короче 8 символов.")
        return 1

    try:
        user_id = create_admin_user(username, password)
    except sqlite3.IntegrityError:
        print(f"Ошибка: Web-админ '{username}' уже существует.")
        return 1
    except ValueError as exc:
        print(f"Ошибка: {exc}")
        return 1

    print(f"Web-админ создан: {username} (id={user_id})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
