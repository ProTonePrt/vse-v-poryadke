from telegram.ext import Application, CommandHandler, ContextTypes
from telegram import Update
import requests
import asyncio
import os
from config import TELEGRAM_BOT_TOKEN

# Создаем приложение Telegram
bot_app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

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
bot_app.add_handler(CommandHandler("start", start))
bot_app.add_handler(CommandHandler("register", register_cmd))
bot_app.add_handler(CommandHandler("checkin", checkin_cmd))

if __name__ == "__main__":
    asyncio.run(bot_app.run_polling())