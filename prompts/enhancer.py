from lib.config_schema import Prompt as LLMPrompt

# Short name for lazy people
PROMPT = LLMPrompt()

PROMPT.anki_deck = '「JP」：言葉::心「Core」'
PROMPT.anki_ref_field = 'Sentence'

# This model performed really well in my tests
# Close second was "qwen3:8b"
PROMPT.model = "phi4-reasoning"

# Keys have to match the field exactly like how they appear in Anki.
# [[FieldName]] will be dynamically filled with the fields content.
PROMPT.inputs = {
    "Word": "[[Word]]",
    "Sentence": "[[Sentence]]",
    "Glossary": "[[Glossary]]",
    "Reading": "[[Reading]]"
}

# Don't mind the single [Brackets], they are just a stylistic choice.
PROMPT.outputs = {
    "Glossary": "Refined or confirmed English translation of input [Word].",
    "Sentence-English": "Natural and accurate English translation of input [Sentence].",
    "Hint": "Explain usage of [Word] in [Sentence]: focus on contextual meaning, part of speech, and key grammatical aspects (e.g., conjugation, common particles)."
}

# This will be fed to the LLM at the end
# get_inputs_json(), get_outputs_json() are what you defined above, but with the data filled in.
PROMPT.template = f"""
Your task is to provide the most accurate and contextually appropriate English translations and usage explanations for Japanese vocabulary.
Review the INPUT DATA, especially the existing [Glossary] and [Sentence] context.

INPUT DATA: {PROMPT.get_inputs_json()}
OUTPUT SCHEMA: {PROMPT.get_outputs_json()}

Output only a valid JSON object. Ensure all specified output fields are present.
"""