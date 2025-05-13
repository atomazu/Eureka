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
    *   Each prompt file defines how the LLM processes cards and should assign its main configuration object to a unique variable (e.g., `EnhancerPrompt = p` inside `enhancer.py`).
    *   To create a new prompt configuration interactively:
        ```bash
        python gen.py
        ```
        After running, `gen.py` will tell you the **filename** it created (e.g., `my_prompt.py`) in the `prompts/` directory, and the **variable name** for the prompt defined inside that file (e.g., `MyPrompt`).

2.  **Edit `config.py`:**
    *   **Import and activate your chosen prompt:**
        ```python
        # In config.py

        # 1. Import your prompt module(s) from the 'prompts' directory.
        #    The module name is the filename without '.py'.
        #    Example: if you have 'prompts/enhancer.py' and 'prompts/translator.py'
        from prompts import enhancer, translator #, ... add your prompt module names here

        # 2. Set 'active_prompt_config' to the prompt variable from your imported module.
        #    Use the format: ModuleName.VariableName
        #
        #    Example for 'prompts/enhancer.py' which contains 'EnhancerPrompt = ...':
        active_prompt_config = enhancer.EnhancerPrompt

        #    Or, if you generated 'my_prompt.py' via gen.py, and it defined 'MyPrompt':
        #    from prompts import my_prompt # Make sure to import it first
        #    active_prompt_config = my_prompt.MyPrompt
        ```
    *   **Enable live changes:** Set `APP_SETTINGS.script.dry_run = False`. (Default is `True` to prevent accidental changes).
    *   **(Optional) Set default LLM model:** `APP_SETTINGS.llm.default_model = "your-ollama-model"`.
    *   Other settings (Anki/Ollama URLs, progress saving) are in `config.py` with comments – check there if defaults don't suit you.

3.  **Run the Enhancer:**
    ```bash
    python run.py
    ```
    *   Monitor terminal output. Logs are saved in `log/`.

## Troubleshooting Quick Tips

*   **Connection Issues:**
    *   Are Anki (with AnkiConnect) and Ollama actually running?
    *   Check URLs in `config.py` if default `localhost` isn't right for your setup.
*   **LLM Errors / Bad JSON:**
    *   The LLM might not understand your instructions or isn't outputting JSON correctly.
    *   Review the `p.template` in your active prompt file (in `prompts/`).
    *   Check `log/` files for the raw LLM response to see what went wrong.
*   **ImportError / ModuleNotFound:**
    *   Did you activate your virtual environment?
    *   Did you correctly import your prompt module in `config.py` (e.g., `from prompts import your_prompt_filename_without_py`)?
    *   Run `pip install -r requirements.txt` again.