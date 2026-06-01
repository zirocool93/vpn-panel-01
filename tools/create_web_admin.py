"""Create the first Web admin user.

Run:
    python tools/create_web_admin.py
"""
from __future__ import annotations

import getpass
import sqlite3
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from database.migrations import run_migrations  # noqa: E402
from services.auth_service import create_admin_user  # noqa: E402


def main() -> int:
    run_migrations()

    username = input("Username: ").strip()
    if not username:
        print("Ошибка: username не может быть пустым.")
        return 1

    password = getpass.getpass("Password: ")
    password_confirm = getpass.getpass("Confirm password: ")
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

