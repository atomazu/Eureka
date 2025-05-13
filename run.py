import sys
import json
import signal
import os
import logging
import lib.progress_manager
from datetime import datetime
from typing import Dict, Any
from rich import print as rprint
from rich.panel import Panel
from rich.text import Text
from config import APP_SETTINGS, EXPECTED_OUTPUT_FIELDS
from lib.anki import Anki, AnkiConnectError
from lib.llm import OllamaProcessor, LLMError
from lib.terminal_ui import UI

shutdown_flag = False

def setup_logger():
    log_dir = "log"
    log_file = f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    if not os.path.exists(log_dir): os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, log_file)

    fmt = logging.Formatter('%(asctime)s - %(levelname)s - [%(name)s] %(message)s')
    fh = logging.FileHandler(log_path, encoding='utf-8')
    fh.setFormatter(fmt)
    fh.setLevel(logging.DEBUG)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    if not any(isinstance(h, logging.FileHandler) for h in root_logger.handlers):
        root_logger.addHandler(fh)

    return root_logger

def signal_handler(sig, frame):
    global shutdown_flag
    # Use logger configured by setup_logger
    logging.getLogger(__name__).warning(f"Shutdown signal {sig} received. Finishing current item.")
    # Use rprint for consistency
    rprint(f"\n[bold yellow]Shutdown requested.[/] Finishing current item...", flush=True)
    shutdown_flag = True

def get_note_fields(note_api_data: Dict[str, Any]) -> Dict[str, str]:
    """Extracts field names and string values from Anki note info data."""
    fields = {}
    if 'fields' in note_api_data and isinstance(note_api_data['fields'], dict):
        for name, data in note_api_data['fields'].items():
            # Ensure value is treated as string
            fields[name] = str(data.get('value', ''))
    return fields


def display_run_config(main_log):
    """Displays the current run configuration to console and log."""
    try:
        model = APP_SETTINGS.get_active_model()
        deck = APP_SETTINGS.anki.deck
        ref_field = APP_SETTINGS.anki.ref_field
        dry_run = APP_SETTINGS.script.dry_run
        save_prog = APP_SETTINGS.script.save_progress
        prog_file = APP_SETTINGS.script.progress_file
        anki_url = APP_SETTINGS.anki.url
        llm_url = APP_SETTINGS.llm.api_url

        # Log details
        main_log.info("--- Configuration ---")
        main_log.info(f"Anki Deck:      '{deck}'")
        main_log.info(f"Ref Field:      '{ref_field}'")
        main_log.info(f"LLM Model:      '{model}'")
        main_log.info(f"Anki URL:       '{anki_url}'")
        main_log.info(f"LLM URL:        '{llm_url}'")
        main_log.info(f"Run Mode:       {'DRY RUN' if dry_run else 'LIVE UPDATE'}")
        main_log.info(f"Save Progress:  {save_prog}")
        if save_prog:
            main_log.info(f"Progress File:  '{prog_file}'")
        main_log.info("--------------------")

        # Console display using Rich Panel
        config_text = Text()
        config_text.append("Anki Deck:      ", style="bold blue")
        config_text.append(f"'{deck}'\n")
        config_text.append("Ref Field:      ", style="bold blue")
        config_text.append(f"'{ref_field}'\n")
        config_text.append("LLM Model:      ", style="bold magenta")
        config_text.append(f"'{model}'\n")
        config_text.append("Anki URL:       ", style="dim")
        config_text.append(f"'{anki_url}'\n", style="dim")
        config_text.append("LLM URL:        ", style="dim")
        config_text.append(f"'{llm_url}'\n", style="dim")
        config_text.append("Save Progress:  ", style="bold green" if save_prog else "bold red")
        config_text.append(f"{'Yes' if save_prog else 'No'}")
        if save_prog:
            config_text.append(f" (File: '{prog_file}')", style="dim")

        run_mode_style = "bold yellow" if dry_run else "bold cyan"
        run_mode_text = "DRY RUN" if dry_run else "LIVE UPDATE"

        rprint(Panel(config_text, title="Run Configuration", border_style="green", expand=False))
        rprint(Panel(f"Mode: [{run_mode_style}]{run_mode_text}[/]", title="Status", border_style="yellow", expand=False))
        if dry_run:
            rprint("[bold yellow]*** DRY RUN MODE ACTIVE: Anki notes will NOT be modified. ***[/]")

    except Exception as e:
        # Log and print error if config display fails, but don't exit
        error_msg = f"Failed to display run configuration: {e}"
        main_log.error(error_msg, exc_info=True)
        rprint(f"[bold red]Error:[/bold red] {error_msg}")


def main():
    # Setup logger first
    logger = setup_logger()
    main_log = logging.getLogger(__name__) # Get logger instance for main
    main_log.info("==================== Script Starting ====================")

    # Setup signal handling
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    rprint("[cyan]Initializing...[/]")
    try:
        anki_api = Anki(APP_SETTINGS.anki.url, APP_SETTINGS.anki.timeout, APP_SETTINGS.anki.verbose_anki)
        llm_model = APP_SETTINGS.get_active_model() # Get model name after validation/init
        # Ensure active_prompt is set before initializing OllamaProcessor
        if not APP_SETTINGS.active_prompt:
             raise ValueError("Initialization Error: No active_prompt configured in APP_SETTINGS.")
        llm_proc = OllamaProcessor(APP_SETTINGS.llm, APP_SETTINGS.active_prompt, llm_model)

        # Log successful initialization
        main_log.info("Core components initialized successfully.")

    except (ValueError, TypeError, AttributeError) as e: # Catch config/init errors
        init_error_msg = f"Initialization Error: {e}"
        rprint(f"[bold red]Fatal Error:[/bold red] {init_error_msg}", file=sys.stderr)
        main_log.critical(init_error_msg, exc_info=True)
        sys.exit(1)
    except Exception as e: # Catch unexpected init errors
        init_error_msg = f"Unexpected Initialization Error: {e}"
        rprint(f"[bold red]Fatal Error:[/bold red] {init_error_msg}", file=sys.stderr)
        main_log.critical(init_error_msg, exc_info=True)
        sys.exit(1)

    rprint("[cyan]Connecting to Anki...[/]")
    if not anki_api.is_connected():
        msg = f"Failed to connect to AnkiConnect at {APP_SETTINGS.anki.url}. Is Anki running with AnkiConnect installed and enabled?"
        rprint(f"[bold red]Error:[/bold red] {msg}", file=sys.stderr)
        main_log.critical(msg)
        sys.exit(1)
    main_log.info("Anki connection successful.")
    rprint("[green]Anki connection successful.[/green]")

    # --- Display Configuration ---
    display_run_config(main_log)
    # ---------------------------

    # Load progress
    completed_ids = progress_manager.load(APP_SETTINGS.script.progress_file)
    if completed_ids:
        main_log.info(f"Loaded {len(completed_ids)} previously processed note IDs from '{APP_SETTINGS.script.progress_file}'.")
        rprint(f"[blue]Resuming progress:[/blue] Found {len(completed_ids)} completed items in '{APP_SETTINGS.script.progress_file}'.")


    main_log.info(f"Finding notes with query: 'deck:\"{APP_SETTINGS.anki.deck}\"'")
    rprint(f"\n[cyan]Fetching notes from deck '[bold]{APP_SETTINGS.anki.deck}[/bold]'...[/]")
    try:
        # Ensure deck name is properly quoted for the query
        safe_deck_query = f'deck:"{APP_SETTINGS.anki.deck.replace('"', '\\"')}"'
        all_ids = anki_api.find_notes(safe_deck_query)

        if not all_ids:
            msg = f"No notes found in deck '{APP_SETTINGS.anki.deck}'."
            main_log.info(msg)
            rprint(f"[yellow]{msg}[/yellow]")
            sys.exit(0)
        main_log.info(f"Found {len(all_ids)} total notes in deck.")
        rprint(f"Found {len(all_ids)} total notes.")

        notes_to_run = sorted([nid for nid in all_ids if nid not in completed_ids]) # Sort for consistent order
        num_skipped = len(all_ids) - len(notes_to_run)
        if num_skipped > 0:
            main_log.info(f"Skipping {num_skipped} already processed notes based on progress file.")
            rprint(f"Skipping {num_skipped} notes already processed.")

        if not notes_to_run:
            msg = "All notes in deck have already been processed according to the progress file."
            main_log.info(msg)
            rprint(f"[yellow]{msg}[/yellow]")
            sys.exit(0)

        main_log.info(f"Fetching data for {len(notes_to_run)} remaining notes.")
        rprint(f"Processing [bold]{len(notes_to_run)}[/] notes...")
        note_batch_data = anki_api.get_notes_data(notes_to_run)

    except AnkiConnectError as e:
        # Specific handling for Anki errors during note fetching
        anki_error_msg = f"Anki API Error during note retrieval: {e}"
        rprint(f"[bold red]Fatal Error:[/bold red] {anki_error_msg}", file=sys.stderr)
        main_log.critical(anki_error_msg, exc_info=True)
        sys.exit(1)
    except ValueError as e:
        # Handle potential errors from invalid query format etc.
        value_error_msg = f"Configuration or Value Error during note retrieval: {e}"
        rprint(f"[bold red]Fatal Error:[/bold red] {value_error_msg}", file=sys.stderr)
        main_log.critical(value_error_msg, exc_info=True)
        sys.exit(1)
    except Exception as e: # Catch any other unexpected errors
        unexpected_error_msg = f"Unexpected error during note retrieval: {e}"
        rprint(f"[bold red]Fatal Error:[/bold red] {unexpected_error_msg}", file=sys.stderr)
        main_log.critical(unexpected_error_msg, exc_info=True)
        sys.exit(1)


    processed_count, failed_count = 0, 0

    # Initialize Terminal UI
    term_ui = UI(total_items=len(note_batch_data))
    with term_ui:
        for note_api in note_batch_data:
            if shutdown_flag:
                main_log.warning("Shutdown initiated, breaking processing loop.")
                break # Exit loop gracefully if shutdown requested

            note_id = note_api.get('noteId')
            if not note_id:
                main_log.error(f"Skipping note due to missing 'noteId': {note_api}")
                failed_count += 1
                term_ui.advance_progress() # Still advance progress for skipped item
                continue

            fields = get_note_fields(note_api)
            # Use configured ref_field, provide default if field missing/empty
            ref_text = fields.get(APP_SETTINGS.anki.ref_field, f"NoteID {note_id} (Ref Field Missing)")
            if not ref_text: # Handle empty ref field case
                ref_text = f"NoteID {note_id} (Ref Field Empty)"

            llm_output = None
            llm_error_occurred = False
            try:
                # Log the attempt before calling LLM
                main_log.debug(f"NoteID {note_id}: Processing with LLM. Ref: '{ref_text[:100]}...'")
                llm_output = llm_proc.process(fields)
                main_log.debug(f"NoteID {note_id}: LLM raw output received.") # llm.py might log details

            except LLMError as e:
                 main_log.error(f"NoteID {note_id}: LLM process error: {e}")
                 failed_count += 1
                 llm_error_occurred = True
            except Exception as e: # Catch unexpected errors during LLM processing
                 main_log.exception(f"NoteID {note_id}: Unexpected error during LLM processing.")
                 failed_count += 1
                 llm_error_occurred = True

            # Always advance progress after attempting processing, unless update succeeded below
            should_advance_progress = True

            if llm_error_occurred:
                 term_ui.update_display(ref_text=f"Error processing: {ref_text}", output_data={"error": "LLM failed"}, advance_by=1)
                 should_advance_progress = False # Already advanced in update_display
                 continue # Skip to next note on LLM error

            if llm_output:
                # Validate and filter LLM output
                fields_to_write = {
                    k: str(v) for k, v in llm_output.items()
                    if k in EXPECTED_OUTPUT_FIELDS and isinstance(v, (str, int, float, bool)) # Check type
                }
                missing_keys = [k for k in EXPECTED_OUTPUT_FIELDS if k not in fields_to_write]

                # Check for missing keys or if the resulting dictionary is empty
                if not fields_to_write or missing_keys:
                    # Log detailed info about the invalid output
                    missing_str = f"Missing keys: {missing_keys}" if missing_keys else "Output dict empty after filtering."
                    main_log.warning(f"NoteID {note_id}: LLM output invalid/incomplete. {missing_str} Raw Output: {llm_output}. Filtered: {fields_to_write}")
                    failed_count += 1
                    term_ui.update_display(ref_text=f"Invalid LLM Output: {ref_text}", output_data={"error": "Invalid/Incomplete Data"}, advance_by=1)
                    should_advance_progress = False # Already advanced
                    continue # Skip update, go to next note

                # --- Anki Update Logic ---
                update_ok = False
                run_mode_str = "[DRY RUN]" if APP_SETTINGS.script.dry_run else "[LIVE]"

                if not APP_SETTINGS.script.dry_run:
                    try:
                        main_log.debug(f"NoteID {note_id}: Attempting Anki update with: {fields_to_write}")
                        anki_api.update_fields(note_id, fields_to_write)
                        main_log.info(f"NoteID {note_id} {run_mode_str}: Successfully updated.")
                        update_ok = True
                        if APP_SETTINGS.script.save_progress:
                            completed_ids.add(note_id)
                            progress_manager.save(APP_SETTINGS.script.progress_file, completed_ids)
                            main_log.debug(f"NoteID {note_id}: Added to progress file.")

                    except AnkiConnectError as e:
                        main_log.error(f"NoteID {note_id} {run_mode_str}: Anki update failed: {e}. Data attempted: {fields_to_write}")
                        failed_count += 1
                    except ValueError as e: # Catch potential issues like invalid field names passed to Anki
                         main_log.error(f"NoteID {note_id} {run_mode_str}: Anki update value error: {e}. Data attempted: {fields_to_write}")
                         failed_count += 1
                    except Exception as e: # Catch unexpected update errors
                        main_log.exception(f"NoteID {note_id} {run_mode_str}: Unexpected Anki update error.")
                        failed_count += 1
                else: # Dry run mode
                    main_log.info(f"NoteID {note_id} {run_mode_str}: Update simulated. Data: {fields_to_write}")
                    update_ok = True # Treat as success for progress purposes in dry run

                # --- Update UI and Log based on success ---
                if update_ok:
                    processed_count += 1
                    # Log previous vs new data only on successful update/dry run
                    prev_data_log = {k: fields.get(k, '<FieldNotFound>') for k in fields_to_write}
                    main_log.info(
                        f"NoteID {note_id} {run_mode_str}: Processed Ref='{ref_text[:100]}...', "
                        f"PrevData='{json.dumps(prev_data_log)}', NewData='{json.dumps(fields_to_write)}'"
                    )
                    # Update UI with success info
                    term_ui.update_display(ref_text=ref_text, output_data=fields_to_write, advance_by=1)
                    should_advance_progress = False # Already advanced
                # else: # Anki update failed in non-dry run (failed_count already incremented)
                    # Error logged above, just need to ensure progress bar advances if not already
                    # pass

            else: # llm_output was None or empty (but not due to an exception caught above)
                 main_log.warning(f"NoteID {note_id}: No valid data returned from LLM processor for Ref='{ref_text[:100]}...'.")
                 failed_count += 1
                 term_ui.update_display(ref_text=f"No LLM Data: {ref_text}", output_data={"error": "No data from LLM"}, advance_by=1)
                 should_advance_progress = False # Already advanced

            # Fallback to ensure progress bar advances if no other update path did
            if should_advance_progress:
                term_ui.advance_progress()


    # --- Final Report ---
    main_log.info("==================== Run Complete =====================")
    rprint("\n[bold]--- Run Report ---[/bold]")
    if APP_SETTINGS.script.dry_run:
        rprint("[yellow]Dry run finished. No Anki notes were modified.[/yellow]")

    rprint(f"Successfully processed: [green]{processed_count}[/green]")
    rprint(f"Failed/Skipped items: [red]{failed_count}[/red]")

    # Show final progress count, reload in case file was modified externally (unlikely but safe)
    final_progress = progress_manager.load(APP_SETTINGS.script.progress_file)
    if APP_SETTINGS.script.save_progress:
        rprint(f"Total processed notes recorded in '{APP_SETTINGS.script.progress_file}': [blue]{len(final_progress)}[/blue]")
        main_log.info(f"Final count in progress file '{APP_SETTINGS.script.progress_file}': {len(final_progress)}")
    else:
        rprint("[dim]Progress saving was disabled.[/dim]")
        main_log.info("Progress saving was disabled for this run.")

    if shutdown_flag:
        rprint("[bold yellow]Processing was interrupted by user.[/bold yellow]")
        main_log.warning("Run was interrupted by signal.")

    main_log.info(f"Run Summary: Success={processed_count}, Failed={failed_count}")
    main_log.info("==================== Script Finished ====================")

if __name__ == "__main__":
    main()