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
| 🤬 **Haqorat & So'kinish filtri** | O'zbekcha va ruscha behayo so'zlarni avtomatik o'chiradi va ogohlantirish (warn) beradi. |
| 🎭 **Media filtrlari (Stiker/Ovoz)** | Guruhda stiker/GIF yoki ovozli xabar (voice) va dumaloq videolarni alohida taqiqlash imkoniyati. |
| ✏️ **/setwelcome** | Yangi a'zolar uchun o'zingiz xohlagan maxsus salomnoma matnini o'rnatish (`{name}`, `{title}`). |
| 📢 **Majburiy kanallar (`/kanal`)** | Bir nechta majburiy kanallar qo'shish va a'zolikni «A'zo bo'ldim» tugmasi bilan tekshirish. |
| 🛡 **Antispam & Reklama** | Kazino (1xbet, stavkalar), oson pul va firibgarlik havolalari aniqlanganda xabar o'chiriladi va ogohlantirish beriladi. |
| 🔗 **Antilink (Begona havolalar)** | Oddiy a'zolar tashlagan `t.me/`, `@username` va veb-sayt havolalari avtomatik o'chiriladi (Adminlarga ruxsat berilgan). |
| ⚠️ **/warn** | Qoidabuzarlarga ogohlantirish berish (1/3, 2/3). 3-ogohlantirishda bot foydalanuvchini 24 soatga guruhda yozishdan cheklaydi. |
| 🔇 **/mute** | Foydalanuvchini vaqtincha yozishdan to'xtatish (masalan: `/mute 10m`, `/mute 2h`, `/mute 1d`). |
| 🚫 **/ban & /unban** | Guruhdan butunlay haydash yoki qayta kirishiga ruxsat berish. |
| 🧹 **/clear** | Guruhdagi oxirgi xabarlarni tozalash (masalan: `/clear 20`). |
| 📜 **/rules & /setrules** | Guruh qoidalarini chiqarish va yangi qoidalar o'rnatish. |
| ❓ **FAQ (Avto-javoblar)** | Tez-tez so'raladigan savollar bo'yicha bot o'zi javob beradi (`/addfaq savol = javob`). |
| 📊 **/stats** | Guruh a'zolari, bugungi xabarlar, jazo choralari va taklif talablari haqida hisobot. |
| 🏆 **/top** | Guruhdagi eng faol 10 ta foydalanuvchi reytingi (🥇 🥈 🥉). |
| 📢 **/broadcast** | Admin e'lonini guruhga yuborish va avtomatik qadab (pin) qo'yish. |
| ⏰ **Rejali xabarlar** | Har kuni ertalab (08:30) va kechqurun (22:30) guruhga avtomatik salomnomalar. |
| ⚙️ **/settings** | Guruh himoya sozlamalarini (Antilink, Antispam, So'kinish filtri, Media taqiqlari, Majburiy taklif) inline tugmalar bilan boshqarish. |

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
