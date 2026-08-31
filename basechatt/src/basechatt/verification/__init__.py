"""Verification package: answer verification and citation persistence."""

VERIFIER_SYSTEM = """You verify that a draft answer is faithfully supported by
its listed citations. Return JSON with keys:
{"verdict": "supported"|"partial"|"unsupported"|"unverifiable",
 "issues": ["...explicit problems..."],
 "missing": ["...facts in the answer with no supporting citation..."]}
Be strict: a number must appear in the cited evidence to be claimed.
"""

from basechatt.verification.citations import persist_citations  # noqa: E402
from basechatt.verification.verifier import (  # noqa: E402
    VerificationResult,
    verify_answer,
)

__all__ = ["VERIFIER_SYSTEM", "persist_citations", "VerificationResult", "verify_answer"]
