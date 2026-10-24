from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timedelta, timezone

from aiogram import Router, Bot, F
from aiogram.types import (
    Message,
    ChatPermissions,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)

from config import (
    SPAM_KEYWORDS,
    PROFANITY_KEYWORDS,
    WHITELISTED_LINKS,
    AUTO_DELETE_NOTIFICATION_DELAY,
    APK_WARNING_NOTIFICATION_DELAY,
    MAX_WARNS,
)
from database.db import db
from filters.admin_filter import is_admin, can_bot_delete
from services.ui_utils import make_progress_bar, set_user_invite_warn_msg, pop_user_invite_warn_msgs

router = Router(name="moderation")
logger = logging.getLogger(__name__)

# Taklif ogohlantirishlari kesh: {(chat_id, user_id): timestamp}
INVITE_WARN_CACHE: dict[tuple[int, int], float] = {}

# Linklarni aniqlash regexi (har qanday domen, vebsayt, Telegram havolasi va @username)
LINK_PATTERN = re.compile(
    r"(https?://\S+|www\.\S+|t\.me/\S+|telegram\.me/\S+|telegram\.dog/\S+|@[a-zA-Z0-9_]{4,}|\b[a-zA-Z0-9.-]+\.(?:com|uz|ru|net|org|io|me|info|biz|xyz|app|site|online|top|club|vip|live|pro|dev|store|shop|link|edu|gov)\b\S*)",
    re.IGNORECASE,
)

# Arab, Xitoy, Yapon, Kores va boshqa chet el spambot yozuvlarini 100% aniqlash regexi
ORIENTAL_FOREIGN_PATTERN = re.compile(
    r"["
    r"\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF"  # Arabcha, Forscha, Pushtu, Urdu
    r"\u4E00-\u9FFF\u3400-\u4DBF\uF900-\uFAFF"                            # Xitoycha (Hanzi / Kanji)
    r"\u3040-\u309F\u30A0-\u30FF\u31F0-\u31FF\u3000-\u303F"              # Yaponcha (Hiragana, Katakana, Yapon belgilari)
    r"\uAC00-\uD7AF\u1100-\u11FF\u3130-\u318F"                            # Korescha (Hangul bo'g'inlari va jamo)
    r"\u0900-\u097F\u0980-\u09FF\u0B80-\u0BFF\u0C00-\u0C7F"              # Hindcha (Devanagari, Bengali, Tamil, Telugu)
    r"\u0E00-\u0E7F"                                                      # Taycha (Thai)
    r"\u0590-\u05FF"                                                      # Yahudiycha (Hebrew)
    r"]"
)
ARABIC_ORIENTAL_PATTERN = ORIENTAL_FOREIGN_PATTERN


# Flood nazorati uchun kesh: {(chat_id, user_id): [timestamps]}
FLOOD_CACHE: dict[tuple[int, int], list[float]] = {}
FLOOD_THRESHOLD_COUNT = 5
FLOOD_THRESHOLD_SECONDS = 4.0

# Bir xil xabarni qayta-qayta yuboruvchi copy-paste spamerlar keshi: {(chat_id, user_id): (clean_text, timestamp, count)}
DUPLICATE_CACHE: dict[tuple[int, int], tuple[str, float, int]] = {}
DUPLICATE_WINDOW_SECONDS = 60.0


def is_flooding(chat_id: int, user_id: int) -> bool:
    """Foydalanuvchi qisqa vaqtda ketma-ket haddan tashqari ko'p xabar yuborayotganini aniqlaydi."""
    try:
        now = asyncio.get_event_loop().time()
    except Exception:
        import time
        now = time.time()
    key = (chat_id, user_id)
    timestamps = FLOOD_CACHE.setdefault(key, [])
    timestamps = [t for t in timestamps if now - t <= FLOOD_THRESHOLD_SECONDS]
    timestamps.append(now)
    FLOOD_CACHE[key] = timestamps
    return len(timestamps) >= FLOOD_THRESHOLD_COUNT


def is_duplicate_message(chat_id: int, user_id: int, raw_text: str) -> tuple[bool, int]:
    """Foydalanuvchi bir xil xabarni 60 soniya ichida qayta-qayta yuborayotganini aniqlash."""
    if not raw_text or len(raw_text.strip()) < 4:
        return False, 1

    clean_t = re.sub(r"\s+", " ", raw_text.strip().lower())
    try:
        now = asyncio.get_event_loop().time()
    except Exception:
        import time
        now = time.time()

    key = (chat_id, user_id)
    prev = DUPLICATE_CACHE.get(key)

    if prev:
        prev_text, prev_time, count = prev
        if prev_text == clean_t and (now - prev_time <= DUPLICATE_WINDOW_SECONDS):
            new_count = count + 1
            DUPLICATE_CACHE[key] = (clean_t, now, new_count)
            return True, new_count

    DUPLICATE_CACHE[key] = (clean_t, now, 1)
    return False, 1


async def send_audit_log(
    bot: Bot,
    chat_id: int,
    chat_title: str,
    event_title: str,
    user_name: str,
    user_id: int | None,
    reason: str,
    snippet: str = "",
) -> None:
    """Guruh xavfsizlik audit log kanaliga hodisani yetkazish."""
    try:
        log_channel = await db.get_group_log_channel(chat_id)
        if not log_channel:
            return

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        mention = safe_mention(user_name, user_id)
        u_info = f"{mention} (`{user_id}`)" if user_id else f"{mention}"

        snip_text = ""
        if snippet:
            clean_snip = snippet.replace("`", "'").replace("*", "")[:200]
            snip_text = f"\n📄 **Xabar:** `{clean_snip}`"

        card = (
            f"🛡 **GURUH XAVFSIZLIK AUDITI** 🛡\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🏛 **Guruh:** {chat_title}\n"
            f"⚡️ **Hodisa:** {event_title}\n"
            f"👤 **Qoidabuzar:** {u_info}\n"
            f"📝 **Sabab:** {reason}{snip_text}\n"
            f"⏰ **Vaqt:** `{now_str}`"
        )
        await bot.send_message(chat_id=log_channel, text=card, parse_mode="Markdown")
    except Exception as e:
        logger.debug(f"Audit log yuborishda: {e}")


def contains_arabic_or_oriental(text: str) -> bool:
    """Matnda arab, xitoy, yapon, kores yoki boshqa chet el spambot belgilari borligini aniqlash."""
    if not text:
        return False
    return bool(ORIENTAL_FOREIGN_PATTERN.search(text))


contains_foreign_oriental_script = contains_arabic_or_oriental


def safe_mention(full_name: str | None, user_id: int | None) -> str:
    """Foydalanuvchi ismidagi qavslar va maxsus belgilarni tozalab xavfsiz Telegram Markdown linkini qaytaradi."""
    name = (
        (full_name or "Foydalanuvchi")
        .replace("[", "(")
        .replace("]", ")")
        .replace("*", "")
        .replace("_", " ")
        .replace("`", "'")
    )
    if user_id:
        return f"[{name}](tg://user?id={user_id})"
    return name


DANGEROUS_EXTENSIONS = (
    ".apk", ".xapk", ".apks", ".ipa", ".bin",
    ".exe", ".bat", ".cmd", ".msi", ".scr", ".vbs", ".jar", ".pif",
    ".apk.1", ".apk.zip", ".apk.bin"
)

DANGEROUS_MIMES = (
    "application/vnd.android.package-archive",
    "application/x-android-package-archive",
    "application/x-apk",
    "application/apk",
    "application/vnd.android",
    "application/x-msdownload",
    "application/x-executable",
    "application/x-msdos-program",
)


def check_dangerous_file(message: Message) -> tuple[bool, str]:
    """
    Xabarda zararli .apk yoki virusli fayllar borligini 100% aniqlaydi.
    Qaytaradi: (is_dangerous, file_name)
    """
    # 1. Document
    if message.document:
        doc_name = (message.document.file_name or "").lower().strip()
        doc_mime = (message.document.mime_type or "").lower().strip()

        # Fayl kengaytmasi bo'yicha
        if any(doc_name.endswith(ext) for ext in DANGEROUS_EXTENSIONS) or ".apk" in doc_name:
            return True, message.document.file_name or "APK dastur"

        # Regex bo'yicha: nom ichida .apk yoki virus kengaytmasi bo'lsa
        if re.search(r"\.(?:apk|xapk|apks|ipa|bin|exe|bat|cmd|msi|vbs|jar)(?:\.|\b|$)", doc_name, re.IGNORECASE):
            return True, message.document.file_name or "APK dastur"

        # MIME type bo'yicha
        if any(mime in doc_mime for mime in DANGEROUS_MIMES) or ("android" in doc_mime and "package" in doc_mime):
            return True, message.document.file_name or "Android APK dasturi"

        if "application/octet-stream" in doc_mime and (".apk" in doc_name or not doc_name):
            return True, message.document.file_name or "Noma'lum fayl (.apk)"

    # 2. Audio va Video fayllar (niqoblangan APK lar)
    if message.audio:
        aud_name = (message.audio.file_name or "").lower().strip()
        if any(aud_name.endswith(ext) for ext in DANGEROUS_EXTENSIONS) or ".apk" in aud_name:
            return True, message.audio.file_name or "APK fayl (audio niqobi ostida)"

    if message.video:
        vid_name = (message.video.file_name or "").lower().strip()
        if any(vid_name.endswith(ext) for ext in DANGEROUS_EXTENSIONS) or ".apk" in vid_name:
            return True, message.video.file_name or "APK fayl (video niqobi ostida)"

    # 3. Matn yoki rasm tavsifi (caption) da to'g'ridan-to'g'ri .apk yuklash havolasi
    text_content = (message.text or message.caption or "").lower()
    if text_content and re.search(r"https?://\S+/[^\s]+\.apk\b", text_content, re.IGNORECASE):
        return True, "APK virus havolasi"

    return False, ""


async def auto_delete_notification(msg: Message, delay: int = AUTO_DELETE_NOTIFICATION_DELAY) -> None:
    await asyncio.sleep(delay)
    try:
        await msg.delete()
    except Exception:
        pass


async def check_user_channel_subscription(
    bot: Bot,
    user_id: int,
    channel_id_raw: str | int,
) -> bool:
    """
    Foydalanuvchi kanalga a'zo bo'lganligini yoki ariza (zayavka) yuborganligini aniqlash.
    Maxfiy kanallar (Private) va Admin tasdiq (Join Request) kanallarni 100% ishonchli tekshiradi.
    """
    ch_str = str(channel_id_raw).strip()

    # 1. Admin tasdiq / Join request (Zayavka) tekshiruvi:
    if await db.has_join_request(user_id, ch_str):
        return True

    # 2. Telegram API get_chat_member orqali tekshirish:
    try:
        if ch_str.startswith("-100") or (ch_str.startswith("-") and ch_str[1:].isdigit()) or ch_str.isdigit():
            target_chat_id: int | str = int(ch_str)
        else:
            target_chat_id = ch_str if ch_str.startswith("@") else f"@{ch_str}"

        member = await bot.get_chat_member(target_chat_id, user_id)
        if member.status in ("member", "administrator", "creator", "restricted"):
            return True
        elif member.status in ("left", "kicked"):
            # A'zo bo'lmasa, qayta zayafkasini tekshirib ko'ramiz
            return await db.has_join_request(user_id, ch_str)
    except Exception as e:
        logger.debug(f"A'zolikni tekshirishda xatolik ({channel_id_raw}): {e}")
        # Agar bot bu kanalda a'zolikni ko'ra olmasa: ariza yuborganligini tekshiramiz
        if await db.has_join_request(user_id, ch_str):
            return True
        return False

    return False


CYRILLIC_TO_LATIN: dict[str, str] = {
    'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
    'ж': 'j', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
    'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
    'ф': 'f', 'х': 'x', 'ҳ': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sh',
    'ъ': '', 'ы': 'i', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya',
    'ў': 'o', 'ғ': 'g', 'қ': 'q',
    'ә': 'a', 'ө': 'o', 'ү': 'u', 'ұ': 'u', 'і': 'i',
}

LEET_MAP: dict[str, str] = {
    "@": "a", "4": "a", "0": "o", "1": "i", "!": "i", "|": "i",
    "3": "e", "$": "s", "5": "s", "7": "t",
}

# So'kinish asoslari (Root stems) - compact matnda uchrasa 100% so'kinish hisoblanadi
PROFANITY_COMPACT_STEMS: list[str] = [
    # O'zbekcha haqorat asoslari
    "jalap", "jalab", "jallap", "jaloq", "zhalap", "zhalab",
    "dalbay", "dalbae", "dolbay", "dolbae", "dalboy", "dolboy",
    "qotoq", "qotaq", "kotog", "kotoq", "qotog",
    "siktir", "sikish", "sikiw", "sikvott", "sikvor", "sikibd", "sikkan",
    "sikaman", "sikasan", "sikadi", "sikamiz", "sikasiz", "sikay", "sike",
    "gandon", "gondon",
    "pidar", "pidor", "pederas",
    "itvachcha", "haromzoda",
    "kotvachcha", "kotqoqi", "kotsan", "kotmisan", "koting", "kotini", "kotbaqa",
    # Ruscha haqorat asoslari
    "blyad", "blyat", "bliad", "blyadin", "blyadstv",
    "nahuy", "nahui", "naxuy", "naxui", "poxuy", "poxui", "xuylo", "huylo", "xuyna", "huyna",
    "xuesos", "huesos", "xuela", "huela", "xuyet", "huyet",
    "pizd",
    "zaeb", "doeb", "proeb", "ueb", "yoban", "yobnut", "eban", "ebat", "ebal", "ebli",
    "suchk", "suchar",
    "mudak", "mudil",
    "shlyux", "shlyuh", "shlux",
    "zalup",
]

# Qisqa so'kinish so'zlari (faqat mustaqil so'z sifatida tekshiriladi)
SHORT_PROFANITY_WORDS: set[str] = {
    # O'zbekcha
    "am", "amcha", "amvachcha", "aming", "amiga", "amingga", "amxor", "amim", "amni", "amdi",
    "om", "omcha", "oming", "omiga",
    "kot", "kotsan", "kotmisan", "koting", "kotingga", "kotini", "kotvachcha",
    "chmo", "chmoshnik", "padla", "haromi",
    # Ruscha
    "xuy", "huy", "xui", "hui",
    "blya", "blet",
    "suka", "suki",
    "mudo", "ebik",
    "xer", "xernya", "poxer",
}

# Qarindosh-urug' bilan haqorat qilish regexi
COMPOUND_PROFANITY_PATTERN = re.compile(
    r"\b(onan|onen|enen|enas|otan|opan|singlin|urugin|avlodin|naslin)\w{0,6}\s*(?:[^\w\s]{1,5}\s*)?(?:ni|di|ning|ga)?\s*\w{0,10}\s*(sik|am|kot|chmo|it|emgan)",
    re.IGNORECASE
)

# Sik / sk asosi tekshiruvi (faqat 'sikl' va 'siqil' kabi odatiy so'zlardan tashqari)
SIK_PATTERN = re.compile(
    r"\b(sik\w*|sk\w+|siq(?:ay|aman|asan|adi|amiz|asiz|ish|tir\w*|vorg\w*))\b",
    re.IGNORECASE
)

SAFE_WORDS: set[str] = {
    "sikl", "siklik", "siqilma", "siqilish", "siqilmay", "siqilmang", "siqilyapman", "siqilmaslik"
}


def normalize_text_for_profanity(text: str) -> tuple[str, set[str], str, str, str]:
    """
    Matnni har qanday so'kinish, leet-kod va niqoblangan belgilardan tozalash.
    Qaytaradi: (t_lat, words_set, compact, compact_reduced, compact_single)
    """
    if not text:
        return "", set(), "", "", ""
    t = text.lower()

    # 0. Tutuq belgilari va apostroflarni tozalash (ko't -> kot, qotog'im -> qotogim, kõtsan -> kotsan)
    t = t.replace("õ", "o").replace("ō", "o").replace("ğ", "g")
    t = re.sub(r"['`ʻʼ’‘´\"]", "", t)

    # 1. Kirill harflarini to'liq lotinga o'girish
    t_lat = "".join(CYRILLIC_TO_LATIN.get(c, c) for c in t)

    # 2. Leetspeak raqam va maxsus belgilarni harfga aylantirish
    for char, rep in LEET_MAP.items():
        t_lat = t_lat.replace(char, rep)

    # 3. Yopishgan tinish belgilarini olib tashlash (s.u.k.a -> suka, s.i.k.a.y -> sikay)
    t_no_punct = re.sub(r"[\._\*\-\+~]", "", t_lat)

    # 4. Yagona harflar oralig'idagi bo'shliqlarni birlashtirish ('s u k a' -> 'suka', 'b l e t' -> 'blet')
    t_despaced = re.sub(r"(?<=\b\w)\s+(?=\w\b)", "", t_lat)
    t_despaced_no_punct = re.sub(r"(?<=\b\w)\s+(?=\w\b)", "", t_no_punct)

    # 5. So'zlar to'plami (barcha variantlarni o'z ichiga oladi)
    cleaned = re.sub(r"[^\w\s]", " ", t_lat)
    words = set(cleaned.split())
    words.update(re.sub(r"[^\w\s]", " ", t_despaced).split())
    words.update(re.sub(r"[^\w\s]", " ", t_no_punct).split())
    words.update(re.sub(r"[^\w\s]", " ", t_despaced_no_punct).split())

    # 6. Bo'shliqsiz ixcham matn (masalan: s.i.k.a.y -> sikay, j a l a p -> jalap)
    compact = re.sub(r"[^\w]", "", t_lat)

    # 7. Ketma-ket takrorlangan harflarni qisqartirish (masalan: siiiikaaaay -> siikay / sikay)
    compact_reduced = re.sub(r"(.)\1{2,}", r"\1\1", compact)
    compact_single = re.sub(r"(.)\1+", r"\1", compact)

    return t_lat, words, compact, compact_reduced, compact_single


def contains_profanity(text: str) -> bool:
    """Xabar matnida haqorat va so'kinish so'zlari bor-yo'qligini 100% universal aniqlash."""
    if not text:
        return False

    t_lat, words, compact, compact_red, compact_single = normalize_text_for_profanity(text)

    # 1. Qisqa va o'tkir so'kinishlar (words to'plami ichida)
    if any(sw in words for sw in SHORT_PROFANITY_WORDS):
        return True

    # 2. So'kinish asoslari (compact, compact_reduced va compact_single ichida)
    for stem in PROFANITY_COMPACT_STEMS:
        if stem in compact or stem in compact_red or stem in compact_single:
            return True

    # 3. Qarindosh-urug' bilan haqorat regexi (onangni..., enangni..., va h.k.)
    if COMPOUND_PROFANITY_PATTERN.search(t_lat):
        return True

    # 4. Sik / sk asosi tekshiruvi (xavfsiz so'zlar himoyalangan)
    for w in words:
        if w in SAFE_WORDS:
            continue
        if SIK_PATTERN.match(w):
            return True

    # 5. Konfiguratsiyadagi qo'shimcha so'zlar ro'yxati tekshiruvi
    for kw in PROFANITY_KEYWORDS:
        kw_clean = kw.lower().strip()
        if not kw_clean:
            continue
        if " " in kw_clean:
            kw_compact = kw_clean.replace(" ", "")
            if kw_clean in t_lat or kw_compact in compact:
                return True
        else:
            if kw_clean in words or (len(kw_clean) >= 4 and kw_clean in compact):
                return True

    return False


def contains_spam(text: str) -> bool:
    """Xabar matnida spam yoki reklama so'zlari bor-yo'qligini tekshirish."""
    lower_text = text.lower()
    for kw in SPAM_KEYWORDS:
        if kw in lower_text:
            return True
    return False


def contains_links(message: Message, bot_username: str = "") -> bool:
    """Xabarda har qanday havola (link), @username yoki URL bor-yo'qligini tekshirish."""
    text = (message.text or message.caption or "").strip()
    whitelist = list(WHITELISTED_LINKS)
    if bot_username:
        clean_bot = bot_username.lower().lstrip("@")
        whitelist.append(f"@{clean_bot}")
        whitelist.append(f"t.me/{clean_bot}")

    # 1. Telegram entities tekshiruvi (yashirin yoki ochiq havolalar)
    entities = (message.entities or []) + (message.caption_entities or [])
    for ent in entities:
        if ent.type in ("url", "text_link", "mention"):
            if ent.type == "text_link" and ent.url:
                if not any(w.lower() in ent.url.lower() for w in whitelist):
                    return True
            else:
                try:
                    sub = text.encode("utf-16-le")[ent.offset * 2 : (ent.offset + ent.length) * 2].decode("utf-16-le", errors="ignore")
                    if not any(w.lower() in sub.lower() for w in whitelist):
                        return True
                except Exception:
                    return True

    # 2. Matn ichidagi har qanday havolalar va domenlar
    matches = LINK_PATTERN.findall(text)
    if matches:
        for match in matches:
            if not any(w.lower() in match.lower() for w in whitelist):
                return True

    return False


def is_forwarded_message(message: Message) -> bool:
    """Xabar boshqa kanaldan yoki profildan forward (uzatilgan) ekanligini aniqlash."""
    return bool(
        getattr(message, "forward_origin", None)
        or getattr(message, "forward_date", None)
        or getattr(message, "forward_from", None)
        or getattr(message, "forward_from_chat", None)
        or getattr(message, "forward_sender_name", None)
    )


@router.message()
async def process_group_message(message: Message, bot: Bot) -> None:
    # Faqat guruh va superguruh xabarlarini qayta ishlash
    if message.chat.type in ("private",):
        return

    # 0. Kirdi-chiqdi va barcha xizmat xabarlarini zudlik bilan o'chirish
    if (
        message.new_chat_members
        or message.left_chat_member
        or message.pinned_message
        or message.video_chat_started
        or message.video_chat_ended
        or message.video_chat_participants_invited
        or message.video_chat_scheduled
        or message.new_chat_photo
        or message.delete_chat_photo
        or message.new_chat_title
        or message.message_auto_delete_timer_changed
    ):
        try:
            await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
        except Exception:
            pass
        return

    # Foydalanuvchi ma'lumotlari mavjud bo'lmasa qaytish
    if not message.from_user and not message.sender_chat:
        return

    # Guruh sozlamalarini olish
    group = await db.get_or_create_group(message.chat.id, message.chat.title or "")
    user_id = message.from_user.id if message.from_user else None
    user_is_admin = await is_admin(bot, message.chat.id, user_id, message=message)

    # 0. Global Qora Ro'yxat (Super Admin Blacklist) tekshiruvi
    if message.from_user and not user_is_admin:
        if await db.is_blacklisted(message.from_user.id):
            try:
                await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
            except Exception:
                pass
            return

    # 0.1 Anti-Channel (Kanal nomidan yozish taqiqi)
    if group.get("anti_channel_enabled", 1) == 1 and message.sender_chat and not message.from_user:
        if message.sender_chat.id != message.chat.id:
            try:
                await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
            except Exception:
                pass
            try:
                await bot.ban_chat_sender_chat(chat_id=message.chat.id, sender_chat_id=message.sender_chat.id)
            except Exception:
                pass
            ch_title = (message.sender_chat.title or "Kanal").replace("*", "").replace("`", "").replace("_", " ")
            notify = await bot.send_message(
                chat_id=message.chat.id,
                text=(
                    f"📢 **KANAL NOMIDAN YOZISH TAQIQLANGAN!** 🚫\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"«{ch_title}» kanali nomidan xabar yozish guruhda taqiqlangan!\n"
                    f"⚡️ Ushbu kanal guruhda yozishdan bloklandi.\n"
                    f"💡 Iltimos, faqat o'z shaxsiy profilingiz orqali muloqot qiling."
                ),
                parse_mode="Markdown",
            )
            asyncio.create_task(auto_delete_notification(notify, 60))
            asyncio.create_task(send_audit_log(
                bot=bot,
                chat_id=message.chat.id,
                chat_title=message.chat.title or "Guruh",
                event_title="Kanal Nomidan Yozish Taqiqi",
                user_name=ch_title,
                user_id=None,
                reason="Begona kanal orqali yozishga urindi (Kanal bloklandi)",
                snippet=message.text or message.caption or "",
            ))
            return

    # 0.2 Ismda reklama / havola va so'kinish tekshiruvi (Anti-Name Spam & Profanity)
    if message.from_user and not user_is_admin:
        user_full_name = message.from_user.full_name or ""
        if LINK_PATTERN.search(user_full_name):
            try:
                await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
            except Exception:
                pass
            mention = safe_mention(message.from_user.first_name, message.from_user.id)
            notify = await bot.send_message(
                chat_id=message.chat.id,
                text=(
                    f"👤 **ISMDAGI REKLAMA ANIQLANDI** 🛡\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"🚫 {mention}, profilingiz ismida reklama havolasi mavjud!\n"
                    f"⚠️ Guruh xavfsizligi yuzasidan xabaringiz o'chirildi.\n"
                    f"💡 Iltimos, ismingizdagi havola yoki @username ni olib tashlang."
                ),
                parse_mode="Markdown",
            )
            asyncio.create_task(auto_delete_notification(notify, 60))
            asyncio.create_task(send_audit_log(
                bot=bot,
                chat_id=message.chat.id,
                chat_title=message.chat.title or "Guruh",
                event_title="Ismda Havola / Reklama",
                user_name=message.from_user.full_name,
                user_id=message.from_user.id,
                reason="Profil ismida havola/reklama aniqlandi",
                snippet=message.from_user.full_name or "",
            ))
            return

        if contains_profanity(user_full_name):
            try:
                await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
            except Exception:
                pass
            mention = safe_mention(message.from_user.first_name, message.from_user.id)
            notify = await bot.send_message(
                chat_id=message.chat.id,
                text=(
                    f"👤 **ISMDAGI NOJO'YA SO'Z ANIQLANDI** 🛡\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"🚫 {mention}, profilingiz ismida haqoratli yoki so'kinish so'zi mavjud!\n"
                    f"⚠️ Guruh madaniyati yuzasidan xabaringiz o'chirildi.\n"
                    f"💡 Iltimos, ismingizdagi haqoratli so'zni tozalang."
                ),
                parse_mode="Markdown",
            )
            asyncio.create_task(auto_delete_notification(notify, 60))
            asyncio.create_task(send_audit_log(
                bot=bot,
                chat_id=message.chat.id,
                chat_title=message.chat.title or "Guruh",
                event_title="Ismda So'kinish / Haqorat",
                user_name=message.from_user.full_name,
                user_id=message.from_user.id,
                reason="Profil ismida so'kinish/haqorat aniqlandi",
                snippet=message.from_user.full_name or "",
            ))
            return

    # 1. Faollikni hisoblash (xabarlar sonini yozib borish) va xabar ID sini saqlash
    if message.from_user:
        await db.record_user_message(
            chat_id=message.chat.id,
            user_id=message.from_user.id,
            full_name=message.from_user.full_name,
            username=message.from_user.username,
        )
        await db.save_chat_message(
            chat_id=message.chat.id,
            user_id=message.from_user.id,
            message_id=message.message_id,
        )

    # 🔒 2. VIRUS (.APK VA BOSHQA ZARARLI) FAYLLAR TEKSHIRUVI (DOIM FAOL)
    is_dangerous, file_name = check_dangerous_file(message)
    if is_dangerous:
        sender_name = message.from_user.full_name if message.from_user else "Foydalanuvchi"
        sender_id = message.from_user.id if message.from_user else None
        mention = safe_mention(sender_name, sender_id)
        sender_type = "👑 Admin" if user_is_admin else "👤 A'zo"

        # 1. Zararli faylni zudlik bilan o'chirish
        deleted = False
        try:
            await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
            deleted = True
        except Exception as del_err:
            logger.warning(f"Zararli faylni o'chirishda xatolik: {del_err}")
            deleted = False

        # 2. Qoidabuzarni 2 soatga yozishdan cheklash (mute)
        mute_action_info = ""
        if not user_is_admin and message.from_user:
            until_date = datetime.now(timezone.utc) + timedelta(hours=2)
            try:
                await bot.restrict_chat_member(
                    chat_id=message.chat.id,
                    user_id=message.from_user.id,
                    permissions=ChatPermissions(can_send_messages=False),
                    until_date=until_date,
                )
                await db.record_punishment(message.chat.id, "mute")
                mute_action_info = "   • 🔇 **Qoidabuzar 2 soatga yozishdan cheklandi (MUTE)!**\n"
            except Exception as mute_err:
                logger.warning(f"Mute qilishda xatolik: {mute_err}")

        rules_btn_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="📜 Guruh Qoidalari", callback_data="btn_rules"),
                ]
            ]
        )

        safe_fname = (file_name or "APK fayl").replace("`", "'").replace("*", "")
        if deleted:
            if user_is_admin:
                apk_alert_text = (
                    f"🛡 **XAVFSIZLIK TIZIMI | KIBER-HIMOYA** 🛡\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"⚠️ **ADMIN TOMONIDAN .APK FAYL YUBORILDI!**\n\n"
                    f"👤 **Yuboruvchi:** {mention} (👑 Administrator)\n"
                    f"📁 **Fayl nomi:** `{safe_fname}`\n"
                    f"⚡️ **Ko'rilgan chora:** Guruh a'zolari xavfsizligi yuzasidan fayl o'chirildi! 🗑\n\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🔒 Guruhda a'zolar xavfsizligini ta'minlash uchun har qanday `.apk` dasturlarni tarqatish qat'iyan man etiladi.\n"
                    f"👮‍♂️ Guruh 24/7 kiber-himoya nazorati ostida ✅"
                )
            else:
                apk_alert_text = (
                    f"🛡 **XAVFSIZLIK TIZIMI | KIBER-HIMOYA** 🛡\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"🚨 **DIQQAT: ZARARLI .APK FAYL ANIQLANDI VA O'CHIRILDI!** 🗑\n\n"
                    f"👤 **Qoidabuzar:** {mention}\n"
                    f"📁 **Fayl nomi:** `{safe_fname}`\n"
                    f"⚡️ **Ko'rilgan tezkor choralar:**\n"
                    f"   • 🗑 **Zararli fayl darhol guruhdan o'chirildi!**\n"
                    f"{mute_action_info}\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"🛑 **BARCHA GURUH A'ZOLARI DIQQATIGA:**\n"
                    f"Telegram orqali tarqalayotgan noma'lum `.apk` fayllar — bank kartalaridagi pullar, "
                    f"SMS-kodlar va shaxsiy Telegram akkauntlarini o'g'irlaydigan **troyan viruslari** hisoblanadi!\n"
                    f"🔒 **O'z xavfsizligingiz uchun notanish fayllarni aslo ochmang va telefoningizga o'rnatmang!**\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"👮‍♂️ Guruh 24/7 kiber-himoya nazorati ostida ✅"
                )
        else:
            bot_info_early = await bot.get_me()
            admin_req_kb_early = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(
                            text="🛡 Botga Adminlik berish",
                            url=f"https://t.me/{bot_info_early.username}?startgroup=true&admin=delete_messages+restrict_members+pin_messages",
                        )
                    ]
                ]
            )
            rules_btn_kb = admin_req_kb_early
            apk_alert_text = (
                f"🚨 **FAVQULODDA XAVF: VIRUS (APK) FAYL!** 🚨\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"👤 **Yuboruvchi:** {mention} ({sender_type})\n"
                f"📁 **Xavfli fayl:** `{safe_fname}`\n\n"
                f"🛑 **BARCHA GURUH A'ZOLARI DIQQATIGA (O'TA MUHIM!):**\n"
                f"Ushbu faylni **ASLO OCHMANG, YUKLAMANG VA TELEFONINGIZGA O'RNATMANG!** ❌\n"
                f"Bu profilingiz va bank kartalaringizni o'g'irlaydigan **troyan virusi** hisoblanadi!\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"ℹ️ **Eslatma:** Telegram qoidasiga ko'ra, agar yuboruvchi Guruh Egasi (Owner) bo'lsa yoki botga 'Xabarlarni o'chirish' adminlik huquqi berilmagan bo'lsa, bot bu xabarni o'chira olmaydi.\n"
                f"1️⃣ Zudlik bilan faylni guruhdan **qo'lda o'chirib tashlang**!\n"
                f"2️⃣ Bot bunday viruslarni o'zi tozalab turishi uchun botga **Administrator (Xabarlarni o'chirish)** huquqini bering! 🛡"
            )

        try:
            notify = await bot.send_message(
                chat_id=message.chat.id,
                text=apk_alert_text,
                parse_mode="Markdown",
                reply_markup=rules_btn_kb,
            )
        except Exception:
            clean_plain = apk_alert_text.replace("*", "").replace("`", "").replace("_", "")
            notify = await bot.send_message(
                chat_id=message.chat.id,
                text=clean_plain,
                reply_markup=rules_btn_kb,
            )

        asyncio.create_task(auto_delete_notification(notify, APK_WARNING_NOTIFICATION_DELAY))
        asyncio.create_task(send_audit_log(
            bot=bot,
            chat_id=message.chat.id,
            chat_title=message.chat.title or "Guruh",
            event_title="Zararli APK / Virus Fayl",
            user_name=sender_name,
            user_id=sender_id,
            reason=f"Zararli fayl ({safe_fname}) aniqlandi va o'chirildi",
            snippet=safe_fname,
        ))
        return

    # ❗ AGAR FOYDALANUVCHI GURUH ADMINI BO'LSA — BOSHQA TEKSHIRUVLARGA TEGINILMAYDI
    if user_is_admin:
        return

    # 2. Majburiy kanallar (Mandatory Channels) tekshiruvi
    channels_enabled = group.get("channels_enabled", 1)
    if channels_enabled == 1 and message.from_user:
        mandatory_channels = await db.get_mandatory_channels(message.chat.id)
        if mandatory_channels:
            not_joined = []
            for ch in mandatory_channels:
                ch_id = ch["channel_id"]
                is_sub = await check_user_channel_subscription(bot, message.from_user.id, ch_id)
                if not is_sub:
                    not_joined.append(ch)

            if not_joined:
                mention = safe_mention(message.from_user.full_name, message.from_user.id)
                # Xabarni o'chirish
                try:
                    await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
                except Exception:
                    pass

                # Kanallarga ulanish tugmalarini yaratish
                buttons = []
                for ch in not_joined:
                    link = ch.get("invite_link") or ""
                    title = ch.get("title") or ch["channel_id"]
                    ch_id_str = str(ch["channel_id"]).strip()
                    if not link:
                        if ch_id_str.startswith("@"):
                            link = f"https://t.me/{ch_id_str.lstrip('@')}"
                        elif ch_id_str.startswith("-100") or (ch_id_str.startswith("-") and ch_id_str[1:].isdigit()):
                            try:
                                created_inv = await bot.create_chat_invite_link(int(ch_id_str), name="Guruh homiylik havolasi")
                                link = created_inv.invite_link
                                await db.update_mandatory_channel_link(message.chat.id, ch_id_str, link)
                            except Exception:
                                link = f"https://t.me/c/{ch_id_str.replace('-100', '')}"

                    if link:
                        is_rq = ch.get("is_join_request", 0) == 1 or ("+" in link or "joinchat" in link)
                        btn_label = f"➕ {title} (Ariza yuborish)" if is_rq else f"➕ {title}"
                        buttons.append([InlineKeyboardButton(text=btn_label, url=link)])

                buttons.append([
                    InlineKeyboardButton(
                        text="🔄 A'zo bo'ldim (Tekshirish)",
                        callback_data=f"check_sub:{message.from_user.id}",
                    )
                ])

                join_kb = InlineKeyboardMarkup(inline_keyboard=buttons)

                channel_list = "\n".join(
                    f"  • {ch.get('title') or ch['channel_id']}" for ch in not_joined
                )
                notify = await bot.send_message(
                    chat_id=message.chat.id,
                    text=(
                        f"📢 **HOMIY KANAL OBUNASI TALABI** 🔒\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"🚫 {mention}, guruhda yozish uchun avval quyidagi kanal(lar)ga a'zo bo'lishingiz lozim:\n\n"
                        f"{channel_list}\n\n"
                        f"✅ Kanalga a'zo bo'lgach (yoki maxfiy/zayafka kanalga ariza yuborgach), **«A'zo bo'ldim»** tugmasini bosing!"
                    ),
                    parse_mode="Markdown",
                    reply_markup=join_kb,
                )
                asyncio.create_task(auto_delete_notification(notify, 60))
                return

    # Botning o'zi ushbu guruhda admin ekanligi va xabar o'chira olishini tekshirish
    bot_can_delete_msg = await can_bot_delete(bot, message.chat.id)
    bot_info = await bot.get_me()

    admin_req_kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🛡 Botga Adminlik berish",
                    url=f"https://t.me/{bot_info.username}?startgroup=true&admin=delete_messages+restrict_members+pin_messages",
                )
            ]
        ]
    )

    # ⚡️ 2.1 Anti-Flood (Ketma-ket tez yozish orqali spam qilish)
    if group.get("anti_flood_enabled", 1) == 1 and message.from_user:
        if is_flooding(message.chat.id, message.from_user.id):
            if bot_can_delete_msg:
                try:
                    await message.delete()
                except Exception:
                    pass
                until_date = datetime.now(timezone.utc) + timedelta(minutes=15)
                try:
                    await bot.restrict_chat_member(
                        chat_id=message.chat.id,
                        user_id=message.from_user.id,
                        permissions=ChatPermissions(can_send_messages=False),
                        until_date=until_date,
                    )
                    await db.record_punishment(message.chat.id, "mute")
                except Exception:
                    pass
                mention = safe_mention(message.from_user.full_name, message.from_user.id)
                notify = await bot.send_message(
                    chat_id=message.chat.id,
                    text=(
                        f"⚡️ **ANTI-FLOOD HIMOYA TIZIMI** ⚡️\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"🚫 {mention}, siz juda tez xabar yozdingiz (Flood spam)!\n"
                        f"⏳ **Guruh tinchligini saqlash maqsadida 15 daqiqaga yozishdan cheklandingiz (MUTE).**"
                    ),
                    parse_mode="Markdown",
                )
                asyncio.create_task(auto_delete_notification(notify, AUTO_DELETE_NOTIFICATION_DELAY))
                asyncio.create_task(send_audit_log(
                    bot=bot,
                    chat_id=message.chat.id,
                    chat_title=message.chat.title or "Guruh",
                    event_title="Anti-Flood (Tezkor Spam)",
                    user_name=message.from_user.full_name,
                    user_id=message.from_user.id,
                    reason="Haddan tashqari tez xabar yozgani sababli 15m MUTE berildi",
                ))
                return

    # 📑 2.1.1 Anti-Duplicate / Copy-Paste Spam (Bir xil xabarni qayta-qayta yozish filtri)
    raw_text = message.text or message.caption or ""
    if group.get("anti_duplicate_enabled", 1) == 1 and raw_text and message.from_user:
        is_dup, dup_count = is_duplicate_message(message.chat.id, message.from_user.id, raw_text)
        if is_dup:
            if bot_can_delete_msg:
                try:
                    await message.delete()
                except Exception:
                    pass

                mute_info = ""
                if dup_count >= 3:
                    until_date = datetime.now(timezone.utc) + timedelta(minutes=15)
                    try:
                        await bot.restrict_chat_member(
                            chat_id=message.chat.id,
                            user_id=message.from_user.id,
                            permissions=ChatPermissions(can_send_messages=False),
                            until_date=until_date,
                        )
                        await db.record_punishment(message.chat.id, "mute")
                        mute_info = "\n⏳ **Qayta-qayta takrorlaganingiz sababli 15 daqiqaga yozishdan cheklandingiz (MUTE).**"
                    except Exception:
                        pass

                mention = safe_mention(message.from_user.full_name, message.from_user.id)
                notify = await bot.send_message(
                    chat_id=message.chat.id,
                    text=(
                        f"📑 **COPY-PASTE (DUBLIKAT) SPAM FILTRI** 🚫\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"🚫 {mention}, bir xil xabarni qayta-qayta yuborish taqiqlangan!\n"
                        f"⚡️ Xabaringiz o'chirildi.{mute_info}"
                    ),
                    parse_mode="Markdown",
                )
                asyncio.create_task(auto_delete_notification(notify, 60))
                asyncio.create_task(send_audit_log(
                    bot=bot,
                    chat_id=message.chat.id,
                    chat_title=message.chat.title or "Guruh",
                    event_title="Dublikat (Copy-Paste) Spam",
                    user_name=message.from_user.full_name,
                    user_id=message.from_user.id,
                    reason=f"Bir xil xabarni {dup_count} marta takrorladi",
                    snippet=raw_text,
                ))
                return

    # 🔠 2.1.2 Anti-Premium Custom Emoji Spam (Haddan ortiq animatsiyali emojilar filtri)
    if group.get("anti_emoji_spam", 1) == 1 and message.from_user:
        entities = (message.entities or []) + (message.caption_entities or [])
        custom_emoji_count = sum(1 for e in entities if e.type == "custom_emoji")
        if custom_emoji_count > 5:
            if bot_can_delete_msg:
                try:
                    await message.delete()
                except Exception:
                    pass
                mention = safe_mention(message.from_user.full_name, message.from_user.id)
                notify = await bot.send_message(
                    chat_id=message.chat.id,
                    text=(
                        f"🔠 **PREMIUM EMOJI CHEKLOVI** 🚫\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"🚫 {mention}, bir xabarda 5 tadan ortiq animatsiyali Premium emoji yuborish taqiqlangan!\n"
                        f"⚡️ Chat tinchligi va a'zolarga noqulaylik tug'dirmaslik maqsadida xabaringiz o'chirildi."
                    ),
                    parse_mode="Markdown",
                )
                asyncio.create_task(auto_delete_notification(notify, 60))
                asyncio.create_task(send_audit_log(
                    bot=bot,
                    chat_id=message.chat.id,
                    chat_title=message.chat.title or "Guruh",
                    event_title="Haddan tashqari Premium Emoji",
                    user_name=message.from_user.full_name,
                    user_id=message.from_user.id,
                    reason=f"{custom_emoji_count} ta animatsiyali emoji ishlatildi",
                ))
                return

    # 🤖 2.2 Anti-Inline Bot (Yashirin botlar orqali reklama yuborish taqiqi)
    if group.get("anti_inline_bot", 0) == 1 and message.via_bot:
        mention = safe_mention(message.from_user.full_name, message.from_user.id) if message.from_user else "Foydalanuvchi"
        if bot_can_delete_msg:
            try:
                await message.delete()
            except Exception:
                pass
            notify = await bot.send_message(
                chat_id=message.chat.id,
                text=(
                    f"🤖 **INLINE BOT REKLAMASI TAQIQI** 🤖\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"🚫 {mention}, guruhda inline botlar (@...) orqali xabar yuborish taqiqlangan!"
                ),
                parse_mode="Markdown",
            )
            asyncio.create_task(auto_delete_notification(notify))
            return

    # 🈲 2.3 Anti-Foreign Oriental (Arab, Xitoy, Yapon, Kores va boshqa yot yozuvlar filtri)
    text_to_check = message.text or message.caption or ""
    user_name_to_check = message.from_user.full_name if message.from_user else ""
    sender_chat_title = message.sender_chat.title if message.sender_chat else ""
    if group.get("anti_arabic_enabled", 1) == 1 and (
        contains_foreign_oriental_script(text_to_check)
        or contains_foreign_oriental_script(user_name_to_check)
        or contains_foreign_oriental_script(sender_chat_title)
    ):
        mention = safe_mention(message.from_user.full_name, message.from_user.id) if message.from_user else "Spambot"
        if bot_can_delete_msg:
            try:
                await message.delete()
            except Exception:
                pass
            notify = await bot.send_message(
                chat_id=message.chat.id,
                text=(
                    f"🈲 **CHET EL (ARAB / XITOY / YAPON / KORES) SPAMBOT FILTRI** 🚫\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"🚫 {mention}, guruhda arabcha, xitoycha, yaponcha, korescha yoki boshqa yot yozuvlarda yozish qat'iyan taqiqlangan!\n"
                    f"⚡️ Xabar guruh tozaligini ta'minlash maqsadida o'chirildi."
                ),
                parse_mode="Markdown",
            )
            asyncio.create_task(auto_delete_notification(notify, 60))
            asyncio.create_task(send_audit_log(
                bot=bot,
                chat_id=message.chat.id,
                chat_title=message.chat.title or "Guruh",
                event_title="Chet el (Arab/Sharq) Spambot",
                user_name=message.from_user.full_name if message.from_user else "Spambot",
                user_id=message.from_user.id if message.from_user else None,
                reason="Yot yozuvlar (arabcha/xitoycha/yaponcha/korescha) aniqlandi",
                snippet=text_to_check,
            ))
            return

    # 2.4 Mass-Mention (Ommaviy @Tag spam hujumi filtri)
    raw_text = message.text or message.caption or ""
    if raw_text and not user_is_admin and message.from_user:
        entities = (message.entities or []) + (message.caption_entities or [])
        mention_count = sum(1 for e in entities if e.type in ("mention", "text_mention"))
        if mention_count >= 5 or len(re.findall(r"@[a-zA-Z0-9_]{4,}", raw_text)) >= 5:
            if bot_can_delete_msg:
                try:
                    await message.delete()
                except Exception:
                    pass
                until_date = datetime.now(timezone.utc) + timedelta(hours=2)
                try:
                    await bot.restrict_chat_member(
                        chat_id=message.chat.id,
                        user_id=message.from_user.id,
                        permissions=ChatPermissions(can_send_messages=False),
                        until_date=until_date,
                    )
                    await db.record_punishment(message.chat.id, "mute")
                except Exception:
                    pass
                mention = safe_mention(message.from_user.full_name, message.from_user.id)
                notify = await bot.send_message(
                    chat_id=message.chat.id,
                    text=(
                        f"⚡️ **OMMAVIY MENTION SPAM ANIQLANDI** ⚡️\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"🚫 {mention}, bir xabarda 5 tadan ortiq a'zolarni teglash (mention) taqiqlangan!\n"
                        f"⏳ **2 soatga yozishdan cheklandingiz (MUTE).**"
                    ),
                    parse_mode="Markdown",
                )
                asyncio.create_task(auto_delete_notification(notify, 60))
                asyncio.create_task(send_audit_log(
                    bot=bot,
                    chat_id=message.chat.id,
                    chat_title=message.chat.title or "Guruh",
                    event_title="Ommaviy @Mention Hujumi",
                    user_name=message.from_user.full_name,
                    user_id=message.from_user.id,
                    reason=f"Bir xabarda {mention_count} ta a'zo teglangan (2 soat MUTE)",
                    snippet=raw_text,
                ))
                return

    # 2.5 Anti-Caps Lock (Katta harflar bilan baqirib yozish filtri)
    if group.get("anti_caps_enabled", 0) == 1 and raw_text and not user_is_admin and message.from_user:
        letters = [c for c in raw_text if c.isalpha()]
        if len(letters) >= 8:
            upper_count = sum(1 for c in letters if c.isupper())
            if (upper_count / len(letters)) >= 0.70:
                if bot_can_delete_msg:
                    try:
                        await message.delete()
                    except Exception:
                        pass
                    mention = safe_mention(message.from_user.full_name, message.from_user.id)
                    notify = await bot.send_message(
                        chat_id=message.chat.id,
                        text=(
                            f"🔠 **KATTA HARFLAR TAQIQI (CAPS LOCK)** 🔠\n"
                            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                            f"🚫 {mention}, guruhda faqat katta harflar bilan baqirib yozish taqiqlangan!\n"
                            f"💡 Iltimos, Caps Lock-ni o'chiring va odatiy kichik harflarda yozing."
                        ),
                        parse_mode="Markdown",
                    )
                    asyncio.create_task(auto_delete_notification(notify, 60))
                    return

    # 3. Forward (Uzatilgan) xabarlarni nazorat qilish va o'chirish (Anti-Forward)
    if group.get("antiforward_enabled", 1) == 1 and is_forwarded_message(message):
        mention = safe_mention(message.from_user.full_name, message.from_user.id) if message.from_user else "Foydalanuvchi"
        if bot_can_delete_msg:
            try:
                await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
            except Exception:
                pass

            notify = await bot.send_message(
                chat_id=message.chat.id,
                text=(
                    f"🔄 **FORWARD XABAR TAQIQI** 🔄\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"⚠️ {mention}, guruhda boshqa kanallardan yoki profillardan xabarlarni **forward (uzatish)** qilish taqiqlangan!"
                ),
                parse_mode="Markdown",
            )
            asyncio.create_task(auto_delete_notification(notify))
            return
        else:
            await message.reply(
                text=(
                    f"🔄 **FORWARD XABAR ANIQLANDI** 🔄\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"👤 Yuboruvchi: {mention}\n\n"
                    f"🤖 **Hurmatli Guruh Administratorlari!**\n"
                    f"Guruhdagi forward xabarlarni avtomatik o'chirib tozalashim uchun "
                    f"menga guruh sozlamalaridan **Administrator (Admin)** huquqini bering! 🛡\n"
                    f"✅ *Kerakli huquq: Xabarlarni o'chirish.*"
                ),
                parse_mode="Markdown",
                reply_markup=admin_req_kb,
            )
            return

    # 4. Majburiy a'zo qo'shish talabi (Invites restriction)
    min_invites = int(group.get("min_invites") or 0)
    invites_enabled = int(group.get("invites_enabled") if group.get("invites_enabled") is not None else 1)

    if invites_enabled == 1 and min_invites > 0 and message.from_user:
        user_invites = await db.get_user_invites(message.chat.id, message.from_user.id)
        if user_invites < min_invites:
            left_needed = min_invites - user_invites
            percent = min(100, int(round((user_invites / min_invites) * 100)))
            bar = make_progress_bar(percent)
            mention = safe_mention(message.from_user.full_name, message.from_user.id)

            deleted = False
            try:
                await message.delete()
                deleted = True
            except Exception:
                deleted = False

            if deleted:
                # Anti-spam: takroriy ogohlantirishlarni 4 soniya ichida qayta yubormaslik (lekin xabar o'chadi)
                now_t = asyncio.get_event_loop().time()
                warn_key = (message.chat.id, message.from_user.id)
                last_warn = INVITE_WARN_CACHE.get(warn_key, 0.0)
                if now_t - last_warn > 4.0:
                    INVITE_WARN_CACHE[warn_key] = now_t

                    # Avvalgi ogohlantirishlarni chat toza bo'lishi uchun o'chirib tashlaymiz
                    old_db_warns = await db.pop_invite_warnings(message.chat.id, message.from_user.id)
                    old_mem_warns = pop_user_invite_warn_msgs(message.chat.id, message.from_user.id)
                    for old_w_id in set(old_db_warns + old_mem_warns):
                        try:
                            await bot.delete_message(chat_id=message.chat.id, message_id=old_w_id)
                        except Exception:
                            pass

                    notify = await bot.send_message(
                        chat_id=message.chat.id,
                        text=(
                            f"👥 **MAJBURIY A'ZO QO'SHISH TALABI** 👥\n"
                            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                            f"🚫 {mention}, siz guruhda yozish uchun kamida **{min_invites} ta** a'zo qo'shishingiz kerak!\n\n"
                            f"📊 **Siz qo'shgan a'zolar:** **{user_invites} / {min_invites} ta ({percent}%)**\n"
                            f"📈 **Jarayon:** {bar} **{percent}%**\n"
                            f"➕ **Yozish huquqi uchun yana:** **{left_needed} ta** a'zo qo'shishingiz kerak!\n\n"
                            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                            f"💡 Guruhga do'stlaringizni taklif qiling va suhbatga qo'shiling! 😊"
                        ),
                        parse_mode="Markdown",
                    )
                    await db.add_invite_warning(message.chat.id, message.from_user.id, notify.message_id)
                    set_user_invite_warn_msg(message.chat.id, message.from_user.id, notify.message_id)
                    asyncio.create_task(auto_delete_notification(notify, 60))
                return
            else:
                # Bot admin bo'lmasa: xabarni o'chira olmagani sababli ogohlantiradi
                bot_info = await bot.get_me()
                admin_req_kb = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="🛡 Botga Adminlik berish",
                                url=f"https://t.me/{bot_info.username}?startgroup=true&admin=delete_messages+restrict_members+pin_messages",
                            )
                        ]
                    ]
                )

                old_db_warns = await db.pop_invite_warnings(message.chat.id, message.from_user.id)
                old_mem_warns = pop_user_invite_warn_msgs(message.chat.id, message.from_user.id)
                for old_w_id in set(old_db_warns + old_mem_warns):
                    try:
                        await bot.delete_message(chat_id=message.chat.id, message_id=old_w_id)
                    except Exception:
                        pass

                warn_inv = await message.reply(
                    text=(
                        f"👥 **MAJBURIY A'ZO QO'SHISH TALABI** 👥\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"🚫 {mention}, guruhda yozish uchun kamida **{min_invites} ta** a'zo qo'shishingiz kerak!\n\n"
                        f"📊 **Siz qo'shgan a'zolar:** **{user_invites} / {min_invites} ta ({percent}%)**\n"
                        f"📈 **Jarayon:** {bar} **{percent}%**\n"
                        f"➕ **Yozish huquqi uchun yana:** **{left_needed} ta** a'zo qo'shishingiz kerak!\n\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                        f"🤖 **Administratorlar diqqatiga:** Bot ushbu qoidani to'liq nazorat qilishi va a'zo qo'shmaganlarning xabarlarini avtomatik o'chirib turishi uchun botga guruhda **Administrator (Xabarlarni o'chirish)** huquqini bering! 🛡"
                    ),
                    parse_mode="Markdown",
                    reply_markup=admin_req_kb,
                )
                await db.add_invite_warning(message.chat.id, message.from_user.id, warn_inv.message_id)
                set_user_invite_warn_msg(message.chat.id, message.from_user.id, warn_inv.message_id)
                asyncio.create_task(auto_delete_notification(warn_inv, 60))
                return

    # 5. Media filtrlari (Stiker/GIF va Ovozli/Dumaloq video cheklovi)
    mention = safe_mention(message.from_user.full_name, message.from_user.id) if message.from_user else "Foydalanuvchi"

    if group.get("block_stickers", 0) == 1 and (message.sticker or message.animation):
        if bot_can_delete_msg:
            try:
                await message.delete()
            except Exception:
                pass
            notify = await bot.send_message(
                chat_id=message.chat.id,
                text=(
                    f"🎭 **STIKER VA GIF TAQIQI** 🎭\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"🚫 {mention}, bu guruhda stiker va GIF larni yuborish taqiqlangan!\n"
                    f"💡 Iltimos, faqat matnli xabarlar orqali muloqot qiling. 😊"
                ),
                parse_mode="Markdown",
            )
            asyncio.create_task(auto_delete_notification(notify))
            return
        else:
            await message.reply(
                text=(
                    f"🎭 **STIKER VA GIF ANIQLANDI** 🎭\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"👤 Yuboruvchi: {mention}\n\n"
                    f"🤖 **Administratorlar diqqatiga:**\n"
                    f"Guruhda stiker va GIF larni avtomatik o'chirib turishim uchun botga **Administrator (Xabarlarni o'chirish)** huquqini bering! 🛡"
                ),
                parse_mode="Markdown",
                reply_markup=admin_req_kb,
            )
            return

    if group.get("block_voice", 0) == 1 and (message.voice or message.video_note or message.audio):
        if bot_can_delete_msg:
            try:
                await message.delete()
            except Exception:
                pass
            notify = await bot.send_message(
                chat_id=message.chat.id,
                text=(
                    f"🎙 **OVOZLI VA VIDEO XABAR TAQIQI** 🎙\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"🚫 {mention}, bu guruhda ovozli xabar (voice) va dumaloq videolar yuborish taqiqlangan!\n"
                    f"💡 Iltimos, fikringizni matn ko'rinishida yozing. 😊"
                ),
                parse_mode="Markdown",
            )
            asyncio.create_task(auto_delete_notification(notify))
            return
        else:
            await message.reply(
                text=(
                    f"🎙 **OVOZLI XABAR ANIQLANDI** 🎙\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"👤 Yuboruvchi: {mention}\n\n"
                    f"🤖 **Administratorlar diqqatiga:**\n"
                    f"Guruhda ovozli xabarlarni avtomatik o'chirib turishim uchun botga **Administrator (Xabarlarni o'chirish)** huquqini bering! 🛡"
                ),
                parse_mode="Markdown",
                reply_markup=admin_req_kb,
            )
            return

    text = message.text or message.caption or ""

    # 5.1 Maxsus taqiqlangan so'zlar filtri (Custom banned words)
    if text and not user_is_admin:
        custom_banned = await db.get_banned_words(message.chat.id)
        if custom_banned:
            lower_txt = text.lower()
            matched_word = None
            for b_word in custom_banned:
                b_clean = b_word.strip().lower()
                if b_clean and b_clean in lower_txt:
                    matched_word = b_word
                    break

            if matched_word:
                if bot_can_delete_msg:
                    try:
                        await message.delete()
                    except Exception:
                        pass
                    warn_cnt = await db.add_warn(message.chat.id, message.from_user.id, f"Taqiqlangan so'z: {matched_word}") if message.from_user else 0
                    mention = safe_mention(message.from_user.full_name, message.from_user.id) if message.from_user else "Foydalanuvchi"
                    notify = await bot.send_message(
                        chat_id=message.chat.id,
                        text=(
                            f"🛑 **TAQIQLANGAN SO'Z ANIQLANDI** 🛑\n"
                            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                            f"🚫 {mention}, bu guruhda **«{matched_word}»** so'zini ishlatish adminlar tomonidan taqiqlangan!\n\n"
                            f"⚠️ Ogohlantirish berildi: **{warn_cnt}/{MAX_WARNS}**\n"
                            f"💡 Guruh qoidalariga rioya qiling!"
                        ),
                        parse_mode="Markdown",
                    )
                    asyncio.create_task(auto_delete_notification(notify))
                    return
                else:
                    await message.reply(
                        text=(
                            f"🛑 **TAQIQLANGAN SO'Z ANIQLANDI** 🛑\n\n"
                            f"⚠️ Ushbu xabarda adminlar tomonidan taqiqlangan so'z ishlatildi.\n"
                            f"Bot xabarni o'chirishi uchun botga **Administrator (Xabarlarni o'chirish)** huquqini bering!"
                        ),
                        parse_mode="Markdown",
                    )
                    return

    # 6. Haqorat va so'kinish filtri (Profanity filter)
    if group.get("profanity_enabled", 1) == 1 and contains_profanity(text):
        if not message.from_user and message.sender_chat:
            if bot_can_delete_msg:
                try:
                    await message.delete()
                except Exception:
                    pass
                try:
                    await bot.ban_chat_sender_chat(chat_id=message.chat.id, sender_chat_id=message.sender_chat.id)
                except Exception:
                    pass
                ch_title = (message.sender_chat.title or "Kanal").replace("*", "").replace("_", " ").replace("`", "'")
                notify = await bot.send_message(
                    chat_id=message.chat.id,
                    text=(
                        f"🚫 **BEGONA KANAL BLOKLANDI** 🚫\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"📢 **Kanal:** «{ch_title}»\n"
                        f"⚡️ **Sabab:** So'kinish va haqorat yuborilgani uchun!\n"
                        f"🔒 Ushbu kanal guruhda yozishdan butunlay bloklandi."
                    ),
                    parse_mode="Markdown",
                )
                asyncio.create_task(auto_delete_notification(notify, 60))
            return

        if message.from_user:
            warn_cnt = await db.add_warn(message.chat.id, message.from_user.id, "So'kinish/Haqorat")

            if bot_can_delete_msg:
                try:
                    await message.delete()
                except Exception:
                    pass

                if warn_cnt >= MAX_WARNS:
                    until_date = datetime.now(timezone.utc) + timedelta(hours=24)
                    try:
                        await bot.restrict_chat_member(
                            chat_id=message.chat.id,
                            user_id=message.from_user.id,
                            permissions=ChatPermissions(can_send_messages=False),
                            until_date=until_date,
                        )
                        await db.reset_warns(message.chat.id, message.from_user.id)
                        notify_mute = await bot.send_message(
                            chat_id=message.chat.id,
                            text=(
                                f"🔇 **QOIDABUZAR CHEKLANDI (MUTE)** 🔇\n"
                                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                                f"👤 **Qoidabuzar:** {mention}\n"
                                f"⚡️ **Sabab:** So'kinish va haqorat qoidalarini ketma-ket buzgani uchun!\n"
                                f"⏳ **Jazo:** **24 soatga guruhda yozishdan cheklandi!**"
                            ),
                            parse_mode="Markdown",
                        )
                        asyncio.create_task(auto_delete_notification(notify_mute, 60))
                        asyncio.create_task(send_audit_log(
                            bot=bot,
                            chat_id=message.chat.id,
                            chat_title=message.chat.title or "Guruh",
                            event_title="So'kinish / 24s MUTE",
                            user_name=message.from_user.full_name,
                            user_id=message.from_user.id,
                            reason=f"So'kinish takrorlangani sababli 24 soatga MUTE berildi ({warn_cnt}/{MAX_WARNS})",
                            snippet=text,
                        ))
                        return
                    except Exception:
                        pass

                notify = await bot.send_message(
                    chat_id=message.chat.id,
                    text=(
                        f"🤬 **NOJO'YA SO'Z ANIQLANDI** 🤬\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"🚫 {mention}, guruhda so'kinish va haqoratli so'zlar ishlatish qat'iyan taqiqlanadi!\n"
                        f"⚠️ Ogohlantirish: **{warn_cnt}/{MAX_WARNS}**\n"
                        f"💡 *Ogohlantirishlar 3 taga yetsa, 24 soatga guruhda yozishdan cheklanasiz!*"
                    ),
                    parse_mode="Markdown",
                )
                asyncio.create_task(auto_delete_notification(notify, 60))
                asyncio.create_task(send_audit_log(
                    bot=bot,
                    chat_id=message.chat.id,
                    chat_title=message.chat.title or "Guruh",
                    event_title="So'kinish / Haqorat",
                    user_name=message.from_user.full_name,
                    user_id=message.from_user.id,
                    reason=f"Nojo'ya so'z ishlatildi (Ogohlantirish: {warn_cnt}/{MAX_WARNS})",
                    snippet=text,
                ))
                return
            else:
                await message.reply(
                    text=(
                        f"🤬 **NOJO'YA SO'Z ANIQLANDI** 🤬\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"👤 Yuboruvchi: {mention}\n"
                        f"⚠️ Guruhda so'kinish va haqorat taqiqlanadi! ({warn_cnt}/{MAX_WARNS})\n\n"
                        f"🤖 **Administratorlar diqqatiga:**\n"
                        f"Bot bunday xabarlarni o'zi tozalab turishi uchun botga **Administrator (Xabarlarni o'chirish)** huquqini bering! 🛡"
                    ),
                    parse_mode="Markdown",
                    reply_markup=admin_req_kb,
                )
                return

    # 7. Begona havolalar (Har qanday havola va reklama) nazorati
    if group.get("antilink_enabled", 1) == 1 and contains_links(message, bot_username=bot_info.username or ""):
        if not message.from_user and message.sender_chat:
            if bot_can_delete_msg:
                try:
                    await message.delete()
                except Exception:
                    pass
                try:
                    await bot.ban_chat_sender_chat(chat_id=message.chat.id, sender_chat_id=message.sender_chat.id)
                except Exception:
                    pass
                ch_title = (message.sender_chat.title or "Kanal").replace("*", "").replace("_", " ").replace("`", "'")
                notify = await bot.send_message(
                    chat_id=message.chat.id,
                    text=(
                        f"🚫 **BEGONA KANAL BLOKLANDI** 🚫\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"📢 **Kanal:** «{ch_title}»\n"
                        f"⚡️ **Sabab:** Guruhda kanal orqali reklama va havola tarqatilgani uchun!\n"
                        f"🔒 Ushbu kanal guruhda yozishdan butunlay bloklandi."
                    ),
                    parse_mode="Markdown",
                )
                asyncio.create_task(auto_delete_notification(notify))
            return

        if message.from_user:
            mention = safe_mention(message.from_user.full_name, message.from_user.id)
            warn_cnt = await db.add_warn(message.chat.id, message.from_user.id, "Ruxsatsiz havola / Reklama")

            if bot_can_delete_msg:
                try:
                    await message.delete()
                except Exception:
                    pass

                if warn_cnt >= MAX_WARNS:
                    until_date = datetime.now(timezone.utc) + timedelta(hours=24)
                    try:
                        await bot.restrict_chat_member(
                            chat_id=message.chat.id,
                            user_id=message.from_user.id,
                            permissions=ChatPermissions(can_send_messages=False),
                            until_date=until_date,
                        )
                        await db.reset_warns(message.chat.id, message.from_user.id)
                        notify_mute = await bot.send_message(
                            chat_id=message.chat.id,
                            text=(
                                f"🔇 **QOIDABUZAR CHEKLANDI (MUTE)** 🔇\n"
                                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                                f"👤 **Qoidabuzar:** {mention}\n"
                                f"⚡️ **Sabab:** Ruxsatsiz havola tarqatgani uchun ({MAX_WARNS}/{MAX_WARNS})\n"
                                f"⏳ **Jazo:** **24 soatga guruhda yozishdan cheklandi!**"
                            ),
                            parse_mode="Markdown",
                        )
                        asyncio.create_task(auto_delete_notification(notify_mute, 60))
                        asyncio.create_task(send_audit_log(
                            bot=bot,
                            chat_id=message.chat.id,
                            chat_title=message.chat.title or "Guruh",
                            event_title="Havola Tarqatish / 24s MUTE",
                            user_name=message.from_user.full_name,
                            user_id=message.from_user.id,
                            reason=f"Ruxsatsiz havola takrorlangani sababli 24 soatga MUTE berildi ({warn_cnt}/{MAX_WARNS})",
                            snippet=text,
                        ))
                        return
                    except Exception:
                        pass

                notify = await bot.send_message(
                    chat_id=message.chat.id,
                    text=(
                        f"🚫 **REKLAMA VA HAVOLA TAQIQI** 🚫\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"🚫 {mention}, guruhda har qanday havola (link) va reklama tarqatish qat'iyan taqiqlanadi!\n\n"
                        f"📢 Reklama bermoqchi bo'lsangiz, iltimos, **guruh administratorlariga** murojaat qiling! 👮‍♂️🤝\n\n"
                        f"⚠️ Ogohlantirish: **{warn_cnt}/{MAX_WARNS}**"
                    ),
                    parse_mode="Markdown",
                )
                asyncio.create_task(auto_delete_notification(notify, 60))
                asyncio.create_task(send_audit_log(
                    bot=bot,
                    chat_id=message.chat.id,
                    chat_title=message.chat.title or "Guruh",
                    event_title="Ruxsatsiz Havola (Link)",
                    user_name=message.from_user.full_name,
                    user_id=message.from_user.id,
                    reason=f"Havola / Reklama aniqlandi (Ogohlantirish: {warn_cnt}/{MAX_WARNS})",
                    snippet=text,
                ))
                return
            else:
                # Bot admin bo'lmasa — reklama tarqatganga ogohlantirish beradi va adminlik so'raydi!
                warn_msg = await message.reply(
                    text=(
                        f"🚫 **REKLAMA VA HAVOLA TAQIQI** 🚫\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"👤 Yuboruvchi: {mention}\n"
                        f"⚠️ Guruhda har qanday havola (link) va reklama tarqatish taqiqlanadi!\n"
                        f"📢 Reklama bermoqchi bo'lsangiz, **guruh administratorlariga** murojaat qiling! 👮‍♂️🤝\n\n"
                        f"🤖 **Administratorlar diqqatiga:**\n"
                        f"Bot havolalarni avtomatik o'chirib turishi uchun botga **Administrator (Xabarlarni o'chirish)** huquqini bering! 🛡"
                    ),
                    parse_mode="Markdown",
                    reply_markup=admin_req_kb,
                )
                asyncio.create_task(auto_delete_notification(warn_msg))
                return

    # 8. Spam va Reklama nazorati
    if group.get("antispam_enabled", 1) == 1 and contains_spam(text):
        if not message.from_user and message.sender_chat:
            if bot_can_delete_msg:
                try:
                    await message.delete()
                except Exception:
                    pass
                try:
                    await bot.ban_chat_sender_chat(chat_id=message.chat.id, sender_chat_id=message.sender_chat.id)
                except Exception:
                    pass
                ch_title = (message.sender_chat.title or "Kanal").replace("*", "").replace("_", " ").replace("`", "'")
                notify = await bot.send_message(
                    chat_id=message.chat.id,
                    text=(
                        f"🚫 **BEGONA KANAL BLOKLANDI** 🚫\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"📢 **Kanal:** «{ch_title}»\n"
                        f"⚡️ **Sabab:** Guruhda kanal orqali spam/reklama tarqatilgani uchun!\n"
                        f"🔒 Ushbu kanal guruhda yozishdan butunlay bloklandi."
                    ),
                    parse_mode="Markdown",
                )
                asyncio.create_task(auto_delete_notification(notify))
            return

        if message.from_user:
            mention = safe_mention(message.from_user.full_name, message.from_user.id)
            warn_cnt = await db.add_warn(message.chat.id, message.from_user.id, "Spam/Reklama")

            if bot_can_delete_msg:
                try:
                    await message.delete()
                except Exception:
                    pass

                if warn_cnt >= MAX_WARNS:
                    until_date = datetime.now(timezone.utc) + timedelta(hours=24)
                    try:
                        await bot.restrict_chat_member(
                            chat_id=message.chat.id,
                            user_id=message.from_user.id,
                            permissions=ChatPermissions(can_send_messages=False),
                            until_date=until_date,
                        )
                        await db.reset_warns(message.chat.id, message.from_user.id)
                        notify_mute = await bot.send_message(
                            chat_id=message.chat.id,
                            text=(
                                f"🔇 **QOIDABUZAR CHEKLANDI (MUTE)** 🔇\n"
                                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                                f"👤 **Qoidabuzar:** {mention}\n"
                                f"⚡️ **Sabab:** Ko'p spam xabar yuborgani uchun ({MAX_WARNS}/{MAX_WARNS})\n"
                                f"⏳ **Jazo:** **24 soatga guruhda yozishdan cheklandi!**"
                            ),
                            parse_mode="Markdown",
                        )
                        asyncio.create_task(auto_delete_notification(notify_mute, 60))
                        asyncio.create_task(send_audit_log(
                            bot=bot,
                            chat_id=message.chat.id,
                            chat_title=message.chat.title or "Guruh",
                            event_title="Spam / 24s MUTE",
                            user_name=message.from_user.full_name,
                            user_id=message.from_user.id,
                            reason=f"Spam takrorlangani sababli 24 soatga MUTE berildi ({warn_cnt}/{MAX_WARNS})",
                            snippet=text,
                        ))
                        return
                    except Exception:
                        pass

                notify = await bot.send_message(
                    chat_id=message.chat.id,
                    text=(
                        f"🛡️ **ANTISPAM HIMOYA TIZIMI** 🛡️\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"⚠️ {mention}, spam yoki reklama xabari aniqlangani sababli o'chirildi!\n"
                        f"📊 Ogohlantirish: **{warn_cnt}/{MAX_WARNS}**"
                    ),
                    parse_mode="Markdown",
                )
                asyncio.create_task(auto_delete_notification(notify, 60))
                asyncio.create_task(send_audit_log(
                    bot=bot,
                    chat_id=message.chat.id,
                    chat_title=message.chat.title or "Guruh",
                    event_title="Spam / Reklama So'zlari",
                    user_name=message.from_user.full_name,
                    user_id=message.from_user.id,
                    reason=f"Taqiqlangan spam/reklama aniqlandi (Ogohlantirish: {warn_cnt}/{MAX_WARNS})",
                    snippet=text,
                ))
                return
            else:
                # Bot admin bo'lmasa — reklama tarqatganga javob yozadi va adminlik so'raydi!
                await message.reply(
                    text=(
                        f"🛡️ **ANTISPAM HIMOYA TIZIMI** 🛡️\n"
                        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                        f"👤 Yuboruvchi: {mention} (Ogohlantirish: {warn_cnt}/{MAX_WARNS})\n\n"
                        f"🤖 **Hurmatli Guruh Administratorlari!**\n"
                        f"Ushbu reklamalarni darhol o'chirib, qoidabuzarlarni cheklab turishim uchun "
                        f"menga guruh sozlamalaridan **Administrator (Admin)** huquqini bering! 🛡\n"
                        f"✅ *Kerakli huquq: Xabarlarni o'chirish va a'zolarni cheklash.*"
                    ),
                    parse_mode="Markdown",
                    reply_markup=admin_req_kb,
                )
                return

    # 9. FAQ (Avto-javoblar) tekshiruvi
    if text:
        faq_ans = await db.match_faq(message.chat.id, text)
        if faq_ans:
            await message.reply(faq_ans)
            return


# ── Majburiy kanallarga a'zolikni tekshirish (Callback) ───────────
@router.callback_query(F.data.startswith("check_sub:"))
async def cb_check_subscription(call: CallbackQuery, bot: Bot) -> None:
    if not call.message or not call.from_user:
        return

    parts = call.data.split(":")
    target_user_id = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    if call.from_user.id != target_user_id:
        await call.answer("❌ Bu tugma siz uchun emas!", show_alert=True)
        return

    channels = await db.get_mandatory_channels(call.message.chat.id)
    not_joined = []
    for ch in channels:
        ch_id = ch["channel_id"]
        is_sub = await check_user_channel_subscription(bot, call.from_user.id, ch_id)
        if not is_sub:
            not_joined.append(ch)

    if not not_joined:
        await call.answer("🎉 Barcha kanallarga a'zoligingiz yoki arizangiz tasdiqlandi! Endi guruhda bemalol yoza olasiz ✅", show_alert=True)
        try:
            await call.message.delete()
        except Exception:
            pass
    else:
        left_count = len(not_joined)
        await call.answer(
            f"❌ Hali {left_count} ta kanalga a'zo bo'lmadingiz yoki ariza yubormadingiz! Iltimos, barcha kanallarga kiring.",
            show_alert=True,
        )


@router.edited_message()
async def process_group_edited_message(message: Message, bot: Bot) -> None:
    """Tahrirlangan xabarlarni ham to'liq tekshirish (so'kinish, reklama yoki virus bo'lsa darhol o'chirish)."""
    await process_group_message(message, bot)

