

```markdown
# Rug Check Telegram Bot

## Overview
The **Rug Check Telegram Bot** is a Telegram bot that helps cryptocurrency users check the risk of tokens, set price alerts, and check wallet balances. The bot integrates with the **RugCheck API** to evaluate token risk scores, supports price alerts for specific tokens, and can fetch wallet balances for Solana addresses.

## Features
- **Risk Score Check**: Check the risk score of any supported token.
- **Price Alerts**: Set price alerts for specific tokens, and the bot will notify you when the price hits the set threshold.
- **Wallet Balance Check**: Check the balance of a Solana wallet address.
- **User-Friendly Commands**: The bot has easy-to-use commands for checking risks, setting alerts, and querying wallet balances.

## Table of Contents
- [Features](#features)
- [Setup Instructions](#setup-instructions)
- [Bot Commands](#bot-commands)
- [Database](#database)
- [Running the Bot](#running-the-bot)
- [Logging](#logging)
- [Error Handling](#error-handling)
- [Future Enhancements](#future-enhancements)
- [Contributing](#contributing)
- [License](#license)

## Setup Instructions

### 1. Clone the Repository
Clone the repository to your local machine.

```bash
git clone <repository_url>
```

### 2. Install Dependencies
Install the required Python dependencies using `pip`.

```bash
pip install -r requirements.txt
```

Make sure to install the necessary libraries such as `aiohttp`, `aiosqlite`, and `python-telegram-bot`.

### 3. Set Up Environment Variables
Create a `.env` file in the project root directory and add the following variables:

```env
RUGCHECK_API_KEY=<your_rugcheck_api_key>
BOT_TOKEN=<your_telegram_bot_token>
SOLANAFM_API_KEY=<your_solana_api_key>
```

### 4. Run the Bot
Once the dependencies are installed and environment variables are set up, run the bot.

```bash
python rug.py
```

The bot should now be running and accessible via Telegram.

## Bot Commands

- `/start`: Starts the bot and displays a welcome message.
- `/alert <token> <price>`: Sets an alert for a token when the price reaches the specified threshold.
- `/alerts`: Displays a list of all active price alerts set by the user.
- `/risk <token>`: Fetches and displays the risk score for a specified token.
- `/wallet <wallet_address>`: Fetches and displays the wallet balance of a provided Solana address.

## Database

The bot uses an SQLite database (`alerts.db`) to store user-specific price alerts. The database schema consists of the following table:

### **alerts**
This table stores the price alerts set by users.

```sql
CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    token TEXT NOT NULL,
    price REAL NOT NULL
);
```

## Running the Bot

To start using the bot, ensure the following:
1. Clone the repository and install dependencies.
2. Set up the required environment variables.
3. Run the bot by executing the Python script.

```bash
python rug.py
```

Once the bot is running, interact with it on Telegram using the commands mentioned above.

## Logging

The bot uses Python’s built-in `logging` module to log important events, such as errors or successful interactions. Logs are printed to the terminal during bot execution.

## Error Handling

The bot includes error handling for common issues, such as:
- Invalid input from users (e.g., unrecognized tokens).
- Network errors when interacting with the RugCheck API or Solana blockchain.
- Database interaction errors.

The bot will notify users of errors through Telegram messages and log these errors for debugging purposes.

## Future Enhancements

The following features are planned for future versions of the bot:

- **Price Tracking**: Notify users when a token's price changes and hits their alert price.
- **Multi-Blockchain Support**: Extend wallet balance checks to support other blockchains in addition to Solana.
- **Rate Limit Handling**: Implement better rate-limiting for handling frequent API requests.

## Contributing

Contributions are welcome! To contribute to the project:
1. Fork the repository.
2. Create a new branch for your changes.
3. Commit your changes and push them to your forked repository.
4. Open a pull request to merge your changes into the main repository.

Please ensure that your changes are well-tested and follow Python’s PEP 8 style guidelines.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

### Thank you for using the **Rug Check Telegram Bot**!

```

This `README.md` covers the core functionality, setup instructions, and additional sections such as database details and logging for your bot project. You can further customize the sections as needed.
