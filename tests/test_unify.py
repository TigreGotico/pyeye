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


# ---------------------------------------------------------------------------
# TripleTerm (RDF-star quoted triples)
# ---------------------------------------------------------------------------

class TestTripleTermUnify:
    def test_ground_tripleterm_subject_match(self):
        from pyeye.term import TripleTerm
        tt = TripleTerm(NN("alice"), NN("knows"), NN("bob"))
        p = T(tt, NN("since"), L("1999"))
        c = T(tt, NN("since"), L("1999"))
        assert unify(p, c) == {}

    def test_ground_tripleterm_inner_mismatch(self):
        from pyeye.term import TripleTerm
        p = T(TripleTerm(NN("alice"), NN("knows"), NN("bob")), NN("since"), L("1999"))
        c = T(TripleTerm(NN("alice"), NN("knows"), NN("carol")), NN("since"), L("1999"))
        assert unify(p, c) is None

    def test_variable_inside_tripleterm_subject(self):
        from pyeye.term import TripleTerm
        x = V("X")
        p = T(TripleTerm(NN("alice"), x, NN("bob")), NN("since"), L("1999"))
        c = T(TripleTerm(NN("alice"), NN("marriedTo"), NN("bob")), NN("since"), L("1999"))
        result = unify(p, c)
        assert result == {x.id: NN("marriedTo")}

    def test_multiple_vars_inside_tripleterm(self):
        from pyeye.term import TripleTerm
        s, o = V("S"), V("O")
        p = T(TripleTerm(s, NN("marriedTo"), o), NN("since"), L("1999"))
        c = T(TripleTerm(NN("alice"), NN("marriedTo"), NN("bob")), NN("since"), L("1999"))
        result = unify(p, c)
        assert result == {s.id: NN("alice"), o.id: NN("bob")}

    def test_tripleterm_in_object_position(self):
        from pyeye.term import TripleTerm
        x = V("X")
        p = T(NN("s"), NN("p"), TripleTerm(NN("d"), NN("e"), x))
        c = T(NN("s"), NN("p"), TripleTerm(NN("d"), NN("e"), NN("f")))
        result = unify(p, c)
        assert result == {x.id: NN("f")}

    def test_tripleterm_vs_namednode_fails(self):
        from pyeye.term import TripleTerm
        p = T(TripleTerm(NN("a"), NN("b"), NN("c")), NN("p"), NN("o"))
        c = T(NN("plain"), NN("p"), NN("o"))
        assert unify(p, c) is None

    def test_variable_binds_to_whole_tripleterm(self):
        from pyeye.term import TripleTerm
        x = V("X")
        tt = TripleTerm(NN("a"), NN("b"), NN("c"))
        p = T(x, NN("p"), NN("o"))
        c = T(tt, NN("p"), NN("o"))
        result = unify(p, c)
        assert result == {x.id: tt}

    def test_nested_tripleterm_unify(self):
        from pyeye.term import TripleTerm
        x = V("X")
        inner_pat = TripleTerm(NN("a"), NN("b"), x)
        inner_cand = TripleTerm(NN("a"), NN("b"), NN("c"))
        p = T(TripleTerm(inner_pat, NN("p2"), NN("o2")), NN("q"), NN("z"))
        c = T(TripleTerm(inner_cand, NN("p2"), NN("o2")), NN("q"), NN("z"))
        result = unify(p, c)
        assert result == {x.id: NN("c")}

    def test_occurs_check_inside_tripleterm(self):
        from pyeye.term import TripleTerm
        from pyeye.unify import unify_terms
        x = V("X")
        # X cannot bind to a TripleTerm that contains X
        tt = TripleTerm(NN("a"), NN("b"), x)
        assert unify_terms(x, tt, {}) is None

    def test_apply_binding_into_tripleterm(self):
        from pyeye.term import TripleTerm
        s, o = V("S"), V("O")
        tt = TripleTerm(s, NN("marriedTo"), o)
        binding = {s.id: NN("alice"), o.id: NN("bob")}
        result = apply_binding(tt, binding)
        assert result == TripleTerm(NN("alice"), NN("marriedTo"), NN("bob"))

    def test_term_contains_var_inside_tripleterm(self):
        from pyeye.term import TripleTerm
        x = V("X")
        tt = TripleTerm(NN("a"), NN("b"), x)
        assert term_contains_var(tt, x.id) is True
        assert term_contains_var(tt, 999999) is False
