import re
import json
from typing import Optional, Dict, Any
from rich.live import Live
from rich.panel import Panel
from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn, TimeRemainingColumn, SpinnerColumn, TaskID
from rich.text import Text
from rich.console import Group

class UI: # Renamed from TerminalUI
    def __init__(self, total_items: int, task_desc: str = "Processing Items..."):
        self._last_ref_text: Optional[str] = None
        self._last_output_data: Optional[Dict[str, Any]] = None
        self._task_id: Optional[TaskID] = None
        self._total = total_items
        self._description = task_desc

        self.progress_bar = Progress(
            SpinnerColumn(), TextColumn("[progress.description]{task.description}"), BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(), "<", TimeRemainingColumn(),
            TextColumn("{task.completed} of {task.total} items"),
        )
        self.status_panel = self._build_panel()
        self.layout = Group(self.status_panel, self.progress_bar)
        self.live_display = Live(self.layout, refresh_per_second=4, vertical_overflow="visible", auto_refresh=False)

    def _build_panel(self) -> Panel:
        content = Text()
        if self._last_ref_text:
            ref_cleaned = re.sub('<[^<]+?>', '', self._last_ref_text)
            content.append("Ref: ", style="bold blue")
            content.append(ref_cleaned)

        if self._last_output_data:
            newline = "\n" if self._last_ref_text else ""
            output_str = json.dumps(self._last_output_data, ensure_ascii=False, indent=2)
            content.append(f"{newline}Output: ", style="bold green")
            content.append(output_str[:250] + ('...' if len(output_str) > 250 else ''))
        elif not self._last_ref_text:
            content.append("Waiting for first item...", style="italic dim")

        return Panel(content, title="Last Processed", border_style="dim", width=80)

    def __enter__(self):
        self.live_display.start(refresh=False)
        self._task_id = self.progress_bar.add_task(f"[yellow]{self._description}[/yellow]", total=self._total)
        self._refresh_display()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.live_display.stop()

    def _refresh_display(self):
        self.status_panel = self._build_panel()
        self.live_display.update(Group(self.status_panel, self.progress_bar), refresh=True)

    def update_display(self, ref_text: Optional[str], output_data: Optional[Dict[str, Any]], advance_by: int = 1) -> None:
        if self._task_id is None: raise RuntimeError("UI not started.")
        self._last_ref_text = ref_text
        self._last_output_data = output_data
        if advance_by > 0: self.progress_bar.update(self._task_id, advance=advance_by)
        self._refresh_display()

    def advance_progress(self, count: int = 1) -> None:
        if self._task_id is None: raise RuntimeError("UI not started.")
        if count > 0: self.progress_bar.update(self._task_id, advance=count)
        self._refresh_display() # Refresh to show only progress change, panel uses last state