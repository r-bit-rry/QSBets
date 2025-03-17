import os
import time

import requests
from event_driven.event_bus import EventBus, EventType
from summarize.utils import dump_failed_text


DEFAULT_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def format_investment_message(result: dict) -> str:
    """
    Format investment analysis result for Telegram with HTML formatting.
    Handles both string-based fields and complex nested structures.
    Supports both standard analysis and hold position analysis schemas.
    """
    try:
        if not result:
            return "No analysis results available."

        # Helper function to escape HTML characters in strings
        def escape_html(text):
            if isinstance(text, str):
                return text.replace("<", "&lt;").replace(">", "&gt;")
            return str(text)

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
                return escape_html(data)

            formatted = []
            for key, value in data.items():
                key_display = key.replace("_", " ").title()

                if isinstance(value, list):
                    formatted.append(f"<b>{key_display}:</b>\n{format_list(value)}")
                else:
                    formatted.append(f"<b>{key_display}:</b> {escape_html(value)}")

            return "\n".join(formatted)

        # Filter out internal fields that shouldn't be displayed
        displayed_result = {k: v for k, v in result.items() 
                        if k not in ['request_id', 'requested_by']}
        
        # Start building message
        message_parts = [
            f"<b>Symbol:</b> {displayed_result.get('symbol', 'N/A')}",
            f"<b>Rating:</b> {displayed_result.get('rating', 'N/A')}",
            f"<b>Confidence:</b> {displayed_result.get('confidence', 'N/A')}",
        ]
        
        # Detect if this is a hold position analysis by checking for specific fields
        is_hold_analysis = 'purchase_price' in displayed_result
        
        # Add hold position specific information
        if is_hold_analysis:
            # Add purchase info
            if "purchase_price" in displayed_result:
                message_parts.insert(1, f"<b>Purchase Price:</b> {displayed_result.get('purchase_price', 'N/A')}")
            
            # Add current price if available
            if "current_price" in displayed_result:
                message_parts.insert(2, f"<b>Current Price:</b> {displayed_result.get('current_price', 'N/A')}")
            
            # Add unrealized gain/loss if available
            if "unrealized_gain_loss_pct" in displayed_result:
                message_parts.insert(3, f"<b>Unrealized Gain/Loss:</b> {displayed_result.get('unrealized_gain_loss_pct', 'N/A')}%")

        # Add reasoning
        if "reasoning" in displayed_result:
            message_parts.append(f"<b>Reasoning:</b> {escape_html(displayed_result['reasoning'])}")

        # Add factors based on schema type
        if is_hold_analysis:
            # Add hold factors if available
            if "hold_factors" in displayed_result:
                message_parts.append(
                    f"<b>Hold Factors:</b>\n{format_list(displayed_result['hold_factors'])}"
                )
                
            # Add risk factors if available
            if "risk_factors" in displayed_result:
                message_parts.append(
                    f"<b>Risk Factors:</b>\n{format_list(displayed_result['risk_factors'])}"
                )
            
            # Add exit conditions if available
            if "exit_conditions" in displayed_result:
                message_parts.append(
                    f"<b>Exit Conditions:</b>\n{format_list(displayed_result['exit_conditions'])}"
                )
        else:
            # Add bullish factors if available
            if "bullish_factors" in displayed_result:
                message_parts.append(
                    f"<b>Bullish Factors:</b>\n{format_list(displayed_result['bullish_factors'])}"
                )

            # Add bearish factors if available
            if "bearish_factors" in displayed_result:
                message_parts.append(
                    f"<b>Bearish Factors:</b>\n{format_list(displayed_result['bearish_factors'])}"
                )

        # Add macro impact if available
        if "macro_impact" in displayed_result:
            message_parts.append(
                f"<b>Macro Impact:</b> {escape_html(displayed_result.get('macro_impact', ''))}"
            )

        # Add strategy sections based on schema type
        if is_hold_analysis:
            # Add exit strategy
            if "exit_strategy" in displayed_result:
                message_parts.append(
                    f"<b>Exit Strategy:</b>\n{format_dict(displayed_result['exit_strategy'])}"
                )
        else:
            # Add enter strategy
            if "enter_strategy" in displayed_result:
                message_parts.append(
                    f"<b>Enter Strategy:</b>\n{format_dict(displayed_result['enter_strategy'])}"
                )

            # Add exit strategy
            if "exit_strategy" in displayed_result:
                message_parts.append(
                    f"<b>Exit Strategy:</b>\n{format_dict(displayed_result['exit_strategy'])}"
                )

        return "\n\n".join(message_parts)
    
    except Exception as e:
        # Import needed only if there's an exception
        error_message = f"Failed to format message: {str(e)}\nOriginal data: {str(result)}"
        dump_failed_text(error_message)
        return f"Error formatting analysis results. Details have been logged. Error: {str(e)}"

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
    Handles incoming Telegram updates and processes /analyze_hold and /analyze commands.
    Adds commands to the analysis queue and reports back to the user.
    """
    message = update.get("message", {})
    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "").strip()

    if text.startswith("/analyze_hold"):
        parts = text.split()
        if len(parts) >= 3:
            ticker = parts[1].upper()
            purchase_price = parts[2]
            confirmation_msg = f"Adding {ticker} (owned at {purchase_price}) to analysis queue with high priority"

            # Publish the event to the EventBus for priority analysis
            EventBus().publish(
                EventType.TELEGRAM_COMMAND,
                {
                    "action": "own",
                    "ticker": ticker,
                    "purchase_price": purchase_price,
                    "chat_id": chat_id,
                },
            )
        else:
            confirmation_msg = "Invalid command format for /analyze_hold. Usage: /analyze_hold {ticker} {purchase_price}"

    elif text.startswith("/analyze"):
        parts = text.split()
        if len(parts) >= 2:
            ticker = parts[1].upper()
            confirmation_msg = (
                f"Adding {ticker} to analysis queue with high priority..."
            )

            # Publish the event to the EventBus for priority analysis
            EventBus().publish(
                EventType.TELEGRAM_COMMAND,
                {
                    "action": "buy",
                    "ticker": ticker,
                    "chat_id": chat_id,
                },
            )
        else:
            confirmation_msg = (
                "Invalid command format for /analyze. Usage: /analyze {ticker}"
            )

    else:
        confirmation_msg = "Command not recognized. Available commands: /analyze {ticker} or /analyze_hold {ticker} {purchase_price}"

    # Send confirmation message back to user
    send_text_via_telegram(confirmation_msg, chat_id)


def listen_to_telegram():
    """
    Listens for incoming Telegram updates using long polling without storing state.
    Uses Telegram's offset parameter to mark messages as read.
    """
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    url = f"https://api.telegram.org/bot{bot_token}/getUpdates"

    # First, get the current update_id to start from
    try:
        # Get the latest update_id without processing messages
        response = requests.get(f"{url}?limit=1")
        result = response.json().get("result", [])

        # If there are any updates, start from the next one
        offset = result[0]["update_id"] + 1 if result else None
        print(f"Starting Telegram listener from update_id: {offset or 'latest'}")
    except Exception as e:
        print(f"Error initializing Telegram offset: {e}")
        offset = None

    while True:
        try:
            # Build parameters with offset if available
            params = {"timeout": 100}
            if offset:
                params["offset"] = offset

            response = requests.get(url, params=params)
            updates = response.json().get("result", [])

            for update in updates:
                handle_telegram_update(update)
                # Always increment offset to mark as read for next poll
                offset = update["update_id"] + 1

        except Exception as e:
            print(f"Error in Telegram listener: {e}")
            # Wait slightly longer on error
            time.sleep(5)
            continue

        time.sleep(15)


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
