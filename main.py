from fastapi import FastAPI
from pydantic import BaseModel
from datetime import datetime, timedelta
from sqlalchemy import create_engine, Column, Integer, String, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# --- Конфигурация ---
DATABASE_URL = "sqlite:///./users.db"
Base = declarative_base()

# --- Модель пользователя ---
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(String, unique=True, index=True)
    name = str
    checkin_time = Column(DateTime)  # Время последней отметки
    contact_telegram_id = Column(String)  # ID доверенного лица
    enabled = Column(Boolean, default=True)

# --- Pydantic модели ---
class UserCreate(BaseModel):
    telegram_id: str
    name: str
    contact_telegram_id: str

class CheckInRequest(BaseModel):
    telegram_id: str

# --- Приложение ---
from fastapi.middleware.cors import CORSMiddleware
app = FastAPI(title="Всё в порядке?", version="0.1.0")
# --- Настройка CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Для разработки. В продакшене указать точные домены
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Инициализация БД ---
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Эндпоинты ---
@app.post("/register")
async def register_user(user_data: UserCreate):
    db = next(get_db())
    
    # Проверяем, существует ли пользователь
    existing_user = db.query(User).filter(User.telegram_id == user_data.telegram_id).first()
    if existing_user:
        return {"status": "error", "message": "Пользователь уже зарегистрирован"}

    # Создаем нового пользователя
    new_user = User(
        telegram_id=user_data.telegram_id,
        name=user_data.name,
        contact_telegram_id=user_data.contact_telegram_id,
        enabled=True
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return {"status": "ok", "user_id": new_user.id}

@app.post("/checkin")
async def check_in(checkin_data: CheckInRequest):
    db = next(get_db())
    
    user = db.query(User).filter(User.telegram_id == checkin_data.telegram_id).first()
    if not user:
        return {"status": "error", "message": "Пользователь не найден"}
    
    user.checkin_time = datetime.utcnow()
    db.commit()

    return {"status": "ok", "message": "Отметка принята"}

@app.get("/status/{telegram_id}")
async def get_status(telegram_id: str):
    db = next(get_db())
    
    user = db.query(User).filter(User.telegram_id == telegram_id).first()
    if not user:
        return {"status": "error", "message": "Пользователь не найден"}
    
    # Проверяем, был ли чекин за последние 24 часа
    now = datetime.utcnow()
    last_checkin = user.checkin_time or now - timedelta(days=1)  # Если никогда не отмечался
    
    if now - last_checkin > timedelta(hours=24):
        status = "ALARM"
    else:
        status = "OK"
    
    return {
        "status": status,
        "last_checkin": user.checkin_time.isoformat() if user.checkin_time else None,
        "contact_telegram_id": user.contact_telegram_id
    }
# --- Telegram Webhook Handler ---
from telegram.ext import Application
from config import TELEGRAM_BOT_TOKEN
import asyncio

# Создаем приложение Telegram
telegram_app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

@app.post("/webhook")
async def handle_webhook(update: dict):
    """Обработка вебхука от Telegram"""
    from telegram import Update
    
    # Преобразуем словарь в объект Update
    update_obj = Update.de_json(update)
    
    # Передаем обновление в обработчики Telegram Bot
    await telegram_app.process_update(update_obj)
    
    return {"status": "ok"}

# Регистрируем обработчики команд (повторно, для вебхука)
from telegram.ext import CommandHandler

async def start(update, context):
    # Копируем функцию из bot.py
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

async def register(update, context):
    # Копируем функцию из bot.py
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

    import requests
    BASE_URL = "http://127.0.0.1:8000"  # Локальный адрес для сервера
    payload = {
        "telegram_id": user_id,
        "name": name,
        "contact_telegram_id": contact_id
    }
    
    try:
        response = requests.post(f"{BASE_URL}/register", json=payload)
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

async def checkin(update, context):
    # Копируем функцию из bot.py
    user_id = str(update.effective_user.id)
    chat_id = update.effective_chat.id
    
    import requests
    BASE_URL = "http://127.0.0.1:8000"  # Локальный адрес для сервера
    payload = {"telegram_id": user_id}
    
    try:
        response = requests.post(f"{BASE_URL}/checkin", json=payload)
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

# Регистрируем обработчики
telegram_app.add_handler(CommandHandler("start", start))
telegram_app.add_handler(CommandHandler("register", register))
telegram_app.add_handler(CommandHandler("checkin", checkin))

# --- Запуск ---
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)