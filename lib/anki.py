import json
import sys
from typing import Optional, List, Dict, Any

import requests

class AnkiConnectError(Exception):
    pass

class Anki:
    def __init__(self, url: str, timeout: int, verbose: bool = False):
        if not url: raise ValueError("Anki-Connect URL cannot be empty.")
        if timeout <= 0: raise ValueError("Anki-Connect timeout must be positive.")
        self.url = url
        self.timeout = timeout
        self.verbose = verbose
        if self.verbose: print(f"Anki Init: URL='{self.url}', Timeout={self.timeout}s")

    def _invoke(self, action: str, params: Optional[Dict[str, Any]] = None) -> Any:
        payload = {'action': action, 'params': params or {}, 'version': 6}
        try:
            data = json.dumps(payload).encode('utf-8')
        except TypeError as e:
             raise AnkiConnectError(f"Failed to serialize params for '{action}': {e}") from e

        headers = {'Content-Type': 'application/json'}
        try:
            if self.verbose: print(f" Anki Req: {action} {params}")
            resp = requests.post(self.url, data=data, headers=headers, timeout=self.timeout)
            resp.raise_for_status()
            json_resp = resp.json()
            if self.verbose: print(f" Anki Resp: {json_resp}")
            if json_resp.get('error') is not None:
                err = json_resp['error']
                if "collection is not available" in str(err):
                    raise AnkiConnectError(f"Anki collection busy: {err}")
                raise AnkiConnectError(f"Anki API error for '{action}': {err}")
            if 'result' not in json_resp:
                 raise AnkiConnectError(f"Anki response for '{action}' missing 'result'. Resp: {json_resp}")
            return json_resp.get('result')
        except requests.exceptions.Timeout:
            raise AnkiConnectError(f"Anki timeout ({self.timeout}s) for '{action}'.")
        except requests.exceptions.ConnectionError:
             raise AnkiConnectError(f"Anki connection error at {self.url} for '{action}'.")
        except requests.exceptions.RequestException as e:
             raise AnkiConnectError(f"Anki request failed for '{action}': {e}") from e
        except json.JSONDecodeError as e:
             raise AnkiConnectError(f"Anki JSON decode error for '{action}': {e}") from e

    def get_version(self) -> Optional[int]:
        try:
            version = self._invoke('version')
            return version if isinstance(version, int) else None
        except AnkiConnectError as e:
            print(f"Anki Error (version): {e}", file=sys.stderr)
            return None

    def is_connected(self) -> bool:
        return self.get_version() is not None

    def find_notes(self, query: str) -> List[int]:
        if not query: raise ValueError("Anki query cannot be empty.")
        result = self._invoke('findNotes', params={'query': query})
        if not isinstance(result, list):
             raise AnkiConnectError(f"'findNotes' expected list, got {type(result)}.")
        return result

    def get_notes_data(self, note_ids: List[int]) -> List[Dict[str, Any]]:
        if not isinstance(note_ids, list): raise ValueError("note_ids must be a list.")
        if not note_ids: return []
        result = self._invoke('notesInfo', params={'notes': note_ids})
        if not isinstance(result, list):
            raise AnkiConnectError(f"'notesInfo' expected list, got {type(result)}.")
        return result

    def update_fields(self, note_id: int, fields: Dict[str, str]) -> None:
        if not isinstance(note_id, int) or note_id <= 0:
             raise ValueError("note_id must be positive int.")
        if not isinstance(fields, dict):
             raise ValueError("fields must be a dict.")
        payload = {'id': note_id, 'fields': fields}
        self._invoke('updateNoteFields', params={'note': payload})