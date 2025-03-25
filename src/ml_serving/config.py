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
QWQ_KWARGS = {
    "max_tokens": 64000,
    "verbose": True,
    "temp": 0.6,
    "top_p": 0.95,
    "min_p": 0.00,
    "top_k": 40,
    "repetition_penalty": 1.0,
    "repetition_context_size": 20,
}
# https://github.com/SUFE-AIFLM-Lab/Fin-R1/blob/main/README_en.md
# https://huggingface.co/mingz2022/Fin-R1-mlx-8Bit
FIN_R1_ARGS = {
    "temp": 0.7,
    "temperature": 0.7,
    "top_p": 0.8,
    "max_tokens": 16000,
    "num_predict": 2048,
    "repetition_penalty": 1.05,
    "repeat_penalty": 1.05,
    "repetition_context_size": 20,
    "repeat_last_n": 20,
    "keep_alive": "10m",
    "format": "json",
}
GEMMA3_KWARGS = {
    "max_tokens": 4096,
    "verbose": True,
    "temp": 1.0,
    "top_p": 0.95,
    "min_p": 0.00,
    "top_k": 64,
}
