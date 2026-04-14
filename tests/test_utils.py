"""Tests for utility functions"""

from py_miraie_ac.utils import to_float


def test_to_float_valid():
    assert to_float("24.5") == 24.5


def test_to_float_integer_string():
    assert to_float("24") == 24.0


def test_to_float_none():
    assert to_float(None) == -1.0


def test_to_float_invalid_string():
    assert to_float("not-a-number") == -1.0


def test_to_float_empty_string():
    assert to_float("") == -1.0


def test_to_float_zero():
    assert to_float("0") == 0.0


def test_to_float_negative():
    assert to_float("-5.5") == -5.5
