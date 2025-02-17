# QSBets
Qiryat Hasharon Bets

## Setup and Installation

Follow these steps to get started with QSBets.

### 1. Install the UV Tool
This project depends on the UV tool. Install it (for example, if using uvicorn):
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

## Additional Notes
- **API Keys:** Remember to generate and securely store API keys before running the application.
- **VENV:** Always activate your virtual environment before installing new packages or running commands.
- **UV Tool:** If the project requirements change or another uv tool is needed, update the installation command accordingly.

Happy coding!

