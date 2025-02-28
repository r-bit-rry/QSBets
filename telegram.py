import os

import requests


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


def send_text_via_telegram(content: str):
    """
    Sends a message via Telegram Bot with Markdown formatting.
    Escapes special characters to avoid parsing errors.
    """
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = {"chat_id": chat_id, "text": content, "parse_mode": "HTML"}
    response = requests.post(url, data=data)
    print(response.json())
