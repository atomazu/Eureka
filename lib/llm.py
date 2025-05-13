import json
import re
import sys
import time
import logging
import requests
from typing import Optional, Dict, Any
from lib.config_schema import LLMConfig, Prompt

logger = logging.getLogger(__name__)

class LLMError(Exception):
    pass

class OllamaProcessor:
    def __init__(self,
                 llm_config: LLMConfig,
                 active_prompt: Prompt,
                 model_to_use: str):

        if not isinstance(llm_config, LLMConfig):
            raise TypeError("llm_config must be an instance of LLMConfig")
        if not isinstance(active_prompt, Prompt):
            raise TypeError("active_prompt must be an instance of Prompt")
        if not model_to_use:
            raise ValueError("model_to_use cannot be empty")

        self.model_name = model_to_use
        self.api_url = llm_config.api_url
        self.timeout = llm_config.timeout
        self.retries = llm_config.retries
        self.retry_delay = llm_config.retry_delay
        self.verbose_log = llm_config.verbose_log
        self.log_llm_prompt = llm_config.log_prompt
        self.log_llm_response = llm_config.log_raw_response

        self.prompt_template = active_prompt.template
        self.expected_outputs = list(active_prompt.outputs.keys())

        if self.verbose_log:
            logger.debug(f"LLM Init: Model='{self.model_name}', URL='{self.api_url}', Timeout={self.timeout}s")
            logger.debug(f"Expected Output Keys: {self.expected_outputs}")

    def _strip_think_tags(self, text: Optional[str]) -> Optional[str]:
        if not text: return text
        try:
            return re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL).strip()
        except Exception:
             if self.verbose_log: logger.warning("Error stripping <think> tags.", exc_info=True)
             return text

    def _send_request(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        last_exc = None
        for attempt in range(self.retries + 1):
            try:
                resp = requests.post(self.api_url, json=payload, timeout=self.timeout)
                resp.raise_for_status()
                return resp.json()
            except requests.exceptions.Timeout as e:
                last_exc = LLMError(f"Request timed out ({attempt+1}/{self.retries+1})")
                if self.verbose_log: logger.warning(last_exc)
            except requests.exceptions.ConnectionError as e:
                 last_exc = LLMError(f"Connection error ({attempt+1}/{self.retries+1}): {e}")
                 if self.verbose_log: logger.warning(last_exc)
            except requests.exceptions.RequestException as e:
                 err_msg = f"API Request Failed: {e}"
                 resp_text = f" Response: {e.response.text}" if hasattr(e, 'response') and e.response else ""
                 raise LLMError(err_msg + resp_text) from e

            if attempt < self.retries:
                if self.verbose_log: logger.info(f"LLM error. Retrying in {self.retry_delay}s...")
                time.sleep(self.retry_delay)
            else:
                raise LLMError(f"Max retries ({self.retries}) reached. Last: {last_exc}") from last_exc
        raise LLMError("Request failed unexpectedly.") # Should be unreachable

    def process(self, fields: Dict[str, str]) -> Optional[Dict[str, Any]]:
        if not fields:
            if self.verbose_log: logger.info("LLM: Received empty fields dict. Skipping.")
            return None

        current_prompt = self.prompt_template
        try:
            for key, value in fields.items():
                current_prompt = current_prompt.replace(f"[[{key}]]", str(value))
        except Exception as e:
             logger.error("Failed to substitute field values into prompt template.", exc_info=True)
             if self.verbose_log: logger.debug(f"Template: {self.prompt_template}\nFields: {fields}")
             return None

        if self.log_llm_prompt:
            logger.debug(f"--LLM PROMPT--\n{current_prompt}\n--END PROMPT--")

        payload = {"model": self.model_name, "prompt": current_prompt, "stream": False, "options": {"temperature": 0.3}, "format": "json"}

        try:
            response_json = self._send_request(payload)
        except LLMError as e:
             from config import APP_SETTINGS # For ref_field
             ref_text = fields.get(APP_SETTINGS.anki.ref_field, "N/A")
             logger.error(f"LLM API Error for source '{ref_text[:50]}...': {e}")
             return None

        llm_output_str = response_json.get('response')
        if self.log_llm_response:
            logger.debug(f"--LLM RAW RESP--\n{llm_output_str}\n--END RAW RESP--")

        if not isinstance(llm_output_str, str) or not llm_output_str.strip():
            logger.error("LLM Error: Missing or invalid 'response' string in API output.")
            if self.verbose_log: logger.debug(f"Full API Output: {response_json}")
            return None

        clean_output_str = self._strip_think_tags(llm_output_str)

        try:
            output_dict = json.loads(clean_output_str)
            if not isinstance(output_dict, dict):
                logger.error(f"LLM Error: Expected JSON dict, got {type(output_dict)}.")
                if self.verbose_log: logger.debug(f"Parsed non-dict: {output_dict}")
                return None

            missing = [k for k in self.expected_outputs if k not in output_dict]
            if missing:
                logger.warning(f"LLM Warning: Response missing expected keys: {missing}. Got: {output_dict}")
                return None

            if self.verbose_log: logger.debug(f"LLM Success. Output: {output_dict}")
            return output_dict

        except json.JSONDecodeError:
             logger.error("LLM Error: Failed decoding LLM JSON response.", exc_info=True)
             if self.verbose_log: logger.debug(f"String attempted: {clean_output_str[:200]}...")
             return None
        except Exception:
             logger.exception("LLM Error: Unexpected error processing LLM JSON.")
             return None