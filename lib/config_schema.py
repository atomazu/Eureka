import json
from dataclasses import dataclass, field
from typing import List, Dict, Optional

@dataclass
class AnkiConfig:
    url: str = "http://127.0.0.1:8765"
    timeout: int = 30
    verbose_anki: bool = False

@dataclass
class LLMConfig:
    api_url: str = "http://localhost:11434/api/generate"
    default_model: Optional[str] = None
    timeout: int = 180
    retries: int = 3
    retry_delay: int = 10
    verbose_log: bool = False
    log_prompt: bool = False
    log_raw_response: bool = False

@dataclass
class Prompt:
    inputs: Optional[Dict[str, str]] = None
    outputs: Optional[Dict[str, str]] = None
    template: Optional[str] = None
    model: Optional[str] = None
    anki_deck: Optional[str] = None
    anki_ref_field: Optional[str] = None

    def get_inputs_json(self) -> str:
        if not self.inputs: return "{}"
        return json.dumps(self.inputs, ensure_ascii=False, indent=2)

    def get_outputs_json(self) -> str:
        if not self.outputs: return "{}"
        return json.dumps(self.outputs, ensure_ascii=False, indent=2)

    def validate(self) -> List[str]:
        errors = []
        if not self.inputs: errors.append("Prompt.inputs is required.")
        if not self.outputs: errors.append("Prompt.outputs is required.")
        if not self.template: errors.append("Prompt.template is required.")
        if not self.anki_deck: errors.append("Prompt.anki_deck is required.")
        if not self.anki_ref_field: errors.append("Prompt.anki_ref_field is required.")
        return errors

@dataclass
class ScriptConfig:
    progress_file: str = "update_progress.json"
    save_progress: bool = True
    dry_run: bool = False

@dataclass
class AppConfig:
    anki: AnkiConfig = field(default_factory=AnkiConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    active_prompt: Optional[Prompt] = None
    script: ScriptConfig = field(default_factory=ScriptConfig)

    def get_active_model(self) -> str:
        if not self.active_prompt:
            raise ValueError("No active_prompt set.")
        if self.active_prompt.model:
            return self.active_prompt.model
        if self.llm.default_model:
            return self.llm.default_model
        raise ValueError("LLM model undefined (active_prompt.model or llm.default_model).")

    def get_output_fields(self) -> List[str]:
        if not self.active_prompt or not self.active_prompt.outputs:
            raise ValueError("Active prompt or its outputs undefined.")
        return list(self.active_prompt.outputs.keys())

    def validate(self) -> None:
        errors = []
        if self.anki.timeout <= 0: errors.append("anki.timeout must be positive.")

        if self.llm.timeout <= 0: errors.append("llm.timeout must be positive.")
        if self.llm.retries < 0: errors.append("llm.retries cannot be negative.")
        if self.llm.retry_delay < 0: errors.append("llm.retry_delay cannot be negative.")

        if not self.active_prompt:
            errors.append("active_prompt must be configured.")
        else:
            errors.extend(self.active_prompt.validate())
            try:
                self.get_active_model()
                self.get_output_fields()
            except ValueError as e:
                errors.append(str(e))
        
        if not self.anki.deck: errors.append("AppConfig.anki.deck is required (should be set from active_prompt).")
        if not self.anki.ref_field: errors.append("AppConfig.anki.ref_field is required (should be set from active_prompt).")


        if errors:
            raise ValueError(f"Config validation failed:\n - " + "\n - ".join(errors))