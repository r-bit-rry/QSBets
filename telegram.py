import os
import time

import requests

DEFAULT_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def format_investment_message(result: dict) -> str:
    return (
        f"<b>Symbol:</b> {result['symbol']}\n"
        f"<b>Rating:</b> {result['rating']}\n"
        f"<b>Reasoning:</b> {result['reasoning']}\n\n"
        "<b>Enter Strategy:</b>\n"
        f"  - <b>Entry Price:</b> {result['enter_strategy'].get('entry_price', 'N/A')}\n"
        f"  - <b>Entry Timing:</b> {result['enter_strategy'].get('entry_timing', 'N/A')}\n"
        f"  - <b>Position Sizing:</b> {result['enter_strategy'].get('position_sizing', 'N/A')}\n"
        f"  - <b>Technical Indicators:</b> {result['enter_strategy'].get('technical_indicators', 'N/A')}\n\n"
        "<b>Exit Strategy:</b>\n"
        f"  - <b>Profit Target:</b> {result['exit_strategy'].get('profit_target', 'N/A')}\n"
        f"  - <b>Stop Loss:</b> {result['exit_strategy'].get('stop_loss', 'N/A')}\n"
        f"  - <b>Time Horizon:</b> {result['exit_strategy'].get('time_horizon', 'N/A')}\n"
        f"  - <b>Exit Conditions:</b> {result['exit_strategy'].get('exit_conditions', 'N/A')}\n"
    )


def send_text_via_telegram(content: str, chat_id: str=DEFAULT_CHAT_ID):
    """
    Sends a message via Telegram Bot with Markdown formatting.
    Escapes special characters to avoid parsing errors.
    """
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = {"chat_id": chat_id, "text": content, "parse_mode": "HTML"}
    response = requests.post(url, data=data)
    print(response.json())


def handle_telegram_update(update: dict):
    """
    Handles incoming Telegram updates and responds to the /analyze_hold and /analyze commands.
    """
    message = update.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "").strip()

    if text.startswith("/analyze_hold"):
        parts = text.split()
        if len(parts) >= 3:
            ticker = parts[1]
            price = parts[2]
            prompt = f"Analyze stock I'm currently holding {ticker.upper()} bought at {price}"
        else:
            prompt = (
                "Invalid command format for /analyze_hold. "
                "Usage: /analyze_hold {ticker} {price}"
            )
    elif text.startswith("/analyze"):
        parts = text.split()
        if len(parts) >= 2:
            ticker = parts[1]
            prompt = f"analyze stock {ticker.upper()}"
        else:
            prompt = "Invalid command format for /analyze. " "Usage: /analyze {ticker}"
    else:
        # If the command is not recognized, you might want to ignore or send a default response.
        prompt = "Command not recognized."

    send_text_via_telegram(prompt, chat_id)


def listen_to_telegram():
    """
    Listens for incoming Telegram updates using long polling.
    """
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    url = f"https://api.telegram.org/bot{bot_token}/getUpdates"
    last_update_id = None

    while True:
        params = {"timeout": 100, "offset": last_update_id}
        response = requests.get(url, params=params)
        updates = response.json().get("result", [])

        for update in updates:
            handle_telegram_update(update)
            last_update_id = update["update_id"] + 1

        time.sleep(1)


if __name__ == "__main__":
    listen_to_telegram()
