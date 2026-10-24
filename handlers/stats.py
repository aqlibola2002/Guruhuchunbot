import asyncio
import random

from aiogram import Router, Bot, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from database.db import db
from filters.admin_filter import is_admin
from services.ui_utils import make_progress_bar, get_level_title

router = Router(name="stats")
LAST_REP_GIVEN: dict[tuple[int, int], float] = {}


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


# ── /profil (Foydalanuvchi profili, darajasi va yutuqlari) ─────────
@router.message(Command("profil", "daraja", "men", "profile", "level", ignore_case=True))
async def cmd_user_profile(message: Message) -> None:
    if message.chat.type in ("private",):
        await message.reply("👤 Profil kartangizni ko'rish uchun ushbu buyruqni guruhingizda yuboring!")
        return

    target_user = (
        message.reply_to_message.from_user
        if message.reply_to_message and message.reply_to_message.from_user
        else message.from_user
    )
    if not target_user:
        return

    profile = await db.get_user_profile(message.chat.id, target_user.id)
    name = target_user.full_name or "Foydalanuvchi"
    uname = f"@{target_user.username}" if target_user.username else name
    user_link = f"[{name}](tg://user?id={target_user.id})"

    msg_cnt = profile.get("message_count", 0)
    xp = profile.get("xp", 0)
    level = profile.get("level", 1)
    rep = profile.get("reputation", 0)
    invites = profile.get("invites_count", 0)
    rank = profile.get("rank", 1)

    title = get_level_title(level)
    xp_in_level = xp % 100
    bar = make_progress_bar(xp_in_level, length=10)

    text = (
        f"👤 **FOYDALANUVCHI PROFILI** 🎖\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 **A'zo:** {user_link} ({uname})\n"
        f"🏆 **Unvon:** **{title}**\n"
        f"⭐ **Daraja:** **Level {level}**\n"
        f"📈 **Tajriba (XP):** `{xp}` XP\n"
        f"📊 **Keyingi darajagacha:** `{xp_in_level} / 100 XP` ({xp_in_level}%)\n"
        f"   {bar}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"💬 **Yozgan xabarlari:** **{msg_cnt}** ta\n"
        f"👥 **Qo'shgan a'zolari:** **{invites}** ta\n"
        f"🌟 **Reputatsiya (+rep):** **{rep}** ball\n"
        f"🏅 **Guruhdagi o'rni:** **#{rank}**-o'rin\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎁 *Har 24 soatda bonus olish uchun:* `/kunlik`"
    )

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🎁 Kunlik Bonus XP", callback_data="btn_claim_daily"),
                InlineKeyboardButton(text="🏆 TOP Darajalar", callback_data="btn_top_levels"),
            ]
        ]
    )

    await message.reply(text, reply_markup=kb, parse_mode="Markdown")


# ── /kunlik (Har kunlik faollik uchun bonus XP) ─────────────────────
@router.message(Command("kunlik", "daily", "bonus", ignore_case=True))
async def cmd_claim_daily(message: Message) -> None:
    if message.chat.type in ("private",):
        await message.reply("🎁 Kunlik bonus olish uchun ushbu buyruqni guruhingizda yuboring!")
        return

    if not message.from_user:
        return

    ok, xp_amount, err = await db.claim_daily_xp(message.chat.id, message.from_user.id)
    mention = f"[{message.from_user.full_name}](tg://user?id={message.from_user.id})"

    if not ok:
        await message.reply(
            f"⏳ {mention}, **siz bugungi kunlik bonusingizni allaqachon olgansiz!** 😊\n\n"
            f"Keyingi bonusni ertaga olishingiz mumkin.\n"
            f"O'z darajangizni ko'rish: `/profil`",
            parse_mode="Markdown",
        )
        return

    profile = await db.get_user_profile(message.chat.id, message.from_user.id)
    new_lvl = profile.get("level", 1)
    new_xp = profile.get("xp", 0)

    await message.reply(
        f"🎉 **KUNLIK BONUS TOPSHIRILDI!** 🎁\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👏 Tabriklaymiz, {mention}!\n"
        f"⭐ **Sizga +{xp_amount} XP bonus taqdim etildi!** 🚀\n\n"
        f"📊 **Hozirgi hisobingiz:**\n"
        f"├ ⭐ Daraja: **Level {new_lvl}**\n"
        f"└ 📈 Jami XP: **{new_xp} XP**\n\n"
        f"💡 Guruhda faol bo'ling va eng yuqori ligaga chiqing!",
        parse_mode="Markdown",
    )


# ── /darajalar (Guruhdagi eng yuqori darajalar ligasi) ──────────────
@router.message(Command("darajalar", "toplevel", "topxp", ignore_case=True))
async def cmd_top_levels(message: Message) -> None:
    if message.chat.type in ("private",):
        await message.reply("🏆 Darajalar reytingini ko'rish uchun ushbu buyruqni guruhingizda yuboring!")
        return

    top_users = await db.get_top_levels(message.chat.id, limit=10)
    if not top_users:
        await message.reply("ℹ️ Guruhda hali daraja to'plagan faol a'zolar mavjud emas.")
        return

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
    text = (
        f"🏆 **ENG YUQORI DARAJA VA XP EGALARI (TOP-10)** 🌟\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"🏛 **Guruh:** «{message.chat.title}»\n\n"
    )

    for idx, u in enumerate(top_users):
        medal = medals[idx] if idx < len(medals) else f"{idx + 1}."
        name = u["full_name"] or "Foydalanuvchi"
        uname = f" (@{u['username']})" if u["username"] else ""
        lvl = u.get("level", 1)
        xp = u.get("xp", 0)
        rep = u.get("reputation", 0)
        title = get_level_title(lvl)
        text += f"{medal} **{name}**{uname}\n   ⭐ **Level {lvl}** ({xp} XP) • {title} • 🌟 {rep} rep\n\n"

    text += "💡 *Xabar yozing, do'stlaringizni taklif qiling va har kuni `/kunlik` oling!*\nSizning profilingiz: `/profil`"
    await message.reply(text, parse_mode="Markdown")


# ── /tasodif (Konkurs va giveaway lar uchun tasodifiy g'olib) ───────
@router.message(Command("tasodif", "random", "giveaway", "golib", ignore_case=True))
async def cmd_random_winner(message: Message, bot: Bot) -> None:
    if message.chat.type in ("private",):
        await message.reply("🎲 Tasodifiy tanlov buyrug'i faqat guruhlarda ishlaydi!")
        return

    user_id = message.from_user.id if message.from_user else None
    if not await is_admin(bot, message.chat.id, user_id, message=message):
        await message.reply("❌ Bu buyruq faqat guruh administratorlari uchun!")
        return

    winner = await db.get_random_active_user(message.chat.id)
    if not winner:
        await message.reply("⚠️ Guruhda tanlash uchun yetarli faol a'zolar topilmadi.")
        return

    status_msg = await message.reply("🎲 **TASODIFIY TANLOV BOSHLANDI...**\n\n⏳ G'olib aniqlanmoqda...")
    await asyncio.sleep(1.0)
    await status_msg.edit_text("🎲 **TASODIFIY TANLOV...**\n\n3️⃣ ...")
    await asyncio.sleep(0.8)
    await status_msg.edit_text("🎲 **TASODIFIY TANLOV...**\n\n2️⃣ ...")
    await asyncio.sleep(0.8)
    await status_msg.edit_text("🎲 **TASODIFIY TANLOV...**\n\n1️⃣ ...")
    await asyncio.sleep(0.8)

    w_name = winner["full_name"] or "Foydalanuvchi"
    w_mention = f"[{w_name}](tg://user?id={winner['user_id']})"
    w_uname = f"@{winner['username']}" if winner.get("username") else "mavjud emas"
    msgs = winner.get("message_count", 0)

    final_text = (
        f"🎉 **TASODIFIY TANLOV G'OLIBI ANIQLANDI!** 🏆\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👑 **G'olib:** {w_mention}\n"
        f"🆔 **ID:** `{winner['user_id']}`\n"
        f"📱 **Username:** {w_uname}\n"
        f"💬 **Guruhdagi faolligi:** {msgs} ta xabar\n\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        f"🎊 Barcha guruh a'zolari nomidan chin dildan tabriklaymiz! 👏\n"
        f"👮‍♂️ O'tkazgan admin: {message.from_user.full_name if message.from_user else 'Admin'}"
    )
    await status_msg.edit_text(final_text, parse_mode="Markdown")


# ── /zar, /tanga, /duel (Interaktiv mini-o'yinlar) ───────────────────
@router.message(Command("zar", "dice", ignore_case=True))
async def cmd_dice(message: Message, bot: Bot) -> None:
    if message.chat.type in ("private",):
        return
    dice_msg = await bot.send_dice(message.chat.id, emoji="🎲")
    val = dice_msg.dice.value
    name = message.from_user.full_name if message.from_user else "Foydalanuvchi"
    await asyncio.sleep(2.5)
    await dice_msg.reply(f"🎲 **{name}**, siz tashlagan zar: **{val}** tushdi!", parse_mode="Markdown")


@router.message(Command("tanga", "coin", ignore_case=True))
async def cmd_coin(message: Message) -> None:
    if message.chat.type in ("private",):
        return
    res = random.choice(["🦅 **Burgut (Orel)**", "🪙 **Gerb (Reshka)**"])
    name = message.from_user.full_name if message.from_user else "Foydalanuvchi"
    msg = await message.reply("🪙 *Tanga havoga tashlandi...* 🌀", parse_mode="Markdown")
    await asyncio.sleep(1.5)
    await msg.edit_text(f"🪙 **{name}**, tanga tushdi:\n\n👉 {res}!", parse_mode="Markdown")


@router.message(Command("duel", "jang", ignore_case=True))
async def cmd_duel(message: Message, bot: Bot) -> None:
    if message.chat.type in ("private",):
        return
    if not message.reply_to_message or not message.reply_to_message.from_user:
        await message.reply(
            "⚔️ **Duel (Zar jangi):**\n\nBiror foydalanuvchining xabariga **Reply** qilib `/duel` deb yozing!",
            parse_mode="Markdown",
        )
        return

    user1 = message.from_user
    user2 = message.reply_to_message.from_user

    if user1.id == user2.id:
        await message.reply("😅 O'zingiz bilan duel qila olmaysiz!")
        return

    await message.reply(
        f"⚔️ **DUEL BOSHLANDI!**\n\n🤺 **{user1.full_name}** 🆚 **{user2.full_name}**\n\n🎲 Zarlar tashlanmoqda..."
    )
    await asyncio.sleep(1.0)

    d1 = await bot.send_dice(message.chat.id, emoji="🎲")
    await asyncio.sleep(2.0)
    d2 = await bot.send_dice(message.chat.id, emoji="🎲")
    await asyncio.sleep(2.5)

    v1, v2 = d1.dice.value, d2.dice.value

    if v1 > v2:
        winner_text = f"🎉 **{user1.full_name} g'olib bo'ldi!** ({v1} vs {v2}) 🏆 (+15 XP)"
        await db.claim_daily_xp(message.chat.id, user1.id)
    elif v2 > v1:
        winner_text = f"🎉 **{user2.full_name} g'olib bo'ldi!** ({v2} vs {v1}) 🏆 (+15 XP)"
        await db.claim_daily_xp(message.chat.id, user2.id)
    else:
        winner_text = f"🤝 **DURRANG!** Ikkala tomonda ham {v1} tushdi! ⚖️"

    await message.reply(
        f"⚔️ **DUEL NATIJASI:**\n━━━━━━━━━━━━━━━━━━━━\n"
        f"🎲 {user1.full_name}: **{v1}**\n"
        f"🎲 {user2.full_name}: **{v2}**\n\n"
        f"{winner_text}",
        parse_mode="Markdown",
    )


# ── Reputatsiya / Minnatdorchilik (+rep, rahmat) ────────────────────
@router.message(
    F.text.lower().in_(
        {
            "+rep",
            "rahmat",
            "tashakkur",
            "raxmat",
            "malades",
            "molodets",
            "spasibo",
            "katta rahmat",
            "minnatdorman",
            "👍",
        }
    )
)
async def on_reputation_trigger(message: Message) -> None:
    if message.chat.type in ("private",):
        return

    if not message.reply_to_message or not message.reply_to_message.from_user or not message.from_user:
        return

    target = message.reply_to_message.from_user
    giver = message.from_user

    if target.id == giver.id or target.is_bot:
        return

    now_t = asyncio.get_event_loop().time()
    rep_key = (message.chat.id, giver.id)
    last_rep = LAST_REP_GIVEN.get(rep_key, 0.0)
    if now_t - last_rep < 30.0:
        return
    LAST_REP_GIVEN[rep_key] = now_t

    new_rep = await db.add_user_reputation(message.chat.id, target.id, amount=1)
    target_mention = f"[{target.full_name}](tg://user?id={target.id})"
    giver_mention = f"[{giver.full_name}](tg://user?id={giver.id})"

    await message.reply(
        f"🌟 {giver_mention} a'zosi {target_mention} ga **+1 Reputatsiya** berdi!\n"
        f"🏆 Jami reputatsiyasi: **{new_rep}** ball ✨",
        parse_mode="Markdown",
    )


# ── Inline Callbacklar: Kunlik bonus va TOP darajalar ──────────────
@router.callback_query(F.data == "btn_claim_daily")
async def cb_claim_daily(call: CallbackQuery) -> None:
    if not call.from_user:
        return
    ok, xp, err = await db.claim_daily_xp(call.message.chat.id, call.from_user.id)
    if ok:
        await call.answer(f"🎉 Tabriklaymiz! Sizga +{xp} XP berildi!", show_alert=True)
    else:
        await call.answer("⏳ Bugungi bonusingizni allaqachon olgansiz. Ertaga urinib ko'ring!", show_alert=True)


@router.callback_query(F.data == "btn_top_levels")
async def cb_top_levels(call: CallbackQuery) -> None:
    top_users = await db.get_top_levels(call.message.chat.id, limit=5)
    if not top_users:
        await call.answer("Guruhda hali darajalar yo'q", show_alert=True)
        return

    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    lines = []
    for idx, u in enumerate(top_users):
        med = medals[idx] if idx < len(medals) else f"{idx+1}."
        lines.append(f"{med} {u['full_name']} — Level {u.get('level', 1)} ({u.get('xp', 0)} XP)")
    await call.answer("\n".join(lines), show_alert=True)




