import re

# (pattern, replacement) pairs applied in order to title and text
PATTERNS: list[tuple[re.Pattern, str]] = [
    # Email addresses
    (
        re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"),
        "[email]",
    ),
    # Canadian / North American phone numbers including dot-separated (EC-14)
    (
        re.compile(r"(\+?1[\s\-.]?)?\(?\d{3}\)?[\s\-.]?\d{3}[\s\-.]?\d{4}"),
        "[phone]",
    ),
    # Account / transaction IDs (e.g. TXN1234567, RRSP123456)
    (
        re.compile(r"\b[A-Z]{2,4}[\-]?\d{6,12}\b"),
        "[id]",
    ),
    # Name trigger phrases — replace only the name part, keep the trigger phrase
    (
        re.compile(
            r"(?i)(my name is|I'm|I am)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)"
        ),
        r"\1 [name]",
    ),
    # Standalone long numeric strings (7+ digits) — catches account numbers etc.
    (
        re.compile(r"\b\d{7,}\b"),
        "[number]",
    ),
]
