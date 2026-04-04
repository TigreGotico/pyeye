"""Tests for pyeye.unify — structural unification."""

from __future__ import annotations

import pytest

from pyeye.term import (
    NamedNode, Literal, Variable, Existential, Formula, Triple, Binding
)
from pyeye.unify import unify, term_contains_var, apply_binding, apply_binding_to_triple


NN = NamedNode
V = Variable
E = Existential
L = Literal
T = Triple


# ---------------------------------------------------------------------------
# Basic unification
# ---------------------------------------------------------------------------

class TestBasicUnify:
    def test_ground_match(self):
        """Ground pattern matches ground candidate."""
        p = T(NN("a"), NN("p"), NN("b"))
        c = T(NN("a"), NN("p"), NN("b"))
        result = unify(p, c)
        assert result == {}

    def test_ground_mismatch_predicate(self):
        p = T(NN("a"), NN("p"), NN("b"))
        c = T(NN("a"), NN("q"), NN("b"))
        assert unify(p, c) is None

    def test_ground_mismatch_subject(self):
        p = T(NN("a"), NN("p"), NN("b"))
        c = T(NN("x"), NN("p"), NN("b"))
        assert unify(p, c) is None

    def test_variable_subject(self):
        p = T(V("X"), NN("p"), NN("b"))
        c = T(NN("a"), NN("p"), NN("b"))
        result = unify(p, c)
        assert result == {"X": NN("a")}

    def test_variable_object(self):
        p = T(NN("a"), NN("p"), V("Y"))
        c = T(NN("a"), NN("p"), NN("b"))
        result = unify(p, c)
        assert result == {"Y": NN("b")}

    def test_variable_both(self):
        p = T(V("X"), NN("p"), V("Y"))
        c = T(NN("a"), NN("p"), NN("b"))
        result = unify(p, c)
        assert result == {"X": NN("a"), "Y": NN("b")}

    def test_variable_predicate(self):
        p = T(NN("a"), V("P"), NN("b"))
        c = T(NN("a"), NN("p"), NN("b"))
        result = unify(p, c)
        assert result == {"P": NN("p")}


# ---------------------------------------------------------------------------
# Binding propagation
# ---------------------------------------------------------------------------

class TestBindingPropagation:
    def test_pre_existing_binding(self):
        """Existing binding is extended, not overwritten."""
        p = T(V("X"), NN("p"), NN("b"))
        c = T(NN("a"), NN("p"), NN("b"))
        result = unify(p, c, binding={"Z": NN("extra")})
        assert result == {"X": NN("a"), "Z": NN("extra")}

    def test_consistent_variable_reuse(self):
        """Same variable in pattern must bind consistently."""
        # First unify binds X=a
        p1 = T(V("X"), NN("p"), NN("b"))
        c1 = T(NN("a"), NN("p"), NN("b"))
        binding = unify(p1, c1)
        assert binding is not None

        # Second pattern also has X, must match a
        p2 = T(V("X"), NN("q"), V("Y"))
        c2 = T(NN("a"), NN("q"), NN("c"))
        result = unify(p2, c2, binding=binding)
        assert result == {"X": NN("a"), "Y": NN("c")}

    def test_inconsistent_binding_fails(self):
        """Variable already bound to a different term → failure."""
        p = T(V("X"), NN("p"), NN("c"))
        c = T(NN("b"), NN("p"), NN("c"))
        binding = {"X": NN("a")}
        assert unify(p, c, binding=binding) is None


# ---------------------------------------------------------------------------
# Occurs check
# ---------------------------------------------------------------------------

class TestOccursCheck:
    def test_simple_occurs_check(self):
        """Variable in candidate that is the same as pattern variable → reject."""
        # This case shouldn't happen with ground candidates from the store,
        # but we test the mechanism anyway.
        p = T(V("X"), NN("p"), NN("b"))
        c = T(V("X"), NN("p"), NN("b"))
        result = unify(p, c)
        # Occurs check: X cannot bind to a term containing X.
        assert result is None

    def test_no_occurs_check_on_ground(self):
        """Ground candidate never triggers occurs check."""
        p = T(V("X"), NN("p"), NN("b"))
        c = T(NN("a"), NN("p"), NN("b"))
        assert unify(p, c) is not None


# ---------------------------------------------------------------------------
# term_contains_var
# ---------------------------------------------------------------------------

class TestTermContainsVar:
    def test_named_node(self):
        assert not term_contains_var(NN("a"), "X")

    def test_variable_yes(self):
        assert term_contains_var(V("X"), "X")

    def test_variable_no(self):
        assert not term_contains_var(V("Y"), "X")

    def test_triple_yes_subject(self):
        assert term_contains_var(T(V("X"), NN("p"), NN("b")), "X")

    def test_triple_no(self):
        assert not term_contains_var(T(NN("a"), NN("p"), NN("b")), "X")

    def test_formula_yes(self):
        f = Formula((T(V("X"), NN("p"), NN("b")),))
        assert term_contains_var(f, "X")

    def test_formula_no(self):
        f = Formula((T(NN("a"), NN("p"), NN("b")),))
        assert not term_contains_var(f, "X")


# ---------------------------------------------------------------------------
# apply_binding
# ---------------------------------------------------------------------------

class TestApplyBinding:
    def test_substitute_variable(self):
        binding: Binding = {"X": NN("a")}
        result = apply_binding(V("X"), binding)
        assert result == NN("a")

    def test_unbound_variable_unchanged(self):
        binding: Binding = {"Y": NN("b")}
        result = apply_binding(V("X"), binding)
        assert result == V("X")

    def test_ground_term_unchanged(self):
        binding: Binding = {"X": NN("a")}
        result = apply_binding(NN("b"), binding)
        assert result == NN("b")

    def test_apply_to_triple(self):
        binding: Binding = {"X": NN("a"), "Y": NN("b")}
        t = T(V("X"), NN("p"), V("Y"))
        result = apply_binding_to_triple(t, binding)
        assert result == T(NN("a"), NN("p"), NN("b"))

    def test_apply_to_formula(self):
        binding: Binding = {"X": NN("a"), "Y": NN("b")}
        f = Formula((T(V("X"), NN("p"), V("Y")),))
        result = apply_binding(f, binding)
        assert result == Formula((T(NN("a"), NN("p"), NN("b")),))


# ---------------------------------------------------------------------------
# Literal and Existential
# ---------------------------------------------------------------------------

class TestLiteralExistentialUnify:
    def test_literal_match(self):
        p = T(NN("a"), NN("p"), V("X"))
        c = T(NN("a"), NN("p"), L("42"))
        result = unify(p, c)
        assert result == {"X": L("42")}

    def test_literal_datatype_mismatch(self):
        dt1 = NN("http://www.w3.org/2001/XMLSchema#integer")
        dt2 = NN("http://www.w3.org/2001/XMLSchema#string")
        p = T(NN("a"), NN("p"), L("42", datatype=dt1))
        c = T(NN("a"), NN("p"), L("42", datatype=dt2))
        assert unify(p, c) is None

    def test_existential_match(self):
        p = T(NN("a"), NN("p"), V("X"))
        c = T(NN("a"), NN("p"), E("genid-1"))
        result = unify(p, c)
        assert result == {"X": E("genid-1")}
