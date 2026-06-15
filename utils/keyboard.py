from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def main_menu(is_admin=False):
    buttons = [
        [InlineKeyboardButton("📦 Build APK", callback_data="build_apk"),
         InlineKeyboardButton("📋 My Builds", callback_data="my_builds")],
        [InlineKeyboardButton("🔑 Activate Key", callback_data="activate_key"),
         InlineKeyboardButton("👤 My Profile", callback_data="my_profile")],
        [InlineKeyboardButton("❓ Help", callback_data="help")],
    ]
    if is_admin:
        buttons.append([InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin_panel")])
    return InlineKeyboardMarkup(buttons)

def admin_panel():
    buttons = [
        [InlineKeyboardButton("📊 Stats", callback_data="admin_stats"),
         InlineKeyboardButton("👥 Users", callback_data="admin_users")],
        [InlineKeyboardButton("🔑 Keys", callback_data="admin_keys"),
         InlineKeyboardButton("📦 All Builds", callback_data="admin_builds")],
        [InlineKeyboardButton("🔧 Settings", callback_data="admin_settings"),
         InlineKeyboardButton("📢 Broadcast", callback_data="admin_broadcast")],
        [InlineKeyboardButton("🔙 Back", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(buttons)

def key_management():
    buttons = [
        [InlineKeyboardButton("➕ Generate Key", callback_data="gen_key"),
         InlineKeyboardButton("📋 List Keys", callback_data="list_keys")],
        [InlineKeyboardButton("❌ Revoke Key", callback_data="revoke_key")],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_panel")],
    ]
    return InlineKeyboardMarkup(buttons)

def build_apk_menu():
    buttons = [
        [InlineKeyboardButton("🌐 WebView APK", callback_data="build_webview"),
         InlineKeyboardButton("⚡ Full APK", callback_data="build_full")],
        [InlineKeyboardButton("📁 Custom Template", callback_data="build_custom")],
        [InlineKeyboardButton("🔙 Back", callback_data="main_menu")],
    ]
    return InlineKeyboardMarkup(buttons)

def build_features():
    buttons = [
        [InlineKeyboardButton("✅ Shizuku Support", callback_data="feat_shizuku"),
         InlineKeyboardButton("✅ File Manager", callback_data="feat_filemanager")],
        [InlineKeyboardButton("✅ Login Screen", callback_data="feat_login"),
         InlineKeyboardButton("✅ Dark Theme", callback_data="feat_darktheme")],
        [InlineKeyboardButton("✅ Ads Enabled", callback_data="feat_ads"),
         InlineKeyboardButton("✅ Key System", callback_data="feat_keysystem")],
        [InlineKeyboardButton("🔨 Start Build", callback_data="confirm_build")],
        [InlineKeyboardButton("🔙 Back", callback_data="build_apk")],
    ]
    return InlineKeyboardMarkup(buttons)

def back_to_main():
    return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]])

def confirm_action(yes_cb, no_cb="main_menu"):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ Yes", callback_data=yes_cb),
         InlineKeyboardButton("❌ No", callback_data=no_cb)]
    ])
