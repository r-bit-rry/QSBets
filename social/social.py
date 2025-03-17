from datetime import datetime
import pandas as pd
import requests
import json
from cache.cache import cached, HOURS2_TTL
import os
import random
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

HEADERS = {
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "accept-encoding": "gzip, deflate, br, zstd",
    "accept-language": "en-GB,en;q=0.9,en-US;q=0.8",
    "cache-control": "max-age=0",
    "cookie": (
        "akaalb_ALB_Default=~op=ao_api__east1:ao_api_central1|~rv=68~m=ao_api_central1:0|~os=ff51b6e767de05e2054c5c99e232919a~id=1008c488fee38514c6a4be6e0c1f1bed; "
        "ak_bmsc=793B63ED6C505C691C11004863AE1E99~000000000000000000000000000000~YAAQLChDFzOZCtOUAQAAjk7y2ho2bfq5gtbTKNESsG47b5ds5FgIZMAc02iSCSFwT4S22Co9BOsC83MBJyMSgiI1VgT6oWdUBJnPs9fAmVgqHsHKJ1uvwjG0gfsIa1grhPgRzzbiuIp6PK35vfLpVfv8EC7QXYpwiwPPHLCiMR0RQ9pmeUrxPCoqBS3v6hcABEjo7bkSdrKmceZcCmpfrHrqjbTQEZbWozP2tLJs7axrfb2BE0B0yXdZLDcMd9brk+sRTgWofZxbXaANgXXDu/3J7Z6jL5oa/k/B0QpFqC+WUadfG4SuSBxY9tyXWV3oyey7k9TPHV2HAql8ursdsoGrKzCa0MUdWIhoQfWHxIPwHkPQu2VasYzke4ZNsLY441pYok7I6iUA"
    ),
    "dnt": "1",
    "priority": "u=0, i",
    "sec-ch-ua": '"Not A(Brand";v="8", "Chromium";v="132", "Microsoft Edge";v="132"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "none",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36 Edg/132.0.0.0",
}
last_cookie_refresh_time = None


# New helper methods for robust error handling
def safe_parse_date(date_str: str, fmt: str) -> datetime | None:
    try:
        return datetime.strptime(date_str, fmt)
    except Exception as e:
        print(f"[safe_parse_date] Error parsing '{date_str}': {e}")
        return None


def safe_convert_to_int(value):
    """Safely convert a value to integer, returning None if conversion fails."""
    try:
        return int(value) if value is not None else None
    except (ValueError, TypeError):
        return None

@cached(ttl_seconds=HOURS2_TTL)
def fetch_stocks_social() -> dict:
    """
    Fetches stocks social ranking from
    https://api.beta.swaggystocks.com/stocks/top-tickers

    return a dictionary like this:
    {
    "data": [
        {
            "timestamp": 1741698061,
            "date": "2025-03-11T00:00:00.000Z",
            "ticker": "TSLA",
            "social_volume": 1113,
            "sentiment": "0.5073",
            "social_volume_share": 12.050999641418457,
            "last_day_social_volume": 599,
            "rank": 1,
            "last_day_rank": 1,
            "last_day_social_volume_share": 10.803000450134277,
            "last_day_sentiment": "0.4886"
        },
        {
            "timestamp": 1741698061,
            "date": "2025-03-11T00:00:00.000Z",
            "ticker": "SPY",
            "social_volume": 400,
            "sentiment": "0.4808",
            "social_volume_share": 4.330999851226807,
            "last_day_social_volume": 207,
            "rank": 2,
            "last_day_rank": 3,
            "last_day_social_volume_share": 3.7330000400543213,
            "last_day_sentiment": "0.4217"
        },
        ...
        {
            "timestamp": 1741698061,
            "date": "2025-03-11T00:00:00.000Z",
            "ticker": "TSLX",
            "social_volume": 3,
            "sentiment": "0.0000",
            "social_volume_share": 0.03200000151991844,
            "rank": 379
        },
        ]
    """
    url = "https://api.beta.swaggystocks.com/stocks/top-tickers"
    mapping = {}

    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        data = response.json()

        if not isinstance(data, dict) or "data" not in data:
            print(f"[fetch_stocks_social] Unexpected data format: {type(data)}")
            return mapping

        # Process each ticker's social data
        for item in data.get("data", []):
            ticker = item.get("ticker")
            if not ticker:
                continue

            # Calculate sentiment change if both values exist
            sentiment_change = None
            if "sentiment" in item and "last_day_sentiment" in item:
                try:
                    current = float(item["sentiment"])
                    last_day = float(item["last_day_sentiment"])
                    sentiment_change = current - last_day
                except (ValueError, TypeError):
                    pass

            # Calculate social volume change if both values exist
            social_volume_change = None
            if "social_volume" in item and "last_day_social_volume" in item:
                try:
                    current = safe_convert_to_int(item["social_volume"])
                    last_day = safe_convert_to_int(item["last_day_social_volume"])
                    if current is not None and last_day is not None:
                        social_volume_change = current - last_day
                except (ValueError, TypeError):
                    pass

            # Create a clean data structure for this ticker
            mapping[ticker] = {
                "social_volume": safe_convert_to_int(item.get("social_volume")),
                "sentiment": item.get("sentiment"),
                "rank": safe_convert_to_int(item.get("rank")),
                "last_day_rank": safe_convert_to_int(item.get("last_day_rank")),
                "sentiment_change": sentiment_change,
                "social_volume_change": social_volume_change,
                "social_volume_share": item.get("social_volume_share"),
            }

    except requests.RequestException as e:
        print(f"[fetch_stocks_social] Request error: {e}")
    except json.JSONDecodeError as e:
        print(f"[fetch_stocks_social] JSON decode error: {e}")
    except Exception as e:
        print(f"[fetch_stocks_social] Unexpected error: {e}")

    return mapping

@cached(ttl_seconds=HOURS2_TTL)
def fetch_stocks_sentiment(timeframe: str = "1+week") -> dict:
    """
    Fetches stock wallstreetbets sentiment analysis from
    https://api.beta.swaggystocks.com/wsb/sentiment/rating?timeframe={timeframe}

    Args:
        timeframe: Time period for data (options: "1+week", "12+hours", "24+hours")

    Returns:
        Dictionary mapping tickers to their sentiment data with cleaned field names

    Response looks like:
    [
        {
            "ticker": "NVDA",
            "sentiment_rating": 0,
            "timestamp": 1739897374,
            "positive": "939",
            "neutral": "2778",
            "negative": "422",
            "total": "4139",
            "next_earnings_date": "2025-02-26T00:00:00.000Z",
            "market_cap": 3292190700000,
            "options_oi_call_ratio": "0.51608346",
            "30_day_avg_iv": 66.60000085830688,
            "unusual_option_volume": None
        },
        ...
    ]
    """
    url = f"https://api.beta.swaggystocks.com/wsb/sentiment/rating?timeframe={timeframe}"
    field_mappings = {
        "sentiment_rating": "sentiment_score[-10,10]",
        "positive": "positive_mentions",
        "neutral": "neutral_mentions",
        "negative": "negative_mentions",
        "options_oi_call_ratio": "calls_to_put_ratio",
        "30_day_avg_iv": "avg_iv_30d",
    }

    skip_fields = {"ticker", "timestamp", "market_cap"}
    mapping = {}

    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        data = response.json()

        if not isinstance(data, list):
            print(f"[fetch_stocks_sentiment] Unexpected data format: {type(data)}")
            return mapping

        for ticker_data in data:
            ticker = ticker_data.get("ticker")
            if not ticker:
                continue

            cleaned_data = {}

            # Process all fields with appropriate transformations
            for key, value in ticker_data.items():
                if key in skip_fields:
                    continue

                # Handle next_earnings_date specially
                if key == "next_earnings_date" and value:
                    try:
                        cleaned_data[key] = (
                            value.split("T")[0] if "T" in value else value
                        )
                    except (AttributeError, IndexError):
                        cleaned_data[key] = value
                # Map field names according to our dictionary
                elif key in field_mappings:
                    cleaned_data[field_mappings[key]] = value
                # Keep other fields as-is
                else:
                    cleaned_data[key] = value

            mapping[ticker] = cleaned_data

    except requests.RequestException as e:
        print(f"[fetch_stocks_sentiment] Request error: {e}")
    except json.JSONDecodeError as e:
        print(f"[fetch_stocks_sentiment] JSON decode error: {e}")
    except Exception as e:
        print(f"[fetch_stocks_sentiment] Unexpected error: {e}")

    return mapping


def get_sentiment_df() -> pd.DataFrame:
    """
    Fetch and return combined sentiment and social data as a DataFrame.

    Returns:
        DataFrame with sentiment and social metrics
    """
    # Fetch both data sources
    sentiment_data = fetch_stocks_sentiment()
    social_data = fetch_stocks_social()

    # Prepare sentiment data
    sentiment_entries = [
        {
            "symbol": symbol,
            "sentiment_rating": safe_convert_to_int(
                data.get("sentiment_score[-10,10]")
            ),
        }
        for symbol, data in sentiment_data.items()
    ]

    # Prepare social data
    social_entries = [
        {
            "symbol": symbol,
            "social_volume": data.get("social_volume"),
            "social_sentiment": data.get("sentiment"),
            "social_rank": data.get("rank"),
            "social_rank_change": data.get("last_day_rank", 0) - data.get("rank", 0) if data.get("rank") and data.get("last_day_rank") else None,
            "sentiment_change": data.get("sentiment_change"),
            "social_volume_change": data.get("social_volume_change"),
            "social_volume_share": data.get("social_volume_share"),
        }
        for symbol, data in social_data.items()
    ]

    # Convert to DataFrames
    sentiment_df = pd.DataFrame(sentiment_entries) if sentiment_entries else pd.DataFrame(columns=["symbol", "sentiment_rating"])
    social_df = pd.DataFrame(social_entries) if social_entries else pd.DataFrame(columns=[
        "symbol", "social_volume", "social_sentiment", "social_rank", 
        "social_rank_change", "sentiment_change", "social_volume_change", "social_volume_share"
    ])

    # Merge both data sources using outer join to keep all tickers
    combined_df = pd.merge(sentiment_df, social_df, on="symbol", how="outer")

    return combined_df

def correlate_stocks_with_sentiment(df: pd.DataFrame) -> pd.DataFrame:
    """
    Correlate stocks with their sentiment rating and social metrics.

    Args:
        df: DataFrame with a 'symbol' column to merge with sentiment data

    Returns:
        DataFrame with sentiment and social data added
    """
    combined_df = get_sentiment_df()
    return pd.merge(df, combined_df, on="symbol", how="outer")
