# PythonAnywhere Deployment Guide (24/7)

Botingizni PythonAnywhere serveriga joylashtirish va 24/7 ishlatish uchun quyidagi qadamlarni bajaring:

## 1. PythonAnywhere hisobini yarating
[pythonanywhere.com](https://www.pythonanywhere.com/) saytida ro'yxatdan o'ting (Free yoki Beginner tarif).

## 2. Fayllarni yuklash
1.  PythonAnywhere-da **"Files"** bo'limiga kiring.
2.  Yangi papka oching (masalan: `my_bot`).
3.  Kompyuteringizdagi barcha fayllarni (bot.py, requirements.txt, .env, products/, prompts/ va h.k.) yuklang.

## 3. Virtual muhit va Kutubxonalar
**"Consoles"** bo'limiga o'tib, **Bash** konsolini oching va quyidagilarni bajaring:

```bash
# Papkaga kiring
cd my_bot

# Virtual muhit yaratish
python3 -m venv venv

# Uni faollashtirish
source venv/bin/activate

# Kutubxonalarni o'rnatish
pip install -r requirements.txt
```

## 4. Botni 24/7 ishga tushirish (Always-on Task)
Agar sizda pullik (Paid) akkaunt bo'lsa:
-   **"Tasks"** bo'limiga kiring.
-   **"Always-on tasks"** ga quyidagi buyruqni yozing:
    `/home/SizningLogin/my_bot/venv/bin/python /home/SizningLogin/my_bot/bot.py`

Agar bepul (Free) akkaunt bo'lsa:
-   **"Consoles"** bo'limida botni yoqib qo'ying (`python bot.py`).
-   *Eslatma:* Bepul akkauntda bot har 24 soatda o'chib qolishi mumkin, uni har kuni saytga kirib "Run" qilib turish kerak.

## 5. Tokenlarni tejash (Sleep Mode)
Admin panelida yangi **"Bot holati: Active/Sleep"** tugmasi qo'shildi. Botni "Sleep" holatiga o'tkazsangiz, u foydalanuvchilarga javob bermaydi va Gemini API tokenlarini ishlatmaydi.
