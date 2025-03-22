from datetime import datetime
import json
import os
from pydantic import BaseModel
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.output_parsers.base import BaseOutputParser


class SummaryResponse(BaseModel):
    date: str
    source: str
    summary: dict
    relevant_symbol: str


def dump_failed_text(text: str):
    """
    Dump the failed text to a file in the debug_dumps folder.

    Args:
        text: The text to dump
    """
    if not os.path.exists(".debug_dumps"):
        os.makedirs(".debug_dumps")

    date_str = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f".debug_dumps/{date_str}.txt"

    with open(filename, "w") as file:
        file.write(text)


def get_chat(backend: str = "mlx", model: str = None, **kwargs) -> BaseChatModel:
    """
    Get the chat model based on the backend.
    maybe add a singleton pattern to avoid multiple instances of the same model.
    Args:
        backend: The backend to use (e.g., "azure", "mlx", "ollama")

    Returns:
        The chat model for the specified backend.
    """
    if backend == "azure":
        from langchain_azure_ai.chat_models import AzureAIChatCompletionsModel
        from azure.core.credentials import AzureKeyCredential
        if model is None:
            return AzureAIChatCompletionsModel(
                endpoint=endpoint,
                credential=AzureKeyCredential(api_key),
                **kwargs,
            )
        else:
            return AzureAIChatCompletionsModel(
                endpoint=os.getenv("AZURE_AI_ENDPOINT"),
                credential=AzureKeyCredential(os.getenv("AZURE_AI_API_KEY")),
                model_name=model,
                **kwargs,
            )
    elif backend == "mlx":
        from langchain_community.chat_models import ChatMLX
        from langchain_community.llms.mlx_pipeline import MLXPipeline
        model = model or os.getenv("MLX_MODEL_PATH")
        GEMMA3_KWARGS = {
            "max_tokens": 4096,
            "verbose": True,
            "temp": 1.0,
            "top_p": 0.95,
            "min_p": 0.00,
            "top_k": 64,
        }
        llm = MLXPipeline.from_model_id(model_id=model, cache=True, pipeline_kwargs=kwargs)
        return ChatMLX(llm=llm, **kwargs)
    elif backend == "ollama":
        from langchain_ollama import ChatOllama
        model = model or os.getenv("OLLAMA_MODEL")
        return ChatOllama(model=model, **kwargs)
    else:
        raise ValueError(f"Unsupported backend: {backend}")


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
    json_str = response[start_idx : end_idx + 1].replace("\n", "")

    return json_str


class JsonOutputParser(BaseOutputParser[str]):
    def parse(self, text: str) -> str:
        json_str = extract_json_from_response(text)
        json.loads(json_str)
        return json_str

    @property
    def _type(self) -> str:
        return "json_output_parser"
