from __future__ import annotations

import asyncio
import logging
from aiogram import Router, Bot, F
from aiogram.types import (
    Message,
    CallbackQuery,
    ChatMemberUpdated,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)
from database.db import db
from filters.admin_filter import is_admin
from handlers.admin import get_settings_keyboard

logger = logging.getLogger(__name__)
router = Router(name="group_events")


async def auto_delete_msg(msg: Message, delay: int = 90) -> None:
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
        f"👋 **Assalomu alaykum, '{chat_title}' guruhi a'zolari va administratorlari!**\n\n"
        "Men — **Guruhchi** botiman! Guruhda tartib saqlash, spamlardan tozalash va a'zolar sonini faol ko'paytirishda sizga xizmat qilaman! 🛡🤖\n\n"
        "✨ **Mening asosiy imkoniyatlarim:**\n"
        "• 👥 **Majburiy a'zo talabi:** `/odam 5` (a'zolar guruhda yozishlari uchun 5 ta odam qo'shishi shart qilinadi)\n"
        "• 📊 **A'zolarni hisoblash:** `/takliflarim` va `/taklifchilar` (TOP-10 taklifchilar)\n"
        "• 🛡️ **Antispam & Antilink:** Reklama, kazino va begona linklarni avtomatik o'chirish\n"
        "• 🧹 **Guruhni tozalash:** `/tozala 20` (keraksiz xabarlarni tozalash)\n"
        "• ⚠️ **Jazo choralari:** `/ogohlantir`, `/chekla`, `/hayda`\n"
        "• 📈 **Statistika & Reyting:** `/statistika` va `/reyting`\n"
        "• ❓ **Avto-javoblar:** `/savollar` va `/savolqoshish`\n\n"
        "⚠️ **DIQQAT (Muhim qadam):**\n"
        "Men to'liq va benuqson ishlashim uchun menga guruh sozlamalaridan **Administrator (Admin)** huquqlarini bering:\n"
        "✅ *Xabarlarni o'chirish (Delete messages)*\n"
        "✅ *Foydalanuvchilarni cheklash (Restrict members)*\n"
        "✅ *Xabarlarni qadash (Pin messages)*\n\n"
        "Barcha buyruqlarni ko'rish: `/yordam`\n"
        "Sozlamalarni ochish: `/sozlamalar`"
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
            await send_group_intro(bot, event.chat.id, event.chat.title or "guruhingiz")


# ── Yangi a'zolar qo'shilganda ──────────────────────────────────────
@router.message(F.new_chat_members)
async def on_new_chat_members(message: Message, bot: Bot) -> None:
    # 1. "Falonchi guruhga qo'shildi" xizmat xabarini o'chirish
    try:
        await message.delete()
    except Exception:
        pass

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
        if inviter and inviter.id != new_user.id:
            is_new, total_invites = await db.record_invite(
                chat_id=message.chat.id,
                inviter_id=inviter.id,
                invited_id=new_user.id,
                inviter_name=inviter.full_name,
                inviter_username=inviter.username,
            )

            if is_new:
                min_req = group.get("min_invites", 0)
                req_text = f" / {min_req}" if min_req > 0 else ""
                invite_notify = await message.answer(
                    f"👏 **{inviter.full_name}**, siz yangi a'zo ({new_user.full_name}) qo'shdingiz!\n"
                    f"📊 Jami takliflaringiz: **{total_invites}{req_text}** ta",
                    parse_mode="Markdown",
                )
                asyncio.create_task(auto_delete_msg(invite_notify, 7))

        # Kutib olish xabari (agar yoqilgan bo'lsa)
        if group.get("welcome_enabled", 1) == 1:
            mention = f"[{new_user.full_name}](tg://user?id={new_user.id})"
            group_title = message.chat.title or "guruhimiz"

            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [
                        InlineKeyboardButton(text="📜 Guruh Qoidalari", callback_data="btn_rules"),
                        InlineKeyboardButton(text="🏆 Faollar Reytingi", callback_data="btn_show_rating"),
                    ],
                ]
            )

            min_req = group.get("min_invites", 0)
            rules_hint = (
                f"\n\n⚠️ **DIQQAT:** Guruhda xabar yozish uchun kamida **{min_req}** ta do'stingizni qo'shishingiz kerak!"
                if min_req > 0
                else ""
            )

            welcome_text = (
                f"╔══════════════════════════╗\n"
                f"   ✨ **XUSH KELIBSIZ!** ✨\n"
                f"╚══════════════════════════╝\n\n"
                f"👋 **Assalomu alaykum, {mention}!**\n\n"
                f"🎉 **«{group_title}»** guruhimizga xush kelibsiz!\n"
                f"Sizni safimizda ko'rib turganimizdan g'oyat mamnunmiz! 🤝😊\n\n"
                f"💬 *Guruhimizda samimiy va do'stona muloqot qilishingizni tilaymiz!*{rules_hint}\n\n"
                f"Qoidalar bilan tanishish uchun quyidagi tugmani bosing 👇"
            )

            welcome_msg = await message.answer(
                text=welcome_text,
                parse_mode="Markdown",
                reply_markup=kb,
                disable_web_page_preview=True,
            )
            asyncio.create_task(auto_delete_msg(welcome_msg, 90))


# ── Foydalanuvchi guruhdan chiqqanda ────────────────────────────────
@router.message(F.left_chat_member)
async def on_left_chat_member(message: Message) -> None:
    try:
        await message.delete()
    except Exception:
        pass


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
            "📜 **Standart guruh qoidalari:**\n\n"
            "1. Bir-biringizni hurmat qiling, haqorat va so'kinish taqiqlanadi.\n"
            "2. Begona havolalar (linklar) va reklama tarqatish qat'iyan man etiladi.\n"
            "3. Boshqa kanallardan xabarlarni uzatish (forward) taqiqlanadi.\n"
            "4. Har qanday APK (.apk) fayllar va viruslar man etiladi.\n"
            "5. Qoidalarni buzganlar ogohlantiriladi (/ogohlantir) yoki cheklanadi (/chekla, /hayda)."
        )
    await call.answer()
    await call.message.reply(rules, parse_mode="Markdown")


@router.callback_query(F.data == "btn_show_rating")
async def cb_show_rating(call: CallbackQuery) -> None:
    top_users = await db.get_top_active_users(call.message.chat.id, limit=5)
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
