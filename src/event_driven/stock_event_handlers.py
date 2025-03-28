"""Event handlers for stock-related events in the QSBets system."""
import os
import json
import sqlite3
import time
import threading
from datetime import datetime
from typing import Any, Dict
from queue import Queue, Empty
import pandas as pd

from event_driven.event_bus import EventBus, EventType
from analysis.stock import Stock
from ml_serving.ai_service import consult
from collectors.nasdaq import fetch_nasdaq_data
from collectors.social import get_sentiment_df
from event_driven.utils import _get_db_connection, _parse_conditions_db, _parse_profit_target_db, _parse_stop_loss_db
from src.analysis.macro_economy import make_macro_yaml
from telegram import listen_to_telegram, send_text_via_telegram, format_investment_message
from logger import get_logger
TWELVE_HOURS_SECONDS = 43200

# Shared queues for inter-thread communication
stock_request_queue = Queue()
analysis_result_queue = Queue()
consult_result_queue = Queue()


class StockEventSystem:
    """Manages stock analysis system event loops for data collection, analysis and evaluation."""
    def __init__(self):
        self.event_bus = EventBus()
        self.logger = get_logger("stock_events")
        self.analysis_dir = os.path.join(os.getcwd(), "analysis_docs")
        self.results_dir = os.path.join(os.getcwd(), "results")
        os.makedirs(self.analysis_dir, exist_ok=True)
        os.makedirs(self.results_dir, exist_ok=True)
        self.sentiment_stocks_limit = 10
        self.quality_rating_threshold = 70 # Adjusted threshold for quality rating
        self.quality_confidence_threshold = 8 # Added threshold for confidence
        self.last_sentiment_check = None
        self._register_event_handlers()

    def _register_event_handlers(self) -> None:
        handlers = {
            EventType.STOCK_REQUEST: self.handle_stock_request,
            EventType.TELEGRAM_COMMAND: self.handle_telegram_command,
            EventType.ANALYSIS_COMPLETE: self.handle_analysis_complete,
        }
        for event_type, handler in handlers.items():
            self.event_bus.subscribe(event_type, handler)

    def handle_stock_request(self, event_data: Dict[str, Any]) -> None:
        symbol = event_data.get("symbol")
        if not symbol:
            self.logger.error("Stock request received without symbol")
            return
        self.logger.info(f"Stock request received for {symbol}")
        stock_request_queue.put({
            "symbol": symbol,
            "request_id": event_data.get("request_id", f"{datetime.now().timestamp()}"),
            "requested_by": event_data.get("requested_by") or os.getenv("TELEGRAM_CHAT_ID"),
        })

    def handle_telegram_command(self, event_data: Dict[str, Any]) -> None:
        ticker = event_data.get("ticker")
        action = event_data.get("action")
        chat_id = event_data.get("chat_id")
        if not ticker or not action:
            self.logger.error("Telegram command received without ticker or action")
            return
        self.logger.info(f"Telegram {action} command received for {ticker}")
        request_data = {
            "symbol": ticker,
            "requested_by": chat_id,
            "request_id": f"{datetime.now().timestamp()}",
            "action_type": action
        }
        if action == "own" and event_data.get("purchase_price"):
            request_data["purchase_price"] = event_data.get("purchase_price")
        # Priority insert at the front of the queue
        stock_request_queue.queue.insert(0, request_data)

    def handle_analysis_complete(self, event_data: Dict[str, Any]) -> None:
        """Handles completed analysis, sends Telegram message, and saves high-quality recommendations."""
        symbol = event_data.get("symbol")
        requested_by = event_data.get("requested_by")
        rating = event_data.get("rating", 0)
        confidence = event_data.get("confidence", 0)
        is_ownership_analysis = "purchase_price" in event_data # Check if it's an ownership analysis

        # Send Telegram notification if requested
        if requested_by:
            try:
                # Only send if it's a direct request OR meets quality threshold for general channel
                if requested_by != os.getenv("TELEGRAM_CHAT_ID") or \
                   (rating >= self.quality_rating_threshold and confidence >= self.quality_confidence_threshold):
                    send_text_via_telegram(format_investment_message(event_data), requested_by)
            except Exception:
                self.logger.error(f"Failed to send analysis for {symbol} via Telegram", exc_info=True)

        # Save high-quality BUY recommendations to database (ignore ownership analysis for now)
        if not is_ownership_analysis and rating >= self.quality_rating_threshold and confidence >= self.quality_confidence_threshold:
            self.logger.info(f"High quality recommendation detected: {symbol} (Rating: {rating}, Confidence: {confidence}). Saving to DB.")
            conn = None
            try:
                conn, cursor = _get_db_connection()
                recommendation_date = datetime.now().strftime('%Y-%m-%d')

                # Extract and parse strategy details for DB
                enter_strategy = event_data.get('enter_strategy', {})
                exit_strategy = event_data.get('exit_strategy', {})

                entry_price_str = str(enter_strategy.get('price', '')) # Store as string
                entry_timing_str = enter_strategy.get('timing', '')
                # Entry conditions are not currently stored in the simple DB schema

                profit_target_str = _parse_profit_target_db(exit_strategy.get('profit_target'))
                stop_loss_str = _parse_stop_loss_db(exit_strategy.get('stop_loss'))
                time_horizon_str = exit_strategy.get('time_horizon', '')
                exit_conditions_str = _parse_conditions_db(exit_strategy.get('conditions'))

                # Store the full JSON response for potential future use/parsing
                strategy_json = json.dumps(event_data)

                cursor.execute('''
                INSERT OR IGNORE INTO recommendations
                (symbol, recommendation_date, rating, confidence, entry_price, entry_timing, profit_target, stop_loss, time_horizon, exit_conditions)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (symbol, recommendation_date, rating, confidence, entry_price_str, entry_timing_str, profit_target_str, stop_loss_str, time_horizon_str, exit_conditions_str))

                if cursor.rowcount > 0:
                    self.logger.info(f"Successfully saved recommendation for {symbol} on {recommendation_date} to DB.")
                else:
                     self.logger.info(f"Recommendation for {symbol} on {recommendation_date} already exists in DB.")

                conn.commit()

            except sqlite3.Error as db_err:
                self.logger.error(f"Database error saving recommendation for {symbol}: {db_err}", exc_info=True)
                if conn:
                    conn.rollback()
            except Exception as e:
                self.logger.error(f"Unexpected error saving recommendation for {symbol}: {e}", exc_info=True)
                if conn:
                    conn.rollback() # Rollback on any error during processing
            finally:
                if conn:
                    conn.close()
        elif rating >= self.quality_rating_threshold and confidence >= self.quality_confidence_threshold:
             self.logger.info(f"High quality ownership analysis for {symbol} (Rating: {rating}, Confidence: {confidence}). Not saving to recommendations DB.")
        else:
            self.logger.debug(f"Recommendation for {symbol} did not meet quality criteria (Rating: {rating}, Confidence: {confidence}). Not saving.")


    def start_main_loop(self):
        self.logger.info("Starting main loop for Telegram and data collection")
        while True:
            try:
                # Get result from the consult queue
                result = consult_result_queue.get(timeout=1)

                # Publish ANALYSIS_COMPLETE event. The handler will decide on Telegram msg & DB saving.
                self.event_bus.publish(EventType.ANALYSIS_COMPLETE, result)

            except Empty:
                # Queue is empty, proceed to other tasks
                pass
            except Exception as e:
                 self.logger.error(f"Error processing result from consult queue: {e}", exc_info=True)

            # Check for sentiment stocks periodically
            self._process_sentiment_stocks()
            time.sleep(60)

    def _process_sentiment_stocks(self):
        try:
            current_time = datetime.now()
            if not self.last_sentiment_check or (current_time - self.last_sentiment_check).total_seconds() >= TWELVE_HOURS_SECONDS:
                self.last_sentiment_check = current_time
                nasdaq_data = fetch_nasdaq_data()
                sentiment_df = get_sentiment_df()
                merged_df = pd.merge(nasdaq_data, sentiment_df, on="symbol", how="inner")
                if "sentiment_rating" in merged_df.columns:
                    top_stocks = merged_df.sort_values("sentiment_rating", ascending=False).head(self.sentiment_stocks_limit)
                    for _, row in top_stocks.iterrows():
                        symbol = row["symbol"]
                        if pd.notna(symbol) and symbol:
                            stock_request_queue.put({
                                "symbol": symbol,
                                "request_id": f"sentiment_{datetime.now().timestamp()}",
                                "requested_by": os.getenv("TELEGRAM_CHAT_ID"),
                            })
                            self.logger.info(f"Queued high-sentiment stock for analysis: {symbol}")
        except Exception as e:
            self.logger.error(f"Error processing sentiment stocks: {str(e)}", exc_info=True)

    def start_analysis_loop(self):
        self.logger.info("Starting analysis loop for stock processing")
        while True:
            try:
                request = stock_request_queue.get(timeout=1)
                symbol = request.get("symbol")
                self.logger.info(f"Processing analysis for {symbol}")
                nasdaq_data = fetch_nasdaq_data()
                meta = Stock.process_meta(nasdaq_data, symbol)
                stock_obj = Stock(nasdaq_data=meta)
                file_path = stock_obj.make_yaml()
                analysis_result_queue.put({
                    "symbol": symbol,
                    "file_path": file_path,
                    "request_id": request.get("request_id"),
                    "requested_by": request.get("requested_by"),
                    "purchase_price": request.get("purchase_price")
                })
                self.logger.info(f"Analysis for {symbol} completed and queued for consultation")
            except Empty:
                continue
            except Exception as e:
                self.logger.error(f"Error in analysis loop: {str(e)}", exc_info=True)
                time.sleep(5)

    def start_consult_loop(self):
        self.logger.info("Starting consult loop for parallelized evaluation")
        macroeconomic_data = make_macro_yaml()

        def on_consult_complete(result, analysis_metadata):
            # Define results file path here to ensure it uses the date the consultation finished
            results_file = os.path.join(self.results_dir, f"results_{datetime.now().strftime('%Y-%m-%d')}.jsonl")
            if not result or "error" in result:
                self.logger.error(f"Consult error for {analysis_metadata.get('symbol', 'unknown')}: {result.get('error', 'Unknown error')}")
                # Optionally put an error marker in the queue or handle differently
                # consult_result_queue.put({"error": result.get('error', 'Unknown error'), **analysis_metadata})
                return
            try:
                # Add metadata back to the result before putting it on the queue
                full_result = {**result, **analysis_metadata}

                # Write raw result to JSONL file
                with open(results_file, "a") as f:
                    f.write(json.dumps(full_result) + "\n")

                # Put the combined result onto the queue for the main loop to handle
                consult_result_queue.put(full_result)
                self.logger.info(f"Consultation for {full_result.get('symbol', 'unknown')} completed with rating {full_result.get('rating', 'N/A')}. Queued for handling.")
            except Exception as e:
                self.logger.error(f"Error processing consult result for {analysis_metadata.get('symbol', 'unknown')}: {str(e)}", exc_info=True)

        while True:
            try:
                analysis = analysis_result_queue.get(timeout=1)
                symbol = analysis.get("symbol")
                file_path = analysis.get("file_path")
                self.logger.info(f"Submitting consultation for {symbol}")
                # Prepare metadata, ensuring purchase_price is included if present
                metadata = {
                    "symbol": symbol,
                    "file_path": file_path, # Keep for potential debugging, though not strictly needed by consult
                    "request_id": analysis.get("request_id"),
                    "requested_by": analysis.get("requested_by"),
                }
                if "purchase_price" in analysis and analysis["purchase_price"]:
                     metadata["purchase_price"] = analysis.get("purchase_price")

                with open(file_path, 'r') as file:
                    document = file.read()
                combined_data = f"{macroeconomic_data}\n\n{document}"
                threading.Thread(
                    target=lambda: consult(
                        data=combined_data,
                        metadata=metadata, # Pass metadata to consult
                        callback=lambda consult_res: on_consult_complete(consult_res, metadata) # Pass metadata to callback context
                    ),
                    daemon=True
                ).start()
            except Empty:
                continue
            except Exception as e:
                self.logger.error(f"Error in consult loop submitting job: {str(e)}", exc_info=True)
                time.sleep(5)


stock_system = StockEventSystem()


def initialize():
    """Initialize the stock event handlers system"""
    bus = EventBus()
    bus.start()
    # bus.start_background_loop() # Ensure this is needed and doesn't conflict if loops run in threads
    threads = [
        threading.Thread(target=stock_system.start_main_loop, daemon=True, name="MainLoopThread"),
        threading.Thread(target=stock_system.start_analysis_loop, daemon=True, name="AnalysisLoopThread"),
        threading.Thread(target=stock_system.start_consult_loop, daemon=True, name="ConsultLoopThread"),
        threading.Thread(target=listen_to_telegram, daemon=True, name="TelegramListenThread")
    ]
    for thread in threads:
        thread.start()
    get_logger("stock_events").info("Stock event system initialized with all loops running")


if __name__ == "__main__":
    initialize()
    try:
        # Keep the main thread alive
        while True:
            # Optional: Check thread health
            alive_threads = [t.name for t in threading.enumerate() if t.is_alive()]
            get_logger("stock_events").debug(f"Active threads: {alive_threads}")
            time.sleep(60) # Check every minute
    except KeyboardInterrupt:
        get_logger("stock_events").info("Shutdown signal received. Stopping event bus.")
        EventBus().stop()
        get_logger("stock_events").info("Event bus stopped. Exiting.")
