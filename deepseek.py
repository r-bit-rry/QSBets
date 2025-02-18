import os
from azure.ai.inference import ChatCompletionsClient
from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv
import json

from nasdaq import fetch_nasdaq_data
from stock import Stock

DEEPSEEK_PROMPT_V1 = 'You are an expert trading advisor for small and mid cap companies.Rate stock buy based on the information I give you, which is the most up-to-date.The rating should be between 0 and 100, where 0 is sell immediatly and stay away and 100 is buy immediatly.Provide a short and concise reasoning. Focus on buying and holding stock for a day to few weeks. Suggest a strategy to enter and exit for the specific stock. Output valid JSON only with the following structure {{"rating": 0-100, "reasoning": "Your reasoning here", "strategy": "Your strategy here"}}. The Stock data:\n\n{loadedDocument}'
DEEPSEEK_PROMPT_V2 = """You are an expert small/mid-cap advisor. Ground all stock-related knowledge in the last days provided data but use your general knowledge about industry and market. Assign a total score (0-100) by summing following categories:
- pressReleases (0-10)  
- stockNews (0-10)  
- revenueEarnings (0-20)  
- shortInterest (0-6)  
- institutionalHoldings (0-14)  
- insiderTrading (0-10)  
- description (0-4)  
- secFilings (0-16)
- historicalQuotes (0-10)
Low score ⇒ Sell/Avoid; High score ⇒ Buy/Hold for 1-few weeks. Briefly explain the key factors and offer buy/exit strategies. Return valid JSON only:
{{
  "rating": 0-100,
  "reasoning": "concise explanation",
  "enter_strategy": "entry plan",
  "exit_strategy": "exit plan"
}}

Stock data:\n{loadedDocument}"""

class DeepSeek:
    def __init__(self):
        api_key = os.getenv("AZURE_INFERENCE_CREDENTIAL", "")
        if not api_key:
            raise Exception("A key should be provided to invoke the endpoint")

        self.client = ChatCompletionsClient(
            endpoint=os.getenv("DEEPSEEK_API_BASE", ""),
            credential=AzureKeyCredential(api_key),
        )

    def consult(self, stockDocument: str):
        with open(stockDocument, "r") as file:
            loadedDocument = file.read()

        payload = {
            "messages": [
                {
                    "role": "user",
                    "content": DEEPSEEK_PROMPT_V2.format(loadedDocument=loadedDocument),
                },
            ],
            "max_tokens": 4096,
            "temperature": 0.6,
            "top_p": 0.95,
        }
        response = self.client.complete(payload)
        content = response.choices[0].message.content
        # Remove and extract the <think></think> section
        think_start = content.find("<think>")
        think_end = content.find("</think>")
        if think_start != -1 and think_end != -1:
            thinking_content = content[think_start + len("<think>") : think_end].strip()
            print("Thinking:", thinking_content)
            # Remove the thinking block from content
            content = content[:think_start] + content[think_end + len("</think>") :]
        print("Response:", content)
        print("Model:", response.model)
        print("Usage:")
        print("	Prompt tokens:", response.usage.prompt_tokens)
        print("	Total tokens:", response.usage.total_tokens)
        print("	Completion tokens:", response.usage.completion_tokens)

        start = content.find("{")
        end = content.rfind("}") + 1
        json_str = content[start:end]
        try:
            parsed_json = json.loads(json_str)
        except json.JSONDecodeError as e:
            print("Error decoding JSON:", e)
            parsed_json = {}

        return parsed_json


def main():
    deepseek = DeepSeek()
    deepseek.consult("./analysis_docs/ACHR_2025-02-18.json")


if __name__ == "__main__":
    load_dotenv(".env")
    main()
