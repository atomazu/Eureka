from config_schema import AppConfig, AnkiConfig, LLMConfig, ScriptConfig
from prompts import *

# Set active prompt
active_prompt_config = EnhancerPrompt

# --- MAIN CONFIGURATION ---
APP_SETTINGS = AppConfig()

# == Preperation (do not edit) ==
if active_prompt_config and active_prompt_config.anki_deck:
    APP_SETTINGS.anki.deck = active_prompt_config.anki_deck
if active_prompt_config and active_prompt_config.anki_ref_field:
    APP_SETTINGS.anki.ref_field = active_prompt_config.anki_ref_field

APP_SETTINGS.active_prompt = active_prompt_config

# == Global Anki Connection Settings (not prompt-specific) ==
# APP_SETTINGS.anki.url = "http://127.0.0.1:8765" # Default is usually fine
# APP_SETTINGS.anki.timeout = 30 # Default is fine
# APP_SETTINGS.anki.verbose_anki = False

# == Global LLM Base Settings (can be overridden by prompt's .model) ==
APP_SETTINGS.llm.default_model = "phi4-reasoning"
# APP_SETTINGS.llm.api_url = "http://localhost:11434/api/generate" # Default
# APP_SETTINGS.llm.log_prompt = False
# APP_SETTINGS.llm.log_raw_response = False
# APP_SETTINGS.llm.timeout = 180 # Default
# APP_SETTINGS.llm.retries = 3 # Default
# APP_SETTINGS.llm.retry_delay = 10 # Default
# APP_SETTINGS.llm.verbose_log = False # Default


# == Global Script Settings ==
# Currently set for testing, does not modify your Anki deck, or save progress
APP_SETTINGS.script.dry_run = True
APP_SETTINGS.script.save_progress = False

APP_SETTINGS.script.progress_file = active_prompt_config.anki_deck + "_progress.json"


# --- VALIDATE AND EXPORT (do not edit) ---
try:
    APP_SETTINGS.validate()
    EXPECTED_OUTPUT_FIELDS = APP_SETTINGS.get_output_fields()
except ValueError as e:
    print(f"FATAL: Config Error\n{e}")
    exit(1)
except Exception as e:
    print(f"FATAL: Unexpected error during config processing.\n{e}")
    exit(1)