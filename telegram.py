import os
import time

import requests

DEFAULT_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def format_investment_message(result: dict) -> str:
    """
    Format investment analysis result for Telegram with HTML formatting.
    Handles both string-based fields and complex nested structures.
    """
    if not result:
        return "No analysis results available."

    # Helper function to escape HTML characters in strings
    def escape_html(text):
        if isinstance(text, str):
            return text.replace("<", "&lt;").replace(">", "&gt;")
        return text

    # Helper function to format lists
    def format_list(items):
        if not items:
            return "None"
        return "\n".join(f"• {escape_html(item)}" for item in items)

    # Helper function to format nested dictionaries
    def format_dict(data):
        if isinstance(data, str):
            return escape_html(data)

        if not isinstance(data, dict):
            return str(data)

        formatted = []
        for key, value in data.items():
            key_display = key.replace("_", " ").title()

            if isinstance(value, list):
                formatted.append(f"<b>{key_display}:</b>\n{format_list(value)}")
            else:
                formatted.append(f"<b>{key_display}:</b> {escape_html(value)}")

        return "\n".join(formatted)

    # Start building message
    message_parts = [
        f"<b>Symbol:</b> {result.get('symbol', 'N/A')}",
        f"<b>Rating:</b> {result.get('rating', 'N/A')}",
        f"<b>Confidence:</b> {result.get('confidence', 'N/A')}",
    ]

    # Add reasoning
    if "reasoning" in result:
        message_parts.append(f"<b>Reasoning:</b> {escape_html(result['reasoning'])}")

    # Add bullish factors if available
    if "bullish_factors" in result:
        message_parts.append(
            f"<b>Bullish Factors:</b>\n{format_list(result['bullish_factors'])}"
        )

    # Add bearish factors if available
    if "bearish_factors" in result:
        message_parts.append(
            f"<b>Bearish Factors:</b>\n{format_list(result['bearish_factors'])}"
        )

    # Add macro impact if available
    if "macro_impact" in result:
        message_parts.append(
            f"<b>Macro Impact:</b> {escape_html(result.get('macro_impact', ''))}"
        )

    # Add enter strategy
    if "enter_strategy" in result:
        message_parts.append(
            f"<b>Enter Strategy:</b>\n{format_dict(result['enter_strategy'])}"
        )

    # Add exit strategy
    if "exit_strategy" in result:
        message_parts.append(
            f"<b>Exit Strategy:</b>\n{format_dict(result['exit_strategy'])}"
        )

    return "\n\n".join(message_parts)


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


def test_send_text_via_telegram():
    data = {
        "symbol": "TEST",
        "rating": 68,
        "confidence": 8,
        "reasoning": "ChromaDex shows strong bullish momentum post-earnings with a 60% surge on 10.9M volume (10x average), breaking above all SMAs ($5.60-$5.64 cluster). Positive fundamentals: FY revenue +19% to $99.6M, first annual profit ($8.6M), and improving margins. Technicals show neutral RSI (48.98) post-surge, MACD nearing bullish crossover, but ADX (9.9) indicates weak trend strength. Risks include potential profit-taking after gap-up and mixed insider selling (net -37k shares last 3M).",
        "enter_strategy": "entry_price: Pullback to $8.50 (near VWAP of $8.97)\nentry_timing: Immediate on confirmed support above $8.50\ntechnical_indicators: Price > SMA 20/50/100, MACD crossover above signal line, volume > 1M shares",
        "exit_strategy": "profit_target: $10.50 (17% gain from $8.97)\nstop_loss: $7.75 (13.6% below entry)\ntime_horizon: 2-3 weeks (pre-earnings quiet period)\nexit_conditions: Close below SMA 20 ($8.50), RSI >70 (overbought), or volume <500k shares (loss of momentum)",
    }
    message = format_investment_message(data)
    send_text_via_telegram(message)

if __name__ == "__main__":
    # test_send_text_via_telegram()
    listen_to_telegram()
