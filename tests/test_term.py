"""Tests for pyeye.term — term hierarchy and triple."""

from __future__ import annotations

import pytest

from pyeye.term import NamedNode, Literal, Variable, Existential, Formula, Triple


class TestNamedNode:
    def test_equality(self):
        a = NamedNode("http://example.org/foo")
        b = NamedNode("http://example.org/foo")
        assert a == b

    def test_hashable(self):
        s = {NamedNode("http://a"), NamedNode("http://a")}
        assert len(s) == 1

    def test_str(self):
        assert str(NamedNode("http://x")) == "http://x"


class TestLiteral:
    def test_plain(self):
        lit = Literal("hello")
        assert lit.value == "hello"
        assert lit.datatype is None
        assert lit.language is None

    def test_datatype(self):
        dt = NamedNode("http://www.w3.org/2001/XMLSchema#integer")
        lit = Literal("42", datatype=dt)
        assert lit.datatype == dt
        assert lit.language is None

    def test_language(self):
        lit = Literal("bonjour", language="fr")
        assert lit.language == "fr"
        assert lit.datatype is None

    def test_cannot_have_both(self):
        dt = NamedNode("http://www.w3.org/2001/XMLSchema#string")
        with pytest.raises(ValueError, match="cannot have both"):
            Literal("x", datatype=dt, language="en")

    def test_equality(self):
        a = Literal("42")
        b = Literal("42")
        assert a == b
        assert a != Literal("43")

    def test_hashable(self):
        s = {Literal("a"), Literal("a")}
        assert len(s) == 1


class TestVariable:
    def test_name(self):
        v = Variable("X")
        assert v.name == "X"

    def test_str(self):
        assert str(Variable("X")) == "?X"

    def test_hashable(self):
        s = {Variable("X"), Variable("X")}
        assert len(s) == 1


class TestExistential:
    def test_name(self):
        e = Existential("genid-1")
        assert e.name == "genid-1"

    def test_str(self):
        assert str(Existential("b1")) == "_:b1"

    def test_hashable(self):
        s = {Existential("b1"), Existential("b1")}
        assert len(s) == 1


class TestFormula:
    def test_empty(self):
        f = Formula()
        assert f.triples == ()

    def test_from_list(self):
        t = Triple(NamedNode("a"), NamedNode("b"), NamedNode("c"))
        f = Formula([t])
        assert len(f.triples) == 1
        assert f.triples[0] == t

    def test_hashable(self):
        t = Triple(NamedNode("a"), NamedNode("b"), NamedNode("c"))
        s = {Formula([t]), Formula([t])}
        assert len(s) == 1


class TestTriple:
    def test_ground(self):
        t = Triple(NamedNode("a"), NamedNode("b"), NamedNode("c"))
        assert t.is_ground()

    def test_not_ground_subject(self):
        t = Triple(Variable("X"), NamedNode("b"), NamedNode("c"))
        assert not t.is_ground()

    def test_not_ground_object(self):
        t = Triple(NamedNode("a"), NamedNode("b"), Variable("Y"))
        assert not t.is_ground()

    def test_hashable(self):
        p = NamedNode("p")
        s = {
            Triple(NamedNode("a"), p, NamedNode("b")),
            Triple(NamedNode("a"), p, NamedNode("b")),
        }
        assert len(s) == 1
