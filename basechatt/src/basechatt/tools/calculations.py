"""Deterministic financial calculation engine.

All arithmetic for BaseChatt lives here. The LLM is NEVER used for
arithmetic; these functions return machine-readable results with their formula
and inputs so the caller can cite exactly how a number was produced.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation


def _d(value) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    if isinstance(value, str):
        return Decimal(value)
    raise TypeError(f"Cannot convert {type(value)} to Decimal")


@dataclass
class CalcResult:
    value: float | None
    formula: str
    inputs: dict
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "value": self.value,
            "formula": self.formula,
            "inputs": self.inputs,
            "error": self.error,
        }


def _pct(delta: Decimal, base: Decimal) -> Decimal:
    if base == 0:
        return Decimal("0")
    return (delta / base) * Decimal("100")


def calculate_growth(current, previous) -> CalcResult:
    """Single-period growth rate, current vs previous. Returns percent."""
    try:
        c, p = _d(current), _d(previous)
        growth = (c - p) / p * Decimal("100")
        return CalcResult(
            value=float(growth),
            formula="growth = (current - previous) / previous * 100",
            inputs={"current": current, "previous": previous},
        )
    except (InvalidOperation, ZeroDivisionError) as e:
        return CalcResult(value=None, formula="growth", inputs={}, error=str(e))


def calculate_yoy(current, previous) -> CalcResult:
    """Year-over-year growth, same as growth but labelled YoY."""
    result = calculate_growth(current, previous)
    result.formula = "yoy = (current - previous) / previous * 100"
    return result


def calculate_cagr(start, end, years) -> CalcResult:
    """Compound annual growth rate over a number of years. Returns percent."""
    try:
        s, e, y = _d(start), _d(end), _d(years)
        if s <= 0 or y <= 0:
            raise InvalidOperation("start value or years must be positive")
        ratio = e / s
        if ratio <= 0:
            raise InvalidOperation("end/start <= 0")
        cagr = (ratio ** (Decimal("1") / y) - Decimal("1")) * Decimal("100")
        return CalcResult(
            value=float(cagr),
            formula="cagr = ((end/start)^(1/years) - 1) * 100",
            inputs={"start": start, "end": end, "years": years},
        )
    except (InvalidOperation, ZeroDivisionError) as e:
        return CalcResult(value=None, formula="cagr", inputs={}, error=str(e))


def calculate_margin(numerator, denominator) -> CalcResult:
    """Margin as a percentage: numerator / denominator * 100."""
    try:
        n, den = _d(numerator), _d(denominator)
        if den == 0:
            raise InvalidOperation("denominator is zero")
        margin = n / den * Decimal("100")
        return CalcResult(
            value=float(margin),
            formula="margin = numerator / denominator * 100",
            inputs={"numerator": numerator, "denominator": denominator},
        )
    except (InvalidOperation, ZeroDivisionError) as e:
        return CalcResult(value=None, formula="margin", inputs={}, error=str(e))


def calculate_ratio(numerator, denominator) -> CalcResult:
    """Plain ratio: numerator / denominator."""
    try:
        n, den = _d(numerator), _d(denominator)
        if den == 0:
            raise InvalidOperation("denominator is zero")
        ratio = n / den
        return CalcResult(
            value=float(ratio),
            formula="ratio = numerator / denominator",
            inputs={"numerator": numerator, "denominator": denominator},
        )
    except (InvalidOperation, ZeroDivisionError) as e:
        return CalcResult(value=None, formula="ratio", inputs={}, error=str(e))


def compare_periods(current, previous) -> CalcResult:
    """Return both growth and absolute change between two periods."""
    try:
        c, p = _d(current), _d(previous)
        change = c - p
        result = calculate_growth(c, p)
        result.value = float(change)
        result.formula = "change = current - previous"
        result.inputs["current"] = current
        result.inputs["previous"] = previous
        result.inputs["growth_pct"] = None
        growth = calculate_growth(c, p)
        result.inputs["growth_pct"] = growth.value
        return result
    except Exception as e:  # noqa: BLE001
        return CalcResult(value=None, formula="compare_periods", inputs={}, error=str(e))


def round_money(value: float, currency: str = "NGN") -> str:
    """Format a number as money in the given currency."""
    d = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return f"{currency} {d:,.2f}"


CALCULATOR_FUNCTIONS = {
    "calculate_growth": calculate_growth,
    "calculate_yoy": calculate_yoy,
    "calculate_cagr": calculate_cagr,
    "calculate_margin": calculate_margin,
    "calculate_ratio": calculate_ratio,
    "compare_periods": compare_periods,
}
