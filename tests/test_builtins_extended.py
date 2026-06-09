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
        from pyeye.term import ListTerm
        engine = Engine()
        result = list_car([ListTerm((L("apple"), L("banana")))], engine)
        assert result is not None
        assert result == L("apple")

    def test_cdr(self):
        from pyeye.term import ListTerm
        engine = Engine()
        result = list_cdr([ListTerm((L("apple"), L("banana")))], engine)
        assert result is not None
        assert result == ListTerm((L("banana"),))


class TestEBuiltins:
    def test_calculate(self):
        """e:evaluate returns literals safely."""
        result = e_calculate([L("42")], None)
        assert result is not None
        assert result.value == "42"

    def test_calculate_string(self):
        result = e_calculate([L("'hello world'")], None)
        assert result is not None
        assert result.value == "hello world"

    def test_calculate_unground(self):
        result = e_calculate([V("X")], None)
        assert result is None

    def test_findall(self):
        engine = Engine()
        engine.add_triple(T(NN("a"), NN("p"), NN("b")))
        result = e_findall([], engine)
        assert result is not None
        assert len(result) == 1


XSD_INT = NN("http://www.w3.org/2001/XMLSchema#integer")


def IL(v) -> Literal:
    return L(str(v), datatype=XSD_INT)


class TestMathIntegerTyping:
    """Integer-typed inputs yield integer-typed (exact) results."""

    def test_remainder_integer_typed(self):
        from pyeye.builtins import math_remainder
        r = math_remainder([IL(7), IL(3)], None)
        assert r.value == "1"
        assert r.datatype == XSD_INT

    def test_integer_quotient_integer_typed(self):
        from pyeye.builtins import math_integerQuotient
        r = math_integerQuotient([IL(7), IL(2)], None)
        assert r.value == "3"
        assert r.datatype == XSD_INT

    def test_negation_integer_typed(self):
        from pyeye.builtins import math_negation
        r = math_negation([IL(5)], None)
        assert r.value == "-5"
        assert r.datatype == XSD_INT

    def test_absolute_value_integer_typed(self):
        from pyeye.builtins import math_absoluteValue
        r = math_absoluteValue([IL(-5)], None)
        assert r.value == "5"
        assert r.datatype == XSD_INT

    def test_exponentiation_integer_exact(self):
        from pyeye.builtins import math_exponentiation
        r = math_exponentiation([IL(238), IL(13)], None)
        assert r.value == str(238 ** 13)
        assert r.datatype == XSD_INT

    def test_exponentiation_float_stays_double(self):
        from pyeye.builtins import math_exponentiation
        r = math_exponentiation([L("2.0"), L("0.5")], None)
        assert abs(float(r.value) - 2 ** 0.5) < 1e-9

    def test_product_big_integer_exact(self):
        from pyeye.builtins import math_product
        big = 8367238 ** 700  # several thousand digits
        r = math_product([IL(big), IL(big)], None)
        assert r.value == str(big * big)

    def test_numeric_equal_cross_datatype(self):
        from pyeye.builtins import numeric_equal
        assert numeric_equal(IL(1), L("1.0", datatype=NN("http://www.w3.org/2001/XMLSchema#double")))
        assert not numeric_equal(IL(1), IL(2))
        assert not numeric_equal(IL(1), NN("http://x/1"))


class TestListAppendModes:
    def _lst(self, *items):
        from pyeye.term import ListTerm
        return ListTerm(items=tuple(items))

    def test_forward_mode_excludes_output_slot(self):
        from pyeye.builtins import list_append
        out = V("M")
        r = list_append([self._lst(L("a")), self._lst(L("b")), out], None)
        assert r is not None
        assert list(r.items) == [L("a"), L("b")]

    def test_forward_mode_unbound_input_skips(self):
        from pyeye.builtins import list_append
        r = list_append([V("m1"), self._lst(L("a")), V("M")], None)
        assert r is None

    def test_check_mode_match(self):
        from pyeye.builtins import list_append
        out = self._lst(L("a"), L("b"))
        r = list_append([self._lst(L("a")), self._lst(L("b")), out], None)
        assert r == out

    def test_reverse_mode_enumerates_splits(self):
        from pyeye.builtins import list_append, BindingsList
        engine = Engine()
        f, g = V("F"), V("G")
        out = self._lst(L("a"), L("b"))
        r = list_append([f, g, out], engine)
        assert isinstance(r, BindingsList)
        splits = {(len(b[f.id].items), len(b[g.id].items)) for b in r.bindings}
        assert splits == {(0, 2), (1, 1), (2, 0)}

    def test_reverse_mode_ground_part_constrains(self):
        from pyeye.builtins import list_append, BindingsList
        engine = Engine()
        g = V("G")
        out = self._lst(L("a"), L("b"), L("c"))
        r = list_append([self._lst(L("a")), g, out], engine)
        assert isinstance(r, BindingsList)
        assert len(r.bindings) == 1
        assert list(r.bindings[0][g.id].items) == [L("b"), L("c")]


class TestLogUri:
    def test_forward_percent_decodes(self):
        from pyeye.builtins import log_uri
        r = log_uri([NN("https://x.org/a%20b%cc%88"), V("S")], None)
        assert r == L("https://x.org/a b̈")

    def test_reverse_percent_encodes_lowercase_hex(self):
        from pyeye.builtins import log_uri, BindingsList
        engine = Engine()
        u = V("uri")
        r = log_uri([u, L("https://x.org/a b̈.pdf")], engine)
        assert isinstance(r, BindingsList)
        assert r.bindings[0][u.id] == NN("https://x.org/a%20b%cc%88.pdf")

    def test_unbound_both_skips(self):
        from pyeye.builtins import log_uri
        assert log_uri([V("uri"), V("S")], None) is None
