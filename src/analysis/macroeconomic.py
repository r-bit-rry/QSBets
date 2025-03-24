import os
from dotenv import load_dotenv
from fredapi import Fred
from datetime import datetime, timedelta
import requests
from trafilatura import extract
import json
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
        "Financial_Stress": "STLFSI",   # St. Louis Fed Financial Stress Index  
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

def fetch_sector_indicators():
    sector_series = {
        "Manufacturing_PMI": "NAPM",        # ISM Manufacturing PMI
        "Services_PMI": "NMFCI",            # ISM Services PMI 
        "Industrial_Production": "INDPRO",   # Industrial Production Index
        "Retail_Sales": "RSXFS",            # Retail Sales
        "Housing_Starts": "HOUST"           # Housing Starts
    }
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365*2)  # 2 years of data
    # Calculate YoY or MoM changes based on industry benchmarks
    sector_data = {}
    for name, series_id in sector_series.items():
        try:
            data = fred.get_series(series_id, start_date, end_date)
            if len(data) >= 12:
                yoy_change = 100 * (data.iloc[-1] - data.iloc[-13]) / data.iloc[-13]
                sector_data[f"{name}_YoY"] = round(yoy_change, 2)
            elif len(data) > 1:
                mom_change = 100 * (data.iloc[-1] - data.iloc[-2]) / data.iloc[-2]
                sector_data[f"{name}_MoM"] = round(mom_change, 2)
        except Exception as e:
            logger.error(f"Error fetching {name}: {e}")
    
    return sector_data

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
    valuation_series = {
        "SP500_PE_Ratio": "SP500_PE_RATIO_MONTH",
        "SP500_Dividend_Yield": "SP500_DIV_YIELD_MONTH",
        "Market_Cap_to_GDP": "DDDM01USA156NWDB"  # Buffett Indicator
    }
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365*2)  # 2 years of data
    valuation_data = {}
    for name, series_id in valuation_series.items():
        try:
            data = fred.get_series(series_id, start_date, end_date)
            if len(data) > 0:
                current = data.iloc[-1]
                valuation_data[name] = round(current, 2)
                
                # Compare to 5-year average for context
                if len(data) >= 60:
                    five_yr_avg = data.iloc[-60:].mean()
                    pct_to_avg = 100 * (current - five_yr_avg) / five_yr_avg
                    valuation_data[f"{name}_vs_5yr_avg"] = f"{round(pct_to_avg, 2)}%"
        except Exception:
            pass
    
    return valuation_data

def fetch_valuation_metrics():
    valuation_series = {
        "SP500_PE_Ratio": "SP500_PE_RATIO_MONTH",
        "SP500_Dividend_Yield": "SP500_DIV_YIELD_MONTH",
        "Market_Cap_to_GDP": "DDDM01USA156NWDB"  # Buffett Indicator
    }
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365*2)  # 2 years of data
    valuation_data = {}
    for name, series_id in valuation_series.items():
        try:
            data = fred.get_series(series_id, start_date, end_date)
            if len(data) > 0:
                current = data.iloc[-1]
                valuation_data[name] = round(current, 2)
                
                # Compare to 5-year average for context
                if len(data) >= 60:
                    five_yr_avg = data.iloc[-60:].mean()
                    pct_to_avg = 100 * (current - five_yr_avg) / five_yr_avg
                    valuation_data[f"{name}_vs_5yr_avg"] = f"{round(pct_to_avg, 2)}%"
        except Exception:
            pass
    
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
            recession_data["Yield_Curve_Inverted"] = spread < 0
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

if __name__ == "__main__":
    macro_summary = get_macroeconomic_context()
    print(json.dumps(macro_summary, indent=2))

    print("\nMarket Sentiment:")
    sentiment_data = fetch_market_sentiment()
    print(json.dumps(sentiment_data, indent=2))
    print("\nSector Indicators:")
    sector_data = fetch_sector_indicators()
    print(json.dumps(sector_data, indent=2))
    print("\nCredit Conditions:")
    credit_data = fetch_credit_conditions()
    print(json.dumps(credit_data, indent=2))
    print("\nValuation Metrics:")
    valuation_data = fetch_valuation_metrics()
    print(json.dumps(valuation_data, indent=2))
    print("\nRecession Indicators:")
    recession_data = fetch_recession_indicators()
    print(json.dumps(recession_data, indent=2))


