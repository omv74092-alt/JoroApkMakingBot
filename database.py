# ============================================================
# database.py - SQLite Database Handler
# Saare tables aur CRUD operations yahan hain
# ============================================================

import sqlite3
import secrets
import logging
from datetime import datetime, timedelta
from config import DB_PATH, SESSION_EXPIRY_HOURS

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._create_tables()

    # ── Internal helpers ──────────────────────────────────────
    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _create_tables(self):
        ddl = """
        CREATE TABLE IF NOT EXISTS users (
            user_id         INTEGER PRIMARY KEY,
            username        TEXT,
            first_name      TEXT,
            is_admin        INTEGER DEFAULT 0,
            is_banned       INTEGER DEFAULT 0,
            shizuku_verified INTEGER DEFAULT 0,
            user_path       TEXT DEFAULT '',
            created_at      TEXT DEFAULT (datetime('now')),
            last_active     TEXT DEFAULT (datetime('now')),
            session_token   TEXT,
            session_expiry  TEXT
        );

        CREATE TABLE IF NOT EXISTS admin_logs (
            log_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            admin_id    INTEGER NOT NULL,
            action      TEXT NOT NULL,
            target_id   INTEGER,
            details     TEXT,
            timestamp   TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS shizuku_commands (
            cmd_id      INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            command     TEXT NOT NULL,
            output      TEXT,
            status      TEXT DEFAULT 'pending',
            executed_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS assets_files (
            file_id     INTEGER PRIMARY KEY AUTOINCREMENT,
            file_name   TEXT NOT NULL,
            file_path   TEXT NOT NULL UNIQUE,
            file_size   INTEGER DEFAULT 0,
            uploaded_by INTEGER,
            uploads     INTEGER DEFAULT 0,
            created_at  TEXT DEFAULT (datetime('now'))
        );
        """
        with self._conn() as conn:
            conn.executescript(ddl)
        logger.info("Database tables created/verified.")

    # ═══════════════════════════════════════════════════════════
    # USER OPERATIONS
    # ═══════════════════════════════════════════════════════════

    def get_user(self, user_id: int) -> dict | None:
        with self._conn() as conn:
            row = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
            return dict(row) if row else None

    def register_user(self, user_id: int, username: str, first_name: str, is_admin: bool = False):
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO users (user_id, username, first_name, is_admin)
                VALUES (?,?,?,?)
                ON CONFLICT(user_id) DO UPDATE SET
                    username=excluded.username,
                    first_name=excluded.first_name,
                    last_active=datetime('now')
            """, (user_id, username or "", first_name or "", int(is_admin)))

    def update_last_active(self, user_id: int):
        with self._conn() as conn:
            conn.execute("UPDATE users SET last_active=datetime('now') WHERE user_id=?", (user_id,))

    def set_user_path(self, user_id: int, path: str):
        with self._conn() as conn:
            conn.execute("UPDATE users SET user_path=? WHERE user_id=?", (path, user_id))

    def ban_user(self, user_id: int):
        with self._conn() as conn:
            conn.execute("UPDATE users SET is_banned=1 WHERE user_id=?", (user_id,))

    def unban_user(self, user_id: int):
        with self._conn() as conn:
            conn.execute("UPDATE users SET is_banned=0 WHERE user_id=?", (user_id,))

    def make_admin(self, user_id: int):
        with self._conn() as conn:
            conn.execute("UPDATE users SET is_admin=1 WHERE user_id=?", (user_id,))

    def set_shizuku_verified(self, user_id: int, status: bool):
        with self._conn() as conn:
            conn.execute("UPDATE users SET shizuku_verified=? WHERE user_id=?", (int(status), user_id))

    def get_all_users(self, page: int = 1, page_size: int = 10) -> tuple[list, int]:
        offset = (page - 1) * page_size
        with self._conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            rows  = conn.execute(
                "SELECT * FROM users ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (page_size, offset)
            ).fetchall()
        return [dict(r) for r in rows], total

    def get_all_user_ids(self) -> list[int]:
        with self._conn() as conn:
            rows = conn.execute("SELECT user_id FROM users WHERE is_banned=0").fetchall()
        return [r[0] for r in rows]

    def is_banned(self, user_id: int) -> bool:
        u = self.get_user(user_id)
        return bool(u and u["is_banned"])

    def is_admin(self, user_id: int) -> bool:
        u = self.get_user(user_id)
        return bool(u and u["is_admin"])

    # ═══════════════════════════════════════════════════════════
    # SESSION MANAGEMENT
    # ═══════════════════════════════════════════════════════════

    def create_session(self, user_id: int) -> str:
        token  = secrets.token_hex(32)
        expiry = (datetime.utcnow() + timedelta(hours=SESSION_EXPIRY_HOURS)).isoformat()
        with self._conn() as conn:
            conn.execute(
                "UPDATE users SET session_token=?, session_expiry=? WHERE user_id=?",
                (token, expiry, user_id)
            )
        return token

    def validate_session(self, user_id: int) -> bool:
        u = self.get_user(user_id)
        if not u or not u["session_token"]:
            return False
        try:
            expiry = datetime.fromisoformat(u["session_expiry"])
            return datetime.utcnow() < expiry
        except Exception:
            return False

    def clear_session(self, user_id: int):
        with self._conn() as conn:
            conn.execute(
                "UPDATE users SET session_token=NULL, session_expiry=NULL WHERE user_id=?",
                (user_id,)
            )

    # ═══════════════════════════════════════════════════════════
    # ADMIN LOGS
    # ═══════════════════════════════════════════════════════════

    def log_admin_action(self, admin_id: int, action: str, target_id: int = None, details: str = ""):
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO admin_logs (admin_id, action, target_id, details) VALUES (?,?,?,?)",
                (admin_id, action, target_id, details)
            )

    def get_admin_logs(self, page: int = 1, page_size: int = 10) -> tuple[list, int]:
        offset = (page - 1) * page_size
        with self._conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM admin_logs").fetchone()[0]
            rows  = conn.execute(
                "SELECT * FROM admin_logs ORDER BY timestamp DESC LIMIT ? OFFSET ?",
                (page_size, offset)
            ).fetchall()
        return [dict(r) for r in rows], total

    # ═══════════════════════════════════════════════════════════
    # SHIZUKU COMMANDS
    # ═══════════════════════════════════════════════════════════

    def log_shizuku_cmd(self, user_id: int, command: str, output: str, status: str):
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO shizuku_commands (user_id, command, output, status) VALUES (?,?,?,?)",
                (user_id, command, output, status)
            )

    def get_user_shizuku_history(self, user_id: int, limit: int = 10) -> list:
        with self._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM shizuku_commands WHERE user_id=? ORDER BY executed_at DESC LIMIT ?",
                (user_id, limit)
            ).fetchall()
        return [dict(r) for r in rows]

    # ═══════════════════════════════════════════════════════════
    # ASSETS FILES
    # ═══════════════════════════════════════════════════════════

    def register_asset(self, file_name: str, file_path: str, file_size: int, uploaded_by: int):
        with self._conn() as conn:
            conn.execute("""
                INSERT INTO assets_files (file_name, file_path, file_size, uploaded_by)
                VALUES (?,?,?,?)
                ON CONFLICT(file_path) DO UPDATE SET
                    file_size=excluded.file_size,
                    uploaded_by=excluded.uploaded_by,
                    created_at=datetime('now')
            """, (file_name, file_path, file_size, uploaded_by))

    def delete_asset(self, file_path: str):
        with self._conn() as conn:
            conn.execute("DELETE FROM assets_files WHERE file_path=?", (file_path,))

    def increment_download(self, file_path: str):
        with self._conn() as conn:
            conn.execute("UPDATE assets_files SET uploads=uploads+1 WHERE file_path=?", (file_path,))

    def get_all_assets(self, page: int = 1, page_size: int = 10) -> tuple[list, int]:
        offset = (page - 1) * page_size
        with self._conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM assets_files").fetchone()[0]
            rows  = conn.execute(
                "SELECT * FROM assets_files ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (page_size, offset)
            ).fetchall()
        return [dict(r) for r in rows], total

    # ═══════════════════════════════════════════════════════════
    # STATS
    # ═══════════════════════════════════════════════════════════

    def get_stats(self) -> dict:
        with self._conn() as conn:
            total_users   = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            active_users  = conn.execute(
                "SELECT COUNT(*) FROM users WHERE last_active > datetime('now','-1 day')"
            ).fetchone()[0]
            banned_users  = conn.execute("SELECT COUNT(*) FROM users WHERE is_banned=1").fetchone()[0]
            admin_users   = conn.execute("SELECT COUNT(*) FROM users WHERE is_admin=1").fetchone()[0]
            total_cmds    = conn.execute("SELECT COUNT(*) FROM shizuku_commands").fetchone()[0]
            total_assets  = conn.execute("SELECT COUNT(*) FROM assets_files").fetchone()[0]
            total_logs    = conn.execute("SELECT COUNT(*) FROM admin_logs").fetchone()[0]
        return {
            "total_users":  total_users,
            "active_users": active_users,
            "banned_users": banned_users,
            "admin_users":  admin_users,
            "total_cmds":   total_cmds,
            "total_assets": total_assets,
            "total_logs":   total_logs,
        }
