import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from database.db import (create_build, update_build, get_user_builds,
                          get_build, check_user_key, get_setting)
from utils.apk_builder import trigger_build, check_build_status, download_apk
from utils.helpers import validate_package, format_build_status
from utils.keyboard import build_apk_menu, build_features, back_to_main
from config import ADMIN_IDS

# Conversation states
APP_NAME, PKG_NAME, APP_URL, ICON, FEATURES, CONFIRM = range(6)

FEAT_LABELS = {
    "feat_shizuku":     ("shizuku",      "Shizuku Support"),
    "feat_filemanager": ("file_manager", "File Manager"),
    "feat_login":       ("login_screen", "Login Screen"),
    "feat_darktheme":   ("dark_theme",   "Dark Theme"),
    "feat_ads":         ("ads",          "Ads Enabled"),
    "feat_keysystem":   ("key_system",   "Key System"),
}

async def build_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    db_user = check_user_key(user.id)

    if user.id not in ADMIN_IDS and not db_user:
        q = update.callback_query
        if q: await q.answer()
        msg = update.message or q.message
        await msg.reply_text(
            "🔑 *Key Required!*\n\nAPK build karne ke liye pehle key activate karo.\n\n"
            "Use: `/key YOUR-KEY-HERE`",
            parse_mode="Markdown"
        )
        return ConversationHandler.END

    ctx.user_data["features"] = {
        "shizuku": False, "file_manager": False, "login_screen": False,
        "dark_theme": True, "ads": False, "key_system": False
    }

    q = update.callback_query
    if q:
        await q.answer()
        await q.message.reply_text("📦 *APK Build Wizard*\n\nStep 1/4 — App ka naam kya hoga?",
                                   parse_mode="Markdown")
    else:
        await update.message.reply_text("📦 *APK Build Wizard*\n\nStep 1/4 — App ka naam kya hoga?",
                                        parse_mode="Markdown")
    return APP_NAME

async def got_app_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if len(name) < 2 or len(name) > 30:
        await update.message.reply_text("❌ Naam 2-30 characters ka hona chahiye. Dobara bhejo:")
        return APP_NAME

    ctx.user_data["app_name"] = name
    await update.message.reply_text(
        f"✅ App Name: *{name}*\n\n"
        "Step 2/4 — Package name kya hoga?\nExample: `com.mycompany.myapp`",
        parse_mode="Markdown"
    )
    return PKG_NAME

async def got_pkg_name(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    pkg = update.message.text.strip().lower()
    if not validate_package(pkg):
        await update.message.reply_text(
            "❌ Invalid package name!\nFormat: `com.example.app`\nDobara bhejo:",
            parse_mode="Markdown"
        )
        return PKG_NAME

    ctx.user_data["package"] = pkg
    await update.message.reply_text(
        f"✅ Package: `{pkg}`\n\n"
        "Step 3/4 — App URL/WebView URL kya hoga?\n"
        "_(Skip karne ke liye `/skip` bhejo)_",
        parse_mode="Markdown"
    )
    return APP_URL

async def got_app_url(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    ctx.user_data["app_url"] = "" if text == "/skip" else text

    await update.message.reply_text(
        "Step 4/4 — *Features select karo:*\n_(Dark theme by default on hai)_",
        parse_mode="Markdown",
        reply_markup=_feature_kb(ctx.user_data["features"])
    )
    return FEATURES

async def toggle_feature(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    cb = q.data

    if cb == "confirm_build":
        return await confirm_build(update, ctx)

    if cb in FEAT_LABELS:
        key, label = FEAT_LABELS[cb]
        ctx.user_data["features"][key] = not ctx.user_data["features"].get(key, False)
        await q.edit_message_reply_markup(_feature_kb(ctx.user_data["features"]))

    return FEATURES

async def confirm_build(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    if q: await q.answer()

    d = ctx.user_data
    feats = d.get("features", {})
    feat_list = "\n".join(f"  {'✅' if v else '❌'} {FEAT_LABELS.get(f'feat_{k}',('',k))[1]}"
                          for k, v in feats.items())

    summary = (
        f"📋 *Build Summary*\n\n"
        f"📦 App: *{d.get('app_name')}*\n"
        f"📌 Package: `{d.get('package')}`\n"
        f"🌐 URL: `{d.get('app_url') or 'None'}`\n\n"
        f"*Features:*\n{feat_list}\n\n"
        f"Build start karein?"
    )

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚀 Build!", callback_data="do_build"),
         InlineKeyboardButton("❌ Cancel", callback_data="cancel_build")]
    ])

    msg = update.message or q.message
    await msg.reply_text(summary, parse_mode="Markdown", reply_markup=kb)
    return CONFIRM

async def do_build(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer("🚀 Build shuru ho rahi hai...")

    user = update.effective_user
    d = ctx.user_data

    build_id = create_build(user.id, d["app_name"], d["package"])
    status_msg = await q.message.reply_text(
        f"⏳ *Build #{build_id} queued...*\n\nGitHub Actions pe bheja ja raha hai...",
        parse_mode="Markdown"
    )

    result = trigger_build(
        app_name=d["app_name"],
        package_name=d["package"],
        app_url=d.get("app_url", ""),
        features=d.get("features", {}),
        icon_url=d.get("icon_url", "")
    )

    if not result["success"]:
        update_build(build_id, status="failed")
        await status_msg.edit_text(f"❌ Build trigger failed!\n`{result.get('error','Unknown')}`",
                                   parse_mode="Markdown")
        return ConversationHandler.END

    run_id = result["run_id"]
    update_build(build_id, status="running", gh_run_id=str(run_id))
    await status_msg.edit_text(
        f"🔄 *Build #{build_id} running...*\n"
        f"GitHub Run ID: `{run_id}`\n\n"
        f"_15-20 minute mein APK ready hogi..._\n"
        f"Use `/status {build_id}` to check progress.",
        parse_mode="Markdown"
    )

    asyncio.create_task(_poll_build(ctx, user.id, build_id, run_id, status_msg))
    ctx.user_data.clear()
    return ConversationHandler.END

async def _poll_build(ctx, user_id, build_id, run_id, status_msg):
    """Background polling for build completion"""
    for _ in range(60):  # poll for max 30 min
        await asyncio.sleep(30)
        result = check_build_status(run_id)

        if result["status"] == "success":
            apk_bytes = download_apk(result["apk_url"]) if result["apk_url"] else None
            from datetime import datetime
            update_build(build_id, status="success",
                         apk_url=result["apk_url"],
                         finished_at=datetime.now().isoformat())

            if apk_bytes:
                await ctx.bot.send_document(
                    chat_id=user_id,
                    document=apk_bytes,
                    filename=f"build_{build_id}.zip",
                    caption=f"✅ *Build #{build_id} Complete!*\nAPK ready hai 🎉",
                    parse_mode="Markdown"
                )
            else:
                await ctx.bot.send_message(
                    user_id,
                    f"✅ Build #{build_id} complete! APK URL:\n{result['apk_url']}"
                )
            break

        elif result["status"] == "failed":
            update_build(build_id, status="failed")
            await ctx.bot.send_message(
                user_id,
                f"❌ *Build #{build_id} failed!*\nGitHub Actions logs check karo.",
                parse_mode="Markdown"
            )
            break

async def build_status(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    args = ctx.args
    if not args:
        await update.message.reply_text("Usage: `/status <build_id>`", parse_mode="Markdown")
        return

    build = get_build(int(args[0]))
    if not build or build["user_id"] != update.effective_user.id:
        await update.message.reply_text("❌ Build nahi mila!")
        return

    await update.message.reply_text(format_build_status(build), parse_mode="Markdown")

async def my_builds(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    builds = get_user_builds(user.id)

    if not builds:
        q = update.callback_query
        if q: await q.answer()
        msg = update.message or q.message
        await msg.reply_text("📭 Abhi tak koi build nahi.", reply_markup=back_to_main())
        return

    text = "📦 *Your Recent Builds:*\n\n"
    for b in builds[:5]:
        text += format_build_status(b) + "\n\n"

    q = update.callback_query
    if q: await q.answer()
    msg = update.message or q.message
    await msg.reply_text(text, parse_mode="Markdown", reply_markup=back_to_main())

def _feature_kb(features):
    def btn(cb, label, key):
        icon = "✅" if features.get(key) else "☑️"
        return InlineKeyboardButton(f"{icon} {label}", callback_data=cb)

    return InlineKeyboardMarkup([
        [btn("feat_shizuku","Shizuku","shizuku"),    btn("feat_filemanager","File Manager","file_manager")],
        [btn("feat_login","Login Screen","login_screen"), btn("feat_darktheme","Dark Theme","dark_theme")],
        [btn("feat_ads","Ads","ads"),                btn("feat_keysystem","Key System","key_system")],
        [InlineKeyboardButton("🔨 Confirm & Build", callback_data="confirm_build")],
        [InlineKeyboardButton("🔙 Back", callback_data="main_menu")],
    ])
