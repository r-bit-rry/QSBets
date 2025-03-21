"""
Configuration for AI services.
"""
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# MLX Configuration
MLX_MODEL_PATH = os.environ.get("MLX_MODEL_PATH", "/Users/roy.belio/Repos/QSBets/ml_serving/mlx_model") # fino1 llama 8b is the one I downloaded and quantized
MLX_NUM_WORKERS = int(os.environ.get("MLX_NUM_WORKERS", "4"))

# Azure OpenAI Configuration
AZURE_ENDPOINT = os.environ.get("OPENAI_API_BASE", "")
AZURE_API_KEY = os.environ.get("OPENAI_API_KEY", "")
AZURE_API_VERSION = os.environ.get("OPENAI_API_VERSION", "2023-05-15")
AZURE_DEPLOYMENT = os.environ.get("DEPLOYMENT_NAME", "")

# Azure Deepseek Configuration
DS_MODEL = os.environ.get("AZURE_FOUNDRY_DEEPSEEK", "")
DS_REGION = os.environ.get("AZURE_REGION", "eastus")
DS_ENDPOINT = f"https://{DS_MODEL}.{DS_REGION}.models.ai.azure.com" if DS_MODEL else ""
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")

# Ollama Configuration
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "plutus3")

# Default backend to use
DEFAULT_BACKEND = os.environ.get("DEFAULT_AI_BACKEND", "mlx")

def initialize_model_server(backend: str = DEFAULT_BACKEND):
    """
    Initialize the model server with the specified backend.
    
    Args:
        backend: Backend type ('mlx', 'azure', 'ollama')
        
    Returns:
        Initialized model server
    """
    from ml_serving.model_server import get_model_server
    
    if backend.lower() == "mlx":
        return get_model_server(
            backend="mlx",
            model_path=MLX_MODEL_PATH,
            num_workers=MLX_NUM_WORKERS
        )
    
    elif backend.lower() == "azure":
        return get_model_server(
            backend="azure",
            azure_endpoint=AZURE_ENDPOINT,
            azure_api_key=AZURE_API_KEY,
            azure_deployment=AZURE_DEPLOYMENT,
            num_workers=1  # Azure handles parallelism internally
        )
    
    elif backend.lower() == "ollama":
        return get_model_server(
            backend="ollama",
            ollama_host=OLLAMA_HOST,
            ollama_model=OLLAMA_MODEL,
            num_workers=1  # Ollama handles parallelism internally
        )
    
    else:
        raise ValueError(f"Unknown backend: {backend}")
