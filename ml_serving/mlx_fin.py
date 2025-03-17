"""
MLX finance module providing high-level financial analysis functions
using the AI service abstraction layer.
"""
from typing import Any

from cache.cache import HOURS2_TTL, WEEK_TTL, cached
from ml_serving.ai_service import consult as ai_consult, summarize as ai_summarize

@cached(WEEK_TTL)
def summarize(text: str, prompt_version: int = 3) -> dict[str, Any]:
    """
    Summarize given text using the MLX model.
    
    Args:
        text: The text to summarize
        prompt_version: Version of prompt to use (2 or 3)
        
    Returns:
        Dictionary with summarized information
    """
    return ai_summarize(
        text=text,
        prompt_version=prompt_version,
        backend="mlx"
    )

@cached(HOURS2_TTL)
def consult(filepath: str, metadata: dict = None, callback=None, max_retries: int = 3, base_delay: float = 2.0) -> dict:
    """
    Consult the MLX model with a stock data file for analysis
    
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
    return ai_consult(
        filepath=filepath,
        metadata=metadata,
        callback=callback,
        backend="mlx",
        max_retries=max_retries
    )
