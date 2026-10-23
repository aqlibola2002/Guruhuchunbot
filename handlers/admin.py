from __future__ import annotations

import asyncio
import re
from datetime import datetime, timedelta, timezone

from aiogram import Router, Bot, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    ChatPermissions,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

from config import MAX_WARNS, DEFAULT_MUTE_SECONDS, AUTO_DELETE_NOTIFICATION_DELAY
from database.db import db
from filters.admin_filter import is_admin
from services.target_resolver import resolve_target

router = Router(name="admin")


def get_admin_name(message: Message) -> str:
    """Admin ismini anonim adminlar va sender_chat uchun xavfsiz aniqlash."""
    if message.from_user and message.from_user.full_name:
        name = message.from_user.full_name
    elif message.sender_chat and message.sender_chat.title:
        name = message.sender_chat.title
    else:
        name = "Administrator"
    return name.replace("*", "").replace("_", " ").replace("`", "'")


def get_bot_id(bot: Bot) -> int:
    """Botning int ID sini xavfsiz olish."""
    try:
        return int(bot.token.split(":")[0])
    except Exception:
        return 0


def parse_duration(time_str: str) -> tuple[timedelta | None, str]:
    """Vaqt satrini timedelta ga aylantirish (masalan: 10m, 2h, 1d)."""
    match = re.search(r"\b(\d+)([mhd])\b", time_str.strip().lower())
    if not match:
        return None, "1h"
    val, unit = int(match.group(1)), match.group(2)
    duration_label = f"{val}{unit}"
    if unit == "m":
        return timedelta(minutes=val), duration_label
    elif unit == "h":
        return timedelta(hours=val), duration_label
    elif unit == "d":
        return timedelta(days=val), duration_label
    return None, "1h"


async def auto_delete_message(msg: Message, delay: int = AUTO_DELETE_NOTIFICATION_DELAY) -> None:
    """Xabarni ma'lum vaqtdan so'ng avtomatik o'chirib yuborish."""
    await asyncio.sleep(delay)
    try:
        await msg.delete()
    except Exception:
        pass


# ── /admin [Guruh admin paneliga tezkor kirish] ──────────────────────
@router.message(Command("admin", ignore_case=True))
async def cmd_admin_info(message: Message, bot: Bot) -> None:
    """Guruh adminlari uchun: bot holati va tezkor boshqaruv paneli."""
    if message.chat.type in ("private",):
        await message.reply(
            "⚠️ Bu buyruq faqat guruhlarda ishlaydi!\n\n"
            "Guruhingizga qo'shib, `/admin` buyrug'ini yuboring."
        )
        return

    user_id = message.from_user.id if message.from_user else None
    if not await is_admin(bot, message.chat.id, user_id, message=message):
        await message.reply("❌ Bu buyruq faqat guruh administratorlari uchun!")
        return

    group = await db.get_or_create_group(message.chat.id, message.chat.title or "")

    def s(val: int) -> str:
        return "✅" if val == 1 else "❌"

    min_inv = group.get("min_invites", 0)
    inv_status = f"✅ ({min_inv} ta)" if (group.get("invites_enabled", 1) == 1 and min_inv > 0) else "❌"

    # Bot huquqlarini tekshirish
    from filters.admin_filter import can_bot_delete
    bot_can_del = await can_bot_delete(bot, message.chat.id)
    bot_status = "✅ Admin (o'chira oladi)" if bot_can_del else "⚠️ Admin emas (o'chira olmaydi!)"

    panel_text = (
        f"╔═══════════════════════════════════════╗\n"
        f"   👑 **GURUH BOSHQARUV PANELI (ADMIN)** 🛡\n"
        f"╚═══════════════════════════════════════╝\n\n"
        f"📍 **Guruh:** «{message.chat.title}»\n"
        f"🤖 **Bot maqomi:** {bot_status}\n\n"
        f"⚙️ **FAOL HIMOYA VA NAZORAT TIZIMLARI:**\n"
        f"├ {s(group.get('profanity_enabled', 1))} 🤬 Haqorat va so'kinish filtri\n"
        f"├ {'🚫' if group.get('block_stickers', 0) == 1 else '🟢'} 🎭 Stiker va GIF taqiqi\n"
        f"├ {'🚫' if group.get('block_voice', 0) == 1 else '🟢'} 🎙 Ovozli va Video doira taqiqi\n"
        f"├ {s(group.get('antilink_enabled', 1))} 🔗 Begona linklar bloklanishi\n"
        f"├ {s(group.get('antispam_enabled', 1))} 🚫 Reklama / Spam tozalash\n"
        f"├ {s(group.get('anti_flood_enabled', 1))} ⚡️ Anti-Flood (Tezkor spam filtri)\n"
        f"├ {s(group.get('anti_arabic_enabled', 0))} 🈲 Arab/Raid spambot filtri\n"
        f"├ {'🚫' if group.get('anti_inline_bot', 0) == 1 else '🟢'} 🤖 Inline botlar taqiqi\n"
        f"├ {s(group.get('night_mode_enabled', 0))} 🌙 Tungi rejim ({group.get('night_mode_start', '23:00')}-{group.get('night_mode_end', '07:00')})\n"
        f"├ {s(group.get('antiforward_enabled', 1))} 🔄 Forward xabarlar taqiqi\n"
        f"├ {s(group.get('channels_enabled', 1))} 📢 Homiy kanal a'zoligi talabi\n"
        f"├ {s(group.get('auto_approve_joins', 1))} 📥 Zayafkalarni avto-qabul qilish\n"
        f"├ {inv_status} 👥 Majburiy a'zo qo'shish talabi\n"
        f"├ {s(group.get('welcome_enabled', 1))} 👋 Yangi a'zolarni kutib olish\n"
        f"├ {s(group.get('scheduled_enabled', 1))} ⏰ Rejali avto-xabarlar\n"
        f"└ ✅ 🦠 APK Virus & Troyan filtri (Doimiy faol)\n\n"
        f"📌 **ASOSIY BUYRUQLAR RO'YXATI:**\n"
        f"├ ⚙️ `/sozlamalar` — Himoya sozlamalari boshqaruv menyusi\n"
        f"├ 🌙 `/tun [on|off]` — Tungi avto-qulf rejimini sozlash\n"
        f"├ 📥 `/zayafka [on|off]` — Qo'shilish arizalarini 1 soniyada avto-qabul qilish\n"
        f"├ 🔇 `/chekla [10m|2h|1d]` — Yozishni vaqtincha cheklash (Mute)\n"
        f"├ 🚫 `/hayda` — A'zoni guruhdan butunlay chiqarish va bloklash (Ban)\n"
        f"├ 🧹 `/tozala [20]` — Oxirgi xabarlarni tozalash (yoki a'zoga reply)\n"
        f"├ 👥 `/odam [soni]` — Majburiy a'zo talabi (`/odam 0` bekor qilish)\n"
        f"├ 🥇 `/toptaklif` — Eng ko'p taklif qilganlar reytingi (TOP-10)\n"
        f"├ 0️⃣ `/nol` — A'zoning takliflarini 0 qilish (reply yoki @ / id)\n"
        f"├ 📢 `/kanal` — Homiy kanallarni sozlash (/kanal @kanal)\n"
        f"├ 📌 `/elon [matn]` — Muhim xabarni e'lon qilib qadash (pin)\n"
        f"└ 📊 `/statistika` — Guruh faolligi va monitoringi"
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⚙️ Sozlamalar paneli", callback_data="open_settings_from_admin"),
            ],
            [
                InlineKeyboardButton(text="📊 Statistika", callback_data="show_stats_admin"),
            ],
        ]
    )

    await message.reply(panel_text, parse_mode="Markdown", reply_markup=kb)


@router.callback_query(F.data == "open_settings_from_admin")
async def cb_open_settings_from_admin(call: CallbackQuery, bot: Bot) -> None:
    if not call.message or not call.from_user:
        return
    if not await is_admin(bot, call.message.chat.id, call.from_user.id):
        await call.answer("❌ Faqat adminlar uchun!", show_alert=True)
        return
    group = await db.get_or_create_group(call.message.chat.id)
    kb = get_settings_keyboard(group)
    await call.message.reply(
        f"╔═══════════════════════════════════════╗\n"
        f"   ⚙️ **HIMOYA VA XAVFSIZLIK SOZLAMALARI** 🛡\n"
        f"╚═══════════════════════════════════════╝\n\n"
        f"📍 **Guruh:** «{call.message.chat.title}»\n\n"
        f"Quyidagi interaktiv tugmalar orqali botning xavfsizlik va nazorat funksiyalarini boshqaring:",
        reply_markup=kb,
        parse_mode="Markdown",
    )
    await call.answer()


@router.callback_query(F.data == "show_stats_admin")
async def cb_show_stats_admin(call: CallbackQuery, bot: Bot) -> None:
    if not call.message or not call.from_user:
        return
    if not await is_admin(bot, call.message.chat.id, call.from_user.id):
        await call.answer("❌ Faqat adminlar uchun!", show_alert=True)
        return
    from database.db import db as _db
    stats = await _db.get_group_stats(call.message.chat.id)
    await call.message.reply(
        f"╔═══════════════════════════════════════╗\n"
        f"   📊 **GURUH STATISTIKASI (ADMIN)** 📈\n"
        f"╚═══════════════════════════════════════╝\n\n"
        f"📍 **Guruh:** «{call.message.chat.title}»\n\n"
        f"├ 💬 Jami xabarlar: **{stats.get('total_messages', 0):,}** ta\n"
        f"├ 👤 Jami a'zolar: **{stats.get('total_members', 0):,}** ta\n"
        f"├ 👥 Taklif qilingan: **{stats.get('total_invites', 0):,}** ta\n"
        f"└ ⚠️ Berilgan ogohlantirishlar: **{stats.get('total_warns', 0):,}** ta",
        parse_mode="Markdown",
    )
    await call.answer()


# ── /odam [har qanday son quyish mumkin] ───────────────────────────
@router.message(Command("odam", "setinvites", ignore_case=True))
async def cmd_odam(message: Message, bot: Bot) -> None:
    if message.chat.type in ("private",):
        await message.reply("⚠️ Ushbu buyruq faqat guruhlarda ishlaydi!")
        return

    group = await db.get_or_create_group(message.chat.id, message.chat.title or "")
    current = group.get("min_invites", 0)

    # Admin ekanligini tekshirish (anonim admin va guruh egasini ham hisobga olgan holda)
    user_id = message.from_user.id if message.from_user else None
    user_is_admin = await is_admin(bot, message.chat.id, user_id, message=message)

    # Agar oddiy a'zo yozsa, hozirgi talab haqida ma'lumot beramiz
    if not user_is_admin:
        user_invites = await db.get_user_invites(message.chat.id, user_id) if user_id else 0
        if current > 0:
            left = max(0, current - user_invites)
            await message.reply(
                f"╔═══════════════════════════════════════╗\n"
                f"   👥 **MAJBURIY A'ZO QO'SHISH TALABI** 👥\n"
                f"╚═══════════════════════════════════════╝\n\n"
                f"📌 Guruhda erkin yozish uchun har bir a'zo kamida **{current}** ta odam qo'shishi shart.\n\n"
                f"├ 📊 Siz qo'shgan a'zolar: **{user_invites} / {current}** ta\n"
                f"└ ➕ Qolgan: **{left}** ta yangi a'zo\n\n"
                f"💡 Takliflaringizni to'liq ko'rish uchun: `/takliflarim`",
                parse_mode="Markdown",
            )
        else:
            await message.reply(
                f"╔═══════════════════════════════════════╗\n"
                f"   👥 **MAJBURIY A'ZO TALABI** 👥\n"
                f"╚═══════════════════════════════════════╝\n\n"
                f"Bu guruhda hozirda majburiy a'zo qo'shish talabi yo'q (barcha uchun erkin muloqot) ✨\n\n"
                f"ℹ️ Agar siz guruh admini bo'lsangiz, talab o'rnatish uchun: `/odam [soni]`",
                parse_mode="Markdown",
            )
        return

    # Admin tomonidan chaqirilganda
    parts = (message.text or "").split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.reply(
            f"╔═══════════════════════════════════════╗\n"
            f"   👥 **MAJBURIY A'ZO TALABI SOZLASH** 👥\n"
            f"╚═══════════════════════════════════════╝\n\n"
            f"📌 Hozirgi o'rnatilgan talab: **{current} ta**\n\n"
            f"Har qanday son qo'yishingiz mumkin:\n"
            f"├ `/odam 5` — Har bir a'zo guruhda yozish uchun 5 ta odam qo'shishi shart bo'ladi.\n"
            f"├ `/odam 10` — Talabni 10 taga oshirish.\n"
            f"└ `/odam 0` — Cheklovni butunlay o'chirish (hammaga ruxsat).",
            parse_mode="Markdown",
        )
        return

    count = int(parts[1])
    await db.set_min_invites(message.chat.id, count)

    if count > 0:
        await message.reply(
            f"╔═══════════════════════════════════════╗\n"
            f"   👥 **MAJBURIY TAKLIF TALABI O'RNATILDI** ✅\n"
            f"╚═══════════════════════════════════════╝\n\n"
            f"🎯 Yangi talab: **{count} ta odam qo'shish shart!**\n\n"
            f"├ 📌 Endi oddiy a'zolar guruhda yozishlari uchun kamida **{count}** ta do'stini taklif qilishlari shart.\n"
            f"├ 🚫 A'zo qo'shmaganlarning xabarlari avtomatik o'chiriladi va ogohlantirish yuboriladi.\n"
            f"└ 👮‍♂️ Admin: {get_admin_name(message)}\n\n"
            f"📊 Takliflarni ko'rish: `/takliflarim` | Reyting: `/toptaklif`",
            parse_mode="Markdown",
        )
    else:
        await message.reply(
            f"╔═══════════════════════════════════════╗\n"
            f"   🔓 **MAJBURIY TAKLIF TALABI O'CHIRILDI** 🔓\n"
            f"╚═══════════════════════════════════════╝\n\n"
            f"✅ Endi barcha guruh a'zolari erkin muloqot qilishi mumkin.\n\n"
            f"👮‍♂️ Admin: {get_admin_name(message)}",
            parse_mode="Markdown",
        )


# ── /nol [A'zo qo'shgan odamlarni nol qilish] ──────────────────────────
@router.message(Command("nol", "resetinvites", "nolga", "taklifnol", ignore_case=True))
async def cmd_reset_invites(message: Message, bot: Bot) -> None:
    if message.chat.type in ("private",):
        await message.reply("⚠️ Ushbu buyruq faqat guruhlarda ishlaydi!")
        return

    user_id = message.from_user.id if message.from_user else None
    if not await is_admin(bot, message.chat.id, user_id, message=message):
        await message.reply("❌ Bu buyruq faqat guruh administratorlari uchun!")
        return

    parts = (message.text or "").split()

    # Agar barcha a'zolarning takliflarini birdaniga nol qilish so'ralsa: /nol all yoki /nol hammasi
    if len(parts) > 1 and parts[1].lower() in ("all", "hammasi", "barchasi", "hamma"):
        deleted = await db.reset_all_group_invites(message.chat.id)
        group = await db.get_or_create_group(message.chat.id)
        min_inv = group.get("min_invites", 0)
        inv_note = (
            f"\n\n⚠️ Guruhda yozish uchun kamida **{min_inv}** ta odam qo'shish talabi o'rnatilgan. "
            f"Endi barcha a'zolar qaytadan odam qo'shishi shart!"
            if min_inv > 0 and group.get("invites_enabled", 1) == 1
            else ""
        )
        await message.reply(
            f"╔═══════════════════════════════════╗\n"
            f"   0️⃣ **BARCHA TAKLIFLAR NOLGA TUSHIRILDI** 0️⃣\n"
            f"╚═══════════════════════════════════╝\n\n"
            f"📊 Jami o'chirilgan taklif qaydlari: **{deleted}** ta.{inv_note}\n\n"
            f"👮‍♂️ Admin: {get_admin_name(message)}",
            parse_mode="Markdown",
        )
        return

    # Muayyan a'zoni reply yoki @username / ID orqali aniqlash
    target = await resolve_target(message)
    if target.error:
        await message.reply(
            "0️⃣ **A'zo takliflarini nol qilish (/nol):**\n\n"
            "Foydalanuvchi guruhga qancha odam qo'shgan bo'lsa, uning hisobini 0 ga tushiradi.\n"
            "Agar guruhda majburiy odam qo'shish talabi bo'lsa, u qaytadan odam qo'shishi kerak bo'ladi.\n\n"
            "**Qanday ishlatiladi:**\n"
            "• Foydalanuvchining xabariga **Reply** qilib: `/nol`\n"
            "• Yoki `@username` orqali: `/nol @foydalanuvchi`\n"
            "• Yoki Telegram **ID** orqali: `/nol 123456789`\n"
            "• Barcha a'zolarnikini birdaniga nol qilish: `/nol hammasi`",
            parse_mode="Markdown",
        )
        return

    if target.user_id == get_bot_id(bot):
        await message.reply("🤖 Bot uchun takliflar hisoblanmaydi!")
        return

    # Oldingi takliflar sonini aniqlash
    old_invites = await db.get_user_invites(message.chat.id, target.user_id)

    # Bazadan takliflarni tozalash (0 qilish)
    await db.reset_user_invites(message.chat.id, target.user_id)

    # Guruhning majburiy taklif sozlamasini olish
    group = await db.get_or_create_group(message.chat.id)
    min_inv = group.get("min_invites", 0)
    inv_enabled = group.get("invites_enabled", 1)

    mention = f"[{target.full_name}](tg://user?id={target.user_id})"

    target_is_admin = await is_admin(bot, message.chat.id, target.user_id)
    if target_is_admin:
        extra_note = (
            "ℹ️ _Eslatma: Ushbu a'zo guruh admini bo'lganligi sababli, "
            "unga majburiy a'zo qo'shish cheklovi ta'sir qilmaydi._"
        )
    elif inv_enabled == 1 and min_inv > 0:
        extra_note = (
            f"🚫 **Diqqat:** Guruhda yozish uchun kamida **{min_inv}** ta odam qo'shish talabi mavjud.\n"
            f"Endi {mention} guruhda xabar yoza olishi uchun yana kamida **{min_inv}** ta yangi odam qo'shishi shart!"
        )
    else:
        extra_note = "ℹ️ Ushbu a'zoning barcha takliflari 0 ga tushirildi."

    await message.reply(
        f"╔═══════════════════════════════════╗\n"
        f"   0️⃣ **TAKLIFLAR NOLGA TUSHIRILDI** 0️⃣\n"
        f"╚═══════════════════════════════════╝\n\n"
        f"👤 **A'zo:** {mention}\n"
        f"📊 **Oldingi qo'shgan odamlari:** **{old_invites}** ta\n"
        f"🔄 **Hozirgi takliflar:** **0** ta\n\n"
        f"{extra_note}\n\n"
        f"👮‍♂️ Admin: {get_admin_name(message)}",
        parse_mode="Markdown",
    )


# ── /kanal [@ yoki id orqali majburiy kanal va guruhlar] ───────────
@router.message(Command("kanal", "kanallar", "channel", "channels", ignore_case=True))
async def cmd_kanal(message: Message, bot: Bot) -> None:
    if message.chat.type in ("private",):
        await message.reply("⚠️ Ushbu buyruq faqat guruhlarda adminlar uchun ishlaydi!")
        return

    user_id = message.from_user.id if message.from_user else None
    if not await is_admin(bot, message.chat.id, user_id, message=message):
        await message.reply("❌ Bu buyruq faqat guruh administratorlari uchun!")
        return

    parts = (message.text or "").split()

    # 1. /kanal (argumentlarsiz) — hozirgi majburiy kanallar ro'yxati
    if len(parts) == 1:
        channels = await db.get_mandatory_channels(message.chat.id)
        if not channels:
            await message.reply(
                f"╔═══════════════════════════════════════╗\n"
                f"   📢 **HOMIY KANALLAR BOSHQARUVI** 📢\n"
                f"╚═══════════════════════════════════════╝\n\n"
                f"Guruhda hozircha majburiy homiy kanallar belgilanmagan.\n\n"
                f"💡 **Yangi kanal qo'shish usullari:**\n"
                f"├ `/kanal @kanal_username`\n"
                f"├ `/kanal -1001234567890` (Kanal yoki Guruh ID si)\n"
                f"├ `/kanal https://t.me/kanal_nomi`\n"
                f"└ Maxsus havola bilan: `/kanal -1001234567890 https://t.me/+AbCdEf`\n\n"
                f"ℹ️ *Kanal qo'shilgach, a'zolar unga a'zo bo'lmaguncha (yoki ariza yubormaguncha) guruhga yuborgan xabarlari avtomatik o'chiriladi.*",
                parse_mode="Markdown",
            )
            return

        text = (
            f"╔═══════════════════════════════════════╗\n"
            f"   📢 **MAJBURIY HOMIY KANALLAR RO'YXATI** 📢\n"
            f"╚═══════════════════════════════════════╝\n\n"
            f"📍 Guruh: «{message.chat.title}»\n\n"
        )
        for idx, ch in enumerate(channels, 1):
            title = ch.get("title") or ch.get("channel_id")
            chid = ch.get("channel_id")
            link = ch.get("invite_link") or (f"https://t.me/{chid.lstrip('@')}" if str(chid).startswith("@") else "")
            prefix = "└" if idx == len(channels) else "├"
            if link:
                text += f"{prefix} {idx}. **[{title}]({link})** (`{chid}`)\n"
            else:
                text += f"{prefix} {idx}. **{title}** (`{chid}`)\n"

        text += (
            f"\n📊 Jami: **{len(channels)}** ta homiy kanal\n\n"
            f"➕ **Kanal qo'shish:** `/kanal @kanal_nomi`\n"
            f"➖ **Kanalni o'chirish:** `/kanal ochir @kanal_nomi`\n"
            f"🗑 **Barchasini tozalash:** `/kanal tozalash`"
        )
        await message.reply(text, parse_mode="Markdown", disable_web_page_preview=True)
        return

    sub_cmd = parts[1].strip().lower()

    # 2. Barchasini tozalash: /kanal tozalash
    if sub_cmd in ("tozalash", "clear", "hammasini_ochir"):
        await db.clear_mandatory_channels(message.chat.id)
        await message.reply(
            f"╔═══════════════════════════════════════╗\n"
            f"   🗑 **HOMIY KANALLAR TOZALANDI** 🗑\n"
            f"╚═══════════════════════════════════════╝\n\n"
            f"✅ Guruhning barcha majburiy kanallari muvaffaqiyatli o'chirildi.\n"
            f"Endi a'zolar obuna bo'lmasdan ham erkin yoza oladi.\n\n"
            f"👮‍♂️ Admin: {get_admin_name(message)}",
            parse_mode="Markdown",
        )
        return

    # 3. Muayyan kanalni o'chirish: /kanal ochir @kanalim
    if sub_cmd in ("ochir", "del", "delete", "remove", "ochirish"):
        if len(parts) < 3:
            await message.reply("⚠️ Qaysi kanalni o'chirmoqchisiz?\nMasalan: `/kanal ochir @kanalim`", parse_mode="Markdown")
            return
        target_ch = parts[2].strip()
        removed = await db.remove_mandatory_channel(message.chat.id, target_ch)
        if removed:
            await message.reply(f"✅ **{target_ch}** majburiy kanallar ro'yxatidan o'chirildi!", parse_mode="Markdown")
        else:
            await message.reply(f"❌ **{target_ch}** ro'yxatda topilmadi.", parse_mode="Markdown")
        return

    # 4. Yangi kanal qo'shish: /kanal @kanalim yoki /kanal -100...
    raw_input = parts[1].strip()
    custom_invite_link = parts[2].strip() if len(parts) > 2 and parts[2].startswith("http") else ""

    chat_target: int | str = raw_input
    # Link kiritilgan bo'lsa username ajratib olish
    if "t.me/" in raw_input and not raw_input.startswith("https://t.me/+"):
        username = raw_input.split("t.me/")[1].split("/")[0].split("?")[0]
        chat_target = f"@{username}"
    elif raw_input.startswith("-100") or (raw_input.startswith("-") and raw_input[1:].isdigit()):
        chat_target = int(raw_input)

    status_msg = await message.reply("⏳ Kanal ma'lumotlari tekshirilmoqda...")

    try:
        chat_obj = await bot.get_chat(chat_target)
        channel_id = f"@{chat_obj.username}" if chat_obj.username else str(chat_obj.id)
        title = chat_obj.title or channel_id

        invite_link = custom_invite_link
        if not invite_link:
            if chat_obj.username:
                invite_link = f"https://t.me/{chat_obj.username}"
            elif getattr(chat_obj, "invite_link", None):
                invite_link = chat_obj.invite_link
            else:
                try:
                    invite_link = await bot.export_chat_invite_link(chat_obj.id)
                except Exception:
                    invite_link = f"https://t.me/c/{str(chat_obj.id).replace('-100', '')}"

        # Bot ushbu kanalda adminmi?
        bot_is_admin = False
        try:
            me = await bot.get_me()
            cm = await bot.get_chat_member(chat_obj.id, me.id)
            bot_is_admin = cm.status in ("creator", "administrator")
        except Exception:
            bot_is_admin = False

        # Bazaga saqlash
        await db.add_mandatory_channel(message.chat.id, channel_id, title=title, invite_link=invite_link)

        admin_status_text = (
            "✅ **Bot kanalda administrator ekanligi tasdiqlandi!** (A'zolik va arizalar 24/7 avtomatik tekshiriladi)"
            if bot_is_admin
            else "⚠️ **DIQQAT (Muhim!):** Bot ushbu kanalda administrator emas!\n"
                 "Bot a'zolikni va arizalarni tekshira olishi uchun botni ushbu kanalga **Administrator (Admin)** qilib tayinlashingiz shart!"
        )

        await status_msg.edit_text(
            f"╔═══════════════════════════════════════╗\n"
            f"   📢 **HOMIY KANAL QO'SHILDI** ✅\n"
            f"╚═══════════════════════════════════════╝\n\n"
            f"├ 📢 **Kanal:** [{title}]({invite_link}) (`{channel_id}`)\n"
            f"└ 🤖 **Bot maqomi:** {'✅ Administrator' if bot_is_admin else '⚠️ Administrator emas'}\n\n"
            f"{admin_status_text}\n\n"
            f"📌 Endi guruh a'zolari ushbu kanalga a'zo bo'lmaguncha (yoki ariza yubormaguncha) guruhda yoza olishmaydi.",
            parse_mode="Markdown",
            disable_web_page_preview=True,
        )
    except Exception as e:
        channel_id = str(raw_input)
        title = channel_id
        invite_link = custom_invite_link or (f"https://t.me/{channel_id.lstrip('@')}" if channel_id.startswith("@") else "")

        await db.add_mandatory_channel(message.chat.id, channel_id, title=title, invite_link=invite_link)

        await status_msg.edit_text(
            f"╔═══════════════════════════════════════╗\n"
            f"   ⚠️ **KANAL RO'YXATGA QO'SHILDI** ⚠️\n"
            f"╚═══════════════════════════════════════╝\n\n"
            f"📍 Identifikator: `{channel_id}`\n\n"
            f"❗ **Eslatma:** Bot kanal a'zolarini va yuborilgan arizalarni tekshira olishi uchun botni ushbu kanalga **Administrator** qilib qo'shishingiz shart!",
            parse_mode="Markdown",
        )



# ── /chekla [ relp 10m|2h|1d] ──────────────────────────────────────
@router.message(Command("chekla", "yopish", "mute", ignore_case=True))
async def cmd_mute(message: Message, bot: Bot) -> None:
    if message.chat.type in ("private",):
        await message.reply("⚠️ Bu buyruq faqat guruhlarda ishlaydi!")
        return

    user_id = message.from_user.id if message.from_user else None
    if not await is_admin(bot, message.chat.id, user_id, message=message):
        await message.reply("❌ Bu buyruq faqat guruh administratorlari uchun!")
        return

    target = await resolve_target(message)
    if target.error:
        await message.reply(
            "🔇 **Foydalanuvchini yozishdan cheklash:**\n\n"
            "Format:\n"
            "• Xabarga **Reply** qilib: `/chekla 10m [sabab]`\n"
            "• Yoki `@username` orqali: `/chekla @foydalanuvchi 2h [sabab]`\n\n"
            "Vaqt turlari:\n"
            "• `10m` — 10 daqiqa\n"
            "• `2h` — 2 soat\n"
            "• `1d` — 1 kun",
            parse_mode="Markdown",
        )
        return

    if target.user_id == get_bot_id(bot) or await is_admin(bot, message.chat.id, target.user_id):
        await message.reply("❌ Bot yoki guruh adminini cheklab bo'lmaydi!")
        return

    # Muddat va sababni aniqlash
    delta, duration_str = parse_duration(target.remaining_text)
    if not delta:
        delta = timedelta(seconds=DEFAULT_MUTE_SECONDS)
        duration_str = "1h"

    # Vaqt tegi o'chirilganidan keyingi qolgan qism sabab bo'ladi
    reason_clean = re.sub(r"\b\d+[mhd]\b", "", target.remaining_text, flags=re.IGNORECASE).strip()
    reason = reason_clean or "Guruh qoidalarini buzganlik"

    until_date = datetime.now(timezone.utc) + delta

    try:
        await bot.restrict_chat_member(
            chat_id=message.chat.id,
            user_id=target.user_id,
            permissions=ChatPermissions(can_send_messages=False),
            until_date=until_date,
        )
        await db.record_punishment(message.chat.id, "mute")
        await message.reply(
            f"╔═══════════════════════════════════╗\n"
            f"   🔇 **YOZISHDAN CHEKLANDI (MUTE)** 🔇\n"
            f"╚═══════════════════════════════════╝\n\n"
            f"👤 **Foydalanuvchi:** {target.full_name}\n"
            f"⏳ **Muddat:** **{duration_str}**\n"
            f"📝 **Sabab:** {reason}\n"
            f"👮‍♂️ **Admin:** {get_admin_name(message)}",
            parse_mode="Markdown",
        )
    except Exception as e:
        await message.reply(f"❌ Xatolik yuz berdi: {e}\n(Bot guruhda admin ekanligiga va 'Restrict members' huquqi borligiga ishonch hosil qiling).")


# ── /hayda [bloklash @ id yoki relp] ─────────────────────────────────
@router.message(Command("hayda", "haydash", "ban", ignore_case=True))
async def cmd_ban(message: Message, bot: Bot) -> None:
    if message.chat.type in ("private",):
        await message.reply("⚠️ Bu buyruq faqat guruhlarda ishlaydi!")
        return

    user_id = message.from_user.id if message.from_user else None
    if not await is_admin(bot, message.chat.id, user_id, message=message):
        await message.reply("❌ Bu buyruq faqat guruh administratorlari uchun!")
        return

    target = await resolve_target(message)
    if target.error:
        await message.reply(
            "🚫 **Guruhdan chiqarish (Ban):**\n\n"
            "Format:\n"
            "• Foydalanuvchi xabariga **Reply** qilib: `/hayda [sabab]`\n"
            "• Yoki `@username` orqali: `/hayda @foydalanuvchi [sabab]`\n"
            "• Yoki Telegram **ID** orqali: `/hayda 123456789 [sabab]`",
            parse_mode="Markdown",
        )
        return

    if target.user_id == get_bot_id(bot) or await is_admin(bot, message.chat.id, target.user_id):
        await message.reply("❌ Bot yoki guruh adminini ban qilib bo'lmaydi!")
        return

    reason = target.remaining_text.strip() or "Guruhdan chetlatildi"

    try:
        await bot.ban_chat_member(chat_id=message.chat.id, user_id=target.user_id)
        await db.record_punishment(message.chat.id, "ban")
        await message.reply(
            f"╔═══════════════════════════════════╗\n"
            f"   🚫 **GURUHDAN CHIQARILDI (BAN)** 🚫\n"
            f"╚═══════════════════════════════════╝\n\n"
            f"👤 **Foydalanuvchi:** {target.full_name}\n"
            f"📝 **Sabab:** {reason}\n"
            f"⚡️ **Holat:** Guruhdan chiqarildi va bloklandi\n"
            f"👮‍♂️ **Admin:** {get_admin_name(message)}",
            parse_mode="Markdown",
        )
    except Exception as e:
        await message.reply(f"❌ Ban qilishda xatolik: {e}")


# Helper: xabarlarni guruhlab (chunk) tez va xavfsiz o'chirish
async def delete_in_batches(bot: Bot, chat_id: int, msg_ids: list[int]) -> int:
    deleted = 0
    unique_ids = sorted(list(set(msg_ids)), reverse=True)
    for i in range(0, len(unique_ids), 100):
        chunk = unique_ids[i : i + 100]
        try:
            await bot.delete_messages(chat_id=chat_id, message_ids=chunk)
            deleted += len(chunk)
        except Exception:
            for mid in chunk:
                try:
                    await bot.delete_message(chat_id=chat_id, message_id=mid)
                    deleted += 1
                except Exception:
                    pass
    return deleted


def get_cleaner_keyboard(group: dict) -> InlineKeyboardMarkup:
    enabled = group.get("auto_clean_enabled", 1) == 1
    interval = group.get("auto_clean_interval", "24soat")

    on_text = "ON ✅" if enabled else "ON"
    off_text = "OFF" if enabled else "OFF ❌"

    t24 = "⏰ 24soat ✅" if interval == "24soat" else "⏰ 24soat"
    t7d = "🗓 1 hafta ✅" if interval in ("7kun", "1hafta") else "1 hafta"
    t30d = "📅 1 oy ✅" if interval in ("30kun", "1oy") else "1 oy"

    kb = [
        [
            InlineKeyboardButton(text=on_text, callback_data="cleaner_on"),
            InlineKeyboardButton(text=off_text, callback_data="cleaner_off"),
        ],
        [
            InlineKeyboardButton(text=t24, callback_data="cleaner_time_24soat"),
            InlineKeyboardButton(text=t7d, callback_data="cleaner_time_1hafta"),
            InlineKeyboardButton(text=t30d, callback_data="cleaner_time_1oy"),
        ],
        [
            InlineKeyboardButton(text="🧹 Hozir tozalash (50 ta)", callback_data="cleaner_clean_50"),
            InlineKeyboardButton(text="🗑 To'liq tozalash (100 ta)", callback_data="cleaner_clean_100"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


# ── /tozala [Guruhni tozalash: chiroyli progress bar va boshqaruv] ──────
@router.message(Command("tozala", "tozalash", "clear", ignore_case=True))
async def cmd_clear(message: Message, bot: Bot) -> None:
    if message.chat.type in ("private",):
        await message.reply("⚠️ Bu buyruq faqat guruhlarda ishlaydi!")
        return

    user_id = message.from_user.id if message.from_user else None
    if not await is_admin(bot, message.chat.id, user_id, message=message):
        await message.reply("❌ Bu buyruq faqat guruh administratorlari uchun!")
        return

    # Adminning /tozala buyruq xabarini o'chirish
    try:
        await message.delete()
    except Exception:
        pass

    group = await db.get_or_create_group(message.chat.id, message.chat.title or "")
    parts = (message.text or "").split()
    custom_count: int | None = None
    if len(parts) > 1 and parts[1].isdigit():
        custom_count = min(int(parts[1]), 200)

    # 1. AGAR A'ZOGA REPLY QILIB TOZALASH SO'RALSA
    if message.reply_to_message:
        target_user = message.reply_to_message.from_user
        target_name = target_user.full_name if target_user else "Foydalanuvchi"
        target_id = target_user.id if target_user else None

        limit = custom_count if custom_count else 100

        # Animatsion progress xabari
        prog_msg = await bot.send_message(
            chat_id=message.chat.id,
            text=(
                f"👥 **GURUH tozalanmoqda...**\n\n"
                f"⏳ (taxminan 3 soniya)\n\n"
                f"🗑 **A'zo xabarlari:**  ▓▓▓▓▓▓▓▓░░ 80%\n"
                f"🚫 **Reklama, Link:**   ▓▓▓▓▓▓▓░░░ 75%\n"
                f"⚠️ **Nojo'ya so'z:**     ▓▓▓▓▓▓▓▓░░ 85%"
            ),
            parse_mode="Markdown",
        )

        msg_ids = set()
        msg_ids.add(message.reply_to_message.message_id)
        if target_id:
            saved_ids = await db.get_user_chat_messages(message.chat.id, target_id, limit=limit)
            msg_ids.update(saved_ids)

        await asyncio.sleep(1.0)
        deleted = await delete_in_batches(bot, message.chat.id, list(msg_ids))
        if target_id:
            await db.delete_saved_chat_messages(message.chat.id, list(msg_ids))

        final_text = (
            f"✨ **GURUH MUVAFFAQIYATLI TOZALANDI!** 🧹\n\n"
            f"👤 **A'zo:** [{target_name}](tg://user?id={target_id})\n\n"
            f"🗑 **A'zo xabarlari:**  ▓▓▓▓▓▓▓▓▓▓ 100% ✅\n"
            f"🚫 **Reklama, Link:**   ▓▓▓▓▓▓▓▓▓▓ 100% ✅\n"
            f"⚠️ **Nojo'ya so'z:**     ▓▓▓▓▓▓▓▓▓▓ 100% ✅\n\n"
            f"📊 Jami **{deleted} ta xabar** tozalandi!\n"
            f"👮‍♂️ Admin: {get_admin_name(message)}"
        )
        try:
            await prog_msg.edit_text(final_text, parse_mode="Markdown")
        except Exception:
            prog_msg = await bot.send_message(chat_id=message.chat.id, text=final_text, parse_mode="Markdown")

        asyncio.create_task(auto_delete_message(prog_msg, AUTO_DELETE_NOTIFICATION_DELAY))
        return

    # 2. AGAR PARAMETRSIZ YOZILSA — STANDART OXIRGI 30 TA XABARNI TOZALASH
    if not custom_count:
        custom_count = 30

    # 3. ANIMATSION TOZALASH VA XABARLARNI HAQIQATDA O'CHIRISH
    await run_animated_cleanup(bot, message.chat.id, message.message_id, custom_count, get_admin_name(message))


# ── /tozalash_paneli [Avto-tozalash sozlamalari menyusi] ─────────────
@router.message(Command("tozalash_paneli", "autoclean", ignore_case=True))
async def cmd_cleaner_panel(message: Message, bot: Bot) -> None:
    if message.chat.type in ("private",):
        return
    user_id = message.from_user.id if message.from_user else None
    if not await is_admin(bot, message.chat.id, user_id, message=message):
        return
    group = await db.get_or_create_group(message.chat.id, message.chat.title or "")
    panel_text = (
        f"⚙️ **'{message.chat.title}' — Avto-tozalash boshqaruvi:**\n\n"
        f"Quyidagi tugmalar orqali xabarlarni davriy tozalash rejimini yoqing yoki o'chiring:"
    )
    kb = get_cleaner_keyboard(group)
    panel_msg = await bot.send_message(
        chat_id=message.chat.id,
        text=panel_text,
        reply_markup=kb,
        parse_mode="Markdown",
    )
    asyncio.create_task(auto_delete_message(panel_msg, 60))


async def run_animated_cleanup(bot: Bot, chat_id: int, current_msg_id: int, count: int, admin_name: str) -> None:
    step1_text = (
        f"🧹 **Guruh xabarlari tozalanmoqda...**\n\n"
        f"⏳ Oxirgi **{count} ta** xabar tekshirilmoqda va o'chirilmoqda...\n\n"
        f"🗑 **Kirdi-Chiqdi:**  ▓▓▓▓▓▓▓▓░░ 85%\n"
        f"🚫 **Reklama, Link:** ▓▓▓▓▓▓▓░░░ 75%\n"
        f"⚠️ **Nojo'ya so'z:**   ▓▓▓▓▓▓▓▓░░ 85%\n"
        f"🦠 **Zararli fayllar:** ▓▓▓▓▓▓▓▓▓░ 95%"
    )
    msg = await bot.send_message(chat_id=chat_id, text=step1_text, parse_mode="Markdown")

    # Bazada qayd etilgan ID lar va ketma-ket ID larni to'plash
    db_ids = await db.get_recent_chat_message_ids(chat_id, limit=count)
    seq_ids = [current_msg_id - i for i in range(1, count + 1) if current_msg_id - i > 0]
    all_msg_ids = list(set(db_ids + seq_ids))

    await asyncio.sleep(0.8)

    deleted = await delete_in_batches(bot, chat_id, all_msg_ids)
    await db.delete_saved_chat_messages(chat_id, all_msg_ids)

    final_text = (
        f"✨ **GURUH MUVAFFAQIYATLI TOZALANDI!** 🧹\n\n"
        f"🗑 **Kirdi-Chiqdi:**  ▓▓▓▓▓▓▓▓▓▓ 100% ✅\n"
        f"🚫 **Reklama, Link:** ▓▓▓▓▓▓▓▓▓▓ 100% ✅\n"
        f"⚠️ **Nojo'ya so'z:**   ▓▓▓▓▓▓▓▓▓▓ 100% ✅\n"
        f"🦠 **Zararli fayllar:** ▓▓▓▓▓▓▓▓▓▓ 100% ✅\n\n"
        f"📊 **Haqiqatda o'chirilgan xabarlar:** **{deleted}** ta\n"
        f"👮‍♂️ **Admin:** {admin_name}"
    )

    try:
        await msg.edit_text(final_text, parse_mode="Markdown")
    except Exception:
        pass

    # Muvaffaqiyat bildirishnomasi 6 soniyadan so'ng avtomatik tozalanadi
    asyncio.create_task(auto_delete_message(msg, 6))


# ── Callbacklar: Avto-tozalash ON / OFF va vaqt tanlash ─────────────
@router.callback_query(F.data.in_({"cleaner_on", "cleaner_off"}))
async def cb_cleaner_toggle(call: CallbackQuery, bot: Bot) -> None:
    if not call.message or not call.from_user:
        return
    if not await is_admin(bot, call.message.chat.id, call.from_user.id):
        await call.answer("❌ Faqat guruh adminlari uchun!", show_alert=True)
        return

    new_val = 1 if call.data == "cleaner_on" else 0
    await db.set_auto_clean(call.message.chat.id, enabled=new_val)
    group = await db.get_or_create_group(call.message.chat.id)
    kb = get_cleaner_keyboard(group)

    status_str = "YOQILDI ✅" if new_val == 1 else "O'CHIRILDI ❌"
    await call.answer(f"Avto-tozalash {status_str}")

    try:
        await call.message.edit_reply_markup(reply_markup=kb)
    except Exception:
        pass


@router.callback_query(F.data.startswith("cleaner_time_"))
async def cb_cleaner_time(call: CallbackQuery, bot: Bot) -> None:
    if not call.message or not call.from_user:
        return
    if not await is_admin(bot, call.message.chat.id, call.from_user.id):
        await call.answer("❌ Faqat guruh adminlari uchun!", show_alert=True)
        return

    time_val = call.data.replace("cleaner_time_", "")
    await db.set_auto_clean(call.message.chat.id, interval=time_val)
    group = await db.get_or_create_group(call.message.chat.id)
    kb = get_cleaner_keyboard(group)

    await call.answer(f"Davriylik belgilandi: {time_val} ⏰")

    try:
        await call.message.edit_reply_markup(reply_markup=kb)
    except Exception:
        pass


@router.callback_query(F.data.in_({"cleaner_clean_50", "cleaner_clean_100"}))
async def cb_cleaner_clean_now(call: CallbackQuery, bot: Bot) -> None:
    if not call.message or not call.from_user:
        return
    if not await is_admin(bot, call.message.chat.id, call.from_user.id):
        await call.answer("❌ Faqat guruh adminlari uchun!", show_alert=True)
        return

    count = 50 if call.data == "cleaner_clean_50" else 100
    await call.answer("Tozalash boshlandi... 🧹")

    try:
        await call.message.delete()
    except Exception:
        pass

    await run_animated_cleanup(bot, call.message.chat.id, call.message.message_id, count, call.from_user.full_name)



# ── /sozlamalar [Himoya sozlamalarini boshqarish] ───────────────────
def get_settings_keyboard(group: dict) -> InlineKeyboardMarkup:
    def mark(val: int) -> str:
        return "✅ Yoqilgan" if val == 1 else "❌ O'chirilgan"

    def mark_block(val: int) -> str:
        return "🚫 Taqiqlangan" if val == 1 else "🟢 Ruxsat"

    min_inv = group.get("min_invites", 0)
    inv_text = f"👥 Majburiy a'zo ({min_inv} ta): {mark(group.get('invites_enabled', 1))}"

    kb = [
        [
            InlineKeyboardButton(
                text=f"🤬 So'kinish filtri: {mark(group.get('profanity_enabled', 1))}",
                callback_data="toggle_profanity",
            )
        ],
        [
            InlineKeyboardButton(
                text=f"🎭 Stiker va GIF: {mark_block(group.get('block_stickers', 0))}",
                callback_data="toggle_block_stickers",
            )
        ],
        [
            InlineKeyboardButton(
                text=f"🎙 Ovozli va Video doira: {mark_block(group.get('block_voice', 0))}",
                callback_data="toggle_block_voice",
            )
        ],
        [
            InlineKeyboardButton(
                text=f"🔗 Begona linklar: {mark(group.get('antilink_enabled', 1))}",
                callback_data="toggle_antilink",
            )
        ],
        [
            InlineKeyboardButton(
                text=f"🛡️ Antispam/Reklama: {mark(group.get('antispam_enabled', 1))}",
                callback_data="toggle_antispam",
            )
        ],
        [
            InlineKeyboardButton(
                text=f"🔄 Forward xabarlar: {mark(group.get('antiforward_enabled', 1))}",
                callback_data="toggle_antiforward",
            )
        ],
        [
            InlineKeyboardButton(
                text=f"📢 Majburiy kanallar: {mark(group.get('channels_enabled', 1))}",
                callback_data="toggle_channels",
            )
        ],
        [
            InlineKeyboardButton(
                text=f"📥 Zayafkalarni avto-qabul: {mark(group.get('auto_approve_joins', 1))}",
                callback_data="toggle_auto_approve",
            )
        ],
        [
            InlineKeyboardButton(
                text=f"🌙 Tungi rejim ({group.get('night_mode_start', '23:00')}-{group.get('night_mode_end', '07:00')}): {mark(group.get('night_mode_enabled', 0))}",
                callback_data="toggle_night_mode",
            )
        ],
        [
            InlineKeyboardButton(
                text=f"⚡️ Anti-Flood (Spam oqimi): {mark(group.get('anti_flood_enabled', 1))}",
                callback_data="toggle_anti_flood",
            )
        ],
        [
            InlineKeyboardButton(
                text=f"🈲 Arab/Raid spambot filtri: {mark(group.get('anti_arabic_enabled', 0))}",
                callback_data="toggle_anti_arabic",
            )
        ],
        [
            InlineKeyboardButton(
                text=f"🤖 Inline botlar: {mark_block(group.get('anti_inline_bot', 0))}",
                callback_data="toggle_anti_inline_bot",
            )
        ],
        [
            InlineKeyboardButton(
                text=inv_text,
                callback_data="toggle_invites",
            )
        ],
        [
            InlineKeyboardButton(
                text=f"👋 Kutib olish: {mark(group.get('welcome_enabled', 1))}",
                callback_data="toggle_welcome",
            )
        ],
        [
            InlineKeyboardButton(
                text=f"⏰ Rejali xabarlar: {mark(group.get('scheduled_enabled', 1))}",
                callback_data="toggle_scheduled",
            )
        ],
        [InlineKeyboardButton(text="🔄 Yangilash", callback_data="refresh_settings")],
    ]
    return InlineKeyboardMarkup(inline_keyboard=kb)


@router.message(Command("sozlamalar", "settings", ignore_case=True))
async def cmd_settings(message: Message, bot: Bot) -> None:
    if message.chat.type in ("private",):
        await message.reply("⚠️ Sozlamalar faqat guruhlarda adminlar uchun ochiladi.")
        return

    user_id = message.from_user.id if message.from_user else None
    if not await is_admin(bot, message.chat.id, user_id, message=message):
        await message.reply("❌ Bu buyruq faqat guruh administratorlari uchun!")
        return

    group = await db.get_or_create_group(message.chat.id, message.chat.title or "")
    kb = get_settings_keyboard(group)
    await message.reply(
        f"╔═══════════════════════════════════════╗\n"
        f"   ⚙️ **HIMOYA VA XAVFSIZLIK SOZLAMALARI** 🛡\n"
        f"╚═══════════════════════════════════════╝\n\n"
        f"📍 **Guruh:** «{message.chat.title}»\n\n"
        f"Quyidagi interaktiv tugmalar orqali botning xavfsizlik va nazorat funksiyalarini boshqaring:",
        reply_markup=kb,
        parse_mode="Markdown",
    )


@router.callback_query(F.data.startswith("toggle_"))
async def callback_toggle_setting(call: CallbackQuery, bot: Bot) -> None:
    if not call.message or not call.from_user:
        return

    if not await is_admin(bot, call.message.chat.id, call.from_user.id):
        await call.answer("❌ Bu sozlamalarni faqat adminlar o'zgartirishi mumkin!", show_alert=True)
        return

    raw = call.data.replace("toggle_", "")
    group = await db.get_or_create_group(call.message.chat.id)

    if raw in ("block_stickers", "block_voice", "anti_inline_bot"):
        setting_key = raw
        current_val = group.get(setting_key, 0)
    elif raw == "auto_approve":
        setting_key = "auto_approve_joins"
        current_val = group.get(setting_key, 1)
    elif raw in ("night_mode", "anti_flood", "anti_arabic"):
        setting_key = raw + "_enabled"
        current_val = group.get(setting_key, 0 if raw != "anti_flood" else 1)
    else:
        setting_key = raw + "_enabled"
        current_val = group.get(setting_key, 1)

    new_val = 0 if current_val == 1 else 1

    await db.update_group_setting(call.message.chat.id, setting_key, new_val)
    group[setting_key] = new_val

    await call.message.edit_reply_markup(reply_markup=get_settings_keyboard(group))
    await call.answer("Sozlama yangilandi! ✅")


@router.callback_query(F.data == "refresh_settings")
async def callback_refresh_settings(call: CallbackQuery, bot: Bot) -> None:
    if not call.message:
        return
    group = await db.get_or_create_group(call.message.chat.id)
    await call.message.edit_reply_markup(reply_markup=get_settings_keyboard(group))
    await call.answer("Yangilandi! 🔄")


# ── /zayafka [Guruh va kanallarga qo'shilish arizalarini avtomatik qabul qilish] ──
@router.message(Command("zayafka", "zayafkalar", "autoapprove", ignore_case=True))
async def cmd_auto_approve_joins(message: Message, bot: Bot) -> None:
    if message.chat.type in ("private",):
        await message.reply(
            f"╔═══════════════════════════════════════╗\n"
            f"   📥 **AVTO-ZAYAFKA QABUL TIZIMI** 🚀\n"
            f"╚═══════════════════════════════════════╝\n\n"
            f"Ushbu funksiya orqali bot guruhingiz yoki kanalingizga qo'shilish so'rovi (Join Request) yuborgan a'zolarni **1 soniyada avtomatik qabul qiladi**!\n\n"
            f"🔹 **Guruh uchun sozlash:**\n"
            f"├ 1. Botni guruhingizga qo'shib, Administrator qiling.\n"
            f"├ 2. Unga «A'zolarni taklif qilish» (Invite Users) huquqini bering.\n"
            f"└ 3. Guruh ichida `/zayafka on` deb yozing.\n\n"
            f"🔹 **Kanal uchun sozlash:**\n"
            f"├ 1. Botni kanalingizga Administrator qilib qo'shing.\n"
            f"├ 2. Unga «A'zolarni taklif qilish» (Invite Users) huquqini bering.\n"
            f"├ 3. Kanalingizda «Arizalarni tasdiqlash» yoqilgan taklif havolasi yarating.\n"
            f"└ 4. Bot barcha arizalarni avtomatik tasdiqlaydi va a'zoga VIP salomnoma yuboradi!",
            parse_mode="Markdown",
        )
        return

    user_id = message.from_user.id if message.from_user else None
    if not await is_admin(bot, message.chat.id, user_id, message=message):
        await message.reply("❌ Bu buyruq faqat guruh administratorlari uchun!")
        return

    group = await db.get_or_create_group(message.chat.id, message.chat.title or "")
    current_raw = group.get("auto_approve_joins")
    current_val = 1 if current_raw is None else int(current_raw)
    approved_count = await db.get_join_requests_count(message.chat.id)

    # Botning a'zolarni qabul qilish huquqini tekshirish
    bot_id = get_bot_id(bot)
    can_invite = True
    try:
        me_member = await bot.get_chat_member(message.chat.id, bot_id)
        can_invite = getattr(me_member, "can_invite_users", False) or getattr(me_member, "status", "") == "creator"
    except Exception:
        can_invite = True

    rights_text = "✅ Huquqlar yetarli" if can_invite else "⚠️ Yetarli emas ('A'zolarni taklif qilish' huquqini bering!)"

    parts = (message.text or "").split()
    if len(parts) >= 2:
        arg = parts[1].strip().lower()
        if arg in ("on", "1", "ha", "yoq", "yoqish", "enable", "start"):
            new_val = 1
        elif arg in ("off", "0", "ochir", "ochirish", "disable", "stop"):
            new_val = 0
        else:
            new_val = 0 if current_val == 1 else 1

        await db.update_group_setting(message.chat.id, "auto_approve_joins", new_val)
        if new_val == 1:
            await message.reply(
                f"╔═══════════════════════════════════════╗\n"
                f"   📥 **AVTO-ZAYAFKA QABUL YOQILDI** ✅\n"
                f"╚═══════════════════════════════════════╝\n\n"
                f"├ 📊 **Qabul qilingan arizalar:** `{approved_count}` ta\n"
                f"├ 🤖 **Bot huquqi:** {rights_text}\n"
                f"└ 👮‍♂️ **Admin:** {get_admin_name(message)}\n\n"
                f"🚀 Endi yangi a'zolar havola orqali so'rov yuborganida, bot ularni 1 soniyada tasdiqlab, guruhga qabul qiladi va VIP salomnoma yuboradi.\n\n"
                f"O'chirish uchun: `/zayafka off`",
                parse_mode="Markdown",
            )
        else:
            await message.reply(
                f"╔═══════════════════════════════════════╗\n"
                f"   🛑 **AVTO-ZAYAFKA QABUL TO'XTATILDI** 🛑\n"
                f"╚═══════════════════════════════════════╝\n\n"
                f"Endi arizalarni adminlar qo'lda tasdiqlashi kerak bo'ladi.\n\n"
                f"Qayta yoqish uchun: `/zayafka on`",
                parse_mode="Markdown",
            )
        return

    # Argument yozilmagan bo'lsa, ma'lumot va boshqaruv tugmasi
    status_label = "✅ YOQILGAN (Avto-qabul)" if current_val == 1 else "🛑 O'CHIRILGAN"
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🛑 O'chirish" if current_val == 1 else "✅ Yoqish",
                    callback_data="toggle_auto_approve",
                ),
                InlineKeyboardButton(
                    text="⚙️ Barcha sozlamalar",
                    callback_data="open_settings_from_admin",
                ),
            ]
        ]
    )

    await message.reply(
        f"╔═══════════════════════════════════════╗\n"
        f"   📥 **QO'SHILISH ARIZALARI (ZAYAFKA)** 🚀\n"
        f"╚═══════════════════════════════════════╝\n\n"
        f"├ 📍 **Guruh:** «{message.chat.title}»\n"
        f"├ ⚡️ **Joriy holat:** {status_label}\n"
        f"├ 📊 **Qabul qilingan jami arizalar:** `{approved_count}` ta\n"
        f"└ 🤖 **Bot huquqi:** {rights_text}\n\n"
        f"💡 **Buyruqlar:**\n"
        f"├ `/zayafka on` — avtomatik qabul qilishni yoqish\n"
        f"└ `/zayafka off` — avtomatik qabul qilishni to'xtatish\n\n"
        f"Yoki quyidagi tugma orqali o'zgartiring:",
        reply_markup=kb,
        parse_mode="Markdown",
    )



async def auto_delete_msg(msg: Message, delay: int = 5) -> None:
    await asyncio.sleep(delay)
    try:
        await msg.delete()
    except Exception:
        pass


# ── /elon [har qanday xabar fayl bulishi mumkin guruhga qadab quyishi kerak] ──
@router.message(Command("elon", "broadcast", "pin", "qada", ignore_case=True))
async def cmd_broadcast(message: Message, bot: Bot) -> None:
    if message.chat.type in ("private",):
        await message.reply("⚠️ E'lon berish faqat guruhlarda ishlaydi!")
        return

    user_id = message.from_user.id if message.from_user else None
    if not await is_admin(bot, message.chat.id, user_id, message=message):
        await message.reply("❌ Bu buyruq faqat guruh administratorlari uchun!")
        return

    # 1. Agar biror xabar yoki faylga Reply qilingan bo'lsa — USHA XABARNI PIN QILISH
    if message.reply_to_message:
        target_msg = message.reply_to_message
        try:
            await bot.pin_chat_message(
                chat_id=message.chat.id,
                message_id=target_msg.message_id,
                disable_notification=False,
            )
            # Adminning /elon buyruq xabarini chat toza turishi uchun o'chirish
            try:
                await message.delete()
            except Exception:
                pass

            notify = await bot.send_message(
                chat_id=message.chat.id,
                text="📌 **Xabar muvaffaqiyatli qadab qo'yildi!**",
                reply_to_message_id=target_msg.message_id,
                parse_mode="Markdown",
            )
            asyncio.create_task(auto_delete_msg(notify, 5))
            return
        except Exception as e:
            await message.reply(
                f"❌ **Xabarni qadab bo'lmadi!**\n\n"
                f"Sabab: `{e}`\n\n"
                f"💡 **Yechim:** Bot guruhda **Administrator (Admin)** bo'lishi va unga **'Xabarlarni qadash' (Pin messages)** huquqi berilgan bo'lishi kerak!",
                parse_mode="Markdown",
            )
            return

    # 2. Agar matn bilan yuborilgan bo'lsa (/elon matn)
    text = (message.text or message.caption or "").strip()
    parts = text.split(maxsplit=1)
    if len(parts) > 1:
        announcement_content = parts[1].strip()
        try:
            await message.delete()
        except Exception:
            pass

        elon_msg = await bot.send_message(
            chat_id=message.chat.id,
            text=f"📢 **MUHIM E'LON!** 📌\n\n{announcement_content}\n\n*— Guruh ma'muriyati*",
            parse_mode="Markdown",
        )
        try:
            await bot.pin_chat_message(chat_id=message.chat.id, message_id=elon_msg.message_id, disable_notification=False)
        except Exception:
            pass
        return

    # 3. Agar rasm/video/fayl bilan birga /elon yozilgan bo'lsa
    if message.photo or message.video or message.document or message.audio or message.voice:
        try:
            await bot.pin_chat_message(chat_id=message.chat.id, message_id=message.message_id, disable_notification=False)
            notify = await bot.send_message(
                chat_id=message.chat.id,
                text="📢 **Faylli e'lon qadab qo'yildi!** 📌",
                reply_to_message_id=message.message_id,
                parse_mode="Markdown",
            )
            asyncio.create_task(auto_delete_msg(notify, 5))
            return
        except Exception as e:
            await message.reply(f"❌ Faylni qadashda xatolik: {e}")
            return

    # Agar hech narsa ko'rsatilmagan va reply qilinmagan bo'lsa — yo'riqnoma ko'rsatamiz
    await message.reply(
        "📢 **Xabarni qadash (PIN / E'LON):**\n\n"
        "• **Istalgan xabarni qadash uchun:**\n"
        "  Har qanday xabar, rasm, video yoki faylga **Reply** qilib `/elon` deb yozing!\n\n"
        "• **Yangi matnli e'lon yozib qadash:**\n"
        "  `/elon [E'lon matni]`\n\n"
        "📌 Bot xabarni barcha a'zolar ko'rishi uchun darhol guruhga qadab (pin) beradi!",
        parse_mode="Markdown",
    )


# ── /tun [Tungi rejimni sozlash] ─────────────────────────────────────
@router.message(Command("tun", "nightmode", "tungi", ignore_case=True))
async def cmd_night_mode(message: Message, bot: Bot) -> None:
    if message.chat.type in ("private",):
        await message.reply("⚠️ Ushbu buyruq faqat guruhlarda ishlaydi!")
        return
    user_id = message.from_user.id if message.from_user else None
    if not await is_admin(bot, message.chat.id, user_id, message=message):
        await message.reply("❌ Bu buyruq faqat guruh administratorlari uchun!")
        return

    group = await db.get_or_create_group(message.chat.id, message.chat.title or "")
    parts = (message.text or "").split()

    if len(parts) == 1:
        cur_en = group.get("night_mode_enabled", 0)
        status_txt = "YOQILGAN ✅" if cur_en == 1 else "O'CHIRILGAN ❌"
        st = group.get("night_mode_start", "23:00")
        en = group.get("night_mode_end", "07:00")
        await message.reply(
            f"╔═══════════════════════════════════════╗\n"
            f"   🌙 **TUNGI REJIM SOZLAMALARI** 🔒\n"
            f"╚═══════════════════════════════════════╝\n\n"
            f"├ 📍 **Guruh:** «{message.chat.title}»\n"
            f"├ ⚡️ **Joriy holat:** {status_txt}\n"
            f"└ ⏰ **Vaqt oralig'i:** `{st}` dan `{en}` gacha\n\n"
            f"📌 **Qanday boshqariladi:**\n"
            f"├ `/tun on` — Tungi rejimni yoqish\n"
            f"├ `/tun off` — Tungi rejimni o'chirish\n"
            f"└ `/tun 23:00-07:00` — Maxsus vaqt oralig'ini sozlash\n\n"
            f"💡 *Tungi rejimda bot belgilangan soatda oddiy a'zolarga yozishni avtomatik yopadi va tongda qayta ochadi.*",
            parse_mode="Markdown",
        )
        return

    arg = parts[1].lower()
    time_match = re.search(r"(\d{1,2}:\d{2})\s*-\s*(\d{1,2}:\d{2})", message.text or "")
    start_val = time_match.group(1) if time_match else None
    end_val = time_match.group(2) if time_match else None

    if arg in ("on", "1", "yoq", "start"):
        await db.set_night_mode(message.chat.id, enabled=1, start=start_val, end=end_val)
        st = start_val or group.get("night_mode_start", "23:00")
        en = end_val or group.get("night_mode_end", "07:00")
        await message.reply(
            f"╔═══════════════════════════════════════╗\n"
            f"   🌙 **TUNGI REJIM ISHGA TUSHIRILDI** ✅\n"
            f"╚═══════════════════════════════════════╝\n\n"
            f"⏰ **Amal qilish vaqti:** Har kuni soat **{st}** dan **{en}** gacha\n"
            f"🔒 Belgilangan vaqt oralig'ida guruh avtomatik yopiladi va tongda qayta ochiladi.\n\n"
            f"👮‍♂️ Admin: {get_admin_name(message)}",
            parse_mode="Markdown",
        )
    elif arg in ("off", "0", "ochir", "stop"):
        await db.set_night_mode(message.chat.id, enabled=0)
        if group.get("night_mode_is_locked", 0) == 1:
            try:
                await bot.set_chat_permissions(
                    chat_id=message.chat.id,
                    permissions=ChatPermissions(
                        can_send_messages=True,
                        can_send_other_messages=True,
                        can_add_web_page_previews=True,
                        can_send_polls=True,
                    ),
                )
                await db.set_night_mode_lock_state(message.chat.id, 0)
            except Exception:
                pass
        await message.reply(
            f"╔═══════════════════════════════════════╗\n"
            f"   ☀️ **TUNGI REJIM O'CHIRILDI** 🔓\n"
            f"╚═══════════════════════════════════════╝\n\n"
            f"✅ Guruh endi 24 soat davomida ochiq holatda qoladi.\n\n"
            f"👮‍♂️ Admin: {get_admin_name(message)}",
            parse_mode="Markdown",
        )
    elif time_match:
        await db.set_night_mode(message.chat.id, enabled=1, start=start_val, end=end_val)
        await message.reply(
            f"╔═══════════════════════════════════════╗\n"
            f"   ⏰ **TUNGI REJIM VAQTI O'ZGARTIRILDI** ✅\n"
            f"╚═══════════════════════════════════════╝\n\n"
            f"⏰ Yangi vaqt oralig'i: **{start_val}** — **{end_val}**\n\n"
            f"👮‍♂️ Admin: {get_admin_name(message)}",
            parse_mode="Markdown",
        )


