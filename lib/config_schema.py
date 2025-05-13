# lib/config_schema.py
"""
Defines the configuration data structures and the main setup logic for the application.
"""
import json
import importlib
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple

# --- Data Structures for Configuration ---

@dataclass
class AnkiConfig:
    """Anki connection settings."""
    url: str = "http://127.0.0.1:8765"
    timeout: int = 30  # seconds
    verbose_anki: bool = False
    # Populated from the active prompt during setup:
    deck: Optional[str] = None
    ref_field: Optional[str] = None

@dataclass
class LLMConfig:
    """Large Language Model (LLM) settings."""
    api_url: str = "http://localhost:11434/api/generate" # For Ollama
    default_model: Optional[str] = None # e.g., "phi3", "llama3:8b"
    timeout: int = 180  # seconds
    retries: int = 3
    retry_delay: int = 10  # seconds
    verbose_log: bool = False # Log detailed LLM activity
    log_prompt: bool = False # Log the exact prompt sent to the LLM
    log_raw_response: bool = False # Log the raw JSON (or non-JSON) from LLM

@dataclass
class Prompt: # This is what users define in their prompt_module.py files
    """
    Defines a specific task for the LLM, including inputs, outputs,
    Anki deck/field info, and the prompt template.
    """
    inputs: Optional[Dict[str, str]] = None # e.g., {"Front": "[[Front]]"}
    outputs: Optional[Dict[str, str]] = None # e.g., {"Back": "Translation of [[Front]]"}
    template: Optional[str] = None # The f-string template for the LLM
    model: Optional[str] = None # Specific LLM model for this prompt (overrides LLMConfig.default_model)
    anki_deck: Optional[str] = None # Exact Anki deck name
    anki_ref_field: Optional[str] = None # Anki field used for reference/logging

    def get_inputs_json(self) -> str:
        """Returns inputs as a JSON string for embedding in the template."""
        if not self.inputs: return "{}"
        return json.dumps(self.inputs, ensure_ascii=False, indent=2)

    def get_outputs_json(self) -> str:
        """Returns outputs (schema) as a JSON string for embedding in the template."""
        if not self.outputs: return "{}"
        return json.dumps(self.outputs, ensure_ascii=False, indent=2)

    def validate(self) -> List[str]:
        """Validates that essential fields for a Prompt are set."""
        errors = []
        if not self.inputs: errors.append("Prompt.inputs is required.")
        if not self.outputs: errors.append("Prompt.outputs is required.")
        if not self.template: errors.append("Prompt.template is required.")
        if not self.anki_deck: errors.append("Prompt.anki_deck is required.")
        if not self.anki_ref_field: errors.append("Prompt.anki_ref_field is required.")
        return errors

@dataclass
class ScriptConfig:
    """Script execution settings."""
    # progress_file is auto-generated based on active_prompt.anki_deck
    progress_file: str = "update_progress.json" # Default if anki_deck isn't resolved
    save_progress: bool = True # Save and resume processing from last point
    dry_run: bool = False # False = Live mode (modifies Anki). True = Test mode.

@dataclass
class AppConfig:
    """Main application configuration container."""
    anki: AnkiConfig = field(default_factory=AnkiConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    script: ScriptConfig = field(default_factory=ScriptConfig)
    # active_prompt is set internally during the setup_app_config process
    active_prompt: Optional[Prompt] = field(init=False, default=None)

    def _integrate_prompt_and_derive(self, prompt_instance: Prompt) -> None:
        """Internal: Integrates prompt, derives anki.deck, ref_field, progress_file."""
        if not isinstance(prompt_instance, Prompt):
            raise TypeError(f"Invalid prompt_instance. Expected Prompt, got {type(prompt_instance)}.")

        prompt_errors = prompt_instance.validate()
        if prompt_errors:
            raise ValueError(
                f"Active prompt '{prompt_instance.__class__.__name__}' is invalid:\n - " +
                "\n - ".join(prompt_errors)
            )
        self.active_prompt = prompt_instance

        if not self.active_prompt.anki_deck or not self.active_prompt.anki_ref_field:
             raise ValueError("INTERNAL: Prompt anki_deck or anki_ref_field is None after its own validation.")

        self.anki.deck = self.active_prompt.anki_deck
        self.anki.ref_field = self.active_prompt.anki_ref_field
        deck_name_sanitized = self.active_prompt.anki_deck.replace(" ", "_").replace("::", "_")
        self.script.progress_file = f"{deck_name_sanitized}_progress.json"

    def _validate_fully(self) -> None:
        """Internal: Performs comprehensive validation after prompt integration."""
        errors = []
        # AnkiConfig
        if self.anki.timeout <= 0: errors.append("anki.timeout must be positive.")
        if not self.anki.deck: errors.append("anki.deck is required (should be derived from active_prompt).")
        if not self.anki.ref_field: errors.append("anki.ref_field is required (should be derived from active_prompt).")

        # LLMConfig
        if self.llm.timeout <= 0: errors.append("llm.timeout must be positive.")
        if self.llm.retries < 0: errors.append("llm.retries cannot be negative.")
        if self.llm.retry_delay < 0: errors.append("llm.retry_delay cannot be negative.")

        # ScriptConfig (progress_file should always be set by now)
        if not self.script.progress_file: errors.append("script.progress_file is missing.")

        # Active Prompt integration
        if not self.active_prompt: errors.append("active_prompt was not set during setup.")
        else:
            try: self.get_active_model()
            except ValueError as e: errors.append(str(e))
            try: self.get_output_fields() # Ensures outputs are defined for the active prompt
            except ValueError as e: errors.append(str(e))

        if errors:
            raise ValueError(f"AppConfig validation failed:\n - " + "\n - ".join(errors))

    def get_active_model(self) -> str:
        """Determines the LLM model to use (prompt-specific or default)."""
        if not self.active_prompt: raise ValueError("Cannot get active model: No active_prompt set.")
        if self.active_prompt.model: return self.active_prompt.model
        if self.llm.default_model: return self.llm.default_model
        raise ValueError("LLM model is undefined. Set active_prompt.model or llm.default_model.")

    def get_output_fields(self) -> List[str]:
        """Returns the list of output field names defined in the active prompt."""
        if not self.active_prompt or not self.active_prompt.outputs:
            raise ValueError("Cannot get output fields: Active prompt or its outputs are undefined.")
        return list(self.active_prompt.outputs.keys())


# --- Internal Helper for Loading Prompt Definition ---
def _get_prompt_definition(module_name: str) -> Prompt:
    """Loads PROMPT_DEFINITION from the specified prompt module."""
    if not module_name:
        raise ValueError("Prompt module_name cannot be empty.")
    try:
        prompt_module = importlib.import_module(f"prompts.{module_name}")
    except ImportError:
        raise ImportError(
            f"CONFIG ERROR: Could not import prompt module 'prompts.{module_name}'. "
            f"Ensure 'prompts/{module_name}.py' exists and is importable."
        )
    try:
        prompt_instance = getattr(prompt_module, "PROMPT")
        if not isinstance(prompt_instance, Prompt):
            raise TypeError(
                f"'PROMPT' in '{prompt_module.__name__}' must be an instance of the Prompt class."
            )
        return prompt_instance
    except AttributeError:
        raise AttributeError(
            f"CONFIG ERROR: The prompt module '{prompt_module.__name__}' (from '{prompt_module.__file__}') "
            f"does not define the required 'PROMPT' variable. "
            f"Ensure this variable (an instance of Prompt) is defined in your prompt file."
        )


# --- Top-Level Setup Function (Called from config.py) ---
def setup_app_config(
    prompt_module_name: str,
    base_settings: AppConfig
) -> Tuple[AppConfig, List[str]]:
    """
    Main configuration setup: loads prompt, integrates with base_settings,
    validates everything, and returns the finalized settings.
    Handles all setup-related error reporting and exits on failure.
    """
    try:
        active_prompt = _get_prompt_definition(prompt_module_name)
        base_settings._integrate_prompt_and_derive(active_prompt)
        base_settings._validate_fully()
        expected_fields = base_settings.get_output_fields()
        return base_settings, expected_fields

    except (ImportError, AttributeError, TypeError, ValueError) as e:
        exit(f"--- FATAL CONFIGURATION SETUP ERROR ---\n"
             f"Error details: {e}\n"
             f"Prompt Module Tried: 'prompts/{prompt_module_name}.py'\n"
             f"Please check 'config.py' and the specified prompt file.\n"
             f"---------------------------------")
    except Exception as e: # Catch any other unexpected errors during setup
        exit(f"--- UNEXPECTED ERROR DURING CONFIGURATION SETUP ---\n"
             f"Error: {e}\n"
             f"---------------------------------")