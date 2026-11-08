from __future__ import annotations

from aiogram import Router, Bot, F
from aiogram.filters import CommandStart, Command
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton

from services.ui_utils import safe_reply

router = Router(name="common")

BOT_CAPABILITIES_TEXT = (
    "👑 **GURUHCHI UZ — PREMIUM GURUH HIMOYA & BOSHQARUV TIZIMI** 🛡\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "💎 **Telegram guruh va kanallari uchun eng kuchli, zamonaviy avtomatlashtirish va kiber-himoya boti!**\n\n"
    "🚀 Guruhingizni 24/7 rejimda spamerlar, viruslar (.apk) va nojo'ya reklamalardan himoya qilib, a'zolarni kengaytirishga xizmat qiladi.\n\n"
    "📋 **ASOSIY IMKONIYATLAR VA MODULLAR:**\n"
    "├ 🛡 **Kiber-Himoya:** .apk viruslar, begona linklar, reklamalar va so'kinish filtri\n"
    "├ 👥 **Majburiy Taklif:** `/odam` (a'zo qo'shmaguncha yozishni to'xtatish)\n"
    "├ 📢 **Homiy Kanallar:** Majburiy homiy kanallarni nazorat qilish (`/kanal`)\n"
    "├ 🌙 **Tungi Rejim:** Belgilangan soatda guruhni avto-qulflash (`/tun`)\n"
    "├ 📥 **Avto-Zayafka:** Qo'shilish so'rovlarini 1 soniyada tasdiqlash (`/zayafka`)\n"
    "├ ⚡️ **Anti-Flood & Raid:** Ketma-ket yozgan spambotlarni avto-mute qilish\n"
    "├ 🈲 **Anti-Arab/Sharqiy:** Chet el spambot xabarlarini darhol yo'q qilish\n"
    "├ 🧹 **Aqlli Tozalash:** Oxirgi xabarlarni batamom tozalash (`/tozala 20`)\n"
    "├ 📌 **VIP E'lonlar:** Muhim xabarlarni bir zumda guruhga qadash (`/elon`)\n"
    "└ ⚙️ **Interaktiv Boshqaruv:** `/sozlamalar` paneli orqali barcha tizimlarni boshqarish\n\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
    "📌 **Botni ishga tushirish uchun:** Guruhingizga qo'shib, unga **Administrator (Admin)** huquqini bering!"
)


def get_start_keyboard(bot_username: str) -> InlineKeyboardMarkup:
    add_url = f"https://t.me/{bot_username}?startgroup=true&admin=change_info+delete_messages+restrict_members+invite_users+pin_messages"
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="➕ Guruhga qo'shish (Admin qilish)", url=add_url),
            ],
            [
                InlineKeyboardButton(text="📖 Buyruqlar qo'llanmasi", callback_data="btn_help_info"),
                InlineKeyboardButton(text="⚙️ Sozlash yo'riqnomasi", callback_data="btn_setup_guide"),
            ],
            [
                InlineKeyboardButton(text="📢 Homiy kanallar (Shaxsiy)", callback_data="pm_grplist"),
                InlineKeyboardButton(text="🛡 Himoya modullari", callback_data="btn_shields_info"),
            ],
            [
                InlineKeyboardButton(text="💎 VIP Funksiyalar", callback_data="btn_vip_info"),
                InlineKeyboardButton(text="🔄 Yangilash", callback_data="btn_refresh_start"),
            ],
        ]
    )


@router.message(CommandStart(ignore_case=True))
@router.message(Command("start", ignore_case=True))
async def cmd_start(message: Message, bot: Bot) -> None:
    bot_info = await bot.get_me()
    bot_username = bot_info.username or ""
    kb = get_start_keyboard(bot_username)

    if message.chat.type in ("private",):
        await safe_reply(message, BOT_CAPABILITIES_TEXT, reply_markup=kb)
    else:
        # Guruh ichida /start yozilganda ham chiroyli ma'lumot beramiz
        group_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(text="⚙️ Sozlamalar paneli", callback_data="open_settings_from_admin"),
                    InlineKeyboardButton(text="📊 Statistika", callback_data="show_stats_admin"),
                ],
                [
                    InlineKeyboardButton(text="📖 Qo'llanma", callback_data="btn_help_info"),
                ],
            ]
        )
        await safe_reply(message, BOT_CAPABILITIES_TEXT, reply_markup=group_kb)


@router.message(Command("yordam", "help", ignore_case=True))
async def cmd_help(message: Message) -> None:
    help_text = (
        "📖 **GURUHCHI UZ — BUYRUQLAR VA QO'LLANMA (VIP)** 💎\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "👥 **GURUH A'ZOLARI UCHUN:**\n"
        "├ `/start` — Bot imkoniyatlari va tezkor boshqaruv menyusi\n"
        "├ 👤 `/profil` — Shaxsiy profilingiz (Daraja, Level, XP va ligangiz)\n"
        "├ 🎁 `/kunlik` — Har 24 soatda bepul kunlik bonus XP olish\n"
        "├ 🏆 `/darajalar` — Eng yuqori darajadagi faollar ligasi (TOP-10)\n"
        "├ 📊 `/takliflarim` — Siz taklif qilgan a'zolar hisoboti va statusi\n"
        "├ 🥇 `/toptaklif` — Eng ko'p do'st taklif qilganlar reytingi (TOP-10)\n"
        "├ 💬 `/reyting` — Eng faol yozuvchi a'zolar ro'yxati (TOP-10)\n"
        "├ 📈 `/statistika` — Guruh monitoringi va bugungi ko'rsatkichlar\n"
        "├ 📜 `/qoidalar` — Guruh qoidalari bilan tanishish\n"
        "└ 🚨 `@admin` yoki `/sos` — Shoshilinch adminlarni chaqirish\n\n"
        "👮‍♂️ **GURUH ADMINISTRATORLARI UCHUN:**\n"
        "├ ⚙️ `/sozlamalar` — Himoya sozlamalari interaktiv boshqaruv paneli\n"
        "├ 👑 `/admin` — Bot holati va barcha tizimlar tezkor menyusi\n"
        "├ 🛡 `/xavfsizlik` — Guruhning to'liq kiber-himoya indeksi va auditi\n"
        "├ 👥 `/odam [soni]` — Majburiy a'zo talabini o'rnatish (`/odam 5`)\n"
        "├ 0️⃣ `/nol` — A'zo yoki butun guruh takliflarini 0 ga tushirish\n"
        "├ 🔒 `/qulf` / 🔓 `/ochish` — Guruhni zudlik bilan yopish va ochish\n"
        "├ ⏳ `/sekin [10|30|60|off]` — Sekin rejim (Slowmode) o'rnatish\n"
        "├ 🧹 `/tozala [soni]` — Xabarlarni batamom tozalash (`/tozala 20`)\n"
        "├ 🗑 `/del` — Reply qilingan xabarni zudlik bilan o'chirish\n"
        "├ 🔇 `/chekla [10m|2h|1d]` — Yozishni vaqtincha cheklash (Mute)\n"
        "├ 🔊 `/unmute` — Yozish cheklovini bekor qilish\n"
        "├ 🚫 `/hayda` — A'zoni guruhdan butunlay chiqarish va bloklash (Ban)\n"
        "├ 🕊 `/unban` — Bandan chiqarish\n"
        "├ ⚠️ `/ogohlantir [sabab]` — A'zoga ogohlantirish (warn) berish\n"
        "├ 🕊 `/unwarn` / `/kechir` — Ogohlantirishni olib tashlash\n"
        "├ 🌙 `/tun [on|off]` — Tungi avto-qulf rejimini sozlash\n"
        "├ 📥 `/zayafka [on|off]` — Qo'shilish arizalarini 1 soniyada tasdiqlash\n"
        "├ 📢 `/kanal` | `/kanal list` — Majburiy homiy kanallarni sozlash\n"
        "├ 🛑 `/sozqoshish` / `/sozochir` — Maxsus taqiqlangan so'zlar filtri\n"
        "├ 📋 `/sozlar` — Guruhdagi taqiqlangan so'zlar ro'yxati\n"
        "├ 💬 `/filtrqosh` / `/filtrlar` — Maxsus avto-javoblar (FAQ) tizimi\n"
        "├ 📢 `/setlog [kanal]` — Audit log kanalini ulash (/dellog o'chirish)\n"
        "├ 📊 `/haftalik` — Haftalik faollik xulosasini olish\n"
        "├ 🎲 `/tasodif` — Konkurs va giveaway lar uchun tasodifiy g'olib\n"
        "├ 👋 `/setwelcome [matn]` — Yangi a'zolarni kutib olish matnini sozlash\n"
        "├ 🔄 `/delwelcome` — Kutib olish matnini standartga qaytarish\n"
        "├ 📜 `/yangiqoida [matn]` — Yangi guruh qoidalarini o'rnatish\n"
        "└ 📌 `/elon [matn]` — Muhim xabar yoki faylni e'lon qilib qadash (pin)\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🛡 *Guruh 24/7 rejimda to'liq avtomatik himoyada!* ✨"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⚙️ Sozlamalar paneli", callback_data="open_settings_from_admin"),
                InlineKeyboardButton(text="🛡 Kiber-Himoya", callback_data="btn_shields_info"),
            ],
            [
                InlineKeyboardButton(text="👥 Majburiy taklif", callback_data="btn_odam_info"),
                InlineKeyboardButton(text="📖 Sozlash yo'riqnomasi", callback_data="btn_setup_guide"),
            ],
        ]
    )
    await safe_reply(message, help_text, reply_markup=kb)


@router.callback_query(F.data == "btn_help_info")
async def cb_help_info(call: CallbackQuery) -> None:
    help_text = (
        "📖 **GURUHCHI UZ — TEZKOR QO'LLANMA** 💎\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🔹 **Eng ko'p ishlatiladigan buyruqlar:**\n"
        "├ ⚙️ `/sozlamalar` — Himoya tizimlarini bitta paneldan boshqarish\n"
        "├ 👥 `/odam 5` — 5 ta a'zo qo'shmaguncha yozishni to'xtatish\n"
        "├ 0️⃣ `/nol` — Takliflarni 0 ga tushirish (yoki /nol hammasi)\n"
        "├ 🧹 `/tozala 20` — Oxirgi 20 ta xabarni tozalash\n"
        "├ 🌙 `/tun on` — Tungi 23:00-07:00 avto-qulf rejimini yoqish\n"
        "├ 📥 `/zayafka on` — Qo'shilish arizalarini 1 soniyada avto-tasdiqlash\n"
        "├ 🔇 `/chekla 10m` — Reply qilingan qoidabuzarni 10 daqiqaga mute qilish\n"
        "├ 🚫 `/hayda` — Reply qilingan spambotni guruhdan haydash (Ban)\n"
        "├ 📌 `/elon [matn]` — Xabarni e'lon qilib, guruhga qadash (Pin)\n"
        "└ 📊 `/statistika` — Guruh faolligi va monitoring ko'rsatkichlari\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "💡 Barcha modullar doimiy ravishda 24/7 avtomatik ishlaydi!"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⚙️ Sozlash yo'riqnomasi", callback_data="btn_setup_guide"),
                InlineKeyboardButton(text="🛡 Himoya modullari", callback_data="btn_shields_info"),
            ],
            [
                InlineKeyboardButton(text="⬅️ Bosh sahifa", callback_data="btn_back_to_start"),
            ],
        ]
    )
    try:
        await call.message.edit_text(help_text, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        await safe_reply(call.message, help_text, reply_markup=kb)
    await call.answer()


@router.callback_query(F.data == "btn_setup_guide")
async def cb_setup_guide(call: CallbackQuery) -> None:
    guide_text = (
        "🚀 **BOTNI GURUHGA SOZLASH YO'RIQNOMASI** 💎\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "1️⃣ **Botni guruhga qo'shing:**\n"
        "   └ Yuqoridagi «➕ Guruhga qo'shish» tugmasini bosing yoki guruh a'zolaridan botni taklif qiling.\n\n"
        "2️⃣ **Botga Administrator huquqini bering:**\n"
        "   ├ ✅ Xabarlarni o'chirish (Delete messages)\n"
        "   ├ ✅ Foydalanuvchilarni cheklash (Restrict members)\n"
        "   ├ ✅ Xabarlarni qadash (Pin messages)\n"
        "   └ ✅ A'zolarni taklif qilish (Invite users / Join requests)\n\n"
        "3️⃣ **Majburiy taklif talabini o'rnating:**\n"
        "   └ Guruhda `/odam 5` deb yozing. Endi har bir a'zo yozishdan oldin 5 ta do'stini qo'shishi shart bo'ladi!\n\n"
        "4️⃣ **Sozlamalar panelini oching:**\n"
        "   └ Guruhda `/sozlamalar` deb yozing va kerakli himoyalarni tugmalar orqali yoqing.\n\n"
        "5️⃣ **Guruh 100% himoyada!** 🛡\n"
        "   └ Barcha zararli fayllar (.apk), reklamalar, spam va haqoratlar avtomatik tozalab boriladi!"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📖 Buyruqlar qo'llanmasi", callback_data="btn_help_info"),
                InlineKeyboardButton(text="🛡 Himoya modullari", callback_data="btn_shields_info"),
            ],
            [
                InlineKeyboardButton(text="⬅️ Bosh sahifa", callback_data="btn_back_to_start"),
            ],
        ]
    )
    try:
        await call.message.edit_text(guide_text, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        await safe_reply(call.message, guide_text, reply_markup=kb)
    await call.answer()


@router.callback_query(F.data == "btn_shields_info")
async def cb_shields_info(call: CallbackQuery) -> None:
    shields_text = (
        "🛡 **KIBER-HIMOYA VA XAVFSIZLIK QALQONLARI** 🛡\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "💎 **Bot guruhda 15 ta avtomatik himoya tizimi bilan ishlaydi:**\n\n"
        "🦠 **1. Anti-APK Troyan Himoyasi:** Har qanday `.apk` troyan va virusli fayllarni 100% aniqlab darhol o'chiradi.\n"
        "🔗 **2. Anti-Link:** Begona Telegram havolalari, saytlar va @username reklamalarini yo'q qiladi.\n"
        "🚫 **3. Anti-Spam:** Kassa, stavka, pul ishlash va behayo spam xabarlarni tozalaydi.\n"
        "⚡️ **4. Anti-Flood:** Ketma-ket tez yozuvchi spamerlarni avtomatik 15 daqiqaga mute qiladi.\n"
        "🈲 **5. Anti-Raid / Arab filtri:** Arabcha, xitoycha yoki yot sharqiy spambot xabarlarini darhol yo'q qiladi.\n"
        "📢 **6. Anti-Channel:** Begona kanallar nomidan anonim yozishni to'xtatadi va kanalni bloklaydi.\n"
        "👤 **7. Anti-Name Spam:** Profil ismida reklama havolasi bo'lgan spambotlarni tozalaydi.\n"
        "🔄 **8. Anti-Forward:** Begona kanallardan forward qilingan postlarni o'chiradi.\n"
        "🤖 **9. Anti-Inline Bot:** Yashirin inline botlar orqali spam tarqatishni to'xtatadi.\n"
        "📑 **10. Anti-Dublikat:** Bir xil matnni tinimsiz copy-paste qiluvchilarni jazolaydi.\n"
        "🔠 **11. Anti-Emoji Spam:** Bir xabarda 5 tadan ortiq Premium animatsiyali emoji yuborishni cheklaydi.\n"
        "🔠 **12. Anti-Caps Lock:** Katta harflar bilan baqirib yozishni taqiqlaydi.\n"
        "🤬 **13. So'kinish filtri:** Madaniyatsiz va haqoratli so'zlarni tozalab, ogohlantirish beradi.\n"
        "🌙 **14. Tungi rejim:** 23:00 dan 07:00 gacha guruhni avto-yopib, ertalab ochadi.\n"
        "📥 **15. Avto-Zayafka:** Qo'shilish arizalarini 1 soniyada avto-tasdiqlaydi.\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "⚡️ *Barcha funksiyalar `/sozlamalar` paneli orqali boshqariladi!*"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⚙️ Sozlash yo'riqnomasi", callback_data="btn_setup_guide"),
                InlineKeyboardButton(text="📖 Buyruqlar", callback_data="btn_help_info"),
            ],
            [
                InlineKeyboardButton(text="⬅️ Bosh sahifa", callback_data="btn_back_to_start"),
            ],
        ]
    )
    try:
        await call.message.edit_text(shields_text, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        await safe_reply(call.message, shields_text, reply_markup=kb)
    await call.answer()


@router.callback_query(F.data == "btn_vip_info")
async def cb_vip_info(call: CallbackQuery) -> None:
    vip_text = (
        "💎 **VIP VA EKSKLYUZIV IMKONIYATLAR** 👑\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "🏆 **GAMIFIKATSIYA VA REYTING TIZIMI:**\n"
        "├ 👤 `/profil` — Shaxsiy profil, daraja, XP va liga darajangiz\n"
        "├ 🎁 `/kunlik` — Har 24 soatda bepul kunlik bonus XP olish\n"
        "├ 🌟 `/darajalar` — Eng yuqori darajadagi faollar ligasi (TOP-10)\n"
        "├ 💬 `/reyting` — Eng faol yozuvchilar reytingi (TOP-10)\n"
        "├ 🥇 `/toptaklif` — Eng ko'p do'st taklif qilganlar reytingi (TOP-10)\n"
        "└ 🎲 `/tasodif` — Konkurs va giveaway lar uchun adolatli tasodifiy tanlov\n\n"
        "📡 **AUDIT VA XAVFSIZLIK JURNALI:**\n"
        "├ 📢 `/setlog @kanal` — Barcha o'chirilgan reklamalar va cheklovlar uchun maxsus kanal ulash\n"
        "├ 📊 `/haftalik` — Har haftalik faollik va tozalov xulosasini avtomatik olish\n"
        "└ 🚨 `@admin` yoki `/sos` — Guruh a'zolari nojo'ya holatlarda zudlik bilan adminlarni chaqira oladi\n\n"
        "━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
        "🚀 Guruhchi Uz bilan guruhingizni eng yuqori darajaga olib chiqing!"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📖 Buyruqlar qo'llanmasi", callback_data="btn_help_info"),
                InlineKeyboardButton(text="🛡 Himoya modullari", callback_data="btn_shields_info"),
            ],
            [
                InlineKeyboardButton(text="⬅️ Bosh sahifa", callback_data="btn_back_to_start"),
            ],
        ]
    )
    try:
        await call.message.edit_text(vip_text, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        await safe_reply(call.message, vip_text, reply_markup=kb)
    await call.answer()


@router.callback_query(F.data.in_({"btn_back_to_start", "btn_refresh_start"}))
async def cb_back_to_start(call: CallbackQuery, bot: Bot) -> None:
    bot_info = await bot.get_me()
    bot_username = bot_info.username or ""
    kb = get_start_keyboard(bot_username)
    try:
        await call.message.edit_text(BOT_CAPABILITIES_TEXT, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        pass
    await call.answer("Bosh sahifa yangilandi! 🔄")
