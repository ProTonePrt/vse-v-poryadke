from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import sqlite3
from datetime import datetime, timedelta
import os
from fastapi.middleware.cors import CORSMiddleware

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
async def register_endpoint( RegisterRequest):
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

# --- Корневой маршрут ---
@app.get("/")
async def root():
    return {"message": "Всё в порядке? API"}