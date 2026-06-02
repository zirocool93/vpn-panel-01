"""Consistent SQLite backups for the Web admin."""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import socket
import sqlite3
import sys
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

from bot.utils.git_utils import get_current_branch, get_current_commit
from database.connection import DB_PATH, get_db
from database.migrations import LATEST_VERSION, get_current_version
from services.security_utils import mask_sensitive_dict


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKUP_DIR = PROJECT_ROOT / "backups"


def ensure_backup_dir() -> Path:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(BACKUP_DIR, 0o700)
    except OSError:
        pass
    return BACKUP_DIR


def create_backup(created_by_admin_id: int | None = None, include_logs: bool = False, note: str = "") -> dict[str, Any]:
    ensure_backup_dir()
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    filename = f"yadreno-vpn-backup-{timestamp}.tar.gz"
    path = BACKUP_DIR / filename

    with tempfile.TemporaryDirectory(prefix="yadreno-backup-") as temp_dir:
        temp_path = Path(temp_dir)
        db_copy = temp_path / "vpn_bot.sqlite"
        _sqlite_backup(db_copy)
        integrity = _integrity_for_path(db_copy)
        metadata = {
            "created_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
            "app": "Yadreno VPN",
            "db_schema_version": get_current_version(),
            "latest_schema_version": LATEST_VERSION,
            "git_branch": get_current_branch(),
            "git_commit": get_current_commit(),
            "python_version": sys.version,
            "hostname": socket.gethostname(),
            "created_by_admin_id": created_by_admin_id,
            "include_logs": bool(include_logs),
            "note": note.strip()[:500],
            "db_integrity_check": integrity.get("integrity_check"),
        }
        (temp_path / "metadata.json").write_text(json.dumps(mask_sensitive_dict(metadata), ensure_ascii=False, indent=2), encoding="utf-8")
        if include_logs:
            logs_dir = PROJECT_ROOT / "logs"
            if logs_dir.exists():
                archive_logs = temp_path / "logs"
                archive_logs.mkdir()
                for log_path in logs_dir.glob("*.log"):
                    shutil.copy2(log_path, archive_logs / log_path.name)
        with tarfile.open(path, "w:gz") as archive:
            archive.add(db_copy, arcname="database/vpn_bot.sqlite")
            archive.add(temp_path / "metadata.json", arcname="metadata.json")
            logs_archive_dir = temp_path / "logs"
            if include_logs and logs_archive_dir.exists():
                archive.add(logs_archive_dir, arcname="logs")

    sha = sha256_file(path)
    result = {"success": True, "filename": filename, "path": str(path), "size": path.stat().st_size, "sha256": sha, "metadata": metadata}
    log_backup_event(created_by_admin_id, "backup.create", filename, True, result["size"], sha, {"include_logs": include_logs, "note": note})
    _apply_retention()
    return result


def list_backups() -> list[dict[str, Any]]:
    ensure_backup_dir()
    backups = []
    for path in sorted(BACKUP_DIR.glob("*.tar.gz"), key=lambda item: item.stat().st_mtime, reverse=True):
        metadata = _read_metadata(path)
        backups.append(
            {
                "filename": path.name,
                "size": path.stat().st_size,
                "created_at": metadata.get("created_at") or datetime.utcfromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds") + "Z",
                "sha256": sha256_file(path),
                "git_commit": metadata.get("git_commit"),
                "schema_version": metadata.get("db_schema_version"),
                "include_logs": metadata.get("include_logs"),
                "note": metadata.get("note"),
                "metadata": metadata,
            }
        )
    return backups


def get_backup_path(filename: str) -> Path:
    clean = Path(filename).name
    if clean != filename or not clean.endswith(".tar.gz"):
        raise ValueError("Invalid backup filename")
    path = (ensure_backup_dir() / clean).resolve()
    if not str(path).startswith(str(ensure_backup_dir().resolve())):
        raise ValueError("Invalid backup path")
    if not path.exists():
        raise FileNotFoundError(clean)
    return path


def verify_backup(filename: str) -> dict[str, Any]:
    try:
        path = get_backup_path(filename)
        with tempfile.TemporaryDirectory(prefix="yadreno-verify-") as temp_dir:
            with tarfile.open(path, "r:gz") as archive:
                members = archive.getnames()
                if "metadata.json" not in members:
                    return {"success": False, "message": "metadata.json not found"}
                if "database/vpn_bot.sqlite" not in members:
                    return {"success": False, "message": "database/vpn_bot.sqlite not found"}
                archive.extract("metadata.json", temp_dir)
                archive.extract("database/vpn_bot.sqlite", temp_dir)
            metadata = json.loads((Path(temp_dir) / "metadata.json").read_text(encoding="utf-8"))
            integrity = _integrity_for_path(Path(temp_dir) / "database" / "vpn_bot.sqlite")
        ok = integrity.get("integrity_check") == "ok"
        return {"success": ok, "message": "Backup verified" if ok else "SQLite integrity check failed", "metadata": metadata, "integrity": integrity}
    except Exception as exc:
        return {"success": False, "message": str(exc), "metadata": {}, "integrity": {}}


def delete_backup(filename: str) -> dict[str, Any]:
    path = get_backup_path(filename)
    size = path.stat().st_size
    sha = sha256_file(path)
    path.unlink()
    return {"success": True, "message": "Backup deleted", "filename": filename, "size": size, "sha256": sha}


def restore_backup(filename: str, make_pre_restore_backup: bool = True, admin_user_id: int | None = None) -> dict[str, Any]:
    verification = verify_backup(filename)
    if not verification.get("success"):
        return {"success": False, "message": verification.get("message", "Backup verification failed")}
    pre_restore = None
    if make_pre_restore_backup:
        pre_restore = create_backup(admin_user_id, include_logs=False, note=f"pre-restore before {filename}")
    path = get_backup_path(filename)
    with tempfile.TemporaryDirectory(prefix="yadreno-restore-") as temp_dir:
        with tarfile.open(path, "r:gz") as archive:
            archive.extract("database/vpn_bot.sqlite", temp_dir)
        restored_db = Path(temp_dir) / "database" / "vpn_bot.sqlite"
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        for suffix in ("-wal", "-shm"):
            sidecar = Path(str(DB_PATH) + suffix)
            if sidecar.exists():
                sidecar.unlink()
        os.replace(restored_db, DB_PATH)
    return {"success": True, "message": "Backup restored. Restart bot and Web services.", "pre_restore_backup": pre_restore}


def vacuum_database() -> dict[str, Any]:
    size_before = _db_size_total()
    with get_db() as conn:
        conn.execute("PRAGMA optimize")
        conn.execute("VACUUM")
    size_after = _db_size_total()
    return {"success": True, "message": "VACUUM completed", "size_before": size_before, "size_after": size_after}


def database_integrity_check() -> dict[str, Any]:
    with get_db() as conn:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        foreign = [tuple(row) for row in conn.execute("PRAGMA foreign_key_check").fetchall()]
        journal_mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        wal_checkpoint = tuple(conn.execute("PRAGMA wal_checkpoint(PASSIVE)").fetchone())
    return {"success": integrity == "ok" and not foreign, "integrity_check": integrity, "foreign_key_check": foreign, "journal_mode": journal_mode, "wal_checkpoint": wal_checkpoint, "files": _db_files()}


def get_backup_log(limit: int = 50) -> list[dict[str, Any]]:
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM backup_log ORDER BY created_at DESC, id DESC LIMIT ?",
            (max(1, min(int(limit), 200)),),
        ).fetchall()
        return [dict(row) for row in rows]


def log_backup_event(admin_user_id: int | None, action: str, filename: str | None, success: bool, size_bytes: int | None = None, sha256: str | None = None, details: Any = None) -> None:
    with get_db() as conn:
        conn.execute(
            """
            INSERT INTO backup_log (admin_user_id, action, filename, success, size_bytes, sha256, details)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (admin_user_id, action, filename, 1 if success else 0, size_bytes, sha256, json.dumps(mask_sensitive_dict(details or {}), ensure_ascii=False, default=str)),
        )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _sqlite_backup(target: Path) -> None:
    source = sqlite3.connect(DB_PATH, timeout=10)
    try:
        target_conn = sqlite3.connect(target)
        try:
            source.backup(target_conn)
        finally:
            target_conn.close()
    finally:
        source.close()


def _integrity_for_path(path: Path) -> dict[str, Any]:
    conn = sqlite3.connect(path)
    try:
        return {
            "integrity_check": conn.execute("PRAGMA integrity_check").fetchone()[0],
            "schema_version": conn.execute("PRAGMA schema_version").fetchone()[0],
        }
    finally:
        conn.close()


def _read_metadata(path: Path) -> dict[str, Any]:
    try:
        with tarfile.open(path, "r:gz") as archive:
            member = archive.extractfile("metadata.json")
            if not member:
                return {}
            return json.loads(member.read().decode("utf-8"))
    except Exception:
        return {}


def _db_size_total() -> int:
    return sum(item["size"] for item in _db_files())


def _db_files() -> list[dict[str, Any]]:
    files = []
    for suffix in ("", "-wal", "-shm"):
        path = Path(str(DB_PATH) + suffix)
        files.append({"name": path.name, "path": str(path), "exists": path.exists(), "size": path.stat().st_size if path.exists() else 0})
    return files


def _apply_retention() -> None:
    try:
        from database.db_settings import get_setting

        keep = int(get_setting("backup_retention_count", "10") or "10")
    except Exception:
        keep = 10
    backups = list_backups()
    for item in backups[max(1, keep):]:
        try:
            get_backup_path(item["filename"]).unlink()
        except OSError:
            pass
