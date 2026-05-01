import os

# Kichik harfli nomlar bilan ham ishlaydi
BOT_TOKEN = os.getenv("BOT_TOKEN") or os.getenv("bot_token")
ADMIN_ID = int(os.getenv("ADMIN_ID") or os.getenv("admin_id") or "123456789")

if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN topilmadi! Environment variable ga BOT_TOKEN qo'shing.")
