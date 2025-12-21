import os
import sqlite3
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.tl.functions.messages import ImportChatInviteRequest

API_ID = int(os.getenv("API_ID"))
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")

BASE_PATH = "/app"
SESSION_PATH = f"{BASE_PATH}/sessions"
DB_PATH = f"{BASE_PATH}/accounts.db"

os.makedirs(SESSION_PATH, exist_ok=True)

db = sqlite3.connect(DB_PATH, check_same_thread=False)
cur = db.cursor()
cur.execute("CREATE TABLE IF NOT EXISTS accounts (phone TEXT PRIMARY KEY)")
db.commit()

sessions = {}
step = {}

async def keep_alive():
    while True:
        for client in sessions.values():
            try:
                await client.connect()
            except:
                pass
        await asyncio.sleep(20)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 Bot Active\n"
        "/login - Add account\n"
        "/st - Account list\n"
        "/join - Channel join\n"
    )

async def login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.message.chat_id
    step[uid] = "phone"
    await update.message.reply_text("📱 Phone भेजो:")

async def text_handler(update, context):
    uid = update.message.chat_id
    txt = update.message.text

    if uid not in step:
        return

    if step[uid] == "phone":
        phone = txt
        cur.execute("INSERT OR IGNORE INTO accounts VALUES (?)", (phone,))
        db.commit()

        client = TelegramClient(f"{SESSION_PATH}/{phone}", API_ID, API_HASH)
        await client.connect()
        await client.send_code_request(phone)

        sessions[phone] = client
        step[uid] = "otp"
        return await update.message.reply_text("📩 OTP भेजो:")

    if step[uid] == "otp":
        phone = list(sessions.keys())[-1]
        client = sessions[phone]

        try:
            await client.sign_in(phone, txt)
            step.pop(uid)
            return await update.message.reply_text("🔥 Login success!")
        except SessionPasswordNeededError:
            step[uid] = "pwd"
            return await update.message.reply_text("🔐 Password भेजो:")
        except:
            return await update.message.reply_text("❌ OTP गलत!")

async def join(update: Update, context):
    uid = update.message.chat_id
    step[uid] = "join"
    await update.message.reply_text("📌 Link भेजो:")

async def join_handler(update: Update, context):
    uid = update.message.chat_id
    if uid not in step or step[uid] != "join":
        return

    link = update.message.text
    step.pop(uid)

    msg = ""
    for phone, client in sessions.items():
        try:
            await client.connect()

            if "/+" in link:
                h = link.split("/")[-1].replace("+", "")
                await client(ImportChatInviteRequest(h))
                msg += f"{phone} → PRIVATE OK\n"
            else:
                u = link.split("/")[-1]
                await client(JoinChannelRequest(u))
                msg += f"{phone} → PUBLIC OK\n"

        except:
            msg += f"{phone} → FAIL\n"

    await update.message.reply_text(msg)

async def st(update: Update, context):
    text = ""
    for phone, client in sessions.items():
        try:
            await client.connect()
            text += f"{phone} 🟢 Online\n"
        except:
            text += f"{phone} 🔴 Offline\n"

    await update.message.reply_text(text)

async def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("login", login))
    app.add_handler(CommandHandler("join", join))
    app.add_handler(CommandHandler("st", st))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, join_handler))

    asyncio.create_task(keep_alive())
    print("BOT RUNNING 🔥🔥🔥")
    await app.run_polling()

asyncio.run(main())
