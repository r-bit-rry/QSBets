import os
from openai import AzureOpenAI

from summarize.utils import SUMMARIZE_PROMPT_V1


client = AzureOpenAI(
    azure_endpoint=os.getenv("OPENAI_API_BASE"),
    api_key=os.getenv("OPENAI_API_KEY"),
    api_version=os.getenv("OPENAI_API_VERSION"),
    azure_deployment=os.getenv("DEPLOYMENT_NAME"),
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
