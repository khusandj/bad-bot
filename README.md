# BAD Product Knowledge Assistant

Bu bot BAD (Biologik Faol Qo'shimchalar) mahsulotlari haqida xodimlar savollariga javob berish uchun mo'ljallangan.

## O'rnatish (Windows PowerShell)

1. **Repozitoriyani yuklab oling yoki oching.**
2. **Virtual muhit yaratish:**
   ```powershell
   python -m venv venv
   ```
3. **Virtual muhitni faollashtirish:**
   ```powershell
   .\venv\Scripts\Activate.ps1
   ```
4. **Kutubxonalarni o'rnatish:**
   ```powershell
   pip install -r requirements.txt
   ```
5. **Sozlamalarni kiritish:**
   - `.env.example` faylini `.env` deb o'zgartiring.
   - `.env` fayli ichiga `TELEGRAM_BOT_TOKEN` va `GEMINI_API_KEY` ni kiriting.

## Botni ishga tushirish
```powershell
python bot.py
```

## Texnologiyalar
- Python 3.10+
- Aiogram 3.x
- Google Gemini API
