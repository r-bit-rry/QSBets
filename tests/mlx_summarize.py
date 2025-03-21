from typing import Any
import os
from dotenv import load_dotenv

from ml_serving.model_server import extract_json_from_response
from ml_serving.utils import SUMMARIZE_PROMPT_V2, SUMMARIZE_PROMPT_V3, SYSTEM_PROMPT, SummaryResponse, dump_failed_text
from langchain_community.llms.mlx_pipeline import MLXPipeline
from langchain_community.chat_models.mlx import ChatMLX
from langchain.schema.messages import HumanMessage, SystemMessage
from logger import get_logger

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

logger = get_logger(__name__)

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
            logger.error(f"Attempt {attempt} {text[:15]} failed: {e}")
            attempt += 1
            if attempt > max_attempts:
                dump_failed_text(formatted_prompt)
                return {}

