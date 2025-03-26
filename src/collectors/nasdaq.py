from datetime import datetime, timedelta
import logging
from dotenv import load_dotenv
import pandas as pd
import requests
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from trafilatura import extract
import time
import json
from storage.cache import cached, DAY_TTL, MONTH_TTL

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("nasdaq")

NASDAQ_HEADERS = {
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
def safe_parse_date(date_str: str, fmt: str) -> (datetime | None):
    try:
        return datetime.strptime(date_str, fmt)
    except Exception as e:
        logger.error(f"[safe_parse_date] Error parsing '{date_str}': {e}")
        return None

def get_full_url(url: str) -> str:
    return "https://www.nasdaq.com" + url if url.startswith("/") else url

def safe_retrieve_page(url: str, format: str = "txt") -> str:
    try:
        return retrieve_nasdaq_page(url, format)
    except Exception as e:
        logger.error(f"[safe_retrieve_page] Error retrieving {url}: {e}")
        return ""

def clean_key_from_json(json_data: dict, key: str) -> str:
    return [
        {k: v for k, v in json_data.items() if k != key}
        if isinstance(datum, dict) else datum
        for datum in json_data
    ]

@cached(ttl_seconds=1800)
def retrieve_nasdaq_page(url: str, format: str = "txt") -> str:
    """
    Retrieve the content of a web page using trafilatura with caching.
    """
    refresh_nasdaq_cookie()
    response = requests.get(url, headers=NASDAQ_HEADERS)
    response.raise_for_status()
    downloaded = response.text
    if downloaded is None:
        return None
    content = extract(
        downloaded,
        url=url,
        favor_precision=True,
        include_comments=True,
        output_format=format,
        deduplicate=True,
    )
    return content

@cached(ttl_seconds=300)
def fetch_nasdaq_api(url: str) -> dict:
    """
    Fetch data from the Nasdaq API using the provided URL.
    """
    refresh_nasdaq_cookie()
    response = requests.get(url, headers=NASDAQ_HEADERS.copy())
    response.raise_for_status()
    return response.json()

def refresh_nasdaq_cookie():
    """
    Uses Selenium to open Nasdaq's homepage and retrieve a fresh cookie.
    Requires Selenium and a webdriver (e.g., ChromeDriver) installed and in PATH.
    """
    global last_cookie_refresh_time
    if (last_cookie_refresh_time is None or (datetime.now() - last_cookie_refresh_time).total_seconds() > 1800):
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        driver = webdriver.Chrome(options=options)
        try:
            driver.get("https://www.nasdaq.com")
            time.sleep(5)
            cookies = driver.get_cookies()
            # Fix: Join each cookie string correctly.
            cookie_str = "; ".join(f"{cookie['name']}={cookie['value']}" for cookie in cookies)
            NASDAQ_HEADERS["cookie"] = cookie_str
            last_cookie_refresh_time = datetime.now()
        except Exception as e:
            logger.error(f"Error refreshing Nasdaq cookie: {e}")
        finally:
            driver.quit()

@cached(ttl_seconds=1800)
def fetch_stock_press_releases(symbol: str) -> list[str]:
    """
    Fetches stock press releases for the given stock symbol from the Nasdaq API.
    https://www.nasdaq.com/api/news/topic/press_release?q=symbol:asts|assetclass:stocks&limit=10&offset=0
    Removes unneeded information from the JSON to keep it as simple as possible for further analysis by LLM.
    Retrieve pages provided by the URL (fetches the press release content) and
    keeps only press releases from the last week.
    """
    url = f"https://www.nasdaq.com/api/news/topic/press_release?q=symbol:{symbol}|assetclass:stocks&limit=10&offset=0"
    json_data = fetch_nasdaq_api(url)
    data = json_data.get("data", {})
    if data is None:
        return []
    rows = data.get("rows") or []

    recent_releases = []

    for row in rows:
        created_date = safe_parse_date(row["created"], "%b %d, %Y")
        if not created_date or created_date < datetime.now() - timedelta(days=15):
            continue

        pr_url = row.get("url", "")
        full_url = get_full_url(pr_url)
        press_release = {
            "title": row.get("title", ""),
            "created": row.get("created", ""),
            "publisher": row.get("publisher", ""),
            "url": full_url,
        }
        content = safe_retrieve_page(full_url, "txt")
        press_release["content"] = content
        recent_releases.append(json.dumps(press_release))
    return recent_releases

@cached(ttl_seconds=1800)
def fetch_stock_news(symbol: str) -> list[str]:
    """
    Fetches stock news for the given stock symbol from the Nasdaq API.
    Removes unneeded information from the JSON to keep it as simple as possible for further analysis by LLM.
    Keeps only news from the last week.
    Retrieves the page content from the URL and stores it in the 'content' field.
    """
    news_url = f"https://www.nasdaq.com/api/news/topic/articlebysymbol?q={symbol}|STOCKS&offset=0&limit=10&fallback=true"
    json_data = fetch_nasdaq_api(news_url)
    data = json_data.get("data", {})
    if data is None:
        return []
    rows = data.get("rows", [])

    recent_news = []

    for row in rows:
        created_date = safe_parse_date(row["created"], "%b %d, %Y")
        if not created_date or created_date < datetime.now() - timedelta(days=7):
            continue

        news_url_field = row.get("url", "")
        full_url = get_full_url(news_url_field)
        news_item = {
            "title": row.get("title", ""),
            "created": row.get("created", ""),
            "publisher": row.get("publisher", ""),
            "url": full_url,
        }
        content = safe_retrieve_page(full_url, "txt")
        news_item["content"] = content
        recent_news.append(json.dumps(news_item))
    return recent_news

@cached(ttl_seconds=DAY_TTL)
def fetch_revenue_earnings(symbol: str) -> str:
    """
    Fetches revenue and earnings data for the given stock symbol from the Nasdaq API.
    https://api.nasdaq.com/api/company/ASTS/revenue?limit=1
    Removes unneeded information from the JSON to keep it as simple as possible for further analysis by LLM.
    Transposes the table to only include the last 4 quarters.
    """
    revenue_earnings_url = (
        f"https://api.nasdaq.com/api/company/{symbol}/revenue?limit=1"
    )

    json_data = fetch_nasdaq_api(revenue_earnings_url)
    data = json_data.get("data")
    if not data:
        logger.warning("No rows found in revenue table")
        return []

    revenue_table = data.get("revenueTable") or {}
    rows = revenue_table.get("rows") or []

    if not rows:
        logger.warning("No rows found in revenue table")
        return []

    # Transpose the table to only include groups containing 4 entries each.
    transposed_data = []
    try:
        for i in range(0, len(rows), 4):
            quarter_data = {
                "quarter": rows[i]["value1"],
                "revenue": rows[i + 1]["value2"],
                "eps": rows[i + 2]["value2"],
                "dividends": rows[i + 3]["value2"],
            }
            transposed_data.append(quarter_data)
    except Exception as e:
        logger.error(f"Error processing revenue rows: {e}")
        return []

    # Keep only the last 6 quarters
    transposed_data = transposed_data[-6:]

    return transposed_data


@cached(ttl_seconds=DAY_TTL)
def fetch_short_interest(symbol: str) -> str:
    """
    Fetches short interest data for the given stock symbol from the Nasdaq API.
    https://api.nasdaq.com/api/quote/ASTS/short-interest?assetClass=stocks
    Removes unneeded information from the JSON to keep it as simple as possible for further analysis by LLM.
    Take only 4 most up to date rows.
    """
    short_interest_url = f"https://api.nasdaq.com/api/quote/{symbol}/short-interest?assetClass=stocks"
    json_data = fetch_nasdaq_api(short_interest_url)
    data = json_data.get("data", {})
    if data is None:
        return []
    short_interest_table = data.get("shortInterestTable") or {}
    rows = short_interest_table.get("rows") or []
    # Update: Take only the 4 most recent rows.
    return rows[:4]


@cached(ttl_seconds=DAY_TTL)
def fetch_institutional_holdings(symbol: str) -> str:
    """
    Fetches institutional holdings data for the given stock symbol from the Nasdaq API.
    https://api.nasdaq.com/api/company/ASTS/institutional-holdings?limit=10&type=TOTAL&sortColumn=marketValue
    Removes unneeded information from the JSON to keep it as simple as possible for further analysis by LLM.
    """
    institutional_holdings_url = f"https://api.nasdaq.com/api/company/{symbol}/institutional-holdings?limit=10&type=TOTAL&sortColumn=marketValue"
    json_data = fetch_nasdaq_api(institutional_holdings_url)
    data = json_data.get("data", {})
    if data is None:
        return {}

    # Extract relevant information
    ownership_summary = data.get("ownershipSummary", {})
    active_positions = data.get("activePositions", {}).get("rows", [])
    new_sold_out_positions = data.get("newSoldOutPositions", {}).get("rows", [])

    holdings_transactions_data = data.get("holdingsTransactions") or {}
    table_data = holdings_transactions_data.get("table") or {}
    holdings_transactions = table_data.get("rows", [])

    cleaned_holdings_transactions = [
        {k: v for k, v in item.items() if k != "url"} for item in holdings_transactions
    ]

    # Format the extracted information as JSON
    institutional_holdings_info = {
        "ownership_summary": ownership_summary,
        "active_positions": active_positions,
        "new_sold_out_positions": new_sold_out_positions,
        "holdings_transactions": cleaned_holdings_transactions,
    }

    return institutional_holdings_info


@cached(ttl_seconds=DAY_TTL)
def fetch_historical_quotes(symbol: str, period: int = 5) -> dict:
    """
    Fetches historical prices for the given stock symbol from the Nasdaq API.
    https://api.nasdaq.com/api/quote/{symbol}/historical?assetclass=stocks

    Returns a dict containing the trading data with numeric values (not string with $ and commas):
    {
        "MM/DD/YYYY": {
            "close": 123.45,  # float
            "volume": 1234567,  # int
            "open": 123.45,    # float
            "high": 124.56,    # float
            "low": 122.34      # float
        },
        ...
    }
    """
    # Calculate dates for the API request
    end_date = datetime.now()
    start_date = end_date - timedelta(
        days=period
    )  # Request more data than needed to ensure we have enough trading days

    historical_url = (
        f"https://api.nasdaq.com/api/quote/{symbol}/historical?"
        f"assetclass=stocks&fromdate={start_date.strftime('%Y-%m-%d')}&"
        f"limit={period}&todate={end_date.strftime('%Y-%m-%d')}"
    )

    json_data = fetch_nasdaq_api(historical_url)

    data = json_data.get("data", {})
    if data is None:
        return {}

    # Extract the trades table which contains all the price information
    trades_data = data.get("tradesTable", {}).get("rows") or []

    prices_dict = {}
    for row in trades_data:
        # Clean and convert price values (remove $ and commas)
        close_price = (
            float(row["close"].replace("$", "").replace(",", ""))
            if row["close"]
            else None
        )
        open_price = (
            float(row["open"].replace("$", "").replace(",", ""))
            if row["open"]
            else None
        )
        high_price = (
            float(row["high"].replace("$", "").replace(",", ""))
            if row["high"]
            else None
        )
        low_price = (
            float(row["low"].replace("$", "").replace(",", "")) if row["low"] else None
        )

        # Clean and convert volume (remove commas)
        volume = int(row["volume"].replace(",", "")) if row["volume"] else None

        prices_dict[row["date"]] = {
            "close": close_price,
            "volume": volume,
            "open": open_price,
            "high": high_price,
            "low": low_price,
        }

    return prices_dict


@cached(ttl_seconds=DAY_TTL)
def fetch_insider_trading(symbol: str) -> str:
    """
    Fetches insider trading data for the given stock symbol from the Nasdaq API.
    https://api.nasdaq.com/api/company/ASTS/insider-trades?limit=10&type=all&sortColumn=lastDate&sortOrder=DESC

    Removes unneeded information from the JSON to keep it as simple as possible for further analysis by LLM.
    """
    insider_trading_url = f"https://api.nasdaq.com/api/company/{symbol}/insider-trades?limit=10&type=all&sortColumn=lastDate&sortOrder=DESC"
    json_data = fetch_nasdaq_api(insider_trading_url)
    data = json_data.get("data", {})
    if data is None:
        return {}

    # Extract relevant information
    number_of_trades = data.get("numberOfTrades", {}).get("rows", [])
    number_of_shares_traded = data.get("numberOfSharesTraded", {}).get("rows", [])
    transaction_table = data.get("transactionTable", {}).get("table", {}).get("rows") or []

    # Remove the "url" field from each transaction in the transaction table
    cleaned_transaction_table = [{k: v for k, v in item.items() if k != 'url'} for item in transaction_table]

    # Format the extracted information as JSON
    insider_trading_info = {
        "number_of_trades": number_of_trades,
        "number_of_shares_traded": number_of_shares_traded,
        "transaction_table": cleaned_transaction_table,
    }

    return insider_trading_info

@cached(ttl_seconds=MONTH_TTL)
def fetch_description(symbol: str) -> str:
    """
    Goes to nasdaq API with symbol and fetches description using symbol
    """
    profile_url = f"https://api.nasdaq.com/api/company/{symbol}/company-profile"
    json_data = fetch_nasdaq_api(profile_url)
    data = json_data.get("data", {})
    if data is None:
        return ""
    company_description = data.get("CompanyDescription", {}).get("value", "")
    return company_description

# Deprecated in favor of edgartools
@cached(ttl_seconds=DAY_TTL)
def fetch_sec_filings(symbol: str) -> str:
    """
    Fetches SEC filings for the given stock symbol from the Nasdaq API.
    Retrieves the latest 10-K and 10-Q filings and other recent filings from the last week.
    Returns the filings as a JSON string where each filing is represented as an object with keys:
    "label", "formType", "filed", "period", and "text".
    """
    sec_filings_url = f"https://api.nasdaq.com/api/company/{symbol}/sec-filings?limit=14&sortColumn=filed&sortOrder=desc&IsQuoteMedia=true"
    response = fetch_nasdaq_api(sec_filings_url)
    data = response.get("data", {})
    if data is None:
        return []
    rows = data.get("rows", [])
    latest_filings = data.get("latest") or []

    # Initialize relevant_filings with the latest 10-K and 10-Q filings
    relevant_filings = []
    for latest in latest_filings:
        if latest["label"] in ["10-K", "10-Q"]:
            relevant_filings.append(
                {
                    "label": latest["label"],
                    "formType": latest["label"],
                    "filed": latest["value"].split("&dateFiled=")[-1],
                    "period": "",
                    "view": {"htmlLink": latest["value"]},
                }
            )

    # Filter other filings from the last week
    one_week_ago = datetime.now() - timedelta(days=7)
    for row in rows:
        filed_date = datetime.strptime(row["filed"], "%m/%d/%Y")
        if filed_date >= one_week_ago:
            relevant_filings.append(row)

    # Retrieve the HTML content for each relevant filing (using filed as placeholder for now)
    filings_content = []
    for filing in relevant_filings:
        html_link = filing["view"]["htmlLink"]
        filings_content.append(
            {
                "label": filing.get("label", filing["formType"]),
                "formType": filing.get("formType", ""),
                "filed": filing.get("filed", ""),
                "period": filing.get("period", ""),
                "text": filing[
                    "filed"
                ],  # TODO: replace with actual text_content retrieval
            }
        )

    return filings_content

@cached(ttl_seconds=1800)
def fetch_nasdaq_news(limit:int = 1000) -> pd.DataFrame:
    """
    Fetch Nasdaq news from the API endpoint:
    https://www.nasdaq.com/api/news/topic/articlebysymbol?q=offset=0&limit=1000&assetclass:stocks

    We construct a DataFrame containing a row for each related symbol, with:
      - symbol (extracted from each related_symbols element before the pipe '|'),
      - news_title,
      - news_created,
      - news_url (ensuring a full URL is provided).
    """
    news_api_url = f"https://www.nasdaq.com/api/news/topic/articlebysymbol?q=offset=0&limit={limit}&assetclass:stocks"
    json_data = fetch_nasdaq_api(news_api_url)
    data = json_data.get("data", {})
    if data is None:
        return pd.DataFrame()
    rows = data.get("rows") or []

    processed = []
    for row in rows:
        title = row.get("title", "")
        created = row.get("created", "")
        url = row.get("url", "")
        # Prepend Nasdaq base URL if the URL is relative.
        if url.startswith("/"):
            url = "https://www.nasdaq.com" + url

        related_symbols = row.get("related_symbols", [])
        if related_symbols and isinstance(related_symbols, list):
            for sym in related_symbols:
                symbol = sym.split("|")[0] if "|" in sym else sym
                processed.append({
                    "symbol": symbol.upper(),
                    "news_title": title,
                    "news_created": created,
                    "news_url": url
                })
        else:
            processed.append({
                "symbol": "",
                "news_title": title,
                "news_created": created,
                "news_url": url
            })

    df = pd.DataFrame(processed)
    return df

def fetch_nasdaq_press_release(limit: int = 1000) -> pd.DataFrame:
    """
    Fetch Nasdaq press releases from the API endpoint:
    https://www.nasdaq.com/api/news/topic/press_release?q=assetclass:stocks&limit=200

    We construct a dataframe containing a row for each related symbol, with:
      - symbol (extracted from each related_symbols element before the pipe '|'),
      - title,
      - created,
      - url (ensuring a full URL is provided).
    """
    press_release_url = f"https://www.nasdaq.com/api/news/topic/press_release?q=assetclass:stocks&limit={limit}"
    json_data = fetch_nasdaq_api(press_release_url)
    data = json_data.get("data", {})
    if data is None:
        return pd.DataFrame()
    rows = data.get("rows") or []
    
    processed = []
    for row in rows:
        title = row.get("title", "")
        created = row.get("created", "")
        url = row.get("url", "")
        # If url is relative, prepend Nasdaq base URL.
        if url.startswith("/"):
            url = "https://www.nasdaq.com" + url

        related_symbols = row.get("related_symbols", [])
        if related_symbols and isinstance(related_symbols, list):
            for sym in related_symbols:
                # Extract the symbol before the pipe if present.
                symbol = sym.split("|")[0] if "|" in sym else sym
                processed.append(
                    {
                        "symbol": symbol.upper(),
                        "press_title": title,
                        "press_created": created,
                        "press_url": url,
                    }
                )
        else:
            # If no related_symbols provided, add a single row with empty symbol.
            processed.append({
                "symbol": "",
                "press_title": title,
                "press_created": created,
                "press_url": url
            })

    df = pd.DataFrame(processed)
    return df

@cached(ttl_seconds=1800)
def fetch_nasdaq_data() -> pd.DataFrame:
    """
    Fetch Nasdaq stock data from cache if available and not expired;
    otherwise, download new data and save it to a local cache file.
    Refreshes the cookie before reaching the Nasdaq API.
    """
    nasdaq_stock_api = "https://api.nasdaq.com/api/screener/stocks?tableonly=false&download=true"
    json_data = fetch_nasdaq_api(nasdaq_stock_api)
    rows = json_data.get("data", {}).get("rows", [])
    df = pd.DataFrame(rows)
    # Convert marketCap to numeric (handle commas or dollar signs if needed)
    df["marketCap"] = pd.to_numeric(df["marketCap"], errors="coerce")
    return df

@cached(ttl_seconds=DAY_TTL)
def fetch_nasdaq_earning_calls() -> pd.DataFrame:
    """
    Fetch Nasdaq earnings calls for the upcoming week and return structured data
    for better sorting and prioritization in trading strategies.

    Returns a DataFrame containing earnings call information with both:
    1. Individual fields for algorithmic sorting/filtering
    2. A formatted 'next_earning_call' text field for display purposes
    https://api.nasdaq.com/api/calendar/earnings?date=YYYY-MM-DD

    Generates calls for the upcoming week dates, parses the results, and returns a DataFrame.
    Example of API return:
    {
        "data": {
            "asOf": "Mon, Feb 24, 2025",
            "headers": { ... },
            "rows": [
                {
                    "lastYearRptDt": "2/26/2024",
                    "lastYearEPS": "$1.18",
                    "time": "time-after-hours",
                    "symbol": "OKE",
                    "name": "ONEOK, Inc.",
                    "marketCap": "$57,618,086,758",
                    "fiscalQuarterEnding": "Dec/2024",
                    "epsForecast": "$1.45",
                    "noOfEsts": "4"
                },
                ...
            ]
        }
    }
    """
    all_rows = []
    # Loop for upcoming 7 days
    for i in range(7):
        current_date = datetime.now() + timedelta(days=i)
        date_str = current_date.strftime("%Y-%m-%d")
        earnings_url = f"https://api.nasdaq.com/api/calendar/earnings?date={date_str}"
        try:
            json_data = fetch_nasdaq_api(earnings_url)
        except Exception as e:
            logger.error(f"[fetch_nasdaq_earning_calls] Error fetching earnings for {date_str}: {e}")
            continue

        data = json_data.get("data", {})
        if not data:
            continue

        rows = data.get("rows") or []
        # Add the queried date to each row
        for row in rows:
            row["callDate"] = date_str
        all_rows.extend(rows)

    df = pd.DataFrame(all_rows)

    if df.empty:
        return df

    try:
        # Convert callDate to datetime for easier sorting/comparison
        df["earnings_date"] = pd.to_datetime(df["callDate"])

        # Calculate days until earnings (for sorting)
        df["days_to_earnings"] = (df["earnings_date"] - pd.Timestamp.now()).dt.days

        # Create the human-readable next_earning_call string
        mapping = [
            ("callDate", "callDate"),
            ("lastYearRptDt", "lastYearReportDate"),
            ("lastYearEPS", "lastYearEPS"),
            ("time", "reportTime"),
            ("fiscalQuarterEnding", "fiscalQuarterEnding"),
            ("epsForecast", "epsForecast"),
            ("noOfEsts", "numberOfEstimates"),
        ]
        df["next_earning_call"] = df.apply(
            lambda row: ", ".join(
                f"{new_key}: {row[old_key]}"
                for old_key, new_key in mapping
                if old_key in row and pd.notnull(row[old_key])
            ),
            axis=1,
        )

        # Return only the necessary columns
        return df[["symbol", "next_earning_call", "days_to_earnings"]]

    except Exception as e:
        logger.error(f"[fetch_nasdaq_earning_calls] Error processing earnings data: {e}")
        # In case of errors, still try to return the minimal data
        if "callDate" in df.columns and "symbol" in df.columns:
            df["next_earning_call"] = df.apply(
                lambda row: f"callDate: {row['callDate']}", axis=1
            )
            df["days_to_earnings"] = None
            return df[["symbol", "next_earning_call", "days_to_earnings"]]
        return pd.DataFrame(columns=["symbol", "next_earning_call", "days_to_earnings"])

def correlate_stocks_with_news() -> pd.DataFrame:
    """
    Fetch Nasdaq stock data and press releases, then correlate the two datasets.
    """
    stock_data = fetch_nasdaq_data()
    press_releases = fetch_nasdaq_press_release()
    news = fetch_nasdaq_news()
    earning_calls = fetch_nasdaq_earning_calls()
    # Perform outer merges to get all rows from each source
    merged_all = pd.merge(stock_data, press_releases, on="symbol", how="outer")
    merged_all = pd.merge(merged_all, news, on="symbol", how="outer")
    merged_all = pd.merge(merged_all, earning_calls, on="symbol", how="outer")

    # Drop rows that don't have any news or press release information.
    # Assumes that 'news_title' comes from news and 'press_title' comes from press releases
    merged_all = merged_all.dropna(subset=["news_title", "press_title", "next_earning_call"], how="all")

    # Parse the created dates using the provided format and filter rows
    merged_all["news_created_dt"] = pd.to_datetime(
        merged_all["news_created"], format="%b %d, %Y", errors="coerce"
    )
    merged_all["press_created_dt"] = pd.to_datetime(
        merged_all["press_created"], format="%b %d, %Y", errors="coerce"
    )

    today = datetime.now().date()
    yesterday = today - timedelta(days=1)

    mask = (
        (merged_all["news_created_dt"].dt.date == today)
        | (merged_all["news_created_dt"].dt.date == yesterday)
        | (merged_all["press_created_dt"].dt.date == today)
        | (merged_all["press_created_dt"].dt.date == yesterday)
    )

    merged_all = merged_all[mask].copy()

    # Optionally, drop the helper datetime columns
    merged_all.drop(columns=["news_created_dt", "press_created_dt"], inplace=True)

    return merged_all

def main():
    """
    Main method to test StockAnalysisTool.
    It randomly selects 4 stocks that fit the small-cap criteria and
    generates markdown documents with the analysis.
    """
    # Fetch full Nasdaq data with caching
    df = correlate_stocks_with_news()

    # Randomly sample 4 stocks (or less if not enough stocks)
    sample_size = min(4, len(df))
    sampled_stocks = df.sample(n=sample_size)

if __name__ == "__main__":
    load_dotenv(".env")
    symbol = "ASTS"
    # main()
    # sec_filings = fetch_sec_filings(symbol)
    # insider_trading_info = fetch_insider_trading(symbol)
    # institutional_holdings_info = fetch_institutional_holdings(symbol)
    # print(institutional_holdings_info)
    # print(insider_trading_info)
    # short_interest_info = fetch_short_interest(symbol)
    # print(short_interest_info)
    # revenue_earnings_info = fetch_revenue_earnings(symbol)
    # print(revenue_earnings_info)
    # print(fetch_stock_press_releases(symbol))
    # print(fetch_stock_news(symbol))
    df = correlate_stocks_with_news()
    print(df)
