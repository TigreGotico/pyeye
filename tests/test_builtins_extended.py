"""Tests for Phase 2: extended builtins."""

from __future__ import annotations

import re

from pyeye.builtins import (
    crypto_md5, crypto_sha256,
    string_matches, string_replace, string_substring,
    math_floor, math_ceiling, math_exponentiation,
    time_hours, time_minutes,
    log_uuid, log_n3String,
    graph_length,
    list_car, list_cdr,
    e_calculate, e_findall,
)
from pyeye.term import NamedNode, Literal, Variable, Existential, Triple as T
from pyeye.engine import Engine
from pyeye.store import TripleStore


NN = NamedNode
V = Variable
E = Existential
L = Literal


class TestCryptoBuiltins:
    def test_md5(self):
        result = crypto_md5([L("hello")], None)
        assert result is not None
        assert result.value == "5d41402abc4b2a76b9719d911017c592"

    def test_sha256(self):
        result = crypto_sha256([L("hello")], None)
        assert result is not None
        assert result.value == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"

    def test_unground_skips(self):
        result = crypto_md5([V("X")], None)
        assert result is None


class TestRegexBuiltins:
    def test_matches(self):
        result = string_matches([L("hello world"), L("world")], None)
        assert result is not None
        assert result.value == "true"

    def test_matches_no_match(self):
        result = string_matches([L("hello world"), L("^start")], None)
        assert result is not None
        assert result.value == "false"

    def test_replace(self):
        result = string_replace([L("hello world"), L("world"), L("there")], None)
        assert result is not None
        assert result.value == "hello there"

    def test_substring(self):
        result = string_substring([L("hello"), L("1"), L("3")], None)
        assert result is not None
        assert result.value == "ell"


class TestMathExtended:
    def test_floor(self):
        result = math_floor([L("3.7")], None)
        assert result is not None
        assert result.value == "3"

    def test_ceiling(self):
        result = math_ceiling([L("3.2")], None)
        assert result is not None
        assert result.value == "4"

    def test_exponentiation(self):
        result = math_exponentiation([L("2"), L("3")], None)
        assert result is not None
        assert float(result.value) == 8.0


class TestTimeExtended:
    def test_hours(self):
        result = time_hours([L("2025-04-04T15:30:00")], None)
        assert result is not None
        assert result.value == "15"

    def test_minutes(self):
        result = time_minutes([L("2025-04-04T15:30:45")], None)
        assert result is not None
        assert result.value == "30"

    def test_unground_skips(self):
        result = time_hours([V("X")], None)
        assert result is None


class TestLogExtended:
    def test_uuid(self):
        result = log_uuid([], None)
        assert result is not None
        # UUID format: 8-4-4-4-12 hex chars
        assert re.match(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            result.value
        )

    def test_n3String(self):
        result = log_n3String([NN("http://ex.org/foo")], None)
        assert result is not None
        assert "http://ex.org/foo" in result.value


class TestGraphBuiltins:
    def test_length(self):
        engine = Engine()
        engine.add_triple(T(NN("a"), NN("p"), NN("b")))
        engine.add_triple(T(NN("c"), NN("q"), NN("d")))
        result = graph_length([], engine)
        assert result is not None
        assert result.value == "2"


class TestListExtended:
    def test_car(self):
        engine = Engine()
        # Create a list: _b1 :first "apple" ; :rest _b2
        engine.add_triple(T(E("_b1"), NN("http://www.w3.org/1999/02/22-rdf-syntax-ns#first"), L("apple")))
        engine.add_triple(T(E("_b1"), NN("http://www.w3.org/1999/02/22-rdf-syntax-ns#rest"), E("_b2")))
        result = list_car([E("_b1")], engine)
        assert result is not None
        assert result == L("apple")

    def test_cdr(self):
        engine = Engine()
        engine.add_triple(T(E("_b1"), NN("http://www.w3.org/1999/02/22-rdf-syntax-ns#first"), L("apple")))
        engine.add_triple(T(E("_b1"), NN("http://www.w3.org/1999/02/22-rdf-syntax-ns#rest"), E("_b2")))
        result = list_cdr([E("_b1")], engine)
        assert result is not None
        assert result == E("_b2")


class TestEBuiltins:
    def test_calculate(self):
        result = e_calculate([L("2 + 3")], None)
        assert result is not None
        assert result.value == "5"

    def test_calculate_unground(self):
        result = e_calculate([V("X")], None)
        assert result is None

    def test_findall(self):
        engine = Engine()
        engine.add_triple(T(NN("a"), NN("p"), NN("b")))
        result = e_findall([], engine)
        assert result is not None
        assert len(result) == 1
