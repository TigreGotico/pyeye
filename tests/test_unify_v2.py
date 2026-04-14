"""Tests for v2 unification: Variable.id bindings, ListTerm unification."""

from pyeye.term import (
    Variable, NamedNode, Literal, Existential, ListTerm, Formula, Triple,
    Binding,
)
from pyeye.unify import (
    unify, unify_terms, term_contains_var, apply_binding,
    apply_binding_to_triple,
)


class TestUnifyTermsBasic:
    """Basic term unification with Variable.id bindings."""

    def test_ground_equal(self):
        a = NamedNode("x")
        b = NamedNode("x")
        assert unify_terms(a, b, {}) == {}

    def test_ground_unequal(self):
        assert unify_terms(NamedNode("x"), NamedNode("y"), {}) is None

    def test_variable_binds_to_ground(self):
        v = Variable("X", id=1)
        n = NamedNode("alice")
        result = unify_terms(v, n, {})
        assert result == {1: n}

    def test_bound_variable_matches(self):
        v = Variable("X", id=1)
        n = NamedNode("alice")
        result = unify_terms(v, n, {1: n})
        assert result is not None

    def test_bound_variable_fails(self):
        v = Variable("X", id=1)
        result = unify_terms(v, NamedNode("bob"), {1: NamedNode("alice")})
        assert result is None

    def test_two_variables_bind(self):
        v1 = Variable("X", id=1)
        v2 = Variable("Y", id=2)
        result = unify_terms(v1, v2, {})
        assert result == {1: v2}

    def test_same_variable_unifies(self):
        v = Variable("X", id=1)
        assert unify_terms(v, v, {}) == {}

    def test_occurs_check(self):
        """A variable cannot bind to a term containing itself."""
        v = Variable("X", id=1)
        lt = ListTerm(items=(v, NamedNode("a")))
        assert unify_terms(v, lt, {}) is None


class TestUnifyListTerm:
    """ListTerm element-by-element unification."""

    def test_empty_lists(self):
        a = ListTerm(items=())
        b = ListTerm(items=())
        assert unify_terms(a, b, {}) == {}

    def test_ground_lists_equal(self):
        a = ListTerm(items=(NamedNode("x"), NamedNode("y")))
        b = ListTerm(items=(NamedNode("x"), NamedNode("y")))
        assert unify_terms(a, b, {}) == {}

    def test_ground_lists_unequal(self):
        a = ListTerm(items=(NamedNode("x"),))
        b = ListTerm(items=(NamedNode("y"),))
        assert unify_terms(a, b, {}) is None

    def test_different_lengths(self):
        a = ListTerm(items=(NamedNode("x"),))
        b = ListTerm(items=(NamedNode("x"), NamedNode("y")))
        assert unify_terms(a, b, {}) is None

    def test_variable_in_list(self):
        v = Variable("X", id=10)
        a = ListTerm(items=(v, NamedNode("b")))
        b = ListTerm(items=(NamedNode("a"), NamedNode("b")))
        result = unify_terms(a, b, {})
        assert result == {10: NamedNode("a")}

    def test_multiple_variables(self):
        v1 = Variable("X", id=10)
        v2 = Variable("Y", id=20)
        a = ListTerm(items=(v1, v2))
        b = ListTerm(items=(NamedNode("a"), NamedNode("b")))
        result = unify_terms(a, b, {})
        assert result == {10: NamedNode("a"), 20: NamedNode("b")}

    def test_nested_lists(self):
        v = Variable("X", id=5)
        inner_a = ListTerm(items=(v,))
        outer_a = ListTerm(items=(inner_a, NamedNode("b")))
        inner_b = ListTerm(items=(NamedNode("a"),))
        outer_b = ListTerm(items=(inner_b, NamedNode("b")))
        result = unify_terms(outer_a, outer_b, {})
        assert result == {5: NamedNode("a")}

    def test_list_vs_non_list_fails(self):
        lt = ListTerm(items=(NamedNode("a"),))
        assert unify_terms(lt, NamedNode("a"), {}) is None

    def test_variable_binds_to_list(self):
        v = Variable("L", id=1)
        lt = ListTerm(items=(NamedNode("a"), NamedNode("b")))
        result = unify_terms(v, lt, {})
        assert result == {1: lt}


class TestUnifyTriple:
    """Triple-level unification."""

    def test_ground_triples(self):
        t1 = Triple(NamedNode("s"), NamedNode("p"), NamedNode("o"))
        t2 = Triple(NamedNode("s"), NamedNode("p"), NamedNode("o"))
        assert unify(t1, t2, {}) == {}

    def test_variable_in_triple(self):
        v = Variable("X", id=1)
        t1 = Triple(v, NamedNode("p"), NamedNode("o"))
        t2 = Triple(NamedNode("s"), NamedNode("p"), NamedNode("o"))
        result = unify(t1, t2, {})
        assert result == {1: NamedNode("s")}

    def test_list_subject_unification(self):
        v = Variable("X", id=1)
        t1 = Triple(ListTerm(items=(v, NamedNode("b"))), NamedNode("p"), NamedNode("o"))
        t2 = Triple(ListTerm(items=(NamedNode("a"), NamedNode("b"))), NamedNode("p"), NamedNode("o"))
        result = unify(t1, t2, {})
        assert result == {1: NamedNode("a")}


class TestApplyBinding:
    """Apply binding with Variable.id keys."""

    def test_resolve_variable(self):
        v = Variable("X", id=1)
        b: Binding = {1: NamedNode("alice")}
        assert apply_binding(v, b) == NamedNode("alice")

    def test_resolve_chain(self):
        v1 = Variable("X", id=1)
        v2 = Variable("Y", id=2)
        b: Binding = {1: v2, 2: NamedNode("alice")}
        assert apply_binding(v1, b) == NamedNode("alice")

    def test_resolve_list(self):
        v = Variable("X", id=1)
        lt = ListTerm(items=(v, NamedNode("b")))
        b: Binding = {1: NamedNode("a")}
        result = apply_binding(lt, b)
        assert isinstance(result, ListTerm)
        assert result.items == (NamedNode("a"), NamedNode("b"))

    def test_unbound_variable_unchanged(self):
        v = Variable("X", id=99)
        assert apply_binding(v, {}) == v

    def test_apply_to_triple(self):
        v = Variable("X", id=1)
        t = Triple(v, NamedNode("p"), NamedNode("o"))
        b: Binding = {1: NamedNode("s")}
        result = apply_binding_to_triple(t, b)
        assert result.subject == NamedNode("s")


class TestTermContainsVar:
    """Occurs check helper with Variable.id."""

    def test_variable_contains_itself(self):
        assert term_contains_var(Variable("X", id=1), 1)

    def test_variable_not_contains_other(self):
        assert not term_contains_var(Variable("X", id=1), 2)

    def test_list_contains_var(self):
        v = Variable("X", id=5)
        lt = ListTerm(items=(NamedNode("a"), v))
        assert term_contains_var(lt, 5)
        assert not term_contains_var(lt, 6)

    def test_ground_term_no_var(self):
        assert not term_contains_var(NamedNode("x"), 1)
        assert not term_contains_var(Literal("x"), 1)


class TestNumericEquivalence:
    """Cross-datatype numeric unification."""

    def test_int_double_equal(self):
        a = Literal("42", datatype=NamedNode("http://www.w3.org/2001/XMLSchema#integer"))
        b = Literal("42.0", datatype=NamedNode("http://www.w3.org/2001/XMLSchema#double"))
        assert unify_terms(a, b, {}) == {}

    def test_int_double_unequal(self):
        a = Literal("42", datatype=NamedNode("http://www.w3.org/2001/XMLSchema#integer"))
        b = Literal("43.0", datatype=NamedNode("http://www.w3.org/2001/XMLSchema#double"))
        assert unify_terms(a, b, {}) is None
