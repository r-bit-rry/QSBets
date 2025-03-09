from typing import Any
import os
from dotenv import load_dotenv
from ollama import Client

from cache.cache import MONTH_TTL, cached
from summarize.utils import SUMMARIZE_PROMPT_V2, SUMMARIZE_PROMPT_V3, SYSTEM_PROMPT, SummaryResponse

# Load environment variables from the project root
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), ".env"))

client = Client(
    host="http://127.0.0.1:11434",
    timeout=600,
)


# @cached(MONTH_TTL)
def ollama_summarize(text: str, prompt_version=3, model="plutus3") -> dict[str, Any]:
    """
    Summarize given text using the local Ollama instance with the specified model.
    
    Args:
        text: The text to summarize
        prompt_version: Version of prompt to use (2 or 3)
        model: Model name to use (default: plutus3)
        
    Returns:
        Dictionary with summarized information
    """
    max_attempts = 2
    attempt = 1

    # Select the appropriate prompt based on version
    prompt = SUMMARIZE_PROMPT_V3 if prompt_version == 3 else SUMMARIZE_PROMPT_V2

    while attempt <= max_attempts:
        try:
            response = client.generate(
                prompt=prompt.format(text=text),
                format=SummaryResponse.model_json_schema(),
                model=model,
                system=SYSTEM_PROMPT,
                options={"temperature": 0.05},
            )
            # Optionally validate the JSON response here to ensure it meets the schema.
            summarized_json = SummaryResponse.model_validate_json(response.response)
            return summarized_json.model_dump()
        except Exception as e:
            print(f"Attempt {attempt} {text[:15]} failed: {e}")
            attempt += 1
            if attempt > max_attempts:
                return {}
