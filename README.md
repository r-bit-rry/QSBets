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
brew intsall lm-studio # Typo: should be install
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
Create a `.env` file in the project root (see fill out .env instructions) and add your API keys and configuration parameters. For example:

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
TELEGRAM_CHAT_ID=your_telegram_chat_id # Used for general notifications and sentiment-based analysis requests
```

Be sure to use secure values for your API keys. This file is automatically ignored by Git thanks to the settings in `.gitignore`.

### 4. Running the Project
Once the virtual environment is activated and dependencies are installed, you can run the main event-driven system with:
```sh
python main.py [OPTIONS]
```
**Options:**
*   `--top N`: Analyze the top `N` sentiment stocks periodically (default: 4).
*   `--env PATH`: Specify the path to the `.env` file (default: `.env`).
*   `--daemon`: Run the process in the background (Unix-like systems only).
*   `--analyze SYMBOL[,SYMBOL,...]`: Immediately queue one or more stock symbols for analysis on startup.
*   `--threshold VALUE`: Set the minimum rating (0-100) for a recommendation to be considered high-quality and saved/notified (default: 80.0).

### 5. Running the Dashboard
To visualize the analysis results and technical data, run the Streamlit dashboard:
```sh
streamlit run src/dashboard.py
```

### 6. Running the Backtester
To test the performance of generated strategies against historical data:
```sh
python src/backtesting/backtester.py
```
This will read recommendations from `recommendations.db`, simulate trades, store results in the `strategy_tracking` table, and print a performance report.

## Project Workflow & Pending Tasks

The system follows an event-driven workflow orchestrated by `main.py` and `stock_event_handlers.py`:
1.  **Initialization:** `main.py` starts the event bus and initializes the `StockEventSystem`.
2.  **Event Loops:** Three main threads run concurrently:
    *   **Main Loop:** Processes completed consultation results, handles periodic sentiment stock checks, and manages overall system flow.
    *   **Analysis Loop:** Listens for `STOCK_REQUEST` events (from Telegram, sentiment checks, or command-line), fetches data using `stock.py`, generates a YAML analysis report, and queues it for consultation.
    *   **Consult Loop:** Listens for analysis reports, submits them to the AI service (`consult`) for evaluation, and queues the results.
    *   **Telegram Listener:** Listens for commands (`/analyze`, `/own`) via Telegram.
3.  **Data Fetching & Analysis (`stock.py`):**
    *   Fetches data from multiple sources (Nasdaq, news feeds, social media, etc.).
    *   Calculates technical indicators and generates interpretations (RSI, MACD, BBands, etc.).
    *   Generates preliminary ratings and entry/exit strategies based on technical and fundamental analysis.
    *   Summarizes news and macroeconomic context.
    *   Produces a structured YAML report (`analysis_docs/YYYY/MM/DD/SYMBOL.yaml`).
4.  **AI Consultation (`ai_service.py`):**
    *   Analyzes the YAML report to generate final insights: rating, confidence, reasoning, bullish/bearish factors, macro impact, and refined entry/exit strategies.
    *   Results are saved to `results/results_YYYY-MM-DD.jsonl`.
5.  **Handling Results (`stock_event_handlers.py`):**
    *   Receives consultation results via the `ANALYSIS_COMPLETE` event.
    *   Sends Telegram notifications for direct requests or high-quality results.
    *   Saves high-quality recommendations (meeting threshold) to the `recommendations.db` SQLite database.
6.  **Dashboard (`dashboard.py`):**
    *   Provides a web interface (Streamlit) to view stock overview, technical charts, analysis reports (YAML), and consultation results (JSONL).
    *   Allows comparison between different stock recommendations.
7.  **Backtesting (`backtester.py`):**
    *   Reads saved recommendations from `recommendations.db`.
    *   Fetches historical price data.
    *   Simulates trades based on parsed entry/exit conditions.
    *   Calculates performance (P/L) and saves tracking data to `strategy_tracking` table.
    *   Generates a summary report.

**Future Tasks:**
- ☑ Integrate additional high-quality news sources and ensure structured aggregation.
- WIP: Develop a dedicated workflow to analyze SEC 10Q and 10K reports.
- ☐ Conduct competitive analysis for specific stocks and related industries.
- ☑ Implement a separate sentiment analysis flow from Reddit to filter out noise. (Using API, WIP for own sentiment analysis)
- ☑ Better technical indicators for stock analysis to support better strategies.
- ☑ Calculate interpretation for technical indicators, conserving tokens.
- ☑ Event driven analysis, initial stocks list + telegram listening, main local analysis with technical indicators, and final deepseek analysis.
- ☑ Better structured input to improve performance and token cost -> changed to yaml.
- ☑ Add proper backtesting for the strategies. (Implemented in `backtester.py`)
- ☑ Add logging to failed consulting and summarization attempts for better debugging.

## Acknowledgments
- Thanks to the contributors and maintainers of the libraries and tools used in this project.
- Follow https://huggingface.co/spaces/TheFinAI/IJCAI-2024-FinLLM-Learderboard for the latest updates on financial models and benchmarks.
- Finetuning ideas: https://aclanthology.org/2024.finnlp-2.13.pdf
- More granular approach: https://arxiv.org/pdf/2502.05878

## Additional Notes
- **API Keys:** Remember to generate and securely store API keys before running the application.
- **VENV:** Always activate your virtual environment before installing new packages or running commands.
- **UV Tool:** If the project requirements change or another uv tool is needed, update the installation command accordingly.
- **TA-Lib:** This project uses `ta-lib`. Ensure the underlying C library is installed (`brew install ta-lib` on macOS) before installing the Python package via `uv sync`.
- **Database:** Recommendations and backtesting results are stored in `recommendations.db`.

## Contribution Guidelines
- Feel free to submit issues or pull requests for improvements and bug fixes.

Happy coding!