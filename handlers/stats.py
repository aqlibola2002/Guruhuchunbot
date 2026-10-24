from __future__ import annotations

from aiogram import Router, Bot
from aiogram.filters import Command
from aiogram.types import Message

from database.db import db
from services.ui_utils import make_progress_bar

router = Router(name="stats")


# ── /statistika (Guruh statistikasi va holati) ────────────────────
@router.message(Command("statistika", "stats", ignore_case=True))
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

    night_mode_text = "🌙 Faol (23:00 - 07:00)" if group.get("night_mode_enabled", 0) else "❌ O'chirilgan"
    if group.get("night_mode_enabled", 0):
        night_mode_text = f"🌙 Faol ({group.get('night_mode_start', '23:00')} - {group.get('night_mode_end', '07:00')})"

    text = (
        f"📊 **GURUH STATISTIKA DASHBOARDI** 📈\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🏛 **Guruh:** «{message.chat.title}»\n"
        f"👥 **Jami a'zolar:** `{member_count}` nafar\n"
        f"💬 **Bugungi faollik:** `{stats['today_messages']}` ta xabar\n"
        f"📈 **Jami qayd etilgan xabarlar:** `{stats['total_messages']}` ta\n\n"
        f"🛡 **BUGUNGI INTIZOM CHORALARI:**\n"
        f"├ 🔇 Cheklovlar (Mute): `{stats['today_mutes']}` ta\n"
        f"└ 🚫 Chetlatishlar (Ban): `{stats['today_bans']}` ta\n\n"
        f"⚙️ **HIMOYA TIZIMLARI HOLATI:**\n"
        f"├ 🔗 Begona linklar filtri: {mark(group.get('antilink_enabled', 1))}\n"
        f"├ 🛡️ Antispam va reklama: {mark(group.get('antispam_enabled', 1))}\n"
        f"├ ⚡️ Anti-Flood (Tezkor spam): {mark(group.get('anti_flood_enabled', 1))}\n"
        f"├ 🌙 Tungi rejim: {night_mode_text}\n"
        f"├ 🈲 Arab/Sharqiy reyd filtri: {mark(group.get('anti_arabic_enabled', 0))}\n"
        f"├ 🤖 Inline-botlar filtri: {mark(group.get('anti_inline_bot', 0))}\n"
        f"├ 👥 Majburiy a'zo talabi: `{inv_req_text}`\n"
        f"└ 👋 Yangi a'zolarni kutib olish: {mark(group.get('welcome_enabled', 1))}\n\n"
        f"🏆 Faol a'zolar: `/reyting` | 🥇 Taklifchilar: `/toptaklif`"
    )

    await message.reply(text, parse_mode="Markdown")


# ── /reyting (Eng faol yozuvchilar reytingi) ────────────────────────
@router.message(Command("reyting", "top", ignore_case=True))
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
    text = (
        f"🏆 **ENG FAOL A'ZOLAR (TOP-10)** 💬\n"
        f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🏛 **Guruh:** «{message.chat.title}»\n\n"
    )

    for idx, u in enumerate(top_users):
        medal = medals[idx] if idx < len(medals) else f"{idx + 1}."
        name = u["full_name"] or "Foydalanuvchi"
        username_part = f" (@{u['username']})" if u["username"] else ""
        text += f"{medal} **{name}**{username_part} — `{u['message_count']}` ta xabar\n"

    text += "\n✨ *Guruhda samimiy suhbatlashib, reytingingizni oshirib boring!*"
    await message.reply(text, parse_mode="Markdown")


# ── /takliflarim (A'zo qo'shganini hisoblash) ───────────────────────
@router.message(Command("takliflarim", "myinvites", ignore_case=True))
async def cmd_takliflarim(message: Message) -> None:
    if message.chat.type in ("private",):
        await message.reply(
            "ℹ️ Ushbu buyruq guruhda ishlatiladi.\n"
            "Guruhda `/takliflarim` deb yozing yoki biror foydalanuvchining xabariga **Reply** qilib yuboring!"
        )
        return

    group = await db.get_or_create_group(message.chat.id, message.chat.title or "")
    min_inv = int(group.get("min_invites") or 0)

    # Agar boshqa bir a'zoning xabariga Reply qilingan bo'lsa
    if message.reply_to_message and message.reply_to_message.from_user:
        target = message.reply_to_message.from_user
        user_invites = await db.get_user_invites(message.chat.id, target.id)

        if min_inv > 0:
            percent = min(100, int(round((user_invites / min_inv) * 100)))
            bar = make_progress_bar(percent)
            if user_invites >= min_inv:
                status_text = (
                    f"├ 📊 **Takliflar:** **{user_invites} / {min_inv} ta ({percent}%)**\n"
                    f"├ 📈 **Jarayon:** {bar} **{percent}%**\n"
                    f"└ ✅ **Holati:** Guruh talabini to'liq bajargan (yozishga ruxsat) ✨"
                )
            else:
                left = min_inv - user_invites
                status_text = (
                    f"├ 📊 **Takliflar:** **{user_invites} / {min_inv} ta ({percent}%)**\n"
                    f"├ 📈 **Jarayon:** {bar} **{percent}%**\n"
                    f"└ ⚠️ **Holati:** Yozish uchun yana **{left} ta** a'zo qo'shishi kerak"
                )
        else:
            status_text = f"└ ➕ **Qo'shgan a'zolari:** **{user_invites} ta** (Guruhda cheklov yo'q)"

        await message.reply(
            f"👤 **A'ZONING TAKLIF HISOBI** 👥\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 **A'zo:** {target.full_name}\n"
            f"{status_text}",
            parse_mode="Markdown",
        )
        return

    # O'zining takliflari statistikasi
    user_id = message.from_user.id if message.from_user else None
    if not user_id:
        await message.reply("Takliflarni hisoblash uchun profilingizdan yozing.")
        return

    user_name = message.from_user.full_name if (message.from_user and message.from_user.full_name) else "Foydalanuvchi"
    user_invites = await db.get_user_invites(message.chat.id, user_id)
    if min_inv > 0:
        percent = min(100, int(round((user_invites / min_inv) * 100)))
        bar = make_progress_bar(percent)
        if user_invites >= min_inv:
            status_text = (
                f"├ 📊 **Siz qo'shgan a'zolar:** **{user_invites} / {min_inv} ta ({percent}%)**\n"
                f"├ 📈 **Jarayon:** {bar} **{percent}%**\n"
                f"└ ✅ **Holati:** Guruh talabini to'liq bajargansiz, bemalol yoza olasiz! 🎉"
            )
        else:
            left = min_inv - user_invites
            status_text = (
                f"├ 📊 **Siz qo'shgan a'zolar:** **{user_invites} / {min_inv} ta ({percent}%)**\n"
                f"├ 📈 **Jarayon:** {bar} **{percent}%**\n"
                f"└ ⚠️ **Holati:** Guruhda yozish uchun yana **{left} ta** do'stingizni taklif qiling!"
            )
    else:
        status_text = f"└ ➕ **Siz taklif qilgan a'zolar:** **{user_invites} ta** (Cheklov o'rnatilmagan)"

    await message.reply(
        f"📊 **SIZNING TAKLIF HISOBINGIZ** 👥\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 **Foydalanuvchi:** {user_name}\n"
        f"{status_text}\n\n"
        f"💡 *Boshqa a'zoning takliflarini bilish uchun uning xabariga Reply qilib `/takliflarim` deb yozing!*",
        parse_mode="Markdown",
    )


# ── /toptaklif (Guruhga eng ko'p odam qo'shganlar reytingi) ─────────
@router.message(Command("toptaklif", "topinvites", ignore_case=True))
async def cmd_top_invites(message: Message) -> None:
    if message.chat.type in ("private",):
        await message.reply("🏆 Taklifchilar reytingini ko'rish uchun ushbu buyruqni guruhingizda yuboring!")
        return

    top_inviters = await db.get_top_inviters(message.chat.id, limit=10)
    if not top_inviters:
        await message.reply(
            f"ℹ️ **'{message.chat.title}'** guruhida hali taklif qilingan a'zolar mavjud emas.\n"
            "Foydalanuvchilar guruhga do'stlarini qo'shgach, reyting avtomatik shakllanadi!"
        )
        return

    group = await db.get_or_create_group(message.chat.id, message.chat.title or "")
    min_inv = int(group.get("min_invites") or 0)

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    text = (
        f"🥇 **TOP TAKLIFCHILAR (TOP-10)** 👥\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🏛 **Guruh:** «{message.chat.title}»\n\n"
    )

    for idx, u in enumerate(top_inviters):
        medal = medals[idx] if idx < len(medals) else f"{idx + 1}."
        name = u["full_name"] or "Foydalanuvchi"
        username_part = f" (@{u['username']})" if u["username"] else ""
        cnt = u["invite_count"]

        if min_inv > 0:
            pct = min(100, int(round((cnt / min_inv) * 100)))
            text += f"{medal} **{name}**{username_part} — **{cnt} ta** ({pct}%)\n   {make_progress_bar(pct, length=8)}\n"
        else:
            text += f"{medal} **{name}**{username_part} — **{cnt} ta** a'zo qo'shgan\n"

    text += "\n💡 *Guruhga do'stlaringizni taklif qiling va reytingda 1-o'ringa chiqing!*\nO'z hisobingiz: `/takliflarim`"
    await message.reply(text, parse_mode="Markdown")



