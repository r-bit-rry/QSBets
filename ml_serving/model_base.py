"""
Base abstract class for model server implementations.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Callable, List

class ModelServer(ABC):
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

# Common utility functions
def extract_json_from_response(response: str) -> str:
    """
    Extract JSON content from the model response.

    Args:
        response: Raw text response from the model

    Returns:
        Extracted JSON string
    """
    import json
    
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
