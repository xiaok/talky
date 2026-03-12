from talky.text_guard import collapse_duplicate_output, enforce_pronoun_consistency


def test_enforce_pronoun_consistency_my_to_your() -> None:
    source = "\u80fd\u542c\u5230\u6211\u7684\u58f0\u97f3\u5417\uff1f"
    output = "\u80fd\u542c\u5230\u60a8\u7684\u58f0\u97f3\u5417\uff1f"

    corrected = enforce_pronoun_consistency(source, output)

    assert corrected == "\u80fd\u542c\u5230\u6211\u7684\u58f0\u97f3\u5417\uff1f"


def test_enforce_pronoun_consistency_preserve_you() -> None:
    source = "\u4f60\u53ef\u4ee5\u542c\u5230\u6211\u7684\u58f0\u97f3\u5417\uff1f"
    output = "\u60a8\u53ef\u4ee5\u542c\u5230\u6211\u7684\u58f0\u97f3\u5417\uff1f"

    corrected = enforce_pronoun_consistency(source, output)

    assert "\u4f60\u53ef\u4ee5" in corrected


def test_collapse_duplicate_output_repeated_lines() -> None:
    text = "Do you hear the people sing?\nDo you hear the people sing?\n"

    collapsed = collapse_duplicate_output(text)

    assert collapsed == "Do you hear the people sing?"
