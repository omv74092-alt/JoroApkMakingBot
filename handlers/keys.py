from telegram import Update
from telegram.ext import ContextTypes
from database.db import use_key, check_user_key
from utils.keyboard import back_to_main

async def activate_key(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    args = ctx.args

    q = update.callback_query
    if q:
        await q.answer()
        await q.message.reply_text(
            "🔑 *Key Activate Karo*\n\nApni key bhejo:\n`/key APK-XXXX-XXXX-XXXX`",
            parse_mode="Markdown"
        )
        return

    if not args:
        existing = check_user_key(user.id)
        if existing:
            await update.message.reply_text(
                f"✅ *Key Already Active!*\n\n"
                f"Key: `{existing['key']}`\n"
                f"Max Builds: {existing['max_builds']}\n"
                f"Activated: {existing['used_at'][:10] if existing['used_at'] else 'N/A'}",
                parse_mode="Markdown",
                reply_markup=back_to_main()
            )
        else:
            await update.message.reply_text(
                "🔑 Usage: `/key YOUR-KEY-HERE`",
                parse_mode="Markdown"
            )
        return

    key = args[0].strip().upper()
    existing = check_user_key(user.id)
    if existing:
        await update.message.reply_text(
            "⚠️ Tumhare paas already ek active key hai!\n"
            f"Key: `{existing['key']}`",
            parse_mode="Markdown"
        )
        return

    if use_key(key, user.id):
        await update.message.reply_text(
            f"🎉 *Key Activated Successfully!*\n\n"
            f"Key: `{key}`\n\n"
            f"Ab tum APK build kar sakte ho! /start",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "❌ *Invalid or Already Used Key!*\n\n"
            "Key galat hai ya kisi ne pehle use kar li hai.",
            parse_mode="Markdown"
        )
