import os
from openai import AzureOpenAI

from dotenv import load_dotenv
from pydantic import BaseModel
from ollama import Client, generate
load_dotenv(".env")

client = AzureOpenAI(
    azure_endpoint=os.getenv("OPENAI_API_BASE"),
    api_key=os.getenv("OPENAI_API_KEY"),
    api_version=os.getenv("OPENAI_API_VERSION"),
    azure_deployment=os.getenv("DEPLOYMENT_NAME"),
)


class SummaryResponse(BaseModel):
    date: str
    source: str
    summary: dict


SUMMARIZE_PROMPT_V1 = "Summarize the following text in concise and technical bullet points for company symbol {symbol} only, keep relevant figures, numbers and relevant names to be used by further analysis, if no relevant information is provided, return article title and the string, 'no relevant data':\n\n{text}"
SUMMARIZE_PROMPT_V2 = (
    "Extract the core points from the document without any fluff, warnings, or recommendations."
    "Return the extracted information as a valid JSON object in the following format:"
    '{{"date": "date of the document", "source": "who wrote the document", "summary": "core relevant data to the stock from the document only"}}. '
    "Include the company symbol {symbol} in your analysis."
    "If no relevant information is provided, empty JSON object {{}}."
    "Analyze the following text:\n\n{text}"
)
SYSTEM_PROMPT = "You are a financial summarization assistant. Extract key economic and financial insights from raw webpage text, ignoring unrelated content. Keep each summary concise (2-3 sentences)."


ollama_client = Client(
    host="http://127.0.0.1:11434",
    timeout=300,
)

def azure_openai_summarize(symbol: str, text: str) -> str:
    """
    Summarize given text using Azure OpenAI GPT-4 via the openai library.
    Relies on the following environment variables being set:
      OPENAI_API_BASE, OPENAI_API_KEY, OPENAI_API_TYPE,
      OPENAI_API_VERSION, and DEPLOYMENT_NAME.
    """

    if not all([client.base_url, client.api_key]):
        raise ValueError(
            "Azure OpenAI configuration not properly set in environment variables."
        )

    response = client.chat.completions.create(
        model=os.getenv("DEPLOYMENT_NAME"),
        messages=[
            {
                "role": "system",
                "content": "You are a helpful summarization assistant of economic and financial information. You handle text retrieved from webpages the text is retrieved raw from web pages and might contain unrelated links and information. make each summerization two or three sentences only.",
            },
            {
                "role": "user",
                "content": SUMMARIZE_PROMPT_V1.format(symbol=symbol, text=text.strip()),
            },
        ],
        max_completion_tokens=400,
        temperature=0.05,
    )

    summarized_text = response.choices[0].message.content.strip()
    return summarized_text


def ollama_summarize(symbol: str, text: str) -> str:
    """
    Summarize given text using the local Ollama instance with the model llama3.2.
    """
    max_attempts = 3
    attempt = 1
    while attempt <= max_attempts:
        try:
            response = ollama_client.generate(
                prompt=SUMMARIZE_PROMPT_V2.format(symbol=symbol, text=text.strip()),
                format=SummaryResponse.model_json_schema(),
                model="plutus",
                system=SYSTEM_PROMPT,
                options={"temperature": 0.05},
            )
            # Optionally validate the JSON response here to ensure it meets the schema.
            summarized_json = SummaryResponse.model_validate_json(response.response)
            return response.response
        except Exception as e:
            print(f"Attempt {attempt} for symbol {symbol} failed: {e}")
            attempt += 1
            if attempt > max_attempts:
                raise e
