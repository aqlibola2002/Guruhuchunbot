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

REM 2. Python va Virtual muhitni (.venv) sozlash
if not exist ".venv" (
    echo [*] Virtual muhit (.venv) yaratilmoqda...
    py -3.12 -m venv .venv 2>nul || py -3.11 -m venv .venv 2>nul || py -3 -m venv .venv 2>nul || python -m venv .venv 2>nul || "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" -m venv .venv 2>nul || "%LOCALAPPDATA%\Programs\Python\Python311\python.exe" -m venv .venv 2>nul
    if errorlevel 1 (
        echo [XATO] Python topilmadi! Iltimos, Python 3.10+ o'rnating va uni PATH ga qo'shing.
        pause
        exit /b 1
    )
    echo [OK] Virtual muhit yaratildi!
    
    echo [*] Kutubxonalar o'rnatilmoqda...
    call .venv\Scripts\activate.bat
    python -m pip install --upgrade pip
    pip install -r requirements.txt
    echo [OK] Barcha kutubxonalar muvaffaqiyatli o'rnatildi!
) else (
    call .venv\Scripts\activate.bat
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
