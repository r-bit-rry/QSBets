"""StockTwits API integration for fetching trending stocks data."""
import os
import requests
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from logger import get_logger
from storage.cache import HOURS2_TTL, cached
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

# Configure retries
retry_strategy = Retry(
    total=3,  # number of retries
    backoff_factor=1,  # wait 1, 2, 4 seconds between retries
    status_forcelist=[500, 502, 503, 504],  # HTTP status codes to retry on
)
adapter = HTTPAdapter(max_retries=retry_strategy)
http = requests.Session()
http.mount("https://", adapter)

logger = get_logger(__name__)

STOCKTWITS_API_URL = "https://api.stocktwits.com/api/2/trending/symbols_enhanced.json"
STOCKTWITS_HEADERS = {
    "authority": "api.stocktwits.com",
    "accept": "application/json",
    "accept-encoding": "gzip, deflate, br",
    "accept-language": "en-GB,en;q=0.9,en-US;q=0.8",
    "cache-control": "max-age=0",
    "dnt": "1",
    "origin": "https://stocktwits.com",
    "referer": "https://stocktwits.com/",
    "sec-ch-ua": '"Microsoft Edge";v="135", "Not-A.Brand";v="8", "Chromium";v="135"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"macOS"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-site",
    "user-agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/135.0.0.0 Safari/537.36 Edg/135.0.0.0"
}

last_cookie_refresh_time = None

def refresh_stocktwits_auth() -> bool:
    """
    Uses Selenium to open StockTwits homepage and retrieve fresh cookies and auth token.
    Handles critical authentication tokens and cookies required for API access.
    """
    global last_cookie_refresh_time
    if (last_cookie_refresh_time is None or 
        (datetime.now() - last_cookie_refresh_time).total_seconds() > 1800):
        options = Options()
        options.add_argument("--headless")
        options.add_argument("--disable-gpu")
        driver = webdriver.Chrome(options=options)
        try:
            driver.get("https://stocktwits.com")
            time.sleep(5)  # Wait for page to load and cookies to be set
            cookies = driver.get_cookies()
            cookie_str = "; ".join(
                f"{cookie['name']}={cookie['value']}" 
                for cookie in cookies 
                if cookie['name'] in [
                    'auto_log_in', 'access_token', 'userId', 
                    'timezone', '_st_se', '_cfuvid'
                ]
            )
            STOCKTWITS_HEADERS["cookie"] = cookie_str
            # Test the auth by making a simple API request
            test_response = http.get(
                STOCKTWITS_API_URL,
                headers=STOCKTWITS_HEADERS,
                params={"limit": "1"},
                timeout=10
            )
            test_response.raise_for_status()
            last_cookie_refresh_time = datetime.now()
            logger.info("Successfully refreshed StockTwits authentication")
            return True
        except Exception as e:
            logger.error(f"Error refreshing StockTwits auth: {e}")
            return False
        finally:
            driver.quit()
    return True  # Already refreshed within timeframe

@cached(HOURS2_TTL)
def fetch_trending_stocks(limit: int = 100, max_retries: int = 2) -> List[Dict[str, Any]]:
    """
    Fetch trending stocks from StockTwits API, filtering for ETFs and Stocks only.
    
    Args:
        limit: Maximum number of trending symbols to fetch
        
    Returns:
        List of filtered trending stock data
    """
    try:
        # Refresh auth before making request
        if not refresh_stocktwits_auth():
            logger.error("Failed to refresh StockTwits authentication")
            return []
        
        params = {
            "class": "stocks",
            "limit": str(limit),  # API expects string values
            "payloads": "prices"
        }
        
        response = http.get(
            STOCKTWITS_API_URL, 
            headers=STOCKTWITS_HEADERS, 
            params=params,
            timeout=10  # Add timeout for better error handling
        )
        response.raise_for_status()
        
        data = response.json()
        
        if not data.get("symbols"):
            logger.warning("No trending symbols found in StockTwits response")
            return []
            
        # Filter for ETFs and Stocks only
        filtered_symbols = []
        for symbol in data["symbols"]:
            instrument_class = symbol.get("instrument_class", "").lower()
            if instrument_class in ["stock", "exchangetradedfund"]:
                # Clean and structure the data
                cleaned_symbol = {
                    "symbol": symbol["symbol"],
                    "title": symbol.get("title", ""),
                    "trending_score": symbol.get("trending_score", 0),
                    "trend_rank": symbol.get("rank", 0),
                    "watchlist_count": symbol.get("watchlist_count", 0),
                    "instrument_class": instrument_class,
                    "updated_at": datetime.utcnow().isoformat()
                }
                
                # Add price data if available
                price_data = symbol.get("price_data", {})
                if price_data:
                    cleaned_symbol.update({
                        "last_price": price_data.get("Last"),
                        "percent_change": price_data.get("PercentChange"),
                        "volume": price_data.get("Volume")
                    })
                
                # Add trending summary if available
                trends = symbol.get("trends", {})
                if trends and trends.get("summary"):
                    cleaned_symbol["trend_summary"] = trends["summary"]
                
                filtered_symbols.append(cleaned_symbol)
        
        logger.info(f"Retrieved {len(filtered_symbols)} trending stocks/ETFs from StockTwits")
        return filtered_symbols
        
    except requests.exceptions.Timeout:
        logger.error("Timeout while fetching trending stocks from StockTwits")
        return []
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 401:
            logger.error("Authentication failed - refreshing auth tokens")
            refresh_stocktwits_auth()
            return []
        logger.error(f"HTTP error fetching trending stocks: {str(e)}")
        return []
    except requests.RequestException as e:
        logger.error(f"Network error fetching trending stocks: {str(e)}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error processing StockTwits data: {str(e)}")
        return []


def test_auth():
    """Test the StockTwits authentication and API access."""
    logger.info("Testing StockTwits authentication...")
    
    if not refresh_stocktwits_auth():
        logger.error("Failed to establish initial authentication")
        return False
        
    try:
        trending = fetch_trending_stocks(limit=1)
        if trending:
            logger.info("Successfully retrieved trending stocks")
            logger.info(f"Sample data: {trending[0]}")
            return True
        else:
            logger.error("No data retrieved")
            return False
    except Exception as e:
        logger.error(f"Error testing authentication: {e}")
        return False

if __name__ == "__main__":
    # Test authentication and API access
    if test_auth():
        logger.info("Authentication test passed")
        
        # If auth test passes, fetch and display trending stocks
        trending = fetch_trending_stocks()
        logger.info(f"Retrieved {len(trending)} trending stocks")
        for stock in trending[:5]:  # Print first 5 stocks
            logger.info(f"Symbol: {stock['symbol']}")
            logger.info(f"Score: {stock['trending_score']}")
            logger.info(f"Class: {stock['instrument_class']}")
            logger.info("---")
    else:
        logger.error("Authentication test failed")
