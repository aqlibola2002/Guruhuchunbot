@echo off
chcp 65001 > nul
title Guruh Admin va Himoya Boti
color 0B

echo ========================================================
echo       🛡 Guruh Admin va Himoya Boti (Windows)
echo ========================================================
echo.

REM 1. .env faylini tekshirish
if not exist ".env" (
    echo [!] .env fayli topilmadi. .env.example faylidan nusxa olinmoqda...
    copy ".env.example" ".env" > nul
    echo [OK] .env fayli yaratildi!
    echo [DIQQAT] .env faylini ochib, TELEGRAM_TOKEN ni kiriting.
    echo.
)

REM 2. Muhit va kutubxonalarni tekshirish
if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
)

REM aiogram o'rnatilganligini tekshirish
python -c "import aiogram" 2>nul
if errorlevel 1 (
    echo [*] Kerakli kutubxonalar o'rnatilmoqda...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [XATO] Kutubxonalarni o'rnatishda xatolik yuz berdi!
        pause
        exit /b 1
    )
    echo [OK] Barcha kutubxonalar muvaffaqiyatli o'rnatildi!
)

echo.
echo ========================================================
echo   🤖 Bot ishga tushmoqda...
echo   To'xtatish uchun: Ctrl + C tugmalarini bosing
echo ========================================================
echo.

python main.py

if errorlevel 1 (
    echo.
    echo [!] Bot to'xtadi yoki xatolik yuz berdi.
    pause
)
