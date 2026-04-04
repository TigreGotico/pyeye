"""Tests for Phase 2: extended builtins (math stats, list ops, RIF/XPath)."""

from __future__ import annotations

import pytest

from pyeye.builtins import (
    math_avg, math_std, math_pcc, math_rms,
    list_select,
    func_concat, func_substring, func_uppercase, func_lowercase,
    func_contains, func_starts_with, func_ends_with,
    func_substring_before, func_substring_after,
    func_normalize_space, func_tokenize,
    pred_equal_to, pred_less_than, pred_greater_than, pred_matches,
    list_length,
)
from pyeye.engine import Engine
from pyeye.term import NamedNode, Literal, Variable, Existential, Triple


NN = NamedNode
V = Variable
L = Literal
E = Existential
T = Triple


class TestMathStats:
    """Extended math builtins."""

    def test_avg(self):
        result = math_avg([L("10"), L("20"), L("30")], None)
        assert result is not None
        assert float(result.value) == 20.0

    def test_std(self):
        result = math_std([L("2"), L("4"), L("4"), L("4"), L("5"), L("5"), L("7"), L("9")], None)
        assert result is not None
        assert abs(float(result.value) - 2.138) < 0.01

    def test_rms(self):
        result = math_rms([L("3"), L("4")], None)
        assert result is not None
        # RMS = sqrt((9 + 16) / 2) = sqrt(12.5) ≈ 3.536
        assert abs(float(result.value) - 3.536) < 0.001

    def test_pcc(self):
        """Pearson correlation: [1,1, 2,2, 3,3] → perfect correlation = 1.0."""
        result = math_pcc([L("1"), L("1"), L("2"), L("2"), L("3"), L("3")], None)
        assert result is not None
        assert abs(float(result.value) - 1.0) < 0.001


class TestListOps:
    """Extended list builtins."""

    def test_select_first(self):
        """Select first element from a list."""
        engine = Engine()
        # Create list: _b1 -> "apple" -> _b2 -> "banana" -> nil
        engine.add_triple(T(E("_b1"), NN("http://www.w3.org/1999/02/22-rdf-syntax-ns#first"), L("apple")))
        engine.add_triple(T(E("_b1"), NN("http://www.w3.org/1999/02/22-rdf-syntax-ns#rest"), E("_b2")))
        engine.add_triple(T(E("_b2"), NN("http://www.w3.org/1999/02/22-rdf-syntax-ns#first"), L("banana")))
        engine.add_triple(T(E("_b2"), NN("http://www.w3.org/1999/02/22-rdf-syntax-ns#rest"), E("nil")))
        result = list_select([E("_b1"), L("1")], engine)
        assert result is not None
        assert result == L("apple")

    def test_select_second(self):
        """Select second element from a list."""
        engine = Engine()
        engine.add_triple(T(E("_b1"), NN("http://www.w3.org/1999/02/22-rdf-syntax-ns#first"), L("apple")))
        engine.add_triple(T(E("_b1"), NN("http://www.w3.org/1999/02/22-rdf-syntax-ns#rest"), E("_b2")))
        engine.add_triple(T(E("_b2"), NN("http://www.w3.org/1999/02/22-rdf-syntax-ns#first"), L("banana")))
        engine.add_triple(T(E("_b2"), NN("http://www.w3.org/1999/02/22-rdf-syntax-ns#rest"), E("nil")))
        result = list_select([E("_b1"), L("2")], engine)
        assert result is not None
        assert result == L("banana")


class TestRIFXPath:
    """RIF/XPath function builtins."""

    def test_func_concat(self):
        result = func_concat([L("hello"), L(" "), L("world")], None)
        assert result is not None
        assert result.value == "hello world"

    def test_func_substring(self):
        result = func_substring([L("hello world"), L("7"), L("5")], None)
        assert result is not None
        assert result.value == "world"

    def test_func_uppercase(self):
        result = func_uppercase([L("hello")], None)
        assert result is not None
        assert result.value == "HELLO"

    def test_func_lowercase(self):
        result = func_lowercase([L("HELLO")], None)
        assert result is not None
        assert result.value == "hello"

    def test_func_contains(self):
        result = func_contains([L("hello world"), L("world")], None)
        assert result is not None
        assert result.value == "true"

    def test_func_starts_with(self):
        result = func_starts_with([L("hello world"), L("hello")], None)
        assert result is not None
        assert result.value == "true"

    def test_func_ends_with(self):
        result = func_ends_with([L("hello world"), L("world")], None)
        assert result is not None
        assert result.value == "true"

    def test_func_substring_before(self):
        result = func_substring_before([L("hello:world"), L(":")], None)
        assert result is not None
        assert result.value == "hello"

    def test_func_substring_after(self):
        result = func_substring_after([L("hello:world"), L(":")], None)
        assert result is not None
        assert result.value == "world"

    def test_func_normalize_space(self):
        result = func_normalize_space([L("  hello   world  ")], None)
        assert result is not None
        assert result.value == "hello world"

    def test_pred_equal_to(self):
        result = pred_equal_to([L("5"), L("5")], None)
        assert result is not None
        assert result.value == "true"

    def test_pred_less_than(self):
        result = pred_less_than([L("3"), L("5")], None)
        assert result is not None
        assert result.value == "true"

    def test_pred_greater_than(self):
        result = pred_greater_than([L("7"), L("5")], None)
        assert result is not None
        assert result.value == "true"

    def test_pred_matches(self):
        result = pred_matches([L("hello123"), L(r"\d+")], None)
        assert result is not None
        assert result.value == "true"
