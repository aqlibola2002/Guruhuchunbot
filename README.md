# 🛡 Guruh Admin va Himoya Boti (Telegram Group Bot)

Telegram guruhlarini avtomatlashtirish, reklama va spamlardan tozalash, qoidabuzarlarni jazolash, a'zolarni kutib olish, savollarga FAQ orqali javob berish, **a'zolar qo'shilishini sanash va majburiy taklif talabi (a'zo qo'shtirish)** hamda faollik statistikasini yuritish uchun professional bot.

---

## ✨ Imkoniyatlar va Funksiyalar

| Funksiya | Tavsif |
| :--- | :--- |
| 👥 **A'zolar qo'shilishini hisoblash** | Kim qancha yangi a'zo qo'shganini aniq sanaydi va takroriy qo'shish firibgarliklarini oldini oladi. |
| 🛑 **Majburiy a'zo qo'shtirish** | Guruhda yozish uchun har bir a'zoga belgilangan miqdorda odam qo'shish talabini qo'yish (`/setinvites 5`). Sharti bajarilmasa, bot xabarni o'chirib, qancha a'zo qo'shishi kerakligini bildiradi. |
| 🌟 **/myinvites & /topinvites** | Foydalanuvchi o'z takliflarini ko'rishi va guruhga eng ko'p a'zo qo'shgan TOP-10 faollar reytingi. |
| 👋 **Avto-kutib olish** | Yangi a'zo kirganda uning ismi bilan chiroyli xush kelibsiz xabari va qoidalar tugmachalari chiqadi. "Falonchi qo'shildi / chiqdi" xizmat xabarlari avtomatik tozalanadi. |
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
| ⚙️ **/settings** | Guruh himoya sozlamalarini (Antilink, Antispam, Majburiy taklif, Welcome, Rejali xabarlar) inline tugmalar bilan boshqarish. |

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
