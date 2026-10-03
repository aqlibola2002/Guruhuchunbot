from __future__ import annotations

from aiogram import Router, Bot, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

router = Router(name="common")

BOT_CAPABILITIES_TEXT = (
    "🤖 **Guruhchi Uz Bot — Guruh Nazoratchisi va Himoyachisi!** 🛡\n\n"
    "Bu bot guruhingizni tartibga solish, reklama va viruslardan tozalash hamda a'zolarni ko'paytirish uchun to'liq avtomatik ishlaydi.\n\n"
    "⚡️ **BOT NIMA QILA OLADI? (Barcha imkoniyatlari):**\n\n"
    "1️⃣ **🦠 Anti-Virus (.APK himoyasi):**\n"
    "• Hozirda Telegramda keng tarqalayotgan barcha xavfli `.apk` (virus/troyan) fayllarni avtomatik aniqlab, guruhdan darhol o'chirib tashlaydi.\n\n"
    "2️⃣ **👥 Majburiy a'zo talabi (`/odam 5`):**\n"
    "• Foydalanuvchilar guruhda yozishlari uchun belgilangan miqdorda odam qo'shishini majburiy qiladi. Qo'shmaganlarning xabari o'chiriladi.\n\n"
    "3️⃣ **📊 A'zolar va taklifchilarni sanash (`/takliflarim`, `/taklifchilar`):**\n"
    "• Kim qancha odam qo'shganini 100% aniq hisoblab boradi va eng ko'p odam qo'shganlar reytingini (TOP-10) chiqaradi.\n\n"
    "4️⃣ **🔗 Anti-Link (Begona havolalar nazorati):**\n"
    "• Guruhda begona kanal/guruh havolalari (linklar) va @username tarqatilishini to'xtatadi.\n\n"
    "5️⃣ **🚫 Anti-Spam va Reklama tozalash:**\n"
    "• Reklama va spam xabarlarni darhol o'chirib, qoidabuzarlarni jazolaydi.\n\n"
    "6️⃣ **⚠️ Jazo choralari (`/ogohlantir`, `/chekla`, `/hayda`, `/kechir`):**\n"
    "• Qoidabuzarlarga ogohlantirish berish (3/3 da avto-mute), yozishni vaqtincha cheklash (`/chekla 10m` | `2h` | `1d`) yoki butunlay chiqarish (`/hayda`).\n\n"
    "7️⃣ **🧹 Xabarlarni tozalash (`/tozala 20`):**\n"
    "• Guruhdagi istalgan miqdordagi xabarlarni bir zumda tozalab beradi.\n\n"
    "8️⃣ **📜 Guruh qoidalari (`/qoidalar`, `/yangiqoida`):**\n"
    "• Guruh a'zolariga qoidalarni ko'rsatish va adminlar tomonidan yangi qoidalarni o'rnatish.\n\n"
    "9️⃣ **📢 E'lonlar va qadash (`/elon`):**\n"
    "• Muhim matn, rasm yoki faylli e'lonlarni guruhga yuborib, avtomatik qadab (pin) qo'yadi.\n\n"
    "🔟 **📈 Statistika va Reyting (`/statistika`, `/reyting`):**\n"
    "• Guruh faolligi va eng faol yozuvchilar TOP-10 ro'yxatini yuritadi.\n\n"
    "⚙️ **Sozlamalar paneli (`/sozlamalar`):**\n"
    "• Guruh himoya tizimlarini bitta qulay tugmali menyu orqali boshqarish.\n\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    "📌 **Botni ishlatish uchun:** Guruhingizga qo'shib, unga **Administrator** huquqlarini bering!"
)


@router.message(CommandStart(ignore_case=True))
@router.message(Command("start", ignore_case=True))
async def cmd_start(message: Message, bot: Bot) -> None:
    bot_info = await bot.get_me()
    bot_username = bot_info.username or ""

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
                    text="📖 Buyruqlar qo'llanmasi",
                    callback_data="btn_help_info",
                )
            ],
        ]
    )

    if message.chat.type in ("private",):
        await message.reply(BOT_CAPABILITIES_TEXT, reply_markup=kb, parse_mode="Markdown")
    else:
        # Guruh ichida /start yozilganda ham to'liq imkoniyatlarni ko'rsatamiz
        await message.reply(BOT_CAPABILITIES_TEXT, parse_mode="Markdown")


@router.message(Command("yordam", "help", ignore_case=True))
async def cmd_help(message: Message) -> None:
    help_text = (
        "📖 **Guruhchi Boti Buyruqlari Qo'llanmasi:**\n\n"
        "👥 **Guruh A'zolari Uchun:**\n"
        "• `/start` — Bot imkoniyatlari va ma'lumotlari\n"
        "• `/odam` — Guruhda yozish uchun majburiy a'zo talabi\n"
        "• `/takliflarim` — Siz qo'shgan a'zolar soni\n"
        "• `/taklifchilar` — Eng ko'p odam qo'shganlar reytingi\n"
        "• `/reyting` — Eng faol yozuvchilar reytingi (TOP-10)\n"
        "• `/statistika` — Guruh statistikasi va holati\n"
        "• `/qoidalar` — Guruh qoidalarini ko'rish\n"
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
        "• `/elon [xabar yoki fayl]` — E'lon yuborish va avtomatik qadash (pin)\n\n"
        "🛡 **Avtomatik himoyalar:**\n"
        "• 🦠 APK virus fayllarini avtomatik o'chirish\n"
        "• 🔗 Begona Telegram havolalarini bloklash\n"
        "• 🚫 Reklama va spam xabarlarni tozalash"
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
        "4. `/odam 5` orqali a'zo qo'shish majburiyatini o'rnating.\n"
        "5. Guruhga yuborilgan barcha `.apk` viruslar va reklamalar bot tomonidan avtomatik o'chiriladi!"
    )
    await call.message.reply(help_text, parse_mode="Markdown")
    await call.answer()
