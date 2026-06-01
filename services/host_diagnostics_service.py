"""Host diagnostics for the machine running bot and Web admin."""
from __future__ import annotations

import os
import platform
import shutil
import socket
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from database.connection import DB_PATH, get_db
from bot.utils import git_utils


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SERVICES = ("yadreno-vpn", "yadreno-vpn-web")


def run_command_safe(cmd: list[str], timeout: int = 5) -> dict[str, Any]:
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
        return {"ok": result.returncode == 0, "stdout": result.stdout.strip(), "stderr": result.stderr.strip(), "returncode": result.returncode, "timeout": False}
    except subprocess.TimeoutExpired as exc:
        return {"ok": False, "stdout": exc.stdout or "", "stderr": exc.stderr or "timeout", "returncode": None, "timeout": True}
    except FileNotFoundError:
        return {"ok": False, "stdout": "", "stderr": f"{cmd[0]} not found", "returncode": None, "timeout": False}
    except Exception as exc:
        return {"ok": False, "stdout": "", "stderr": str(exc), "returncode": None, "timeout": False}


def get_host_diagnostics() -> dict[str, Any]:
    return {
        "system": get_system_info(),
        "resources": get_resource_info(),
        "services": get_services_info(),
        "network": get_network_info(),
        "git": get_git_info(),
        "database": get_database_info(),
        "logs": get_logs_info(),
    }


def get_system_info() -> dict[str, Any]:
    return {
        "hostname": socket.gethostname(),
        "os": platform.platform(),
        "uptime": _uptime(),
        "load_average": os.getloadavg() if hasattr(os, "getloadavg") else None,
        "timezone": time.tzname,
        "current_time": time.strftime("%Y-%m-%d %H:%M:%S %z"),
        "python_version": sys.version,
        "current_user": os.getenv("USER") or os.getenv("USERNAME") or "",
        "project_root": str(PROJECT_ROOT),
    }


def get_resource_info() -> dict[str, Any]:
    usage = shutil.disk_usage(PROJECT_ROOT)
    return {
        "cpu_count": os.cpu_count(),
        "disk": {"total": usage.total, "used": usage.used, "free": usage.free},
        "memory": _memory_info(),
        "swap": _swap_info(),
    }


def get_services_info() -> dict[str, Any]:
    result = {}
    for service in SERVICES:
        result[service] = {
            "active": run_command_safe(["systemctl", "is-active", service], timeout=5),
            "enabled": run_command_safe(["systemctl", "is-enabled", service], timeout=5),
            "status": run_command_safe(["systemctl", "status", service, "--no-pager"], timeout=8),
            "journal": run_command_safe(["journalctl", "-u", service, "-n", "50", "--no-pager"], timeout=8),
        }
    return result


def get_network_info() -> dict[str, Any]:
    return {
        "default_route": run_command_safe(["ip", "route", "show", "default"]),
        "dns_resolvers": _read_file("/etc/resolv.conf"),
        "github_dns": run_command_safe(["getent", "hosts", "github.com"]),
        "telegram_dns": run_command_safe(["getent", "hosts", "api.telegram.org"]),
        "github_https": run_command_safe([sys.executable, "-c", "import urllib.request; r=urllib.request.urlopen('https://github.com', timeout=5); print(r.status)"], timeout=8),
        "telegram_https": run_command_safe([sys.executable, "-c", "import urllib.request; r=urllib.request.urlopen('https://api.telegram.org', timeout=5); print(r.status)"], timeout=8),
    }


def get_git_info() -> dict[str, Any]:
    branch = git_utils.get_current_branch()
    remote = git_utils.get_remote_url()
    dirty = git_utils.run_git_command(["status", "--porcelain"])[1]
    ahead_behind = git_utils.run_git_command(["rev-list", "--left-right", "--count", "HEAD...origin/" + (branch or "main")])
    return {
        "branch": branch,
        "commit": git_utils.get_current_commit(),
        "remote_url": remote,
        "dirty": bool(dirty.strip()),
        "ahead_behind": ahead_behind[1] if ahead_behind[0] else ahead_behind[1],
    }


def get_database_info() -> dict[str, Any]:
    info = {"available": False, "path": str(DB_PATH), "files": _db_files()}
    try:
        with get_db() as conn:
            info.update(
                {
                    "available": True,
                    "integrity_check": conn.execute("PRAGMA integrity_check").fetchone()[0],
                    "journal_mode": conn.execute("PRAGMA journal_mode").fetchone()[0],
                    "foreign_keys": conn.execute("PRAGMA foreign_keys").fetchone()[0],
                    "busy_timeout": conn.execute("PRAGMA busy_timeout").fetchone()[0],
                    "schema_version": conn.execute("PRAGMA schema_version").fetchone()[0],
                    "users_count": _count(conn, "users"),
                    "keys_count": _count(conn, "vpn_keys"),
                    "payments_count": _count(conn, "payments"),
                }
            )
    except sqlite3.Error as exc:
        info["error"] = str(exc)
    return info


def get_logs_info() -> dict[str, Any]:
    logs_dir = PROJECT_ROOT / "logs"
    files = []
    if logs_dir.exists():
        for path in logs_dir.glob("*.log"):
            files.append({"name": path.name, "size": path.stat().st_size, "tail": _tail(path)})
    return {"dir": str(logs_dir), "files": files}


def restart_service(service: str) -> dict[str, Any]:
    if service not in SERVICES:
        return {"ok": False, "stderr": "Unsupported service"}
    return run_command_safe(["systemctl", "restart", service], timeout=15)


def _uptime() -> str:
    if Path("/proc/uptime").exists():
        seconds = float(Path("/proc/uptime").read_text().split()[0])
        return f"{int(seconds // 86400)}d {int(seconds % 86400 // 3600)}h {int(seconds % 3600 // 60)}m"
    return ""


def _memory_info() -> dict[str, int]:
    data = _proc_meminfo()
    total = data.get("MemTotal", 0) * 1024
    free = (data.get("MemAvailable") or data.get("MemFree", 0)) * 1024
    return {"total": total, "free": free, "used": max(0, total - free)}


def _swap_info() -> dict[str, int]:
    data = _proc_meminfo()
    total = data.get("SwapTotal", 0) * 1024
    free = data.get("SwapFree", 0) * 1024
    return {"total": total, "free": free, "used": max(0, total - free)}


def _proc_meminfo() -> dict[str, int]:
    if not Path("/proc/meminfo").exists():
        return {}
    result = {}
    for line in Path("/proc/meminfo").read_text().splitlines():
        key, _, value = line.partition(":")
        parts = value.strip().split()
        if parts and parts[0].isdigit():
            result[key] = int(parts[0])
    return result


def _read_file(path: str) -> str:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return str(exc)


def _db_files() -> list[dict[str, Any]]:
    files = []
    for suffix in ("", "-wal", "-shm"):
        path = Path(str(DB_PATH) + suffix)
        files.append({"name": path.name, "path": str(path), "size": path.stat().st_size if path.exists() else 0, "exists": path.exists()})
    return files


def _count(conn, table: str) -> int:
    try:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
    except sqlite3.Error:
        return 0


def _tail(path: Path, lines: int = 50) -> str:
    try:
        return "\n".join(path.read_text(encoding="utf-8", errors="replace").splitlines()[-lines:])
    except OSError as exc:
        return str(exc)
