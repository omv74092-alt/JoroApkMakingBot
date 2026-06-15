import os

# ── Bot Settings ──────────────────────────────────────────
BOT_TOKEN    = os.getenv("BOT_TOKEN", "")
ADMIN_IDS    = list(map(int, os.getenv("ADMIN_IDS", "").split(","))) if os.getenv("ADMIN_IDS") else []

# ── GitHub Settings (for APK build) ───────────────────────
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
GITHUB_REPO  = os.getenv("GITHUB_REPO", "username/apk-builder")  # your repo

# ── Database ──────────────────────────────────────────────
DATABASE_URL = os.getenv("DATABASE_URL", "bot_data.db")

# ── APK Build Settings ────────────────────────────────────
APK_BUILD_TIMEOUT = int(os.getenv("APK_BUILD_TIMEOUT", "1800"))  # 30 min

# ── Messages ──────────────────────────────────────────────
BOT_NAME    = "APK Builder Bot"
BOT_VERSION = "1.0.0"
