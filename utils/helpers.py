import random
import string
from datetime import datetime

def generate_key(length=16, prefix="APK"):
    chars = string.ascii_uppercase + string.digits
    rand  = ''.join(random.choices(chars, k=length))
    return f"{prefix}-{rand[:4]}-{rand[4:8]}-{rand[8:12]}"

def format_build_status(build):
    status_emoji = {
        "pending":  "⏳",
        "running":  "🔄",
        "success":  "✅",
        "failed":   "❌",
        "cancelled":"🚫"
    }
    emoji = status_emoji.get(build["status"], "❓")
    text = (
        f"{emoji} *Build #{build['id']}*\n"
        f"📦 App: `{build['app_name']}`\n"
        f"📌 Package: `{build['package']}`\n"
        f"📊 Status: *{build['status'].upper()}*\n"
        f"🕐 Started: {build['created_at'][:16]}"
    )
    if build.get("finished_at"):
        text += f"\n✅ Done: {build['finished_at'][:16]}"
    return text

def validate_package(package):
    parts = package.split(".")
    if len(parts) < 2:
        return False
    for p in parts:
        if not p or not p[0].isalpha():
            return False
        if not all(c.isalnum() or c == '_' for c in p):
            return False
    return True

def escape_md(text):
    chars = r'_*[]()~`>#+-=|{}.!'
    return ''.join(f'\\{c}' if c in chars else c for c in str(text))
