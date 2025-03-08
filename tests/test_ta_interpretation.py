"""
Test module for the technical analysis interpretation functions.
Uses real stock data to validate interpretation algorithms.
"""

import json
import os
import sys
import pprint

# Add the parent directory to sys.path to allow importing from ta_interpretation
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analysis.ta_interpretation import (
    interpret_rsi,
    interpret_macd,
    interpret_moving_averages,
    interpret_bollinger_bands,
    interpret_adx,
    interpret_insider_activity,
    interpret_institutional_holdings,
    generate_preliminary_rating,
    generate_entry_exit_strategy
)

def load_test_data(filepath):
    """Load test data from a JSON file"""
    with open(filepath, 'r') as f:
        return json.load(f)

def test_ta_interpretation(stock_data):
    """Test the technical analysis interpretation functions"""
    results = {}
    
    # Get technical indicators from the stock data
    indicators = stock_data.get('technical_indicators', {})
    price_data = stock_data.get('historical_quotes', {})
    
    if not indicators or not price_data:
        print("Test data missing required technical indicators or price data")
        return
    
    # Get current price (most recent close)
    recent_date = list(price_data.keys())[0]
    current_price = price_data[recent_date]['close']
    
    # Test RSI interpretation
    results['rsi_analysis'] = interpret_rsi(indicators.get('rsi'))
    
    # Test MACD interpretation
    results['macd_analysis'] = interpret_macd(indicators.get('macd', {}))
    
    # Test Moving Averages interpretation
    results['ma_analyses'] = interpret_moving_averages(
        current_price,
        indicators.get('sma_20'),
        indicators.get('sma_50'),
        indicators.get('sma_100')
    )
    
    # Test Bollinger Bands interpretation
    results['bb_analysis'] = interpret_bollinger_bands(
        current_price, 
        indicators.get('bollinger_bands', {})
    )
    
    # Test ADX interpretation
    results['adx_analysis'] = interpret_adx(indicators.get('adx'))
    
    # Test insider activity interpretation
    results['insider_analysis'] = interpret_insider_activity(
        stock_data.get('insider_trading', {})
    )
    
    # Test institutional holdings interpretation
    results['institutional_analysis'] = interpret_institutional_holdings(
        stock_data.get('institutional_holdings', {})
    )
    
    # Test preliminary rating
    results['prelim_rating'] = generate_preliminary_rating(stock_data)
    
    # Test entry/exit strategy generation
    entry_strategy, exit_strategy = generate_entry_exit_strategy(stock_data)
    results['entry_strategy'] = entry_strategy
    results['exit_strategy'] = exit_strategy
    
    return results

def print_test_results(results):
    """Print test results in a readable format"""
    print("\n=== TECHNICAL ANALYSIS INTERPRETATION TEST RESULTS ===\n")
    
    print("== RSI ANALYSIS ==")
    print(f"Status: {results['rsi_analysis']['status']}")
    print(f"Strength: {results['rsi_analysis']['strength']}")
    print(f"Description: {results['rsi_analysis']['description']}")
    print()
    
    print("== MACD ANALYSIS ==")
    print(f"Status: {results['macd_analysis']['status']}")
    print(f"Strength: {results['macd_analysis']['strength']}")
    print(f"Description: {results['macd_analysis']['description']}")
    print()
    
    print("== MOVING AVERAGES ANALYSES ==")
    for i, ma in enumerate(results['ma_analyses']):
        print(f"MA {i+1}: {ma['status']} (Strength: {ma['strength']}) - {ma['description']}")
    print()
    
    print("== BOLLINGER BANDS ANALYSIS ==")
    print(f"Status: {results['bb_analysis']['status']}")
    print(f"Strength: {results['bb_analysis']['strength']}")
    print(f"Description: {results['bb_analysis']['description']}")
    print()
    
    print("== ADX ANALYSIS ==")
    print(f"Status: {results['adx_analysis']['status']}")
    print(f"Strength: {results['adx_analysis']['strength']}")
    print(f"Description: {results['adx_analysis']['description']}")
    print()
    
    print("== INSIDER ACTIVITY ANALYSIS ==")
    print(f"Status: {results['insider_analysis'].get('status', 'N/A')}")
    print(f"Strength: {results['insider_analysis'].get('strength', 'N/A')}")
    print(f"Description: {results['insider_analysis'].get('description', 'N/A')}")
    print()
    
    print("== INSTITUTIONAL HOLDINGS ANALYSIS ==")
    print(f"Status: {results['institutional_analysis'].get('status', 'N/A')}")
    print(f"Strength: {results['institutional_analysis'].get('strength', 'N/A')}")
    print(f"Description: {results['institutional_analysis'].get('description', 'N/A')}")
    print()
    
    print("== PRELIMINARY RATING ==")
    print(f"Overall Rating: {results['prelim_rating'].get('rating', 'N/A')}/100")
    print(f"Technical Score: {results['prelim_rating'].get('technical_score', 'N/A')}/70")
    print(f"Fundamental Score: {results['prelim_rating'].get('fundamental_score', 'N/A')}/30")
    print(f"Confidence Level: {results['prelim_rating'].get('confidence', 'N/A')}/10")
    print("\nExplanations:")
    for exp in results['prelim_rating'].get('explanations', []):
        print(f"- {exp}")
    print()
    
    print("== ENTRY STRATEGY ==")
    print(f"Entry Price: {results['entry_strategy'].get('entry_price', 'N/A')}")
    print(f"Entry Timing: {results['entry_strategy'].get('entry_timing', 'N/A')}")
    print("Technical Indicators:")
    for indicator in results['entry_strategy'].get('technical_indicators', []):
        print(f"- {indicator}")
    print()
    
    print("== EXIT STRATEGY ==")
    print(f"Profit Target: {results['exit_strategy'].get('profit_target', 'N/A')}")
    print(f"Stop Loss: {results['exit_strategy'].get('stop_loss', 'N/A')}")
    print(f"Time Horizon: {results['exit_strategy'].get('time_horizon', 'N/A')}")
    print("Exit Conditions:")
    for condition in results['exit_strategy'].get('exit_conditions', []):
        print(f"- {condition}")

if __name__ == "__main__":
    # Path to test data
    achr_data_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)), 
        'QSBets/tests/ACHR_2025-03-06.json'
    )
    
    # Try different path if the first one doesn't work
    if not os.path.exists(achr_data_path):
        achr_data_path = os.path.join(
            os.path.dirname(__file__),
            './ACHR_2025-03-06.json'
        )
    
    # Load test data
    try:
        stock_data = load_test_data(achr_data_path)
        print(f"Successfully loaded test data for {stock_data.get('meta', {}).get('symbol', 'UNKNOWN')}")
        
        # Run the tests
        results = test_ta_interpretation(stock_data)
        
        # Print results
        if results:
            print_test_results(results)
        else:
            print("Test failed to produce results")
            
    except FileNotFoundError:
        print(f"Could not find test data file at: {achr_data_path}")
        print("Please ensure the file exists and the path is correct.")
    except json.JSONDecodeError:
        print(f"Error parsing JSON data from: {achr_data_path}")
        print("Please ensure the file contains valid JSON.")
    except Exception as e:
        print(f"Error during testing: {str(e)}")
