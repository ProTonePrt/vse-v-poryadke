import requests
from config import TELEGRAM_BOT_TOKEN

WEBHOOK_URL = "https://vse-v-poryadke-production.up.railway.app/webhook"

url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/setWebhook"
payload = {"url": WEBHOOK_URL}

response = requests.post(url, json=payload)
print(response.json())