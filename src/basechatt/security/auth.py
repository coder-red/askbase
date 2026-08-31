"""API authentication.

Supports API-key auth (for programmatic access) and optional JWT. In
development the API can run unauthenticated; production deployments should set
``BASECHATT_API_KEY`` so every request carries an ``X-API-Key`` header.
"""

from __future__ import annotations

import os
import secrets

from basechatt.config.settings import settings


def api_key_enabled() -> bool:
    return bool(_api_key())


def _api_key() -> str:
    return settings.api_key or os.getenv("BASECHATT_API_KEY", "")


def validate_api_key(provided: str | None) -> bool:
    key = _api_key()
    if not key:
        # No key configured -> auth is open (dev mode).
        return True
    if not provided:
        return False
    return secrets.compare_digest(provided.strip(), key)


def require_api_key() -> dict:
    """Return a helper that fastapi dependencies call."""
    return {"enabled": api_key_enabled()}
