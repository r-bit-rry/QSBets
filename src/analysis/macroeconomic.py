import os
from dotenv import load_dotenv
from fredapi import Fred
from datetime import datetime, timedelta
import requests
from trafilatura import extract
import json
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from storage.cache import cached, DAY_TTL
from logger import get_logger

logger = get_logger(__name__)

# You would need to get a free API key from https://fred.stlouisfed.org/docs/api/api_key.html
load_dotenv(".env")
api_key = os.getenv("FRED_API_KEY")
fred = Fred(api_key=api_key)

@cached(ttl_seconds=DAY_TTL)
def fetch_macroeconomic_data():
    """
    Fetches key macroeconomic indicators from FRED and processes them
    to provide market context for stock analysis.
    
    Returns a dict with concise, relevant macroeconomic data.
    """
    # Get dates for calculations
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365*2)  # 2 years of data

    # Dictionary to store our indicators
    macro_data = {}

    # Interest rates
    try:
        # Federal Funds Rate (current)
        fed_funds = fred.get_series('FEDFUNDS', end_date - timedelta(days=40), end_date)
        macro_data['fed_funds_rate'] = round(fed_funds.iloc[-1], 2)

        # 10-Year Treasury Rate
        treasury_10y = fred.get_series('DGS10', end_date - timedelta(days=7), end_date)
        macro_data['treasury_10y'] = round(treasury_10y.iloc[-1], 2)

        # 2-Year Treasury Rate (for yield curve)
        treasury_2y = fred.get_series('DGS2', end_date - timedelta(days=7), end_date)
        macro_data['treasury_2y'] = round(treasury_2y.iloc[-1], 2)

        # Yield curve (2y-10y spread, negative indicates potential recession)
        macro_data['yield_curve'] = round(macro_data['treasury_10y'] - macro_data['treasury_2y'], 2)
    except Exception as e:
        logger.error(f"Error fetching interest rates: {e}")

    # Inflation
    try:
        # CPI Annual Rate
        cpi = fred.get_series('CPIAUCSL', start_date, end_date)
        cpi_yoy = 100 * (cpi.iloc[-1] - cpi.iloc[-13]) / cpi.iloc[-13]
        macro_data['inflation_rate'] = round(cpi_yoy, 2)

        # Core CPI (excluding food and energy)
        core_cpi = fred.get_series('CPILFESL', start_date, end_date)
        core_cpi_yoy = 100 * (core_cpi.iloc[-1] - core_cpi.iloc[-13]) / core_cpi.iloc[-13]
        macro_data['core_inflation'] = round(core_cpi_yoy, 2)
    except Exception as e:
        logger.error(f"Error fetching inflation data: {e}")

    # Debt Cycle Position Indicators
    try:
        # Total Public Debt to GDP
        public_debt = fred.get_series('GFDEGDQ188S', start_date, end_date)
        macro_data['public_debt_to_gdp'] = round(public_debt.iloc[-1], 2)

        # Household Debt Service Ratio
        household_dsr = fred.get_series('TDSP', start_date, end_date)
        macro_data['household_debt_service_ratio'] = round(household_dsr.iloc[-1], 2)

        # Corporate Debt to GDP
        corp_debt = fred.get_series('NCBCMDPMVCE', start_date, end_date)
        gdp = fred.get_series('GDP', start_date, end_date)

        # Find closest dates since they might not align perfectly
        last_debt = corp_debt.iloc[-1]
        last_gdp = gdp.iloc[-1]
        macro_data['corporate_debt_to_gdp'] = round(100 * last_debt / last_gdp, 2)

        # Calculate where we are in debt cycle (simplified)
        # High ratio + high rates = late cycle, Low ratio + low rates = early cycle
        debt_cycle_score = macro_data['public_debt_to_gdp'] / 100 + macro_data['fed_funds_rate'] / 5

        if debt_cycle_score > 1.5:
            debt_cycle = "Late Cycle (High Debt, High Rates)"
        elif debt_cycle_score > 1.2:
            debt_cycle = "Mid-Late Cycle"
        elif debt_cycle_score > 0.8:
            debt_cycle = "Mid Cycle"
        else:
            debt_cycle = "Early Cycle (Low Debt, Low Rates)"

        macro_data['debt_cycle_position'] = debt_cycle
    except Exception as e:
        logger.error(f"Error calculating debt cycle position: {e}")

    # Liquidity Indicators
    try:
        # M2 Money Supply Growth Rate
        m2 = fred.get_series("M2SL", start_date, end_date)

        # Check if we have enough data points for a year-over-year comparison
        if len(m2) >= 53:
            m2_yoy = 100 * (m2.iloc[-1] - m2.iloc[-53]) / m2.iloc[-53]  # Weekly data
        else:
            # Alternative calculation based on available data points
            # If we have at least 2 points, calculate percentage change from earliest to latest
            if len(m2) >= 2:
                m2_yoy = 100 * (m2.iloc[-1] - m2.iloc[0]) / m2.iloc[0]
            else:
                m2_yoy = 0

        macro_data["m2_growth"] = round(m2_yoy, 2)

        # Total Fed Assets (proxy for QE/QT)
        fed_assets = fred.get_series("WALCL", start_date, end_date)

        # Check if we have enough data points for a year-over-year comparison
        if len(fed_assets) >= 53:
            fed_assets_change = (
                100 * (fed_assets.iloc[-1] - fed_assets.iloc[-53]) / fed_assets.iloc[-53]
            )
        else:
            # Alternative calculation based on available data points
            # If we have at least 2 points, calculate percentage change from earliest to latest
            if len(fed_assets) >= 2:
                fed_assets_change = (
                    100 * (fed_assets.iloc[-1] - fed_assets.iloc[0]) / fed_assets.iloc[0]
                )
            else:
                fed_assets_change = 0

        macro_data["fed_balance_sheet_change"] = round(fed_assets_change, 2)

        # Determine liquidity condition
        if macro_data["m2_growth"] > 5 and macro_data["fed_balance_sheet_change"] > 0:
            liquidity = "Expanding (Supportive)"
        elif macro_data["m2_growth"] < 0 and macro_data["fed_balance_sheet_change"] < 0:
            liquidity = "Contracting (Restrictive)"
        else:
            liquidity = "Neutral"

        macro_data["liquidity_conditions"] = liquidity
    except Exception as e:
        logger.error(f"Error calculating liquidity indicators: {e}")
        # Set default values if calculation fails
        macro_data["m2_growth"] = "N/A"
        macro_data["fed_balance_sheet_change"] = "N/A"
        macro_data["liquidity_conditions"] = "Unknown (data unavailable)"

    # GDP Growth
    try:
        gdp_growth = fred.get_series('A191RL1Q225SBEA', start_date, end_date)
        macro_data['gdp_growth'] = round(gdp_growth.iloc[-1], 2)
    except Exception as e:
        logger.error(f"Error fetching GDP data: {e}")

    return macro_data

def fetch_market_sentiment():
    # FRED series IDs
    sentiment_series = {
        "VIX": "VIXCLS",               # CBOE Volatility Index
        "Financial_Stress": "STLFSI4",   # St. Louis Fed Financial Stress Index  
        "Risk_Premium": "THREEFYTP10"   # Treasury Term Premium
    }
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365*2)  # 2 years of data
    # Fetch and process each series
    sentiment_data = {}
    for name, series_id in sentiment_series.items():
        data = fred.get_series(series_id, start_date, end_date)
        if len(data) > 0:
            sentiment_data[name] = data.iloc[-1]
    
    return sentiment_data

def fetch_credit_conditions():
    credit_series = {
        "Commercial_Loan_Rate": "TERMCBPER24NS",
        "Bank_Lending_Standards": "DRTSCILM",
        "High_Yield_Spreads": "BAMLH0A0HYM2"
    }
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365*2)  # 2 years of data
    credit_data = {}
    for name, series_id in credit_series.items():
        try:
            data = fred.get_series(series_id, start_date, end_date)
            if len(data) > 0:
                credit_data[name] = data.iloc[-1]
                
                # Also calculate change from 3 months ago
                if len(data) >= 3:
                    change = data.iloc[-1] - data.iloc[-3]
                    credit_data[f"{name}_3M_Change"] = round(change, 2)
        except Exception:
            pass
    
    return credit_data

def fetch_valuation_metrics():
    """Calculate key market valuation metrics using available FRED data."""
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365*5)  # 5 years for historical context
    valuation_data = {}
    
    try:
        # 1. S&P 500 P/E Ratio
        # Get S&P 500 index
        sp500 = fred.get_series('SP500', end_date - timedelta(days=30), end_date)
        # Get S&P 500 earnings (quarterly data)
        sp_earnings = fred.get_series('CPIAUCSL', start_date, end_date)
        # Estimate earnings from Corporate Profits
        corp_profits = fred.get_series('CP', start_date, end_date)
        
        if len(sp500) > 0 and len(corp_profits) > 0:
            # Use latest values
            latest_price = sp500.iloc[-1]
            latest_earnings = corp_profits.iloc[-1] * 0.04  # Estimated S&P 500 earnings as fraction of corporate profits
            pe_ratio = latest_price / latest_earnings
            valuation_data["SP500_PE_Ratio"] = round(pe_ratio, 2)
            
            # Calculate 5-year average P/E
            five_yr_avg_pe = sp500.mean() / (corp_profits.mean() * 0.04)
            pct_to_avg = 100 * (pe_ratio - five_yr_avg_pe) / five_yr_avg_pe
            valuation_data["SP500_PE_Ratio_vs_5yr_avg"] = f"{round(pct_to_avg, 2)}%"
        
        # 2. S&P 500 Dividend Yield
        # Get dividend yield data directly (or calculate from dividends and prices)
        try:
            # Try to get dividend data 
            dividends = fred.get_series('DIVIDEND', start_date, end_date)
            if len(dividends) > 0 and len(sp500) > 0:
                latest_div = dividends.iloc[-1]
                latest_price = sp500.iloc[-1]
                div_yield = (latest_div * 4 / latest_price) * 100  # Annualized and as percentage
                valuation_data["SP500_Dividend_Yield"] = round(div_yield, 2)
                
                # Calculate 5-year average dividend yield
                five_yr_avg_yield = (dividends.mean() * 4 / sp500.mean()) * 100
                pct_to_avg = 100 * (div_yield - five_yr_avg_yield) / five_yr_avg_yield
                valuation_data["SP500_Dividend_Yield_vs_5yr_avg"] = f"{round(pct_to_avg, 2)}%"
        except Exception:
            # If DIVIDEND series not found, estimate with alternative method
            valuation_data["SP500_Dividend_Yield"] = 1.5  # Example fallback
        
        # 3. Market Cap to GDP (Buffett Indicator)
        #TODO: fred removed market cap, wilshire 5000 and other indexes, need another source
    except Exception as e:
        logger.error(f"Error calculating valuation metrics: {e}")
        
    return valuation_data

def fetch_recession_indicators():
    # Key recession indicators
    recession_series = {
        "Yield_Curve_10Y_2Y": ["DGS10", "DGS2"],  # 10Y-2Y Treasury spread
        "Leading_Index": "USSLIND",               # Leading Economic Index
        "Recession_Prob": "RECPROUSM156N"         # Fed model recession probability
    }
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365*2)  # 2 years of data
    recession_data = {}
    
    # Handle yield curve specially
    try:
        ten_yr = fred.get_series(recession_series["Yield_Curve_10Y_2Y"][0], start_date, end_date)
        two_yr = fred.get_series(recession_series["Yield_Curve_10Y_2Y"][1], start_date, end_date)
        
        if len(ten_yr) > 0 and len(two_yr) > 0:
            spread = ten_yr.iloc[-1] - two_yr.iloc[-1]
            recession_data["Yield_Curve_Spread"] = round(spread, 2)
            recession_data["Yield_Curve_Inverted"] = str(spread < 0)
    except Exception:
        pass
    
    # Handle other indicators
    for name, series_id in recession_series.items():
        if isinstance(series_id, str):  # Skip the yield curve which was handled above
            try:
                data = fred.get_series(series_id, start_date, end_date)
                if len(data) > 0:
                    recession_data[name] = round(data.iloc[-1], 2)
            except Exception:
                pass
    
    return recession_data

@cached(ttl_seconds=DAY_TTL)
def fallback_macro_data():
    """
    Fallback method to scrape macroeconomic data from the web
    using trafilatura if the FRED API is not available.
    """
    macro_data = {}
    
    # Fetch current Fed Funds Rate from Fed website
    try:
        url = "https://www.federalreserve.gov/releases/h15/"
        response = requests.get(url)
        if response.status_code == 200:
            content = extract(response.text)
            # Simple parsing to find federal funds rate
            if content and "Federal funds" in content:
                lines = content.split('\n')
                for i, line in enumerate(lines):
                    if "Federal funds" in line and i + 1 < len(lines):
                        rate_text = lines[i+1].strip()
                        try:
                            rate = float(rate_text.split()[0])
                            macro_data['fed_funds_rate'] = rate
                        except:
                            pass
    except Exception as e:
        logger.error(f"Error in fallback Fed funds rate: {e}")
    
    # Fetch inflation data from BLS
    try:
        url = "https://www.bls.gov/news.release/cpi.nr0.htm"
        response = requests.get(url)
        if response.status_code == 200:
            content = extract(response.text)
            # Look for "percent over the last 12 months"
            if content:
                idx = content.find("percent over the last 12 months")
                if idx > 0:
                    text_before = content[max(0, idx-30):idx]
                    # Extract number before "percent"
                    import re
                    matches = re.findall(r"(\d+\.\d+)\s*percent", text_before)
                    if matches:
                        macro_data['inflation_rate'] = float(matches[0])
    except Exception as e:
        logger.error(f"Error in fallback inflation data: {e}")
    
    return macro_data

def get_macroeconomic_context() -> dict:
    """
    Main function to get macroeconomic data for stock analysis.
    Tries the FRED API first, then falls back to web scraping if needed.
    
    Returns a formatted string with key macro indicators.
    """
    try:
        macro_data = fetch_macroeconomic_data()
    except Exception as e:
        logger.error(f"Error with FRED API, using fallback: {e}")
        macro_data = fallback_macro_data()
    
    # Format the data for inclusion in stock analysis
    summary = {
        "interest_rates": {
            "fed_funds": macro_data.get('fed_funds_rate', 'N/A'),
            "10y_treasury": macro_data.get('treasury_10y', 'N/A'),
            "yield_curve": macro_data.get('yield_curve', 'N/A')
        },
        "inflation": {
            "cpi_annual": macro_data.get('inflation_rate', 'N/A'),
            "core_cpi": macro_data.get('core_inflation', 'N/A')
        },
        "debt_cycle": {
            "position": macro_data.get('debt_cycle_position', 'N/A'),
            "public_debt_to_gdp": macro_data.get('public_debt_to_gdp', 'N/A'),
            "household_debt_service_ratio": macro_data.get('household_debt_service_ratio', 'N/A')
        },
        "liquidity": {
            "conditions": macro_data.get('liquidity_conditions', 'N/A'),
            "m2_growth": macro_data.get('m2_growth', 'N/A'),
            "fed_balance_sheet_change": macro_data.get('fed_balance_sheet_change', 'N/A')
        },
        "economy": {
            "gdp_growth": macro_data.get('gdp_growth', 'N/A')
        }
    }
    
    return summary

@cached(ttl_seconds=DAY_TTL)
def get_all_macro_data():
    """
    Function to convert the macroeconomic data to YAML format.
    """
    all_data = {
        "macroeconomic": get_macroeconomic_context(),
        "market_sentiment": fetch_market_sentiment(),
        "credit_conditions": fetch_credit_conditions(),
        "valuation_metrics": fetch_valuation_metrics(),
        "recession_indicators": fetch_recession_indicators()
    }
    return all_data

if __name__ == "__main__":
    macro_summary = get_macroeconomic_context()
    logger.info(json.dumps(macro_summary, indent=2))

    logger.info("\nMarket Sentiment:")
    sentiment_data = fetch_market_sentiment()
    logger.info(json.dumps(sentiment_data, indent=2))
    logger.info("\nCredit Conditions:")
    credit_data = fetch_credit_conditions()
    logger.info(json.dumps(credit_data, indent=2))
    logger.info("\nValuation Metrics:")
    valuation_data = fetch_valuation_metrics()
    logger.info(json.dumps(valuation_data, indent=2))
    logger.info("\nRecession Indicators:")
    recession_data = fetch_recession_indicators()
    logger.info(json.dumps(recession_data, indent=2))


