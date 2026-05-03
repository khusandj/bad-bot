import os
import asyncio
import logging
import json
from datetime import datetime
import re

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

# NEW Gemini SDK
from google import genai
from google.genai import types as genai_types

# For document and audio processing
import docx
import PyPDF2

from aiogram.client.session.aiohttp import AiohttpSession

# Load environment variables
load_dotenv()
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
ADMIN_ID = os.getenv("ADMIN_ID")

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize NEW Gemini Client
client = genai.Client(api_key=GEMINI_API_KEY)
MODEL_NAME = "gemini-3.1-pro-preview"

# Setup Bot with Proxy for PythonAnywhere (Free Account support)
session = None
if os.environ.get('PYTHONANYWHERE_DOMAIN'):
    session = AiohttpSession(proxy="http://proxy.server:3128")

bot = Bot(token=TELEGRAM_BOT_TOKEN, session=session)
dp = Dispatcher(storage=MemoryStorage())

# States for admin actions
class AdminStates(StatesGroup):
    waiting_for_edit_content = State()
    waiting_for_new_name = State()
    waiting_for_broadcast = State()
    waiting_for_system_prompt = State()

# Directories and Files
PRODUCTS_DIR = "products"
IMAGES_DIR = "images"
STATS_FILE = "stats.json"
FEEDBACK_FILE = "feedback.json"
SETTINGS_FILE = "settings.json"
FALLBACK_MESSAGE_UZ = "Bu savol bo‘yicha bazada aniq ma’lumot topilmadi. Product managerga murojaat qiling."
FALLBACK_MESSAGE_RU = "По этому вопросу в базе данных точной информации не найдено. Обратитесь к продакт-менеджеру."

# Ensure directories exist
os.makedirs(PRODUCTS_DIR, exist_ok=True)
os.makedirs(IMAGES_DIR, exist_ok=True)

# Helper Functions
def load_json(file_path):
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            try: return json.load(f)
            except: return {}
    return {}

def save_json(file_path, data):
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def update_stats(product_name):
    stats = load_json(STATS_FILE)
    stats[product_name] = stats.get(product_name, 0) + 1
    save_json(STATS_FILE, stats)

def load_knowledge_base():
    context = ""
    if os.path.exists(PRODUCTS_DIR):
        for filename in sorted(os.listdir(PRODUCTS_DIR)):
            if filename.endswith(".md"):
                with open(os.path.join(PRODUCTS_DIR, filename), "r", encoding="utf-8") as f:
                    context += f"\n--- {filename} ---\n{f.read()}\n"
    return context

def load_system_prompt():
    settings = load_json(SETTINGS_FILE)
    if "system_prompt" in settings:
        return settings["system_prompt"]
    
    prompt_path = "prompts/system_prompt.md"
    if os.path.exists(prompt_path):
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()
    return "Siz yordamchisiz."

def get_product_list():
    if not os.path.exists(PRODUCTS_DIR): return []
    return [f.replace(".md", "") for f in sorted(os.listdir(PRODUCTS_DIR)) if f.endswith(".md")]

def is_bot_active():
    settings = load_json(SETTINGS_FILE)
    return settings.get("active", True)

# Store user settings
user_languages = {}
all_users = set()

# --- COMMAND HANDLERS ---

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    all_users.add(message.from_user.id)
    builder = InlineKeyboardBuilder()
    builder.button(text="🇺🇿 O'zbekcha", callback_data="lang_uz")
    builder.button(text="🇷🇺 Русский", callback_data="lang_ru")
    builder.adjust(2)
    await message.answer("Tilni tanlang / Выберите язык:", reply_markup=builder.as_markup())

@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    user_id = str(message.from_user.id)
    if user_id != str(ADMIN_ID):
        await message.answer(f"❌ Siz admin emassiz. ID: `{user_id}`")
        return
    
    active = is_bot_active()
    status_text = "🟢 ACTIVE" if active else "😴 SLEEP"
    
    builder = InlineKeyboardBuilder()
    builder.button(text=f"Bot Holati: {status_text}", callback_data="admin_toggle_status")
    builder.button(text="📋 Javobsiz savollar", callback_data="admin_unanswered")
    builder.button(text="📊 Statistika", callback_data="admin_stats")
    builder.button(text="⚙️ Mahsulotlarni boshqarish", callback_data="admin_manage")
    builder.button(text="📢 Broadcast", callback_data="admin_broadcast")
    builder.button(text="🧠 System Prompt", callback_data="admin_prompt")
    builder.adjust(1)
    await message.answer("🛠 Admin Panel:", reply_markup=builder.as_markup())

@dp.message(Command("products"))
async def cmd_products(message: types.Message):
    if not is_bot_active() and str(message.from_user.id) != str(ADMIN_ID):
        await message.answer("😴 Bot hozir dam olmoqda (Sleep mode).")
        return
    lang = user_languages.get(message.from_user.id, "uz")
    products = get_product_list()
    if not products:
        await message.answer("Bazada mahsulotlar yo'q." if lang == "uz" else "В базе нет продуктов.")
        return
    builder = InlineKeyboardBuilder()
    for product in products:
        builder.button(text=product.capitalize(), callback_data=f"prod_{product}")
    builder.adjust(2)
    msg = "👇 Mahsulotni tanlang:" if lang == "uz" else "👇 Выберите продукт:"
    await message.answer(msg, reply_markup=builder.as_markup())

# --- CALLBACK HANDLERS ---

@dp.callback_query(F.data == "admin_toggle_status")
async def toggle_status(callback: types.CallbackQuery):
    settings = load_json(SETTINGS_FILE)
    current = settings.get("active", True)
    settings["active"] = not current
    save_json(SETTINGS_FILE, settings)
    await callback.answer(f"Bot {'Active' if not current else 'Sleep'}")
    await cmd_admin(callback.message)
    await callback.message.delete()

@dp.callback_query(F.data.startswith("lang_"))
async def set_language(callback: types.CallbackQuery):
    lang = callback.data.split("_")[1]
    user_languages[callback.from_user.id] = lang
    await callback.answer()
    msg = "🔍 Savolingizni yozing!" if lang == "uz" else "🔍 Напишите ваш вопрос!"
    await callback.message.answer(f"✅ {msg}\n📦 /products")

@dp.callback_query(F.data.startswith("prod_"))
async def process_product_click(callback: types.CallbackQuery):
    if not is_bot_active() and str(callback.from_user.id) != str(ADMIN_ID):
        await callback.answer("😴 Bot uyquda.", show_alert=True)
        return
    
    product_name = callback.data.split("_")[1]
    lang = user_languages.get(callback.from_user.id, "uz")
    
    try: await callback.answer()
    except: pass
        
    update_stats(product_name)
    query = f"{product_name} haqida ma'lumot ber" if lang == "uz" else f"Инфо о {product_name}"
    
    wait_msg = await callback.message.answer("🔄 Qidirilmoqda..." if lang == "uz" else "🔄 Поиск...")
    await handle_ai_response(callback.message, query, lang, product_name)
    try: await wait_msg.delete()
    except: pass

@dp.callback_query(F.data == "admin_manage")
async def admin_manage_products(callback: types.CallbackQuery):
    products = get_product_list()
    builder = InlineKeyboardBuilder()
    for p in products:
        builder.button(text=f"📝 Edit", callback_data=f"edit_{p}")
        builder.button(text=f"🏷 Rename", callback_data=f"rename_{p}")
        builder.button(text=f"🗑 Delete", callback_data=f"del_{p}")
        builder.button(text=f"--- {p.capitalize()} ---", callback_data="none")
    builder.adjust(3, 1)
    builder.button(text="⬅️ Orqaga", callback_data="admin_back")
    await callback.message.edit_text("📦 Boshqarish:", reply_markup=builder.as_markup())

@dp.callback_query(F.data.startswith("del_"))
async def delete_product(callback: types.CallbackQuery):
    prod = callback.data.split("_")[1]
    path = os.path.join(PRODUCTS_DIR, f"{prod}.md")
    if os.path.exists(path): os.remove(path)
    img_path = os.path.join(IMAGES_DIR, f"{prod}.jpg")
    if os.path.exists(img_path): os.remove(img_path)
    await callback.answer(f"✅ {prod} o'chirildi")
    await admin_manage_products(callback)

@dp.callback_query(F.data.startswith("edit_"))
async def edit_product_start(callback: types.CallbackQuery, state: FSMContext):
    prod = callback.data.split("_")[1]
    await state.update_data(edit_target=prod)
    await state.set_state(AdminStates.waiting_for_edit_content)
    await callback.message.answer(f"📝 **{prod.capitalize()}** uchun yangi matnni yuboring:")
    await callback.answer()

@dp.callback_query(F.data.startswith("rename_"))
async def rename_product_start(callback: types.CallbackQuery, state: FSMContext):
    prod = callback.data.split("_")[1]
    await state.update_data(rename_target=prod)
    await state.set_state(AdminStates.waiting_for_new_name)
    await callback.message.answer(f"🏷 **{prod.capitalize()}** uchun yangi nomni yuboring:")
    await callback.answer()

@dp.callback_query(F.data == "admin_broadcast")
async def broadcast_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_broadcast)
    await callback.message.answer("📢 Xabarni yozing:")
    await callback.answer()

@dp.callback_query(F.data == "admin_prompt")
async def prompt_edit_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.waiting_for_system_prompt)
    current = load_system_prompt()
    await callback.message.answer(f"🧠 Prompt:\n`{current[:200]}...`\n\nYangi promptni yuboring:")
    await callback.answer()

@dp.callback_query(F.data == "admin_back")
async def admin_back(callback: types.CallbackQuery):
    await callback.message.delete()
    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Javobsiz", callback_data="admin_unanswered")
    builder.button(text="📊 Stats", callback_data="admin_stats")
    builder.button(text="⚙️ Manage", callback_data="admin_manage")
    builder.adjust(1)
    await callback.message.answer("🛠 Admin Panel:", reply_markup=builder.as_markup())
    await callback.answer()

@dp.callback_query(F.data.startswith("fb_"))
async def handle_feedback(callback: types.CallbackQuery):
    feedback = load_json(FEEDBACK_FILE)
    user_id = str(callback.from_user.id)
    feedback[user_id] = feedback.get(user_id, [])
    feedback[user_id].append({"type": callback.data, "time": str(datetime.now())})
    save_json(FEEDBACK_FILE, feedback)
    await callback.answer("Rahmat!")

# --- MEDIA HANDLERS ---

@dp.message(F.voice)
async def handle_voice(message: types.Message):
    if not is_bot_active() and str(message.from_user.id) != str(ADMIN_ID):
        await message.answer("😴 Bot uyquda.")
        return
    lang = user_languages.get(message.from_user.id, "uz")
    wait_msg = await message.answer("🎤 ..." if lang == "uz" else "🎤 ...")
    file = await bot.get_file(message.voice.file_id)
    save_path = f"voice_{message.from_user.id}.ogg"
    await bot.download_file(file.file_path, save_path)
    try:
        with open(save_path, "rb") as f: audio_data = f.read()
        context = load_knowledge_base()
        system_prompt = load_system_prompt().format(context=context)
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=[genai_types.Content(parts=[
                genai_types.Part.from_text(text=f"{system_prompt}\n\nAudio savolga javob ber. Til: {lang}"),
                genai_types.Part.from_bytes(data=audio_data, mime_type="audio/ogg")
            ])],
            config=genai_types.GenerateContentConfig(tools=[genai_types.Tool(google_search=genai_types.GoogleSearchRetrieval())])
        )
        await wait_msg.delete()
        await handle_final_answer(message, response.text.strip(), lang)
    except Exception as e:
        logging.error(f"Voice error: {e}")
        await message.answer("❌")
    finally:
        if os.path.exists(save_path): os.remove(save_path)

@dp.message(F.document)
async def handle_document(message: types.Message):
    if str(message.from_user.id) != str(ADMIN_ID): return
    file = await bot.get_file(message.document.file_id)
    save_path = f"temp_{message.document.file_name}"
    await bot.download_file(file.file_path, save_path)
    text = ""
    if save_path.endswith(".docx"):
        text = "\n".join([p.text for p in docx.Document(save_path).paragraphs])
    elif save_path.endswith(".pdf"):
        for page in PyPDF2.PdfReader(save_path).pages: text += page.extract_text()
    if text:
        with open(os.path.join(PRODUCTS_DIR, message.document.file_name.rsplit('.',1)[0].lower()+".md"), "w", encoding="utf-8") as f: f.write(text)
        await message.answer("✅ Qo'shildi.")
    os.remove(save_path)

# --- TEXT HANDLER ---

@dp.message(F.text)
async def handle_text(message: types.Message, state: FSMContext):
    curr_state = await state.get_state()
    
    if curr_state == AdminStates.waiting_for_edit_content:
        data = await state.get_data(); prod = data['edit_target']
        with open(os.path.join(PRODUCTS_DIR, f"{prod}.md"), "w", encoding="utf-8") as f: f.write(message.text)
        await message.answer(f"✅ {prod} yangilandi."); await state.clear(); return

    if curr_state == AdminStates.waiting_for_new_name:
        data = await state.get_data(); old_name = data['rename_target']
        new_name = message.text.strip().lower().replace(" ", "-")
        os.rename(os.path.join(PRODUCTS_DIR, f"{old_name}.md"), os.path.join(PRODUCTS_DIR, f"{new_name}.md"))
        old_img = os.path.join(IMAGES_DIR, f"{old_name}.jpg")
        if os.path.exists(old_img): os.rename(old_img, os.path.join(IMAGES_DIR, f"{new_name}.jpg"))
        await message.answer(f"✅ Nom o'zgardi."); await state.clear(); return

    if curr_state == AdminStates.waiting_for_broadcast:
        for user_id in all_users:
            try: await bot.send_message(user_id, f"📢 **XABAR:**\n\n{message.text}")
            except: pass
        await message.answer("✅ Yuborildi."); await state.clear(); return

    if curr_state == AdminStates.waiting_for_system_prompt:
        settings = load_json(SETTINGS_FILE); settings["system_prompt"] = message.text; save_json(SETTINGS_FILE, settings)
        await message.answer("✅ Prompt yangilandi."); await state.clear(); return

    if not is_bot_active() and str(message.from_user.id) != str(ADMIN_ID):
        await message.answer("😴 Bot hozir dam olmoqda (Sleep mode). Tokenlar tejalmoqda."); return

    lang = user_languages.get(message.from_user.id, "uz")
    await handle_ai_response(message, message.text, lang)

MODEL_NAME_FAST = "gemini-3.1-flash-preview"
MODEL_NAME_PRO = "gemini-3.1-pro-preview"

async def handle_ai_response(message, query, lang, product_hint=None):
    context = load_knowledge_base()
    system_prompt = load_system_prompt().format(context=context)

    # Check if internet search is really needed (saves time)
    needs_search = any(word in query.lower() for word in ["narx", "qancha", "uzum", "market", "rasm", "photo", "image", "цена", "сколько"])

    # Use Flash for regular info, Pro only for complex searches
    selected_model = MODEL_NAME_PRO if needs_search else MODEL_NAME_FAST

    try:
        config = None
        if needs_search:
            config = genai_types.GenerateContentConfig(
                tools=[genai_types.Tool(google_search=genai_types.GoogleSearchRetrieval())]
            )

        response = client.models.generate_content(
            model=selected_model,
            contents=f"{system_prompt}\n\nFoydalanuvchi so'rovi: {query}",
            config=config
        )
        await handle_final_answer(message, response.text.strip(), lang, product_hint)
    except Exception as e:
        logging.error(f"AI error: {e}")
        await message.answer("❌ Xatolik.")

async def handle_final_answer(message, answer, lang, product_hint=None):
    if "topilmadi" in answer.lower() or "не найдено" in answer.lower():
        log_unanswered_question(message.text or "Voice")
        await message.answer(FALLBACK_MESSAGE_UZ if lang == "uz" else FALLBACK_MESSAGE_RU)
        return
    
    fb_builder = InlineKeyboardBuilder()
    fb_builder.button(text="👍", callback_data="fb_up"); fb_builder.button(text="👎", callback_data="fb_down")
    
    image_url = None
    if "IMAGE_URL:" in answer:
        match = re.search(r"IMAGE_URL:\s*(https?://[^\s\n]+)", answer)
        if match:
            image_url = match.group(1)
            answer = answer.replace(match.group(0), "").strip()

    prod = product_hint
    if not image_url and not prod:
        for p in get_product_list():
            if p.lower() in answer.lower()[:100]: prod = p; break
    
    if not image_url and prod:
        img_path = os.path.join(IMAGES_DIR, f"{prod}.jpg")
        if os.path.exists(img_path):
            try:
                await message.answer_photo(types.FSInputFile(img_path), caption=answer, reply_markup=fb_builder.as_markup())
                return
            except: pass
            
    if image_url:
        try:
            await message.answer_photo(photo=image_url, caption=answer, reply_markup=fb_builder.as_markup())
            return
        except Exception as e:
            logging.error(f"Failed AI image: {e}")
            await message.answer(f"{answer}\n\n(Rasm yuklashda xato)", reply_markup=fb_builder.as_markup())
            return

    await message.answer(answer, reply_markup=fb_builder.as_markup())

async def main():
    logging.info("Bot ishga tushmoqda...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
