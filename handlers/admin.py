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


# ── /odam [har qanday son quyish mumkin] ───────────────────────────
@router.message(Command("odam", "setinvites"))
async def cmd_odam(message: Message, bot: Bot) -> None:
    if message.chat.type in ("private",):
        await message.reply("⚠️ Ushbu buyruq faqat guruhlarda ishlaydi!")
        return

    group = await db.get_or_create_group(message.chat.id, message.chat.title or "")
    current = group.get("min_invites", 0)

    # Agar oddiy a'zo yozsa, hozirgi talab haqida ma'lumot beramiz
    if not await is_admin(bot, message.chat.id, message.from_user.id):
        user_invites = await db.get_user_invites(message.chat.id, message.from_user.id)
        if current > 0:
            left = max(0, current - user_invites)
            await message.reply(
                f"👥 **Majburiy a'zo qo'shish talabi:**\n\n"
                f"📌 Guruhda yozish uchun har bir a'zo kamida **{current}** ta odam qo'shishi shart.\n"
                f"📊 Siz qo'shgan a'zolar: **{user_invites} / {current}** ta\n"
                f"➕ Qolgan: **{left}** ta\n\n"
                f"💡 O'z takliflaringizni to'liq ko'rish uchun: `/takliflarim`",
                parse_mode="Markdown",
            )
        else:
            await message.reply(
                "👥 Bu guruhda hozirda majburiy a'zo qo'shish talabi yo'q (erkin muloqot).",
                parse_mode="Markdown",
            )
        return

    # Admin tomonidan chaqirilganda
    parts = (message.text or "").split()
    if len(parts) < 2 or not parts[1].isdigit():
        await message.reply(
            f"👥 **Majburiy a'zo qo'shish talabi:**\n\n"
            f"📌 Hozirgi talab: **{current} ta**\n\n"
            "Har qanday son qo'yishingiz mumkin:\n"
            "• `/odam 5` — Har bir a'zo guruhda yozish uchun 5 ta odam qo'shishi shart bo'ladi.\n"
            "• `/odam 10` — Talabni 10 taga oshirish.\n"
            "• `/odam 0` — Cheklovni butunlay o'chirish (hammaga ruxsat).",
            parse_mode="Markdown",
        )
        return

    count = int(parts[1])
    await db.set_min_invites(message.chat.id, count)

    if count > 0:
        await message.reply(
            f"✅ **Majburiy a'zo talabi {count} ta qilib belgilandi!**\n\n"
            f"Endi oddiy foydalanuvchilar guruhda yozishlari uchun kamida **{count}** ta odam qo'shishlari shart bo'ladi.\n"
            f"Takliflarni tekshirish uchun: `/takliflarim`",
            parse_mode="Markdown",
        )
    else:
        await message.reply(
            "🔓 **Majburiy a'zo qo'shish talabi o'chirildi!**\nEndi barcha a'zolar erkin yoza oladi.",
            parse_mode="Markdown",
        )


# ── /ogohlantir [@ id yoki relp] ────────────────────────────────────
@router.message(Command("ogohlantir", "ogohlantirish", "warn"))
async def cmd_warn(message: Message, bot: Bot) -> None:
    if message.chat.type in ("private",):
        await message.reply("⚠️ Bu buyruq faqat guruhlarda ishlaydi!")
        return

    if not await is_admin(bot, message.chat.id, message.from_user.id):
        await message.reply("❌ Bu buyruq faqat guruh administratorlari uchun!")
        return

    target = await resolve_target(message)
    if target.error:
        await message.reply(target.error, parse_mode="Markdown")
        return

    if target.user_id == bot.id:
        await message.reply("🤖 Botlarga ogohlantirish berilmaydi!")
        return

    if await is_admin(bot, message.chat.id, target.user_id):
        await message.reply("❌ Guruh adminlariga ogohlantirish berib bo'lmaydi!")
        return

    reason = target.remaining_text.strip() or "Guruh qoidalarini buzganlik uchun"
    warn_count = await db.add_warn(message.chat.id, target.user_id, reason)

    # 3 ta ogohlantirishga yetsa — 24 soatga mute qilish
    if warn_count >= MAX_WARNS:
        until_date = datetime.now(timezone.utc) + timedelta(hours=24)
        try:
            await bot.restrict_chat_member(
                chat_id=message.chat.id,
                user_id=target.user_id,
                permissions=ChatPermissions(can_send_messages=False),
                until_date=until_date,
            )
            await db.reset_warns(message.chat.id, target.user_id)
            await db.record_punishment(message.chat.id, "mute")

            await message.reply(
                f"🚫 **{target.full_name}** ({warn_count}/{MAX_WARNS}) marta ogohlantirish oldi "
                f"va **24 soatga** yozishdan cheklandi!\n"
                f"📝 Sabab: {reason}\n"
                f"👮‍♂️ Admin: {message.from_user.full_name}",
                parse_mode="Markdown",
            )
        except Exception as e:
            await message.reply(f"❌ Cheklashda xatolik: {e}\n(Bot adminligini va ruxsatlarini tekshiring).")
    else:
        left = MAX_WARNS - warn_count
        await message.reply(
            f"⚠️ **{target.full_name}** ogohlantirildi! ({warn_count}/{MAX_WARNS})\n"
            f"📝 Sabab: {reason}\n"
            f"❗️ Yana {left} ta ogohlantirishdan keyin yozish cheklanadi.\n"
            f"👮‍♂️ Admin: {message.from_user.full_name}",
            parse_mode="Markdown",
        )


# ── /chekla [ relp 10m|2h|1d] ──────────────────────────────────────
@router.message(Command("chekla", "yopish", "mute"))
async def cmd_mute(message: Message, bot: Bot) -> None:
    if message.chat.type in ("private",):
        await message.reply("⚠️ Bu buyruq faqat guruhlarda ishlaydi!")
        return

    if not await is_admin(bot, message.chat.id, message.from_user.id):
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

    if target.user_id == bot.id or await is_admin(bot, message.chat.id, target.user_id):
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
            f"🔇 **{target.full_name}** yozishdan vaqtincha cheklandi!\n"
            f"⏳ Muddat: **{duration_str}**\n"
            f"📝 Sabab: {reason}\n"
            f"👮‍♂️ Admin: {message.from_user.full_name}",
            parse_mode="Markdown",
        )
    except Exception as e:
        await message.reply(f"❌ Xatolik yuz berdi: {e}\n(Bot guruhda admin ekanligiga va 'Restrict members' huquqi borligiga ishonch hosil qiling).")


# ── /hayda [bloklash @ id yoki relp] ─────────────────────────────────
@router.message(Command("hayda", "haydash", "ban"))
async def cmd_ban(message: Message, bot: Bot) -> None:
    if message.chat.type in ("private",):
        await message.reply("⚠️ Bu buyruq faqat guruhlarda ishlaydi!")
        return

    if not await is_admin(bot, message.chat.id, message.from_user.id):
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

    if target.user_id == bot.id or await is_admin(bot, message.chat.id, target.user_id):
        await message.reply("❌ Bot yoki guruh adminini ban qilib bo'lmaydi!")
        return

    reason = target.remaining_text.strip() or "Guruhdan chetlatildi"

    try:
        await bot.ban_chat_member(chat_id=message.chat.id, user_id=target.user_id)
        await db.record_punishment(message.chat.id, "ban")
        await message.reply(
            f"🚫 **{target.full_name}** guruhdan chiqarildi va bloklandi (Ban)!\n"
            f"📝 Sabab: {reason}\n"
            f"👮‍♂️ Admin: {message.from_user.full_name}",
            parse_mode="Markdown",
        )
    except Exception as e:
        await message.reply(f"❌ Ban qilishda xatolik: {e}")


# ── /kechir [blokdan ochish @ id yoki rel] ───────────────────────────
@router.message(Command("kechir", "unban", "och", "ochish", "qaytish"))
async def cmd_unban_and_unmute(message: Message, bot: Bot) -> None:
    if message.chat.type in ("private",):
        await message.reply("⚠️ Bu buyruq faqat guruhlarda ishlaydi!")
        return

    if not await is_admin(bot, message.chat.id, message.from_user.id):
        await message.reply("❌ Bu buyruq faqat guruh administratorlari uchun!")
        return

    target = await resolve_target(message)
    if target.error:
        await message.reply(
            "🔓 **Blokdan va cheklovdan ochish (/kechir):**\n\n"
            "Format:\n"
            "• Foydalanuvchi xabariga **Reply** qilib: `/kechir`\n"
            "• Yoki `@username` orqali: `/kechir @foydalanuvchi`\n"
            "• Yoki Telegram **ID** orqali: `/kechir 123456789`",
            parse_mode="Markdown",
        )
        return

    try:
        # Bandan chiqarish
        await bot.unban_chat_member(chat_id=message.chat.id, user_id=target.user_id, only_if_banned=True)
    except Exception:
        pass

    try:
        # Cheklovlarni (mute) bekor qilish
        await bot.restrict_chat_member(
            chat_id=message.chat.id,
            user_id=target.user_id,
            permissions=ChatPermissions(
                can_send_messages=True,
                can_send_other_messages=True,
                can_add_web_page_previews=True,
                can_send_polls=True,
            ),
        )
    except Exception:
        pass

    # Ogohlantirishlarni nolga tushirish
    await db.reset_warns(message.chat.id, target.user_id)

    await message.reply(
        f"🔓 **{target.full_name}** blokdan va barcha cheklovlardan ochildi! Endi guruhda bemalol yoza oladi.\n"
        f"👮‍♂️ Admin: {message.from_user.full_name}",
        parse_mode="Markdown",
    )


# ── /tozala [Xabarlarni tozalashi] ─────────────────────────────────
@router.message(Command("tozala", "tozalash", "clear"))
async def cmd_clear(message: Message, bot: Bot) -> None:
    if message.chat.type in ("private",):
        await message.reply("⚠️ Bu buyruq faqat guruhlarda ishlaydi!")
        return

    if not await is_admin(bot, message.chat.id, message.from_user.id):
        await message.reply("❌ Bu buyruq faqat guruh administratorlari uchun!")
        return

    parts = (message.text or "").split()
    count = 10
    if len(parts) > 1 and parts[1].isdigit():
        count = min(int(parts[1]), 100)

    # Adminning o'z buyruq xabarini o'chirish
    try:
        await message.delete()
    except Exception:
        pass

    deleted = 0
    current_msg_id = message.message_id
    msg_ids = [current_msg_id - i for i in range(1, count + 1) if current_msg_id - i > 0]

    try:
        await bot.delete_messages(chat_id=message.chat.id, message_ids=msg_ids)
        deleted = len(msg_ids)
    except Exception:
        for mid in msg_ids:
            try:
                await bot.delete_message(chat_id=message.chat.id, message_id=mid)
                deleted += 1
            except Exception:
                pass

    notify = await bot.send_message(
        chat_id=message.chat.id,
        text=f"🧹 **{deleted} ta xabar muvaffaqiyatli tozalandi!**",
        parse_mode="Markdown",
    )
    asyncio.create_task(auto_delete_message(notify, 4))


# ── /sozlamalar [Himoya sozlamalarini boshqarish] ───────────────────
def get_settings_keyboard(group: dict) -> InlineKeyboardMarkup:
    def mark(val: int) -> str:
        return "✅ Yoqilgan" if val == 1 else "❌ O'chirilgan"

    min_inv = group.get("min_invites", 0)
    inv_text = f"👥 Majburiy a'zo ({min_inv} ta): {mark(group.get('invites_enabled', 1))}"

    kb = [
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


@router.message(Command("sozlamalar", "settings"))
async def cmd_settings(message: Message, bot: Bot) -> None:
    if message.chat.type in ("private",):
        await message.reply("⚠️ Sozlamalar faqat guruhlarda adminlar uchun ochiladi.")
        return

    if not await is_admin(bot, message.chat.id, message.from_user.id):
        await message.reply("❌ Bu buyruq faqat guruh administratorlari uchun!")
        return

    group = await db.get_or_create_group(message.chat.id, message.chat.title or "")
    kb = get_settings_keyboard(group)
    await message.reply(
        f"⚙️ **'{message.chat.title}' guruhi himoya sozlamalari:**\n\n"
        f"Quyidagi tugmalar orqali xavfsizlik va nazorat funksiyalarini boshqaring:",
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

    setting_key = call.data.replace("toggle_", "") + "_enabled"
    group = await db.get_or_create_group(call.message.chat.id)
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


# ── /yangiqoida [matn avtomatik quyishilishi kerak va admin uzi tahrirlashi mumkin] ──
@router.message(Command("yangiqoida", "setrules"))
async def cmd_setrules(message: Message, bot: Bot) -> None:
    if message.chat.type in ("private",):
        await message.reply("⚠️ Bu buyruq faqat guruhlarda ishlaydi!")
        return

    if not await is_admin(bot, message.chat.id, message.from_user.id):
        await message.reply("❌ Bu buyruq faqat guruh administratorlari uchun!")
        return

    parts = (message.text or "").split(maxsplit=1)
    if len(parts) < 2:
        current_rules = await db.get_group_rules(message.chat.id)
        current_display = f"\n\n📌 **Hozirgi qoidalar:**\n{current_rules}" if current_rules else ""

        await message.reply(
            f"📝 **Guruhga yangi qoidalar o'rnatish:**\n\n"
            f"Format:\n`/yangiqoida [qoidalar matni]`\n\n"
            f"💡 Masalan quyidagi namunadan nusxa olib, tahrirlab yuboring:\n"
            f"`/yangiqoida 1. Bir-biringizni hurmat qiling, haqorat taqiqlanadi.\n"
            f"2. Begona guruh havolalari (linklar) va reklama man etiladi.\n"
            f"3. Guruh mavzusiga mos fikr bildiring.\n"
            f"4. Qoidalarni buzganlar guruhdan chetlatiladi.`"
            f"{current_display}\n\n"
            f"Ko'rish uchun: `/qoidalar`",
            parse_mode="Markdown",
        )
        return

    new_rules = parts[1].strip()
    await db.set_group_rules(message.chat.id, new_rules)
    await message.reply(
        "✅ **Guruh qoidalari muvaffaqiyatli saqlandi!**\n\n"
        "Barcha a'zolar `/qoidalar` buyrug'i orqali qoidalar bilan tanishishlari mumkin.",
        parse_mode="Markdown",
    )


# ── /elon [har qanday xabar fayl bulishi mumkin guruhga qadab quyishi kerak] ──
@router.message(Command("elon", "broadcast"))
async def cmd_broadcast(message: Message, bot: Bot) -> None:
    if message.chat.type in ("private",):
        await message.reply("⚠️ E'lon berish faqat guruhlarda ishlaydi!")
        return

    if not await is_admin(bot, message.chat.id, message.from_user.id):
        await message.reply("❌ Bu buyruq faqat guruh administratorlari uchun!")
        return

    # 1. Agar biror xabar yoki faylga Reply qilingan bo'lsa
    if message.reply_to_message:
        target_msg = message.reply_to_message
        try:
            await bot.pin_chat_message(
                chat_id=message.chat.id,
                message_id=target_msg.message_id,
                notify=True,
            )
            # Adminning /elon buyruq xabarini o'chirish
            try:
                await message.delete()
            except Exception:
                pass

            notify = await bot.send_message(
                chat_id=message.chat.id,
                text="📢 **E'lon muvaffaqiyatli qadab qo'yildi!** 📌",
                parse_mode="Markdown",
            )
            asyncio.create_task(auto_delete_message(notify, 5))
            return
        except Exception as e:
            await message.reply(f"❌ Xabarni qadashda xatolik yuz berdi: {e}\n(Bot adminligini va 'Pin messages' huquqi borligini tekshiring).")
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
            await bot.pin_chat_message(chat_id=message.chat.id, message_id=elon_msg.message_id, notify=True)
        except Exception:
            pass
        return

    # 3. Agar rasm/video/fayl bilan birga /elon yozilgan bo'lsa
    if message.photo or message.video or message.document or message.audio or message.voice:
        try:
            await bot.pin_chat_message(chat_id=message.chat.id, message_id=message.message_id, notify=True)
            notify = await bot.send_message(
                chat_id=message.chat.id,
                text="📢 **Faylli e'lon qadab qo'yildi!** 📌",
                parse_mode="Markdown",
            )
            asyncio.create_task(auto_delete_message(notify, 5))
            return
        except Exception as e:
            await message.reply(f"❌ Faylni qadashda xatolik: {e}")
            return

    # Agar hech narsa ko'rsatilmagan bo'lsa — yo'riqnoma ko'rsatamiz
    await message.reply(
        "📢 **E'lon yuborish va qadash (Pin):**\n\n"
        "• **Matnli e'lon:** `/elon [E'lon matni]`\n"
        "• **Fayl, rasm yoki videoni e'lon qilish:**\n"
        "  Har qanday fayl yoki xabarga **Reply** qilib `/elon` deb yozing!\n"
        "• **Yoki fayl yuborayotganda** izohiga `/elon` deb yozing.\n\n"
        "📌 Bot e'lonni barcha a'zolar ko'rishi uchun avtomatik tarzda guruhga qadab qo'yadi!",
        parse_mode="Markdown",
    )
