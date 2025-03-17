from datetime import datetime
import os
from pydantic import BaseModel


class SummaryResponse(BaseModel):
    date: str
    source: str
    summary: dict
    relevant_symbol: str


def dump_failed_text(text: str):
    """
    Dump the failed text to a file in the debug_dumps folder.

    Args:
        text: The text to dump
    """
    if not os.path.exists(".debug_dumps"):
        os.makedirs(".debug_dumps")

    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f".debug_dumps/{date_str}.txt"

    with open(filename, "w") as file:
        file.write(text)


SUMMARIZE_PROMPT_V1 = "Summarize the following text in concise and technical bullet points for company symbol {symbol} only, keep relevant figures, numbers and relevant names to be used by further analysis, if no relevant information is provided, return article title and the string, 'no relevant data':\n\n{text}"
SUMMARIZE_PROMPT_V2 = (
    "Summarize in 100 words maximum."
    "Return valid JSON object in the following format:"
    '{{"date": "date of the document", "source": "who wrote the document", "summary": "key point or measure, and its value", "relevant_symbol": "relevant stock symbol or ticker"}}. '
    "Analyze the following text:\n{text}"
)
SYSTEM_PROMPT = "You are a financial summarization assistant specialized in extracting quantitative insights. Focus on key metrics, valuations (P/E, P/S ratios), growth rates, market positioning, and business risks. Ignore unrelated content and format your response as structured data."

SUMMARIZE_PROMPT_V3 = (
    "Extract and summarize key financial metrics from the content below."
    "\n\nRETURN A VALID JSON OBJECT using this EXACT format:"
    "\n{{\n"
    '  "date": "publication date in YYYY-MM-DD format",\n'
    '  "source": "name of the publishing organization",\n'
    '  "summary": {{\n'
    '    "[ACTUAL_TICKER_SYMBOL]": "1-2 sentence summary with key metrics and valuation"\n'
    '  }},\n'
    '  "relevant_symbol": "actual ticker symbol of the company"\n'
    "}}\n\n"
    "IMPORTANT INSTRUCTIONS:\n"
    "1. Replace [ACTUAL_TICKER_SYMBOL] with the real stock ticker symbol (e.g., AAPL, MSFT, GOOGL)\n"
    "2. If ticker isn't explicitly mentioned, research the company name to determine the correct ticker\n"
    "3. Focus on quantitative data: revenue growth percentages, earnings, EPS, P/E ratios, margins\n"
    "4. Include year-over-year comparisons when available\n"
    "5. If multiple companies are mentioned, create separate entries for each ticker\n"
    "6. Do not use placeholder text like 'TICKER1' in your response\n\n"
    "Text to analyze:\n{text}"
)

SUMMARIZE_PROMPT_V4 = (
    "Extract basic financial information from the text below."
    "\n\nProvide your response in this JSON format:"
    "\n{{\n"
    '  "date": "YYYY-MM-DD (use the date mentioned in the text)",\n'
    '  "source": "publishing organization name",\n'
    '  "summary": {{\n'
    '    "TICKER": "Brief summary focusing on key numbers"\n'
    "  }},\n"
    '  "relevant_symbol": "TICKER"\n'
    "}}\n\n"
    "SIMPLIFIED INSTRUCTIONS:\n"
    "1. Use ONLY ticker symbols explicitly mentioned in the text\n"
    "2. If no ticker symbol is found, use the company name as is\n"
    "3. Focus only on the most important metrics clearly stated in the text\n"
    "4. Keep your summary to one short sentence\n"
    "5. If multiple companies appear, just focus on the main one\n"
    "6. If no financial metrics are present, simply describe what the text is about\n\n"
    "Text to analyze:\n{text}"
)
