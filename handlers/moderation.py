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
from services.ui_utils import make_progress_bar

router = Router(name="moderation")
logger = logging.getLogger(__name__)

# Taklif ogohlantirishlari kesh: {(chat_id, user_id): timestamp}
INVITE_WARN_CACHE: dict[tuple[int, int], float] = {}

# Linklarni aniqlash regexi (har qanday domen, vebsayt, Telegram havolasi va @username)
LINK_PATTERN = re.compile(
    r"(https?://\S+|www\.\S+|t\.me/\S+|telegram\.me/\S+|telegram\.dog/\S+|@[a-zA-Z0-9_]{4,}|\b[a-zA-Z0-9.-]+\.(?:com|uz|ru|net|org|io|me|info|biz|xyz|app|site|online|top|club|vip|live|pro|dev|store|shop|link|edu|gov)\b\S*)",
    re.IGNORECASE,
)

# Arab, Eron va Xitoy spambot yozuvlarini aniqlash regexi
ARABIC_ORIENTAL_PATTERN = re.compile(
    r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF\u4E00-\u9FFF]"
)

# Flood nazorati uchun kesh: {(chat_id, user_id): [timestamps]}
FLOOD_CACHE: dict[tuple[int, int], list[float]] = {}
FLOOD_THRESHOLD_COUNT = 5
FLOOD_THRESHOLD_SECONDS = 4.0


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


def contains_arabic_or_oriental(text: str) -> bool:
    """Matnda arab, fors yoki sharqiy spambot belgilari borligini aniqlash."""
    if not text:
        return False
    return bool(ARABIC_ORIENTAL_PATTERN.search(text))


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


def contains_profanity(text: str) -> bool:
    """Xabar matnida haqorat va so'kinish so'zlari bor-yo'qligini aniqlash."""
    if not text:
        return False
    lower_text = text.lower()
    # Nuqta, tire, yulduzcha va belgilarni bo'shliqqa aylantirish
    normalized = re.sub(r"[^\w\s]", " ", lower_text)
    words = set(normalized.split())
    no_spaces = re.sub(r"\s+", "", lower_text)

    for kw in PROFANITY_KEYWORDS:
        kw_lower = kw.lower()
        if " " in kw_lower:
            if kw_lower in lower_text:
                return True
        else:
            if kw_lower in words or kw_lower in no_spaces:
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
                # Ariza yuborgan bo'lsa — ruxsat beriladi
                has_request = await db.has_join_request(message.from_user.id, ch_id)
                if has_request:
                    continue
                # A'zoligini tekshirish
                try:
                    member = await bot.get_chat_member(ch_id, message.from_user.id)
                    if member.status in ("member", "administrator", "creator", "restricted"):
                        continue
                    not_joined.append(ch)
                except Exception:
                    # Kanal/guruhga kirish yo'q bo'lsa — ehtiyot chorasi sifatida o'tkazib yuboramiz
                    continue

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
                    if not link:
                        # username bo'lsa havola yasash
                        ch_id_str = str(ch["channel_id"]).strip()
                        if ch_id_str.startswith("@"):
                            link = f"https://t.me/{ch_id_str.lstrip('@')}"
                    if link:
                        buttons.append([InlineKeyboardButton(text=f"➕ {title}", url=link)])

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
                        f"✅ Kanalga obuna bo'lgach (yoki ariza yuborgach), **«A'zo bo'ldim»** tugmasini bosing!"
                    ),
                    parse_mode="Markdown",
                    reply_markup=join_kb,
                )
                asyncio.create_task(auto_delete_notification(notify, 25))
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
                asyncio.create_task(auto_delete_notification(notify, 15))
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

    # 🈲 2.3 Anti-Arabic / Anti-Raid (Arab va sharqiy spambotlar filtri)
    text_to_check = message.text or message.caption or ""
    user_name_to_check = message.from_user.full_name if message.from_user else ""
    if group.get("anti_arabic_enabled", 0) == 1 and (contains_arabic_or_oriental(text_to_check) or contains_arabic_or_oriental(user_name_to_check)):
        mention = safe_mention(message.from_user.full_name, message.from_user.id) if message.from_user else "Spambot"
        if bot_can_delete_msg:
            try:
                await message.delete()
            except Exception:
                pass
            notify = await bot.send_message(
                chat_id=message.chat.id,
                text=(
                    f"🈲 **ANTI-RAID / SPAMBOT FILTRI** 🈲\n"
                    f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                    f"🚫 {mention}, guruhda arab/fors/xitoy yozuvlari bilan xabar yozish taqiqlangan!"
                ),
                parse_mode="Markdown",
            )
            asyncio.create_task(auto_delete_notification(notify))
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
                    asyncio.create_task(auto_delete_notification(notify, 15))
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
                asyncio.create_task(auto_delete_notification(warn_inv, 15))
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
                asyncio.create_task(auto_delete_notification(notify))
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
                        asyncio.create_task(auto_delete_notification(notify_mute))
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
                asyncio.create_task(auto_delete_notification(notify))
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
                        asyncio.create_task(auto_delete_notification(notify_mute))
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
                asyncio.create_task(auto_delete_notification(notify))
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
                        asyncio.create_task(auto_delete_notification(notify_mute))
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
                asyncio.create_task(auto_delete_notification(notify))
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
        has_request = await db.has_join_request(call.from_user.id, ch_id)
        if has_request:
            continue
        try:
            member = await bot.get_chat_member(ch_id, call.from_user.id)
            if member.status in ("member", "administrator", "creator", "restricted"):
                continue
            not_joined.append(ch)
        except Exception:
            continue

    if not not_joined:
        await call.answer("🎉 Barcha kanallarga a'zo bo'ldingiz! Endi guruhda bemalol yoza olasiz ✅", show_alert=True)
        try:
            await call.message.delete()
        except Exception:
            pass
    else:
        left_count = len(not_joined)
        await call.answer(
            f"❌ Hali {left_count} ta kanalga a'zo emassiz! Iltimos, barcha kanallarga a'zo bo'ling.",
            show_alert=True,
        )

