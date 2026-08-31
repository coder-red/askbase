"""Input sanitisation and output guards.

Protects the system from prompt-injection via retrieved documents and from
oversized/abusive queries. All trust boundaries funnel through ``sanitize_query``
and ``sanitize_for_log``.
"""

from __future__ import annotations

import re

from basechatt.config.settings import settings

_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_PROMPT_INJECTION_PATTERNS = [
    r"(?i)\b(ignore (all )?(previous|prior|above) (instructions|prompts|context))\b",
    r"(?i)\b(system prompt|developer message)\b",
    r"(?i)\b(forget everything)\b",
    r"(?i)\b(disregard.*instructions)\b",
]


def sanitize_query(query: str) -> str | None:
    """Sanitize and validate a user query.

    Returns the cleaned query, or ``None`` if it should be rejected outright
    (empty after cleaning, or an explicit prompt-injection attempt).
    """
    if not query:
        return None
    cleaned = _CONTROL_RE.sub("", query).strip()
    cleaned = re.sub(r"[ \t\r\n]+", " ", cleaned)
    if not cleaned:
        return None
    if len(cleaned) > settings.max_query_length:
        cleaned = cleaned[: settings.max_query_length]
    if _looks_like_injection(cleaned):
        return None
    return cleaned


def _looks_like_injection(text: str) -> bool:
    return any(re.search(p, text) for p in _PROMPT_INJECTION_PATTERNS)


def sanitize_for_log(text: str, max_len: int = 400) -> str:
    """Trim and strip newlines/control characters for safe log output."""
    return _CONTROL_RE.sub("", (text or "")).replace("\n", " ")[:max_len]


def has_blocked_terms(text: str) -> bool:
    """Block obviously unsafe/malicious request content."""
    blocked = [
        r"(?i)\b(sql|drop|delete|truncate)\b",
        r"(?i)\b(rm\s+-rf|powershell|cmd\.exe)\b",
    ]
    return any(re.search(p, text) for p in blocked)
