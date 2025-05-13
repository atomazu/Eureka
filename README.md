# Eureka: Anki-deck Enhancer using LLMs

> ⚠️
> This was vibe coded with Gemini 2.5 + some manual editing and testing.

This project enhances Anki flashcards using local Large Language Models (LLMs) via Ollama. It connects to your Anki deck, processes notes based on customizable "prompt" configurations, and updates them with LLM-generated content.

## Core Features

*   **Anki Integration:** Modifies Anki cards via AnkiConnect.
*   **Local LLM Power:** Uses Ollama for content generation (e.g., translations, explanations, summaries).
*   **Customizable Prompts:** Define inputs, outputs, and LLM instructions per task.
*   **Interactive Prompt Setup:** `gen.py` script to easily create new prompt configurations.
*   **Progress Tracking & Dry Run:** Resumes processing and allows testing without live changes.

## Prerequisites

1.  **Python:** Python 3.7+
2.  **Anki Desktop** with the **AnkiConnect Add-on** installed and running.
3.  **Ollama** installed and running, with desired LLM models downloaded (e.g., `ollama pull phi4-reasoning`).

## Quick Setup

1.  **Clone/Download:** Get the project files.
2.  **Virtual Environment (Recommended):**
    ```bash
    cd your-project-directory
    python -m venv .venv
    # Windows PowerShell: .\.venv\Scripts\Activate.ps1
    # Windows CMD: .\.venv\Scripts\activate.bat
    # macOS/Linux: source .venv/bin/activate
    ```
3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```
4.  **Verify:** Ensure Anki (with AnkiConnect) and Ollama are running.

## Configuration

1.  **Prompt Configurations (`prompts/` directory):**
    *   These are Python files (e.g., `prompts/enhancer.py`) that define *how* to process notes for a specific task.
    *   Each file typically creates an `LLMPrompt` instance (often named `p`) and assigns it to a unique variable at the end (e.g., `EnhancerPrompt = p`).
    *   Key settings within a prompt file:
        *   `p.anki_deck`: The exact Anki deck name.
        *   `p.anki_ref_field`: A field for logging/reference.
        *   `p.model` (optional): Specific LLM model for this prompt (overrides global default).
        *   `p.inputs`: Dictionary defining Anki fields used as input to the LLM.
        *   `p.outputs`: Dictionary defining Anki fields to be updated by the LLM, with descriptions for the LLM.
        *   `p.template`: The f-string template for the LLM prompt.
    *   Use `python gen.py` to help create new prompt configuration files. It will guide you and generate a Python module with the necessary structure.

2.  **Main Configuration (`config.py`):**
    *   This file orchestrates the overall settings and selects which prompt configuration is active.
    *   **Activating a Prompt:**
        *   All prompt configurations from the `prompts/` directory are made available via `from prompts import *`.
        *   To select an active prompt, you assign its main variable (e.g., `EnhancerPrompt` from `prompts/enhancer.py`) to `active_prompt_config`:
            ```python
            from prompts import * # Makes EnhancerPrompt, etc., available

            # Set active prompt
            active_prompt_config = EnhancerPrompt # Or any other prompt variable you defined
            ```
    *   **`APP_SETTINGS`**: This central object holds all configurations.
        *   `APP_SETTINGS.active_prompt` is automatically set to your chosen `active_prompt_config`.
        *   `APP_SETTINGS.anki.deck` and `APP_SETTINGS.anki.ref_field` are automatically derived from the `active_prompt_config`.
        *   **Global LLM Settings:**
            *   `APP_SETTINGS.llm.default_model`: Sets a default LLM model (e.g., `"phi4-reasoning"`) if the active prompt doesn't specify one.
            *   Other settings like `api_url`, `timeout`, logging options.
        *   **Global Script Settings:**
            *   `APP_SETTINGS.script.dry_run`: `True` to test without changing Anki (default in your example), `False` for live updates.
            *   `APP_SETTINGS.script.save_progress`: `True` to save and resume progress (default `False` in your example).
            *   `APP_SETTINGS.script.progress_file`: Automatically named based on the active prompt's deck (e.g., `Your_Anki_Deck_Name_progress.json`).
        *   Anki/Ollama URLs and other advanced settings are also configurable here (often commented out by default if standard values are expected).

## Usage

1.  **Generate a New Prompt (Optional, if existing ones don't suit):**
    ```bash
    python gen.py
    ```
    *   Follow the interactive steps. It connects to Anki to list decks/fields.
    *   After generation, it will tell you the variable name (e.g., `MyNewPrompt`).
    *   Update `config.py` to import and use this new prompt (see "Configuration" above).

2.  **Configure `config.py`:**
    *   Ensure `active_prompt_config` points to your desired prompt module.
    *   Set `APP_SETTINGS.script.dry_run = False` to make actual changes to Anki.
    *   Review other settings like `default_model` or `save_progress`.

3.  **Run the Processing:**
    ```bash
    python run.py
    ```
    *   Monitor terminal output for progress. Logs are saved in the `log/` directory.

## Troubleshooting Tips

*   **Connection Issues:**
    *   Ensure Anki Desktop (with AnkiConnect) and Ollama are running.
    *   Verify AnkiConnect URL (`APP_SETTINGS.anki.url`) and Ollama URL (`APP_SETTINGS.llm.api_url`) in `config.py` are correct.
*   **LLM Errors (e.g., "Failed decoding LLM JSON"):**
    *   The LLM didn't output valid JSON. Review your prompt template (`p.template` in the active prompt file in `prompts/`).
    *   Ensure the LLM model specified is suitable for JSON output and following instructions.
    *   Check `log/` files for raw LLM responses.
*   **"ImportError" / "ModuleNotFound":**
    *   Make sure your virtual environment is activated.
    *   Run `pip install -r requirements.txt` again if unsure.