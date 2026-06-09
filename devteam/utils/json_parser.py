"""JSON parsing utilities for LLM responses."""
import json
import re


def extract_json(text: str) -> str:
    """Extract JSON from LLM response, handling markdown code fences.

    Args:
        text: Raw LLM response text

    Returns:
        Cleaned JSON string ready for json.loads()
    """
    text = text.strip()

    # Try markdown code fences first (most common from LLMs)
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?```", text, re.DOTALL)
    if match:
        return match.group(1).strip()

    # Try to find a JSON object/array using brace counting
    # This handles nested objects correctly
    for start_char, end_char in [('{', '}'), ('[', ']')]:
        start_idx = text.find(start_char)
        if start_idx == -1:
            continue

        depth = 0
        in_string = False
        escape_next = False

        for i in range(start_idx, len(text)):
            c = text[i]

            if escape_next:
                escape_next = False
                continue

            if c == '\\' and in_string:
                escape_next = True
                continue

            if c == '"' and not escape_next:
                in_string = not in_string
                continue

            if in_string:
                continue

            if c == start_char:
                depth += 1
            elif c == end_char:
                depth -= 1
                if depth == 0:
                    return text[start_idx:i + 1].strip()

    return text


def parse_json_response(text: str) -> dict:
    """Parse JSON from LLM response with error handling.

    Args:
        text: Raw LLM response text

    Returns:
        Parsed dict

    Raises:
        json.JSONDecodeError: If JSON cannot be parsed
    """
    json_str = extract_json(text)
    return json.loads(json_str)
