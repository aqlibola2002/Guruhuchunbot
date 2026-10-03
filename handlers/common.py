from __future__ import annotations

from aiogram import Router, Bot, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

router = Router(name="common")


@router.message(CommandStart())
async def cmd_start(message: Message, bot: Bot) -> None:
    bot_info = await bot.get_me()
    bot_username = bot_info.username or ""

    if message.chat.type in ("private",):
        add_to_group_url = f"https://t.me/{bot_username}?startgroup=true&admin=change_info+delete_messages+restrict_members+invite_users+pin_messages"
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="➕ Guruhga qo'shish",
                        url=add_to_group_url,
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="📖 Bot qo'llanmasi",
                        callback_data="btn_help_info",
                    )
                ],
            ]
        )

        text = (
            f"Assalomu alaykum, **{message.from_user.full_name}**! 👋\n\n"
            f"Men — **Guruhchi** himoya va nazorat botiman! 🛡🤖\n\n"
            "Guruhlaringizda quyidagi vazifalarni to'liq avtomatik bajara olaman:\n"
            "• 👥 **Majburiy a'zo talabi** (`/odam 5`)\n"
            "• 📊 **A'zolarni sanash** (`/takliflarim`, `/taklifchilar`)\n"
            "• 🛡️ Reklama va spam xabarlarni o'chirish\n"
            "• 🔗 Begona Telegram havolalarini bloklash\n"
            "• 👋 Yangi kirganlarni chiroyli kutib olish\n"
            "• 🧹 Guruh xabarlarini tozalash (`/tozala 20`)\n"
            "• ⚠️ Qoidabuzarlarni jazolash (`/ogohlantir`, `/chekla`, `/hayda`)\n"
            "• 📈 Statistika va faollar reytingi (`/statistika`, `/reyting`)\n"
            "• ❓ Guruh savol-javoblari (`/savollar`, `/qoidalar`)\n\n"
            "Meni guruhga qo'shib, **Administrator** huquqini bersangiz bas! 👇"
        )
        await message.reply(text, reply_markup=kb, parse_mode="Markdown")
    else:
        await message.reply(
            "👋 Bot guruhda faol ishlamoqda!\nBarcha buyruqlarni ko'rish uchun: `/yordam`",
            parse_mode="Markdown",
        )


@router.message(Command("yordam", "help"))
async def cmd_help(message: Message) -> None:
    help_text = (
        "📖 **Guruhchi Boti Buyruqlari Qo'llanmasi:**\n\n"
        "👥 **Guruh A'zolari Uchun:**\n"
        "• `/odam` — Guruhda yozish uchun a'zo talabini ko'rish\n"
        "• `/takliflarim` — Siz qo'shgan a'zolar soni\n"
        "• `/taklifchilar` — Eng ko'p odam qo'shganlar reytingi\n"
        "• `/reyting` — Eng faol yozuvchilar reytingi (TOP-10)\n"
        "• `/statistika` — Guruh statistikasi va holati\n"
        "• `/qoidalar` — Guruh qoidalarini ko'rish\n"
        "• `/savollar` — Ko'p beriladigan savollar va javoblar\n"
        "• `/yordam` — Ushbu qo'llanmani chiqarish\n\n"
        "👮‍♂️ **Guruh Adminlari Uchun:**\n"
        "• `/odam [soni]` — Majburiy a'zo talabini o'rnatish (`/odam 5` yoki `/odam 0`)\n"
        "• `/ogohlantir [@ id yoki reply]` — Qoidabuzarga ogohlantirish berish\n"
        "• `/chekla [10m|2h|1d]` — Yozishni vaqtincha cheklash (reply)\n"
        "• `/hayda [@ id yoki reply]` — Guruhdan chiqarish va bloklash (Ban)\n"
        "• `/kechir [@ id yoki reply]` — Blokdan va barcha cheklovlardan ochish (Unban)\n"
        "• `/tozala [soni]` — Xabarlarni tozalash (masalan: `/tozala 20`)\n"
        "• `/sozlamalar` — Himoya sozlamalarini boshqarish\n"
        "• `/yangiqoida [matn]` — Yangi guruh qoidalarini belgilash\n"
        "• `/elon [xabar yoki fayl]` — E'lon yuborish va avtomatik qadash (pin)\n"
        "• `/savolqoshish savol = javob` — Yangi avto-javob qo'shish\n"
        "• `/savolochirish kalit` — Avto-javobni o'chirish"
    )
    await message.reply(help_text, parse_mode="Markdown")


@router.callback_query(F.data == "btn_help_info")
async def cb_help_info(call: CallbackQuery) -> None:
    help_text = (
        "📖 **Qisqacha qo'llanma:**\n\n"
        "1. Botni guruhingizga qo'shing.\n"
        "2. Guruh sozlamalaridan botga **Administrator** huquqlarini bering:\n"
        "   - Xabarlarni o'chirish\n"
        "   - Foydalanuvchilarni cheklash\n"
        "   - Xabarlarni qadash (pin)\n"
        "3. Guruhda `/sozlamalar` buyrug'i orqali kerakli funksiyalarni yoqing yoki o'chiring.\n"
        "4. `/odam 5` orqali a'zo qo'shish majburiyatini o'rnating."
    )
    await call.message.reply(help_text, parse_mode="Markdown")
    await call.answer()
