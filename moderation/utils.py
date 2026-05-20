"""Shared utilities for agent response parsing."""

import ast
import json
import re

_WHITESPACE_ESCAPES = {"\n": "\\n", "\r": "\\r", "\t": "\\t"}


def _escape_newlines_in_strings(s: str) -> str:
    """Escape literal newlines/tabs inside JSON string values."""
    result = []
    in_string = False
    i = 0
    while i < len(s):
        c = s[i]
        if c == "\\" and in_string:
            result.append(c)
            i += 1
            if i < len(s):
                result.append(s[i])
                i += 1
            continue
        if c == '"':
            in_string = not in_string
        if in_string and c in _WHITESPACE_ESCAPES:
            result.append(_WHITESPACE_ESCAPES[c])
        else:
            result.append(c)
        i += 1
    return "".join(result)


def parse_json_response(content: str | None) -> dict:
    """Parse a JSON response from an LLM.

    Handles markdown fences, literal newlines in strings, single-quoted
    Python dicts, and trailing commas.
    """
    if content is None:
        raise ValueError("Model returned no content (finish_reason may be 'length' or 'error')")
    content = content.strip()

    # Strip markdown code fences
    if content.startswith("```"):
        content = re.sub(r"^```(?:json)?\s*\n?", "", content)
        content = re.sub(r"\n?```\s*$", "", content)
        content = content.strip()

    # Extract the first {...} block if surrounded by prose
    match = re.search(r"\{.*\}", content, re.DOTALL)
    if match:
        content = match.group(0)

    # 1. Standard JSON
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # 2. Escape literal newlines/tabs inside strings then retry
    try:
        return json.loads(_escape_newlines_in_strings(content))
    except json.JSONDecodeError:
        pass

    # 3. Python dict literal (handles single quotes)
    try:
        result = ast.literal_eval(content)
        if isinstance(result, dict):
            return result
    except (ValueError, SyntaxError):
        pass

    # 4. Strip trailing commas then retry
    fixed = re.sub(r",\s*([}\]])", r"\1", content)
    try:
        return json.loads(fixed)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Could not parse model response as JSON: {e}\n\nRaw content:\n{content}"
        ) from e
