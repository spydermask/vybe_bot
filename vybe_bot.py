import asyncio
import logging
import aiohttp
import aiosqlite
import ssl
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes,
    MessageHandler, filters
)
import nest_asyncio
nest_asyncio.apply()

BOT_TOKEN = "8148038932:AAFwezssgPDlQtHjOGuuu4s3Sck5sywlyXU"
VYBE_API_KEY = "1vvvcLSPj7UUM6VqHB2hAMJoknZ3UpzXZPZF6TTsnZ8irQ7E"
API_BASE = "https://api.vybenetwork.xyz"

logging.basicConfig(level=logging.INFO)

TOKEN_MAP = {
    "SOL": "So11111111111111111111111111111111111111112",
    "USDC": "Es9vMFrzaCERz7vpgg1UZtRwR6yfMjjfB1XfDksGuoQA",
    "WIF": "7Q52Xbi2bwXnLtbXD5DL4zF6Uyb5KzXos3BrVvZ1FeJG",
    "BONK": "DezXHre4G4fjJzYs9VjTPCh8DNurYEvaE7aRoUZkGmZg",
    "JUP": "JUP4Fb2cqiRUcaTHdrPC8h2gNsA2ETXiPDD33WcGuJB",
    "PYTH": "FsSM8iB1bGu3pVcMdrhWLM5Ws8TrAmv95kj5zszB8GBM"
}

USER_STATES = {}


def get_ssl_session():
    ssl_context = ssl.create_default_context()
    ssl_context.set_ciphers("DEFAULT@SECLEVEL=1")
    return aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=ssl_context))


async def fetch_json(url, headers):
    async with get_ssl_session() as session:
        async with session.get(url, headers=headers) as resp:
            if resp.status != 200:
                return {}
            return await resp.json()


def resolve_token(symbol: str) -> str:
    return TOKEN_MAP.get(symbol.upper(), symbol)


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


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🔔 Alert", callback_data="alert")],
        [InlineKeyboardButton("📋 Alerts", callback_data="alerts")],
        [InlineKeyboardButton("📊 Volume", callback_data="volume")],
        [InlineKeyboardButton("📈 History", callback_data="history")],
        [InlineKeyboardButton("🐋 Whale Alerts", callback_data="whalealerts")],
        [InlineKeyboardButton("🧲 Track Wallet", callback_data="trackwallet")],
        [InlineKeyboardButton("📁 Wallet", callback_data="wallet")],
        [InlineKeyboardButton("💰 Holdings", callback_data="holdings")],
        [InlineKeyboardButton("📝 Transfers", callback_data="transfers")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "👋 Welcome to *VybeBot* – your crypto analyst bot!\n\n"
        "*Here’s what I can do:*\n\n"
        "🔔 `/alert <token> <price>` – Set price alerts\n"
        "📋 `/alerts` – View your active alerts\n"
        "📊 `/volume <token>` – Get 24H trading volume\n"
        "📈 `/history <token>` – View price history\n"
        "🐋 `/whalealerts <token>` – See big whale movements\n"
        "🧲 `/trackwallet <wallet>` – Track wallet activity\n"
        "📁 `/wallet <wallet>` – Full wallet analysis\n"
        "💰 `/holdings <wallet>` – Show token holdings\n"
        "📝 `/transfers <wallet>` – View recent transfers\n\n"
        "🔥 *Just tap a button or type a command to get started!*",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    command = query.data
    USER_STATES[query.from_user.id] = command
    if command == "alert":
        await query.message.reply_text("Enter token and price (e.g., SOL 80):")
    elif command == "alerts":
        await send_alerts(query.from_user.id, query.message)
    elif command in ["wallet", "holdings", "transfers", "trackwallet"]:
        await query.message.reply_text("Enter wallet address:")
    else:
        await query.message.reply_text("Enter token symbol (e.g., SOL, JUP):")


async def send_alerts(user_id, message):
    async with aiosqlite.connect("alerts.db") as db:
        async with db.execute("SELECT token, target_price FROM alerts WHERE user_id = ?", (user_id,)) as cursor:
            rows = await cursor.fetchall()
            if not rows:
                await message.reply_text("📋 You have no active alerts.")
            else:
                text = "\n".join([f"{row[0]} @ ${row[1]}" for row in rows])
                await message.reply_text(f"📋 Your alerts:\n{text}")


async def handle_user_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_input = update.message.text.strip()

    if user_id not in USER_STATES:
        return

    command = USER_STATES.pop(user_id)

    if command == "alert":
        parts = user_input.split()
        if len(parts) != 2:
            await update.message.reply_text("❌ Format: <token> <price>")
            return
        token, price = parts[0].upper(), float(parts[1])
        async with aiosqlite.connect("alerts.db") as db:
            await db.execute("INSERT INTO alerts (user_id, token, target_price) VALUES (?, ?, ?)", (user_id, token, price))
            await db.commit()
        await update.message.reply_text(f"🔔 Alert set for {token} @ ${price}")

    elif command in ["volume", "whalealerts", "history"]:
        token = resolve_token(user_input.upper())
        headers = {"Authorization": f"Bearer {VYBE_API_KEY}"}
        if command == "volume":
            url = f"{API_BASE}/volume?symbol={token}"
            data = await fetch_json(url, headers)
            if not data or "volume_24h" not in data:
                await update.message.reply_text("📊 No volume data.\n\n🔍 Debug:\n" + str(data))
            else:
                volume = float(data.get("volume_24h", 0))
                change = float(data.get("change_24h", 0))
                price = data.get("price", 'N/A')
                direction = "📈 Increasing" if change > 0 else "📉 Decreasing"
                await update.message.reply_text(f"📊 Volume: ${volume:,.2f}\n{direction} ({change:+.2f}%)\n💵 Price: ${price}")

        elif command == "whalealerts":
            url = f"{API_BASE}/whalealerts?symbol={token}"
            data = await fetch_json(url, headers)
            alerts = data.get("whale_alerts", [])
            if not alerts:
                await update.message.reply_text("🐋 No whale alerts.\n\n🔍 Debug:\n" + str(data))
            else:
                msg = "\n".join([f"{tx['amount']} {tx['token']} at ${tx['price']}" for tx in alerts[:5]])
                await update.message.reply_text(f"🐋 Whale Alerts:\n{msg}")

        elif command == "history":
            url = f"{API_BASE}/history?symbol={token}"
            data = await fetch_json(url, headers)
            history = data.get("history", [])
            if not history:
                await update.message.reply_text("📈 No history found.\n\n🔍 Debug:\n" + str(data))
            else:
                highest = max(history, key=lambda x: x['price'])
                lowest = min(history, key=lambda x: x['price'])
                msg = (
                    f"📆 This Month Price Range:\n"
                    f"🔺 Highest: ${highest['price']} on {highest['date']}\n"
                    f"🔻 Lowest: ${lowest['price']} on {lowest['date']}"
                )
                await update.message.reply_text(msg)

    elif command in ["wallet", "holdings", "transfers", "trackwallet"]:
        wallet = user_input.strip()
        headers = {"Authorization": f"Bearer {VYBE_API_KEY}"}
        url = f"{API_BASE}/{command}?wallet={wallet}"
        data = await fetch_json(url, headers)
        if command == "trackwallet":
            await update.message.reply_text(f"🧲 Tracking wallet: {wallet}")
        elif not data:
            await update.message.reply_text(f"❌ No data found for wallet.\n\n🔍 Debug:\n{data}")
        else:
            if command == "wallet":
                tokens = data.get("tokens", [])
                if not tokens:
                    await update.message.reply_text(f"❌ No tokens found in wallet.\n\n🔍 Debug:\n{data}")
                else:
                    msg = "\n".join([f"{t['symbol']}: {t['amount']} (${t['value']})" for t in tokens[:5]])
                    await update.message.reply_text(f"📁 Wallet Summary:\n{msg}")
            elif command == "holdings":
                holdings = data.get("holdings", [])
                if not holdings:
                    await update.message.reply_text(f"❌ No holdings found.\n\n🔍 Debug:\n{data}")
                else:
                    msg = "\n".join([f"{h['symbol']}: {h['amount']} (${h['value']})" for h in holdings[:5]])
                    await update.message.reply_text(f"💰 Holdings:\n{msg}")
            elif command == "transfers":
                transfers = data.get("transfers", [])
                if not transfers:
                    await update.message.reply_text(f"❌ No transfers found.\n\n🔍 Debug:\n{data}")
                else:
                    msg = "\n".join([f"{t['date']} – {t['type']} {t['amount']} {t['symbol']}" for t in transfers[:5]])
                    await update.message.reply_text(f"📝 Recent Transfers:\n{msg}")


async def main():
    await setup_db()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), handle_user_input))
    logging.info("VybeBot is running!")
    await app.run_polling()


if __name__ == "__main__":
    asyncio.run(main())
