"""Checks used by the evals and the tests.

The main one: every number in an answer must come from the tool output or from the question.
"""
import re

NUMBER = re.compile(r"\d+(?:\.\d+)?")
INSTANCE_NAME = re.compile(r"\b(?:ft|la)\d{2}\b", re.IGNORECASE)


def numbers_in_text(text):
    """All numbers in a text, as strings. Instance names like ft06 are ignored."""
    return NUMBER.findall(INSTANCE_NAME.sub(" ", text))


def numbers_in_data(data):
    """All numbers inside a nested dict or list."""
    found = []
    if isinstance(data, bool):
        return found
    if isinstance(data, (int, float)):
        found.append(float(data))
    elif isinstance(data, dict):
        for value in data.values():
            found.extend(numbers_in_data(value))
    elif isinstance(data, (list, tuple)):
        for value in data:
            found.extend(numbers_in_data(value))
    return found


def matches(token, allowed):
    """A number matches if it equals an allowed number, rounded to the decimals the token shows.

    So "18%" matches 18.18 and "18.2" matches 18.18, but "19" does not.
    """
    decimals = len(token.split(".")[1]) if "." in token else 0
    value = float(token)
    return any(round(number, decimals) == value for number in allowed)


def unmatched_numbers(answer, summary, question):
    """Numbers in the answer that are neither in the tool output nor in the question."""
    allowed = numbers_in_data(summary) + [float(n) for n in numbers_in_text(question)]
    return [token for token in numbers_in_text(answer) if not matches(token, allowed)]


def normalize(arguments):
    return {key: int(value) if isinstance(value, (int, float)) and not isinstance(value, bool) else value
            for key, value in (arguments or {}).items()}


def same_arguments(expected, actual):
    """Do the tool arguments match? Extra keys or different values count as wrong."""
    return normalize(expected) == normalize(actual)
