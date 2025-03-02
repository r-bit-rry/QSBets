from datetime import datetime
from functools import partial
import json
import os
import time

from macroeconomic import get_macroeconomic_context
from social import fetch_stocks_sentiment
from summarize import azure_openai_summarize, ollama_summarize
from nasdaq import (
    fetch_historical_quotes,
    fetch_revenue_earnings,
    fetch_short_interest,
    fetch_institutional_holdings,
    fetch_insider_trading,
    fetch_description,
    fetch_sec_filings,
    fetch_nasdaq_data,
    fetch_stock_news,
    fetch_stock_press_releases,
)
from ta import fetch_technical_indicators

class Stock:
    def __init__(self, nasdaq_data):
        self.meta = nasdaq_data.to_dict()
        self.symbol = self.meta["symbol"]

    @staticmethod
    def process_meta(nasdaq_data, symbol):
        """
        Extract metadata for a specific symbol from nasdaq_data DataFrame

        Args:
            nasdaq_data: DataFrame containing data for multiple stocks
            symbol: Stock ticker symbol to extract

        Returns:
            Dictionary with metadata for the requested symbol
        """
        try:
            # Filter for the specific symbol and convert to dict
            symbol_data = nasdaq_data[nasdaq_data["symbol"] == symbol]
            if symbol_data.empty:
                print(f"Symbol {symbol} not found in nasdaq data")
                return {"symbol": symbol}
            return symbol_data.iloc[0]
        except Exception as e:
            print(f"Error processing metadata for {symbol}: {e}")
            return {"symbol": symbol}

    def make_json(self):
        """Optimized version to create more LLM-friendly JSON files with reduced tokens"""
        report = {}
        timings = {}
        start_total = time.time()

        # Add essential company information
        t_start = time.time()
        report["description"] = fetch_description(self.symbol)
        timings["description"] = time.time() - t_start

        # Clean and optimize metadata - use numeric types properly
        t_start = time.time()
        meta = dict(self.meta)
        # Convert string numbers to actual numeric types
        for field in ["marketCap", "volume", "netchange", "pctchange"]:
            if field in meta and meta[field] is not None:
                try:
                    # Remove $ and commas, then convert to appropriate numeric type
                    if isinstance(meta[field], str):
                        clean_value = (
                            meta[field].replace("$", "").replace(",", "").replace("%", "")
                        )
                        meta[field] = float(clean_value)
                except (ValueError, TypeError):
                    pass

        # Avoid duplicating news that will appear in dedicated sections
        if "news_titles" in meta:
            del meta["news_titles"]
        if "press_titles" in meta:
            del meta["press_titles"]

        report["meta"] = meta
        timings["metadata"] = time.time() - t_start

        # Technical indicators analysis
        t_start = time.time()
        technical_indicators = fetch_technical_indicators(self.symbol)
        report["technical_indicators"] = technical_indicators
        timings["technical_indicators"] = time.time() - t_start

        # Macroeconomic indicators
        t_start = time.time()
        macroeconomic_context = get_macroeconomic_context()
        report["macroeconomic_context"] = macroeconomic_context
        timings["macroeconomic_context"] = time.time() - t_start

        # Revenue and Earnings - ensure numeric values
        t_start = time.time()
        revenue_data = json.loads(fetch_revenue_earnings(self.symbol))
        for item in revenue_data:
            if isinstance(item, dict):  # Only process if item is a dict
                for key, value in item.items():
                    if key in ["revenue", "eps"]:
                        # Clean and convert financial metrics
                        if isinstance(value, str):
                            item[key] = self._clean_financial_metric(value)
        report["revenue_earnings"] = revenue_data
        timings["revenue_earnings"] = time.time() - t_start

        # Skip empty data sections
        t_start = time.time()
        short_interest = json.loads(fetch_short_interest(self.symbol))
        if short_interest and not all(len(item) == 0 for item in short_interest):
            report["short_interest"] = short_interest
        timings["short_interest"] = time.time() - t_start

        # Optimize institutional holdings - clean numeric data
        t_start = time.time()
        holdings_data = json.loads(fetch_institutional_holdings(self.symbol))
        report["institutional_holdings"] = self._optimize_institutional_holdings(
            holdings_data
        )
        timings["institutional_holdings"] = time.time() - t_start

        # Optimize insider trading - clean numeric data and standardize dates
        t_start = time.time()
        insider_data = json.loads(fetch_insider_trading(self.symbol))
        report["insider_trading"] = self._optimize_insider_trading(insider_data)
        timings["insider_trading"] = time.time() - t_start

        # Historical quotes - convert to numeric and standardize format
        t_start = time.time()
        historical_data = json.loads(fetch_historical_quotes(self.symbol, 5))
        report["historical_quotes"] = self._optimize_historical_quotes(historical_data)
        timings["historical_quotes"] = time.time() - t_start

        # SEC filings - keep only recent and relevant filings
        t_start = time.time()
        sec_filings = json.loads(fetch_sec_filings(self.symbol))
        report["sec_filings"] = sec_filings[:5]  # Limit to most recent 5 filings
        timings["sec_filings"] = time.time() - t_start

        # Social sentiment - only include if available
        t_start = time.time()
        reddit_wsb_sentiment = fetch_stocks_sentiment().get(self.symbol, {})
        if reddit_wsb_sentiment:
            report["reddit_wallstreetbets_sentiment"] = reddit_wsb_sentiment
        timings["reddit_wallstreetbets_sentiment"] = time.time() - t_start

        # News with optimized summaries - eliminate redundant fields
        t_start = time.time()
        news = fetch_stock_news(self.symbol)
        summarized_news = [
            self._optimize_news_item(item)
            for item in filter(
                lambda x: x.get("relevant_symbol", "") == self.symbol,
                [ollama_summarize(text=d) for d in news],
            )
        ]
        if summarized_news:
            report["news"] = summarized_news
        timings["news"] = time.time() - t_start

        # Press releases with optimized summaries
        t_start = time.time()
        press_releases = fetch_stock_press_releases(self.symbol)
        summarized_press = [
            self._optimize_news_item(item)
            for item in filter(
                lambda x: x.get("relevant_symbol", "") == self.symbol,
                [ollama_summarize(text=d) for d in press_releases],
            )
        ]
        if summarized_press:
            report["press_releases"] = summarized_press
        timings["press_releases"] = time.time() - t_start

        # Save JSON report (minified to conserve tokens)
        t_start = time.time()
        today = datetime.now().strftime("%Y-%m-%d")
        safe_name = "".join(
            c for c in self.meta["symbol"] if c.isalnum() or c in ("_", "-")
        )
        docs_folder = "analysis_docs"
        os.makedirs(docs_folder, exist_ok=True)
        file_name = f"{safe_name}_{today}.json"
        file_path = os.path.join(docs_folder, file_name)
        with open(file_path, "w", encoding="utf-8") as fp:
            fp.write(json.dumps(report, separators=(",", ":")))
        timings["save_file"] = time.time() - t_start

        # Calculate total time and log all timings
        total_time = time.time() - start_total
        timings["total"] = total_time

        # Print timing summary
        print(f"\n--- Performance Report for {self.symbol} ---")
        print(f"Total processing time: {total_time:.2f}s")

        # Sort timings by duration (descending)
        sorted_timings = sorted(
            [(k, v) for k, v in timings.items() if k != "total"],
            key=lambda x: x[1],
            reverse=True,
        )
        for name, duration in sorted_timings:
            print(f"  {name}: {duration:.2f}s ({(duration/total_time)*100:.1f}%)")

        return file_path

    def _clean_financial_metric(self, value):
        """Convert financial strings like "$2(m)" to numeric values"""
        if not value or not isinstance(value, str):
            return None

        # Remove $ and other non-numeric characters
        value = value.replace("$", "").replace(",", "")

        # Extract numeric part and multiplier
        multiplier = 1
        if "(m)" in value.lower():
            multiplier = 1000000
            value = value.replace("(m)", "").replace("(M)", "")
        elif "(b)" in value.lower():
            multiplier = 1000000000
            value = value.replace("(b)", "").replace("(B)", "")

        try:
            return float(value) * multiplier
        except ValueError:
            return value

    def _optimize_institutional_holdings(self, data):
        """Clean and structure institutional holdings data"""
        if not data:
            return {}

        result = {}

        # Clean ownership summary percentages and values
        if "ownership_summary" in data:
            for category, item in data["ownership_summary"].items():
                if "value" in item:
                    if "%" in item["value"]:
                        item["value"] = float(item["value"].replace("%", "")) / 100
                    elif "$" in item["value"] and "million" in item["value"]:
                        item["value"] = (
                            float(item["value"].replace("$", "").replace(" million", ""))
                            * 1000000
                        )

            result["ownership_summary"] = data["ownership_summary"]

        # Include only key transaction data
        if "holdings_transactions" in data:
            # Keep only top 5 transactions
            result["key_transactions"] = data["holdings_transactions"][:5]

        return result

    def _optimize_insider_trading(self, data):
        """Clean and structure insider trading data"""
        if not data:
            return {}

        # Keep transaction summary counts
        result = {}

        # For transaction table, keep only last 5 transactions
        if "transaction_table" in data and data["transaction_table"]:
            result["recent_transactions"] = data["transaction_table"][:5]

        # Calculate net insider buying/selling ratio
        if "number_of_shares_traded" in data:
            for item in data["number_of_shares_traded"]:
                if item.get("insiderTrade") == "Net Activity":
                    try:
                        result["net_insider_activity_3m"] = self._clean_numeric(
                            item.get("months3", "0")
                        )
                        result["net_insider_activity_12m"] = self._clean_numeric(
                            item.get("months12", "0")
                        )
                    except:
                        pass
                    break

        return result

    def _optimize_historical_quotes(self, data):
        """Convert string price/volume data to numeric for easier analysis"""
        result = {}

        for date, values in data.items():
            result[date] = {}
            for key, value in values.items():
                if key in ["close", "open", "high", "low"]:
                    result[date][key] = self._clean_numeric(value)
                elif key == "volume":
                    result[date][key] = self._clean_financial_metric(value)
                else:
                    result[date][key] = value

        return result

    def _optimize_news_item(self, item):
        """Remove redundant fields in news items and standardize format"""
        if not item:
            return {}

        # No need to include symbol in every item since it's already in the report
        if "relevant_symbol" in item:
            del item["relevant_symbol"]

        # Simplify summary structure if it's redundant
        if "summary" in item and isinstance(item["summary"], dict):
            if "key_point" in item["summary"] and "value" in item["summary"]:
                item["headline"] = item["summary"]["key_point"]
                item["detail"] = item["summary"]["value"]
                del item["summary"]

        return item

    def _clean_numeric(self, value):
        """Convert string numbers to actual numeric types"""
        if isinstance(value, (int, float)):
            return value

        if not value or not isinstance(value, str):
            return None

        try:
            # Remove formatting characters
            clean_value = value.replace("$", "").replace(",", "").replace("%", "")
            return float(clean_value) if "." in clean_value else int(clean_value)
        except ValueError:
            return value


# Example usage
if __name__ == "__main__":
    nasdaq_data = fetch_nasdaq_data()
    symbol = "LPTH"
    meta = Stock.process_meta(nasdaq_data, symbol)  # modified to use #sym:process_meta
    stock = Stock(nasdaq_data=meta)
    stock.make_json()
