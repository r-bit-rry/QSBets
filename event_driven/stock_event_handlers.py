"""Event handlers for stock-related events in the QSBets system."""
import os
import json
import time
import threading
from datetime import datetime
from typing import Any, Dict
from queue import Queue, Empty
import pandas as pd

from event_driven.event_bus import EventBus, EventType
from analysis.stock import Stock
from ml_serving.ai_service import consult
from social.social import get_sentiment_df
from nasdaq import fetch_nasdaq_data
from telegram import listen_to_telegram, send_text_via_telegram, format_investment_message
from logger import get_logger
FOUR_HOURS_SECONDS = 14400

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
        self.quality_rating_threshold = 60
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
        symbol = event_data.get("symbol")
        requested_by = event_data.get("requested_by")
        if requested_by:
            try:
                send_text_via_telegram(format_investment_message(event_data), requested_by)
            except Exception:
                self.logger.error(f"Failed to send analysis for {symbol}", exc_info=True)
        if event_data.get("rating", 0) > self.quality_rating_threshold:
            self.logger.info(f"High quality stock detected: {symbol} with rating {event_data.get('rating')}")

    def start_main_loop(self):
        self.logger.info("Starting main loop for Telegram and data collection")
        while True:
            try:
                result = consult_result_queue.get(timeout=1)
                # Respond to any request not from the main chat or if rating exceeds threshold for main chat
                if result.get("requested_by") != os.getenv("TELEGRAM_CHAT_ID") or result.get("rating", 0) > self.quality_rating_threshold:
                    self.event_bus.publish(EventType.ANALYSIS_COMPLETE, result)
            except Empty:
                pass
            self._process_sentiment_stocks()
            time.sleep(60)

    def _process_sentiment_stocks(self):
        try:
            current_time = datetime.now()
            if not self.last_sentiment_check or (current_time - self.last_sentiment_check).total_seconds() >= FOUR_HOURS_SECONDS:
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
        self.logger.info("Starting consult loop for parallelized MLX evaluation")
        results_file = os.path.join(self.results_dir, f"results_{datetime.now().strftime('%Y-%m-%d')}.jsonl")

        def on_consult_complete(result, analysis_metadata):
            if not result or "error" in result:
                self.logger.error(f"Consult error: {result.get('error', 'Unknown error')}")
                return
            try:
                result["request_id"] = analysis_metadata.get("request_id")
                result["requested_by"] = analysis_metadata.get("requested_by")
                with open(results_file, "a") as f:
                    f.write(json.dumps(result) + "\n")
                consult_result_queue.put(result)
                self.logger.info(f"Consultation for {result.get('symbol', 'unknown')} completed with rating {result.get('rating', 'N/A')}")
            except Exception as e:
                self.logger.error(f"Error processing consult result: {str(e)}", exc_info=True)

        while True:
            try:
                analysis = analysis_result_queue.get(timeout=1)
                symbol = analysis.get("symbol")
                file_path = analysis.get("file_path")
                self.logger.info(f"Submitting consultation for {symbol}")
                metadata = {
                    "symbol": symbol,
                    "file_path": file_path,
                    "request_id": analysis.get("request_id"),
                    "requested_by": analysis.get("requested_by"),
                    "purchase_price": analysis.get("purchase_price"),
                }
                threading.Thread(
                    target=lambda: consult(
                        file_path, 
                        metadata=metadata, 
                        callback=lambda result: on_consult_complete(result, metadata)
                    ),
                    daemon=True
                ).start()
                self.logger.info(f"Consultation for {symbol} submitted")
            except Empty:
                continue
            except Exception as e:
                self.logger.error(f"Error in consult loop: {str(e)}", exc_info=True)
                time.sleep(5)


stock_system = StockEventSystem()


def initialize():
    """Initialize the stock event handlers system"""
    bus = EventBus()
    bus.start()
    bus.start_background_loop()
    threads = [
        threading.Thread(target=stock_system.start_main_loop, daemon=True),
        threading.Thread(target=stock_system.start_analysis_loop, daemon=True),
        threading.Thread(target=stock_system.start_consult_loop, daemon=True),
        threading.Thread(target=listen_to_telegram, daemon=True)
    ]
    for thread in threads:
        thread.start()
    get_logger("stock_events").info("Stock event system initialized with all loops running")


if __name__ == "__main__":
    initialize()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        EventBus().stop()
