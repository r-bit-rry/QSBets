import os
import time
from typing import List, Dict, Any, Union

import requests
from event_driven.event_bus import EventBus, EventType
from ml_serving.utils import dump_failed_text
from logger import get_logger

logger = get_logger("telegram")

DEFAULT_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


# Helper function to escape HTML characters in strings
def escape_html(text: Any) -> str:
    if isinstance(text, str):
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return str(text)

# Helper function to format lists
def format_list(items: List[Any]) -> str:
    if not items:
        return "None"
    return "\n".join(f"• {escape_html(item)}" for item in items)

# Helper function to format conditions list
def format_conditions(conditions: List[Dict[str, Any]]) -> str:
    if not conditions:
        return "None specified"
    
    formatted_conditions = []
    for cond in conditions:
        desc = cond.get("description")
        if desc:
            formatted_conditions.append(f"• {escape_html(desc)}")
        else:
            indicator = escape_html(cond.get('indicator', 'N/A'))
            operator = escape_html(cond.get('operator', 'N/A'))
            value = escape_html(cond.get('value', 'N/A'))
            formatted_conditions.append(f"• {indicator} {operator} {value}")
            
    return "\n".join(formatted_conditions)

# Helper function to format profit target
def format_profit_target(target: Union[Dict[str, Any], Any]) -> str:
    if not isinstance(target, dict):
        return escape_html(target) # Handle older formats or simple values

    lines = []
    primary = target.get("primary")
    secondary = target.get("secondary")

    if primary and isinstance(primary, dict):
        price = primary.get('price')
        percentage = primary.get('percentage')
        line = f"Primary: {escape_html(price)}"
        if percentage is not None:
            line += f" ({escape_html(percentage)}%)"
        lines.append(line)

    if secondary and isinstance(secondary, dict):
        price = secondary.get('price')
        percentage = secondary.get('percentage')
        line = f"Secondary: {escape_html(price)}"
        if percentage is not None:
            line += f" ({escape_html(percentage)}%)"
        lines.append(line)
        
    return "\n".join(lines) if lines else "N/A"

# Helper function to format stop loss
def format_stop_loss(sl: Union[Dict[str, Any], Any]) -> str:
    if not isinstance(sl, dict):
        return escape_html(sl) # Handle older formats or simple values

    price = sl.get('price')
    percentage = sl.get('percentage')
    line = f"{escape_html(price)}"
    if percentage is not None:
        line += f" ({escape_html(percentage)}% loss)"
    return line if price is not None else "N/A"

# Helper function to format entry strategy
def format_entry_strategy(strategy: Dict[str, Any]) -> str:
    if not strategy or not isinstance(strategy, dict):
        return "N/A"
        
    parts = []
    if "price" in strategy:
        parts.append(f"<b>Price:</b> {escape_html(strategy['price'])}")
    if "timing" in strategy:
        parts.append(f"<b>Timing:</b> {escape_html(strategy['timing'])}")
    if "conditions" in strategy:
        parts.append(f"<b>Conditions:</b>\n{format_conditions(strategy['conditions'])}")
    # Handle old 'technical_indicators' field if present
    elif "technical_indicators" in strategy:
         parts.append(f"<b>Technical Indicators:</b> {escape_html(strategy['technical_indicators'])}")

    return "\n".join(parts)

# Helper function to format exit strategy
def format_exit_strategy(strategy: Dict[str, Any], is_hold: bool) -> str:
    if not strategy or not isinstance(strategy, dict):
        return "N/A"

    parts = []
    if "profit_target" in strategy:
        parts.append(f"<b>Profit Target:</b>\n{format_profit_target(strategy['profit_target'])}")
    if "stop_loss" in strategy:
        parts.append(f"<b>Stop Loss:</b> {format_stop_loss(strategy['stop_loss'])}")
    if "time_horizon" in strategy:
        parts.append(f"<b>Time Horizon:</b> {escape_html(strategy['time_horizon'])}")
    if is_hold and "trailing_stop" in strategy:
         parts.append(f"<b>Trailing Stop:</b> {escape_html(strategy['trailing_stop'])}")
    if "conditions" in strategy:
        parts.append(f"<b>Conditions:</b>\n{format_conditions(strategy['conditions'])}")
    # Handle old 'exit_conditions' field if present and 'conditions' is not
    elif "exit_conditions" in strategy and isinstance(strategy['exit_conditions'], str):
         parts.append(f"<b>Exit Conditions:</b> {escape_html(strategy['exit_conditions'])}")


    return "\n".join(parts)


def format_investment_message(result: dict) -> str:
    """
    Format investment analysis result for Telegram with HTML formatting.
    Handles both string-based fields and complex nested structures.
    Supports both standard analysis (CONSULT_PROMPT_V7) and hold position analysis (OWNERSHIP_PROMPT) schemas.
    """
    try:
        if not result:
            return "No analysis results available."

        # Filter out internal fields
        displayed_result = {k: v for k, v in result.items()
                            if k not in ['request_id', 'requested_by']}

        # Start building message
        message_parts = [
            f"<b>Symbol:</b> {escape_html(displayed_result.get('symbol', 'N/A'))}",
            f"<b>Rating:</b> {escape_html(displayed_result.get('rating', 'N/A'))}",
            f"<b>Confidence:</b> {escape_html(displayed_result.get('confidence', 'N/A'))}",
        ]

        # Detect if this is a hold position analysis
        is_hold_analysis = 'purchase_price' in displayed_result

        # Add hold position specific information
        if is_hold_analysis:
            if "purchase_price" in displayed_result:
                message_parts.insert(1, f"<b>Purchase Price:</b> {escape_html(displayed_result.get('purchase_price', 'N/A'))}")
            if "current_price" in displayed_result:
                message_parts.insert(2, f"<b>Current Price:</b> {escape_html(displayed_result.get('current_price', 'N/A'))}")
            if "unrealized_gain_loss_pct" in displayed_result:
                gain_loss = displayed_result.get('unrealized_gain_loss_pct', 'N/A')
                message_parts.insert(3, f"<b>Unrealized Gain/Loss:</b> {escape_html(gain_loss)}{'%' if isinstance(gain_loss, (int, float)) else ''}")

        # Add reasoning
        if "reasoning" in displayed_result:
            message_parts.append(f"<b>Reasoning:</b> {escape_html(displayed_result['reasoning'])}")

        # Add factors based on schema type
        if is_hold_analysis:
            if "hold_factors" in displayed_result:
                message_parts.append(
                    f"<b>Hold Factors:</b>\n{format_list(displayed_result['hold_factors'])}"
                )
            if "risk_factors" in displayed_result:
                message_parts.append(
                    f"<b>Risk Factors:</b>\n{format_list(displayed_result['risk_factors'])}"
                )
        else: # Standard analysis
            if "bullish_factors" in displayed_result:
                message_parts.append(
                    f"<b>Bullish Factors:</b>\n{format_list(displayed_result['bullish_factors'])}"
                )
            if "bearish_factors" in displayed_result:
                message_parts.append(
                    f"<b>Bearish Factors:</b>\n{format_list(displayed_result['bearish_factors'])}"
                )

        # Add macro impact
        if "macro_impact" in displayed_result:
            message_parts.append(
                f"<b>Macro Impact:</b> {escape_html(displayed_result.get('macro_impact', ''))}"
            )

        # Add strategy sections based on schema type
        if is_hold_analysis:
            # Add exit strategy for hold analysis
            if "exit_strategy" in displayed_result:
                message_parts.append(
                    f"<b>Exit Strategy:</b>\n{format_exit_strategy(displayed_result['exit_strategy'], is_hold=True)}"
                )
        else: # Standard analysis
            # Add enter strategy
            if "enter_strategy" in displayed_result:
                message_parts.append(
                    f"<b>Enter Strategy:</b>\n{format_entry_strategy(displayed_result['enter_strategy'])}"
                )
            # Add exit strategy
            if "exit_strategy" in displayed_result:
                message_parts.append(
                    f"<b>Exit Strategy:</b>\n{format_exit_strategy(displayed_result['exit_strategy'], is_hold=False)}"
                )
        
        # Handle potential old format 'exit_conditions' if it was a list at the top level (hold analysis)
        if is_hold_analysis and "exit_conditions" in displayed_result and isinstance(displayed_result["exit_conditions"], list):
             message_parts.append(
                    f"<b>Exit Conditions:</b>\n{format_list(displayed_result['exit_conditions'])}"
                )


        return "\n\n".join(part for part in message_parts if part) # Filter empty parts

    except Exception as e:
        error_message = f"Failed to format message: {str(e)}\nOriginal data: {str(result)}"
        logger.error(error_message, exc_info=True)
        dump_failed_text(error_message) # Ensure this function exists and works
        return f"Error formatting analysis results. Details logged. Error: {escape_html(str(e))}"

def send_text_via_telegram(content: str, chat_id: str=DEFAULT_CHAT_ID):
    """
    Sends a message via Telegram Bot with Markdown formatting.
    Escapes special characters to avoid parsing errors.
    """
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    data = {"chat_id": chat_id, "text": content, "parse_mode": "HTML"}
    response = requests.post(url, data=data)
    logger.info(f"Telegram message sent. Response: {response.json()}")


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
        logger.info(f"Starting Telegram listener from update_id: {offset or 'latest'}")
    except Exception as e:
        logger.error(f"Error initializing Telegram offset: {e}")
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
            logger.error(f"Error in Telegram listener: {e}")
            # Wait slightly longer on error
            time.sleep(5)
            continue

        time.sleep(15)


def test_send_text_via_telegram():
    # Example using CONSULT_PROMPT_V7 structure
    data_v7 = {
        "symbol": "TEST",
        "rating": 75,
        "confidence": 9,
        "reasoning": "Strong ecosystem, services growth, and upcoming product cycles offset near-term supply chain risks. Technicals show consolidation near support.",
        "bullish_factors": [
            "Services revenue +15% YoY",
            "Strong iPhone demand expected in H2",
            "Share buyback program active ($90B authorized)"
        ],
        "bearish_factors": [
            "Potential regulatory headwinds in EU",
            "Macroeconomic slowdown impacting consumer spending",
            "Increased competition in smartphone market"
        ],
        "macro_impact": "Rising interest rates could dampen consumer demand for high-ticket items, but strong brand loyalty provides resilience.",
        "enter_strategy": {
            "price": "170.50",
            "timing": "On pullback to SMA50",
            "conditions": [
                {"indicator": "rsi", "operator": ">", "value": 50, "description": "RSI holding above 50"},
                {"indicator": "macd", "operator": "crosses_above", "value": "signal_line", "description": "MACD bullish crossover"}
            ]
        },
        "exit_strategy": {
            "profit_target": {
                "primary": {"price": 185.00, "percentage": 8.5},
                "secondary": {"price": 195.00, "percentage": 14.4}
            },
            "stop_loss": {"price": 165.00, "percentage": 3.2},
            "time_horizon": "4-6 weeks",
            "conditions": [
                {"indicator": "price", "operator": "<", "value": "sma100", "description": "Close below SMA100"},
                {"indicator": "macd", "operator": "crosses_below", "value": "signal_line", "description": "MACD bearish crossover"}
            ]
        }
    }
    
    # Example using OWNERSHIP_PROMPT structure
    data_own = {
        "symbol": "TEST",
        "purchase_price": 280.00,
        "current_price": 310.50,
        "unrealized_gain_loss_pct": 10.89,
        "rating": 85, # Hold rating
        "confidence": 9,
        "reasoning": "Position showing solid gain. Cloud growth remains robust, AI integration provides significant upside. Hold based on strong fundamentals and technical support.",
        "hold_factors": [
            "Azure revenue growth +27% YoY",
            "Strong AI positioning with OpenAI partnership",
            "Consistent dividend increases"
        ],
        "risk_factors": [
            "Antitrust scrutiny increasing globally",
            "Slowing PC market affecting Windows revenue",
            "Integration challenges with Activision Blizzard"
        ],
        "macro_impact": "Resilient enterprise spending benefits cloud segment, though broader economic slowdown could impact other areas.",
        "exit_strategy": {
            "stop_loss": {"price": 295.00, "percentage": 5.0}, # Updated SL based on current price
            "profit_target": {"primary": {"price": 330.00, "percentage": 6.3}}, # Revised PT
            "time_horizon": "6-12 months",
            "trailing_stop": "7%",
            "conditions": [
                {"indicator": "price", "operator": "<", "value": "sma200", "description": "Close below SMA200"},
                {"indicator": "fundamental", "operator": "deteriorates", "value": "cloud_growth < 20%", "description": "Azure growth slows significantly"}
            ]
        }
    }

    print("--- Formatting Standard Analysis (V7) ---")
    message_v7 = format_investment_message(data_v7)
    print(message_v7)
    send_text_via_telegram(message_v7) # Uncomment to send

    print("\n\n--- Formatting Hold Analysis (Ownership) ---")
    message_own = format_investment_message(data_own)
    print(message_own)
    send_text_via_telegram(message_own) # Uncomment to send

if __name__ == "__main__":
    # test_send_text_via_telegram()
    listen_to_telegram()
