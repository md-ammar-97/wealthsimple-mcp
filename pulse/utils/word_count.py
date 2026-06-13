import re


def count_words(text: str) -> int:
    """Count words in note body, excluding the Generated footer line."""
    lines = text.splitlines()
    body_lines = [
        line for line in lines
        if not re.match(r"^\*Generated:", line.strip())
    ]
    body = " ".join(body_lines)
    words = body.split()
    return len(words)
