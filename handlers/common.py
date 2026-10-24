from __future__ import annotations

from aiogram import Router, Bot, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

router = Router(name="common")

BOT_CAPABILITIES_TEXT = (
    "👑 **GURUHCHI UZ — PREMIUM GURUH HIMOYA** 🛡\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "💎 **Telegram guruh va kanallari uchun eng kuchli, zamonaviy avtomatlashtirish va kiber-himoya boti!**\n\n"
    "🚀 Guruhingizni 24/7 rejimda spamerlar, viruslar (.apk) va nojo'ya reklamalardan himoya qilib, a'zolarni ko'paytirishga yordam beradi.\n\n"
    "⚙️ **ENG KUCHLI IMKONIYATLAR VA MODULLAR:**\n"
    "├ 🌙 **Tungi rejim (`/tun`):** Belgilangan soatda (23:00-07:00) guruhni avto-yopish va ertalab ochish\n"
    "├ ⚡️ **Anti-Flood tizimi:** Sekundiga tinimsiz xabar yog'diruvchi spamerlarni avtomatik mute qilish\n"
    "├ 🈲 **Anti-Raid / Arab filtri:** Arab, fors yoki sharqiy spambot xabarlarini darhol yo'q qilish\n"
    "├ 🤖 **Inline botlar filtri:** Begona inline botlar (`via @bot`) orqali yuborilgan reklamalarni tozalash\n"
    "├ 🦠 **Anti-Virus Kiber-Himoya:** Har qanday `.apk` troyan va zararli fayllarni 100% aniqlab yo'q qilish\n"
    "├ 🤬 **Haqorat va so'kinish filtri:** Madaniyatsiz so'zlarni o'chirib, qoidabuzarga avto-ogohlantirish berish\n"
    "├ 👥 **Majburiy taklif talabi (`/odam 5`):** Yozishdan oldin do'stlarini qo'shish sharti va `/toptaklif` reytingi\n"
    "├ 📢 **Homiy kanallar (`/kanal`):** Homiy kanallarga a'zolikni (yoki zayafkasini) 24/7 qat'iy nazorat qilish\n"
    "├ 📥 **Avto-Zayafka qabul (`/zayafka on`):** Qo'shilish arizalarini 1 soniyada avto-tasdiqlash\n"
    "├ 🔇 **Tezkor cheklovlar (`/chekla`, `/hayda`):** Qoidabuzarlarni vaqtincha (10m, 2h, 1d) mute yoki doimiy ban qilish\n"
    "├ 🧹 **Aqlli tozalash (`/tozala 20`):** Xabarlarni qulay progress bar bilan batamom tozalash\n"
    "├ 📌 **VIP E'lonlar (`/elon`):** Muhim xabarlar, rasm va videolarni bir zumda guruhga qadash (pin)\n"
    "└ ⚙️ **Boshqaruv menyusi (`/sozlamalar`):** Barcha funksiyalarni bitta qulay tugmali panel orqali boshqarish\n\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "📌 **Botni faollashtirish uchun:** Guruhingizga qo'shib, unga **Administrator (Admin)** huquqini bering!"
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
        "📖 **BUYRUQLAR VA QO'LLANMA (VIP)** 💎\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "👥 **GURUH A'ZOLARI UCHUN:**\n"
        "├ `/start` — Bot imkoniyatlari va boshqaruv havolasi\n"
        "├ 👤 `/profil` — Shaxsiy profilingiz (Daraja, Level, XP va reyting)\n"
        "├ 🎁 `/kunlik` — Har 24 soatda bepul kunlik bonus XP olish\n"
        "├ 🏆 `/darajalar` — Eng yuqori darajadagi faollar ligasi (TOP-10)\n"
        "├ 📊 `/takliflarim` — Siz taklif qilgan a'zolar hisoboti\n"
        "├ 🥇 `/toptaklif` — Eng ko'p do'st taklif qilganlar reytingi (TOP-10)\n"
        "├ 💬 `/reyting` — Eng faol yozuvchi a'zolar ro'yxati (TOP-10)\n"
        "├ 📈 `/statistika` — Guruh monitoringi va faollik ko'rsatkichlari\n"
        "├ 📜 `/qoidalar` — Guruh qoidalari bilan tanishish\n"
        "├ 🎲 `/zar` | `/tanga` | `/duel` — Interaktiv o'yinlar va musobaqa\n"
        "└ 🌟 `+rep` yoki `rahmat` — Foydalanuvchiga reputatsiya berish (reply)\n\n"
        "👮‍♂️ **GURUH ADMINISTRATORLARI UCHUN:**\n"
        "├ ⚙️ `/sozlamalar` — Himoya sozlamalari interaktiv boshqaruv paneli\n"
        "├ 👑 `/admin` — Bot holati va barcha tizimlar tezkor menyusi\n"
        "├ ⏳ `/sekin [10|30|60|off]` — Sekin rejim (Slowmode) o'rnatish\n"
        "├ 🎲 `/tasodif` — Konkurs va giveaway lar uchun adolatli g'olibni aniqlash\n"
        "├ 👋 `/setwelcome` — Yangi a'zolarni kutib olish matnini sozlash\n"
        "├ 🔄 `/delwelcome` — Kutib olish matnini standartga qaytarish\n"
        "├ 📜 `/yangiqoida [matn]` — Yangi guruh qoidalarini o'rnatish\n"
        "├ ⚠️ `/ogohlantir [sabab]` — A'zoga ogohlantirish (warn) berish\n"
        "├ 🕊 `/kechir` yoki `/unwarn` — Ogohlantirishni olib tashlash\n"
        "├ 🌙 `/tun` — Tungi avto-qulf rejimini boshqarish (`/tun on`, `/tun off`)\n"
        "├ 📥 `/zayafka` — Qo'shilish arizalarini avto-qabul qilish (`/zayafka on|off`)\n"
        "├ 🔇 `/chekla [10m|2h|1d]` — Yozishni vaqtincha cheklash (Mute)\n"
        "├ 🚫 `/hayda` — A'zoni guruhdan chiqarish va bloklash (Ban)\n"
        "├ 🧹 `/tozala [soni]` — Xabarlarni tozalash (`/tozala 20`)\n"
        "├ 👥 `/odam [soni]` — Majburiy a'zo talabini o'rnatish (`/odam 5`)\n"
        "├ 0️⃣ `/nol` — Qo'shgan odamlarni nolga tushirish (reply yoki @)\n"
        "├ 📢 `/kanal` | `/kanal list` — Majburiy homiy kanallarni sozlash\n"
        "└ 📌 `/elon` — Muhim xabar yoki faylni e'lon qilib darhol qadash (pin)\n\n"
        "🛡 **24/7 AVTOMATIK FAOL HIMOYA TIZIMLARI:**\n"
        "├ 🤖 Anti-Bot Captcha (Yangi a'zolar uchun 'Robot emasman' tekshiruvi)\n"
        "├ 🌙 Tungi rejimda guruhni avtomatik yopish va ertalab ochish\n"
        "├ ⚡️ Anti-Flood: Tez yozgan spamerlarni avtomatik mute qilish\n"
        "├ 🈲 Arab va sharqiy spambot xabarlarini tozalash\n"
        "├ 🤖 Begona inline botlar orqali spam yuborishni to'xtatish\n"
        "├ 🦠 APK virus va troyan fayllarni zudlik bilan yo'q qilish\n"
        "├ 🤬 Haqorat va so'kinishlarni avtomatik tozalash va jazolash\n"
        "├ 🎭 Stiker, GIF yoki ovozli xabarlarni xohishga ko'ra taqiqlash\n"
        "└ 🔗 Har qanday begona havolalar va reklamalarni to'xtatish"
    )
    await message.reply(help_text, parse_mode="Markdown")


@router.callback_query(F.data == "btn_help_info")
async def cb_help_info(call: CallbackQuery) -> None:
    help_text = (
        "🚀 **TEZKOR SOZLASH BO'YICHA YO'RIQNOMA** 💎\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "1️⃣ Botni guruhingizga qo'shing.\n"
        "2️⃣ Guruh sozlamalaridan botga **Administrator (Admin)** huquqini bering:\n"
        "   ├ Xabarlarni o'chirish (Delete messages)\n"
        "   ├ Foydalanuvchilarni cheklash (Restrict members)\n"
        "   ├ Xabarlarni qadash (Pin messages)\n"
        "   └ A'zolarni taklif qilish (Invite users / Join requests)\n"
        "3️⃣ Guruhda `/sozlamalar` yozib, kerakli himoyalarni tugmalar orqali sozlang.\n"
        "4️⃣ `/odam 5` buyrug'i orqali a'zo qo'shish talabini yoqing.\n"
        "5️⃣ Barcha zararli fayllar (.apk), reklamalar va spamlarni bot avtomatik tozalab turadi! 🛡✨"
    )
    await call.message.reply(help_text, parse_mode="Markdown")
    await call.answer()
