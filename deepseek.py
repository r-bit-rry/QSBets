from datetime import datetime
import os
from azure.ai.inference import ChatCompletionsClient
from azure.core.pipeline.transport import RequestsTransport
from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv
import json

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

DEEPSEEK_PROMPT_V3 = """Rate stock, ground all specific stock-related knowledge in the last days provided data but use your general knowledge about industry and market.
Low score ⇒ Sell/Avoid; High score ⇒ Buy/Hold for a few weeks. Briefly explain the key factors and offer buy/exit strategies. Return valid JSON only:
{{
  "rating": 0-100,
  "reasoning": "concise explanation",
  "enter_strategy": "entry plan",
  "exit_strategy": "exit plan"
}}

Stock data:\n{loadedDocument}"""

class DeepSeek:
    def __init__(self):
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise Exception("A key should be provided to invoke the endpoint")

        self.client = ChatCompletionsClient(
            endpoint=os.getenv("DEEPSEEK_API_BASE", ""),
            credential=AzureKeyCredential(api_key),
            transport=RequestsTransport(read_timeout=600),
        )

    def consult(self, stockDocument: str):
        with open(stockDocument, "r") as file:
            loadedDocument = file.read()

        payload = {
            "messages": [
                {
                    "role": "user",
                    "content": DEEPSEEK_PROMPT_V3.format(loadedDocument=loadedDocument),
                },
            ],
            "max_tokens": 2048,
            "temperature": 0.6,
            "top_p": 0.95,
            # "model": "DEEPSEEK-R1"
        }
        content = ""
        try:
            response = self.client.complete(payload)
            content = response.choices[0].message.content
            print("Response:", content)
            print("Model:", response.model)
            print("Usage:")
            print("	Prompt tokens:", response.usage.prompt_tokens)
            print("	Total tokens:", response.usage.total_tokens)
            print("	Completion tokens:", response.usage.completion_tokens)
        except Exception as e:
            print("Error on deepseek call:", e)
            raise e

        # Remove and extract the <think></think> section
        think_start = content.find("<think>")
        think_end = content.find("</think>")
        if think_start != -1 and think_end != -1:
            thinking_content = content[think_start + len("<think>") : think_end].strip()
            print("Thinking:", thinking_content)
            # Remove the thinking block from content
            content = content[:think_start] + content[think_end + len("</think>") :]

        start = content.find("{")
        end = content.rfind("}") + 1
        json_str = content[start:end]
        try:
            parsed_json = json.loads(json_str)
        except json.JSONDecodeError as e:
            print("Error decoding JSON:", e)
            parsed_json = {}

        return parsed_json


def analyze_folder(folder: str):
    today_str = datetime.now().strftime("%Y-%m-%d")
    deepseek = DeepSeek()
    for filename in os.listdir(folder):
        if filename.endswith(f"{today_str}.json"):
            filepath = os.path.join(folder, filename)
            print(f"Processing file: {filepath}")
            deepseek.consult(filepath)

def main():
    deepseek = DeepSeek()
    deepseek.consult("./analysis_docs/ACHR_2025-02-18.json")


if __name__ == "__main__":
    load_dotenv(".env")
    # main()
    analyze_folder("analysis_docs")
