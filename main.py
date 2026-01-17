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

# --- Запуск ---
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)