from __future__ import annotations

from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message

from database.db import db

router = Router(name="stats")


# ── /statistika (Guruh statistikasi va holati) ────────────────────
@router.message(Command("statistika", "stats"))
async def cmd_stats(message: Message, bot: Bot) -> None:
    if message.chat.type in ("private",):
        await message.reply("📊 Guruh statistikasini ko'rish uchun ushbu buyruqni guruhingizda yuboring!")
        return

    chat_id = message.chat.id
    stats = await db.get_group_stats(chat_id)
    group = await db.get_or_create_group(chat_id, message.chat.title or "")

    # Telegram API dan jami a'zolar sonini olish
    try:
        member_count = await bot.get_chat_member_count(chat_id)
    except Exception:
        member_count = "Noma'lum"

    def mark(val: int) -> str:
        return "✅ Faol" if val == 1 else "❌ O'chirilgan"

    min_inv = group.get("min_invites", 0)
    inv_req_text = f"{min_inv} ta ({mark(group.get('invites_enabled', 1))})" if min_inv > 0 else "Cheklov yo'q"

    text = (
        f"📊 **'{message.chat.title}' guruhi statistikasi:**\n\n"
        f"👥 **Jami a'zolar:** {member_count}\n"
        f"💬 **Bugungi xabarlar:** {stats['today_messages']} ta\n"
        f"📈 **Jami qayd etilgan xabarlar:** {stats['total_messages']} ta\n\n"
        f"🛡 **Bugungi jazo choralari:**\n"
        f"• ⚠️ Ogohlantirishlar: {stats['today_warns']}\n"
        f"• 🔇 Cheklovlar (Mute): {stats['today_mutes']}\n"
        f"• 🚫 Chetlatishlar (Ban): {stats['today_bans']}\n\n"
        f"⚙️ **Himoya sozlamalari holati:**\n"
        f"• 🔗 Begona linklar filtri: {mark(group.get('antilink_enabled', 1))}\n"
        f"• 🛡️ Antispam va reklama filtri: {mark(group.get('antispam_enabled', 1))}\n"
        f"• 👥 Majburiy a'zo talabi (/odam): {inv_req_text}\n"
        f"• 👋 Yangi a'zolarni kutib olish: {mark(group.get('welcome_enabled', 1))}\n\n"
        f"🏆 Faol a'zolar: `/reyting`\n"
        f"🌟 Eng ko'p taklif qilganlar: `/taklifchilar`"
    )

    await message.reply(text, parse_mode="Markdown")


# ── /reyting (Eng faol yozuvchilar reytingi) ────────────────────────
@router.message(Command("reyting", "top"))
async def cmd_top(message: Message) -> None:
    if message.chat.type in ("private",):
        await message.reply("🏆 Faollik reytingini ko'rish uchun ushbu buyruqni guruhingizda yuboring!")
        return

    top_users = await db.get_top_users(message.chat.id, limit=10)
    if not top_users:
        await message.reply(
            f"ℹ️ **'{message.chat.title}'** guruhida hali faollik yetarli emas.\n"
            "Xabarlar yozilgach, reyting avtomatik shakllanadi!"
        )
        return

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    text = f"🏆 **'{message.chat.title}' — Eng faol a'zolar reytingi (TOP-10):**\n\n"

    for idx, u in enumerate(top_users):
        medal = medals[idx] if idx < len(medals) else f"{idx + 1}."
        name = u["full_name"] or "Foydalanuvchi"
        username_part = f" (@{u['username']})" if u["username"] else ""
        text += f"{medal} **{name}**{username_part} — `{u['message_count']}` ta xabar\n"

    text += "\n💡 *Guruhda xabar yozish orqali reytingingizni oshirib boring!*"
    await message.reply(text, parse_mode="Markdown")


# ── /takliflarim (A'zo qo'shganini hisoblash) ───────────────────────
@router.message(Command("takliflarim", "myinvites"))
async def cmd_takliflarim(message: Message) -> None:
    if message.chat.type in ("private",):
        await message.reply(
            "ℹ️ Ushbu buyruq guruhda ishlatiladi.\n"
            "Guruhda `/takliflarim` deb yozing yoki biror foydalanuvchining xabariga **Reply** qilib yuboring!"
        )
        return

    group = await db.get_or_create_group(message.chat.id, message.chat.title or "")
    min_inv = group.get("min_invites", 0)

    # Agar boshqa bir a'zoning xabariga Reply qilingan bo'lsa
    if message.reply_to_message and message.reply_to_message.from_user:
        target = message.reply_to_message.from_user
        user_invites = await db.get_user_invites(message.chat.id, target.id)

        status_text = ""
        if min_inv > 0:
            if user_invites >= min_inv:
                status_text = "\n✅ **Ushbu foydalanuvchi guruh talabini to'liq bajargan!**"
            else:
                left = min_inv - user_invites
                status_text = f"\n⚠️ Guruhda yozish uchun yana **{left}** ta do'stini qo'shishi kerak."

        await message.reply(
            f"👤 **{target.full_name}** qo'shgan a'zolar statistikasi:\n\n"
            f"➕ Guruhga taklif qilgan: **{user_invites}** ta a'zo\n"
            f"🎯 Guruh talabi: **{min_inv}** ta{status_text}",
            parse_mode="Markdown",
        )
        return

    # O'zining takliflari statistikasi
    if not message.from_user:
        return

    user_invites = await db.get_user_invites(message.chat.id, message.from_user.id)
    status_text = ""
    if min_inv > 0:
        if user_invites >= min_inv:
            status_text = "\n✅ **Siz guruh talabini bajargansiz, bemalol yoza olasiz!**"
        else:
            left = min_inv - user_invites
            status_text = f"\n⚠️ Guruhda yozish uchun yana **{left}** ta do'stingizni taklif qilishingiz kerak!"

    await message.reply(
        f"👥 **{message.from_user.full_name}**, sizning takliflaringiz statistikasi:\n\n"
        f"➕ Siz qo'shgan a'zolar soni: **{user_invites}** ta\n"
        f"🎯 Guruh talabi: **{min_inv}** ta{status_text}\n\n"
        f"💡 *Boshqa a'zoning takliflarini bilish uchun uning xabariga Reply qilib `/takliflarim` deb yozing!*",
        parse_mode="Markdown",
    )


# ── /taklifchilar (Eng ko'p taklif qilganlar) ──────────────────────
@router.message(Command("taklifchilar", "topinvites", "toptaklif"))
async def cmd_topinvites(message: Message) -> None:
    if message.chat.type in ("private",):
        await message.reply("🌟 Taklifchilar reytingini ko'rish uchun ushbu buyruqni guruhingizda yuboring!")
        return

    top_inviters = await db.get_top_inviters(message.chat.id, limit=10)
    if not top_inviters:
        await message.reply(
            f"ℹ️ **'{message.chat.title}'** guruhida hali a'zolar taklif qilish statistikasi mavjud emas.\n"
            "A'zolar odam qo'shishni boshlagach, TOP-10 ro'yxat shakllanadi!"
        )
        return

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    text = f"🌟 **'{message.chat.title}' — Eng ko'p odam qo'shganlar (TOP-10):**\n\n"

    for idx, u in enumerate(top_inviters):
        medal = medals[idx] if idx < len(medals) else f"{idx + 1}."
        name = u["full_name"] or "Foydalanuvchi"
        username_part = f" (@{u['username']})" if u["username"] else ""
        text += f"{medal} **{name}**{username_part} — **{u['invite_count']}** ta a'zo\n"

    text += "\n👥 *Guruhimizga do'stlaringizni qo'shib, guruh rivojiga hissa qo'shing!*"
    await message.reply(text, parse_mode="Markdown")
