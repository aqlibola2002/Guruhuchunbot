from __future__ import annotations

import asyncio
import re
from datetime import datetime, timedelta, timezone

from aiogram import Router, Bot
from aiogram.types import (
    Message,
    ChatPermissions,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from config import (
    SPAM_KEYWORDS,
    PROFANITY_KEYWORDS,
    WHITELISTED_LINKS,
    AUTO_DELETE_NOTIFICATION_DELAY,
    MAX_WARNS,
)
from database.db import db
from filters.admin_filter import is_admin, can_bot_delete

router = Router(name="moderation")

# Linklarni aniqlash regexi
LINK_PATTERN = re.compile(
    r"(https?://\S+|t\.me/\S+|telegram\.me/\S+|telegram\.dog/\S+|@[a-zA-Z0-9_]{5,})",
    re.IGNORECASE,
)


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


def contains_links(text: str) -> bool:
    """Xabarda ruxsat etilmagan havolalar bor-yo'qligini tekshirish."""
    matches = LINK_PATTERN.findall(text)
    if not matches:
        return False

    # Oq ro'yxatdagi havolalar tekshiruvi
    for match in matches:
        is_whitelisted = any(w_link.lower() in match.lower() for w_link in WHITELISTED_LINKS)
        if not is_whitelisted:
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

    # Foydalanuvchi ma'lumotlari mavjud bo'lmasa qaytish
    if not message.from_user and not message.sender_chat:
        return

    # Guruh sozlamalarini olish
    group = await db.get_or_create_group(message.chat.id, message.chat.title or "")
    user_id = message.from_user.id if message.from_user else None
    user_is_admin = await is_admin(bot, message.chat.id, user_id, message=message)

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

    # 🔒 VIRUS FAYL TEKSHIRUVI — ADMINLAR UCHUN HAM ISHLAYDI
    is_dangerous_file_early = False
    file_name_early = ""

    if message.document:
        doc_name = (message.document.file_name or "").lower().strip()
        doc_mime = (message.document.mime_type or "").lower().strip()
        if (
            ".apk" in doc_name
            or doc_name.endswith((".apk", ".xapk", ".apks", ".ipa", ".bin"))
            or "android.package-archive" in doc_mime
            or "application/vnd.android" in doc_mime
            or ("application/octet-stream" in doc_mime and ".apk" in doc_name)
        ):
            is_dangerous_file_early = True
            file_name_early = message.document.file_name or "APK fayl"

    if not is_dangerous_file_early and message.audio:
        audio_name = (message.audio.file_name or "").lower().strip()
        if ".apk" in audio_name:
            is_dangerous_file_early = True
            file_name_early = message.audio.file_name or "APK fayl"

    if not is_dangerous_file_early and message.video:
        video_name = (message.video.file_name or "").lower().strip()
        if ".apk" in video_name:
            is_dangerous_file_early = True
            file_name_early = message.video.file_name or "APK fayl"

    if is_dangerous_file_early:
        sender_name = message.from_user.full_name if message.from_user else "Foydalanuvchi"
        sender_id = message.from_user.id if message.from_user else None
        mention = f"[{sender_name}](tg://user?id={sender_id})" if sender_id else sender_name
        sender_type = "👑 Admin" if user_is_admin else "👤 A'zo"

        deleted = False
        try:
            await message.delete()
            deleted = True
        except Exception:
            deleted = False

        if deleted:
            warn_info = ""
            if not user_is_admin and message.from_user:
                warn_cnt = await db.add_warn(message.chat.id, message.from_user.id, "Zararli APK fayl yuborish")
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
                        warn_info = f"\n🚫 Siz {MAX_WARNS} ta ogohlantirish olganingiz sababli **24 soatga guruhda yozishdan cheklandingiz (MUTE)!**"
                    except Exception:
                        warn_info = f"\n⚠️ **Sizga ogohlantirish berildi:** {warn_cnt}/{MAX_WARNS}"
                else:
                    left = MAX_WARNS - warn_cnt
                    warn_info = f"\n⚠️ **Sizga ogohlantirish berildi:** {warn_cnt}/{MAX_WARNS} (yana {left} tadan so'ng yozish cheklanadi)."

            notify = await bot.send_message(
                chat_id=message.chat.id,
                text=(
                    f"🚨 **XAVFSIZLIK: Zararli APK fayl aniqlandi va o'chirildi!** 🛡\n\n"
                    f"🚫 {mention} ({sender_type}), siz yuborgan **«{file_name_early}»** fayli xavfli bo'lgani sababli guruhdan darhol o'chirildi!\n"
                    f"{warn_info}\n\n"
                    f"⚠️ **DIQQAT:** Telegram orqali tarqalayotgan noma'lum APK fayllar — profilingiz, bank kartalaringiz va SMS-kodlaringizni o'g'irlaydigan **troyan viruslari** hisoblanadi!\n"
                    f"Guruh a'zolarining xavfsizligini ta'minlash maqsadida guruhda har qanday APK fayllarni yuborish qat'iyan taqiqlanadi."
                ),
                parse_mode="Markdown",
            )
            asyncio.create_task(auto_delete_notification(notify, 20))
            return
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
            await message.reply(
                text=(
                    f"🚨🚨 **DIQQAT: GURUHDA XAVFLI VIRUS (APK) FAYL ANIQLANDI!** 🚨🚨\n\n"
                    f"👤 **Yuboruvchi:** {mention} ({sender_type})\n"
                    f"📁 **Fayl:** `{file_name_early}`\n\n"
                    f"🛑 **BARCHA GURUH A'ZOLARI DIQQATIGA (MUHIM!):**\n"
                    f"Ushbu faylni **ASLO OCHMANG, YUKLAMANG VA TELEFONINGIZGA O'RNATMANG!** ❌\n"
                    f"Bu sizning bank kartalaringizdagi pullarni, SMS-kodlaringizni va Telegram profilingizni o'g'irlaydigan **troyan virusi** hisoblanadi!\n\n"
                    f"👮‍♂️ **Guruh Administratorlari diqqatiga:**\n"
                    f"Bot guruhda Administrator emasligi sababli ushbu xavfli faylni avtomatik o'chira olmadi!\n"
                    f"1️⃣ Zudlik bilan yuqoridagi faylni guruhdan **qo'lda o'chirib tashlang**!\n"
                    f"2️⃣ Bot bunday viruslarni o'zi tozalab turishi uchun botga **Administrator (Xabarlarni o'chirish)** huquqini bering! 🛡"
                ),
                parse_mode="Markdown",
                reply_markup=admin_req_kb_early,
            )
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
                mention = f"[{message.from_user.full_name}](tg://user?id={message.from_user.id})"
                # Xabarni o'chirish
                try:
                    await message.delete()
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
                        f"🔒 {mention}, guruhda yozish uchun avval quyidagi kanal(lar)ga **a'zo bo'lishingiz** shart:\n\n"
                        f"{channel_list}\n\n"
                        f"✅ Barchasiga a'zo bo'lgach, quyidagi **«A'zo bo'ldim»** tugmasini bosing!\n"
                        f"📩 *Agar kirish so'rovingiz ko'rib chiqilayotgan bo'lsa, xabar yozaversangiz bo'ladi.*"
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

    # 2. Xavfli APK (Virus/Troyan) fayllarini aniqlash — bu yerga kelganda foydalanuvchi admin EMAS
    # (Adminlar uchun tekshiruv yuqorida — admin bypass'dan oldin o'tkazildi)

    # 3. Forward (Uzatilgan) xabarlarni nazorat qilish va o'chirish (Anti-Forward)
    if group.get("antiforward_enabled", 1) == 1 and is_forwarded_message(message):
        mention = f"[{message.from_user.full_name}](tg://user?id={message.from_user.id})" if message.from_user else "Foydalanuvchi"
        if bot_can_delete_msg:
            try:
                await message.delete()
            except Exception:
                pass

            notify = await bot.send_message(
                chat_id=message.chat.id,
                text=f"⚠️ {mention}, guruhda boshqa kanallardan yoki profillardan xabarlarni **forward (uzatish)** qilish taqiqlangan!",
                parse_mode="Markdown",
            )
            asyncio.create_task(auto_delete_notification(notify, 7))
            return
        else:
            await message.reply(
                text=(
                    f"⚠️ **DIQQAT: Guruhda forward xabar aniqlandi!**\n\n"
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
    min_invites = group.get("min_invites", 0)
    invites_enabled = group.get("invites_enabled", 1)

    if invites_enabled == 1 and min_invites > 0 and message.from_user:
        user_invites = await db.get_user_invites(message.chat.id, message.from_user.id)
        if user_invites < min_invites:
            left_needed = min_invites - user_invites
            mention = f"[{message.from_user.full_name}](tg://user?id={message.from_user.id})"

            deleted = False
            try:
                await message.delete()
                deleted = True
            except Exception:
                deleted = False

            if deleted:
                # Bot admin bo'lsa: xabarni o'chirib, a'zo qo'shish kerakligi haqida ogohlantirish yuboradi
                notify = await bot.send_message(
                    chat_id=message.chat.id,
                    text=(
                        f"🚫 **DIQQAT: Guruhda yozish uchun a'zo qo'shishingiz shart!**\n\n"
                        f"{mention}, siz guruhda yozish uchun kamida **{min_invites}** ta odam qo'shishingiz kerak!\n\n"
                        f"👥 Siz qo'shgan a'zolar: **{user_invites} / {min_invites}** ta\n"
                        f"➕ Yana **{left_needed}** ta do'stingizni taklif qiling!\n\n"
                        f"💡 A'zolar qo'shganingizdan so'ng guruhda bemalol yoza olasiz."
                    ),
                    parse_mode="Markdown",
                )
                asyncio.create_task(auto_delete_notification(notify, 10))
                return
            else:
                # Bot admin bo'lmasa: xabarni o'chirmasdan a'zo qo'shish kerakligi haqida xabar yuboradi
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
                await message.reply(
                    text=(
                        f"🚫 {mention}, guruhda yozish uchun kamida **{min_invites}** ta odam qo'shishingiz kerak!\n\n"
                        f"👥 Siz qo'shgan a'zolar: **{user_invites} / {min_invites}** ta\n"
                        f"➕ Yana **{left_needed}** ta do'stingizni taklif qiling!\n\n"
                        f"🤖 **Administratorlar diqqatiga:** Bot ushbu qoidani to'liq nazorat qilishi va a'zo qo'shmaganlarning xabarlarini avtomatik o'chirib turishi uchun botga guruhda **Administrator (Admin)** huquqini bering! 🛡"
                    ),
                    parse_mode="Markdown",
                    reply_markup=admin_req_kb,
                )
                return

    # 5. Media filtrlari (Stiker/GIF va Ovozli/Dumaloq video cheklovi)
    mention = f"[{message.from_user.full_name}](tg://user?id={message.from_user.id})" if message.from_user else "Foydalanuvchi"

    if group.get("block_stickers", 0) == 1 and (message.sticker or message.animation):
        if bot_can_delete_msg:
            try:
                await message.delete()
            except Exception:
                pass
            notify = await bot.send_message(
                chat_id=message.chat.id,
                text=f"🎭 {mention}, guruhda stiker va GIF lar yuborish taqiqlangan!",
                parse_mode="Markdown",
            )
            asyncio.create_task(auto_delete_notification(notify, 6))
            return
        else:
            await message.reply(
                text=f"🎭 {mention}, guruhda stiker va GIF lar taqiqlangan!",
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
                text=f"🎙 {mention}, guruhda ovozli xabar (voice) va dumaloq video yuborish taqiqlangan!",
                parse_mode="Markdown",
            )
            asyncio.create_task(auto_delete_notification(notify, 6))
            return
        else:
            await message.reply(
                text=f"🎙 {mention}, guruhda ovozli va video xabarlar taqiqlangan!",
                parse_mode="Markdown",
                reply_markup=admin_req_kb,
            )
            return

    text = message.text or message.caption or ""

    # 6. Haqorat va so'kinish filtri (Profanity filter)
    if group.get("profanity_enabled", 1) == 1 and contains_profanity(text):
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
                    await bot.send_message(
                        chat_id=message.chat.id,
                        text=f"🚫 {mention} ko'p so'kingani va qoidalarni buzgani sababli 24 soatga guruhda yozishdan cheklandi!",
                        parse_mode="Markdown",
                    )
                    return
                except Exception:
                    pass

            notify = await bot.send_message(
                chat_id=message.chat.id,
                text=(
                    f"🤬 {mention}, guruhda so'kinish va haqoratli so'zlar ishlatish qat'iyan taqiqlanadi!\n"
                    f"⚠️ Ogohlantirish: {warn_cnt}/{MAX_WARNS}"
                ),
                parse_mode="Markdown",
            )
            asyncio.create_task(auto_delete_notification(notify, 7))
            return
        else:
            await message.reply(
                text=(
                    f"🤬 {mention}, guruhda so'kinish va haqorat taqiqlanadi!\n"
                    f"⚠️ Ogohlantirish: {warn_cnt}/{MAX_WARNS}"
                ),
                parse_mode="Markdown",
                reply_markup=admin_req_kb,
            )
            return

    # 7. Begona havolalar (Linklar) nazorati
    if group.get("antilink_enabled", 1) == 1 and contains_links(text):
        mention = f"[{message.from_user.full_name}](tg://user?id={message.from_user.id})"

        if bot_can_delete_msg:
            try:
                await message.delete()
            except Exception:
                pass

            notify = await bot.send_message(
                chat_id=message.chat.id,
                text=f"⚠️ {mention}, guruhda begona havolalar (linklar) tarqatish taqiqlangan!",
                parse_mode="Markdown",
            )
            asyncio.create_task(auto_delete_notification(notify))
            return
        else:
            # Bot admin bo'lmasa — reklama tarqatganga ogohlantirish beradi va adminlik so'raydi!
            await message.reply(
                text=(
                    f"⚠️ **DIQQAT: Guruhda begona havola (link) aniqlandi!**\n\n"
                    f"👤 Yuboruvchi: {mention}\n\n"
                    f"🤖 **Hurmatli Guruh Administratorlari!**\n"
                    f"Guruhdagi bunday begona reklamalarni avtomatik o'chirib tozalashim uchun "
                    f"menga guruh sozlamalaridan **Administrator (Admin)** huquqini bering! 🛡\n"
                    f"✅ *Kerakli huquq: Xabarlarni o'chirish.*"
                ),
                parse_mode="Markdown",
                reply_markup=admin_req_kb,
            )
            return

    # 8. Spam va Reklama nazorati
    if group.get("antispam_enabled", 1) == 1 and contains_spam(text):
        mention = f"[{message.from_user.full_name}](tg://user?id={message.from_user.id})"
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
                    await bot.send_message(
                        chat_id=message.chat.id,
                        text=f"🚫 {mention} ko'p reklama tarqatgani sababli 24 soatga guruhda yozishdan cheklandi!",
                        parse_mode="Markdown",
                    )
                    return
                except Exception:
                    pass

            notify = await bot.send_message(
                chat_id=message.chat.id,
                text=(
                    f"🛡️ {mention}, spam yoki reklama xabari aniqlangani sababli o'chirildi!\n"
                    f"⚠️ Ogohlantirish: {warn_cnt}/{MAX_WARNS}"
                ),
                parse_mode="Markdown",
            )
            asyncio.create_task(auto_delete_notification(notify))
            return
        else:
            # Bot admin bo'lmasa — reklama tarqatganga javob yozadi va adminlik so'raydi!
            await message.reply(
                text=(
                    f"🛡️ **DIQQAT: Reklama yoki spam xabari aniqlandi!**\n\n"
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

