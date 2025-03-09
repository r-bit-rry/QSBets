import traceback
from typing import Any
import os
import json
import random
import time
from dotenv import load_dotenv
from mlx_lm import load, generate

from cache.cache import MONTH_TTL, cached
from summarize.utils import SUMMARIZE_PROMPT_V2, SUMMARIZE_PROMPT_V3, SYSTEM_PROMPT, SummaryResponse
from langchain_community.llms.mlx_pipeline import MLXPipeline
from langchain_community.chat_models.mlx import ChatMLX
from langchain.schema.messages import HumanMessage, SystemMessage
from langchain.prompts import PromptTemplate

from ml_serving.deepseek_lc import DEEPSEEK_PROMPT_V3, DEEPSEEK_PROMPT_V4, DEEPSEEK_PROMPT_V5

MLX_PROMPT_V1 = PromptTemplate(
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
"""
)

# Load environment variables from the project root
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

# Path to the local model file
MODEL_PATH = "/Users/roy.belio/Repos/QSBets/ml_serving/mlx_model"

# System prompt for stock analysis
STOCK_SYSTEM_PROMPT = "You are an expert stock analyst. Always provide your analysis in the requested JSON format."
llm = MLXPipeline.from_model_id(
    model_id=MODEL_PATH, pipeline_kwargs={"max_tokens": 2048, "verbose": True}
)
chatmlx = ChatMLX(llm=llm)

# @cached(MONTH_TTL)
def mlx_summarize(text: str, prompt_version=3) -> dict[str, Any]:
    """
    Summarize given text using the local MLX model with LangChain MLXPipeline.
    
    Args:
        text: The text to summarize
        prompt_version: Version of prompt to use (2 or 3)
        model_path: Path to the local MLX model (default: mlx_model in the project)
        
    Returns:
        Dictionary with summarized information
    """
    max_attempts = 2
    attempt = 1

    prompt = SUMMARIZE_PROMPT_V3 if prompt_version == 3 else SUMMARIZE_PROMPT_V2
    formatted_prompt = prompt.format(text=text)

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=formatted_prompt)
    ]

    while attempt <= max_attempts:
        try:
            # Generate response using the MLXPipeline
            response = chatmlx.invoke(messages)
            
            # Extract the JSON response from the text output
            json_text = extract_json_from_response(response.content)

            # Validate against the schema
            summarized_json = SummaryResponse.model_validate_json(json_text)
            return summarized_json.model_dump()
        except Exception as e:
            print(f"Attempt {attempt} {text[:15]} failed: {e}")
            attempt += 1
            if attempt > max_attempts:
                return {}

def consult(filepath: str, max_retries: int = 3, base_delay: float = 2.0) -> dict:
    """
    Consult the MLX model with a stock data file for analysis using MLXPipeline
    
    Args:
        filepath: Path to the JSON file containing stock data
        prompt_version: Version of the prompt to use (3, 4, or 5)
        model_path: Path to the local MLX model
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds for backoff
        
    Returns:
        Parsed JSON response with stock analysis or empty dict on failure
    """
    retry_count = 0

    try:
        with open(filepath, 'r') as file:
            document = file.read()
    except Exception as e:
        print(f"Error reading file {filepath}: {e}")
        return {}

    formatted_prompt = MLX_PROMPT_V1.format(loadedDocument=document)
    messages = [
        SystemMessage(content=STOCK_SYSTEM_PROMPT),
        HumanMessage(content=formatted_prompt)
    ]

    while retry_count <= max_retries:
        try:
            print(f"Processing file: {filepath}")

            response = chatmlx.invoke(messages)

            # Extract and parse the JSON from the response
            try:
                json_str = extract_json_from_response(response.content)
                parsed_json = json.loads(json_str)
                print(f"Analysis completed successfully")
                return parsed_json
            except Exception as e:
                print(f"Error parsing JSON response: {e}")
                raise

        except Exception as e:
            retry_count += 1
            if retry_count > max_retries:
                print(f"Failed after {max_retries} retries: {e}")
                return {}

            # Exponential backoff with jitter
            delay = base_delay * (2 ** (retry_count - 1)) + random.uniform(0, 1)
            traceback.print_exc()
            print(f"Error: {e}. Retrying in {delay:.2f} seconds... (Attempt {retry_count}/{max_retries})")
            time.sleep(delay)

    return {}


def extract_json_from_response(response: str) -> str:
    """
    Extract JSON content from the model response.

    Args:
        response: Raw text response from the MLX model

    Returns:
        Extracted JSON string
    """
    # Look for JSON content between { and } brackets
    start_idx = response.find("{")
    if start_idx == -1:
        raise ValueError("No JSON object found in the response")

    # Find the matching closing bracket
    bracket_count = 0
    for i in range(start_idx, len(response)):
        if response[i] == "{":
            bracket_count += 1
        elif response[i] == "}":
            bracket_count -= 1
            if bracket_count == 0:
                end_idx = i + 1
                break
    else:
        raise ValueError("No valid JSON object found in the response")

    # Extract and validate the JSON
    json_str = response[start_idx:end_idx]
    # Ensure it's valid JSON
    json.loads(json_str)  # This will raise an exception if the JSON is invalid

    return json_str
