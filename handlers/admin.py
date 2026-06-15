from telegram import Update
from telegram.ext import ContextTypes
from database.db import (get_stats, get_all_users, get_all_keys,
                          create_key, revoke_key, ban_user,
                          get_setting, set_setting)
from utils.helpers import generate_key
from utils.keyboard import admin_panel, key_management, back_to_main
from config import ADMIN_IDS

def is_admin(user_id):
    return user_id in ADMIN_IDS

async def admin_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Access denied.")
        return
    await update.message.reply_text(
        "⚙️ *Admin Panel*\nSelect an option:",
        parse_mode="Markdown",
        reply_markup=admin_panel()
    )

async def admin_stats(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q: await q.answer()

    stats = get_stats()
    maintenance = get_setting("maintenance")
    max_builds  = get_setting("max_builds_per_day")

    text = (
        "📊 *Bot Statistics*\n\n"
        f"👥 Total Users: *{stats['users']}*\n"
        f"📦 Total Builds: *{stats['builds']}*\n"
        f"🔑 Active Keys: *{stats['active_keys']}*\n\n"
        f"🔧 Maintenance: *{'ON' if maintenance=='1' else 'OFF'}*\n"
        f"📈 Max Builds/Day: *{max_builds}*"
    )

    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔧 Toggle Maintenance", callback_data="toggle_maintenance")],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]
    ])

    msg = update.message or q.message
    await msg.reply_text(text, parse_mode="Markdown", reply_markup=kb)

async def admin_users_list(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q: await q.answer()

    users = get_all_users()
    text = f"👥 *Total Users: {len(users)}*\n\n"
    for u in users[-10:]:
        ban_status = "🚫" if u["is_banned"] else "✅"
        text += f"{ban_status} `{u['user_id']}` — @{u.get('username','N/A')} — Builds: {u['builds_done']}\n"

    msg = update.message or q.message
    await msg.reply_text(text, parse_mode="Markdown", reply_markup=back_to_main())

async def admin_keys_panel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q: await q.answer()
    msg = update.message or q.message
    await msg.reply_text("🔑 *Key Management*", parse_mode="Markdown",
                         reply_markup=key_management())

async def gen_key_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ Access denied.")
        return

    args = ctx.args
    count     = int(args[0]) if args else 1
    max_builds = int(args[1]) if len(args) > 1 else 5
    count = min(count, 20)  # max 20 at once

    keys = []
    for _ in range(count):
        key = generate_key()
        create_key(key, update.effective_user.id, max_builds)
        keys.append(key)

    text = f"✅ *{count} Key(s) Generated:*\n\n"
    text += "\n".join(f"`{k}`" for k in keys)
    text += f"\n\n_Max builds each: {max_builds}_"

    await update.message.reply_text(text, parse_mode="Markdown")

async def list_keys_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    keys = get_all_keys()
    if not keys:
        await update.message.reply_text("No keys found.")
        return

    text = f"🔑 *All Keys ({len(keys)}):*\n\n"
    for k in keys[:15]:
        status = "✅" if k["is_active"] and not k["used_by"] else ("🔒" if k["used_by"] else "❌")
        text += f"{status} `{k['key']}` — Used by: `{k['used_by'] or 'None'}`\n"

    await update.message.reply_text(text, parse_mode="Markdown")

async def revoke_key_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    args = ctx.args
    if not args:
        await update.message.reply_text("Usage: `/revokekey KEY`", parse_mode="Markdown")
        return
    revoke_key(args[0].upper())
    await update.message.reply_text(f"❌ Key `{args[0].upper()}` revoked.", parse_mode="Markdown")

async def ban_user_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    args = ctx.args
    if not args:
        await update.message.reply_text("Usage: `/ban <user_id>`", parse_mode="Markdown")
        return
    ban_user(int(args[0]), True)
    await update.message.reply_text(f"🚫 User `{args[0]}` banned.", parse_mode="Markdown")

async def unban_user_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    args = ctx.args
    if not args:
        await update.message.reply_text("Usage: `/unban <user_id>`", parse_mode="Markdown")
        return
    ban_user(int(args[0]), False)
    await update.message.reply_text(f"✅ User `{args[0]}` unbanned.", parse_mode="Markdown")

async def broadcast_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    msg_text = " ".join(ctx.args)
    if not msg_text:
        await update.message.reply_text("Usage: `/broadcast Your message here`",
                                        parse_mode="Markdown")
        return

    users = get_all_users()
    sent, failed = 0, 0
    for u in users:
        try:
            await ctx.bot.send_message(u["user_id"], f"📢 *Announcement:*\n\n{msg_text}",
                                       parse_mode="Markdown")
            sent += 1
        except:
            failed += 1

    await update.message.reply_text(
        f"📢 Broadcast done!\n✅ Sent: {sent}\n❌ Failed: {failed}"
    )

async def toggle_maintenance(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q: await q.answer()
    if not is_admin(update.effective_user.id):
        return
    current = get_setting("maintenance")
    new_val = "0" if current == "1" else "1"
    set_setting("maintenance", new_val)
    status = "ON 🔧" if new_val == "1" else "OFF ✅"
    msg = update.message or q.message
    await msg.reply_text(f"Maintenance mode: *{status}*", parse_mode="Markdown")
