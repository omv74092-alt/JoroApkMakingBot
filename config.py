# ============================================================
# config.py - Bot Configuration File
# Telegram Bot - Master Config
# ============================================================

import os

# ── Bot Token (BotFather se milega) ──────────────────────────
BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

# ── Admin Telegram IDs (list of int) ─────────────────────────
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "123456789").split(",")]

# ── Assets Folder Path ────────────────────────────────────────
ASSETS_PATH = os.getenv("ASSETS_PATH", "assets")

# ── Database File ─────────────────────────────────────────────
DB_PATH = os.getenv("DB_PATH", "bot_database.db")

# ── Session Settings ─────────────────────────────────────────
SESSION_EXPIRY_HOURS = 24

# ── Rate Limiting ─────────────────────────────────────────────
RATE_LIMIT_COMMANDS = 5       # Max commands per window
RATE_LIMIT_WINDOW   = 1       # Window in seconds
COMMAND_COOLDOWN    = 2       # Seconds between commands per user

# ── File Whitelist ────────────────────────────────────────────
ALLOWED_EXTENSIONS = {".apk", ".zip", ".sh", ".py", ".json", ".bin", ".dex", ".txt"}

# ── Assets Sub-folders ────────────────────────────────────────
ASSET_FOLDERS = {
    "scripts": os.path.join(ASSETS_PATH, "scripts"),
    "apks":    os.path.join(ASSETS_PATH, "apks"),
    "modules": os.path.join(ASSETS_PATH, "modules"),
    "configs": os.path.join(ASSETS_PATH, "configs"),
    "tools":   os.path.join(ASSETS_PATH, "tools"),
}

# ── Shizuku / ADB Settings ───────────────────────────────────
ADB_PATH        = os.getenv("ADB_PATH", "adb")          # adb binary path
SHIZUKU_SOCKET  = os.getenv("SHIZUKU_SOCKET", "/dev/socket/shizuku")
USE_ADB_FALLBACK = True

# ── Pagination ────────────────────────────────────────────────
PAGE_SIZE = 10

# ── Logging ───────────────────────────────────────────────────
LOG_FILE  = "bot.log"
LOG_LEVEL = "INFO"
