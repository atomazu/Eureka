# Eureka: Anki-deck Enhancer using LLMs

> ⚠️
> This was vibe coded with Gemini 2.5 + some manual editing and testing.

Enhance your Anki flashcards using local Large Language Models (LLMs) via Ollama. This tool connects to your Anki deck, processes notes based on customizable prompt configurations, and updates them with LLM-generated content.

## Core Features

*   **Anki Integration:** Modifies cards via AnkiConnect.
*   **Local LLM Power:** Uses Ollama for content generation.
*   **Custom Prompts:** Define tasks in `prompts/` (or use `gen.py` to create new ones).
*   **Dry Run & Progress Tracking:** Test safely and resume processing.

## You'll Need

1.  **Python:** Python 3.7+
2.  **Anki Desktop** with **AnkiConnect Add-on** (running).
3.  **Ollama** installed and running, with models downloaded (e.g., `ollama pull phi3`).

## Quick Setup

1.  **Clone/Download:** Get the files.
2.  **Virtual Environment (Recommended):**
    ```bash
    cd your-project-directory
    python -m venv .venv
    # Activate the environment:
    # PowerShell: .\.venv\Scripts\Activate.ps1 
    # CMD: .\.venv\Scripts\activate.bat 
    # macOS/Linux: source .venv/bin/activate 
    ```
3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
4.  **Verify:** Ensure Anki (with AnkiConnect) and Ollama are running.

## How to Use

This project is configured via `config.py` and individual prompt files in the `prompts/` directory.

1.  **Choose or Create a Prompt:**
    *   Prompts are Python files in the `prompts/` directory (e.g., `prompts/enhancer.py`).
    *   Each prompt file defines an LLM task. The main configuration object (an instance of `LLMPrompt` from `lib.config_schema`) inside this file **must be assigned to a variable named `PROMPT`**.
        For example, the `prompts/enhancer.py` file contains:
        ```python
        # In prompts/enhancer.py
        from lib.config_schema import Prompt as LLMPrompt

        # Short name for lazy people
        PROMPT = LLMPrompt() # This is the important variable

        PROMPT.anki_deck = '「JP」：言葉::心「Core」'
        PROMPT.anki_ref_field = 'Sentence'
        PROMPT.model = "phi4-reasoning" 
        # ... other configurations for PROMPT.inputs, PROMPT.outputs, PROMPT.template ...
        ```
    *   To create a new prompt configuration interactively:
        ```bash
        python gen.py
        ```
        `gen.py` will guide you to define your prompt and save it as a new Python file (e.g., `my_custom_prompt.py`) in the `prompts/` directory. The script will automatically ensure the main prompt object is assigned to the `PROMPT` variable within the generated file. It will then provide "Next Steps" on how to activate this new prompt in `config.py`.

2.  **Edit `config.py`:**
    *   **Set the active prompt module:**
        Open `config.py`. You will find a section for prompt configuration:
        ```python
        # In config.py

        # ... (other imports and AppConfig setup) ...

        # Prompt
        ACTIVE_PROMPT = "enhancer" # This string is the name of the prompt module file (without .py)

        # ... (SETTINGS.anki, SETTINGS.llm, etc.) ...

        # Export
        SETTINGS, EXPECTED_OUTPUT_FIELDS = setup_app_config(
            prompt_module_name=ACTIVE_PROMPT, # This uses the ACTIVE_PROMPT string
            base_settings=SETTINGS
        )
        ```
        Change the string value assigned to `ACTIVE_PROMPT` (e.g., `"enhancer"`) to the **filename (without the `.py` extension)** of your chosen prompt module from the `prompts/` directory. This module must contain the `PROMPT` variable as described in Step 1.
        *   To use the default `prompts/enhancer.py`:
            ```python
            ACTIVE_PROMPT = "enhancer"
            ```
        *   If you created `prompts/my_custom_prompt.py` using `gen.py`:
            ```python
            ACTIVE_PROMPT = "my_custom_prompt"
            ```
        The main script will then automatically load and use the `PROMPT` configuration from `prompts/{ACTIVE_PROMPT}.py`. Settings such as `anki_deck` and `anki_ref_field` defined in your active prompt will be automatically applied to the main `APP_SETTINGS`.
    *   **Enable live changes:** In `config.py`, find `SETTINGS.script.dry_run` and set it to `False` if you want the script to modify your Anki cards. The default is `True` (dry run mode), which prevents accidental changes.
        ```python
        # In config.py, under # Script
        SETTINGS.script.dry_run = False # Set to False for live updates to Anki
        ```
    *   **(Optional) Set global default LLM model:** In `config.py`, you can set `SETTINGS.llm.default_model`.
        ```python
        # In config.py, under # Ollama
        SETTINGS.llm.default_model = "your-ollama-model" # e.g., "phi3", "llama3:8b"
        ```
        This model will be used if the active prompt module does not specify its own `PROMPT.model`. Prompt-specific models (like `PROMPT.model = "phi4-reasoning"` in `prompts/enhancer.py`) will override this global default.
    *   Other settings such as AnkiConnect URL, Ollama API URL, timeouts, and progress saving options are also available in `config.py` (within the `SETTINGS` object). Review them to ensure they match your setup.

3.  **Run the Enhancer:**
    ```bash
    python run.py
    ```
    *   Monitor terminal output. Logs are saved in `log/`.

## Troubleshooting Quick Tips

*   **Connection Issues:**
    *   Are Anki (with AnkiConnect) and Ollama actually running?
    *   Check URLs in `config.py` (e.g., `SETTINGS.anki.url`, `SETTINGS.llm.api_url`) if default `localhost` isn't right for your setup.
*   **LLM Errors / Bad JSON:**
    *   The LLM might not understand your instructions or isn't outputting JSON correctly.
    *   Review the `PROMPT.template` in your active prompt file (in `prompts/`).
    *   Check `log/` files for the raw LLM response to see what went wrong.
*   **ImportError / ModuleNotFound (often related to prompts):**
    *   Did you activate your virtual environment?
    *   In `config.py`, is `ACTIVE_PROMPT` set to the correct filename (without the `.py` extension) of your prompt module? For example, if your prompt is `prompts/my_task.py`, then `ACTIVE_PROMPT` should be `"my_task"`.
    *   Does the prompt file (e.g., `prompts/my_task.py`) exist in the `prompts/` directory and is it correctly named?
    *   Does the prompt file define the main configuration variable as `PROMPT` (e.g., `PROMPT = LLMPrompt(...)`)? `gen.py` handles this automatically for new prompts.
    *   Run `pip install -r requirements.txt` again to ensure all dependencies are installed.