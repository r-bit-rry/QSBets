"""
Model server implementations and factory for different AI backends.
"""
import os
import json
import random
import threading
import time
import traceback
from typing import Dict, Any, Callable, List

from langchain.schema.messages import SystemMessage, HumanMessage
from ml_serving.model_base import ModelServer, extract_json_from_response

# Import implementations (but not the MLXModelServer class directly to avoid circular imports)
from langchain_azure_ai.chat_models import AzureAIChatCompletionsModel
from langchain_community.chat_models.ollama import ChatOllama
from azure.core.credentials import AzureKeyCredential

# Constants
DEFAULT_TIMEOUT = 300  # seconds
DEFAULT_MAX_RETRIES = 3
DEFAULT_BASE_DELAY = 2.0


class AzureAIServer(ModelServer):
    """Azure OpenAI Model Server implementation."""
    
    def __init__(self, endpoint: str, api_key: str, deployment_name: str, parallelism: int = 1):
        """
        Initialize Azure OpenAI backend.
        
        Args:
            endpoint: Azure AI endpoint URL
            api_key: Azure API key
            deployment_name: Deployment name to use
            parallelism: Max parallel requests (currently not used but kept for API consistency)
        """
        self.model = AzureAIChatCompletionsModel(
            endpoint=endpoint,
            credential=AzureKeyCredential(api_key),
            deployment_name=deployment_name,
            max_tokens=2048,
            temperature=0.6,
            top_p=0.95
        )
        self.request_queue = {}  # For tracking requests if needed
        
    def submit_request(self, 
                      request_id: str,
                      messages: List[Any],
                      callback: Callable[[str, Dict[str, Any]], None],
                      metadata: Dict[str, Any] = None) -> bool:
        """Submit a request to Azure OpenAI."""
        metadata = metadata or {}
        
        # Create a thread to handle the async request
        def process_thread():
            try:
                response = self.model.invoke(messages)
                callback(request_id, {
                    "content": response.content,
                    "metadata": metadata,
                    "processing_time": 0  # Azure doesn't provide this directly
                })
            except Exception as e:
                print(f"Error in Azure AI request {request_id}: {e}")
                callback(request_id, {
                    "error": str(e),
                    "metadata": metadata
                })
                
        thread = threading.Thread(target=process_thread)
        thread.start()
        return True
        
    def process_sync(self, messages: List[Any], metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Process a request synchronously using Azure OpenAI."""
        try:
            response = self.model.invoke(messages)
            return {
                "content": response.content,
                "metadata": metadata or {}
            }
        except Exception as e:
            return {"error": str(e), "metadata": metadata or {}}


class OllamaServer(ModelServer):
    """Ollama Model Server implementation."""
    
    def __init__(self, host: str = "http://127.0.0.1:11434", model_name: str = "plutus3", parallelism: int = 1):
        """
        Initialize Ollama backend.
        
        Args:
            host: Ollama API host URL
            model_name: Model name to use
            parallelism: Max parallel requests (currently not used but kept for API consistency)
        """
        self.model = ChatOllama(
            base_url=host,
            model=model_name,
            temperature=0.05
        )
        
    def submit_request(self, 
                      request_id: str,
                      messages: List[Any],
                      callback: Callable[[str, Dict[str, Any]], None],
                      metadata: Dict[str, Any] = None) -> bool:
        """Submit a request to Ollama."""
        metadata = metadata or {}
        
        # Create a thread to handle the async request
        def process_thread():
            try:
                start_time = time.time()
                response = self.model.invoke(messages)
                proc_time = time.time() - start_time
                
                callback(request_id, {
                    "content": response.content,
                    "metadata": metadata,
                    "processing_time": proc_time
                })
            except Exception as e:
                print(f"Error in Ollama request {request_id}: {e}")
                callback(request_id, {
                    "error": str(e),
                    "metadata": metadata
                })
                
        thread = threading.Thread(target=process_thread)
        thread.start()
        return True
        
    def process_sync(self, messages: List[Any], metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Process a request synchronously using Ollama."""
        try:
            response = self.model.invoke(messages)
            return {
                "content": response.content,
                "metadata": metadata or {}
            }
        except Exception as e:
            return {"error": str(e), "metadata": metadata or {}}


# Singleton server instance
_model_server_instance = None

def get_model_server(
    backend: str = "mlx", 
    model_path: str = None,
    num_workers: int = 3,
    azure_endpoint: str = None,
    azure_api_key: str = None,
    azure_deployment: str = None,
    ollama_host: str = "http://127.0.0.1:11434",
    ollama_model: str = "plutus3"
) -> ModelServer:
    """
    Get or create the singleton model server instance.
    
    Args:
        backend: Backend type ('mlx', 'azure', or 'ollama')
        model_path: Path to MLX model (required for MLX backend)
        num_workers: Number of workers (for MLX) or parallel requests
        azure_endpoint: Azure AI endpoint URL (required for Azure backend)
        azure_api_key: Azure API key (required for Azure backend)
        azure_deployment: Azure deployment name (required for Azure backend)
        ollama_host: Ollama host URL (for Ollama backend)
        ollama_model: Ollama model name (for Ollama backend)
        
    Returns:
        ModelServer instance
    """
    global _model_server_instance
    
    if _model_server_instance is None:
        if backend.lower() == "mlx":
            if not model_path:
                raise ValueError("model_path is required for MLX backend")
            # Import MLX server only when needed, avoiding circular imports
            from ml_serving.mlx_model_server import get_model_server as get_mlx_server
            _model_server_instance = get_mlx_server(model_path, num_workers)
            
        elif backend.lower() == "azure":
            if not all([azure_endpoint, azure_api_key, azure_deployment]):
                raise ValueError("azure_endpoint, azure_api_key, and azure_deployment are required for Azure backend")
            _model_server_instance = AzureAIServer(
                endpoint=azure_endpoint,
                api_key=azure_api_key,
                deployment_name=azure_deployment,
                parallelism=num_workers
            )
            
        elif backend.lower() == "ollama":
            _model_server_instance = OllamaServer(
                host=ollama_host,
                model_name=ollama_model,
                parallelism=num_workers
            )
            
        else:
            raise ValueError(f"Unknown backend type: {backend}")
    
    return _model_server_instance
