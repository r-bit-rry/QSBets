from datetime import datetime
from functools import partial
import json
import os
import time

from summarize import azure_openai_summarize, ollama_summarize
from nasdaq import (
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

class Stock:
    def __init__(self, symbol, meta,):
        self.symbol = symbol
        self.meta = meta

    def make_json(self):
        report = {}

        start = time.perf_counter()
        self.description = fetch_description(self.symbol)
        elapsed = time.perf_counter() - start
        print(f"{self.symbol}: Fetched description in {elapsed:.2f} seconds")
        report["description"] = self.description

        # Add metadata
        report["meta"] = dict(self.meta)

        # Revenue and Earnings
        start = time.perf_counter()
        revenue_earnings = fetch_revenue_earnings(self.symbol)
        elapsed = time.perf_counter() - start
        print(f"{self.symbol}: Fetched revenue and earnings in {elapsed:.2f} seconds")
        report["revenue_earnings"] = json.loads(revenue_earnings)

        # Short Interest
        start = time.perf_counter()
        short_interest = fetch_short_interest(self.symbol)
        elapsed = time.perf_counter() - start
        print(f"{self.symbol}: Fetched short interest in {elapsed:.2f} seconds")
        report["short_interest"] = json.loads(short_interest)

        # Institutional Holdings
        start = time.perf_counter()
        institutional_holdings = fetch_institutional_holdings(self.symbol)
        elapsed = time.perf_counter() - start
        print(f"{self.symbol}: Fetched institutional holdings in {elapsed:.2f} seconds")
        report["institutional_holdings"] = json.loads(institutional_holdings)

        # Insider Trading
        start = time.perf_counter()
        insider_trading = fetch_insider_trading(self.symbol)
        elapsed = time.perf_counter() - start
        print(f"{self.symbol}: Fetched insider trading in {elapsed:.2f} seconds")
        report["insider_trading"] = json.loads(insider_trading)

        # SEC Filings (as a summarized string)
        start = time.perf_counter()
        sec_filings = fetch_sec_filings(self.symbol)
        elapsed = time.perf_counter() - start
        print(f"{self.symbol}: Fetched SEC filings in {elapsed:.2f} seconds")
        # Using partial ollama summarize for SEC filings summary
        partial_ollama_summarize = partial(ollama_summarize, symbol=f"{self.meta['name']} ({self.meta['symbol']})")
        report["sec_filings"] = "\n\n".join(sec_filings)

        # Nasdaq News
        start = time.perf_counter()
        news = fetch_stock_news(self.symbol)
        elapsed = time.perf_counter() - start
        print(f"{self.symbol}: Fetched Nasdaq news in {elapsed:.2f} seconds")
        start = time.perf_counter()
        summarized_news = '[' + ",".join(map(lambda d: partial_ollama_summarize(text=d), news)) + ']'
        elapsed = time.perf_counter() - start
        print(f"{self.symbol}: Summarized Nasdaq news in {elapsed:.2f} seconds")
        report["nasdaq_news"] = summarized_news

        # Nasdaq Press Releases
        start = time.perf_counter()
        press_releases = fetch_stock_press_releases(self.symbol)
        elapsed = time.perf_counter() - start
        print(f"{self.symbol}: Fetched Nasdaq press releases in {elapsed:.2f} seconds")
        start = time.perf_counter()
        summarized_press_release = '[' + ",".join(map(lambda d: partial_ollama_summarize(text=d), press_releases)) + ']'
        elapsed = time.perf_counter() - start
        print(f"{self.symbol}: Summarized Nasdaq press releases in {elapsed:.2f} seconds")
        report["nasdaq_press_releases"] = summarized_press_release

        # Save JSON report (minified to conserve tokens)
        today = datetime.now().strftime("%Y-%m-%d")
        safe_name = "".join(c for c in self.meta["symbol"] if c.isalnum() or c in ("_", "-"))
        docs_folder = "analysis_docs"
        os.makedirs(docs_folder, exist_ok=True)
        file_name = f"{safe_name}_{today}.json"
        file_path = os.path.join(docs_folder, file_name)
        with open(file_path, "w", encoding="utf-8") as fp:
            fp.write(json.dumps(report, separators=(",", ":")))
        print(f"Saved analysis for {self.meta['symbol']} to {file_path}")
        return file_path

# Example usage
if __name__ == "__main__":
    nasdaq_data = fetch_nasdaq_data()
    symbol = "LPTH"
    meta = nasdaq_data[nasdaq_data["symbol"] == symbol].iloc[0].to_dict()
    stock = Stock(symbol=symbol, meta=meta)
    stock.make_json()
