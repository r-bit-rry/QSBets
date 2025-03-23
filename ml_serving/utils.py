from datetime import datetime
import json
import os
from pydantic import BaseModel
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.output_parsers.base import BaseOutputParser
_chat_instances = {}


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
    Implements a singleton pattern to avoid multiple instances of the same model.

    Args:
        backend: The backend to use (e.g., "azure", "mlx", "ollama")
        model: The model name or path to use

    Returns:
        The chat model for the specified backend.
    """
    # Resolve model if it's None
    if model is None:
        if backend == "mlx":
            model = os.getenv("MLX_MODEL_PATH")
        elif backend == "ollama":
            model = os.getenv("OLLAMA_MODEL")

    # Create a key for the instance cache
    instance_key = (backend, model)

    # Return cached instance if it exists
    if instance_key in _chat_instances:
        return _chat_instances[instance_key]

    # Create a new instance
    if backend == "azure":
        from langchain_azure_ai.chat_models import AzureAIChatCompletionsModel
        from azure.core.credentials import AzureKeyCredential

        if model is None:
            instance = AzureAIChatCompletionsModel(
                endpoint=os.getenv(
                    "AZURE_AI_ENDPOINT"
                ),  # Fixed undefined endpoint variable
                credential=AzureKeyCredential(
                    os.getenv("AZURE_AI_API_KEY")
                ),  # Fixed undefined api_key variable
                **kwargs,
            )
        else:
            instance = AzureAIChatCompletionsModel(
                endpoint=os.getenv("AZURE_AI_ENDPOINT"),
                credential=AzureKeyCredential(os.getenv("AZURE_AI_API_KEY")),
                model_name=model,
                **kwargs,
            )
    elif backend == "mlx":
        from langchain_community.chat_models import ChatMLX
        from langchain_community.llms.mlx_pipeline import MLXPipeline

        llm = MLXPipeline.from_model_id(
            model_id=model, cache=True, pipeline_kwargs=kwargs
        )
        instance = ChatMLX(llm=llm, **kwargs)
    elif backend == "ollama":
        from langchain_ollama import ChatOllama

        instance = ChatOllama(model=model, num_ctx=128000, **kwargs)
    else:
        raise ValueError(f"Unsupported backend: {backend}")

    # Cache the instance
    _chat_instances[instance_key] = instance
    return instance


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
        return json.loads(json_str)
        

    @property
    def _type(self) -> str:
        return "json_output_parser"
