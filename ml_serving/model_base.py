"""
Base abstract class for model server implementations.
"""
from abc import abstractmethod
from typing import Dict, Any, Callable, List, Optional
from langchain.callbacks.base import BaseCallbackHandler
from langchain_core.messages import SystemMessage, HumanMessage
from langchain_core.language_models import LLM


class ModelServer(LLM):
    """Abstract base class for all model server implementations."""

    @abstractmethod
    def submit_request(self, 
                      request_id: str,
                      messages: List[Any],
                      callback: Callable[[str, Dict[str, Any]], None],
                      metadata: Dict[str, Any] = None) -> bool:
        """
        Submit a request to the model server for processing
        
        Args:
            request_id: Unique identifier for this request
            messages: List of messages to process
            callback: Function to call with the result
            metadata: Additional metadata to pass along with the request
            
        Returns:
            True if request was accepted, False otherwise
        """
        pass

    @abstractmethod
    def process_sync(self, messages: List[Any], metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Process a request synchronously
        
        Args:
            messages: List of messages to process
            metadata: Additional metadata
            
        Returns:
            Dictionary with model response
        """
        pass

    def _call(
        self,
        prompt: str,
        stop: Optional[List[str]] = None,
        run_manager: Optional[BaseCallbackHandler] = None,
        **kwargs,
    ) -> str:
        messages = [
            SystemMessage(content="You are a professional financial analyst."),
            HumanMessage(content=prompt),
        ]

        # Use synchronous processing
        result = self.process_sync(messages)

        if "error" in result:
            raise RuntimeError(f"Model error: {result['error']}")

        return result.get("content", "")


def extract_json_from_response(response: str) -> str:
    """
    Extract JSON content from the model response.
    Args:
        response: Raw text response from the model
    Returns:
        Extracted JSON string
    """
    start_idx = response.find("{")
    end_idx = response.rfind("}")
    if start_idx == -1 or end_idx == -1:
        raise ValueError("No valid JSON found in the response.")
    json_str = response[start_idx:end_idx+1].replace("\n", "")

    return json_str
