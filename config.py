from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv

# Loyihaning asosiy papkasi
BASE_DIR = Path(__file__).resolve().parent

# .env faylini yuklash
load_dotenv(BASE_DIR / ".env")

# Telegram Bot Token
TELEGRAM_TOKEN: str = os.getenv("TELEGRAM_TOKEN", "")
if not TELEGRAM_TOKEN:
    raise ValueError("❌ .env faylida TELEGRAM_TOKEN ko'rsatilmagan!")

# Bot asosiy adminlari (ID lar vergul bilan: 1234567,7654321)
_raw_admins = os.getenv("ADMIN_IDS", "")
ADMIN_IDS: list[int] = [
    int(x.strip()) for x in _raw_admins.split(",") if x.strip().isdigit()
]

# Ma'lumotlar bazasi
DATA_DIR: Path = BASE_DIR / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH: Path = DATA_DIR / "group_bot.db"

# Guruh sozlamalari (Standart)
MAX_WARNS: int = int(os.getenv("MAX_WARNS", "3"))
DEFAULT_MUTE_SECONDS: int = int(os.getenv("DEFAULT_MUTE_SECONDS", "3600"))  # 1 soat
AUTO_DELETE_NOTIFICATION_DELAY: int = 7  # Bildirishnomalarni 7 soniyada o'chirish

# Taqiqlangan spam so'zlar ro'yxati
SPAM_KEYWORDS: list[str] = [
    "investitsiya", "daromad", "kuniga pul ishlash", "kuniga 500$", "kuniga 100$",
    "kassa", "stavka", "1xbet", "linebet", "melbet", "mostbet", "parimatch",
    "vazifa bajarib pul", "kriptovalyuta", "kripto", "sarmoyasiz daromad",
    "kartaga pul tashlab", "payme orqali pul", "click orqali pul",
    "intim", "sevishganlar", "porn", "xxx", "prostitutka", "seks", "jinsiy",
    "oyiga million", "oson pul", "referal", "bonus oling"
]

# Ruxsat etilgan havolalar (agar bo'lsa, bloklanmaydi)
WHITELISTED_LINKS: list[str] = [
    # masalan: "t.me/sizning_kanalingiz"
]
