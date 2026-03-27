from __future__ import annotations


DEFAULT_LLM_PROMPT_TEMPLATE = (
    "You are a professional text-cleaning assistant. Process a raw voice transcript.\n"
    "1. Rewrite only. Preserve facts, intent, pronouns, and perspective.\n"
    "2. Keep the source language. Do not translate.\n"
    "3. Remove fillers and obvious ASR noise; fix likely homophone/term errors.\n"
    "4. Short question input -> output exactly one question sentence. Do not answer or expand.\n"
    "5. For short single-intent input, keep one natural paragraph. No forced bullets or headings.\n"
    "6. For long multi-point input, use scannable structure: short lines, blank lines between blocks, "
    "and clear section headers/lists.\n"
    "7. In parallel lists, keep grammar form consistent and phrase lengths reasonably aligned.\n"
    "8. Dictionary is correction-only. Never insert dictionary terms unless implied by source.\n"
    "9. You are not a QA assistant. No advice, plans, recommendations, or extra knowledge.\n"
    "10. Dictionary terms: [{dictionary}].\n"
    "Output only the cleaned result. No explanations, prefixes, or suffixes."
)


def _format_dictionary(dictionary_terms: list[str]) -> str:
    cleaned = [term.strip() for term in dictionary_terms if term.strip()]
    return ", ".join(cleaned) if cleaned else "(empty)"


def build_asr_initial_prompt(dictionary_terms: list[str]) -> str:
    dictionary_text = _format_dictionary(dictionary_terms)
    return (
        "High-priority term dictionary. Prefer these terms during transcription: "
        f"{dictionary_text}."
    )


def build_llm_system_prompt(
    dictionary_terms: list[str],
    custom_template: str = "",
) -> str:
    dictionary_text = _format_dictionary(dictionary_terms)
    template = custom_template.strip() or DEFAULT_LLM_PROMPT_TEMPLATE
    if "{dictionary}" in template:
        return template.replace("{dictionary}", dictionary_text)
    return template + f"\nDictionary terms: [{dictionary_text}]."
