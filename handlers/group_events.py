from __future__ import annotations

import asyncio
import logging
from aiogram import Router, Bot, F
from aiogram.types import (
    Message,
    CallbackQuery,
    ChatMemberUpdated,
    ChatJoinRequest,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ChatPermissions,
    User,
)
from database.db import db
from filters.admin_filter import is_admin
from services.ui_utils import make_progress_bar, pop_user_invite_warn_msg, pop_user_invite_warn_msgs

logger = logging.getLogger(__name__)
router = Router(name="group_events")
RECENT_WELCOMES: dict[tuple[int, int], float] = {}


async def auto_delete_msg(msg: Message, delay: int = 60) -> None:
    await asyncio.sleep(delay)
    try:
        await msg.delete()
    except Exception:
        pass


async def send_group_intro(bot: Bot, chat_id: int, chat_title: str) -> None:
    """Bot yangi guruhga qo'shilganda to'liq imkoniyatlar haqida ma'lumot berish."""
    # Guruhni bazaga kiritish
    await db.get_or_create_group(chat_id, chat_title)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⚙️ Guruh Sozlamalari", callback_data="btn_open_settings"),
                InlineKeyboardButton(text="📜 Qoidalar", callback_data="btn_rules"),
            ],
            [
                InlineKeyboardButton(text="📖 Barcha Buyruqlar", callback_data="btn_help_info"),
            ],
        ]
    )

    intro_text = (
        f"👑 **GURUHCHI UZ — PREMIUM HIMOYACHI** 🛡\n"
        f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"Assalomu alaykum, **«{chat_title}»** guruhi jamoasi va administratorlari!\n"
        f"Guruhingizni tartibga solish, reklama/viruslardan 24/7 tozalash va a'zolar oqimini kengaytirish uchun bot faollashdi! 🚀\n\n"
        f"💎 **ENG ASOSIY IMKONIYATLAR:**\n"
        f"├ 🌙 **Tungi rejim:** Soat 23:00 dan 07:00 gacha avtomatik yopilish (`/tun`)\n"
        f"├ ⚡️ **Anti-Flood:** Sekundiga xabar yog'diruvchi spamerlarni avto-cheklash\n"
        f"├ 📥 **Zayafka avto-qabul:** Guruh/kanal arizalarini 1 soniyada tasdiqlash (`/zayafka`)\n"
        f"├ 🈲 **Anti-Raid:** Xorijiy arab/sharqiy spambot xabarlarini darhol yo'q qilish\n"
        f"├ 🤖 **Anti-Inline bot:** Begona inline reklama botlarini tozalash\n"
        f"├ 🦠 **Anti-APK:** Troyan va virusli fayllarni 100% o'chirish\n"
        f"├ 👥 **Majburiy taklif:** `/odam 5` (a'zo qo'shmaguncha yoza olmaydi)\n"
        f"├ 🥇 **TOP Taklifchilar:** Eng ko'p odam qo'shganlar reytingi (`/toptaklif`)\n"
        f"└ 🧹 **Tezkor tozalash:** Oxirgi xabarlarni tozalash (`/tozala 20`)\n\n"
        f"⚡️ **BOT BENUQSON ISHLASHI UCHUN:**\n"
        f"Guruh sozlamalaridan botga **Administrator** huquqlarini bering:\n"
        f"✅ *Xabarlarni o'chirish* | ✅ *A'zolarni cheklash* | ✅ *Xabarlarni qadash*\n\n"
        f"⚙️ Boshqaruv paneli: `/sozlamalar`\n"
        f"📖 Barcha buyruqlar: `/yordam`"
    )

    try:
        await bot.send_message(
            chat_id=chat_id,
            text=intro_text,
            reply_markup=kb,
            parse_mode="Markdown",
        )
    except Exception as e:
        logger.warning(f"Guruhga intro yuborishda xatolik: {e}")


# ── Bot guruhga qo'shilganda (my_chat_member hodisasi) ─────────────
@router.my_chat_member()
async def on_bot_added_to_chat(event: ChatMemberUpdated, bot: Bot) -> None:
    if event.chat.type in ("group", "supergroup"):
        old_status = event.old_chat_member.status
        new_status = event.new_chat_member.status

        # Agar bot guruhga yangi a'zo yoki admin qilib qo'shilgan bo'lsa
        if old_status not in ("member", "administrator") and new_status in ("member", "administrator"):
            chat_title = event.chat.title or "Guruh"
            chat_username = event.chat.username or ""
            invite_link = f"https://t.me/{chat_username}" if chat_username else ""

            # Agar ochiq havola bo'lmasa va bot admin bo'lsa, taklif havolasini olamiz
            if not invite_link and new_status == "administrator":
                try:
                    invite_link = await bot.export_chat_invite_link(event.chat.id)
                except Exception:
                    pass

            await db.get_or_create_group(event.chat.id, chat_title, invite_link, chat_username)
            await send_group_intro(bot, event.chat.id, chat_title)

            # Bot Egasiga (Super Adminlarga) yangi guruh havolasi bilan xabar yetkazish
            from config import ADMIN_IDS
            for admin_id in ADMIN_IDS:
                try:
                    members_cnt = "?"
                    try:
                        members_cnt = await bot.get_chat_member_count(event.chat.id)
                    except Exception:
                        pass
                    link_display = f"[Guruhga o'tish]({invite_link})" if invite_link else "_Olinmadi (bot admin qilinmagan)_"
                    await bot.send_message(
                        chat_id=admin_id,
                        text=(
                            f"🎉 **BOT YANGI GURUHGA QO'SHILDI!** 🏛\n"
                            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                            f"📌 **Nomi:** {chat_title}\n"
                            f"🆔 **ID:** `{event.chat.id}`\n"
                            f"👥 **A'zolar soni:** {members_cnt} ta\n"
                            f"🔗 **Guruh havolasi:** {link_display}\n"
                            f"👤 **Qo'shgan shaxs:** {event.from_user.full_name} (`{event.from_user.id}`)\n\n"
                            f"💡 Barcha guruhlar ro'yxatini `/panel` yoki `/guruhlar` orqali ko'rishingiz mumkin."
                        ),
                        parse_mode="Markdown",
                        disable_web_page_preview=True,
                    )
                except Exception:
                    pass


async def send_invite_notification(
    bot: Bot,
    chat_id: int,
    inviter: User,
    new_user: User,
    total_invites: int,
    group: dict,
) -> None:
    """Yangi a'zo qo'shilganda zamonaviy foizli va progress barli bildirishnoma yuborish."""
    min_req = int(group.get("min_invites") or 0)
    inviter_name = inviter.full_name or "Foydalanuvchi"
    inviter_mention = f"[{inviter_name}](tg://user?id={inviter.id})"
    new_user_name = new_user.full_name or "Yangi a'zo"

    # Avvalgi barcha ogohlantirish xabarlarini guruhdan avtomatik o'chirib tashlaymiz
    db_warns = await db.pop_invite_warnings(chat_id, inviter.id)
    mem_warns = pop_user_invite_warn_msgs(chat_id, inviter.id)
    for old_warn_id in set(db_warns + mem_warns):
        try:
            await bot.delete_message(chat_id=chat_id, message_id=old_warn_id)
        except Exception:
            pass

    if min_req > 0:
        percent = min(100, int(round((total_invites / min_req) * 100)))
        bar = make_progress_bar(percent)

        if total_invites >= min_req:
            # Foydalanuvchi talabni to'liq bajardi — yozish huquqini to'liq beramiz
            try:
                await bot.restrict_chat_member(
                    chat_id=chat_id,
                    user_id=inviter.id,
                    permissions=ChatPermissions(
                        can_send_messages=True,
                        can_send_media_messages=True,
                        can_send_polls=True,
                        can_send_other_messages=True,
                        can_add_web_page_previews=True,
                    ),
                )
            except Exception:
                pass

            text = (
                f"🎉 **TABRIKLAYMIZ, {inviter_mention}!** 🎉\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 **Yangi qo'shilgan a'zo:** {new_user_name}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📊 **Jami takliflaringiz:** **{total_invites} / {min_req} ta (100% ✅)**\n"
                f"📈 **Jarayon:** {bar} **100%**\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"✅ **Siz guruhda yozish uchun talab qilingan barcha a'zolarni qo'shdingiz!**\n"
                f"💬 **Endi guruhda bemalol va erkin xabar yozishingiz mumkin!** ✨"
            )
        else:
            left = min_req - total_invites
            text = (
                f"👏 **{inviter_mention}**, yangi a'zo qo'shdingiz! 🚀\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"👤 **Yangi qo'shilgan a'zo:** {new_user_name}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📊 **Qo'shgan a'zolaringiz:** **{total_invites} / {min_req} ta ({percent}%)**\n"
                f"📈 **Jarayon:** {bar} **{percent}%**\n"
                f"➕ **Yozish huquqi uchun yana:** **{left} ta** a'zo qo'shishingiz kerak!\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"💡 Do'stlaringizni taklif qiling va suhbatga qo'shiling! 😊"
            )
    else:
        text = (
            f"👏 **{inviter_mention}**, guruhga yangi a'zo qo'shdingiz! 🚀\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 **Yangi a'zo:** {new_user_name}\n"
            f"📊 **Jami takliflaringiz:** **{total_invites} ta**\n"
            f"🏆 TOP taklifchilar reytingida ishtirok etmoqdasiz! (`/toptaklif`)"
        )

    try:
        msg = await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode="Markdown",
        )
        # Xabar 1 daqiqa (60 soniya) turadi
        asyncio.create_task(auto_delete_msg(msg, 60))
    except Exception as e:
        logger.debug(f"Taklif xabarini yuborishda xatolik: {e}")


async def send_welcome_message(bot: Bot, chat_id: int, chat_title: str, new_user: User, group: dict) -> None:
    """Kutib olish (Welcome) xabarini yuborish."""
    if group.get("welcome_enabled", 1) != 1:
        return

    # Takroriy welcome xabarini yubormaslik (chat_member va new_chat_members bir vaqtda kelganda)
    now_t = asyncio.get_event_loop().time()
    w_key = (chat_id, new_user.id)
    if now_t - RECENT_WELCOMES.get(w_key, 0.0) < 5.0:
        return
    RECENT_WELCOMES[w_key] = now_t

    clean_name = (
        (new_user.full_name or "Foydalanuvchi")
        .replace("[", "(")
        .replace("]", ")")
        .replace("*", "")
        .replace("_", " ")
        .replace("`", "'")
    )
    mention = f"[{clean_name}](tg://user?id={new_user.id})"
    group_title = chat_title or "guruhimiz"
    u_name = f"@{new_user.username}" if new_user.username else clean_name

    old_welcome_id = await db.get_last_welcome_msg_id(chat_id)
    if old_welcome_id:
        try:
            await bot.delete_message(chat_id=chat_id, message_id=old_welcome_id)
        except Exception:
            pass

    members_cnt = None
    try:
        members_cnt = await bot.get_chat_member_count(chat_id)
    except Exception:
        pass

    chat_desc = ""
    try:
        chat_info = await bot.get_chat(chat_id)
        chat_desc = chat_info.description or ""
    except Exception:
        pass

    min_req = int(group.get("min_invites") or 0)
    if min_req > 0 and group.get("invites_enabled", 1) == 1:
        req_info = f"• 👥 **Yozish talabi:** Guruhda yozish uchun kamida **{min_req} ta a'zo qo'shish shart**\n"
    else:
        req_info = "• 💬 **Yozish tartibi:** Barcha a'zolar uchun erkin muloqot\n"

    desc_info = f"• 📝 **Tavsif:** _{chat_desc[:120]}_\n" if chat_desc else ""
    members_info = f"• 👥 **Jami a'zolar:** **{members_cnt}** ta\n" if members_cnt else ""

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📜 Qoidalar", callback_data="btn_rules"),
                InlineKeyboardButton(text="📊 Takliflarim", callback_data="btn_my_invites"),
            ],
            [
                InlineKeyboardButton(text="🏆 Faollar Reytingi", callback_data="btn_show_rating"),
            ],
        ]
    )

    custom_tpl = await db.get_custom_welcome(chat_id)
    if custom_tpl:
        welcome_text = (
            custom_tpl.replace("{name}", mention)
            .replace("{title}", group_title)
            .replace("{username}", u_name)
            .replace("{first_name}", new_user.first_name or "")
            .replace("{members}", str(members_cnt or ""))
            .replace("{rules}", req_info)
        )
    else:
        welcome_text = (
            f"✨ **XUSH KELIBSIZ GURUHIMIZGA!** ✨\n"
            f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"👋 **Assalomu alaykum, {mention}!**\n\n"
            f"🎉 **«{group_title}»** guruhimizga xush kelibsiz!\n\n"
            f"📋 **Guruh haqida ma'lumot:**\n"
            f"{members_info}"
            f"{desc_info}"
            f"{req_info}"
            f"• 🛡️ **Xavfsizlik:** Guruhda reklama, haqorat, so'kinish va viruslar qat'iyan taqiqlangan!\n\n"
            f"💬 *Marhamat, guruhimiz qoidalari bilan tanishib chiqing va samimiy suhbatda bo'ling!* 😊"
        )

    try:
        welcome_msg = await bot.send_message(
            chat_id=chat_id,
            text=welcome_text,
            parse_mode="Markdown",
            reply_markup=kb,
            disable_web_page_preview=True,
        )
    except Exception:
        clean_welcome = welcome_text.replace("*", "").replace("`", "").replace("_", "")
        welcome_msg = await bot.send_message(
            chat_id=chat_id,
            text=clean_welcome,
            reply_markup=kb,
            disable_web_page_preview=True,
        )
    await db.set_last_welcome_msg_id(chat_id, welcome_msg.message_id)
    asyncio.create_task(auto_delete_msg(welcome_msg, 60))


# ── Foydalanuvchilar qo'shilganda yoki kirganda (chat_member yangilanishi) ──
@router.chat_member()
async def on_user_chat_member_updated(event: ChatMemberUpdated, bot: Bot) -> None:
    if event.chat.type in ("private",):
        return

    old_status = event.old_chat_member.status
    new_status = event.new_chat_member.status

    was_member = old_status in ("member", "administrator")
    is_now_member = new_status in ("member", "administrator", "restricted")

    # Yangi a'zo qo'shilgan yoki kirgan holat
    if not was_member and is_now_member:
        new_user = event.new_chat_member.user
        actor = event.from_user

        bot_info = await bot.get_me()
        if new_user.id == bot_info.id or new_user.is_bot:
            return

        group = await db.get_or_create_group(event.chat.id, event.chat.title or "")

        # 1. Boshqa foydalanuvchi taklif qilgan bo'lsa (Taklif / Invite)
        if actor and actor.id != new_user.id and not actor.is_bot:
            is_new, total_invites = await db.record_invite(
                chat_id=event.chat.id,
                inviter_id=actor.id,
                invited_id=new_user.id,
                inviter_name=actor.full_name,
                inviter_username=actor.username,
            )
            if is_new:
                await send_invite_notification(
                    bot=bot,
                    chat_id=event.chat.id,
                    inviter=actor,
                    new_user=new_user,
                    total_invites=total_invites,
                    group=group,
                )

        # 2. Xush kelibsiz (Welcome) xabari yuborish
        await send_welcome_message(
            bot=bot,
            chat_id=event.chat.id,
            chat_title=event.chat.title or "guruhimiz",
            new_user=new_user,
            group=group,
        )


# ── Yangi a'zolar qo'shilganda (Message xizmati orqali) ──────────────
@router.message(F.new_chat_members)
async def on_new_chat_members(message: Message, bot: Bot) -> None:
    # 1. "Falonchi guruhga qo'shildi" (Kirdi) xizmat xabarini darhol o'chirish
    try:
        await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
    except Exception as e:
        logger.debug(f"Kirdi xizmat xabarini o'chirishda: {e}")

    bot_info = await bot.get_me()

    # Agar yangi qo'shilganlar orasida botning o'zi bo'lsa:
    if any(new_u.id == bot_info.id for new_u in message.new_chat_members):
        await send_group_intro(bot, message.chat.id, message.chat.title or "guruhingiz")
        return

    inviter = message.from_user
    group = await db.get_or_create_group(message.chat.id, message.chat.title or "")

    for new_user in message.new_chat_members:
        if new_user.is_bot:
            continue

        # Agar boshqa foydalanuvchi taklif qilgan bo'lsa (o'zi kirmagan bo'lsa)
        if inviter and inviter.id != new_user.id and not inviter.is_bot:
            is_new, total_invites = await db.record_invite(
                chat_id=message.chat.id,
                inviter_id=inviter.id,
                invited_id=new_user.id,
                inviter_name=inviter.full_name,
                inviter_username=inviter.username,
            )

            if is_new:
                await send_invite_notification(
                    bot=bot,
                    chat_id=message.chat.id,
                    inviter=inviter,
                    new_user=new_user,
                    total_invites=total_invites,
                    group=group,
                )

        await send_welcome_message(
            bot=bot,
            chat_id=message.chat.id,
            chat_title=message.chat.title or "guruhimiz",
            new_user=new_user,
            group=group,
        )


# ── Foydalanuvchi guruhdan chiqqanda (Chiqdi) va barcha xizmat xabarlari ──
@router.message(
    F.left_chat_member
    | F.pinned_message
    | F.new_chat_title
    | F.new_chat_photo
    | F.delete_chat_photo
    | F.video_chat_started
    | F.video_chat_ended
    | F.video_chat_participants_invited
    | F.video_chat_scheduled
    | F.message_auto_delete_timer_changed
)
async def on_service_message(message: Message, bot: Bot) -> None:
    """Guruhdagi chiqdi va barcha keraksiz xizmat xabarlarini darhol o'chirish."""
    try:
        await bot.delete_message(chat_id=message.chat.id, message_id=message.message_id)
    except Exception as e:
        logger.debug(f"Xizmat xabarini o'chirishda: {e}")


# ── Inline tugmalar callbacklari ────────────────────────────────────
@router.callback_query(F.data == "btn_open_settings")
async def cb_open_settings(call: CallbackQuery, bot: Bot) -> None:
    if not call.message or not call.from_user:
        return

    if not await is_admin(bot, call.message.chat.id, call.from_user.id):
        await call.answer("❌ Bu sozlamalarni faqat guruh adminlari o'zgartirishi mumkin!", show_alert=True)
        return

    group = await db.get_or_create_group(call.message.chat.id)
    kb = get_settings_keyboard(group)
    await call.message.reply(
        f"⚙️ **'{call.message.chat.title}' guruhi sozlamalari:**\n\n"
        f"Quyidagi tugmalar orqali bot funksiyalarini yoqishingiz yoki o'chirishingiz mumkin:",
        reply_markup=kb,
    )
    await call.answer()


@router.callback_query(F.data == "btn_rules")
async def cb_rules(call: CallbackQuery) -> None:
    rules = await db.get_group_rules(call.message.chat.id)
    if not rules:
        rules = (
            "📜 **GURUH QOIDALARI**\n\n"
            "1️⃣ **HURMAT** — Har bir a'zoga hurmat bilan muomala qiling. "
            "Haqorat, kamsitish, millat yoki dinga tegishli so'zlar qat'iyan taqiqlanadi.\n\n"
            "2️⃣ **SPAM & REKLAMA** — Ruxsatsiz reklama, havola (link), kanal va guruh targ'iboti taqiqlanadi. "
            "Qoidabuzarlar darhol guruhdan chiqariladi.\n\n"
            "3️⃣ **SIYOSAT & ZIDDIYAT** — Siyosiy tortishuvlar, urush targ'iboti va provokatsion xabarlar taqiqlanadi.\n\n"
            "4️⃣ **YOLG'ON AXBOROT** — Tasdiqlanmagan yangilik, soxta skrinshotlar va yolg'on ma'lumot "
            "tarqatish taqiqlanadi. Manbani tekshiring!\n\n"
            "5️⃣ **APK & ZARARLI FAYLLAR** — Har qanday .apk, .exe va noma'lum fayl yuborish taqiqlanadi. "
            "Telegram orqali tarqalayotgan viruslardan ehtiyot bo'ling!\n\n"
            "6️⃣ **SHAXSIY MA'LUMOT** — Boshqalarning telefon raqami, manzili yoki shaxsiy ma'lumotlarini "
            "ruxsatsiz tarqatish (doxing) taqiqlanadi.\n\n"
            "7️⃣ **FIRIBGARLIK (SCAM)** — \"Pul ishlash\", \"investitsiya\", \"kripto\" bahonasida aldash "
            "urinishlari darhol ban bilan jazolanadi.\n\n"
            "8️⃣ **FORWARD XABARLAR** — Boshqa kanal va guruhlardan xabarlarni forward qilish taqiqlanadi.\n\n"
            "9️⃣ **18+ KONTENT** — Voyaga etmaganlar uchun noma'qul, zo'ravonlik va shok materiallar mutlaqo taqiqlanadi.\n\n"
            "🔟 **DEEPFAKE & AI SOXTA KONTENT** — AI yordamida yaratilgan soxta surat/video tarqatish taqiqlanadi.\n\n"
            "⚠️ **OGOHLANTIRISH TIZIMI:**\n"
            "• 1-ogohlantirish: Xabar o'chiriladi\n"
            "• 2-ogohlantirish: 24 soat sukut (yozish taqiqlanadi)\n"
            "• 3-ogohlantirish: Guruhdan chiqarish\n\n"
            "✅ *Guruhda yozish uchun qoidalarni qabul qilgan deb hisoblanasiz!*"
        )
    await call.answer()
    await call.message.reply(rules, parse_mode="Markdown")


@router.callback_query(F.data == "btn_show_rating")
async def cb_show_rating(call: CallbackQuery) -> None:
    top_users = await db.get_top_users(call.message.chat.id, limit=5)
    if not top_users:
        await call.answer("Guruhda hali xabarlar statistikasi mavjud emas.", show_alert=True)
        return
    text = "🏆 **Guruhning eng faol a'zolari (TOP-5):**\n\n"
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]
    for i, u in enumerate(top_users):
        name = u.get("full_name") or "Foydalanuvchi"
        cnt = u.get("message_count", 0)
        text += f"{medals[i]} **{name}** — {cnt} ta xabar\n"
    await call.answer()
    await call.message.reply(text, parse_mode="Markdown")


@router.callback_query(F.data == "btn_my_invites")
async def cb_my_invites(call: CallbackQuery) -> None:
    if not call.message or not call.from_user:
        return
    group = await db.get_or_create_group(call.message.chat.id)
    min_inv = group.get("min_invites", 0)
    cnt = await db.get_user_invites(call.message.chat.id, call.from_user.id)
    if min_inv > 0:
        if cnt >= min_inv:
            msg = f"✅ Siz guruh talabini to'liq bajargansiz ({cnt}/{min_inv} ta a'zo qo'shgansiz)!"
        else:
            msg = f"⚠️ Siz {cnt}/{min_inv} ta a'zo qo'shgansiz. Yana {min_inv - cnt} ta do'stingizni taklif qilishingiz kerak."
    else:
        msg = f"📊 Siz guruhga {cnt} ta a'zo taklif qilgansiz."
    await call.answer(msg, show_alert=True)


# ── Kanal yoki guruhga a'zo bo'lish uchun ariza (Join Request / Zayafka) ──
@router.chat_join_request()
async def on_chat_join_request(event: ChatJoinRequest, bot: Bot) -> None:
    """Foydalanuvchi ariza (zayafka) yuborganida avtomatik qabul qilish va bazaga kiritish."""
    try:
        user_id = event.from_user.id
        await db.record_join_request(user_id, str(event.chat.id))
        if event.chat.username:
            await db.record_join_request(user_id, f"@{event.chat.username}".lower())
            await db.record_join_request(user_id, event.chat.username.lower())
        logger.info(f"Join request qayd etildi: user {user_id} -> {event.chat.type} {event.chat.id} ({event.chat.title})")

        group = await db.get_or_create_group(event.chat.id, event.chat.title or "")
        auto_approve = group.get("auto_approve_joins")

        # Agar guruh/kanalda zayafkalarni avtomatik qabul qilish yoqilgan bo'lsa (standart: 1)
        if auto_approve is None or int(auto_approve) == 1:
            try:
                await bot.approve_chat_join_request(chat_id=event.chat.id, user_id=event.from_user.id)
                logger.info(f"✅ Zayafka avtomatik tasdiqlandi: {event.from_user.full_name} -> {event.chat.title}")

                # Foydalanuvchiga shaxsiy xabar yuborish (agar bot bilan muloqot boshlagan bo'lsa)
                try:
                    is_channel = event.chat.type == "channel"
                    chat_type_label = "kanaliga" if is_channel else "guruhiga"
                    chat_title = event.chat.title or ("Kanal" if is_channel else "Guruh")

                    kb = None
                    if event.chat.username:
                        chat_url = f"https://t.me/{event.chat.username}"
                        kb = InlineKeyboardMarkup(
                            inline_keyboard=[[InlineKeyboardButton(text="Kirish 🚀", url=chat_url)]]
                        )

                    await bot.send_message(
                        chat_id=event.from_user.id,
                        text=(
                            f"💎 **ARIZANGIZ TASDIQLANDI!** 🚀\n"
                            f"━━━━━━━━━━━━━━━━━━━━━━\n\n"
                            f"Assalomu alaykum, **{event.from_user.full_name}**!\n\n"
                            f"Sizning «**{chat_title}**» {chat_type_label} a'zo bo'lish arizangiz avtomatik qabul qilindi. "
                            f"Xush kelibsiz! 😊✨"
                        ),
                        reply_markup=kb,
                        parse_mode="Markdown",
                    )
                except Exception:
                    pass
            except Exception as approve_err:
                err_text = str(approve_err).lower()
                if "user_already_participant" in err_text or "hide_requester_missing" in err_text:
                    logger.info(f"Zayafka holati: foydalanuvchi allaqachon a'zo yoki ariza o'zgartirilgan ({event.from_user.id})")
                elif "rights" in err_text or "admin" in err_text:
                    logger.warning(f"⚠️ Botda '{event.chat.title}' chatida arizani qabul qilish huquqi (can_invite_users) yetarli emas!")
                else:
                    logger.warning(f"Zayafkani tasdiqlashda xatolik: {approve_err}")
    except Exception as e:
        logger.warning(f"Join request qayd etishda umumiy xatolik: {e}")



