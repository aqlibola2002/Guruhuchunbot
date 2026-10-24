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
AUTO_DELETE_NOTIFICATION_DELAY: int = 60  # Bot xabarlari 60 soniyada (1 daqiqa) avtomatik o'chiriladi
WELCOME_NOTIFICATION_DELAY: int = 60  # Xush kelibsiz xabari 60 soniyada (1 daqiqa) tozalanadi
APK_WARNING_NOTIFICATION_DELAY: int = 60  # APK virus ogohlantirishi 60 soniyada (1 daqiqa) tozalanadi

# Taqiqlangan spam so'zlar ro'yxati
SPAM_KEYWORDS: list[str] = [
    "investitsiya", "daromad", "kuniga pul ishlash", "kuniga 500$", "kuniga 100$",
    "kassa", "stavka", "1xbet", "linebet", "melbet", "mostbet", "parimatch",
    "vazifa bajarib pul", "kriptovalyuta", "kripto", "sarmoyasiz daromad",
    "kartaga pul tashlab", "payme orqali pul", "click orqali pul",
    "intim", "sevishganlar", "porn", "xxx", "prostitutka", "seks", "jinsiy",
    "oyiga million", "oson pul", "referal", "bonus oling"
]

# Taqiqlangan so'kinish va haqorat so'zlari ro'yxati (O'zbekcha va Ruscha haqoratlar)
PROFANITY_KEYWORDS: list[str] = [
    # O'zbekcha haqorat va so'kinishlar
    "jalap", "jallap", "jalab", "jaloq", "zhalap", "zhallap", "jalabmisan", "jalapsan",
    "dalbayob", "dalbayop", "dalbaeb", "dolbayob", "dolbayop", "dolbaeb", "dalboyob", "dolboyob",
    "siktir", "siktirish", "sikey", "sikay", "sikaman", "sikayotgan", "sikish", "sikiw",
    "siqay", "siqaman", "siqish", "skaman", "skay", "sktir", "siqtr", "siqqan", "sike",
    "qotoq", "qo'toq", "qotoqmisan", "qotoqbosh", "qotoqvoy", "qotaq", "qo'taq", "qotoqqa", "qotog'im",
    "amcha", "amvachcha", "amiga", "aminga", "ominga", "omcha", "aming", "oming",
    "onangni sik", "onangdi sik", "onangni s", "onangni ami", "onangni amiga", "onangning ami",
    "oneni sik", "enengni sik", "enasini sik", "onangizni sik", "onangni sikey",
    "gandon", "gondon", "gandonsan", "gandonmisan",
    "pidar", "pidaraz", "pidaras", "pederast", "pidarsan",
    "haromi", "haromzoda", "itvachcha", "it emgan", "itdan tarqagan",
    "ko't", "kot", "kotvachcha", "ko'tvachcha", "kotqoqi", "kotmisan", "kotsan", "ko'tsan",
    "chmo", "chmoshnik", "manqurt", "padla",

    # Ruscha haqorat va so'kinishlar (Markaziy Osiyo guruhlarida keng tarqalgan)
    "blyat", "blya", "blyad", "bliad", "blet",
    "nahuy", "nahui", "naxuy", "naxui", "poxuy", "poxui", "haxuy",
    "xuy", "huy", "xui", "hui", "huylo", "xuylo", "xuyna", "huyna",
    "axuel", "oxuel", "axuet", "oxuet", "oxuenniy",
    "pizda", "pizdets", "pizdecs", "pizdec", "pizdato", "pizdish", "pizdyuk", "pizdet",
    "ebat", "ebal", "ebik", "eban", "ebanat", "ebaniy", "ebanoe", "ebanniy",
    "zaebal", "zaebis", "doebalsya", "proebal", "uebishe", "uebok", "yobaniy", "yobnutiy",
    "suka", "cyka", "suki", "suchka", "sukaa", "sukin",
    "mudak", "mudo", "mudila",
    "shlyuxa", "shlyuha", "shluxa", "zalupa", "zalupka", "geyporn",

    # Kirillcha so'kinish va haqoratlar (O'zbek va Rus tillarida)
    "жалаб", "жалап", "жалоқ", "далбаёб", "далбаеб", "долбаёб", "долбаеб",
    "сиктир", "сикаман", "сикай", "сикиш", "сиквор", "сикивор", "сике",
    "қотоқ", "коток", "қотоғим", "қотоқбош", "қотоқвой",
    "амча", "амвачча", "аминг", "амига", "амингга", "амхўр",
    "онангни сикай", "онангни сикаман", "онангди сикай", "энангни сикай", "онангни ами",
    "гондон", "гандон", "пидараз", "пидорас", "пидар", "пидор",
    "ҳароми", "ҳаромзода", "итвачча", "ит эмган",
    "кўт", "кот", "кўтинг", "кўтингга", "кўтсан", "кўтвачча",
    "блять", "блядь", "бля", "блет", "блядина",
    "нахуй", "нахуя", "похуй", "похую", "дохуя", "нихуя",
    "хуй", "хуя", "хуем", "хуесос", "хуила", "хуйня", "хуёвый",
    "ахуел", "охуел", "ахуеть", "охуеть",
    "пизда", "пиздец", "пиздато", "пиздеть", "пиздишь", "пиздюк",
    "ебать", "ебал", "ебанутый", "ебанат", "ебаный", "ебаное",
    "заебал", "заебись", "доебался", "проебал", "уёбок", "уебище",
    "сука", "сучки", "сучка", "сучара",
    "мудак", "мудила", "шлюха", "залупа", "чмо", "чмошник", "падла"
]

# Ruxsat etilgan havolalar (agar bo'lsa, bloklanmaydi)
WHITELISTED_LINKS: list[str] = [
    # masalan: "t.me/sizning_kanalingiz"
]

