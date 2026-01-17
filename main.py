from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import sqlite3
from datetime import datetime, timedelta
import os
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram import Update
import requests
from fastapi.middleware.cors import CORSMiddleware
import asyncio

# --- Конфигурация ---
app = FastAPI(title="Всё в порядке?", version="0.1.0")

# --- Настройка CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Модель для запросов ---
class RegisterRequest(BaseModel):
    telegram_id: str
    name: str
    contact_telegram_id: str

class CheckinRequest(BaseModel):
    telegram_id: str

# --- Работа с базой данных ---
DB_PATH = "users.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            contact_telegram_id TEXT,
            checkin_time TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def get_user_by_telegram_id(telegram_id: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row:
        return {
            "id": row[0],
            "telegram_id": row[1],
            "name": row[2],
            "contact_telegram_id": row[3],
            "checkin_time": row[4]
        }
    return None

def update_checkin_time(telegram_id: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET checkin_time = ? WHERE telegram_id = ?", 
                   (datetime.now().isoformat(), telegram_id))
    conn.commit()
    conn.close()

def register_user(telegram_id: str, name: str, contact_telegram_id: str):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("""
            INSERT INTO users (telegram_id, name, contact_telegram_id) 
            VALUES (?, ?, ?)
        """, (telegram_id, name, contact_telegram_id))
        conn.commit()
        conn.close()
        return True
    except sqlite3.IntegrityError:
        conn.close()
        return False

# --- API маршруты ---
@app.on_event("startup")
async def startup_event():
    init_db()

@app.post("/register")
async def register_endpoint(data: RegisterRequest):
    user = get_user_by_telegram_id(data.telegram_id)
    
    if user:
        return {"status": "error", "message": "Пользователь уже зарегистрирован"}
    
    success = register_user(data.telegram_id, data.name, data.contact_telegram_id)
    
    if success:
        return {"status": "ok", "user_id": data.telegram_id}
    else:
        return {"status": "error", "message": "Ошибка регистрации"}

@app.post("/checkin")
async def checkin_endpoint(data: CheckinRequest):
    user = get_user_by_telegram_id(data.telegram_id)
    
    if not user:
        return {"status": "error", "message": "Пользователь не найден"}
    
    update_checkin_time(data.telegram_id)
    
    return {"status": "ok", "message": "Отметка обновлена"}

@app.get("/status/{telegram_id}")
async def get_status(telegram_id: str):
    user = get_user_by_telegram_id(telegram_id)
    
    if not user:
        return {"status": "error", "message": "Пользователь не найден"}
    
    last_checkin = user["checkin_time"]
    last_checkin_dt = datetime.fromisoformat(last_checkin)
    time_diff = datetime.now() - last_checkin_dt
    
    status = "ALARM" if time_diff > timedelta(hours=24) else "OK"
    
    return {
        "status": status,
        "last_checkin": last_checkin,
        "contact_telegram_id": user["contact_telegram_id"]
    }

# --- Telegram Bot (для вебхука) ---
try:
    from config import TELEGRAM_BOT_TOKEN
except ImportError:
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

telegram_app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

# --- Инициализация при запуске ---
@app.on_event("startup")
async def initialize_telegram_app():
    await telegram_app.initialize()
    await telegram_app.start()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    chat_id = update.effective_chat.id
    
    message = (
        f"Привет! Я бот для системы 'Всё в порядке?'.\n\n"
        f"Ваш Telegram ID: {user_id}\n\n"
        f"Для регистрации в системе используйте команду:\n"
        f"/register <ваше_имя> <ID_доверенного_лица>\n\n"
        f"Для отметки 'я в порядке' используйте:\n"
        f"/checkin"
    )
    
    await context.bot.send_message(chat_id=chat_id, text=message)

async def register_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    chat_id = update.effective_chat.id
    
    if len(context.args) < 2:
        await context.bot.send_message(
            chat_id=chat_id,
            text="Используйте: /register <ваше_имя> <ID_доверенного_лица>"
        )
        return

    name = context.args[0]
    contact_id = context.args[1]

    payload = {
        "telegram_id": user_id,
        "name": name,
        "contact_telegram_id": contact_id
    }
    
    try:
        response = requests.post("http://127.0.0.1:8000/register", json=payload)
        data = response.json()
        
        if data["status"] == "ok":
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"Вы успешно зарегистрированы!\nВаш ID: {data['user_id']}"
            )
        else:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"Ошибка регистрации: {data['message']}"
            )
    except Exception as e:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"Ошибка подключения к серверу: {str(e)}"
        )

async def checkin_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    chat_id = update.effective_chat.id
    
    payload = {"telegram_id": user_id}
    
    try:
        response = requests.post("http://127.0.0.1:8000/checkin", json=payload)
        data = response.json()
        
        if data["status"] == "ok":
            await context.bot.send_message(
                chat_id=chat_id,
                text="✅ Вы отметились! Всё в порядке."
            )
        else:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"❌ Ошибка отметки: {data['message']}"
            )
    except Exception as e:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"❌ Ошибка подключения к серверу: {str(e)}"
        )

# Регистрация обработчиков
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CommandHandler("register", register_cmd))
telegram_app.add_handler(CommandHandler("checkin", checkin_cmd))

# --- Вебхук ---
@app.post("/webhook")
async def webhook_endpoint(request: Request):
    """Обработка вебхука от Telegram"""
    try:
        update_data = await request.json()
        update = Update.de_json(update_data)
        await telegram_app.update_queue.put(update)
        return JSONResponse({"status": "ok"})
    except Exception as e:
        print(f"Ошибка в вебхуке: {e}")
        return JSONResponse({"status": "error"}, status_code=500)

# --- Корневой маршрут ---
@app.get("/")
async def root():
    return {"message": "Всё в порядке? API"}