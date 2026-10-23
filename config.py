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
_env_db_path = os.getenv("DB_PATH", "").strip()
if _env_db_path:
    DB_PATH: Path = BASE_DIR / _env_db_path if not os.path.isabs(_env_db_path) else Path(_env_db_path)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
else:
    DB_PATH: Path = DATA_DIR / "group_bot.db"

# Guruh sozlamalari (Standart)
MAX_WARNS: int = int(os.getenv("MAX_WARNS", "3"))
DEFAULT_MUTE_SECONDS: int = int(os.getenv("DEFAULT_MUTE_SECONDS", "3600"))  # 1 soat
AUTO_DELETE_NOTIFICATION_DELAY: int = 15  # Bot xabarlari 15 soniyada avtomatik o'chiriladi
WELCOME_NOTIFICATION_DELAY: int = 25  # Xush kelibsiz xabari 25 soniyada tozalanadi
APK_WARNING_NOTIFICATION_DELAY: int = 30  # APK virus ogohlantirishi 30 soniyada tozalanadi

# Taqiqlangan spam so'zlar ro'yxati
SPAM_KEYWORDS: list[str] = [
    "investitsiya", "daromad", "kuniga pul ishlash", "kuniga 500$", "kuniga 100$",
    "kassa", "stavka", "1xbet", "linebet", "melbet", "mostbet", "parimatch",
    "vazifa bajarib pul", "kriptovalyuta", "kripto", "sarmoyasiz daromad",
    "kartaga pul tashlab", "payme orqali pul", "click orqali pul",
    "intim", "sevishganlar", "porn", "xxx", "prostitutka", "seks", "jinsiy",
    "oyiga million", "oson pul", "referal", "bonus oling"
]

# Taqiqlangan so'kinish va haqorat so'zlari ro'yxati
PROFANITY_KEYWORDS: list[str] = [
    "jalap", "jallap", "zhalap", "dalbayob", "dalbayop", "dolbayob", "dolbaeb",
    "siktir", "sikaman", "sikay", "sikish", "sikey", "sikayotgan",
    "qotoq", "qo'toq", "qotoqmisan", "qotoqbosh",
    "gandon", "gondon", "pidar", "pidaraz", "pederast",
    "onangni sik", "onangdi sik", "onangni s", "onangni ami",
    "haromi", "itvachcha", "molcha", "chmo", "sukaa",
    "blyat", "blyad", "nahuy", "huy", "pizda", "yeblet", "mudak",
    "shlyuxa", "pozor", "geyporn"
]

# Ruxsat etilgan havolalar (agar bo'lsa, bloklanmaydi)
WHITELISTED_LINKS: list[str] = [
    # masalan: "t.me/sizning_kanalingiz"
]

