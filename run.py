from datetime import datetime
import concurrent
import os
import traceback
from dotenv import load_dotenv
import pandas as pd
import chromadb

# from chromadb_integration import chromadb_insert
from deepseek_lc import consult
from nasdaq import DAY_TTL, correlate_stocks_with_news
from social import correlate_stocks_with_sentiment
from stock import Stock
from telegram import send_text_via_telegram, format_investment_message

# Constants for small-cap filter (in USD)
SMALL_CAP_MIN = 100e6  # $100M
SMALL_CAP_MAX = 9000e6  # $9,000M
STOCKS_TO_ANALYZE = 20

def aggregate_group(group: pd.DataFrame) -> pd.Series:
    aggregated = {
        "marketCap": group["marketCap"].max(),
        "press_news_total_count": len(group),
        "news_titles": list(
            {
                f"{row['news_created']} - {row['news_title']}"
                for _, row in group.iterrows()
                if pd.notna(row.get("news_title"))
            }
        ),
        "press_titles": list(
            {
                f"{row['press_created']} - {row['press_title']}"
                for _, row in group.iterrows()
                if pd.notna(row.get("press_title"))
            }
        ),
    }
    # Maintain other keys as they are
    single_keys = [
        "symbol",
        "name",
        "lastsale",
        "netchange",
        "pctchange",
        "volume",
        "country",
        "ipoyear",
        "industry",
        "sector",
        "next_earning_call",
        "sentiment_rating",
        "days_to_earnings",
    ]
    for key in single_keys:
        if key in group.columns:
            aggregated[key] = group.iloc[0][key]

    return pd.Series(aggregated)


# @chromadb_insert(collection_name="investment_recommendations")
def process_stock(nasdaq_data: pd.Series) -> dict:
    # Extract the full meta dict from the row.
    stock = Stock(nasdaq_data=nasdaq_data)
    doc = stock.make_json()
    recommendation = consult(doc)

    return {
        "symbol": stock.symbol,
        "rating": recommendation.get("rating"),
        "reasoning": recommendation.get("reasoning"),
        "enter_strategy": format_strategy(recommendation.get("enter_strategy", {})),
        "exit_strategy": format_strategy(recommendation.get("exit_strategy", {})),
    }

def format_strategy(strategy: dict) -> str:
    return "\n".join([f"{key}: {value}" for key, value in strategy.items()])


def summarize_chroma():
    # Create a persistent client with the same directory used for saving
    client = chromadb.PersistentClient(path="chroma_db")
    submission_collection = client.get_or_create_collection("submission")
    redditor_collection = client.get_or_create_collection("redditor")
    comment_collection = client.get_or_create_collection("comment")
    # Retrieve all documents (assuming no filter returns all)
    submissions = submission_collection.get()  
    redditors = redditor_collection.get()
    comments = comment_collection.get()
    print("Summary from ChromaDB:")
    print(f"Total submissions: {len(submissions.get('ids', []))}")
    print(f"Total redditors: {len(redditors.get('ids', []))}")
    print(f"Total comments: {len(comments.get('ids', []))}")


def main():
    """
    Main method to test StockAnalysisTool.
    It selects stocks that fit the small-cap criteria, processes them in parallel,
    sends an immediate Telegram message for stocks with rating >= 60, and finally writes
    all recommendations to a markdown file even if an exception or keyboard interruption occurs.
    """
    # Fetch full Nasdaq data with caching
    df = correlate_stocks_with_news()
    df = correlate_stocks_with_sentiment(df)
    small_cap_df = df[
        (df["marketCap"] >= SMALL_CAP_MIN) & (df["marketCap"] <= SMALL_CAP_MAX)
    ]
    if small_cap_df.empty:
        print("No small-cap stocks found.")
        return

    # Group by symbol while aggregating news and press info.
    aggregated_df = (
        small_cap_df.groupby("symbol", as_index=False)
        .apply(aggregate_group)
        .reset_index(drop=True)
    )
    aggregated_df['days_to_earnings'] = aggregated_df['days_to_earnings'] if 'days_to_earnings' in aggregated_df.columns else (
        aggregated_df['next_earning_date'].apply(
            lambda x: (pd.to_datetime(x) - pd.Timestamp.now()).days if pd.notna(x) else 999
        )
    )

    # Convert percentage change to numeric for proper sorting
    aggregated_df["pctchange"] = pd.to_numeric(
        aggregated_df["pctchange"].str.replace("%", ""), errors="coerce"
    ).abs()

    aggregated_df['volume'] = pd.to_numeric(aggregated_df['volume'], errors='coerce')

    aggregated_df['next_day_potential'] = (
        # Earnings within 0-2 days get highest priority
        (aggregated_df['days_to_earnings'] <= 2) * 1000 +
        # Social sentiment has strong impact on retail-driven stocks
        (aggregated_df['sentiment_rating'].fillna(0) * 5) +
        # Recent price volatility indicates ongoing interest
        aggregated_df['pctchange'].fillna(0) * 2 +
        # News coverage drives interest and potential movement
        aggregated_df['press_news_total_count'].fillna(0) * 5 +
        # High volume indicates liquidity and interest
        aggregated_df['volume'].fillna(0) / 1000
    )

    # Sort by our composite next_day_potential score
    aggregated_df = aggregated_df.sort_values(
        by=['next_day_potential'], 
        ascending=False
    )
    print("Total amount of small-cap stocks:", len(aggregated_df))
    aggregated_df = aggregated_df.head(STOCKS_TO_ANALYZE)
    results = []
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            # Submit jobs for each stock row
            futures = [
                executor.submit(process_stock, row)
                for _, row in aggregated_df.iterrows()
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

                    if rating > 70:
                        message = format_investment_message(result)
                        send_text_via_telegram(message)
                except Exception as e:
                    traceback.print_exc()
                    print(f"Error processing a stock: {e}")
    except KeyboardInterrupt:
        print("Keyboard interruption received. Saving results collected so far...")
    except Exception as e:
        print(f"An error occurred during processing: {e}")
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

    # At the end, after processing stocks, summarize documents from ChromaDB
    # summarize_chroma()


if __name__ == "__main__":
    load_dotenv(".env")
    main()
