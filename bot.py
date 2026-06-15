import logging
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    MessageHandler, ConversationHandler, filters
)
from config import BOT_TOKEN
from database.db import init_db

from handlers.start  import start, help_cmd, cancel
from handlers.apk    import (build_start, got_app_name, got_pkg_name, got_app_url,
                              toggle_feature, do_build, build_status, my_builds,
                              APP_NAME, PKG_NAME, APP_URL, FEATURES, CONFIRM)
from handlers.keys   import activate_key
from handlers.admin  import (admin_cmd, admin_stats, admin_users_list,
                              admin_keys_panel, gen_key_cmd, list_keys_cmd,
                              revoke_key_cmd, ban_user_cmd, unban_user_cmd,
                              broadcast_cmd, toggle_maintenance)
from handlers.user   import profile

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def main():
    init_db()
    logger.info("Database initialized")

    app = Application.builder().token(BOT_TOKEN).build()

    # ── Build Conversation ─────────────────────────────────
    build_conv = ConversationHandler(
        entry_points=[
            CommandHandler("build", build_start),
            CallbackQueryHandler(build_start, pattern="^build_apk$"),
        ],
        states={
            APP_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_app_name)],
            PKG_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_pkg_name)],
            APP_URL:  [MessageHandler(filters.TEXT, got_app_url)],
            FEATURES: [CallbackQueryHandler(toggle_feature)],
            CONFIRM:  [CallbackQueryHandler(do_build, pattern="^do_build$"),
                       CallbackQueryHandler(cancel,   pattern="^cancel_build$")],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True
    )

    # ── Register Handlers ──────────────────────────────────
    app.add_handler(CommandHandler("start",    start))
    app.add_handler(CommandHandler("help",     help_cmd))
    app.add_handler(CommandHandler("cancel",   cancel))
    app.add_handler(CommandHandler("key",      activate_key))
    app.add_handler(CommandHandler("status",   build_status))
    app.add_handler(CommandHandler("mybuilds", my_builds))
    app.add_handler(CommandHandler("profile",  profile))

    # Admin commands
    app.add_handler(CommandHandler("admin",      admin_cmd))
    app.add_handler(CommandHandler("genkey",     gen_key_cmd))
    app.add_handler(CommandHandler("listkeys",   list_keys_cmd))
    app.add_handler(CommandHandler("revokekey",  revoke_key_cmd))
    app.add_handler(CommandHandler("ban",        ban_user_cmd))
    app.add_handler(CommandHandler("unban",      unban_user_cmd))
    app.add_handler(CommandHandler("broadcast",  broadcast_cmd))
    app.add_handler(CommandHandler("stats",      admin_stats))

    app.add_handler(build_conv)

    # Callback handlers
    app.add_handler(CallbackQueryHandler(start,              pattern="^main_menu$"))
    app.add_handler(CallbackQueryHandler(admin_cmd,          pattern="^admin_panel$"))
    app.add_handler(CallbackQueryHandler(admin_stats,        pattern="^admin_stats$"))
    app.add_handler(CallbackQueryHandler(admin_users_list,   pattern="^admin_users$"))
    app.add_handler(CallbackQueryHandler(admin_keys_panel,   pattern="^admin_keys$"))
    app.add_handler(CallbackQueryHandler(toggle_maintenance, pattern="^toggle_maintenance$"))
    app.add_handler(CallbackQueryHandler(my_builds,          pattern="^my_builds$"))
    app.add_handler(CallbackQueryHandler(activate_key,       pattern="^activate_key$"))
    app.add_handler(CallbackQueryHandler(profile,            pattern="^my_profile$"))

    logger.info("Bot started!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
