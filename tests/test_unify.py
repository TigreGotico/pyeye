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
        x = V("X")
        p = T(x, NN("p"), NN("b"))
        c = T(NN("a"), NN("p"), NN("b"))
        result = unify(p, c)
        assert result == {x.id: NN("a")}

    def test_variable_object(self):
        y = V("Y")
        p = T(NN("a"), NN("p"), y)
        c = T(NN("a"), NN("p"), NN("b"))
        result = unify(p, c)
        assert result == {y.id: NN("b")}

    def test_variable_both(self):
        x, y = V("X"), V("Y")
        p = T(x, NN("p"), y)
        c = T(NN("a"), NN("p"), NN("b"))
        result = unify(p, c)
        assert result == {x.id: NN("a"), y.id: NN("b")}

    def test_variable_predicate(self):
        pv = V("P")
        p = T(NN("a"), pv, NN("b"))
        c = T(NN("a"), NN("p"), NN("b"))
        result = unify(p, c)
        assert result == {pv.id: NN("p")}


# ---------------------------------------------------------------------------
# Binding propagation
# ---------------------------------------------------------------------------

class TestBindingPropagation:
    def test_pre_existing_binding(self):
        """Existing binding is extended, not overwritten."""
        x, z = V("X"), V("Z")
        p = T(x, NN("p"), NN("b"))
        c = T(NN("a"), NN("p"), NN("b"))
        result = unify(p, c, binding={z.id: NN("extra")})
        assert result == {x.id: NN("a"), z.id: NN("extra")}

    def test_consistent_variable_reuse(self):
        """Same variable in pattern must bind consistently."""
        x, y = V("X"), V("Y")
        # First unify binds X=a
        p1 = T(x, NN("p"), NN("b"))
        c1 = T(NN("a"), NN("p"), NN("b"))
        binding = unify(p1, c1)
        assert binding is not None

        # Second pattern reuses X (same id), must match a
        p2 = T(x, NN("q"), y)
        c2 = T(NN("a"), NN("q"), NN("c"))
        result = unify(p2, c2, binding=binding)
        assert result == {x.id: NN("a"), y.id: NN("c")}

    def test_inconsistent_binding_fails(self):
        """Variable already bound to a different term → failure."""
        x = V("X")
        p = T(x, NN("p"), NN("c"))
        c = T(NN("b"), NN("p"), NN("c"))
        binding = {x.id: NN("a")}
        assert unify(p, c, binding=binding) is None


# ---------------------------------------------------------------------------
# Occurs check
# ---------------------------------------------------------------------------

class TestOccursCheck:
    def test_simple_occurs_check(self):
        """A variable cannot bind to a term that contains itself."""
        from pyeye.term import ListTerm
        from pyeye.unify import unify_terms
        x = V("X")
        # X unified with (X) — the list contains X, so occurs check rejects.
        result = unify_terms(x, ListTerm((x,)), {})
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
        assert not term_contains_var(NN("a"), V("X").id)

    def test_variable_yes(self):
        x = V("X")
        assert term_contains_var(x, x.id)

    def test_variable_no(self):
        assert not term_contains_var(V("Y"), V("X").id)

    def test_triple_yes_subject(self):
        x = V("X")
        assert term_contains_var(T(x, NN("p"), NN("b")), x.id)

    def test_triple_no(self):
        assert not term_contains_var(T(NN("a"), NN("p"), NN("b")), V("X").id)

    def test_formula_yes(self):
        x = V("X")
        f = Formula((T(x, NN("p"), NN("b")),))
        assert term_contains_var(f, x.id)

    def test_formula_no(self):
        f = Formula((T(NN("a"), NN("p"), NN("b")),))
        assert not term_contains_var(f, V("X").id)


# ---------------------------------------------------------------------------
# apply_binding
# ---------------------------------------------------------------------------

class TestApplyBinding:
    def test_substitute_variable(self):
        x = V("X")
        binding: Binding = {x.id: NN("a")}
        result = apply_binding(x, binding)
        assert result == NN("a")

    def test_unbound_variable_unchanged(self):
        x = V("X")
        binding: Binding = {V("Y").id: NN("b")}
        result = apply_binding(x, binding)
        assert result == x

    def test_ground_term_unchanged(self):
        binding: Binding = {V("X").id: NN("a")}
        result = apply_binding(NN("b"), binding)
        assert result == NN("b")

    def test_apply_to_triple(self):
        x, y = V("X"), V("Y")
        binding: Binding = {x.id: NN("a"), y.id: NN("b")}
        t = T(x, NN("p"), y)
        result = apply_binding_to_triple(t, binding)
        assert result == T(NN("a"), NN("p"), NN("b"))

    def test_apply_to_formula(self):
        x, y = V("X"), V("Y")
        binding: Binding = {x.id: NN("a"), y.id: NN("b")}
        f = Formula((T(x, NN("p"), y),))
        result = apply_binding(f, binding)
        assert result == Formula((T(NN("a"), NN("p"), NN("b")),))


# ---------------------------------------------------------------------------
# Literal and Existential
# ---------------------------------------------------------------------------

class TestLiteralExistentialUnify:
    def test_literal_match(self):
        x = V("X")
        p = T(NN("a"), NN("p"), x)
        c = T(NN("a"), NN("p"), L("42"))
        result = unify(p, c)
        assert result == {x.id: L("42")}

    def test_literal_datatype_mismatch(self):
        dt1 = NN("http://www.w3.org/2001/XMLSchema#integer")
        dt2 = NN("http://www.w3.org/2001/XMLSchema#string")
        p = T(NN("a"), NN("p"), L("42", datatype=dt1))
        c = T(NN("a"), NN("p"), L("42", datatype=dt2))
        assert unify(p, c) is None

    def test_existential_match(self):
        x = V("X")
        p = T(NN("a"), NN("p"), x)
        c = T(NN("a"), NN("p"), E("genid-1"))
        result = unify(p, c)
        assert result == {x.id: E("genid-1")}
