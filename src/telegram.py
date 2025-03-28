import os
import time
import logging
from typing import List, Dict, Any, Union, Optional, Tuple

import requests
from event_driven.event_bus import EventBus, EventType
from ml_serving.utils import dump_failed_text
from logger import get_logger

logger = get_logger("telegram")

# --- Configuration ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DEFAULT_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"
GET_UPDATES_URL = f"{TELEGRAM_API_URL}/getUpdates"
SEND_MESSAGE_URL = f"{TELEGRAM_API_URL}/sendMessage"

# --- Constants ---
HTML_ESCAPE_MAP = {
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
}
INTERNAL_FIELDS = {'request_id', 'requested_by'}
NA_STRING = "N/A"
NONE_SPECIFIED = "None specified"
NONE_STRING = "None"

# --- Helper Functions ---

def escape_html(text: Any) -> str:
    """Escapes HTML special characters in a string."""
    text_str = str(text)
    for char, escaped_char in HTML_ESCAPE_MAP.items():
        text_str = text_str.replace(char, escaped_char)
    return text_str

def format_list(items: Optional[List[Any]]) -> str:
    """Formats a list into a bulleted string, escaping HTML."""
    if not items:
        return NONE_STRING
    return "\n".join(f"• {escape_html(item)}" for item in items)

def format_conditions(conditions: Optional[List[Dict[str, Any]]]) -> str:
    """Formats a list of conditions, preferring descriptions."""
    if not conditions:
        return NONE_SPECIFIED
    
    formatted = []
    for cond in conditions:
        desc = cond.get("description")
        if desc:
            formatted.append(f"• {escape_html(desc)}")
        else:
            indicator = escape_html(cond.get('indicator', NA_STRING))
            operator = escape_html(cond.get('operator', NA_STRING))
            value = escape_html(cond.get('value', NA_STRING))
            formatted.append(f"• {indicator} {operator} {value}")
    return "\n".join(formatted)

def _format_price_percentage(data: Optional[Dict[str, Any]], prefix: str = "", suffix: str = "") -> Optional[str]:
    """Helper to format price and optional percentage."""
    if not data or not isinstance(data, dict):
        return None
    price = data.get('price')
    if price is None:
        return None
    
    line = f"{prefix}{escape_html(price)}"
    percentage = data.get('percentage')
    if percentage is not None:
        line += f" ({escape_html(percentage)}%{suffix})"
    return line

def format_profit_target(target: Union[Dict[str, Any], Any]) -> str:
    """Formats profit target information."""
    if not isinstance(target, dict):
        return escape_html(target) # Handle older formats or simple values

    lines = filter(None, [
        _format_price_percentage(target.get("primary"), prefix="Primary: "),
        _format_price_percentage(target.get("secondary"), prefix="Secondary: ")
    ])
    return "\n".join(lines) if lines else NA_STRING

def format_stop_loss(sl: Union[Dict[str, Any], Any]) -> str:
    """Formats stop loss information."""
    if not isinstance(sl, dict):
        return escape_html(sl) # Handle older formats or simple values
    
    formatted = _format_price_percentage(sl, suffix=" loss")
    return formatted if formatted is not None else NA_STRING

def _format_strategy_part(label: str, value: Optional[Any], formatter=escape_html, multiline: bool = False) -> Optional[str]:
    """Helper to format a single part of a strategy message."""
    if value is None:
        return None
    formatted_value = formatter(value)
    separator = "\n" if multiline else " "
    return f"<b>{label}:</b>{separator}{formatted_value}"

def format_entry_strategy(strategy: Optional[Dict[str, Any]]) -> str:
    """Formats entry strategy information."""
    if not strategy or not isinstance(strategy, dict):
        return NA_STRING
        
    parts = filter(None, [
        _format_strategy_part("Price", strategy.get('price')),
        _format_strategy_part("Timing", strategy.get('timing')),
        _format_strategy_part("Conditions", strategy.get('conditions'), formatter=format_conditions, multiline=True),
        # Handle old 'technical_indicators' field if present and 'conditions' is not
        _format_strategy_part("Technical Indicators", strategy.get('technical_indicators')) if 'conditions' not in strategy else None
    ])
    return "\n".join(parts) if parts else NA_STRING

def format_exit_strategy(strategy: Optional[Dict[str, Any]], is_hold: bool) -> str:
    """Formats exit strategy information."""
    if not strategy or not isinstance(strategy, dict):
        return NA_STRING

    parts = filter(None, [
        _format_strategy_part("Profit Target", strategy.get('profit_target'), formatter=format_profit_target, multiline=True),
        _format_strategy_part("Stop Loss", strategy.get('stop_loss'), formatter=format_stop_loss),
        _format_strategy_part("Time Horizon", strategy.get('time_horizon')),
        _format_strategy_part("Trailing Stop", strategy.get('trailing_stop')) if is_hold else None,
        _format_strategy_part("Conditions", strategy.get('conditions'), formatter=format_conditions, multiline=True),
        # Handle old 'exit_conditions' field if present and 'conditions' is not
        _format_strategy_part("Exit Conditions", strategy.get('exit_conditions')) if 'conditions' not in strategy and isinstance(strategy.get('exit_conditions'), str) else None
    ])
    return "\n".join(parts) if parts else NA_STRING

# --- Core Logic ---

def format_investment_message(result: dict) -> str:
    """Formats investment analysis result for Telegram using HTML."""
    try:
        if not result:
            return "No analysis results available."

        data = {k: v for k, v in result.items() if k not in INTERNAL_FIELDS}
        is_hold = 'purchase_price' in data # Simplified check

        parts = [
            _format_strategy_part("Symbol", data.get('symbol')),
        ]

        if is_hold:
            parts.extend(filter(None, [
                _format_strategy_part("Purchase Price", data.get('purchase_price')),
                _format_strategy_part("Current Price", data.get('current_price')),
            ]))
            gain_loss = data.get('unrealized_gain_loss_pct')
            if gain_loss is not None:
                 suffix = '%' if isinstance(gain_loss, (int, float)) else ''
                 parts.append(f"<b>Unrealized Gain/Loss:</b> {escape_html(gain_loss)}{suffix}")

        parts.extend(filter(None, [
            _format_strategy_part("Rating", data.get('rating')),
            _format_strategy_part("Confidence", data.get('confidence')),
            _format_strategy_part("Reasoning", data.get('reasoning')),
        ]))

        # Factors
        if is_hold:
            parts.extend(filter(None, [
                _format_strategy_part("Hold Factors", data.get('hold_factors'), formatter=format_list, multiline=True),
                _format_strategy_part("Risk Factors", data.get('risk_factors'), formatter=format_list, multiline=True),
            ]))
        else:
            parts.extend(filter(None, [
                _format_strategy_part("Bullish Factors", data.get('bullish_factors'), formatter=format_list, multiline=True),
                _format_strategy_part("Bearish Factors", data.get('bearish_factors'), formatter=format_list, multiline=True),
            ]))

        parts.append(_format_strategy_part("Macro Impact", data.get('macro_impact')))

        # Strategies
        if is_hold:
            parts.append(_format_strategy_part("Exit Strategy", data.get('exit_strategy'), lambda s: format_exit_strategy(s, is_hold=True), multiline=True))
            # Handle potential old format 'exit_conditions' list at top level
            if isinstance(data.get("exit_conditions"), list):
                 parts.append(_format_strategy_part("Exit Conditions", data["exit_conditions"], formatter=format_list, multiline=True))
        else:
            parts.extend(filter(None, [
                _format_strategy_part("Enter Strategy", data.get('enter_strategy'), formatter=format_entry_strategy, multiline=True),
                _format_strategy_part("Exit Strategy", data.get('exit_strategy'), lambda s: format_exit_strategy(s, is_hold=False), multiline=True),
            ]))

        return "\n\n".join(filter(None, parts))

    except Exception as e:
        error_message = f"Failed to format message: {e}\nOriginal data: {result}"
        logger.error(error_message, exc_info=True)
        dump_failed_text(error_message)
        return f"Error formatting analysis results. Details logged. Error: {escape_html(str(e))}"

def send_text_via_telegram(content: str, chat_id: str = DEFAULT_CHAT_ID):
    """Sends a message via Telegram Bot using HTML parse mode."""
    if not TELEGRAM_BOT_TOKEN or not chat_id:
        logger.error("Telegram Bot Token or Chat ID is not configured.")
        return

    payload = {"chat_id": chat_id, "text": content, "parse_mode": "HTML"}
    try:
        response = requests.post(SEND_MESSAGE_URL, data=payload, timeout=10)
        response.raise_for_status() # Raise an exception for bad status codes
        logger.info(f"Telegram message sent to {chat_id}. Response: {response.json()}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Failed to send Telegram message to {chat_id}: {e}")
    except Exception as e:
        logger.error(f"An unexpected error occurred sending Telegram message: {e}")


def _parse_command(text: str) -> Optional[Tuple[str, List[str]]]:
    """Parses a command string into command name and arguments."""
    if not text or not text.startswith('/'):
        return None
    parts = text.split()
    command = parts[0].lower()
    args = parts[1:]
    return command, args

def handle_telegram_update(update: dict):
    """Handles incoming Telegram updates."""
    message = update.get("message")
    if not message:
        logger.debug("Update without message received.")
        return

    chat_id = message.get("chat", {}).get("id")
    text = message.get("text", "").strip()
    
    if not chat_id:
        logger.warning("Received message without chat ID.")
        return

    parsed_command = _parse_command(text)
    if not parsed_command:
        confirmation_msg = "Command not recognized. Use /analyze {ticker} or /analyze_hold {ticker} {purchase_price}"
        send_text_via_telegram(confirmation_msg, chat_id)
        return

    command, args = parsed_command
    event_data = {"chat_id": chat_id}
    confirmation_msg = ""

    if command == "/analyze_hold" and len(args) >= 2:
        ticker = args[0].upper()
        purchase_price = args[1]
        event_data.update({
            "action": "own",
            "ticker": ticker,
            "purchase_price": purchase_price,
        })
        confirmation_msg = f"Adding {ticker} (owned at {purchase_price}) to analysis queue (high priority)."
    elif command == "/analyze" and len(args) >= 1:
        ticker = args[0].upper()
        event_data.update({
            "action": "buy",
            "ticker": ticker,
        })
        confirmation_msg = f"Adding {ticker} to analysis queue (high priority)."
    else:
        # Construct usage message based on command
        if command == "/analyze_hold":
            confirmation_msg = "Usage: /analyze_hold {ticker} {purchase_price}"
        elif command == "/analyze":
            confirmation_msg = "Usage: /analyze {ticker}"
        else:
             confirmation_msg = f"Command '{command}' not recognized."

    if event_data.get("action"): # If action was set, publish event
        EventBus().publish(EventType.TELEGRAM_COMMAND, event_data)
    
    send_text_via_telegram(confirmation_msg, chat_id)


def listen_to_telegram(poll_interval: int = 15, error_sleep: int = 5, timeout: int = 100):
    """Listens for Telegram updates using long polling."""
    if not TELEGRAM_BOT_TOKEN:
        logger.error("Telegram Bot Token not configured. Cannot listen for updates.")
        return

    offset = None
    # Initialize offset
    try:
        response = requests.get(GET_UPDATES_URL, params={"limit": 1}, timeout=10)
        response.raise_for_status()
        result = response.json().get("result", [])
        if result:
            offset = result[0]["update_id"] + 1
        logger.info(f"Starting Telegram listener. Initial offset: {offset or 'None'}")
    except requests.exceptions.RequestException as e:
        logger.error(f"Error initializing Telegram offset: {e}. Starting without offset.")
    except Exception as e:
         logger.error(f"Unexpected error initializing Telegram offset: {e}. Starting without offset.")


    while True:
        try:
            params = {"timeout": timeout}
            if offset:
                params["offset"] = offset

            response = requests.get(GET_UPDATES_URL, params=params, timeout=timeout + 10) # Timeout slightly longer than API timeout
            response.raise_for_status()
            updates = response.json().get("result", [])

            if not updates:
                time.sleep(poll_interval) # Sleep only if no updates received
                continue

            for update in updates:
                logger.debug(f"Received update: {update.get('update_id')}")
                handle_telegram_update(update)
                offset = update["update_id"] + 1 # Processed, move to next offset

        except requests.exceptions.RequestException as e:
            logger.error(f"Error polling Telegram: {e}")
            time.sleep(error_sleep)
        except Exception as e:
            logger.error(f"Error processing Telegram update: {e}", exc_info=True)
            if offset:
                 logger.warning(f"Skipping potential problematic update by incrementing offset to {offset}")
            time.sleep(error_sleep)


def test_send_text_via_telegram():
    data_v7 = {
        "symbol": "TEST",
        "rating": 75,
        "confidence": 9,
        "reasoning": "Strong ecosystem, services growth, & upcoming product cycles offset near-term supply chain risks. Technicals show consolidation near support.",
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
        "reasoning": "Position showing solid gain. Cloud growth remains robust, AI integration provides significant upside. Hold based on strong fundamentals & technical support.",
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

    logger.info("--- Formatting Standard Analysis (V7) ---")
    message_v7 = format_investment_message(data_v7)
    logger.info(f"Formatted V7 Message:\n{message_v7}")
    send_text_via_telegram(message_v7)

    logger.info("\n\n--- Formatting Hold Analysis (Ownership) ---")
    message_own = format_investment_message(data_own)
    logger.info(f"Formatted Ownership Message:\n{message_own}")
    send_text_via_telegram(message_own)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # test_send_text_via_telegram()
    listen_to_telegram()