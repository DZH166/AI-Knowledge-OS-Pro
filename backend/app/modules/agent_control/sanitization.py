from __future__ import annotations

import re


_SENSITIVE_PATTERNS = (
    re.compile(r"(?i)\b(?:api[_-]?key|password|secret|authorization|bearer)\b"),
    re.compile(r"(?i)\bsk-[a-z0-9_-]{8,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b"),
    re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(r"(?i)\b(?:[a-z]:\\users\\|/home/|/users/)[^\s]+"),
)


def sanitize_fact(value: object, *, maximum_length: int = 160) -> str:
    text = str(value).replace("\n", " ").replace("\r", " ")
    if any(pattern.search(text) for pattern in _SENSITIVE_PATTERNS):
        return "[redacted]"
    return text[:maximum_length]


def contains_sensitive_text(value: object) -> bool:
    text = str(value)
    return any(pattern.search(text) for pattern in _SENSITIVE_PATTERNS)
