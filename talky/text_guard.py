from __future__ import annotations


def enforce_pronoun_consistency(source_text: str, output_text: str) -> str:
    """
    Keep pronouns aligned with source text to avoid unwanted rewrites.
    """
    source = source_text.strip()
    output = output_text.strip()
    if not source or not output:
        return output_text

    you = "\u4f60"
    formal_you = "\u60a8"
    me = "\u6211"
    my = "\u6211\u7684"
    your = "\u4f60\u7684"
    formal_your = "\u60a8\u7684"

    has_source_you = (you in source) or (formal_you in source)
    has_source_me = me in source

    result = output

    # If source is first-person-only, don't let model rewrite to second person.
    if has_source_me and not has_source_you:
        result = result.replace(formal_your, my).replace(your, my)
        result = result.replace(formal_you, me).replace(you, me)

    # If source uses informal second person, avoid formalizing to polite form.
    if (you in source) and (formal_you not in source):
        result = result.replace(formal_you, you)

    return result


def collapse_duplicate_output(text: str) -> str:
    """
    Collapse obvious duplicate output fragments, e.g.:
    - Two identical lines
    - Entire content repeated twice with only whitespace between copies
    """
    stripped = text.strip()
    if not stripped:
        return text

    lines = [line.strip() for line in stripped.splitlines() if line.strip()]
    if len(lines) >= 2 and all(line == lines[0] for line in lines):
        return lines[0]

    compact = "".join(stripped.split())
    if len(compact) % 2 == 0:
        half = len(compact) // 2
        if compact[:half] == compact[half:]:
            # Return first visible line/segment as canonical output.
            return lines[0] if lines else stripped[: len(stripped) // 2].strip()

    return stripped
