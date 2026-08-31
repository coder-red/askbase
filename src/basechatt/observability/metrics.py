"""Lightweight metrics helpers for BaseChatt.

We keep a minimal in-process histogram/registry so latency benchmarks and the
API can report P50/P95 without pulling in a heavyweight metrics backend. All
values are in-memory and lossy on restart — that is fine for a $0 local
portfolio system and is clearly not presented as persistent ground truth.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

_lock = threading.Lock()
_histograms: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=10000))
_counters: defaultdict[str, int] = defaultdict(int)


def record(name: str, value: float) -> None:
    with _lock:
        _histograms[name].append(value)


def increment(name: str, amount: int = 1) -> None:
    with _lock:
        _counters[name] += amount


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    values = sorted(values)
    idx = min(len(values) - 1, int(p * len(values)))
    return values[idx]


def summary() -> dict:
    with _lock:
        out: dict = {}
        for name, values in _histograms.items():
            vals = list(values)
            out[name] = {
                "count": len(vals),
                "p50": _percentile(vals, 0.50),
                "p95": _percentile(vals, 0.95),
                "min": min(vals) if vals else 0.0,
                "max": max(vals) if vals else 0.0,
                "mean": sum(vals) / len(vals) if vals else 0.0,
            }
        out["counters"] = dict(_counters)
        return out


class Timer:
    """Context manager that records an elapsed time in seconds to a metric."""

    def __init__(self, name: str) -> None:
        self.name = name

    def __enter__(self) -> Timer:
        self._start = time.perf_counter()
        return self

    def __exit__(self, *exc: object) -> None:
        record(self.name, time.perf_counter() - self._start)
