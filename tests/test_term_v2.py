"""Tests for the v2 term model: Variable.id, ListTerm, no PathTerm."""

from pyeye.term import (
    Variable, NamedNode, Literal, Existential, ListTerm, Formula, Triple,
    Binding, _next_var_id, reset_var_ids, TripleTerm, FormulaTerm,
    NegativeSurface, SetTerm, Quad,
)


class TestVariableId:
    """Variable.id uniqueness and scoping."""

    def test_auto_assigned_ids_are_unique(self):
        a = Variable("X")
        b = Variable("X")
        assert a.id != b.id  # same name, different identity

    def test_explicit_id(self):
        v = Variable("X", id=42)
        assert v.id == 42
        assert v.name == "X"

    def test_eq_uses_id_not_name(self):
        a = Variable("X", id=1)
        b = Variable("X", id=2)
        c = Variable("X", id=1)
        assert a != b
        assert a == c

    def test_hash_uses_id(self):
        a = Variable("X", id=1)
        b = Variable("Y", id=1)  # different name, same id
        c = Variable("X", id=2)
        assert hash(a) == hash(b)  # same id → same hash
        assert hash(a) != hash(c)

    def test_variable_in_set(self):
        a = Variable("X", id=1)
        b = Variable("X", id=2)
        c = Variable("X", id=1)
        s = {a, b, c}
        assert len(s) == 2  # a and c are the same

    def test_variable_as_dict_key(self):
        a = Variable("X", id=10)
        b = Variable("X", id=20)
        d: Binding = {a.id: NamedNode("alice"), b.id: NamedNode("bob")}
        assert d[10] == NamedNode("alice")
        assert d[20] == NamedNode("bob")

    def test_str(self):
        v = Variable("Foo", id=99)
        assert str(v) == "?Foo"


class TestListTerm:
    """ListTerm: native list representation."""

    def test_empty_list(self):
        lt = ListTerm(items=())
        assert len(lt) == 0
        assert list(lt) == []
        assert lt.is_ground()

    def test_ground_list(self):
        lt = ListTerm(items=(NamedNode("a"), Literal("1")))
        assert len(lt) == 2
        assert lt.is_ground()

    def test_list_with_variables(self):
        v = Variable("X", id=5)
        lt = ListTerm(items=(v, NamedNode("b")))
        assert not lt.is_ground()

    def test_nested_list(self):
        inner = ListTerm(items=(Literal("1"), Literal("2")))
        outer = ListTerm(items=(inner, Literal("3")))
        assert len(outer) == 2
        assert outer.is_ground()

    def test_hashable(self):
        lt1 = ListTerm(items=(NamedNode("a"),))
        lt2 = ListTerm(items=(NamedNode("a"),))
        assert hash(lt1) == hash(lt2)
        assert lt1 == lt2
        s = {lt1, lt2}
        assert len(s) == 1

    def test_str(self):
        lt = ListTerm(items=(NamedNode("a"), NamedNode("b")))
        assert str(lt) == "(a b)"

    def test_empty_str(self):
        assert str(ListTerm(items=())) == "()"

    def test_from_list(self):
        """Constructor accepts a plain list and normalizes to tuple."""
        lt = ListTerm(items=[NamedNode("a"), NamedNode("b")])
        assert isinstance(lt.items, tuple)

    def test_iterable(self):
        items = [NamedNode("a"), NamedNode("b"), NamedNode("c")]
        lt = ListTerm(items=tuple(items))
        assert list(lt) == items


class TestListTermInTriple:
    """ListTerm can appear as subject or object of a Triple."""

    def test_list_as_subject(self):
        lt = ListTerm(items=(Literal("1"), Literal("2")))
        t = Triple(lt, NamedNode("math:sum"), Variable("R", id=1))
        assert isinstance(t.subject, ListTerm)
        assert not t.is_ground()

    def test_ground_list_triple(self):
        lt = ListTerm(items=(Literal("1"), Literal("2")))
        t = Triple(lt, NamedNode("math:sum"), Literal("3"))
        assert t.is_ground()

    def test_list_in_store(self):
        """ListTerm triples are hashable and can be stored in sets."""
        lt = ListTerm(items=(Literal("1"),))
        t = Triple(lt, NamedNode("p"), NamedNode("o"))
        s = {t}
        assert t in s


class TestBindingType:
    """Binding is dict[int, Term] keyed by Variable.id."""

    def test_binding_keyed_by_id(self):
        v1 = Variable("X", id=100)
        v2 = Variable("X", id=200)
        b: Binding = {v1.id: NamedNode("a"), v2.id: NamedNode("b")}
        assert b[100] == NamedNode("a")
        assert b[200] == NamedNode("b")

    def test_no_name_collision(self):
        """Same name, different scopes → independent bindings."""
        v1 = Variable("N", id=10)
        v2 = Variable("N", id=20)
        b: Binding = {v1.id: Literal("3"), v2.id: Literal("2")}
        assert b[v1.id] != b[v2.id]


class TestPathTermRemoved:
    """Path expressions are compiled to intermediate triples at parse time;
    there is no PathTerm in the term model."""

    def test_pathterm_not_exported(self):
        import pyeye.term as term_mod
        assert not hasattr(term_mod, "PathTerm")


class TestExistingTypesUnchanged:
    """All other term types still work."""

    def test_named_node(self):
        n = NamedNode("http://example.org/x")
        assert str(n) == "http://example.org/x"

    def test_literal(self):
        l = Literal("42", datatype=NamedNode("http://www.w3.org/2001/XMLSchema#integer"))
        assert l.value == "42"

    def test_existential(self):
        e = Existential("_b0")
        assert str(e) == "_:_b0"

    def test_formula(self):
        t = Triple(NamedNode("a"), NamedNode("p"), NamedNode("b"))
        f = Formula(triples=(t,))
        assert len(f.triples) == 1

    def test_triple_term(self):
        tt = TripleTerm(NamedNode("a"), NamedNode("p"), NamedNode("b"))
        assert tt.is_ground()

    def test_formula_term(self):
        ft = FormulaTerm(NamedNode("f"), args=(NamedNode("a"),))
        assert ft.is_ground()

    def test_negative_surface(self):
        f = Formula(triples=(Triple(NamedNode("a"), NamedNode("p"), NamedNode("b")),))
        ns = NegativeSurface(formula=f)
        assert ns.is_ground()

    def test_quad(self):
        q = Quad(NamedNode("s"), NamedNode("p"), NamedNode("o"), graph=NamedNode("g"))
        t = q.to_triple()
        assert t.subject == NamedNode("s")

    def test_set_term(self):
        st = SetTerm(elements=(NamedNode("a"), NamedNode("b")))
        assert st.is_ground()
