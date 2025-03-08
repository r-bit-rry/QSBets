"""
Main entry point for the QSBets stock analysis system.
Initializes the stock event system with three dedicated loops.
"""
import os
import time
import argparse
import signal
import sys
from dotenv import load_dotenv

from event_driven.event_bus import EventBus, EventType
from event_driven.stock_event_handlers import initialize as init_stock_system, stock_system

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='QSBets stock analysis system')
    
    parser.add_argument(
        '--top', 
        type=int, 
        default=20,
        help='Maximum number of top sentiment stocks to analyze initially (default: 10)'
    )
    
    parser.add_argument(
        '--env', 
        type=str, 
        default=".env",
        help='Path to .env file (default: .env)'
    )
    
    parser.add_argument(
        '--daemon', 
        action='store_true',
        help='Run as daemon (background process)'
    )
    
    parser.add_argument(
        '--analyze', 
        type=str,
        help='Immediately analyze a specific stock symbol'
    )
    
    parser.add_argument(
        '--threshold', 
        type=float,
        default=60.0,
        help='Rating threshold for high-quality stock recommendations (default: 60.0)'
    )
    
    return parser.parse_args()

def handle_shutdown(sig, frame):
    """Handle shutdown signals"""
    print("\nShutting down gracefully...")
    EventBus().stop()
    sys.exit(0)

def main():
    """Run the stock analysis system"""
    # Parse command line arguments
    args = parse_args()
    
    # Load environment variables
    env_path = os.path.join(os.getcwd(), args.env)
    if not os.path.exists(env_path):
        # Try relative path if not found
        env_path = args.env
    
    load_dotenv(env_path)
    
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)
    
    # If running as daemon, detach from terminal
    if args.daemon and os.name != 'nt':  # Not supported on Windows
        try:
            pid = os.fork()
            if pid > 0:
                # Exit parent process
                sys.exit(0)
        except OSError as e:
            print(f"Fork failed: {e}")
            sys.exit(1)
        
        # Detach from terminal
        os.setsid()
        os.umask(0)
        
        # Close all open file descriptors
        for fd in range(0, 1024):
            try:
                os.close(fd)
            except OSError:
                pass
    
    # Initialize the stock event system with all three loops
    print("Initializing stock analysis system...")
    init_stock_system()
    
    # Set the maximum number of top sentiment stocks to analyze
    if hasattr(stock_system, '_max_sentiment_stocks'):
        stock_system._max_sentiment_stocks = args.top
        
    # Set the rating threshold for high-quality recommendations
    if hasattr(stock_system, '_rating_threshold'):
        stock_system._rating_threshold = args.threshold
    
    # If a specific symbol was provided, request analysis immediately
    if args.analyze:
        symbols = args.analyze.upper().split(',')
        for symbol in symbols:
            symbol = symbol.strip()
            if symbol:
                print(f"Requesting immediate analysis for {symbol}...")
                event_bus = EventBus()
                event_bus.publish(EventType.STOCK_REQUEST, {
                    "symbol": symbol,
                    "request_id": f"cmdline_{time.time()}",
                })
    
    print(f"System running with:")
    print(f"- Top {args.top} sentiment stocks analyzed hourly")
    print(f"- Rating threshold for recommendations: {args.threshold}")
    print(f"- Results stored in results/results_YYYY-MM-DD.jsonl")
    print("Press Ctrl+C to exit.")
    
    # Keep main thread alive
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        handle_shutdown(None, None)

if __name__ == "__main__":
    main()
