from datetime import datetime
import os
import random
import time
from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv
import json

import os
from langchain_azure_ai.chat_models import AzureAIChatCompletionsModel

from ml_serving.prompts import CONSULT_PROMPT_V6
from logger import get_logger

logger = get_logger("deepseek_lc")

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
            logger.error(f"Error initializing model: {e}")
            raise

    return _model_instance


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
        logger.error("Error decoding JSON: %s", e)
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
            chain = CONSULT_PROMPT_V6 | model
            response = chain.stream({"loadedDocument": document})
            content = []
            for chunk in response:
                logger.debug(chunk.content)
                content.append(chunk.content)

            return decode_response("".join(content))

        except Exception as e:
            error_message = str(e).lower()
            if "too many requests" in error_message or "timeout" in error_message:
                retry_count += 1
                if retry_count > max_retries:
                    logger.error(f"Failed after {max_retries} retries: {e}")
                    return {}

                # Calculate exponential backoff with jitter
                delay = base_delay * (2 ** (retry_count - 1)) + random.uniform(0, 1)
                logger.warning(
                    f"Rate limited or timeout. Retrying in {delay:.2f} seconds... (Attempt {retry_count}/{max_retries})"
                )
                time.sleep(delay)
            else:
                logger.error(f"Error: {e}")
                return {}


def analyze_folder(folder: str):
    today_str = datetime.now().strftime("%Y-%m-%d")
    for filename in os.listdir(folder):
        if filename.endswith(f"{today_str}.json"):
            filepath = os.path.join(folder, filename)
            logger.info(f"Processing file: {filepath}")
            result = consult(filepath)
            logger.info(f"Result: {result}")

def main():
    start_time = datetime.now()
    result = consult("./analysis_docs/SEDG_2025-02-27.json")
    logger.info(f"Analysis result: {json.dumps(result, indent=2)}")
    end_time = datetime.now()
    logger.info(f"Duration: {end_time - start_time}")


if __name__ == "__main__":
    load_dotenv(".env")
    main()
    # analyze_folder("analysis_docs")
