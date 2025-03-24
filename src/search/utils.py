import datetime
from typing import Dict
import pandas as pd

SEARCH_PROMPTS: Dict[str, Dict[str, str]] = {
    "real_time": {
        "q": (
            '("{stock_name}" OR "{stock_symbol}") ("performance" OR "forecast" OR "earnings" OR "market update") '
            "(site:bloomberg.com OR site:reuters.com OR site:ft.com OR site:cnbc.com OR site:businessinsider.com OR "
            "site:investors.com OR site:news.google.com OR site:yahoo.com OR site:msn.com/money)"
        ),
        "freshness": "Week",  # Last week.
    },
    "regulatory": {
        "q": (
            '("{stock_name}") ("SEC filing" OR "regulatory filing" OR "government report" OR "EDGAR") '
            "(site:sec.gov OR site:investor.gov OR site:reuters.com OR site:bloomberg.com OR site:wsj.com OR site:govinfo.gov)"
        ),
        "freshness": "Month",  # Last month.
    },
    "industry_analysis": {
        "q": (
            '("{industry}" OR "{sector}") ("industry analysis" OR "growth trends" OR "market outlook" OR "market analysis") '
            "(site:forbes.com OR site:investopedia.com OR site:bloomberg.com OR site:financialtimes.com OR "
            "site:marketwatch.com OR site:cnbc.com OR site:marketbeat.com OR site:msn.com/money)"
        ),
        "freshness": "Month",  # Last month.
    },
    "social_sentiment": {
        "q": (
            '("{stock_name}" OR "{stock_symbol}") ("sentiment" OR "social trends" OR "public opinion" OR "investor sentiment") '
            "(site:twitter.com OR site:reddit.com OR site:stocktwits.com OR site:google.com/news OR site:yahoo.com)"
        ),
        "freshness": "Week",  # Last week.
    },
    "historical_performance": {
        "q": (
            '("{stock_name}" OR "{stock_symbol}") ("historical performance" OR "stock price" OR "price history") '
            "(site:yahoo.com OR site:investing.com OR site:marketwatch.com OR site:google.com/finance)"
        ),
        "freshness": "{past_6_months}",
    },
    "alternative_data": {
        "q": (
            '("{stock_name}") ("sustainability" OR "ESG" OR "alternative data" OR "corporate responsibility" '
            'OR "social responsibility") '
            "(site:wsj.com OR site:forbes.com OR site:reuters.com OR site:bloomberg.com OR site:sustainalytics.com)"
        ),
        "freshness": "{past_6_months}",
    },
}


def fill_template(params: object, stock: pd.Series) -> str:
    """
    Replace placeholders in the template with values from the stock series and current dates.
    """
    current_date = datetime.datetime.now().strftime("%Y-%m-%d")
    past_date = (datetime.datetime.now() - datetime.timedelta(days=365)).strftime(
        "%Y-%m-%d"
    )
    recent_date = (datetime.datetime.now() - datetime.timedelta(days=30)).strftime(
        "%Y-%m-%d"
    )
    past5years = (datetime.datetime.now() - datetime.timedelta(days=365 * 5)).strftime(
        "%Y-%m-%d"
    )
    past_6_months = (datetime.datetime.now() - datetime.timedelta(days=180)).strftime(
        "%Y-%m-%d"
    )
    template = params.get("q", "")
    freshness = params.get("freshness", "")
    template_filled = template.format(
        stock_name=stock.get("name", ""),
        stock_symbol=stock.get("symbol", ""),
        country=stock.get("country", "us").lower(),
        sector=stock.get("sector", ""),
        industry=stock.get("industry", ""),
        ipo_year=stock.get("ipoyear", "2000"),
        current_date=current_date,
        past_date=past_date,
        recent_date=recent_date,
        past5years=past5years,
        past_6_months=past_6_months,
    )
    freshness_filled = freshness.format(
        current_date=current_date,
        past_date=past_date,
        recent_date=recent_date,
        past5years=past5years,
        past_6_months=past_6_months,
    )
    params["q"] = template_filled
    params["freshness"] = freshness_filled
    return params
