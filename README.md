# 🤖 Telegram Bot — Setup Guide (Hindi)

## 📋 Features

- 🔐 Login / Session System (24 ghante expiry)
- 🛡️ Admin Panel (ban, unban, broadcast, logs, stats)
- 📁 Assets Folder Manager (.apk, .sh, .zip, .py, .json, .bin, .dex, .txt)
- 📱 Shizuku / ADB Integration (root-less privileged commands)
- 📂 User Path Manager (push/pull/exec)
- ⚡ Rate Limiting & Cooldown System
- 📊 SQLite Database

---

## ⚙️ Requirements

| Cheez | Version |
|-------|---------|
| Python | 3.10+ |
| pyTelegramBotAPI | 4.20.0 |
| ADB (optional) | Latest |

---

## 🚀 Setup Steps

### 1️⃣ Repository Clone / Files Copy Karo

```bash
mkdir telegram_bot && cd telegram_bot
# Saari files yahan daal do (config.py, database.py, shizuku_api.py, bot.py)
```

### 2️⃣ Virtual Environment Banao (Recommended)

```bash
python3 -m venv venv
source venv/bin/activate        # Linux/Mac
# ya
venv\Scripts\activate           # Windows
```

### 3️⃣ Dependencies Install Karo

```bash
pip install -r requirements.txt
```

### 4️⃣ Bot Token Set Karo

**Option A — config.py edit karo:**
```python
BOT_TOKEN = "1234567890:ABCdefGHIjklMNOpqrSTUvwxyz"
ADMIN_IDS = [123456789]   # Apna Telegram ID daal do
```

**Option B — Environment Variables (recommended for production):**
```bash
export BOT_TOKEN="1234567890:ABCdefGHIjklMNOpqrSTUvwxyz"
export ADMIN_IDS="123456789"
export ASSETS_PATH="assets"
```

### 5️⃣ Assets Folders Banao

```bash
mkdir -p assets/scripts assets/apks assets/modules assets/configs assets/tools
```

### 6️⃣ ADB Setup (Shizuku ke liye)

```bash
# ADB install karo
sudo apt install adb          # Linux (Debian/Ubuntu)
brew install android-platform-tools  # Mac

# Device connect karo (USB ya wireless)
adb devices

# Shizuku start karo (Android device par)
# Shizuku app install karo Play Store se
# Phir "Start via ADB" button dabao
adb shell sh /sdcard/Android/data/moe.shizuku.privileged.api/start.sh
```

### 7️⃣ Bot Chalao

```bash
python bot.py
```

---

## 📁 Folder Structure

```
telegram_bot/
├── bot.py              # Main bot file
├── config.py           # Configuration
├── database.py         # SQLite handler
├── shizuku_api.py      # Shizuku/ADB wrapper
├── requirements.txt    # Python dependencies
├── README.md           # Ye file
├── bot.log             # Auto-generated log file
├── bot_database.db     # Auto-generated SQLite DB
└── assets/
    ├── apks/           # APK files yahan rakhna
    ├── scripts/        # .sh scripts yahan rakhna
    ├── modules/        # Python modules
    ├── configs/        # JSON configs
    └── tools/          # Binary tools
```

---

## 📱 Bot Commands

### 🔐 Auth Commands
| Command | Kaam |
|---------|------|
| `/start` | Bot start karo, register ho jao |
| `/login` | Login karo (session banao) |
| `/logout` | Logout karo |
| `/menu` | Main menu kholo |
| `/profile` | Apna profile dekho |
| `/help` | Saari commands dekho |

### 📁 File Commands
| Command | Kaam |
|---------|------|
| `/listfiles [page]` | Assets files list karo |
| `/getfile <name>` | File download karo |
| `/uploadfile` | File upload karo (reply as document) — Admin only |
| `/deletefile <name>` | File delete karo — Admin only |

### 📱 Shizuku/ADB Commands
| Command | Kaam |
|---------|------|
| `/shizuku_status` | Shizuku check karo |
| `/runcmd <cmd>` | Shell command chalao |
| `/deviceinfo` | Device ki puri info lo |
| `/screenshot` | Screenshot lo |
| `/packages` | Installed apps list |
| `/install_apk <file>` | APK silently install karo |
| `/uninstall <pkg>` | App uninstall karo |
| `/kill <pkg>` | App force stop karo |
| `/cleardata <pkg>` | App data clear karo |
| `/grant <pkg> <perm>` | Permission grant karo |
| `/runscript <name>` | assets/scripts se script chalao |

### 📂 Path Manager
| Command | Kaam |
|---------|------|
| `/setpath <path>` | Working path set karo |
| `/listpath` | Path ki files list karo |
| `/push <file>` | Asset se device par push karo |
| `/pull <file>` | Device se file pull karo |
| `/exec <cmd>` | Path par command chalao |
| `/deletepath <file>` | Path par file delete karo |

### 🛡️ Admin Commands
| Command | Kaam |
|---------|------|
| `/admin` | Admin panel kholo |
| `/users [page]` | Saare users dekho |
| `/ban <id>` | User ban karo |
| `/unban <id>` | User unban karo |
| `/makeadmin <id>` | User ko admin banao |
| `/broadcast <msg>` | Saare users ko message bhejo |
| `/stats` | Bot statistics dekho |
| `/logs [page]` | Admin logs dekho |

---

## 🔒 Security Notes

- **BOT_TOKEN** kabhi bhi public mat karo (GitHub, etc.)
- **ADMIN_IDS** mein sirf apna Telegram ID dalo
- ADB USB Debugging sirf trusted devices par enable karo
- Rate limit: 5 commands per second per user
- Command cooldown: 2 seconds

---

## ❗ Troubleshooting

**Bot reply nahi kar raha?**
```bash
# Token check karo
python -c "import config; print(config.BOT_TOKEN[:10])"
# Bot.log dekho
tail -f bot.log
```

**ADB nahi chal raha?**
```bash
adb kill-server
adb start-server
adb devices
```

**Shizuku not found?**
```bash
# Shizuku app open karo aur "Start" button dabao
adb shell sh /sdcard/Android/data/moe.shizuku.privileged.api/start.sh
```

**Database reset karna ho?**
```bash
rm bot_database.db
python bot.py   # Auto re-create hoga
```

---

## 📞 Support

Koi problem ho to:
1. `bot.log` file check karo
2. `/stats` command se bot status dekho
3. `/shizuku_status` se ADB/Shizuku check karo
