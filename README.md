# 🛡 Guruh Admin va Himoya Boti (Telegram Group Bot)

Telegram guruhlarini avtomatlashtirish, reklama va spamlardan tozalash, qoidabuzarlarni jazolash, a'zolarni kutib olish, savollarga FAQ orqali javob berish, **a'zolar qo'shilishini sanash va majburiy taklif talabi (a'zo qo'shtirish)** hamda faollik statistikasini yuritish uchun professional bot.

---

## ✨ Imkoniyatlar va Funksiyalar

| Funksiya | Tavsif |
| :--- | :--- |
| 👥 **A'zolar qo'shilishini hisoblash** | Kim qancha yangi a'zo qo'shganini aniq sanaydi va takroriy qo'shish firibgarliklarini oldini oladi. |
| 🛑 **Majburiy a'zo qo'shtirish** | Guruhda yozish uchun har bir a'zoga belgilangan miqdorda odam qo'shish talabini qo'yish (`/odam 5` yoki `/setinvites 5`). Sharti bajarilmasa, bot xabarni o'chirib, qancha a'zo qo'shishi kerakligini bildiradi. |
| 0️⃣ **/nol** | Reply orqali a'zoning guruhga qo'shgan barcha odamlarini nol (0) ga tushirish. Foydalanuvchi guruhda yozish uchun qaytadan yangi a'zo qo'shishi kerak bo'ladi (`/nol`, `/nol @username`, `/nol ID`, `/nol all`). |
| 🌟 **/takliflarim** | Foydalanuvchi o'z takliflarini ko'rishi va majburiyat bajarilganini tekshirish. |
| 👋 **Avto-kutib olish** | Yangi a'zo kirganda uning ismi bilan chiroyli xush kelibsiz xabari va qoidalar tugmachalari chiqadi. "Falonchi qo'shildi / chiqdi" xizmat xabarlari avtomatik tozalanadi. |
| 🤬 **Haqorat & So'kinish filtri** | O'zbekcha va ruscha behayo so'zlarni avtomatik o'chiradi va qoidabuzarga ogohlantirish beradi. |
| 🎭 **Media filtrlari (Stiker/Ovoz)** | Guruhda stiker/GIF yoki ovozli xabar (voice) va dumaloq videolarni alohida taqiqlash imkoniyati. |
| 🌙 **/tun** | Tungi rejimni sozlash (`/tun on`, `/tun off`, `/tun 23:00-07:00`). Belgilangan soatda guruhni avto-yopish va ertalab ochish. |
| 📥 **/zayafka** | Guruh va kanallarga qo'shilish arizalarini (Join Request) 1 soniyada avtomatik tasdiqlash (`/zayafka on`, `/zayafka off`). |
| 📢 **Majburiy kanallar (`/kanal`)** | Homiy kanallar qo'shish va a'zolikni «A'zo bo'ldim» tugmasi bilan 24/7 tekshirish (`/kanal @kanal`, `/kanal ochir @kanal`). |
| 🛡 **Antispam & Reklama** | Kazino (1xbet, stavkalar), oson pul va firibgarlik havolalari aniqlanganda xabarlar o'chiriladi. |
| 🔗 **Antilink (Begona havolalar)** | Oddiy a'zolar yuborgan `t.me/`, `@username` va veb-sayt havolalari avtomatik o'chiriladi (Adminlarga ruxsat berilgan). |
| 🔇 **/chekla** | Qoidabuzarni vaqtincha yozishdan to'xtatish (masalan: `/chekla 10m`, `/chekla 2h`, `/chekla 1d`). |
| 🚫 **/hayda** | Guruhdan butunlay chiqarish va bloklash (Ban). |
| 🧹 **/tozala** | Guruhdagi oxirgi xabarlarni progress bar bilan tozalash (masalan: `/tozala 20` yoki a'zoga reply). |
| ❓ **FAQ (Avto-javoblar)** | Tez-tez so'raladigan savollar bo'yicha bot o'zi javob beradi (`/addfaq savol = javob`). |
| 📊 **/statistika** | Guruh a'zolari, bugungi xabarlar, jazo choralari va himoya tizimlari holati. |
| 🏆 **/reyting** | Guruhdagi eng faol 10 ta foydalanuvchi reytingi (🥇 🥈 🥉). |
| 🥇 **/toptaklif** | Eng ko'p do'st taklif qilgan 10 ta a'zo reytingi. |
| 📌 **/elon** | Har qanday xabar, rasm yoki videoli e'lonni guruhga yuborish va avtomatik qadab (pin) qo'yish. |
| ⏰ **Rejali xabarlar** | Har kuni ertalab (08:30) va kechqurun (22:30) guruhga avtomatik salomnomalar. |
| ⚙️ **/sozlamalar** | Guruh himoya tizimlarini bitta qulay tugmali menyu orqali boshqarish. |
| 👑 **/panel** | Bot Egasi (Super Admin) boshqaruv paneli (Global statistika, Uptime, tizim holati). |
| 💾 **/backup** | Ma'lumotlar bazasini (`group_bot.db`) bot egasiga Telegram orqali yuborish. |
| 📢 **/send, /send_users, /send_all** | Barcha guruhlar, shaxsiy foydalanuvchilar yoki barchaga professional xabar tarqatish (rassilka). |
| 🚫 **/ban_global, /unban_global** | Qoidabuzar va firibgarlarni bot bo'yicha global qora ro'yxatga kiritish va chiqarish. |
| 🛠 **/profilaktika** | Botni texnik xizmat / profilaktika rejimiga o'tkazish. |
| 🚪 **/chiq [chat_id]** | Botni masofadan turib begona guruhlardan chiqarish. |

---

## 🚀 Ishga tushirish

1. `.env` faylida bot tokenini tekshiring:
```env
TELEGRAM_TOKEN=8888231466:AAEN44GXnW-V-0uiWQxbFpUKfv6wf6barzs
ADMIN_IDS=8781024332
```

2. Botni ishga tushiring:
```bash
python main.py
```

3. Botni Telegram guruhingizga qo'shing va unga **Administrator** huquqlarini bering:
   - *Xabarlarni o'chirish (Delete messages)*
   - *Foydalanuvchilarni cheklash (Restrict members)*
   - *Xabarlarni qadash (Pin messages)*
