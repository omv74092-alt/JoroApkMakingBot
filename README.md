# 🤖 APK Builder Bot

Telegram bot jo custom APK build karke directly bhejta hai — GitHub Actions ke through.

## 🚀 Features
- 📦 Custom APK builder (WebView + Full)
- 🔑 Key activation system
- 👤 User panel + profile
- ⚙️ Admin panel (stats, users, keys, broadcast)
- 🛡️ Shizuku support toggle
- 📁 File Manager toggle
- 🌐 Login screen toggle
- 🔧 Maintenance mode

## 📁 Project Structure
```
apk-bot/
├── bot.py              # Main entry point
├── config.py           # All settings from env vars
├── requirements.txt
├── Procfile            # Railway worker
├── runtime.txt
├── database/
│   └── db.py           # SQLite DB functions
├── handlers/
│   ├── start.py        # /start, /help, /cancel
│   ├── apk.py          # Build conversation flow
│   ├── keys.py         # Key activation
│   ├── admin.py        # Admin commands
│   └── user.py         # Profile
└── utils/
    ├── keyboard.py     # All inline keyboards
    ├── apk_builder.py  # GitHub Actions API
    └── helpers.py      # Key gen, validators
```

## ⚙️ Railway Setup

### Environment Variables (Railway Dashboard → Variables):
| Variable | Value |
|---|---|
| `BOT_TOKEN` | BotFather se mila token |
| `ADMIN_IDS` | `123456789` (comma separated for multiple) |
| `GITHUB_TOKEN` | GitHub → Settings → Developer → Personal Access Token (repo + workflow scope) |
| `GITHUB_REPO` | `yourusername/apk-builder-repo` |
| `DATABASE_URL` | `bot_data.db` |
| `APK_BUILD_TIMEOUT` | `1800` |

### Deploy Steps:
1. GitHub pe ye folder push karo
2. Railway.app → New Project → Deploy from GitHub
3. Variables set karo (upar wali table)
4. Service type: **Worker** (not Web)
5. Deploy!

## 🔑 Key System
```
Admin:  /genkey 5 10     → 5 keys, max 10 builds each
User:   /key APK-XXXX-XXXX-XXXX
```

## 📦 APK Build Flow
1. User `/build` karta hai
2. App naam → Package name → URL → Features select
3. Bot GitHub Actions workflow trigger karta hai
4. 15-20 min mein APK ready → bot bhej deta hai

## 👑 Admin Commands
| Command | Use |
|---|---|
| `/admin` | Admin panel |
| `/genkey [count] [max_builds]` | Keys generate |
| `/listkeys` | Sab keys dekho |
| `/revokekey KEY` | Key revoke |
| `/ban user_id` | User ban |
| `/unban user_id` | User unban |
| `/broadcast message` | Sab ko message |
| `/stats` | Statistics |
