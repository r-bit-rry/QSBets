from datetime import datetime
import concurrent
import os  # <-- added import
from dotenv import load_dotenv
import pandas as pd

from deepseek import DeepSeek
from nasdaq import correlate_stocks_with_news
from stock import Stock
from utils import send_text_via_telegram

# Constants for small-cap filter (in USD)
SMALL_CAP_MIN = 100e6  # $100M
SMALL_CAP_MAX = 9000e6  # $9,000M


def process_stock(stock_meta: pd.Series) -> dict:
    # Extract the full meta dict from the row.
    meta = stock_meta.to_dict()
    deepseek = DeepSeek()
    stock = Stock(symbol=meta["symbol"], meta=meta)
    doc = stock.make_json()
    recommendation = deepseek.consult(doc)

    return {
        "symbol": meta["symbol"],
        "rating": recommendation.get("rating"),
        "reasoning": recommendation.get("reasoning"),
        "enter_strategy": recommendation.get("enter_strategy"),
        "exit_strategy": recommendation.get("exit_strategy"),
    }


def main():
    """
    Main method to test StockAnalysisTool.
    It selects stocks that fit the small-cap criteria, processes them in parallel,
    sends an immediate Telegram message for stocks with rating >= 60, and finally writes
    all recommendations to a markdown file even if an exception or keyboard interruption occurs.
    """
    # Fetch full Nasdaq data with caching
    df = correlate_stocks_with_news()
    small_cap_df = df[
        (df["marketCap"] >= SMALL_CAP_MIN) & (df["marketCap"] <= SMALL_CAP_MAX)
    ]
    if small_cap_df.empty:
        print("No small-cap stocks found.")
        return

    # Count total news and press releases per symbol and sort the DataFrame
    small_cap_df.loc[:, "total_count"] = small_cap_df.groupby("symbol")[
        "symbol"
    ].transform("count")
    small_cap_df = small_cap_df.sort_values(
        by=["total_count", "marketCap"], ascending=[False, False]
    )
    small_cap_df = small_cap_df.drop_duplicates(subset=["symbol"])
    print("Total amount of small-cap stocks:", len(small_cap_df))

    results = []
    try:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            # Submit jobs for each stock row
            futures = [
                executor.submit(process_stock, row)
                for _, row in small_cap_df.iterrows()
            ]
            for future in concurrent.futures.as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                    try:
                        # Convert rating to float for comparison; if conversion fails skip immediate messaging.
                        rating = float(result["rating"])
                    except (ValueError, TypeError):
                        rating = 0

                    if rating >= 60:
                        message = (
                            f"<b>Symbol:</b> {result['symbol']}\n"
                            f"<b>Rating:</b> {result['rating']}\n"
                            f"<b>Reasoning:</b> {result['reasoning']}\n"
                            f"<b>Enter Strategy:</b> {result['enter_strategy']}\n"
                            f"<b>Exit Strategy:</b> {result['exit_strategy']}\n"
                        )
                        send_text_via_telegram(message)
                except Exception as e:
                    print(f"Error processing a stock: {e}")
    except KeyboardInterrupt:
        print("Keyboard interruption received. Saving results collected so far...")
    except Exception as e:
        print("An error occurred during processing:", e)
    finally:
        # Create a DataFrame from the collected results and sort by rating descending
        if results:
            recommendations_df = pd.DataFrame(results)
            recommendations_df["rating"] = pd.to_numeric(
                recommendations_df["rating"], errors="coerce"
            )
            recommendations_df = recommendations_df.sort_values(
                by="rating", ascending=False
            )
        else:
            recommendations_df = pd.DataFrame()
            print("No recommendations to save.")

        # Create the "reports" folder if it doesn't exist.
        os.makedirs("reports", exist_ok=True)
        # Create a datetime stamp in format YYYYMMDD_HHMM
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        md_content = f"# Investment Recommendations - {timestamp}\n\n"
        if not recommendations_df.empty:
            md_content += recommendations_df.to_markdown(index=False)
        else:
            md_content += "No recommendations available."

        filename = f"reports/investment_recommendation_{timestamp}.md"  # updated path
        with open(filename, "w", encoding="utf-8") as f:
            f.write(md_content)
        print(f"Investment recommendations saved to {filename}")


if __name__ == "__main__":
    load_dotenv(".env")
    main()
