import asyncio
import logging
import aiohttp
import aiosqlite
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import nest_asyncio
import re
import ssl

# Apply nested event loop patch (useful in Jupyter/Windows)
nest_asyncio.apply()

# Config
BOT_TOKEN = "8148038932:AAFwezssgPDlQtHjOGuuu4s3Sck5sywlyXU"
VYBE_API_KEY = "1vvvcLSPj7UUM6VqHB2hAMJoknZ3UpzXZPZF6TTsnZ8irQ7E"
API_BASE = "https://alpha.vybenetwork.com"

# Logging
logging.basicConfig(level=logging.INFO)

# SSL Session with lower security level for Vybe API (if needed)
def get_ssl_session():
    ssl_context = ssl.create_default_context()
    ssl_context.set_ciphers("DEFAULT@SECLEVEL=1")
    return aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context))

# Setup SQLite DB
async def setup_db():
    async with aiosqlite.connect("alerts.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                user_id INTEGER,
                token TEXT,
                target_price REAL
            )
        """)
        await db.commit()

# Welcome /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("📈 Set Alert", callback_data='/alert')],
        [InlineKeyboardButton("🔍 Wallet Analysis", callback_data='/wallet')],
        [InlineKeyboardButton("🐋 Whale Alerts", callback_data='/whalealerts')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        """👋 Welcome to *VybeBot* – your crypto analyst bot!

*Here’s what I can do:*

🔔 /alert `<token>` `<price>` – Set price alerts  
📋 /alerts – View your active alerts  
📊 /volume `<token>` – Get 24H trading volume  
📈 /history `<token>` – View price history  
🐋 /whalealerts `<token>` – See big whale movements  
🧾 /trackwallet `<wallet>` – Track wallet activity  
📁 /wallet `<wallet>` – Full wallet analysis  
💰 /holdings `<wallet>` – Show token holdings  
🔄 /transfers `<wallet>` – View recent transfers

🔥 Just type a command to get started!
""",
        parse_mode="Markdown",
        reply_markup=reply_markup
    )

# JSON Fetcher
async def fetch_json(url, headers):
    async with get_ssl_session() as session:
        async with session.get(url, headers=headers) as resp:
            if resp.headers.get("Content-Type", "").startswith("application/json"):
                return await resp.json()
            else:
                text = await resp.text()
                logging.error(f"Unexpected content type at {url}: {text}")
                return {}

# /alert
async def set_alert(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) != 2:
        await update.message.reply_text("Usage: /alert ETH 3000")
        return
    token = context.args[0].upper()
    try:
        price = float(context.args[1])
    except ValueError:
        await update.message.reply_text("Invalid price.")
        return

    async with aiosqlite.connect("alerts.db") as db:
        await db.execute("INSERT INTO alerts (user_id, token, target_price) VALUES (?, ?, ?)",
                         (update.effective_user.id, token, price))
        await db.commit()

    await update.message.reply_text(f"Alert set for {token} at ${price}")

# /alerts
async def show_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with aiosqlite.connect("alerts.db") as db:
        async with db.execute("SELECT token, target_price FROM alerts WHERE user_id = ?",
                              (update.effective_user.id,)) as cursor:
            rows = await cursor.fetchall()

    if not rows:
        await update.message.reply_text("No alerts found.")
    else:
        message = "\n".join([f"{row[0]} ➜ ${row[1]}" for row in rows])
        await update.message.reply_text(message)

# /volume
async def token_volume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /volume ETH")
        return
    token = context.args[0].upper()
    url = f"{API_BASE}/v1/volume?symbol={token}"
    headers = {"Authorization": f"Bearer {VYBE_API_KEY}"}
    data = await fetch_json(url, headers)
    volume = data.get("volume_24h", "N/A")
    await update.message.reply_text(f"24H Volume for {token}: ${volume}")

# /trackwallet
async def track_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /trackwallet <wallet_address>")
        return
    wallet = context.args[0]
    if not re.match(r'^(0x)?[0-9a-fA-F]{40}$', wallet):
        await update.message.reply_text("Invalid wallet address format.")
        return
    url = f"{API_BASE}/v1/wallet/{wallet}"
    headers = {"Authorization": f"Bearer {VYBE_API_KEY}"}
    data = await fetch_json(url, headers)
    txs = data.get("transactions", [])
    if not txs:
        await update.message.reply_text("No transactions found.")
        return
    tx_log = "\n".join([f"{tx['date']}: {tx['amount']} {tx['token']}" for tx in txs[:5]])
    await update.message.reply_text(f"Recent Transactions:\n{tx_log}")

# /whalealerts
async def whale_alerts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /whalealerts ETH")
        return
    token = context.args[0].upper()
    url = f"{API_BASE}/v1/whalealerts?symbol={token}"
    headers = {"Authorization": f"Bearer {VYBE_API_KEY}"}
    data = await fetch_json(url, headers)
    alerts = data.get("whale_alerts", [])
    if not alerts:
        await update.message.reply_text("No whale alerts for now.")
    else:
        message = "\n".join([f"{tx['amount']} {tx['token']} at ${tx['price']}" for tx in alerts[:5]])
        await update.message.reply_text(f"🐋 Whale Alerts:\n{message}")

# /wallet
async def wallet_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /wallet <wallet_address>")
        return
    wallet = context.args[0]
    url = f"{API_BASE}/v1/wallet/{wallet}"
    headers = {"Authorization": f"Bearer {VYBE_API_KEY}"}
    data = await fetch_json(url, headers)
    value = data.get("portfolio_value", 0)
    tokens = len(data.get("tokens", []))
    whale = "✅" if value > 10000 else "⭕ Not a whale"
    await update.message.reply_text(
        f"📦 Wallet Summary for {wallet[:6]}...\n- Portfolio: ${value}\n- Tokens: {tokens}\n- Whale Status: {whale}"
    )

# /holdings
async def wallet_holdings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /holdings <wallet_address>")
        return
    wallet = context.args[0]
    url = f"{API_BASE}/v1/wallet/{wallet}"
    headers = {"Authorization": f"Bearer {VYBE_API_KEY}"}
    data = await fetch_json(url, headers)
    holdings = data.get("tokens", [])
    if not holdings:
        await update.message.reply_text("No holdings found.")
        return
    output = "\n".join([f"- {t['token']}: {t['balance']} (${t['value']})" for t in holdings])
    await update.message.reply_text(f"💼 Token Holdings:\n{output}")

# /transfers
async def wallet_transfers(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /transfers <wallet_address>")
        return
    wallet = context.args[0]
    url = f"{API_BASE}/v1/wallet/{wallet}/transfers"
    headers = {"Authorization": f"Bearer {VYBE_API_KEY}"}
    data = await fetch_json(url, headers)
    txs = data.get("transfers", [])
    if not txs:
        await update.message.reply_text("No recent transfers.")
        return
    msg = "\n".join([f"{tx['date']}: {tx['token']} {tx['amount']}" for tx in txs[:5]])
    await update.message.reply_text(f"🔁 Recent Transfers:\n{msg}")

# /history
async def price_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /history ETH")
        return
    token = context.args[0].upper()
    url = f"{API_BASE}/v1/history?symbol={token}"
    headers = {"Authorization": f"Bearer {VYBE_API_KEY}"}
    data = await fetch_json(url, headers)
    history = data.get("history", [])
    if not history:
        await update.message.reply_text("No history found.")
        return
    msg = "\n".join([f"{row['date']}: ${row['price']}" for row in history[-5:]])
    await update.message.reply_text(f"📉 Price History for {token}:\n{msg}")

# Price fetch for alerts
async def fetch_price(token):
    url = f"{API_BASE}/v1/price?symbol={token}"
    headers = {"Authorization": f"Bearer {VYBE_API_KEY}"}
    data = await fetch_json(url, headers)
    return float(data.get("price", 0))

# Background alert monitor
async def monitor_alerts(app):
    while True:
        try:
            async with aiosqlite.connect("alerts.db") as db:
                async with db.execute("SELECT DISTINCT token FROM alerts") as cursor:
                    tokens = [row[0] for row in await cursor.fetchall()]
                for token in tokens:
                    price = await fetch_price(token)
                    async with db.execute("SELECT user_id, target_price FROM alerts WHERE token = ?", (token,)) as cursor:
                        rows = await cursor.fetchall()
                    for user_id, target_price in rows:
                        if price >= target_price:
                            await app.bot.send_message(user_id, f"{token} reached ${price} (Target: ${target_price})")
                            await db.execute("DELETE FROM alerts WHERE user_id = ? AND token = ? AND target_price = ?",
                                             (user_id, token, target_price))
                            await db.commit()
        except Exception as e:
            logging.error(f"Alert monitoring error: {e}")
        await asyncio.sleep(30)

# Main entry point
async def main():
    await setup_db()
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("alert", set_alert))
    app.add_handler(CommandHandler("alerts", show_alerts))
    app.add_handler(CommandHandler("volume", token_volume))
    app.add_handler(CommandHandler("trackwallet", track_wallet))
    app.add_handler(CommandHandler("whalealerts", whale_alerts))
    app.add_handler(CommandHandler("wallet", wallet_summary))
    app.add_handler(CommandHandler("holdings", wallet_holdings))
    app.add_handler(CommandHandler("transfers", wallet_transfers))
    app.add_handler(CommandHandler("history", price_history))

    asyncio.create_task(monitor_alerts(app))
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
