"""Tests for pyeye.term — Phase 2 extended term types."""

from __future__ import annotations

import pytest

from pyeye.term import (
    NamedNode, Literal, Variable, Existential, Formula, Triple,
    TripleTerm, FormulaTerm, PathTerm, Quad,
)


NN = NamedNode
V = Variable
E = Existential
L = Literal
T = Triple
F = Formula


# ---------------------------------------------------------------------------
# TripleTerm
# ---------------------------------------------------------------------------

class TestTripleTerm:
    def test_create(self):
        tt = TripleTerm(NN("a"), NN("p"), NN("b"))
        assert tt.subject == NN("a")
        assert tt.predicate == NN("p")
        assert tt.object == NN("b")

    def test_str(self):
        tt = TripleTerm(NN("a"), NN("p"), NN("b"))
        assert str(tt) == "<<a p b>>"

    def test_hashable(self):
        s = {
            TripleTerm(NN("a"), NN("p"), NN("b")),
            TripleTerm(NN("a"), NN("p"), NN("b")),
        }
        assert len(s) == 1

    def test_is_ground(self):
        assert TripleTerm(NN("a"), NN("p"), NN("b")).is_ground()
        assert not TripleTerm(V("X"), NN("p"), NN("b")).is_ground()
        assert not TripleTerm(NN("a"), NN("p"), V("Y")).is_ground()

    def test_can_be_subject(self):
        """TripleTerm can appear as subject of another triple."""
        t = T(TripleTerm(NN("a"), NN("p"), NN("b")), NN("saidBy"), NN("alice"))
        assert isinstance(t.subject, TripleTerm)

    def test_can_be_object(self):
        """TripleTerm can appear as object of another triple."""
        t = T(NN("alice"), NN("believes"), TripleTerm(NN("a"), NN("p"), NN("b")))
        assert isinstance(t.object, TripleTerm)


# ---------------------------------------------------------------------------
# FormulaTerm
# ---------------------------------------------------------------------------

class TestFormulaTerm:
    def test_create(self):
        ft = FormulaTerm(NN("says"), (NN("alice"), L("hello")))
        assert ft.functor == NN("says")
        assert ft.args == (NN("alice"), L("hello"))

    def test_empty_args(self):
        ft = FormulaTerm(NN("true"))
        assert ft.args == ()

    def test_str(self):
        ft = FormulaTerm(NN("says"), (NN("alice"), L("hello")))
        assert str(ft) == "(|says alice \"hello\"|)"

    def test_hashable(self):
        s = {
            FormulaTerm(NN("f"), (NN("a"),)),
            FormulaTerm(NN("f"), (NN("a"),)),
        }
        assert len(s) == 1

    def test_is_ground(self):
        assert FormulaTerm(NN("f"), (NN("a"),)).is_ground()
        assert not FormulaTerm(V("F"), (NN("a"),)).is_ground()
        assert not FormulaTerm(NN("f"), (V("X"),)).is_ground()

    def test_can_be_object(self):
        t = T(NN("alice"), NN("believes"), FormulaTerm(NN("p"), (NN("a"),)))
        assert isinstance(t.object, FormulaTerm)


# ---------------------------------------------------------------------------
# PathTerm
# ---------------------------------------------------------------------------

class TestPathTerm:
    def test_create_forward(self):
        pt = PathTerm((NN("a"), NN("b"), NN("c")), ("forward", "forward", "forward"))
        assert pt.terms == (NN("a"), NN("b"), NN("c"))
        assert pt.directions == ("forward", "forward", "forward")

    def test_create_reverse(self):
        pt = PathTerm((NN("a"), NN("b")), ("reverse", "reverse"))
        assert pt.directions == ("reverse", "reverse")

    def test_auto_fill_directions(self):
        """If directions are missing, they default to forward."""
        pt = PathTerm((NN("a"), NN("b"), NN("c")))
        assert pt.directions == ("forward", "forward", "forward")

    def test_str_forward(self):
        pt = PathTerm((NN("a"), NN("b"), NN("c")), ("forward", "forward", "forward"))
        assert str(pt) == "a ! b ! c"

    def test_str_reverse(self):
        pt = PathTerm((NN("a"), NN("b")), ("reverse", "reverse"))
        assert str(pt) == "a ^ b"

    def test_hashable(self):
        s = {
            PathTerm((NN("a"), NN("b")), ("forward",)),
            PathTerm((NN("a"), NN("b")), ("forward",)),
        }
        assert len(s) == 1

    def test_is_ground(self):
        assert PathTerm((NN("a"), NN("b"))).is_ground()
        assert not PathTerm((V("X"), NN("b"))).is_ground()


# ---------------------------------------------------------------------------
# Triple.is_ground with nested types
# ---------------------------------------------------------------------------

class TestTripleIsGroundNested:
    def test_triple_term_in_subject(self):
        t = T(TripleTerm(NN("a"), NN("p"), NN("b")), NN("saidBy"), NN("alice"))
        assert t.is_ground()

    def test_triple_term_with_variable(self):
        t = T(TripleTerm(V("X"), NN("p"), NN("b")), NN("saidBy"), NN("alice"))
        assert not t.is_ground()

    def test_formula_term_in_object(self):
        t = T(NN("a"), NN("believes"), FormulaTerm(NN("p"), (NN("b"),)))
        assert t.is_ground()

    def test_path_term_in_subject(self):
        t = T(PathTerm((NN("a"), NN("b"))), NN("leadsTo"), NN("c"))
        assert t.is_ground()

    def test_path_term_with_variable(self):
        t = T(PathTerm((V("X"), NN("b"))), NN("leadsTo"), NN("c"))
        assert not t.is_ground()


# ---------------------------------------------------------------------------
# Quad
# ---------------------------------------------------------------------------

class TestQuad:
    def test_create(self):
        q = Quad(NN("a"), NN("p"), NN("b"), NN("g1"))
        assert q.subject == NN("a")
        assert q.graph == NN("g1")

    def test_default_graph(self):
        q = Quad(NN("a"), NN("p"), NN("b"))
        assert q.graph is None

    def test_hashable(self):
        s = {
            Quad(NN("a"), NN("p"), NN("b"), NN("g1")),
            Quad(NN("a"), NN("p"), NN("b"), NN("g1")),
        }
        assert len(s) == 1

    def test_to_triple(self):
        q = Quad(NN("a"), NN("p"), NN("b"), NN("g1"))
        t = q.to_triple()
        assert t == T(NN("a"), NN("p"), NN("b"))

    def test_graph_distinction(self):
        """Same triple in different graphs is a different Quad."""
        q1 = Quad(NN("a"), NN("p"), NN("b"), NN("g1"))
        q2 = Quad(NN("a"), NN("p"), NN("b"), NN("g2"))
        assert q1 != q2
        assert hash(q1) != hash(q2)
