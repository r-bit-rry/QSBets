from langchain.prompts import PromptTemplate

SUMMARIZE_PROMPT_V1 = "Summarize the following text in concise and technical bullet points for company symbol {symbol} only, keep relevant figures, numbers and relevant names to be used by further analysis, if no relevant information is provided, return article title and the string, 'no relevant data':\n\n{text}"
SUMMARIZE_PROMPT_V2 = (
    "Summarize in 100 words maximum."
    "Return valid JSON object in the following format:"
    '{{"date": "date of the document", "source": "who wrote the document", "summary": "key point or measure, and its value", "relevant_symbol": "relevant stock symbol or ticker"}}. '
    "Analyze the following text:\n{text}"
)
STOCK_SUMMARIZE_SYSTEM_PROMPT = "You are a financial summarization assistant specialized in extracting quantitative insights. Focus on key metrics, valuations (P/E, P/S ratios), growth rates, market positioning, and business risks. Ignore unrelated content and format your response as structured data."
STOCK_CONSULT_SYSTEM_PROMPT = "You are an expert stock analyst. Always provide your analysis in the requested JSON format."

SUMMARIZE_PROMPT_V3 = (
    "Extract and summarize key financial metrics from the content below."
    "\n\nRETURN A VALID JSON OBJECT using this EXACT format:"
    "\n{{\n"
    '  "date": "publication date in YYYY-MM-DD format",\n'
    '  "source": "name of the publishing organization",\n'
    '  "summary": {{\n'
    '    "[ACTUAL_TICKER_SYMBOL]": "1-2 sentence summary with key metrics and valuation"\n'
    "  }},\n"
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

CONSULT_PROMPT_V3 = PromptTemplate(
    input_variables=["loadedDocument"],
    template="""Rate stock, use the stock provided data and your general knowledge about industry and market.
Low score ⇒ Sell/Avoid; High score ⇒ Buy/Hold for a few weeks. Briefly explain the key factors and offer buy/exit strategies.
Describe your strategy with using the technical trading terms available to me (you don't have to use all of them): Price Greater/Lower than, Trading Volume, Start Date, P/B Ratio, P/E Ratio, ADX, RSI, ROC, Parabolic SAR, MACD, StdDev, SMA 20/50/100, Bollinger Bands, VWAP, Benchmark Index, profit, loss, price target, end date.
Return valid JSON only:
{{
  "rating": 0-100,
  "reasoning": "concise explanation",
  "enter_strategy": "entry plan",
  "exit_strategy": "exit plan"
}}

Stock data:
{loadedDocument}""",
)

CONSULT_PROMPT_V4 = PromptTemplate(
    input_variables=["loadedDocument"],
    template="""You are an expert stock analyst with deep knowledge of both technical and fundamental analysis. Analyze the provided stock data comprehensively.

First, examine all available information including:
- Price action and technical indicators
- Social sentiment and news coverage
- Upcoming earnings and company events
- Sector trends and comparative performance
- Recent volume patterns

Rate the stock on a scale of 0-100 where:
- 0-30: Strong Sell (High risk, negative outlook)
- 31-45: Sell (Underperform, concerning signals)
- 46-55: Hold/Neutral (Mixed signals, unclear direction)
- 56-70: Buy (Favorable outlook, good potential)
- 71-100: Strong Buy (Excellent setup, high conviction)

Consider both short-term catalysts (1-5 days) and medium-term outlook (2-4 weeks).

Return your analysis in this JSON format:
{{
  "rating": 0-100,
  "confidence": 1-10,
  "reasoning": "Concise explanation of your rating rationale",
  "enter_strategy": {{
    "entry_price": "Specific price or condition",
    "entry_timing": "Immediate or specific condition",
    "technical_indicators": "Key technical indicators supporting entry"
  }},
  "exit_strategy": {{
    "profit_target": "Price target or percentage gain",
    "stop_loss": "Specific price or percentage from entry",
    "time_horizon": "Expected holding period",
    "exit_conditions": "Technical or news-based exit signals"
  }}
}}

Ensure your response is pragmatic, actionable, concise, technical, using numbers instead of markers, considers both upside potential and downside risks.
These are the available technical trading terms for strategy: Price Greater/Lower than, Trading Volume, Start Date, P/B Ratio, P/E Ratio, ADX, RSI, ROC, Parabolic SAR, MACD, StdDev, SMA 20/50/100, Bollinger Bands, VWAP, Benchmark Index.

Stock data:
{loadedDocument}""",
)

# New optimized prompt that uses pre-analyzed data
CONSULT_PROMPT_V5 = PromptTemplate(
    input_variables=["loadedDocument"],
    template="""You are an expert stock analyst. Evaluate the provided stock data which includes pre-analyzed technical indicators, sentiment metrics, and preliminary ratings.

Review and refine the preliminary rating (0-100) where:
- 0-30: Strong Sell (High risk, negative outlook)
- 31-45: Sell (Underperform, concerning signals)
- 46-55: Hold/Neutral (Mixed signals, unclear direction)
- 56-70: Buy (Favorable outlook, good potential)
- 71-100: Strong Buy (Excellent setup, high conviction)

Return your analysis in this JSON format:
{{
  "symbol": "The ticker symbol",
  "rating": 0-100,
  "confidence": 1-10,
  "reasoning": "Concise explanation of your rating with key data points",
  "enter_strategy": {{
    "entry_price": "Specific price or condition",
    "entry_timing": "Immediate or specific condition",
    "technical_indicators": "Key technical indicators supporting entry"
  }},
  "exit_strategy": {{
    "profit_target": "Price target or percentage gain",
    "stop_loss": "Specific price or percentage from entry",
    "time_horizon": "Expected holding period",
    "exit_conditions": "Technical or news-based exit signals"
  }}
}}

Focus your reasoning on validating or adjusting the preliminary rating based on the most critical data points. Use only numbers instead of verbal markers (like "slightly" or "strong").

Stock data:
{loadedDocument}""",
)


CONSULT_PROMPT_V6 = PromptTemplate(
    input_variables=["loadedDocument"],
    template="""You are an expert financial analyst evaluating a stock for potential investment. Analyze the provided data and generate a comprehensive investment thesis with the following structure:

{{
  "symbol": "TICKER",
  "rating": [0-100 score with 100 being strongest buy],
  "confidence": [1-10 confidence in your rating],
  "reasoning": [Concise summary of key factors driving your rating],
  "bullish_factors": [
    "List 3-5 specific reasons supporting a bullish case, with quantitative values"
  ],
  "bearish_factors": [
    "List 2-4 specific risks or concerns, with quantitative values"
  ],
  "macro_impact": "How current macroeconomic conditions specifically affect this stock",
  "enter_strategy": {{
    "entry_price": "Specific price levels with rationale",
    "entry_timing": "Market conditions that would trigger entry",
    "technical_indicators": "Key indicators to monitor with specific values"
  }},
  "exit_strategy": {{
    "profit_target": "Primary and secondary price targets with percentage gains",
    "stop_loss": "Specific price with percentage loss and rationale",
    "time_horizon": "Expected holding period",
    "exit_conditions": [
      "List specific technical or fundamental conditions that would trigger exit"
    ]
  }}
}}

Return ONLY the JSON response with no additional text.

Stock Data:
{loadedDocument}
""",
)

CONSULT_PROMPT_V7 = PromptTemplate(
    input_variables=["loadedDocument"],
    template="""Analyze this stock as an expert financial analyst. Identify key opportunities and risks.
    Be thorough, focusing on actionable entry/exit strategies adhering to the specified format.
    Reason around the input data until you are confident (confidence >= 8). If not confident, state why.
    Provide a technical, data-driven investment thesis.

RETURN ONLY THE JSON response with no additional text, using this exact structure:
{{
  "symbol": "TICKER",
  "rating": 0-100 score where 0=strongest sell and 100=strongest buy,
  "confidence": 1-10 confidence,
  "reasoning": "Concise summary of key factors driving rating",
  "bullish_factors": [
    "List 3-5 specific bullish reasons with quantitative values"
  ],
  "bearish_factors": [
    "List 2-4 specific risks/concerns with quantitative values"
  ],
  "macro_impact": "How current macroeconomic conditions affect this stock",
  "enter_strategy": {{
    "price": "[Target entry price level(s) or condition string, e.g., '10.50' or 'SMA20']",
    "timing": "[Timing instruction string, e.g., 'Immediate' or 'On pullback']",
    "conditions": [ 
      {{ "indicator": "e.g., price", "operator": "e.g., >", "value": "e.g., sma50", "description": "Optional: Price > SMA50" }}
    ]
  }},
  "exit_strategy": {{
    "profit_target": {{ 
        "primary": {{ "price": [numeric target price], "percentage": [optional string % gain] }},
        "secondary": {{ "price": [optional numeric target price], "percentage": [optional string % gain] }}
    }},
    "stop_loss": {{ "price": [numeric stop loss price], "percentage": [optional string % loss] }},
    "time_horizon": "[Expected holding period string, e.g., '2-4 weeks']",
    "conditions": [
      {{ "indicator": "e.g., price", "operator": "e.g., <", "value": "e.g., sma100", "description": "Optional: Close below SMA100" }}
    ]
  }}
}}

Stock Data:
{loadedDocument}
""",
)

OWNERSHIP_PROMPT = PromptTemplate(
    input_variables=["loadedDocument", "purchase_price"],
    template="""You are an elite portfolio manager managing an existing position bought at ${purchase_price}. Provide a clear hold/sell recommendation.
    Analyze the position critically relative to the purchase price and original thesis. Evaluate indicators, fundamentals, and sentiment.
    Assess: 1. Current price vs purchase. 2. Thesis validity. 3. Indicator signals. 4. Macro impact.
    Reason until confident (confidence >= 8). If not confident, state why.
    Generate a comprehensive position recommendation.

RETURN ONLY THE JSON response with no additional text, using this exact structure:
{{
  "symbol": "TICKER",
  "purchase_price": {purchase_price},
  "current_price": current stock price from data,
  "unrealized_gain_loss_pct": [percentage gain/loss from purchase],
  "rating": 0-100 score where 0=strongest sell and 100=strongest hold,
  "confidence": 1-10 confidence,
  "reasoning": "Concise summary driving recommendation",
  "hold_factors": [
    "List 2-4 specific reasons supporting hold, with quantitative values"
  ],
  "risk_factors": [
    "List 2-4 specific risks for holding, with quantitative values"
  ],
  "macro_impact": "How current macroeconomic conditions affect this position",
  "exit_strategy": {{
    "stop_loss": {{ "price": [UPDATED numeric stop loss price], "percentage": [optional string % loss from current price] }},
    "profit_target": {{ "primary": {{ "price": [REVISED numeric target price], "percentage": [optional string % gain from current price] }} }},
    "time_horizon": "[Remaining recommended holding period string]",
    "trailing_stop": "[Optional: Suggest trailing stop % string, e.g., '5%']",
    "conditions": [
      {{ "indicator": "e.g., price", "operator": "e.g., <", "value": "e.g., sma200", "description": "Optional: Close below key level" }}
    ]
  }}
}}

Stock Data:
{loadedDocument}
""",
)
