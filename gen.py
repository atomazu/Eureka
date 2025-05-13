import os
import re
import sys
from pathlib import Path
from typing import List, Dict, Optional, Tuple

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt as RichPrompt, Confirm, IntPrompt
from rich.table import Table
from rich.text import Text

try:
    from lib.anki import Anki, AnkiConnectError
    from lib.config_schema import Prompt as LLMPrompt
except ImportError as e:
    print(f"Error: Could not import necessary modules. Make sure anki.py and config_schema.py are accessible: {e}")
    sys.exit(1)

CONSOLE = Console()
ANKI_CONNECT_URL = "http://127.0.0.1:8765"
ANKI_TIMEOUT = 10

def slugify(value: str) -> str:
    """
    Normalizes string for Python module names: lowercase, underscore separators,
    valid identifier format.
    """
    value = re.sub(r'[^\w\s-]', '', value).strip().lower()
    value = re.sub(r'[-\s]+', '_', value)
    if not re.match(r'^[a-zA-Z_]', value):
        value = '_' + value
    value = re.sub(r'[^a-zA-Z0-9_]', '', value)
    if not value:
        return "unnamed_prompt"
    return value

def get_anki_client() -> Optional[Anki]:
    """Initializes and returns an Anki client if connection is successful."""
    try:
        CONSOLE.print("Attempting to connect to AnkiConnect...")
        anki_client = Anki(url=ANKI_CONNECT_URL, timeout=ANKI_TIMEOUT, verbose=False)
        version = anki_client.get_version()
        if version:
            CONSOLE.print(f"[green]Successfully connected to AnkiConnect (Version: {version})[/green]")
            return anki_client
        else:
            CONSOLE.print(f"[red]Failed to connect to AnkiConnect or get version at {ANKI_CONNECT_URL}.[/red]")
            CONSOLE.print("Please ensure Anki is running and AnkiConnect addon is installed and configured.")
            return None
    except AnkiConnectError as e:
        CONSOLE.print(f"[red]AnkiConnect Error: {e}[/red]")
        CONSOLE.print("Please ensure Anki is running and AnkiConnect addon is installed and configured.")
        return None
    except Exception as e:
        CONSOLE.print(f"[red]An unexpected error occurred during Anki connection: {e}[/red]")
        return None

def select_deck(anki: Anki) -> Optional[str]:
    """Lets the user select an Anki deck."""
    try:
        deck_names = anki._invoke("deckNames")
        if not deck_names:
            CONSOLE.print("[yellow]No decks found in Anki.[/yellow]")
            return None
    except AnkiConnectError as e:
        CONSOLE.print(f"[red]Error fetching deck names: {e}[/red]")
        return None

    deck_names.sort()
    CONSOLE.print("\nAvailable Anki Decks:", style="bold blue")
    for i, name in enumerate(deck_names):
        CONSOLE.print(f"{i+1}. {name}")

    while True:
        choice = IntPrompt.ask("Select a deck by number", choices=[str(i+1) for i in range(len(deck_names))])
        selected_deck = deck_names[choice-1]
        if Confirm.ask(f"You selected '[cyan]{selected_deck}[/cyan]'. Confirm?"):
            return selected_deck

def get_model_and_fields_for_deck(anki: Anki, deck_name: str) -> Optional[Tuple[str, List[str]]]:
    """
    Determines the model and fields for notes in a deck.
    If multiple models, asks user to choose.
    """
    try:
        CONSOLE.print(f"\nFetching note types (models) for deck '[cyan]{deck_name}[/cyan]'...")
        safe_deck_query = f'"deck:{deck_name.replace('"', '\\"')}"'
        note_ids = anki.find_notes(safe_deck_query)
        if not note_ids:
            CONSOLE.print(f"[yellow]No notes found in deck '{deck_name}'. Cannot determine fields.[/yellow]")
            # Try to get model for deck even if no notes
            deck_config = anki._invoke("getDeckConfig", params={"deck": deck_name})
            if deck_config and 'mid' in deck_config:
                model = anki._invoke("modelForMod", params={"mod": deck_config['mid']})
                if model and 'name' in model:
                    selected_model_name = model['name']
                    CONSOLE.print(f"Deck '{deck_name}' is configured for note type (model): '[cyan]{selected_model_name}[/cyan]' (no notes found, using deck default).")
                    field_names = anki._invoke("modelFieldNames", params={"modelName": selected_model_name})
                    if field_names:
                         CONSOLE.print(f"Available fields for '{selected_model_name}': [green]{', '.join(field_names)}[/green]")
                         return selected_model_name, field_names
            CONSOLE.print(f"[yellow]Could not determine model or fields for empty deck '{deck_name}'.[/yellow]")
            return None


        notes_info = anki.get_notes_data(note_ids[:10]) # Check first 10 notes
        model_names = sorted(list(set(note['modelName'] for note in notes_info if 'modelName' in note)))

        if not model_names:
            CONSOLE.print(f"[yellow]Could not determine note types for deck '{deck_name}'.[/yellow]")
            return None

        selected_model_name: str
        if len(model_names) == 1:
            selected_model_name = model_names[0]
            CONSOLE.print(f"Deck primarily uses note type (model): '[cyan]{selected_model_name}[/cyan]'")
        else:
            CONSOLE.print("\nMultiple note types found in this deck. Please select one to base the prompt fields on:")
            for i, name in enumerate(model_names):
                CONSOLE.print(f"{i+1}. {name}")
            choice = IntPrompt.ask("Select a note type by number", choices=[str(i+1) for i in range(len(model_names))])
            selected_model_name = model_names[choice-1]
            CONSOLE.print(f"Using note type: '[cyan]{selected_model_name}[/cyan]'")

        field_names = anki._invoke("modelFieldNames", params={"modelName": selected_model_name})
        if not field_names:
            CONSOLE.print(f"[yellow]No fields found for model '{selected_model_name}'.[/yellow]")
            return None
        CONSOLE.print(f"Available fields for '{selected_model_name}': [green]{', '.join(field_names)}[/green]")
        return selected_model_name, field_names

    except AnkiConnectError as e:
        CONSOLE.print(f"[red]Error fetching model/fields: {e}[/red]")
        return None
    except Exception as e:
        CONSOLE.print(f"[red]Unexpected error fetching model/fields: {e}[/red]")
        return None


def select_fields_with_descriptions(
    field_names: List[str],
    prompt_title: str,
    prompt_message: str,
    description_prompt_message: str,
    allow_empty: bool = False
) -> Dict[str, str]:
    """Allows user to select multiple fields and provide specific strings (placeholders/descriptions) for them."""
    selected_fields_with_desc: Dict[str, str] = {}
    CONSOLE.print(Panel(prompt_message, title=prompt_title, expand=False, border_style="blue"))

    if not field_names:
        CONSOLE.print("[yellow]No fields available for selection.[/yellow]")
        return selected_fields_with_desc

    table = Table(title="Available Fields")
    table.add_column("No.", style="dim", justify="right")
    table.add_column("Field Name", style="cyan")

    for i, name in enumerate(field_names):
        table.add_row(str(i+1), name)
    CONSOLE.print(table)

    CONSOLE.print("Enter numbers of fields to select, separated by commas (e.g., 1,3,4).")
    CONSOLE.print("Or type 'all' to select all fields.")

    while True:
        raw_choices = RichPrompt.ask("Your choices").strip().lower()
        chosen_indices = set()
        valid_input = True

        if not raw_choices and allow_empty:
            if Confirm.ask("[yellow]No fields selected. Continue without selecting any?"):
                 return selected_fields_with_desc
            else:
                 continue

        if raw_choices == 'all':
            chosen_indices = set(range(len(field_names)))
            break

        try:
            parts = raw_choices.split(',')
            if not any(p.strip() for p in parts) and raw_choices != "": # handle empty string if not allowed_empty
                 if allow_empty:
                     if Confirm.ask("[yellow]No fields selected. Continue without selecting any?"):
                         return selected_fields_with_desc
                     else:
                         continue
                 else:
                     CONSOLE.print("[yellow]No fields selected. Please enter choices, 'all', or ^C to exit.[/yellow]")
                     continue
            elif not any(p.strip() for p in parts) and raw_choices == "" and not allow_empty: # explicit empty string
                CONSOLE.print("[yellow]No fields selected. Please enter choices, 'all', or ^C to exit.[/yellow]")
                continue


            for item in parts:
                item = item.strip()
                if not item: continue
                idx = int(item) - 1
                if 0 <= idx < len(field_names):
                    chosen_indices.add(idx)
                else:
                    CONSOLE.print(f"[red]Invalid choice: {item}. Number out of range (1-{len(field_names)}).[/red]")
                    valid_input = False
                    break
            if valid_input and chosen_indices:
                break
            elif not chosen_indices and valid_input and not allow_empty: # No valid indices extracted
                 CONSOLE.print(f"[yellow]No valid fields selected. Please enter choices or 'all'.[/yellow]")
            elif not chosen_indices and valid_input and allow_empty and raw_choices : # typed something but was all whitespace or invalid that became empty
                 CONSOLE.print(f"[yellow]No valid fields selected. Please enter choices or 'all', or press Enter for no selection.[/yellow]")
            elif not valid_input:
                 CONSOLE.print(f"[yellow]Please correct your input.[/yellow]")

        except ValueError:
            CONSOLE.print("[red]Invalid input. Please use numbers separated by commas (e.g., 1,3,4) or 'all'.[/red]")
            valid_input = False

    if not chosen_indices:
        CONSOLE.print("[yellow]No fields were selected.[/yellow]") # Should only happen if allow_empty is true and user confirmed
        return selected_fields_with_desc

    CONSOLE.print("\n[bold]Selected fields:[/bold]")
    sorted_indices = sorted(list(chosen_indices))
    for idx in sorted_indices:
        field_name = field_names[idx]
        CONSOLE.print(f"- [cyan]{field_name}[/cyan]")

        default_value = ""
        if "INPUT" in prompt_title: default_value = f"[[{field_name}]]"
        elif "OUTPUT" in prompt_title: default_value = f"Generated content for {field_name}"

        description = RichPrompt.ask(
            f"  Enter text for '[bold]{field_name}[/bold]' ({description_prompt_message})",
            default=default_value
        ).strip()
        selected_fields_with_desc[field_name] = description
    return selected_fields_with_desc


def generate_python_config_string(
    prompt_name_title: str,
    anki_deck: str,
    ref_field: str,
    input_field_configs: Dict[str, str],
    output_field_configs: Dict[str, str],
    llm_model_override: Optional[str],
    base_template_str: Optional[str] = None
) -> str:
    """Generates the Python configuration file content as a string for a prompt module."""

    inputs_str_parts = []
    for k, v_raw in input_field_configs.items():
        v = v_raw.replace('"', '\\"')
        inputs_str_parts.append(f'    "{k}": "{v}",')
    inputs_assignment_str = "\n".join(inputs_str_parts)
    if inputs_assignment_str: inputs_assignment_str = "\n" + inputs_assignment_str + "\n"

    outputs_str_parts = []
    for k, v_raw in output_field_configs.items():
        v = v_raw.replace('"', '\\"')
        outputs_str_parts.append(f'    "{k}": "{v}",')
    outputs_assignment_str = "\n".join(outputs_str_parts)
    if outputs_assignment_str: outputs_assignment_str = "\n" + outputs_assignment_str + "\n"

    if llm_model_override:
        model_section = f'''
# LLM model override for this specific prompt.
# This setting will take precedence over 'LLMConfig.default_model' from the main configuration.
PROMPT.model = "{llm_model_override.replace('"', '\\"')}"
'''
    else:
        model_section = '''
# To use a specific LLM model for THIS prompt (overriding the global default from main config.py),
# uncomment and set the PROMPT.model line below.
# Examples:
# PROMPT.model = "phi4-reasoning"
# PROMPT.model = "qwen3:8b"
#
# If PROMPT.model is not set or is commented out, 'LLMConfig.default_model' from the main config will be used.
'''
    # LLM Prompt Template section
    if base_template_str is None:
        # Default generic template content.
        template_inner_fstring_content = """
Your task is to process the provided data based on the INPUT DATA.
Generate content for the fields specified in the OUTPUT SCHEMA, following any instructions provided in their descriptions.

INPUT DATA: {PROMPT.get_inputs_json()}

OUTPUT SCHEMA: {PROMPT.get_outputs_json()}

General Instructions:
- Output ONLY a valid JSON object.
- Ensure all specified output fields from the OUTPUT SCHEMA are present in your JSON response.
- Adhere to any specific formatting or content instructions provided in the OUTPUT SCHEMA descriptions for each field.
""".strip()
    else:
        # User-provided template
        template_inner_fstring_content = base_template_str

    escaped_template_for_codegen = template_inner_fstring_content.replace('{', '{{').replace('}', '}}').replace('"""', '\\"\\"\\"')
    template_definition_str = f'PROMPT.template = f"""{escaped_template_for_codegen}"""'


    filename_slug = slugify(prompt_name_title)

    config_content = f"""# Generated by generate.py
# Prompt Name: {prompt_name_title}

from lib.config_schema import Prompt as Prompt
# Create new prompt
PROMPT = LLMPrompt()

PROMPT.anki_deck = "{anki_deck.replace('"', '\\"')}"
PROMPT.anki_ref_field = "{ref_field.replace('"', '\\"')}"
{model_section.strip()}

# Keys have to match the field exactly like how they appear in Anki.
# [[FieldName]] will be dynamically filled with the fields content by the main processing script.
PROMPT.inputs = {{{inputs_assignment_str}}}

# The values for 'outputs' are descriptions/examples/instructions for the LLM on how to fill each output field.
PROMPT.outputs = {{{outputs_assignment_str}}}

# This will be fed to the LLM at the end.
# template is an f-string; get_inputs_json() and get_outputs_json() are evaluated
# when this config module is loaded, using the data from PROMPT.inputs and PROMPT.outputs.
# [[FieldName]] placeholders from inputs are substituted later by the main script with actual Anki note data.
{template_definition_str}
"""
    return config_content.strip() + "\n"

def main():
    """Main function to run the prompt generator."""
    CONSOLE.print(Panel("Anki LLM Prompt Generator", style="bold magenta", expand=False))

    anki_client = get_anki_client()
    if not anki_client:
        sys.exit(1)

    selected_deck = select_deck(anki_client)
    if not selected_deck:
        sys.exit(1)

    model_fields_tuple = get_model_and_fields_for_deck(anki_client, selected_deck)
    if not model_fields_tuple:
        CONSOLE.print("[red]Cannot proceed without field information. Exiting.[/red]")
        sys.exit(1)
    _selected_model, all_field_names = model_fields_tuple

    CONSOLE.rule("[bold blue]Define LLM Input Fields[/]")
    input_field_configs = select_fields_with_descriptions(
        all_field_names,
        "LLM Inputs",
        "Select Anki fields to use as [bold]INPUTS[/bold] for the LLM.",
        "Enter placeholder string (e.g., '[[FieldName]]' or fixed text)",
        allow_empty=True
    )
    if not input_field_configs:
        CONSOLE.print("[yellow]Warning: No input fields selected. The LLM prompt might need fixed input text or rely solely on the template structure.[/yellow]")

    CONSOLE.rule("[bold blue]Define LLM Output Fields[/]")
    output_field_configs = select_fields_with_descriptions(
        all_field_names,
        "LLM Outputs",
        "Select Anki fields where LLM [bold]OUTPUTS[/bold] will be stored.",
        "Enter description for LLM (e.g., 'English translation', 'Summary')",
        allow_empty=False
    )
    if not output_field_configs:
        CONSOLE.print("[red]No output fields selected. Cannot generate a useful prompt. Exiting.[/red]")
        sys.exit(1)

    CONSOLE.rule("[bold blue]Select Reference Field[/]")
    CONSOLE.print("The 'Reference Field' is used for logging and context during processing.")
    CONSOLE.print("It should ideally be a field that uniquely identifies or describes the note content.")
    potential_ref_fields = sorted(list(input_field_configs.keys()))
    potential_ref_fields.extend(sorted([f for f in output_field_configs if f not in potential_ref_fields]))
    potential_ref_fields.extend(sorted([f for f in all_field_names if f not in potential_ref_fields]))


    if not potential_ref_fields:
         CONSOLE.print("[red]No fields available to select as reference field. Exiting.[/red]")
         sys.exit(1)

    CONSOLE.print("\nAvailable fields for reference field selection:")
    ref_field_choices_display = [f"{i+1}. {name}" for i, name in enumerate(potential_ref_fields)]
    default_ref_choice_idx = 0
    if input_field_configs:
        try:
            default_ref_choice_idx = potential_ref_fields.index(list(input_field_configs.keys())[0])
        except ValueError:
            default_ref_choice_idx = 0
    elif output_field_configs:
        try:
            default_ref_choice_idx = potential_ref_fields.index(list(output_field_configs.keys())[0])
        except ValueError:
            default_ref_choice_idx = 0


    CONSOLE.print("\n".join(ref_field_choices_display))
    ref_choice_idx_input = IntPrompt.ask(
        "Select a reference field by number",
        choices=[str(i + 1) for i in range(len(potential_ref_fields))],
        default=str(default_ref_choice_idx + 1)
    )
    selected_ref_field = potential_ref_fields[ref_choice_idx_input - 1]
    CONSOLE.print(f"Reference field set to: [cyan]{selected_ref_field}[/cyan]")

    CONSOLE.rule("[bold blue]Prompt Configuration Name[/]")
    input_desc = slugify(list(input_field_configs.keys())[0]) if input_field_configs else "inputs"
    output_desc = slugify(list(output_field_configs.keys())[0]) if output_field_configs else "outputs"
    deck_part = slugify(selected_deck.split('::')[-1])
    prompt_name_default = f"{deck_part}_{input_desc}_to_{output_desc}"

    prompt_name_title = RichPrompt.ask(
        "Enter a descriptive name for this prompt configuration (used for filename and Python variable)",
        default=prompt_name_default
        ).strip()
    if not prompt_name_title:
        CONSOLE.print("[red]Prompt name cannot be empty. Using default.[/red]")
        prompt_name_title = prompt_name_default

    filename_slug = slugify(prompt_name_title)
    CONSOLE.print(f"Generated Python module name: [cyan]{filename_slug}.py[/cyan]")

    CONSOLE.rule("[bold blue]LLM Model Override (Optional)[/]")
    llm_model_override = None
    if Confirm.ask("Do you want to specify a particular LLM model just for THIS prompt (overrides global default)?", default=False):
        llm_model_override = RichPrompt.ask("Enter LLM model name (e.g., 'llama3:instruct', 'qwen2:7b', 'phi4-reasoning')").strip()
        if not llm_model_override:
            llm_model_override = None

    CONSOLE.rule("[bold blue]Custom Prompt Template (Optional)[/]")
    user_template_str: Optional[str] = None
    if Confirm.ask("Do you want to provide a custom LLM prompt template string instead of the default?", default=False):
        CONSOLE.print(Panel(
            Text.from_markup(
            "Enter your custom template. It will be treated as a Python f-string in the generated file.\n"
            "You can use:\n"
            "- `{PROMPT.get_inputs_json()}` (single braces): Evaluated to a JSON string of inputs when the prompt config is loaded.\n"
            "- `{PROMPT.get_outputs_json()}` (single braces): Evaluated to a JSON string of output descriptions when prompt config is loaded.\n"
            "- `[[FieldName]]`: Placeholders for Anki field values (these are substituted by the main processing script later).\n"
            "- To include literal curly braces in the template string itself, use `{{` or `}}`.\n"
            "[dim]Generic Example of what to type here for a custom template:[/dim]\n" # Updated example intro
            "[yellow]Process the '[[SourceText]]' to generate a '[[Summary]]' and '[[Keywords]]'.\n" # Generic example
            "INPUT DATA: {PROMPT.get_inputs_json()}\n"
            "OUTPUT SCHEMA: {PROMPT.get_outputs_json()}\n"
            "Instructions: Ensure the response is a valid JSON object. The '[[Summary]]' should be concise.[/yellow]"
            ),
            title="Custom Template Input", border_style="yellow", width=100
        ))
        user_template_str = RichPrompt.ask("Paste or type your template here (Ctrl+D or Meta+Enter to finish on Unix/macOS, Ctrl+Z then Enter on Windows)")
        if not user_template_str.strip():
            user_template_str = None


    CONSOLE.rule("[bold green]Generate and Save Configuration[/]")
    try:
        config_str = generate_python_config_string(
            prompt_name_title,
            selected_deck,
            selected_ref_field,
            input_field_configs,
            output_field_configs,
            llm_model_override,
            base_template_str=user_template_str
        )
    except Exception as e:
        CONSOLE.print(f"[bold red]Error during configuration string generation: {e}[/bold red]")
        CONSOLE.print_exception(show_locals=True)
        sys.exit(1)

    prompts_dir = Path("prompts")
    prompts_dir.mkdir(exist_ok=True)
    init_file = prompts_dir / "__init__.py"
    init_file.touch(exist_ok=True)

    file_path = prompts_dir / f"{filename_slug}.py"

    CONSOLE.print(f"\nConfiguration will be saved to: [cyan]{file_path}[/cyan]")
    CONSOLE.print(Panel(Text(config_str, "python"), title="Generated Code Preview", border_style="blue", expand=False))

    if Confirm.ask("Proceed to save this configuration?", default=True):
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(config_str)
            CONSOLE.print(f"[bold green]Configuration saved successfully![/bold green]")

            CONSOLE.print("\n[bold white on blue] Next Steps [/]")
            CONSOLE.print(f"1. The new prompt configuration has been saved to: [cyan]prompts/{filename_slug}.py[/cyan]")
            CONSOLE.print(f"   Inside this file, the main prompt settings are assigned to a variable named [bold]PROMPT[/bold].")
            CONSOLE.print(f"2. To use this new prompt, edit your main [bold]config.py[/bold] file.")
            CONSOLE.print(f"3. In `config.py`, find the line [bold]ACTIVE_PROMPT = ...[/bold]")
            CONSOLE.print(f"4. Change it to point to your new prompt's filename (without .py):")
            CONSOLE.print(f"   [cyan]ACTIVE_PROMPT = \"{filename_slug}\"[/cyan]")
            CONSOLE.print(f"5. The application will automatically load the [bold]PROMPT[/bold] variable from [cyan]prompts/{filename_slug}.py[/cyan].")
            CONSOLE.print(f"   Settings like `anki_deck` and `anki_ref_field` from your new prompt will be automatically applied.")
            CONSOLE.print(f"6. Run the main script (e.g., [bold]python run.py[/bold]).")


        except IOError as e:
            CONSOLE.print(f"[bold red]Error saving file:[/bold red] {e}")
        except Exception as e:
            CONSOLE.print(f"[bold red]An unexpected error occurred during file saving:[/bold red] {e}")
            CONSOLE.print_exception(show_locals=False)
    else:
        CONSOLE.print("[yellow]Save cancelled by user.[/yellow]")

    CONSOLE.print("\nPrompt generation process complete.", style="bold magenta")

if __name__ == "__main__":
    script_dir = Path(__file__).parent.resolve()
    if str(script_dir) not in sys.path:
       sys.path.insert(0, str(script_dir))

    try:
        main()
    except KeyboardInterrupt:
        CONSOLE.print("\n[yellow]Operation cancelled by user (Ctrl+C).[/yellow]")
        sys.exit(0)
    except Exception as e:
        CONSOLE.print(f"\n[bold red]An unexpected error occurred:[/bold red]")
        CONSOLE.print_exception(show_locals=True)
        sys.exit(1)