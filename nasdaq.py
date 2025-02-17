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
import hashlib

# Add cache folder and ensure it exists
CACHE_FOLDER = "./cache"
if not os.path.exists(CACHE_FOLDER):
    os.makedirs(CACHE_FOLDER)
CACHE_FILE = os.path.join(CACHE_FOLDER, "nasdaq_cache.json")
CACHE_EXPIRY_MINUTES = 30

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
        print(f"[safe_parse_date] Error parsing '{date_str}': {e}")
        return None

def get_full_url(url: str) -> str:
    return "https://www.nasdaq.com" + url if url.startswith("/") else url

def safe_retrieve_page(url: str, format: str = "txt") -> str:
    try:
        return retrieve_nasdaq_page(url, format)
    except Exception as e:
        print(f"[safe_retrieve_page] Error retrieving {url}: {e}")
        return ""


# Helper function to convert URL to a safe cache filename using MD5
def url_to_cache_filename(url: str) -> str:
    hashed = hashlib.md5(url.encode("utf-8")).hexdigest()
    return os.path.join(CACHE_FOLDER, f"{hashed}.txt")

def retrieve_nasdaq_page(url: str, format: str = "txt") -> str:
    """
    Retrieve the content of a web page using trafilatura with caching.
    """
    refresh_nasdaq_cookie()
    cache_path = url_to_cache_filename(url)
    if os.path.exists(cache_path):
        with open(cache_path, "r", encoding="utf-8") as fp:
            return fp.read()
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
    with open(cache_path, "w", encoding="utf-8") as fp:
        fp.write(content)
    return content

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
    if (
        last_cookie_refresh_time is None
        or (datetime.now() - last_cookie_refresh_time).total_seconds()
        > 1800
    ):
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        driver = webdriver.Chrome(options=options)
        try:
            driver.get("https://www.nasdaq.com")
            # Wait for the page to fully load and cookies to be set.
            time.sleep(5)
            cookies = driver.get_cookies()
            # Convert cookies list into a single cookie header string.
            cookie_str = "; ".join(
                [f"{cookie['name']}={cookie['value']}"] for cookie in cookies
            )
            NASDAQ_HEADERS["cookie"] = cookie_str
            last_cookie_refresh_time = datetime.now()
        finally:
            driver.quit()


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
    rows = data.get("rows", [])

    one_week_ago = datetime.now() - timedelta(days=15)
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
    data = json_data.get("data", {})
    if data is None:
        return json.dumps({"error": "No data field in API response"}, indent=2)

    data = json_data.get("data")  # May be None!
    if not data:
        return json.dumps({"error": "No data field in API response"}, indent=2)

    revenue_table = data.get("revenueTable") or {}
    rows = revenue_table.get("rows") or []

    if not rows:
        return json.dumps({"error": "No rows in revenue table"}, indent=2)

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
        return json.dumps(
            {"error": "Error processing revenue rows", "detail": str(e)}, indent=2
        )

    # Keep only the last 6 quarters
    transposed_data = transposed_data[-6:]

    return json.dumps(transposed_data)

def fetch_short_interest(symbol: str) -> str:
    """
    Fetches short interest data for the given stock symbol from the Nasdaq API.
    https://api.nasdaq.com/api/quote/ASTS/short-interest?assetClass=stocks
    Removes unneeded information from the JSON to keep it as simple as possible for further analysis by LLM.
    Take only 2 most up to date rows.
    """
    short_interest_url = (
        f"https://api.nasdaq.com/api/quote/{symbol}/short-interest?assetClass=stocks"
    )
    json_data = fetch_nasdaq_api(short_interest_url)
    data = json_data.get("data", {})
    if data is None:
        return json.dumps([])

    # Extract relevant information
    short_interest_table = data.get("shortInterestTable") or {}
    rows = short_interest_table.get("rows") or []

    # Take only the 2 most recent rows
    recent_rows = rows[:4]

    # Format the extracted information as JSON
    short_interest_info = recent_rows

    return json.dumps(short_interest_info)


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
        return json.dumps({})

    # Extract relevant information
    ownership_summary = data.get("ownershipSummary", {})
    active_positions = data.get("activePositions", {}).get("rows", [])
    new_sold_out_positions = data.get("newSoldOutPositions", {}).get("rows", [])
    holdings_transactions = (
        data.get("holdingsTransactions", {}).get("table", {}).get("rows", [])
    )

    # Format the extracted information as JSON
    institutional_holdings_info = {
        "ownership_summary": ownership_summary,
        "active_positions": active_positions,
        "new_sold_out_positions": new_sold_out_positions,
        "holdings_transactions": holdings_transactions,
    }

    return json.dumps(institutional_holdings_info)


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
        return json.dumps({})

    # Extract relevant information
    number_of_trades = data.get("numberOfTrades", {}).get("rows", [])
    number_of_shares_traded = data.get("numberOfSharesTraded", {}).get("rows", [])
    transaction_table = (
        data.get("transactionTable", {}).get("table", {}).get("rows", [])
    )

    # Format the extracted information as JSON
    insider_trading_info = {
        "number_of_trades": number_of_trades,
        "number_of_shares_traded": number_of_shares_traded,
        "transaction_table": transaction_table,
    }

    return json.dumps(insider_trading_info)


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
        return json.dumps([])
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
                "formType": filing["formType"],
                "filed": filing["filed"],
                "period": filing.get("period", ""),
                "text": filing[
                    "filed"
                ],  # TODO: replace with actual text_content retrieval
            }
        )

    return json.dumps(filings_content)


def fetch_nasdaq_news() -> pd.DataFrame:
    """
    Fetch Nasdaq news from the API endpoint:
    https://www.nasdaq.com/api/news/topic/articlebysymbol?q=offset=0&limit=100&assetclass:stocks

    We construct a DataFrame containing a row for each related symbol, with:
      - symbol (extracted from each related_symbols element before the pipe '|'),
      - news_title,
      - news_created,
      - news_url (ensuring a full URL is provided).
    """
    news_api_url = "https://www.nasdaq.com/api/news/topic/articlebysymbol?q=offset=0&limit=1000&assetclass:stocks"
    json_data = fetch_nasdaq_api(news_api_url)
    data = json_data.get("data", {})
    if data is None:
        return pd.DataFrame()
    rows = data.get("rows", [])
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

def fetch_nasdaq_press_release() -> pd.DataFrame:
    """
    Fetch Nasdaq press releases from the API endpoint:
    https://www.nasdaq.com/api/news/topic/press_release?q=assetclass:stocks&limit=200

    We construct a dataframe containing a row for each related symbol, with:
      - symbol (extracted from each related_symbols element before the pipe '|'),
      - title,
      - created,
      - url (ensuring a full URL is provided).
    """
    press_release_url = (
        "https://www.nasdaq.com/api/news/topic/press_release?q=assetclass:stocks&limit=1000"
    )
    json_data = fetch_nasdaq_api(press_release_url)
    data = json_data.get("data", {})
    if data is None:
        return pd.DataFrame()
    rows = data.get("rows", [])
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

def fetch_nasdaq_data() -> pd.DataFrame:
    """
    Fetch Nasdaq stock data from cache if available and not expired;
    otherwise, download new data and save it to a local cache file.
    Refreshes the cookie before reaching the Nasdaq API.
    """
    use_cache = False
    nasdaq_stock_api = "https://api.nasdaq.com/api/screener/stocks?tableonly=false&download=true"
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as fp:
                cache = json.load(fp)
            timestamp = datetime.fromisoformat(cache.get("timestamp"))
            if (
                datetime.now() - timestamp
            ).total_seconds() < CACHE_EXPIRY_MINUTES * 60:
                use_cache = True
                rows = cache.get("rows", [])
                print(f"Loaded Nasdaq data from cache (timestamp: {timestamp}).")
            else:
                print("Cache expired. Fetching new Nasdaq data.")
        except Exception as e:
            print("Error reading cache:", e)
    if not use_cache:
        print("Fetching Nasdaq stock data from API...")
        NASDAQ_URL = "https://api.nasdaq.com/api/screener/stocks?tableonly=false&download=true"
        json_data = fetch_nasdaq_api(nasdaq_stock_api)
        rows = json_data["data"]["rows"]
        cache = {
            "timestamp": datetime.now().isoformat(),
            "rows": rows,
        }
        with open(CACHE_FILE, "w", encoding="utf-8") as fp:
            json.dump(cache, fp)
        print("Nasdaq data cached locally.")
    df = pd.DataFrame(rows)
    # Convert marketCap to numeric (handle commas or dollar signs if needed)
    df["marketCap"] = pd.to_numeric(df["marketCap"], errors="coerce")
    return df


def correlate_stocks_with_news() -> pd.DataFrame:
    """
    Fetch Nasdaq stock data and press releases, then correlate the two datasets.
    """
    stock_data = fetch_nasdaq_data()
    press_releases = fetch_nasdaq_press_release()
    news = fetch_nasdaq_news()
    # Perform outer merges to get all rows from each source
    merged_all = pd.merge(stock_data, press_releases, on="symbol", how="outer")
    merged_all = pd.merge(merged_all, news, on="symbol", how="outer")

    # Drop rows that don't have any news or press release information.
    # Assumes that 'news_title' comes from news and 'press_title' comes from press releases
    merged_all = merged_all.dropna(subset=["news_title", "press_title"], how="all")

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
    print(fetch_stock_news(symbol))
