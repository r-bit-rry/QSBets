import os
import sys


sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from telegram import format_investment_message

def test_message_formatter():
    """
    Test the format_investment_message function with sample data.
    """
    # Sample data for testing
    test_data = {
        "symbol": "ASTS",
        "rating": 85,
        "confidence": 8,
        "reasoning": "The stock has shown strong bullish momentum with indicators like RSI at 62.28 and a strong MACD signal. Moving averages are also aligned in a bullish manner, with the price above the 20,50,  and100-day SMAs. Moderate institutional ownership and balanced insider activity further support this view. The company's revenue-generating nature and recent advancements in satellite technology are positive factors.",
        "bullish_factors": [
            "RSI at 62.28 indicates a bullish trend.",
            "Strong MACD signal with a difference of1.79, indicating a strong buy signal.",
            "Price is above all moving averages (20,50, 100-day SMAs), showing a strong uptrend.",
            "Moderate institutional ownership at33.1%, indicating a balanced level of support.",
            "Recent contract with the U.S. Space Development Agency worth $43 million, showing significant financial backing.",
        ],
        "bearish_factors": [
            "High debt levels with public debt to GDP at121.87%, indicating potential financial strain.",
            "Interest rates are relatively high, with the10-year treasury yield at4.29%, which could impact borrowing costs.",
            "Inflation is slightly above average, with the CPI annual rate at3.0%, potentially affecting consumer spending.",
            "Short interest is  high, with42,427,798  shares shorted, indicating potential selling pressure.",
        ],
        "macro_impact": "The current macroeconomic conditions, with interest rates at4.33% and a 10-year treasury yield of 4.29%, are slightly unfavorable for ASTS. However, the company's focus on satellite technology and its potential for growth in the space-based cellular broadband network might mitigate these effects. Inflation at3.0% is manageable,  and the company's revenue growth could  be less impacted compared to other sectors.",
        "enter_strategy": {
            "entry_price": "The current price of $33.40 or a pullback to the20-day SMA at $29.35.",
            "entry_timing": "Immediate entry or on  a pullback, looking for a volume of over10 million shares.",
            "technical _indicators": [
                "Monitor the20-day SMA for support at $29.35.",
                " Look for a volume spike above10 million shares to confirm entry.",
            ],
        },
        "exit_strategy": {
            "profit_target": "$34.33 (Bollinger Upper Band, +2.8%)",
            "stop_loss": "$24.78 (-34. 8%) ",
            "time_horizon": "2-4 weeks",
            "exit_conditions": [
                "Close below the100-day SMA.",
                "RSI >70, indicating an overb ought condition.",
            ],
        },
        "request_id": "sentiment_1741615213.591004",
        "requested_by": "-4614455844",
    }

    # Format the message using the function
    formatted_message = format_investment_message(test_data)

    # Print the formatted message for inspection
    print("Formatted Telegram Message:")
    print("=" * 60)
    print(formatted_message)
    print("=" * 60)

    # You could also add assertions here to verify specific aspects of formatting
    assert "ASTS" in formatted_message, "Symbol not found in formatted message"
    assert "<b>Rating:</b> 85" in formatted_message, "Rating not found or incorrect"
    assert "<b>Confidence:</b> 8" in formatted_message, "Confidence not found or incorrect"

    # Verify internal fields are filtered out
    assert "request_id" not in formatted_message, "Internal field 'request_id' should be filtered out"
    assert "requested_by" not in formatted_message, "Internal field 'requested_by' should be filtered out"

    print("All tests passed!")

if __name__ == "__main__":
    test_message_formatter()
