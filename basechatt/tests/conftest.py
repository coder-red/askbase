"""Shared test fixtures for BaseChatt.

Unit tests never touch a live database — ``database/session.py`` builds the
async engine lazily at import time without connecting, so importing models is
safe. Anything that needs Postgres lives under ``tests/integration``.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


@pytest.fixture
def settings_env(monkeypatch):
    """Patch the global settings singleton per-test from a ``BASECHATT_*`` kwargs dict."""

    def _apply(**kwargs):
        from basechatt.config.settings import settings

        for key, value in kwargs.items():
            setattr(settings, key, value)
        return settings

    return _apply
