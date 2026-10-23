from __future__ import annotations

from aiogram import Router, Bot, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

router = Router(name="common")

BOT_CAPABILITIES_TEXT = (
    "🤖 **Guruhchi Uz Bot — Zamonaviy Guruh Nazoratchisi va Himoyachisi!** 🛡\n\n"
    "Bu bot guruhingizni tartibga solish, reklama va viruslardan tozalash, spamer va bot hujumlaridan himoya qilish hamda a'zolarni ko'paytirish uchun to'liq avtomatik ishlaydi.\n\n"
    "⚡️ **BOT NIMA QILA OLADI? (Barcha imkoniyatlari):**\n\n"
    "1️⃣ **🌙 Tungi rejim (`/tun`):**\n"
    "• Belgilangan vaqtda (masalan, 23:00 dan 07:00 gacha) guruhda yozishni avtomatik yopadi va tongda yana qayta ochadi.\n\n"
    "2️⃣ **⚡️ Anti-Flood (Tezkor spamdan himoya):**\n"
    "• Qisqa vaqtda ketma-ket (4 soniyada 5 tadan ortiq) xabar yuborib guruhni to'ldiruvchi spamerlarni avtomatik aniqlab, 15 daqiqaga ovozini o'chiradi (mute).\n\n"
    "3️⃣ **🈲 Arab va sharqiy yozuvlar filtri (Anti-Raid):**\n"
    "• Guruhlarni buzuvchi spambotlar tomonidan yuboriladigan arabcha/eroncha/xitoycha reklamalarni darhol yo'q qiladi.\n\n"
    "4️⃣ **🤖 Inline botlar filtri:**\n"
    "• Begona o'yin, musiqa yoki reklama inline botlari orqali (`via @bot`) yuborilgan xabarlarni tozalaydi.\n\n"
    "5️⃣ **🦠 Anti-Virus (.APK himoyasi):**\n"
    "• Hozirda Telegramda keng tarqalayotgan barcha xavfli `.apk` (virus/troyan) fayllarni avtomatik aniqlab, guruhdan darhol o'chirib tashlaydi.\n\n"
    "6️⃣ **🤬 Haqorat va so'kinish filtri (Profanity):**\n"
    "• Guruhdagi so'kinish va haqoratli so'zlarni avtomatik o'chiradi va a'zoga ogohlantirish (warn) beradi.\n\n"
    "7️⃣ **👥 Majburiy a'zo talabi (`/odam 5`) va TOP taklifchilar (`/toptaklif`):**\n"
    "• Foydalanuvchilar guruhda yozishlari uchun belgilangan miqdorda odam qo'shishini majburiy qiladi. Eng ko'p odam qo'shganlar reytingi yuritiladi.\n\n"
    "8️⃣ **📢 Majburiy kanallar (`/kanal`):**\n"
    "• A'zolar guruhda yozishi uchun homiy kanalga a'zo bo'lishini talab qilish va «A'zo bo'ldim» tugmasi orqali tekshirish.\n\n"
    "9️⃣ **⚡️ Tezkor jazo choralari (`/chekla`, `/hayda`):**\n"
    "• Qoidabuzarlarning yozishini darhol vaqtincha cheklash (`/chekla 10m` | `2h` | `1d`) yoki guruhdan butunlay chiqarish va bloklash (`/hayda`).\n\n"
    "🔟 **🧹 Xabarlarni tozalash (`/tozala 20`) va 📢 E'lonlar (`/elon`):**\n"
    "• Keraksiz xabarlarni bir zumda tozalash va muhim xabarlarni guruhga qadash (pin).\n\n"
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
        "• `/toptaklif` — Eng ko'p odam taklif qilganlar reytingi (TOP-10)\n"
        "• `/reyting` — Eng faol yozuvchilar reytingi (TOP-10)\n"
        "• `/statistika` — Guruh statistikasi va holati\n"
        "• `/yordam` — Ushbu qo'llanmani chiqarish\n\n"
        "👮‍♂️ **Guruh Adminlari Uchun:**\n"
        "• `/sozlamalar` — Himoya sozlamalarini boshqarish (Tungi rejim, Flood, Link, Arabcha va h.k.)\n"
        "• `/tun` — Tungi rejimni yoqish/o'chirish (`/tun on`, `/tun off`, `/tun 23:00 07:00`)\n"
        "• `/zayafka` — Qo'shilish arizalarini avto-qabul qilish (`/zayafka on` | `/zayafka off`)\n"
        "• `/chekla [10m|2h|1d]` — Yozishni vaqtincha cheklash (reply yoki @ / id)\n"
        "• `/hayda [@ id yoki reply]` — Guruhdan chiqarish va bloklash (Ban)\n"
        "• `/tozala [soni yoki reply]` — Xabarlarni tozalash (`/tozala 20` yoki a'zoga reply)\n"
        "• `/odam [soni]` — Majburiy a'zo talabini o'rnatish (`/odam 5` yoki `/odam 0`)\n"
        "• `/nol` — A'zoning qo'shgan odamlarini 0 ga tushirish (reply yoki @ / id)\n"
        "• `/kanal` — Majburiy kanallar ro'yxati va sozlash (`/kanal @kanalim`)\n"
        "• `/elon [xabar yoki fayl]` — E'lon yuborish va avtomatik qadash (pin)\n\n"
        "🛡 **Avtomatik himoyalar:**\n"
        "• 🌙 Tungi rejimda guruhni avtomatik yopish/ochish\n"
        "• ⚡️ Anti-Flood: 4 soniyada 5 tadan ko'p yozgan spamerlarni avto-mute qilish\n"
        "• 🈲 Arab/Sharqiy yozuvli spambot xabarlarini tozalash\n"
        "• 🤖 Inline botlar orqali spam yuborishni bloklash\n"
        "• 🦠 APK virus fayllarini avtomatik o'chirish\n"
        "• 🤬 So'kinish va haqoratlarni avtomatik o'chirish\n"
        "• 🎭 Stiker/GIF yoki ovozli xabarlarni taqiqlash\n"
        "• 🔗 Begona Telegram havolalarini bloklash"
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
