# ============================================================
# bot.py - Main Telegram Bot File
# Saare handlers, middleware aur bot logic yahan hain
# ============================================================

import os
import sys
import time
import logging
import math
import threading
from collections import defaultdict, deque
from functools import wraps
from datetime import datetime

import telebot
from telebot import types

from config import (
    BOT_TOKEN, ADMIN_IDS, ASSETS_PATH, ASSET_FOLDERS,
    ALLOWED_EXTENSIONS, PAGE_SIZE, RATE_LIMIT_COMMANDS,
    RATE_LIMIT_WINDOW, COMMAND_COOLDOWN, LOG_FILE, LOG_LEVEL
)
from database import Database
from shizuku_api import ShizukuRunner

# ── Logging Setup ─────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ]
)
logger = logging.getLogger("TelegramBot")

# ── Global Instances ──────────────────────────────────────────
bot     = telebot.TeleBot(BOT_TOKEN, parse_mode="Markdown")
db      = Database()
shizuku = ShizukuRunner()

# ── Rate Limiter State ────────────────────────────────────────
_rate_buckets : dict[int, deque]  = defaultdict(lambda: deque())
_last_cmd_time: dict[int, float]  = defaultdict(float)
_rate_lock = threading.Lock()

# ── Ensure asset folders exist ────────────────────────────────
for folder in ASSET_FOLDERS.values():
    os.makedirs(folder, exist_ok=True)

# ═══════════════════════════════════════════════════════════════
# DECORATORS / MIDDLEWARE
# ═══════════════════════════════════════════════════════════════

def _check_rate(user_id: int) -> bool:
    """
    Rate limiter: RATE_LIMIT_COMMANDS per RATE_LIMIT_WINDOW seconds.
    Returns True agar allowed, False agar throttled.
    """
    now = time.time()
    with _rate_lock:
        q = _rate_buckets[user_id]
        # Purane entries nikalo
        while q and now - q[0] > RATE_LIMIT_WINDOW:
            q.popleft()
        if len(q) >= RATE_LIMIT_COMMANDS:
            return False
        q.append(now)
        return True


def _check_cooldown(user_id: int) -> bool:
    now = time.time()
    with _rate_lock:
        if now - _last_cmd_time[user_id] < COMMAND_COOLDOWN:
            return False
        _last_cmd_time[user_id] = now
        return True


def require_login(f):
    """Session valid hona chahiye"""
    @wraps(f)
    def wrapper(message, *args, **kwargs):
        uid = message.from_user.id
        if not db.validate_session(uid):
            bot.reply_to(message, "🔐 Pehle login karo: /login")
            return
        db.update_last_active(uid)
        return f(message, *args, **kwargs)
    return wrapper


def require_admin(f):
    """Admin hona chahiye"""
    @wraps(f)
    def wrapper(message, *args, **kwargs):
        uid = message.from_user.id
        if not db.is_admin(uid) and uid not in ADMIN_IDS:
            bot.reply_to(message, "⛔ Sirf admins ke liye hai!")
            return
        return f(message, *args, **kwargs)
    return wrapper


def not_banned(f):
    """Banned nahi hona chahiye"""
    @wraps(f)
    def wrapper(message, *args, **kwargs):
        uid = message.from_user.id
        if db.is_banned(uid):
            bot.reply_to(message, "🚫 Aap ban hain. Admin se contact karo.")
            return
        return f(message, *args, **kwargs)
    return wrapper


def rate_limited(f):
    """Rate limit + cooldown enforce karo"""
    @wraps(f)
    def wrapper(message, *args, **kwargs):
        uid = message.from_user.id
        if not _check_rate(uid):
            bot.reply_to(message, "⚡ Bahut tez! Thoda slow karo.")
            return
        if not _check_cooldown(uid):
            bot.reply_to(message, f"⏳ `{COMMAND_COOLDOWN}s` cooldown. Ruko thoda.")
            return
        return f(message, *args, **kwargs)
    return wrapper


def register_and_guard(f):
    """Auto-register + rate + ban check (chained)"""
    @wraps(f)
    @rate_limited
    @not_banned
    def wrapper(message, *args, **kwargs):
        u   = message.from_user
        uid = u.id
        is_super = uid in ADMIN_IDS
        db.register_user(uid, u.username, u.first_name, is_admin=is_super)
        return f(message, *args, **kwargs)
    return wrapper


# ═══════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════

def _page_info(total: int, page: int, page_size: int) -> str:
    total_pages = max(1, math.ceil(total / page_size))
    return f"📄 Page {page}/{total_pages} | Total: {total}"


def _file_size_human(size_bytes: int) -> str:
    for unit in ["B", "KB", "MB", "GB"]:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def _scan_assets_to_db():
    """Assets folder scan karke DB update karo"""
    for folder_name, folder_path in ASSET_FOLDERS.items():
        if not os.path.isdir(folder_path):
            continue
        for fname in os.listdir(folder_path):
            ext = os.path.splitext(fname)[1].lower()
            if ext not in ALLOWED_EXTENSIONS:
                continue
            fpath = os.path.join(folder_path, fname)
            fsize = os.path.getsize(fpath)
            db.register_asset(fname, fpath, fsize, uploaded_by=0)


def _main_menu_keyboard(is_admin: bool = False) -> types.InlineKeyboardMarkup:
    mk = types.InlineKeyboardMarkup(row_width=2)
    mk.add(
        types.InlineKeyboardButton("👤 Profile",      callback_data="menu_profile"),
        types.InlineKeyboardButton("📁 Files",        callback_data="menu_files"),
        types.InlineKeyboardButton("📱 Shizuku",      callback_data="menu_shizuku"),
        types.InlineKeyboardButton("📂 My Path",      callback_data="menu_path"),
    )
    if is_admin:
        mk.add(
            types.InlineKeyboardButton("🛡️ Admin Panel", callback_data="menu_admin"),
            types.InlineKeyboardButton("📊 Stats",        callback_data="menu_stats"),
        )
    mk.add(types.InlineKeyboardButton("🚪 Logout", callback_data="logout"))
    return mk


def _admin_menu_keyboard() -> types.InlineKeyboardMarkup:
    mk = types.InlineKeyboardMarkup(row_width=2)
    mk.add(
        types.InlineKeyboardButton("👥 Users",       callback_data="admin_users_1"),
        types.InlineKeyboardButton("📢 Broadcast",   callback_data="admin_broadcast"),
        types.InlineKeyboardButton("📋 Logs",        callback_data="admin_logs_1"),
        types.InlineKeyboardButton("📊 Stats",       callback_data="admin_stats"),
        types.InlineKeyboardButton("🔙 Back",        callback_data="menu_main"),
    )
    return mk


def _shizuku_menu_keyboard() -> types.InlineKeyboardMarkup:
    mk = types.InlineKeyboardMarkup(row_width=2)
    mk.add(
        types.InlineKeyboardButton("📡 Status",       callback_data="shizuku_status"),
        types.InlineKeyboardButton("📱 Device Info",  callback_data="shizuku_devinfo"),
        types.InlineKeyboardButton("📦 Packages",     callback_data="shizuku_packages_all"),
        types.InlineKeyboardButton("📸 Screenshot",   callback_data="shizuku_screenshot"),
        types.InlineKeyboardButton("🔙 Back",         callback_data="menu_main"),
    )
    return mk


# ═══════════════════════════════════════════════════════════════
# /start
# ═══════════════════════════════════════════════════════════════

@bot.message_handler(commands=["start"])
@register_and_guard
def cmd_start(message: types.Message):
    u   = message.from_user
    uid = u.id
    name = u.first_name or "User"
    text = (
        f"🤖 *Namaste {name}!*\n\n"
        f"Telegram Bot ready hai ✅\n\n"
        f"📌 Login karne ke liye: /login\n"
        f"📌 Help ke liye: /help\n"
        f"📌 Menu ke liye: /menu"
    )
    bot.reply_to(message, text)


# ── /help ─────────────────────────────────────────────────────
@bot.message_handler(commands=["help"])
@register_and_guard
def cmd_help(message: types.Message):
    text = (
        "📋 *Available Commands*\n\n"
        "🔐 *Auth*\n"
        "`/login` — Login karo\n"
        "`/logout` — Logout karo\n"
        "`/profile` — Profile dekho\n\n"
        "📁 *Assets*\n"
        "`/listfiles [page]` — Files list karo\n"
        "`/getfile <name>` — File download karo\n\n"
        "📱 *Shizuku/ADB*\n"
        "`/shizuku_status` — Shizuku check\n"
        "`/runcmd <cmd>` — Command chalao\n"
        "`/deviceinfo` — Device info\n"
        "`/screenshot` — Screenshot lo\n"
        "`/packages` — Apps list\n"
        "`/install_apk <file>` — APK install\n"
        "`/uninstall <pkg>` — App hataao\n"
        "`/kill <pkg>` — Force stop\n"
        "`/cleardata <pkg>` — Data clear\n"
        "`/grant <pkg> <perm>` — Permission do\n"
        "`/runscript <name>` — Script chalao\n\n"
        "📂 *Path Manager*\n"
        "`/setpath <path>` — Path set karo\n"
        "`/listpath` — Path files list\n"
        "`/push <file>` — Asset push karo\n"
        "`/pull <file>` — File pull karo\n"
        "`/exec <cmd>` — Path par command\n\n"
        "🛡️ *Admin Only*\n"
        "`/users [page]` `/ban` `/unban` `/makeadmin`\n"
        "`/broadcast <msg>` `/stats` `/logs [page]`\n"
        "`/uploadfile` `/deletefile <name>`"
    )
    bot.reply_to(message, text)


# ═══════════════════════════════════════════════════════════════
# LOGIN / LOGOUT
# ═══════════════════════════════════════════════════════════════

@bot.message_handler(commands=["login"])
@register_and_guard
def cmd_login(message: types.Message):
    uid = message.from_user.id
    if db.validate_session(uid):
        bot.reply_to(message, "✅ Aap pehle se logged in hain!\n\n/menu — Main menu")
        return
    token = db.create_session(uid)
    bot.reply_to(
        message,
        f"✅ *Login successful!*\n\n"
        f"🎫 Session Token (private rakhna):\n`{token[:16]}...`\n\n"
        f"⏰ Session 24 ghante mein expire hoga\n"
        f"/menu — Main menu",
    )
    logger.info(f"User {uid} logged in.")


@bot.message_handler(commands=["logout"])
@register_and_guard
@require_login
def cmd_logout(message: types.Message):
    uid = message.from_user.id
    db.clear_session(uid)
    bot.reply_to(message, "👋 Successfully logged out!\n/login — Wapas login karo")
    logger.info(f"User {uid} logged out.")


# ═══════════════════════════════════════════════════════════════
# MENU
# ═══════════════════════════════════════════════════════════════

@bot.message_handler(commands=["menu"])
@register_and_guard
@require_login
def cmd_menu(message: types.Message):
    uid      = message.from_user.id
    is_admin = db.is_admin(uid) or uid in ADMIN_IDS
    bot.reply_to(
        message,
        "🏠 *Main Menu*\nButton dabao:",
        reply_markup=_main_menu_keyboard(is_admin)
    )


# ═══════════════════════════════════════════════════════════════
# PROFILE
# ═══════════════════════════════════════════════════════════════

@bot.message_handler(commands=["profile"])
@register_and_guard
@require_login
def cmd_profile(message: types.Message):
    uid  = message.from_user.id
    user = db.get_user(uid)
    if not user:
        bot.reply_to(message, "❌ Profile nahi mila.")
        return
    role  = "🛡️ Admin" if user["is_admin"] else "👤 User"
    sku   = "✅ Verified" if user["shizuku_verified"] else "❌ Not verified"
    path  = user["user_path"] or "_(Not set)_"
    text = (
        f"👤 *User Profile*\n\n"
        f"🆔 ID: `{uid}`\n"
        f"📛 Name: *{user['first_name']}*\n"
        f"🔖 Username: @{user['username'] or 'None'}\n"
        f"🎭 Role: {role}\n"
        f"📱 Shizuku: {sku}\n"
        f"📂 Path: `{path}`\n"
        f"📅 Joined: `{user['created_at'][:10]}`\n"
        f"🕐 Last Active: `{user['last_active'][:16]}`"
    )
    bot.reply_to(message, text)


# ═══════════════════════════════════════════════════════════════
# ASSETS / FILE MANAGEMENT
# ═══════════════════════════════════════════════════════════════

@bot.message_handler(commands=["listfiles"])
@register_and_guard
@require_login
def cmd_listfiles(message: types.Message):
    parts = message.text.split()
    page  = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1

    _scan_assets_to_db()
    files, total = db.get_all_assets(page=page, page_size=PAGE_SIZE)

    if not files:
        bot.reply_to(message, "📭 Assets folder khali hai.")
        return

    lines = [f"📁 *Assets Files* — {_page_info(total, page, PAGE_SIZE)}\n"]
    for f in files:
        sz = _file_size_human(f["file_size"])
        lines.append(f"• `{f['file_name']}` _{sz}_ — ⬇️{f['uploads']}")

    total_pages = max(1, math.ceil(total / PAGE_SIZE))
    nav = []
    if page > 1:
        nav.append(types.InlineKeyboardButton("⬅️ Prev", callback_data=f"listfiles_{page-1}"))
    if page < total_pages:
        nav.append(types.InlineKeyboardButton("➡️ Next", callback_data=f"listfiles_{page+1}"))

    mk = types.InlineKeyboardMarkup()
    if nav:
        mk.row(*nav)

    bot.reply_to(message, "\n".join(lines), reply_markup=mk if nav else None)


@bot.message_handler(commands=["getfile"])
@register_and_guard
@require_login
def cmd_getfile(message: types.Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "❓ Usage: `/getfile <filename>`")
        return

    filename = parts[1].strip()
    # Extension check
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        bot.reply_to(message, f"⛔ File type `{ext}` allowed nahi hai.")
        return

    # Search in all asset folders
    found_path = None
    for folder in ASSET_FOLDERS.values():
        candidate = os.path.join(folder, filename)
        if os.path.isfile(candidate):
            found_path = candidate
            break

    if not found_path:
        bot.reply_to(message, f"❌ File `{filename}` nahi mili assets mein.")
        return

    wait_msg = bot.reply_to(message, "⏳ File bhej raha hun...")
    db.increment_download(found_path)
    with open(found_path, "rb") as fh:
        bot.send_document(message.chat.id, fh, caption=f"📎 `{filename}`")
    bot.delete_message(message.chat.id, wait_msg.message_id)
    logger.info(f"User {message.from_user.id} downloaded: {filename}")


@bot.message_handler(commands=["uploadfile"], content_types=["document"])
@register_and_guard
@require_login
@require_admin
def cmd_uploadfile(message: types.Message):
    """Admin file upload kare - reply karo document pe"""
    bot.reply_to(
        message,
        "📤 *File Upload Instructions:*\n\n"
        "1. Ek file bhejo (document)\n"
        "2. Caption mein subfolder likho:\n"
        "   `apks`, `scripts`, `configs`, `tools`, `modules`\n\n"
        "_Example: Caption = `apks`_"
    )


@bot.message_handler(content_types=["document"])
@register_and_guard
@require_login
def handle_document_upload(message: types.Message):
    """Document receive karo aur appropriate assets folder mein save karo"""
    uid = message.from_user.id
    if not (db.is_admin(uid) or uid in ADMIN_IDS):
        return  # Sirf admin upload kar sakta hai

    doc      = message.document
    fname    = doc.file_name or "unnamed"
    ext      = os.path.splitext(fname)[1].lower()

    if ext not in ALLOWED_EXTENSIONS:
        bot.reply_to(message, f"⛔ `{ext}` files allowed nahi hain.")
        return

    caption   = (message.caption or "").strip().lower()
    subfolder = caption if caption in ASSET_FOLDERS else "tools"
    dest_dir  = ASSET_FOLDERS[subfolder]
    dest_path = os.path.join(dest_dir, fname)

    wait = bot.reply_to(message, f"⏳ `{fname}` download ho raha hai...")
    file_info = bot.get_file(doc.file_id)
    data      = bot.download_file(file_info.file_path)

    with open(dest_path, "wb") as fh:
        fh.write(data)

    db.register_asset(fname, dest_path, len(data), uploaded_by=uid)
    db.log_admin_action(uid, "UPLOAD_FILE", details=f"{fname} -> {subfolder}")
    bot.edit_message_text(
        f"✅ `{fname}` upload ho gaya!\n📂 Folder: `{subfolder}`\n📦 Size: {_file_size_human(len(data))}",
        message.chat.id, wait.message_id
    )
    logger.info(f"Admin {uid} uploaded: {fname} to {subfolder}")


@bot.message_handler(commands=["deletefile"])
@register_and_guard
@require_login
@require_admin
def cmd_deletefile(message: types.Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "❓ Usage: `/deletefile <filename>`")
        return

    filename = parts[1].strip()
    deleted  = False
    for folder in ASSET_FOLDERS.values():
        candidate = os.path.join(folder, filename)
        if os.path.isfile(candidate):
            os.remove(candidate)
            db.delete_asset(candidate)
            db.log_admin_action(message.from_user.id, "DELETE_FILE", details=filename)
            bot.reply_to(message, f"🗑️ `{filename}` delete ho gaya!")
            deleted = True
            break

    if not deleted:
        bot.reply_to(message, f"❌ File `{filename}` nahi mili.")


# ═══════════════════════════════════════════════════════════════
# PATH MANAGER
# ═══════════════════════════════════════════════════════════════

@bot.message_handler(commands=["setpath"])
@register_and_guard
@require_login
def cmd_setpath(message: types.Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "❓ Usage: `/setpath /sdcard/MyFolder`")
        return
    path = parts[1].strip()
    db.set_user_path(message.from_user.id, path)
    bot.reply_to(message, f"✅ Path set:\n`{path}`")


@bot.message_handler(commands=["listpath"])
@register_and_guard
@require_login
def cmd_listpath(message: types.Message):
    uid  = message.from_user.id
    user = db.get_user(uid)
    path = user.get("user_path", "") if user else ""
    if not path:
        bot.reply_to(message, "❌ Pehle path set karo: `/setpath <path>`")
        return
    wait = bot.reply_to(message, f"⏳ `{path}` list ho raha hai...")
    ok, out = shizuku.list_dir(path)
    bot.edit_message_text(
        f"📂 *{path}*\n\n```\n{out[:3500]}\n```",
        message.chat.id, wait.message_id
    )


@bot.message_handler(commands=["push"])
@register_and_guard
@require_login
def cmd_push(message: types.Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "❓ Usage: `/push <filename>`")
        return
    uid      = message.from_user.id
    user     = db.get_user(uid)
    dev_path = user.get("user_path", "") if user else ""
    if not dev_path:
        bot.reply_to(message, "❌ Pehle path set karo: `/setpath <path>`")
        return
    filename = parts[1].strip()
    src_path = None
    for folder in ASSET_FOLDERS.values():
        candidate = os.path.join(folder, filename)
        if os.path.isfile(candidate):
            src_path = candidate
            break
    if not src_path:
        bot.reply_to(message, f"❌ `{filename}` assets mein nahi mili.")
        return
    wait = bot.reply_to(message, f"⏳ Push ho raha hai...")
    ok, out = shizuku.push_file(src_path, os.path.join(dev_path, filename))
    status = "✅ Push successful!" if ok else "❌ Push failed!"
    bot.edit_message_text(f"{status}\n```\n{out[:2000]}\n```", message.chat.id, wait.message_id)


@bot.message_handler(commands=["pull"])
@register_and_guard
@require_login
def cmd_pull(message: types.Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "❓ Usage: `/pull <filename>`")
        return
    uid      = message.from_user.id
    user     = db.get_user(uid)
    dev_path = user.get("user_path", "") if user else ""
    if not dev_path:
        bot.reply_to(message, "❌ Pehle path set karo: `/setpath <path>`")
        return
    filename  = parts[1].strip()
    src       = os.path.join(dev_path, filename)
    local_tmp = f"/tmp/pull_{uid}_{filename}"
    wait = bot.reply_to(message, "⏳ Pull ho raha hai...")
    ok, out = shizuku.pull_file(src, local_tmp)
    if ok and os.path.isfile(local_tmp):
        with open(local_tmp, "rb") as fh:
            bot.send_document(message.chat.id, fh, caption=f"📎 Pulled: `{filename}`")
        os.remove(local_tmp)
        bot.delete_message(message.chat.id, wait.message_id)
    else:
        bot.edit_message_text(f"❌ Pull failed!\n```\n{out[:2000]}\n```", message.chat.id, wait.message_id)


@bot.message_handler(commands=["exec"])
@register_and_guard
@require_login
def cmd_exec(message: types.Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "❓ Usage: `/exec <command>`")
        return
    uid  = message.from_user.id
    user = db.get_user(uid)
    path = user.get("user_path", "") if user else ""
    if not path:
        bot.reply_to(message, "❌ Pehle path set karo: `/setpath <path>`")
        return
    cmd  = parts[1]
    wait = bot.reply_to(message, f"⏳ Execute ho raha hai...")
    ok, out = shizuku.exec_at_path(path, cmd)
    status = "✅" if ok else "❌"
    db.log_shizuku_cmd(uid, f"exec:{cmd}", out, "success" if ok else "failed")
    bot.edit_message_text(
        f"{status} `{cmd}`\n\n```\n{out[:3000]}\n```",
        message.chat.id, wait.message_id
    )


@bot.message_handler(commands=["deletepath"])
@register_and_guard
@require_login
def cmd_deletepath(message: types.Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "❓ Usage: `/deletepath <filename>`")
        return
    uid      = message.from_user.id
    user     = db.get_user(uid)
    dev_path = user.get("user_path", "") if user else ""
    if not dev_path:
        bot.reply_to(message, "❌ Pehle path set karo.")
        return
    filepath = os.path.join(dev_path, parts[1].strip())
    ok, out  = shizuku.delete_file(filepath)
    status   = "🗑️ Delete ho gaya!" if ok else "❌ Delete failed!"
    bot.reply_to(message, f"{status}\n```\n{out[:1000]}\n```")


# ═══════════════════════════════════════════════════════════════
# SHIZUKU / ADB COMMANDS
# ═══════════════════════════════════════════════════════════════

@bot.message_handler(commands=["shizuku_status", "verify_shizuku"])
@register_and_guard
@require_login
def cmd_shizuku_status(message: types.Message):
    uid  = message.from_user.id
    wait = bot.reply_to(message, "⏳ Shizuku check ho raha hai...")
    running = shizuku.is_shizuku_running()
    ok_adb, adb_out = shizuku.adb_status()

    db.set_shizuku_verified(uid, running)

    status = "✅ *Shizuku Running!*" if running else "❌ *Shizuku Not Found*"
    adb_status = "✅ ADB Connected" if ok_adb else "❌ ADB Disconnected"
    bot.edit_message_text(
        f"📡 *Shizuku Status*\n\n{status}\n{adb_status}\n\n```\n{adb_out[:500]}\n```",
        message.chat.id, wait.message_id
    )


@bot.message_handler(commands=["runcmd"])
@register_and_guard
@require_login
def cmd_runcmd(message: types.Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "❓ Usage: `/runcmd <shell command>`")
        return
    uid  = message.from_user.id
    cmd  = parts[1]
    wait = bot.reply_to(message, f"⏳ Running: `{cmd[:50]}`...")
    ok, out = shizuku.run(cmd)
    db.log_shizuku_cmd(uid, cmd, out, "success" if ok else "failed")
    status = "✅" if ok else "❌"
    bot.edit_message_text(
        f"{status} *Output:*\n```\n{out[:3800]}\n```",
        message.chat.id, wait.message_id
    )


@bot.message_handler(commands=["grant"])
@register_and_guard
@require_login
def cmd_grant(message: types.Message):
    parts = message.text.split()
    if len(parts) < 3:
        bot.reply_to(message, "❓ Usage: `/grant <package> <permission>`")
        return
    pkg, perm = parts[1], parts[2]
    wait = bot.reply_to(message, f"⏳ Permission de raha hun...")
    ok, out  = shizuku.grant_permission(pkg, perm)
    status   = "✅ Permission granted!" if ok else "❌ Grant failed!"
    db.log_shizuku_cmd(message.from_user.id, f"grant {pkg} {perm}", out, "success" if ok else "failed")
    bot.edit_message_text(f"{status}\n```\n{out[:1000]}\n```", message.chat.id, wait.message_id)


@bot.message_handler(commands=["install_apk"])
@register_and_guard
@require_login
def cmd_install_apk(message: types.Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "❓ Usage: `/install_apk <filename.apk>`")
        return
    filename = parts[1].strip()
    apk_path = os.path.join(ASSET_FOLDERS["apks"], filename)
    if not os.path.isfile(apk_path):
        bot.reply_to(message, f"❌ `{filename}` assets/apks mein nahi mili.")
        return
    wait = bot.reply_to(message, f"⏳ Installing `{filename}`...")
    ok, out = shizuku.install(apk_path)
    status  = "✅ APK Install ho gaya!" if ok else "❌ Installation failed!"
    db.log_shizuku_cmd(message.from_user.id, f"install {filename}", out, "success" if ok else "failed")
    bot.edit_message_text(f"{status}\n```\n{out[:2000]}\n```", message.chat.id, wait.message_id)


@bot.message_handler(commands=["uninstall"])
@register_and_guard
@require_login
def cmd_uninstall(message: types.Message):
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "❓ Usage: `/uninstall <package.name>`")
        return
    pkg  = parts[1]
    wait = bot.reply_to(message, f"⏳ Uninstalling `{pkg}`...")
    ok, out = shizuku.uninstall(pkg)
    status  = "✅ Uninstall ho gaya!" if ok else "❌ Uninstall failed!"
    db.log_shizuku_cmd(message.from_user.id, f"uninstall {pkg}", out, "success" if ok else "failed")
    bot.edit_message_text(f"{status}\n```\n{out[:1000]}\n```", message.chat.id, wait.message_id)


@bot.message_handler(commands=["kill"])
@register_and_guard
@require_login
def cmd_kill(message: types.Message):
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "❓ Usage: `/kill <package.name>`")
        return
    pkg  = parts[1]
    ok, out = shizuku.force_stop(pkg)
    status  = "✅ Force stopped!" if ok else "❌ Failed!"
    bot.reply_to(message, f"{status}\n```\n{out[:500]}\n```")


@bot.message_handler(commands=["cleardata"])
@register_and_guard
@require_login
def cmd_cleardata(message: types.Message):
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "❓ Usage: `/cleardata <package.name>`")
        return
    pkg  = parts[1]
    wait = bot.reply_to(message, f"⏳ Data clear ho raha hai `{pkg}`...")
    ok, out = shizuku.clear_data(pkg)
    status  = "✅ Data cleared!" if ok else "❌ Failed!"
    bot.edit_message_text(f"{status}\n```\n{out[:500]}\n```", message.chat.id, wait.message_id)


@bot.message_handler(commands=["deviceinfo"])
@register_and_guard
@require_login
def cmd_deviceinfo(message: types.Message):
    wait = bot.reply_to(message, "⏳ Device info le raha hun...")
    info = shizuku.get_device_info()
    text = (
        f"📱 *Device Information*\n\n"
        f"🏭 Brand: `{info.get('brand', 'Unknown')}`\n"
        f"📦 Model: `{info.get('model', 'Unknown')}`\n"
        f"🏷️ Device: `{info.get('device', 'Unknown')}`\n"
        f"🏗️ Manufacturer: `{info.get('manufacturer', 'Unknown')}`\n"
        f"🤖 Android: `{info.get('android', 'Unknown')}`\n"
        f"🔢 SDK: `{info.get('sdk', 'Unknown')}`\n"
        f"🏷️ Build: `{info.get('build', 'Unknown')}`\n"
        f"⚙️ CPU ABI: `{info.get('cpu_abi', 'Unknown')}`\n"
        f"🔋 Battery:\n```\n{info.get('battery', 'Unknown')}\n```\n"
        f"⏰ Uptime: `{info.get('uptime', 'Unknown')}`"
    )
    bot.edit_message_text(text, message.chat.id, wait.message_id)


@bot.message_handler(commands=["screenshot"])
@register_and_guard
@require_login
def cmd_screenshot(message: types.Message):
    wait = bot.reply_to(message, "📸 Screenshot le raha hun...")
    ok, result = shizuku.take_screenshot()
    if ok and os.path.isfile(result):
        with open(result, "rb") as fh:
            bot.send_photo(message.chat.id, fh, caption="📸 Screenshot")
        os.remove(result)
        bot.delete_message(message.chat.id, wait.message_id)
    else:
        bot.edit_message_text(f"❌ Screenshot failed:\n```\n{result[:500]}\n```", message.chat.id, wait.message_id)


@bot.message_handler(commands=["packages"])
@register_and_guard
@require_login
def cmd_packages(message: types.Message):
    parts = message.text.split()
    flag  = parts[1] if len(parts) > 1 else ""
    wait  = bot.reply_to(message, "⏳ Packages list ho rahi hai...")
    ok, out = shizuku.list_packages(flag)
    if ok:
        # Split into chunks if too long
        lines  = out.split("\n")
        chunk  = "\n".join(lines[:80])
        total  = len(lines)
        bot.edit_message_text(
            f"📦 *Installed Packages* (first 80 of {total})\n```\n{chunk[:3500]}\n```",
            message.chat.id, wait.message_id
        )
    else:
        bot.edit_message_text(f"❌ Failed:\n```\n{out[:500]}\n```", message.chat.id, wait.message_id)


@bot.message_handler(commands=["runscript"])
@register_and_guard
@require_login
def cmd_runscript(message: types.Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "❓ Usage: `/runscript <scriptname.sh>`")
        return
    filename    = parts[1].strip()
    script_path = os.path.join(ASSET_FOLDERS["scripts"], filename)
    if not os.path.isfile(script_path):
        bot.reply_to(message, f"❌ Script `{filename}` assets/scripts mein nahi mili.")
        return
    wait = bot.reply_to(message, f"⏳ Running script `{filename}`...")
    ok, out = shizuku.run_script(script_path)
    status  = "✅ Script completed!" if ok else "❌ Script failed!"
    db.log_shizuku_cmd(message.from_user.id, f"runscript:{filename}", out, "success" if ok else "failed")
    bot.edit_message_text(f"{status}\n```\n{out[:3500]}\n```", message.chat.id, wait.message_id)


# ═══════════════════════════════════════════════════════════════
# ADMIN COMMANDS
# ═══════════════════════════════════════════════════════════════

@bot.message_handler(commands=["admin"])
@register_and_guard
@require_login
@require_admin
def cmd_admin(message: types.Message):
    bot.reply_to(message, "🛡️ *Admin Panel*\nSelect an option:", reply_markup=_admin_menu_keyboard())


@bot.message_handler(commands=["users"])
@register_and_guard
@require_login
@require_admin
def cmd_users(message: types.Message):
    parts = message.text.split()
    page  = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
    users, total = db.get_all_users(page=page, page_size=PAGE_SIZE)

    lines = [f"👥 *Users List* — {_page_info(total, page, PAGE_SIZE)}\n"]
    for u in users:
        ban   = "🚫" if u["is_banned"] else ""
        adm   = "🛡️" if u["is_admin"] else ""
        lines.append(f"{adm}{ban} `{u['user_id']}` — *{u['first_name']}* @{u['username'] or '-'}")

    total_pages = max(1, math.ceil(total / PAGE_SIZE))
    nav = []
    if page > 1:
        nav.append(types.InlineKeyboardButton("⬅️", callback_data=f"users_{page-1}"))
    if page < total_pages:
        nav.append(types.InlineKeyboardButton("➡️", callback_data=f"users_{page+1}"))
    mk = types.InlineKeyboardMarkup()
    if nav:
        mk.row(*nav)

    bot.reply_to(message, "\n".join(lines), reply_markup=mk if nav else None)


@bot.message_handler(commands=["ban"])
@register_and_guard
@require_login
@require_admin
def cmd_ban(message: types.Message):
    parts = message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        bot.reply_to(message, "❓ Usage: `/ban <user_id>`")
        return
    target = int(parts[1])
    if target in ADMIN_IDS:
        bot.reply_to(message, "⛔ Super admin ko ban nahi kar sakte!")
        return
    db.ban_user(target)
    db.log_admin_action(message.from_user.id, "BAN", target_id=target)
    bot.reply_to(message, f"🚫 User `{target}` ban ho gaya!")
    try:
        bot.send_message(target, "🚫 Aap ko admin ne ban kar diya hai.")
    except Exception:
        pass


@bot.message_handler(commands=["unban"])
@register_and_guard
@require_login
@require_admin
def cmd_unban(message: types.Message):
    parts = message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        bot.reply_to(message, "❓ Usage: `/unban <user_id>`")
        return
    target = int(parts[1])
    db.unban_user(target)
    db.log_admin_action(message.from_user.id, "UNBAN", target_id=target)
    bot.reply_to(message, f"✅ User `{target}` unban ho gaya!")
    try:
        bot.send_message(target, "✅ Aap ka ban lift ho gaya hai!")
    except Exception:
        pass


@bot.message_handler(commands=["makeadmin"])
@register_and_guard
@require_login
@require_admin
def cmd_makeadmin(message: types.Message):
    parts = message.text.split()
    if len(parts) < 2 or not parts[1].isdigit():
        bot.reply_to(message, "❓ Usage: `/makeadmin <user_id>`")
        return
    target = int(parts[1])
    db.make_admin(target)
    db.log_admin_action(message.from_user.id, "MAKE_ADMIN", target_id=target)
    bot.reply_to(message, f"🛡️ User `{target}` admin ban gaya!")
    try:
        bot.send_message(target, "🛡️ Aap ko admin bana diya gaya hai!")
    except Exception:
        pass


@bot.message_handler(commands=["broadcast"])
@register_and_guard
@require_login
@require_admin
def cmd_broadcast(message: types.Message):
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2:
        bot.reply_to(message, "❓ Usage: `/broadcast <message>`")
        return
    text     = parts[1]
    user_ids = db.get_all_user_ids()
    wait     = bot.reply_to(message, f"📢 {len(user_ids)} users ko bhej raha hun...")
    sent, failed = 0, 0
    for uid in user_ids:
        try:
            bot.send_message(uid, f"📢 *Broadcast:*\n\n{text}")
            sent += 1
        except Exception:
            failed += 1
    db.log_admin_action(message.from_user.id, "BROADCAST", details=f"sent={sent} failed={failed}")
    bot.edit_message_text(
        f"📢 Broadcast complete!\n✅ Sent: {sent}\n❌ Failed: {failed}",
        message.chat.id, wait.message_id
    )


@bot.message_handler(commands=["stats"])
@register_and_guard
@require_login
@require_admin
def cmd_stats(message: types.Message):
    s = db.get_stats()
    text = (
        f"📊 *Bot Statistics*\n\n"
        f"👥 Total Users: `{s['total_users']}`\n"
        f"🟢 Active (24h): `{s['active_users']}`\n"
        f"🚫 Banned: `{s['banned_users']}`\n"
        f"🛡️ Admins: `{s['admin_users']}`\n"
        f"📱 Shizuku Commands: `{s['total_cmds']}`\n"
        f"📁 Asset Files: `{s['total_assets']}`\n"
        f"📋 Admin Logs: `{s['total_logs']}`\n"
        f"\n🕐 `{datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC`"
    )
    bot.reply_to(message, text)


@bot.message_handler(commands=["logs"])
@register_and_guard
@require_login
@require_admin
def cmd_logs(message: types.Message):
    parts = message.text.split()
    page  = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 1
    logs, total = db.get_admin_logs(page=page, page_size=PAGE_SIZE)

    lines = [f"📋 *Admin Logs* — {_page_info(total, page, PAGE_SIZE)}\n"]
    for log in logs:
        lines.append(
            f"• [{log['timestamp'][:16]}] `{log['admin_id']}` → *{log['action']}*"
            + (f" on `{log['target_id']}`" if log["target_id"] else "")
            + (f"\n  _{log['details']}_" if log["details"] else "")
        )

    total_pages = max(1, math.ceil(total / PAGE_SIZE))
    nav = []
    if page > 1:
        nav.append(types.InlineKeyboardButton("⬅️", callback_data=f"logs_{page-1}"))
    if page < total_pages:
        nav.append(types.InlineKeyboardButton("➡️", callback_data=f"logs_{page+1}"))
    mk = types.InlineKeyboardMarkup()
    if nav:
        mk.row(*nav)

    bot.reply_to(message, "\n".join(lines), reply_markup=mk if nav else None)


# ═══════════════════════════════════════════════════════════════
# INLINE KEYBOARD CALLBACKS
# ═══════════════════════════════════════════════════════════════

@bot.callback_query_handler(func=lambda c: True)
def callback_handler(call: types.CallbackQuery):
    uid  = call.from_user.id
    data = call.data

    # Auto-ensure registration
    db.register_user(uid, call.from_user.username, call.from_user.first_name, is_admin=(uid in ADMIN_IDS))

    # ── Session auto-check for protected menus ────────────────
    if data not in ("logout",) and not db.validate_session(uid):
        bot.answer_callback_query(call.id, "🔐 Login karo pehle!", show_alert=True)
        return

    # ── Menu routing ──────────────────────────────────────────
    if data == "menu_main":
        is_admin = db.is_admin(uid) or uid in ADMIN_IDS
        bot.edit_message_text(
            "🏠 *Main Menu*", call.message.chat.id, call.message.message_id,
            reply_markup=_main_menu_keyboard(is_admin)
        )

    elif data == "menu_profile":
        user  = db.get_user(uid)
        role  = "🛡️ Admin" if user and user["is_admin"] else "👤 User"
        sku   = "✅" if user and user["shizuku_verified"] else "❌"
        path  = (user and user.get("user_path")) or "_(not set)_"
        bot.edit_message_text(
            f"👤 *Profile*\n🆔 `{uid}`\n🎭 {role}\n📱 Shizuku: {sku}\n📂 Path: `{path}`",
            call.message.chat.id, call.message.message_id,
            reply_markup=types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton("🔙 Back", callback_data="menu_main")
            )
        )

    elif data == "menu_files":
        _scan_assets_to_db()
        files, total = db.get_all_assets(page=1, page_size=PAGE_SIZE)
        lines = [f"📁 *Assets* ({total} files)\n"]
        for f in files:
            lines.append(f"• `{f['file_name']}` _{_file_size_human(f['file_size'])}_")
        mk = types.InlineKeyboardMarkup().add(
            types.InlineKeyboardButton("🔙 Back", callback_data="menu_main")
        )
        bot.edit_message_text("\n".join(lines) or "📭 Khali hai", call.message.chat.id, call.message.message_id, reply_markup=mk)

    elif data == "menu_shizuku":
        bot.edit_message_text(
            "📱 *Shizuku Menu*", call.message.chat.id, call.message.message_id,
            reply_markup=_shizuku_menu_keyboard()
        )

    elif data == "shizuku_status":
        running = shizuku.is_shizuku_running()
        status  = "✅ Running" if running else "❌ Not Found"
        db.set_shizuku_verified(uid, running)
        bot.edit_message_text(
            f"📡 *Shizuku Status*\n{status}",
            call.message.chat.id, call.message.message_id,
            reply_markup=types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton("🔙 Back", callback_data="menu_shizuku")
            )
        )

    elif data == "shizuku_devinfo":
        bot.answer_callback_query(call.id, "⏳ Device info le raha hun...")
        info = shizuku.get_device_info()
        text = (
            f"📱 *Device Info*\n"
            f"Brand: `{info.get('brand')}`\n"
            f"Model: `{info.get('model')}`\n"
            f"Android: `{info.get('android')}`\n"
            f"SDK: `{info.get('sdk')}`"
        )
        bot.edit_message_text(
            text, call.message.chat.id, call.message.message_id,
            reply_markup=types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton("🔙 Back", callback_data="menu_shizuku")
            )
        )

    elif data.startswith("shizuku_packages"):
        flag = "-3" if "3p" in data else ("-s" if "sys" in data else "")
        bot.answer_callback_query(call.id, "⏳ Loading...")
        ok, out = shizuku.list_packages(flag)
        lines   = out.split("\n")[:50]
        bot.edit_message_text(
            f"📦 *Packages*\n```\n{chr(10).join(lines)}\n```",
            call.message.chat.id, call.message.message_id,
            reply_markup=types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton("🔙 Back", callback_data="menu_shizuku")
            )
        )

    elif data == "shizuku_screenshot":
        bot.answer_callback_query(call.id, "📸 Screenshot le raha hun...")
        ok, result = shizuku.take_screenshot()
        if ok and os.path.isfile(result):
            with open(result, "rb") as fh:
                bot.send_photo(call.message.chat.id, fh, caption="📸 Screenshot")
            os.remove(result)
        else:
            bot.send_message(call.message.chat.id, f"❌ Screenshot failed:\n```\n{result[:300]}\n```")

    elif data == "menu_path":
        user = db.get_user(uid)
        path = (user and user.get("user_path")) or "_(not set)_"
        bot.edit_message_text(
            f"📂 *Path Manager*\nCurrent Path: `{path}`\n\n`/setpath <path>` se change karo",
            call.message.chat.id, call.message.message_id,
            reply_markup=types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton("🔙 Back", callback_data="menu_main")
            )
        )

    elif data == "menu_admin":
        if not (db.is_admin(uid) or uid in ADMIN_IDS):
            bot.answer_callback_query(call.id, "⛔ Access denied!", show_alert=True)
            return
        bot.edit_message_text(
            "🛡️ *Admin Panel*", call.message.chat.id, call.message.message_id,
            reply_markup=_admin_menu_keyboard()
        )

    elif data == "menu_stats" or data == "admin_stats":
        if not (db.is_admin(uid) or uid in ADMIN_IDS):
            bot.answer_callback_query(call.id, "⛔ Access denied!", show_alert=True)
            return
        s = db.get_stats()
        bot.edit_message_text(
            f"📊 *Stats*\n👥 Users: `{s['total_users']}`\n🟢 Active: `{s['active_users']}`\n"
            f"🚫 Banned: `{s['banned_users']}`\n📱 Cmds: `{s['total_cmds']}`\n📁 Assets: `{s['total_assets']}`",
            call.message.chat.id, call.message.message_id,
            reply_markup=types.InlineKeyboardMarkup().add(
                types.InlineKeyboardButton("🔙 Back", callback_data="menu_admin")
            )
        )

    elif data.startswith("admin_users_"):
        page = int(data.split("_")[-1])
        users, total = db.get_all_users(page=page, page_size=PAGE_SIZE)
        lines = [f"👥 *Users* — {_page_info(total, page, PAGE_SIZE)}\n"]
        for u in users:
            ban = "🚫" if u["is_banned"] else ""
            adm = "🛡️" if u["is_admin"] else ""
            lines.append(f"{adm}{ban} `{u['user_id']}` {u['first_name']}")
        total_pages = max(1, math.ceil(total / PAGE_SIZE))
        mk = types.InlineKeyboardMarkup(row_width=3)
        nav = []
        if page > 1:
            nav.append(types.InlineKeyboardButton("⬅️", callback_data=f"admin_users_{page-1}"))
        nav.append(types.InlineKeyboardButton("🔙", callback_data="menu_admin"))
        if page < total_pages:
            nav.append(types.InlineKeyboardButton("➡️", callback_data=f"admin_users_{page+1}"))
        mk.row(*nav)
        bot.edit_message_text("\n".join(lines), call.message.chat.id, call.message.message_id, reply_markup=mk)

    elif data.startswith("admin_logs_"):
        page = int(data.split("_")[-1])
        logs, total = db.get_admin_logs(page=page, page_size=PAGE_SIZE)
        lines = [f"📋 *Logs* — {_page_info(total, page, PAGE_SIZE)}\n"]
        for log in logs:
            lines.append(f"• `{log['action']}` by `{log['admin_id']}` [{log['timestamp'][:16]}]")
        total_pages = max(1, math.ceil(total / PAGE_SIZE))
        mk = types.InlineKeyboardMarkup(row_width=3)
        nav = []
        if page > 1:
            nav.append(types.InlineKeyboardButton("⬅️", callback_data=f"admin_logs_{page-1}"))
        nav.append(types.InlineKeyboardButton("🔙", callback_data="menu_admin"))
        if page < total_pages:
            nav.append(types.InlineKeyboardButton("➡️", callback_data=f"admin_logs_{page+1}"))
        mk.row(*nav)
        bot.edit_message_text("\n".join(lines), call.message.chat.id, call.message.message_id, reply_markup=mk)

    elif data.startswith("listfiles_"):
        page = int(data.split("_")[-1])
        _scan_assets_to_db()
        files, total = db.get_all_assets(page=page, page_size=PAGE_SIZE)
        lines = [f"📁 *Assets* — {_page_info(total, page, PAGE_SIZE)}\n"]
        for f in files:
            lines.append(f"• `{f['file_name']}` _{_file_size_human(f['file_size'])}_")
        total_pages = max(1, math.ceil(total / PAGE_SIZE))
        mk = types.InlineKeyboardMarkup(row_width=2)
        nav = []
        if page > 1:
            nav.append(types.InlineKeyboardButton("⬅️", callback_data=f"listfiles_{page-1}"))
        if page < total_pages:
            nav.append(types.InlineKeyboardButton("➡️", callback_data=f"listfiles_{page+1}"))
        if nav:
            mk.row(*nav)
        bot.edit_message_text("\n".join(lines), call.message.chat.id, call.message.message_id, reply_markup=mk if nav else None)

    elif data == "logout":
        db.clear_session(uid)
        bot.edit_message_text("👋 Logged out!\n/login — Wapas login karo", call.message.chat.id, call.message.message_id)

    bot.answer_callback_query(call.id)


# ═══════════════════════════════════════════════════════════════
# ERROR HANDLER
# ═══════════════════════════════════════════════════════════════

@bot.message_handler(func=lambda m: True)
def unknown_command(message: types.Message):
    bot.reply_to(message, "❓ Command samajh nahi aaya.\n/help — Command list dekho")


# ═══════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    logger.info("🤖 Bot start ho raha hai...")
    _scan_assets_to_db()
    logger.info(f"✅ Assets scan complete. Bot polling shuru...")
    bot.infinity_polling(timeout=30, long_polling_timeout=20, logger_level=logging.WARNING)
