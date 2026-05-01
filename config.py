import os

BOT_TOKEN = os.getenv("8617458668:AAF46pmvmBKrD4SNXXKVirNCqz9Oul6tMY4")
if not BOT_TOKEN:
    raise ValueError("❌ BOT_TOKEN topilmadi! Environment variable ga BOT_TOKEN qo'shing.")

ADMIN_ID = int(os.getenv("ADMIN_ID", "1199320930"))
