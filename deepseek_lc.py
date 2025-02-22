from datetime import datetime
import os
from azure.core.credentials import AzureKeyCredential
from dotenv import load_dotenv
import json

import os
from langchain_azure_ai.chat_models import AzureAIChatCompletionsModel
from langchain.prompts import PromptTemplate
# Defining model's endpoint and Azure credentials
DS_Model = os.getenv("AZURE_FOUNDRY_DEEPSEEK")
DS_Region = "eastus"
DS_Endpoint = f"https://{DS_Model}.{DS_Region}.models.ai.azure.com"

model = AzureAIChatCompletionsModel(
    endpoint=DS_Endpoint,
    credential=AzureKeyCredential(os.getenv("DEEPSEEK_API_KEY")),
    max_tokens=2048,
    temperature=0.6,
    top_p=0.95,
    model_kwargs={"stream_options": {"include_usage": True}},
)

DEEPSEEK_PROMPT_V3 = PromptTemplate(
    input_variables=["loadedDocument"],
    template="""Rate stock, use the stock provided data and your general knowledge about industry and market.
Low score ⇒ Sell/Avoid; High score ⇒ Buy/Hold for a few weeks. Briefly explain the key factors and offer buy/exit strategies. Return valid JSON only:
{{
  "rating": 0-100,
  "reasoning": "concise explanation",
  "enter_strategy": "entry plan",
  "exit_strategy": "exit plan"
}}

Stock data:
{loadedDocument}"""
)

def decode_response(content: str):
    # Remove and extract the <think></think> section
    think_start = content.find("<think>")
    think_end = content.find("</think>")
    if think_start != -1 and think_end != -1:
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

def consult(filepath: str):
    try:
        document = open(filepath).read()
        chain = DEEPSEEK_PROMPT_V3 | model 
        response = chain.stream({"loadedDocument": document})
        content = []
        for chunk in response:
            print(chunk.content, end="", flush=True)
            content.append(chunk.content)

        # TODO fix usage on straming api
        # print("Usage:")
        # print("\tPrompt tokens:", response.usage_metadata["input_tokens"])
        # print("\tCompletion tokens:", response.usage_metadata["output_tokens"])
        # print("\tTotal tokens:", response.usage_metadata["total_tokens"])

        return decode_response("".join(content))
    except Exception as e:
        print(f"Error: {e}")

def analyze_folder(folder: str):
    today_str = datetime.now().strftime("%Y-%m-%d")
    for filename in os.listdir(folder):
        if filename.endswith(f"{today_str}.json"):
            filepath = os.path.join(folder, filename)
            print(f"Processing file: {filepath}")
            result = consult(filepath)
            print(f"Result: {result}")

def main():
    start_time = datetime.now()
    consult("./analysis_docs/SEDG_2025-02-20.json")
    end_time = datetime.now()
    print(f"Duration: {end_time - start_time}")


if __name__ == "__main__":
    load_dotenv(".env")
    main()
    # analyze_folder("analysis_docs")
