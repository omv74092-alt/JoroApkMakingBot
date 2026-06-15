from telegram import Update
from telegram.ext import ContextTypes
from database.db import get_user, check_user_key
from utils.keyboard import main_menu, back_to_main
from config import ADMIN_IDS

async def profile(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = get_user(user.id)
    key_info = check_user_key(user.id)
    is_admin = user.id in ADMIN_IDS

    q = update.callback_query
    if q: await q.answer()

    text = (
        f"👤 *Your Profile*\n\n"
        f"🆔 ID: `{user.id}`\n"
        f"👤 Name: {user.full_name}\n"
        f"📛 Username: @{user.username or 'N/A'}\n"
        f"🎖️ Role: {'👑 Admin' if is_admin else '👤 User'}\n\n"
        f"🔑 Key Status: {'✅ Active' if key_info else '❌ No Key'}\n"
    )
    if key_info:
        text += (
            f"   Key: `{key_info['key']}`\n"
            f"   Max Builds: {key_info['max_builds']}\n"
        )
    if db_user:
        text += f"\n📦 Total Builds: {db_user.get('builds_done', 0)}\n"
        text += f"📅 Joined: {db_user.get('joined_at','')[:10]}"

    msg = update.message or q.message
    await msg.reply_text(text, parse_mode="Markdown",
                         reply_markup=back_to_main())
