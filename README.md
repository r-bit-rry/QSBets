# QSBets
Qiryat Hasharon Bets

## Setup and Installation

Follow these steps to get started with QSBets.

### 1. Install the UV Tool
This project depends on the UV tool. Install it.
```brew
brew install uv
```
macos/linux:
```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
```

windows:
```pwsh
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Or follow these instructions:
https://docs.astral.sh/uv/#highlights


### 2. Create and Activate Virtual Environment with UV Tool
ta-lib dependancy was introduced, and does not have a fallback, on mac you can install the underlying C library with:
```sh
brew install ta-lib
```

Serving of the models can be done with any supported backend of langchain, mainly tested on Azure AI, Ollama, and lm-studio.
can install it with:
```sh
brew install ollama
brew intsall lm-studio
```

It is recommended to isolate project dependencies. Run the following command to create the virtual environment with all extras:
```sh
uv sync --all-extras --prerelease=allow
```

Then, activate the environment:
- On macOS/Linux:
  ```sh
  source venv/bin/activate
  ```
- On Windows:
  ```sh
  venv\\Scripts\\activate
  ```

### 3. Set Up Environment Variables
Create a .env file in the project root (see fill out .env instructions) and add your API keys and configuration parameters. For example:

```env
# API keys and endpoints
BING_API_KEY=your_bing_api_key
OPENAI_API_BASE=https://api.openai.com/v1
OPENAI_API_KEY=your_openai_api_key
OPENAI_API_VERSION=2023-05-15
DEPLOYMENT_NAME=your_deployment_name

# Azure Inference / DeepSeek
AZURE_INFERENCE_CREDENTIAL=your_azure_inference_key
DEEPSEEK_API_BASE=https://your.deepseek.endpoint

# Telegram Notifications
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_CHAT_ID=your_telegram_chat_id
```

Be sure to use secure values for your API keys. This file is automatically ignored by Git thanks to the settings in .gitignore.

### 4. Running the Project
Once the virtual environment is activated and dependencies are installed, you can run the project with:
```sh
python run.py
```
or run individual scripts as needed (e.g., deepseek.py or stock.py).

## Project Workflow & Pending Tasks

The system follows a clear #codebase flow:
1. Data is fetched from multiple sources (Nasdaq, news feeds, SEC filings, etc.).
2. Summaries are generated using Azure OpenAI and/or Ollama services with a dedicated plutus trained llama model (for financial bias).
3. JSON reports are produced for each stock.
4. DeepSeek is used to analyze the reports and generate insights including, rating, enter strategy and exit_strategy.
5. High-rated stocks trigger immediate Telegram notifications and messages with details.
6. Final markdown report is generated for all analyzed stocks.

**Future Tasks:**
- ☑ Integrate additional high-quality news sources and ensure structured aggregation.
- WIP: Develop a dedicated workflow to analyze SEC 10Q and 10K reports.
- ☐ Conduct competitive analysis for specific stocks and related industries.
- ☑ Implement a separate sentiment analysis flow from Reddit to filter out noise. (Using API, WIP for own sentiment analysis)
- ☑ Better technical indicators for stock analysis to support better strategies.
- ☑ Calculate interpertation for techincal indicators, conserving tokens.
- ☑ Event driven analysis, intial stocks list + telegram listening, main local analysis with technical indicators, and final deepseek analysis.
- ☑ Better structured input to improve performance and token cost -> changed to yaml.
- ☐ Add proper backtesting for the strategies.
- ☑ Add logging to failed consulting and summarization attempts for better debugging.

## Acknowledgments
- Thanks to the contributors and maintainers of the libraries and tools used in this project.
- Follow https://huggingface.co/spaces/TheFinAI/IJCAI-2024-FinLLM-Learderboard for the latest updates on financial models and benchmarks.
- Finetuning ideas: https://aclanthology.org/2024.finnlp-2.13.pdf
- More granualar approach: https://arxiv.org/pdf/2502.05878

## Additional Notes
- **API Keys:** Remember to generate and securely store API keys before running the application.
- **VENV:** Always activate your virtual environment before installing new packages or running commands.
- **UV Tool:** If the project requirements change or another uv tool is needed, update the installation command accordingly.
- This project uses both ta-lib, ta-lib can be compiled or downloaded or simply replaced with the ta-lib wheel.

## Contribution Guidelines
- Feel free to submit issues or pull requests for improvements and bug fixes.

Happy coding!

