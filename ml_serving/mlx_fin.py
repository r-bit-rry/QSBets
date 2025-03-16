# Add imports at the top of the file
import json
import os
import random
import threading
import time
import traceback
from typing import Any

from ml_serving.prompts import CONSULT_PROMPT_V7, OWNERSHIP_PROMPT
from summarize.utils import SUMMARIZE_PROMPT_V2, SUMMARIZE_PROMPT_V3, SYSTEM_PROMPT, SummaryResponse, dump_failed_text
from .mlx_model_server import get_model_server, MLXModelServer
from langchain.schema.messages import HumanMessage, SystemMessage

MODEL_PATH = "/Users/roy.belio/Repos/QSBets/ml_serving/mlx_model"

# Initialize the model server on module load
model_server = get_model_server(MODEL_PATH, num_workers=4)

# System prompt for stock analysis
STOCK_SYSTEM_PROMPT = "You are an expert stock analyst. Always provide your analysis in the requested JSON format."

# Cache for request results
request_results = {}
request_locks = {}

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


def mlx_summarize(text: str, prompt_version=3) -> dict[str, Any]:
    """
    Summarize given text using the MLX model server.
    
    Args:
        text: The text to summarize
        prompt_version: Version of prompt to use (2 or 3)
        
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
            # Create a unique request ID and lock for this request
            request_id = f"summarize_{hash(text)[:20]}_{time.time()}"
            result_event = threading.Event()
            request_results[request_id] = None

            # Define callback function
            def on_complete(req_id, result):
                request_results[req_id] = result
                result_event.set()

            # Submit request to model server
            model_server.submit_request(
                request_id=request_id,
                messages=messages,
                callback=on_complete,
                metadata={"attempt": attempt}
            )

            # Wait for result with timeout
            if not result_event.wait(timeout=120):
                print(f"Request {request_id} timed out")
                attempt += 1
                continue

            result = request_results.pop(request_id)
            if "error" in result:
                raise Exception(f"Model server error: {result['error']}")

            # Extract the JSON response from the text output
            try:
                json_text = extract_json_from_response(result["content"])
                # Validate against the schema
                summarized_json = SummaryResponse.model_validate_json(json_text)
                return summarized_json.model_dump()
            except ValueError as e:
                print(f"Failed to extract JSON: {e}")
                dump_failed_text(result["content"])
                raise

        except Exception as e:
            print(f"Attempt {attempt} {text[:15]} failed: {e}")
            attempt += 1
            if attempt > max_attempts:
                dump_failed_text(formatted_prompt)
                return {}

def consult(filepath: str, metadata: dict = None, callback=None, max_retries: int = 3, base_delay: float = 2.0) -> dict:
    """
    Consult the MLX model with a stock data file for analysis using the MLX model server
    
    Args:
        filepath: Path to the JSON/YAML file containing stock data
        metadata: Additional metadata to include in the result
        callback: Function to call with the result when complete
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds for backoff
        
    Returns:
        Parsed JSON response with stock analysis or empty dict on failure
        If callback is provided, the result is passed to the callback and None is returned
    """
    retry_count = 0
    result = {}

    try:
        with open(filepath, 'r') as file:
            document = file.read()
    except Exception as e:
        error_msg = f"Error reading file {filepath}: {e}"
        print(error_msg)
        result = {"error": error_msg, "metadata": metadata}
        if callback:
            callback(result)
        return result

    try:
        purchase_price = metadata.get("purchase_price")
        if purchase_price is not None and str(purchase_price).strip() and float(purchase_price) > 0:
            formatted_prompt = OWNERSHIP_PROMPT.format(loadedDocument=document, purchase_price=purchase_price)
        else:
            formatted_prompt = CONSULT_PROMPT_V7.format(loadedDocument=document)
    except (ValueError, TypeError):
        formatted_prompt = CONSULT_PROMPT_V7.format(loadedDocument=document)

    messages = [
        SystemMessage(content=STOCK_SYSTEM_PROMPT),
        HumanMessage(content=formatted_prompt)
    ]

    request_id = f"consult_{os.path.basename(filepath)}_{time.time()}"
    result_event = threading.Event()
    request_results[request_id] = None

    def on_complete(req_id, mlx_result):
        request_results[req_id] = mlx_result
        result_event.set()

    while retry_count <= max_retries:
        try:
            print(f"Processing file: {filepath}")

            # Submit request to model server
            model_server.submit_request(
                request_id=request_id,
                messages=messages,
                callback=on_complete,
                metadata=metadata
            )

            # Wait for result with timeout
            if not result_event.wait(timeout=300):
                print(f"Request {request_id} timed out")
                retry_count += 1
                if retry_count <= max_retries:
                    continue
                else:
                    result = {"error": "Request timed out", "metadata": metadata}
                    break

            mlx_result = request_results.pop(request_id, None)
            if not mlx_result:
                raise Exception("No result received from model server")

            if "error" in mlx_result:
                raise Exception(f"Model server error: {mlx_result.get('error')}")

            # Extract and parse the JSON from the response
            try:
                json_str = extract_json_from_response(mlx_result["content"])
                result = json.loads(json_str)
                # Add metadata to the result
                result["metadata"] = metadata
                print(f"Analysis completed successfully")
                break
            except Exception as e:
                error_msg = f"Error parsing JSON response: {e}"
                print(error_msg)
                raise

        except Exception as e:
            retry_count += 1
            if retry_count > max_retries:
                print(f"Failed after {max_retries} retries: {e}")
                result = {"error": str(e), "metadata": metadata}
                break

            # Exponential backoff with jitter
            delay = base_delay * (2 ** (retry_count - 1)) + random.uniform(0, 1)
            traceback.print_exc()
            print(f"Error: {e}. Retrying in {delay:.2f} seconds... (Attempt {retry_count}/{max_retries})")
            time.sleep(delay)

    # If a callback was provided, call it with the result
    if callback:
        callback(result)
        return None

    return result
