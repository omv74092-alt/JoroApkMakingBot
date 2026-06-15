from telegram import Update
from telegram.ext import ContextTypes
from database.db import add_user, get_user, get_setting
from utils.keyboard import main_menu
from config import ADMIN_IDS

WELCOME = """
╔══════════════════════════╗
║   🤖 *APK Builder Bot*   ║
╚══════════════════════════╝

Kya kar sakta hai ye bot:
📦 Custom APK build karo
🔑 Key system se access lo
⚙️ Features choose karo
🚀 Direct Telegram pe APK pao

*Shuru karne ke liye neeche click karo!*
"""

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    add_user(user.id, user.username, user.full_name)

    if get_setting("maintenance") == "1" and user.id not in ADMIN_IDS:
        await update.message.reply_text("🔧 Bot maintenance mode mein hai. Thodi der baad try karo.")
        return

    is_admin = user.id in ADMIN_IDS
    await update.message.reply_text(
        WELCOME,
        parse_mode="Markdown",
        reply_markup=main_menu(is_admin)
    )

async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = """
*📖 Help & Commands*

`/start` — Bot shuru karo
`/build` — APK build shuru karo
`/status <id>` — Build status check karo
`/key <KEY>` — Key activate karo
`/mybuilds` — Apni builds dekho
`/profile` — Apna profile dekho
`/cancel` — Current process cancel karo

*Admin Commands:*
`/admin` — Admin panel
`/genkey [count]` — Keys generate karo
`/ban <user_id>` — User ban karo
`/broadcast <msg>` — Sab ko message bhejo
`/stats` — Bot statistics

*APK Features Available:*
✅ Shizuku Support
✅ File Manager
✅ Login System
✅ Dark Theme
✅ Key Verification
✅ WebView Mode
    """
    await update.message.reply_text(text, parse_mode="Markdown")

async def cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    ctx.user_data.clear()
    await update.message.reply_text(
        "❌ Cancelled.",
        reply_markup=main_menu(update.effective_user.id in ADMIN_IDS)
    )
