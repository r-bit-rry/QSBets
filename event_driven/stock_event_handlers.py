"""
Event handlers for stock-related events in the QSBets system.
Processes various data sources and triggers analysis.
"""
import os
import json
import time
import threading
from datetime import datetime
import traceback
from typing import Any, Dict, List
import logging
from queue import Queue
import pandas as pd

from event_driven.event_bus import EventBus, EventType
from ml_serving.mlx_fin import MODEL_PATH, consult
from analysis.stock import Stock
from social.social import get_sentiment_df
from nasdaq import fetch_nasdaq_data
from telegram import send_text_via_telegram, format_investment_message
from ml_serving.mlx_model_server import get_model_server

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("stock_events")

# Shared queues for inter-loop communication
stock_request_queue = Queue()
analysis_result_queue = Queue()
consult_result_queue = Queue()

class StockEventSystem:
    """
    Manages the three main loops of the stock analysis system:
    1. Main loop - Handles Telegram, initial data collection, and results publishing
    2. Analysis loop - Processes stock requests using Stock.make_json
    3. Consult loop - Evaluates analysis data using DeepSeek and filters high-rated stocks
    """

    def __init__(self):
        self.event_bus = EventBus()
        self.analysis_dir = os.path.join(os.getcwd(), "analysis_docs")
        os.makedirs(self.analysis_dir, exist_ok=True)
        self.results_dir = os.path.join(os.getcwd(), "results")
        os.makedirs(self.results_dir, exist_ok=True)
        self._max_sentiment_stocks = 10  # Default number of top sentiment stocks to analyze
        self._rating_threshold = 60  # Default rating threshold for high-quality recommendations
        self._register_event_handlers()

    def _register_event_handlers(self) -> None:
        """Register all event handlers with the event bus"""
        self.event_bus.subscribe(EventType.STOCK_REQUEST, self.handle_stock_request)
        self.event_bus.subscribe(EventType.TELEGRAM_COMMAND, self.handle_telegram_command)
        self.event_bus.subscribe(EventType.ANALYSIS_COMPLETE, self.handle_analysis_complete)

    def handle_stock_request(self, event_data: Dict[str, Any]) -> None:
        """Handle incoming stock analysis requests"""
        symbol = event_data.get("symbol")
        if not symbol:
            logger.error("Stock request received without symbol")
            return

        logger.info(f"Stock request received for {symbol}")

        # Push to the analysis queue
        stock_request_queue.put({
            "symbol": symbol,
            "request_id": event_data.get("request_id", str(datetime.now().timestamp())),
            "requested_by": event_data.get("requested_by") or os.getenv("TELEGRAM_CHAT_ID")
        })

    def handle_telegram_command(self, event_data: Dict[str, Any]) -> None:
        """Handle commands from Telegram"""
        command = event_data.get("command")
        chat_id = event_data.get("chat_id")

        if command.startswith("/analyze"):
            parts = command.split()
            if len(parts) >= 2:
                symbol = parts[1].upper()
                # Create a stock request
                self.event_bus.publish(EventType.STOCK_REQUEST, {
                    "symbol": symbol,
                    "requested_by": chat_id,
                    "request_id": str(datetime.now().timestamp())
                })
                send_text_via_telegram(f"Analysis for {symbol} has been queued.", chat_id)
            else:
                send_text_via_telegram("Please specify a stock symbol. Usage: /analyze SYMBOL", chat_id)

    def handle_analysis_complete(self, event_data: Dict[str, Any]) -> None:
        """Handle completed analysis results"""
        symbol = event_data.get("symbol")
        requested_by = event_data.get("requested_by")

        if requested_by and event_data:
            try:
                message = format_investment_message(event_data)
                send_text_via_telegram(message, requested_by)
            except:
                traceback.print_exc()

        # Log high-rating results
        if event_data and event_data.get("rating", 0) > self._rating_threshold:
            logger.info(
                f"High rating stock detected: {symbol} with rating {event_data.get('rating')}"
            )

    def start_main_loop(self):
        """Start the main loop for Telegram integration and data collection"""
        logger.info("Starting main loop for Telegram and data collection")

        while True:
            try:
                # Check for high-rated stocks from the consult loop
                if not consult_result_queue.empty():
                    result = consult_result_queue.get()
                    if (
                        result.get("rating", 0) > self._rating_threshold
                        or result.get("requested_by") != os.getenv("TELEGRAM_CHAT_ID")
                    ):
                        self.event_bus.publish(EventType.ANALYSIS_COMPLETE, result)

                # Periodically fetch and analyze stocks with sentiment
                self._process_sentiment_stocks()

                # Sleep to prevent excessive CPU usage
                time.sleep(60)  # Check every minute
            except Exception as e:
                logger.error(f"Error in main loop: {str(e)}")
                time.sleep(10)  # Continue after a short delay

    def _process_sentiment_stocks(self):
        """
        Periodically fetch stocks with high sentiment and queue them for analysis
        """
        try:
            current_time = datetime.now()

            # If this is the first run or if 4 hours have passed since last run
            if not hasattr(self, "_last_sentiment_time") or (current_time - self._last_sentiment_time).total_seconds() >= 14400:  # 4 hours in seconds
                self._last_sentiment_time = current_time
                # Get NASDAQ data
                nasdaq_data = fetch_nasdaq_data()

                # Get sentiment data and correlate
                sentiment_df = get_sentiment_df()
                df = pd.merge(nasdaq_data, sentiment_df, on="symbol", how="inner")
                # Sort by sentiment rating (descending) and take top stocks
                if "sentiment_rating" in df.columns:
                    top_stocks = df.sort_values("sentiment_rating", ascending=False).head(
                        self._max_sentiment_stocks
                    )

                    # Queue these stocks for analysis
                    for _, row in top_stocks.iterrows():
                        symbol = row["symbol"]
                        if pd.notna(symbol) and symbol:
                            stock_request_queue.put(
                                {
                                    "symbol": symbol,
                                    "request_id": f"sentiment_{datetime.now().timestamp()}",
                                    "requested_by": os.getenv("TELEGRAM_CHAT_ID"),
                                }
                            )
                            logger.info(f"Queued high-sentiment stock for analysis: {symbol}")

        except Exception as e:
            logger.error(f"Error processing sentiment stocks: {str(e)}")

    def start_analysis_loop(self):
        """Start the analysis loop for processing stock requests"""
        logger.info("Starting analysis loop for stock processing")

        while True:
            try:
                # Get the next stock request from the queue
                if not stock_request_queue.empty():
                    request = stock_request_queue.get()
                    symbol = request.get("symbol")

                    logger.info(f"Processing analysis for {symbol}")

                    # Get NASDAQ data for the symbol
                    nasdaq_data = fetch_nasdaq_data()
                    meta = Stock.process_meta(nasdaq_data, symbol)

                    # Create Stock instance and generate analysis JSON
                    stock = Stock(nasdaq_data=meta)
                    file_path = stock.make_yaml()

                    # Put the result in the analysis_result_queue for the consult loop
                    analysis_result_queue.put({
                        "symbol": symbol,
                        "file_path": file_path,
                        "request_id": request.get("request_id"),
                        "requested_by": request.get("requested_by")
                    })

                    logger.info(f"Analysis for {symbol} completed and queued for consultation")
                else:
                    # Sleep if no requests are waiting
                    time.sleep(1)

            except Exception as e:
                traceback.print_exc()
                logger.error(f"Error in analysis loop for {symbol}: {str(e)}")
                time.sleep(5)  # Continue after a short delay

    def start_consult_loop(self):
        """Start the consult loop for evaluating analysis data using the MLX model server"""
        logger.info("Starting consult loop for parallelized MLX evaluation")

        # Create a results file for today
        today_str = datetime.now().strftime("%Y-%m-%d")
        results_file = os.path.join(self.results_dir, f"results_{today_str}.jsonl")

        def on_consult_complete(result):
            """Handle completed consultation results"""
            # Check for errors
            if not result or "error" in result:
                logger.error(f"Consult error: {result.get('error', 'Unknown error')}")
                return

            # Extract the metadata from the result
            metadata = result.get("metadata", {})
            symbol = metadata.get("symbol")
            requested_by = metadata.get("requested_by")

            try:
                # Add metadata from the original request
                if symbol and "symbol" not in result:
                    result["symbol"] = symbol

                result["request_id"] = metadata.get("request_id")
                result["requested_by"] = requested_by

                # Write to the results file
                with open(results_file, "a") as f:
                    f.write(json.dumps(result) + "\n")

                # Put in the consult_result_queue for the main loop
                consult_result_queue.put(result)

                logger.info(
                    f"Consultation for {symbol} completed with rating {result.get('rating', 'N/A')}"
                )
            except Exception as e:
                logger.error(f"Error processing consult result: {str(e)}")
                traceback.print_exc()

        while True:
            try:
                # Get the next analysis result from the queue
                if not analysis_result_queue.empty():
                    analysis = analysis_result_queue.get()
                    symbol = analysis.get("symbol")
                    file_path = analysis.get("file_path")

                    logger.info(f"Submitting consultation for {symbol}")

                    try:
                        # Use the consult function with metadata
                        metadata = {
                            "symbol": symbol,
                            "file_path": file_path,
                            "request_id": analysis.get("request_id"),
                            "requested_by": analysis.get("requested_by"),
                        }
                        
                        # Start consultation in a separate thread to avoid blocking
                        threading.Thread(
                            target=lambda: consult(
                                file_path,
                                metadata=metadata,
                                callback=on_consult_complete
                            ),
                            daemon=True
                        ).start()

                        logger.info(f"Consultation for {symbol} submitted")
                    except Exception as e:
                        logger.error(f"Error submitting consult request for {symbol}: {str(e)}")
                        traceback.print_exc()
                else:
                    # Sleep if no analyses are waiting
                    time.sleep(1)

            except Exception as e:
                logger.error(f"Error in consult loop: {str(e)}")
                traceback.print_exc()
                time.sleep(5)  # Continue after a short delay

stock_system = StockEventSystem()


def initialize():
    """Initialize the stock event handlers system with all three loops"""
    get_model_server(MODEL_PATH)

    bus = EventBus()
    bus.start()
    bus.start_background_loop()

    # Start the three loops in separate threads
    threading.Thread(target=stock_system.start_main_loop, daemon=True).start()
    threading.Thread(target=stock_system.start_analysis_loop, daemon=True).start()
    threading.Thread(target=stock_system.start_consult_loop, daemon=True).start()

    logger.info("Stock event system initialized with all three loops running")


if __name__ == "__main__":
    initialize()
    # Keep the main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        EventBus().stop()
