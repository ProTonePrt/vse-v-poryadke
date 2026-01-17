from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram import Update
import requests
import asyncio
from config import TELEGRAM_BOT_TOKEN

# --- Глобальные переменные ---
BASE_URL = "http://127.0.0.1:8000"

# --- Команды бота ---

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

async def register(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    chat_id = update.effective_chat.id
    
    # Проверяем, есть ли аргументы
    if len(context.args) < 2:
        await context.bot.send_message(
            chat_id=chat_id,
            text="Используйте: /register <ваше_имя> <ID_доверенного_лица>"
        )
        return

    name = context.args[0]
    contact_id = context.args[1]

    # Отправляем запрос на регистрацию
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

async def checkin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    chat_id = update.effective_chat.id
    
    # Отправляем запрос на отметку
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

# --- Основная функция запуска бота ---
def main():
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("register", register))
    application.add_handler(CommandHandler("checkin", checkin))
    
    # Запускаем бота
    application.run_polling()

if __name__ == "__main__":
    main()