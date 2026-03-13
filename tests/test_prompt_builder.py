from talky.prompting import build_asr_initial_prompt, build_llm_system_prompt


def test_build_asr_prompt_contains_dictionary_terms() -> None:
    dictionary = ["MLX", "Qwen", "Alice Chen"]

    prompt = build_asr_initial_prompt(dictionary)

    assert "MLX" in prompt
    assert "Qwen" in prompt
    assert "Alice Chen" in prompt


def test_build_llm_prompt_includes_required_rules() -> None:
    dictionary = ["TensorRT", "Alice Huang"]

    prompt = build_llm_system_prompt(dictionary)

    assert "Remove filler words" in prompt
    assert "Convert spoken style to written style" in prompt
    assert "Output only the cleaned result" in prompt
    assert "Preserve original pronouns and perspective" in prompt
    assert "Preserve the source language" in prompt
    assert "Do not translate" in prompt
    assert "Enforce high scannability" in prompt
    assert "blank lines between blocks" in prompt
    assert "clear section headers" in prompt
    assert "grammatical form consistent" in prompt
    assert "similar in length" in prompt
    assert "symptom-cause-action" in prompt
    assert "ordered or unordered lists" in prompt
    assert "keep one natural paragraph" in prompt
    assert "structure it with short headers" in prompt
    assert "Dictionary is correction-only" in prompt
    assert "You are not a QA assistant" in prompt
    assert "NEVER provide suggestions" in prompt
    assert "strictly bounded to source content" in prompt
    assert "TensorRT" in prompt
    assert "Alice Huang" in prompt
