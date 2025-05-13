import json
import os
import sys
from typing import Set
from rich import print as rprint

def load(filepath: str) -> Set[int]:
    if not os.path.exists(filepath): return set()
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return set(int(item) for item in data) if isinstance(data, list) else set()
    except (IOError, json.JSONDecodeError, ValueError) as e:
        rprint(f"[red]Warn:[/red] Could not load progress from '{filepath}': {e}", file=sys.stderr)
        return set()

def save(filepath: str, ids: Set[int]) -> None:
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(list(ids), f)
    except IOError as e:
        rprint(f"[red]Warn:[/red] Could not save progress to '{filepath}': {e}", file=sys.stderr)