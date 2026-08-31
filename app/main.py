"""Compat shim: uvicorn expects app.main:app but the FastAPI instance
lives in apps.api.main. This re-exports it under the expected name so the
Render service (which is hard-coded to `uvicorn app.main:app`) can boot.
"""

from apps.api.main import app

__all__ = ["app"]
