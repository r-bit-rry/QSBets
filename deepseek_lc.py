from datetime import datetime
import os
import random
import time
from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv
import json

import os
from langchain_azure_ai.chat_models import AzureAIChatCompletionsModel
from langchain.prompts import PromptTemplate
# Defining model's endpoint and Azure credentials
DS_Model = os.getenv("AZURE_FOUNDRY_DEEPSEEK")
DS_Region = "eastus"
DS_Endpoint = f"https://{DS_Model}.{DS_Region}.models.ai.azure.com"

_model_instance = None

def get_model():
    """
    Returns a static instance of AzureAIChatCompletionsModel.
    Creates it once and reuses it for subsequent calls.
    """
    global _model_instance

    if _model_instance is None:
        try:
            _model_instance = AzureAIChatCompletionsModel(
                endpoint=DS_Endpoint,
                credential=AzureKeyCredential(os.getenv("DEEPSEEK_API_KEY")),
                max_tokens=2048,
                temperature=0.6,
                top_p=0.95,
                model_kwargs={"stream_options": {"include_usage": True}},
            )
        except Exception as e:
            print(f"Error initializing model: {e}")
            raise

    return _model_instance


DEEPSEEK_PROMPT_V3 = PromptTemplate(
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
{loadedDocument}"""
)

DEEPSEEK_PROMPT_V4 = PromptTemplate(
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
  "primary_catalysts": "Top 2-3 factors driving your rating",
  "risk_factors": "Key risks that could invalidate your thesis",
  "reasoning": "Concise explanation of your rating rationale",
  "technical_analysis": "Key technical signals from the data",
  "sentiment_analysis": "Assessment of news sentiment and social signals",
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

Ensure your response is pragmatic, actionable, and considers both upside potential and downside risks.
These are the available technical trading terms for strategy: Price Greater/Lower than, Trading Volume, Start Date, P/B Ratio, P/E Ratio, ADX, RSI, ROC, Parabolic SAR, MACD, StdDev, SMA 20/50/100, Bollinger Bands, VWAP, Benchmark Index.

Stock data:
{loadedDocument}""",
)

def decode_response(content: str):
    # Remove and extract the <think></think> section
    think_start = content.find("<think>")
    think_end = content.find("</think>")
    if think_start != -1 and think_end != -1:
        content = content[:think_start] + content[think_end + len("</think>") :]

    start = content.find("{")
    end = content.rfind("}") + 1
    json_str = content[start:end]
    try:
        parsed_json = json.loads(json_str)
    except json.JSONDecodeError as e:
        print("Error decoding JSON:", e)
        parsed_json = {}
    return parsed_json


def consult(filepath: str, max_retries: int = 5, base_delay: float = 2.0):
    """
    Consult the Deepseek model with a file, implementing retry with exponential backoff

    Args:
        filepath: Path to the file to analyze
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds for backoff

    Returns:
        Parsed JSON response or empty dict on failure
    """
    model = get_model()
    retry_count = 0

    while retry_count <= max_retries:
        try:
            document = open(filepath).read()
            chain = DEEPSEEK_PROMPT_V4 | model
            response = chain.stream({"loadedDocument": document})
            content = []
            for chunk in response:
                print(chunk.content, end="", flush=True)
                content.append(chunk.content)

            return decode_response("".join(content))

        except Exception as e:
            error_message = str(e).lower()
            if "too many requests" in error_message or "timeout" in error_message:
                retry_count += 1
                if retry_count > max_retries:
                    print(f"Failed after {max_retries} retries: {e}")
                    return {}

                # Calculate exponential backoff with jitter
                delay = base_delay * (2 ** (retry_count - 1)) + random.uniform(0, 1)
                print(
                    f"Rate limited or timeout. Retrying in {delay:.2f} seconds... (Attempt {retry_count}/{max_retries})"
                )
                time.sleep(delay)
            else:
                # For other errors, don't retry
                print(f"Error: {e}")
                return {}


def analyze_folder(folder: str):
    today_str = datetime.now().strftime("%Y-%m-%d")
    for filename in os.listdir(folder):
        if filename.endswith(f"{today_str}.json"):
            filepath = os.path.join(folder, filename)
            print(f"Processing file: {filepath}")
            result = consult(filepath)
            print(f"Result: {result}")

def main():
    start_time = datetime.now()
    consult("./analysis_docs/SEDG_2025-02-27.json")
    end_time = datetime.now()
    print(f"Duration: {end_time - start_time}")


if __name__ == "__main__":
    load_dotenv(".env")
    main()
    # analyze_folder("analysis_docs")
