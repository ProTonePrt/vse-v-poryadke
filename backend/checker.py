import asyncio
import requests
from datetime import datetime, timedelta
from telegram.ext import Application
from config import TELEGRAM_BOT_TOKEN
import time

# --- Глобальные переменные ---
BASE_URL = "http://127.0.0.1:8000"
CHECK_INTERVAL_SECONDS = 30  # Проверять каждые 30 секунд (для теста). В продакшене — 3600 (1 час)

class StatusChecker:
    def __init__(self):
        self.bot_app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    async def send_telegram_message(self, chat_id, message):
        """Отправка сообщения в Telegram"""
        try:
            await self.bot_app.updater.bot.send_message(chat_id=chat_id, text=message)
            print(f"✅ Сообщение отправлено {chat_id}: {message}")
        except Exception as e:
            print(f"❌ Ошибка отправки в Telegram {chat_id}: {e}")

    async def check_users(self):
        """Проверка статусов всех пользователей"""
        try:
            # Простой тест: проверим твой ID
            user_id = "347445457"
            
            print(f"Проверка пользователя {user_id}...")
            
            response = requests.get(f"{BASE_URL}/status/{user_id}")
            if response.status_code != 200:
                print(f"❌ Ошибка HTTP {response.status_code} при запросе /status/{user_id}")
                return
                
            data = response.json()
            print(f"📊 Получен ответ: {data}")
            
            if data.get("status") == "ALARM":
                contact_id = data.get("contact_telegram_id")
                
                if contact_id and contact_id != "None":
                    alarm_message = f"⚠️ ТРЕВОГА: Пользователь {user_id} не отмечался более 24 часов!"
                    await self.send_telegram_message(contact_id, alarm_message)
                    print(f"✅ Отправлено уведомление контакту {contact_id}")
                else:
                    print("ℹ️ Контакт не указан или пустой")
            else:
                print("🟢 Статус OK, уведомление не требуется")
                
        except Exception as e:
            print(f"❌ Ошибка при проверке статусов: {e}")

    async def run_checker(self):
        """Основной цикл проверки"""
        print(f"🚀 Запуск проверки статусов. Интервал: {CHECK_INTERVAL_SECONDS} секунд")
        
        while True:
            try:
                await self.check_users()
            except Exception as e:
                print(f"❌ Ошибка в цикле проверки: {e}")
            
            await asyncio.sleep(CHECK_INTERVAL_SECONDS)

# --- Запуск ---
if __name__ == "__main__":
    checker = StatusChecker()
    asyncio.run(checker.run_checker())