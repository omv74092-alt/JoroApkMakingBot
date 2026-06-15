import sqlite3
import json
from datetime import datetime
from config import DATABASE_URL

def get_conn():
    conn = sqlite3.connect(DATABASE_URL)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS users (
        user_id     INTEGER PRIMARY KEY,
        username    TEXT,
        full_name   TEXT,
        joined_at   TEXT,
        is_banned   INTEGER DEFAULT 0,
        builds_done INTEGER DEFAULT 0
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS keys (
        key         TEXT PRIMARY KEY,
        created_by  INTEGER,
        used_by     INTEGER DEFAULT NULL,
        used_at     TEXT DEFAULT NULL,
        max_builds  INTEGER DEFAULT 5,
        is_active   INTEGER DEFAULT 1,
        created_at  TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS builds (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     INTEGER,
        app_name    TEXT,
        package     TEXT,
        status      TEXT DEFAULT 'pending',
        gh_run_id   TEXT,
        apk_url     TEXT,
        created_at  TEXT,
        finished_at TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS settings (
        key   TEXT PRIMARY KEY,
        value TEXT
    )''')

    c.execute("INSERT OR IGNORE INTO settings VALUES ('maintenance','0')")
    c.execute("INSERT OR IGNORE INTO settings VALUES ('max_builds_per_day','3')")

    conn.commit()
    conn.close()

def add_user(user_id, username, full_name):
    conn = get_conn()
    conn.execute('''INSERT OR IGNORE INTO users (user_id,username,full_name,joined_at)
                    VALUES (?,?,?,?)''',
                 (user_id, username, full_name, datetime.now().isoformat()))
    conn.commit(); conn.close()

def get_user(user_id):
    conn = get_conn()
    u = conn.execute("SELECT * FROM users WHERE user_id=?", (user_id,)).fetchone()
    conn.close()
    return dict(u) if u else None

def ban_user(user_id, ban=True):
    conn = get_conn()
    conn.execute("UPDATE users SET is_banned=? WHERE user_id=?", (1 if ban else 0, user_id))
    conn.commit(); conn.close()

def get_all_users():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM users").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_stats():
    conn = get_conn()
    total_users  = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    total_builds = conn.execute("SELECT COUNT(*) FROM builds").fetchone()[0]
    active_keys  = conn.execute("SELECT COUNT(*) FROM keys WHERE is_active=1").fetchone()[0]
    conn.close()
    return {"users": total_users, "builds": total_builds, "active_keys": active_keys}

def create_key(key, created_by, max_builds=5):
    conn = get_conn()
    conn.execute('''INSERT INTO keys (key,created_by,max_builds,created_at)
                    VALUES (?,?,?,?)''',
                 (key, created_by, max_builds, datetime.now().isoformat()))
    conn.commit(); conn.close()

def use_key(key, user_id):
    conn = get_conn()
    k = conn.execute("SELECT * FROM keys WHERE key=? AND is_active=1 AND used_by IS NULL",
                     (key,)).fetchone()
    if not k:
        conn.close(); return False
    conn.execute("UPDATE keys SET used_by=?,used_at=? WHERE key=?",
                 (user_id, datetime.now().isoformat(), key))
    conn.commit(); conn.close()
    return True

def check_user_key(user_id):
    conn = get_conn()
    k = conn.execute("SELECT * FROM keys WHERE used_by=? AND is_active=1", (user_id,)).fetchone()
    conn.close()
    return dict(k) if k else None

def get_all_keys():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM keys ORDER BY created_at DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def revoke_key(key):
    conn = get_conn()
    conn.execute("UPDATE keys SET is_active=0 WHERE key=?", (key,))
    conn.commit(); conn.close()

def create_build(user_id, app_name, package):
    conn = get_conn()
    c = conn.cursor()
    c.execute('''INSERT INTO builds (user_id,app_name,package,created_at)
                 VALUES (?,?,?,?)''',
              (user_id, app_name, package, datetime.now().isoformat()))
    build_id = c.lastrowid
    conn.commit(); conn.close()
    return build_id

def update_build(build_id, **kwargs):
    conn = get_conn()
    sets = ", ".join(f"{k}=?" for k in kwargs)
    vals = list(kwargs.values()) + [build_id]
    conn.execute(f"UPDATE builds SET {sets} WHERE id=?", vals)
    conn.commit(); conn.close()

def get_user_builds(user_id):
    conn = get_conn()
    rows = conn.execute("SELECT * FROM builds WHERE user_id=? ORDER BY created_at DESC LIMIT 10",
                        (user_id,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_build(build_id):
    conn = get_conn()
    r = conn.execute("SELECT * FROM builds WHERE id=?", (build_id,)).fetchone()
    conn.close()
    return dict(r) if r else None

def get_setting(key):
    conn = get_conn()
    r = conn.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    conn.close()
    return r[0] if r else None

def set_setting(key, value):
    conn = get_conn()
    conn.execute("INSERT OR REPLACE INTO settings VALUES (?,?)", (key, str(value)))
    conn.commit(); conn.close()
