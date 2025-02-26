from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import pandas as pd
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from trafilatura import extract
import time
import json
from cache import cached
from utils import DAY_TTL


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


@cached(ttl_seconds=DAY_TTL)
def fetch_api(url: str) -> dict:
    """
    Fetch data from the Nasdaq API using the provided URL.
    """
    refresh_nasdaq_cookie()
    response = requests.get(url, headers=HEADERS.copy())
    response.raise_for_status()
    return response.json()


def refresh_nasdaq_cookie():
    """
    Uses Selenium to open Nasdaq's homepage and retrieve a fresh cookie.
    Requires Selenium and a webdriver (e.g., ChromeDriver) installed and in PATH.
    """
    global last_cookie_refresh_time
    if (
        last_cookie_refresh_time is None
        or (datetime.now() - last_cookie_refresh_time).total_seconds() > 1800
    ):
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        driver = webdriver.Chrome(options=options)
        try:
            driver.get("https://www.nasdaq.com")
            time.sleep(5)
            cookies = driver.get_cookies()
            # Fix: Join each cookie string correctly.
            cookie_str = "; ".join(
                f"{cookie['name']}={cookie['value']}" for cookie in cookies
            )
            HEADERS["cookie"] = cookie_str
            last_cookie_refresh_time = datetime.now()
        finally:
            driver.quit()


@cached(ttl_seconds=DAY_TTL)
def fetch_stocks_sentiment(timeframe: str = "24+hours"):
    """
    Fetches stock wallstreetbets sentiment analysis from
    https://api.beta.swaggystocks.com/wsb/sentiment/rating?timeframe={timeframe}

    timeframe: 1+week, 12+hours, 24+hours

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
        {
            "ticker": "PLTR",
            "sentiment_rating": 0,
            "timestamp": 1739897373,
            "positive": "574",
            "neutral": "2289",
            "negative": "666",
            "total": "3529",
            "next_earnings_date": "2025-05-05T00:00:00.000Z",
            "market_cap": 237702217656,
            "options_oi_call_ratio": "0.54221248",
            "30_day_avg_iv": 71.63000106811523,
            "unusual_option_volume": None
        },
        ...
    ]
    """
    url = f"https://api.beta.swaggystocks.com/wsb/sentiment/rating?timeframe={timeframe}"
    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        data = response.json()
        mapping = {}
        if isinstance(data, list):
            for ticker_data in data:
                ticker = ticker_data.get("ticker")
                if ticker:
                    cleaned_data = ticker_data.copy()
                    cleaned_data.pop("ticker", None)
                    cleaned_data.pop("timestamp", None)
                    cleaned_data.pop("market_cap", None)
                    mapping[ticker] = cleaned_data
    except Exception as e:
        print(f"[fetch_stocks_sentiment] Error fetching sentiment data: {e}")
    return mapping


def correlate_stocks_with_sentiment(df: pd.DataFrame) -> pd.DataFrame:
    """
    Correlate stocks with their sentiment rating.

    This function extracts only the 'sentiment_rating' for each symbol from
    the sentiment API data, converts the rating to an integer, and merges it
    with the provided DataFrame on the 'symbol' column.
    """
    sentiment_data = fetch_stocks_sentiment()

    # Build a DataFrame with only the symbol and its sentiment_rating as an integer.
    ratings = []
    for symbol, data in sentiment_data.items():
        rating_value = data.get("sentiment_rating")
        try:
            rating_int = int(rating_value)
        except (ValueError, TypeError):
            rating_int = None
        ratings.append({"symbol": symbol, "sentiment_rating": rating_int})

    sentiment_df = pd.DataFrame(ratings)

    # Merge provided DataFrame with sentiment ratings on symbol.
    merged_df = pd.merge(df, sentiment_df, on="symbol", how="outer")
    return merged_df
