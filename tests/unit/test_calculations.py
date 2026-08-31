"""Unit tests for the financial calculation toolbox."""

from __future__ import annotations

import pytest

from basechatt.tools.calculations import (
    CALCULATOR_FUNCTIONS,
    calculate_cagr,
    calculate_growth,
    calculate_margin,
    calculate_ratio,
    calculate_yoy,
    compare_periods,
    round_money,
)


def test_growth_happy_path():
    result = calculate_growth(120, 100)
    assert result.value == 20.0
    assert "current - previous" in result.formula


def test_growth_negative_values():
    result = calculate_growth(50, 100)
    assert result.value == -50.0


def test_growth_zero_base_returns_error():
    result = calculate_growth(10, 0)
    assert result.value is None
    assert result.error is not None


def test_growth_accepts_strings_and_decimals():
    assert calculate_growth("120", "100").value == 20.0


def test_yoy_same_as_growth():
    result = calculate_yoy(220, 200)
    assert result.value == 10.0
    assert result.formula.startswith("yoy")


def test_cagr_three_year():
    result = calculate_cagr(100, 133.1, 3)
    assert result.value == pytest.approx(10.0, abs=0.01)


def test_cagr_rejects_non_positive_start():
    result = calculate_cagr(0, 100, 3)
    assert result.value is None
    assert result.error


def test_margin_and_ratio():
    assert calculate_margin(25, 100).value == 25.0
    assert calculate_ratio(25, 100).value == 0.25
    assert calculate_margin(1, 0).error is not None


def test_compare_periods_includes_growth():
    result = compare_periods(150, 100)
    assert result.value == 50.0
    assert result.inputs["growth_pct"] == 50.0


def test_round_money_format():
    assert round_money(1234.5) == "NGN 1,234.50"
    assert round_money(2.675, "USD") == "USD 2.68"


def test_calculator_registry_has_all_functions():
    for name in (
        "calculate_growth",
        "calculate_yoy",
        "calculate_cagr",
        "calculate_margin",
        "calculate_ratio",
        "compare_periods",
    ):
        assert callable(CALCULATOR_FUNCTIONS[name])
