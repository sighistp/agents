"""Security guard - adapted from RAGv3 guard.py"""

import re

# Dangerous patterns to detect (narrowed to reduce false positives)
INJECTION_PATTERNS = [
    r"ignore\s+(previous|above|all)\s+instructions",
    r"ignore\s+all\s+(previous|above)\s+instructions",
    r"forget\s+(everything|all|your\s+instructions)",
    r"new\s+instructions?\s*:",
    r"忽略之前的指令",
    r"忽略以上指令",
    r"disregard\s+(all|previous|your)\s+.*instructions",
]


def check_injection(text: str) -> bool:
    """Check if text contains prompt injection attempts.

    Returns True if a suspicious pattern is detected.
    """
    text_lower = text.lower()
    for pattern in INJECTION_PATTERNS:
        if re.search(pattern, text_lower):
            return True
    return False


def sanitize_input(text: str) -> str:
    """Sanitize user input.

    Removes control characters (except newline/tab) and limits length.
    """
    text = "".join(c for c in text if c.isprintable() or c in "\n\t")
    if len(text) > 10000:
        text = text[:10000]
    return text.strip()
