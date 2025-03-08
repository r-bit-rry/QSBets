from pydantic import BaseModel


class SummaryResponse(BaseModel):
    date: str
    source: str
    summary: dict
    relevant_symbol: str


SUMMARIZE_PROMPT_V1 = "Summarize the following text in concise and technical bullet points for company symbol {symbol} only, keep relevant figures, numbers and relevant names to be used by further analysis, if no relevant information is provided, return article title and the string, 'no relevant data':\n\n{text}"
SUMMARIZE_PROMPT_V2 = (
    "Summarize in 100 words maximum."
    "Return valid JSON object in the following format:"
    '{{"date": "date of the document", "source": "who wrote the document", "summary": "key point or measure, and its value", "relevant_symbol": "relevant stock symbol or ticker"}}. '
    "Analyze the following text:\n{text}"
)
SYSTEM_PROMPT = "You are a financial summarization assistant specialized in extracting quantitative insights. Focus on key metrics, valuations (P/E, P/S ratios), growth rates, market positioning, and business risks. Ignore unrelated content and format your response as structured data."

SUMMARIZE_PROMPT_V3 = (
    "Analyze and summarize the financial content below in under 100 words total."
    "Return a valid JSON object in this exact format:\n"
    "{{\n"
    '  "date": "publication date (YYYY-MM-DD format if available)",\n'
    '  "source": "publication source name",\n'
    '  "summary": {{\n'
    '    "TICKER1": "1-2 sentence summary with key metrics and valuation",\n'
    '    "TICKER2": "1-2 sentence summary with key metrics and valuation"\n'
    '  }},\n'
    '  "relevant_symbol": "primary ticker discussed or all tickers separated by commas"\n'
    "}}\n\n"
    "Include P/E ratios, P/S multiples, growth rates, and key business developments. Prioritize quantitative information."
    "Text to analyze:\n{text}"
)
