from lib.config_schema import AppConfig, setup_app_config

# Setup
SETTINGS = AppConfig()

# Prompt
ACTIVE_PROMPT = "enhancer"

# Anki
SETTINGS.anki.url = "http://127.0.0.1:8765"
SETTINGS.anki.timeout = 30
SETTINGS.anki.verbose_anki = False

# Ollama
SETTINGS.llm.api_url = "http://localhost:11434/api/generate"
SETTINGS.llm.default_model = None
SETTINGS.llm.timeout = 180
SETTINGS.llm.retries = 3
SETTINGS.llm.retry_delay = 10
SETTINGS.llm.verbose_log = False
SETTINGS.llm.log_prompt = False
SETTINGS.llm.log_raw_response = False

# Script
SETTINGS.script.save_progress = False
SETTINGS.script.dry_run = True

# Export
SETTINGS, EXPECTED_OUTPUT_FIELDS = setup_app_config(
    prompt_module_name=ACTIVE_PROMPT,
    base_settings=SETTINGS
)