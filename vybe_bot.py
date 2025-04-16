import logging
import random
import nest_asyncio
import asyncio
import httpx
import ssl
import os
from dotenv import load_dotenv
import time
from typing import Optional
import aiohttp
import aiosqlite
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes  # Added MessageHandler and filters

nest_asyncio.apply()

# Load environment variables from .env file
load_dotenv()

# === CONFIG ===
RUGCHECK_API_URL = "https://api.rugcheck.xyz/v1"
RUGCHECK_API_KEY = os.getenv("RUGCHECK_API_KEY")  # Make sure to set this as an environment variable
BOT_TOKEN = os.getenv("BOT_TOKEN")  # Make sure to set this as an environment variable
DB_FILE = "alerts.db"
COINGECKO_URL = "https://api.coingecko.com/api/v3"
SOLANAFM_API_KEY = os.getenv("SOLANAFM_API_KEY")  # Make sure to set this as an environment variable

# === SETUP ===
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

ssl_ctx = ssl.create_default_context()

# === TOKEN NORMALIZATION ===
TOKEN_ALIASES = {
    "SOL": "solana",
    "ETH": "ethereum",
    "BTC": "bitcoin",
}

def normalize_token(symbol: str):
    return TOKEN_ALIASES.get(symbol.upper(), symbol.lower())

# === UTILS ===
async def get_token_risk_score(token, session, retries=3, backoff=1):
    token = normalize_token(token)
    url = f"{RUGCHECK_API_URL}/token/{token}/risk"
    headers = {"Authorization": f"Bearer {RUGCHECK_API_KEY}"}
    try:
        async with session.get(url, headers=headers) as res:
            if res.status == 200:
                data = await res.json()
                return data.get("risk_score", 0)
            elif res.status == 429:  # Rate limit exceeded
                if retries > 0:
                    await asyncio.sleep(backoff)
                    return await get_token_risk_score(token, session, retries - 1, backoff * 2)
                else:
                    logger.warning(f"Rate limit exceeded. Max retries reached.")
                    return None
            else:
                logger.error(f"Error fetching risk score for {token}: {res.status}")
                return None
    except Exception as e:
        logger.error(f"Exception while fetching risk score for {token}: {e}")
        return None


async def alert_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("⚠️ Usage: /alert <token> <price>")
        return
    token = args[0]
    try:
        price = float(args[1])
    except ValueError:
        await update.message.reply_text("⚠️ Invalid price value.")
        return
    response = await add_alert(update.message.from_user.id, token, price)
    await update.message.reply_text(response)


async def alerts_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    alerts = await get_alerts(update.message.from_user.id)
    if alerts:
        msg = "\n".join([f"• {a['token']} @ ${a['price']}" for a in alerts])
        await update.message.reply_text(f"📋 *Your alerts:*\n{msg}", parse_mode='Markdown')
    else:
        await update.message.reply_text("ℹ️ You have no active alerts.")

async def risk_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("⚠️ Usage: /risk <token>")
        return
    token = args[0]
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_ctx)) as session:
        risk_score = await get_token_risk_score(token, session)
        if risk_score is not None:
            await update.message.reply_text(f"🔍 The risk score for {token} is: {risk_score}")
        else:
            await update.message.reply_text("⚠️ Unable to fetch risk score.")

async def wallet_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if not args:
        await update.message.reply_text("⚠️ Usage: /wallet <wallet_address>")
        return
    wallet = args[0]
    async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_ctx)) as session:
        balances = await get_wallet_balances(wallet, session)
        if balances:
            await update.message.reply_text(f"📊 Wallet balances:\n{balances}")
        else:
            await update.message.reply_text("⚠️ Unable to fetch wallet profile.")

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⚠️ Unknown command.")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    parts = text.split()
    if len(parts) == 2:
        token, price_str = parts
        try:
            price = float(price_str)
            response = await add_alert(update.message.from_user.id, token, price)
            await update.message.reply_text(response)
        except ValueError:
            await update.message.reply_text("⚠️ Invalid price format. Please enter a number.")
    elif len(parts) == 1:
        input_str = parts[0]
        if len(input_str) == 44:  # Assuming Solana wallet addresses are 44 characters
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_ctx)) as session:
                balances = await get_wallet_balances(input_str, session)
                if balances:
                    await update.message.reply_text(f"📊 Wallet balances:\n{balances}")
                else:
                    await update.message.reply_text("⚠️ Unable to fetch wallet profile.")
        else:
            async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_ctx)) as session:
                risk_score = await get_token_risk_score(input_str, session)
                if risk_score is not None:
                    await update.message.reply_text(f"🔍 The risk score for {input_str} is: {risk_score}")
                else:
                    await update.message.reply_text("⚠️ Unable to fetch risk score.")
    else:
        await update.message.reply_text("⚠️ Unrecognized input format.")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == "set_alert":
        await query.edit_message_text("📌 Use /alert <token> <price> to set an alert.")
    elif data == "check_risk":
        await query.edit_message_text("🔍 Use /risk <token> to check the risk score.")
    elif data == "wallet_balance":
        await query.edit_message_text("💼 Use /wallet <address> to view wallet balance.")
    elif data == "view_alerts":
        alerts = await get_alerts(query.from_user.id)
        if alerts:
            msg = "\n".join([f"• {a['token']} @ ${a['price']}" for a in alerts])
            await query.edit_message_text(f"📋 *Your alerts:*\n{msg}", parse_mode='Markdown')
        else:
            await query.edit_message_text("ℹ️ You have no active alerts.")

# === DATABASE ===
async def init_db():
    async with aiosqlite.connect(DB_FILE) as db:
        await db.execute(""" 
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                token TEXT NOT NULL,
                price REAL NOT NULL
            )
        """)
        await db.commit()

async def add_alert(user_id, token, price):
    # Check if alert already exists
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT id FROM alerts WHERE user_id = ? AND token = ? AND price = ?", (user_id, token, price)) as cursor:
            existing_alert = await cursor.fetchone()
            if existing_alert:
                return "⚠️ You already have this alert set."
        await db.execute("INSERT INTO alerts (user_id, token, price) VALUES (?, ?, ?)", (user_id, token, price))
        await db.commit()
        return f"✅ Alert set for {token} at ${price}"

async def get_alerts(user_id):
    async with aiosqlite.connect(DB_FILE) as db:
        async with db.execute("SELECT token, price FROM alerts WHERE user_id = ?", (user_id,)) as cursor:
            rows = await cursor.fetchall()
            return [{"token": row[0], "price": row[1]} for row in rows]

# === BOT SETUP ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.message.from_user
    await update.message.reply_text(f"Hi {user.first_name}! Welcome to the Rug Check Bot.")

def main():
    application = Application.builder().token(BOT_TOKEN).build()

    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("alert", alert_command))
    application.add_handler(CommandHandler("alerts", alerts_command))
    application.add_handler(CommandHandler("risk", risk_command))
    application.add_handler(CommandHandler("wallet", wallet_command))

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))

    application.run_polling()

if __name__ == "__main__":
    asyncio.run(init_db())
    main()
