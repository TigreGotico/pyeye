"""Tests for pyeye.store — triple store with predicate indexing."""

from __future__ import annotations

from pyeye.term import NamedNode, Literal, Variable, Triple
from pyeye.store import TripleStore


NN = NamedNode
T = Triple


class TestAdd:
    def test_add_returns_true_for_new(self):
        store = TripleStore()
        assert store.add(T(NN("a"), NN("p"), NN("b"))) is True

    def test_add_returns_false_for_duplicate(self):
        store = TripleStore()
        t = T(NN("a"), NN("p"), NN("b"))
        store.add(t)
        assert store.add(t) is False

    def test_contains(self):
        store = TripleStore()
        t = T(NN("a"), NN("p"), NN("b"))
        store.add(t)
        assert store.contains(t) is True
        assert store.contains(T(NN("x"), NN("p"), NN("b"))) is False

    def test_len(self):
        store = TripleStore()
        store.add(T(NN("a"), NN("p"), NN("b")))
        store.add(T(NN("c"), NN("p"), NN("d")))
        store.add(T(NN("a"), NN("p"), NN("b")))  # duplicate
        assert len(store) == 2


class TestMatch:
    def test_match_all(self):
        store = TripleStore()
        store.add(T(NN("a"), NN("p"), NN("b")))
        store.add(T(NN("c"), NN("q"), NN("d")))
        results = list(store.match())
        assert len(results) == 2

    def test_match_by_predicate_indexed(self):
        """Uses _by_pred index when predicate is NamedNode."""
        store = TripleStore()
        store.add(T(NN("a"), NN("p"), NN("b")))
        store.add(T(NN("c"), NN("p"), NN("d")))
        store.add(T(NN("e"), NN("q"), NN("f")))
        results = list(store.match(predicate=NN("p")))
        assert len(results) == 2
        assert all(t.predicate == NN("p") for t in results)

    def test_match_by_predicate_empty(self):
        store = TripleStore()
        store.add(T(NN("a"), NN("p"), NN("b")))
        results = list(store.match(predicate=NN("nonexistent")))
        assert results == []

    def test_match_by_subject(self):
        store = TripleStore()
        store.add(T(NN("a"), NN("p"), NN("b")))
        store.add(T(NN("a"), NN("q"), NN("c")))
        store.add(T(NN("x"), NN("p"), NN("b")))
        results = list(store.match(subject=NN("a")))
        assert len(results) == 2

    def test_match_by_object(self):
        store = TripleStore()
        store.add(T(NN("a"), NN("p"), NN("b")))
        store.add(T(NN("c"), NN("q"), NN("b")))
        store.add(T(NN("a"), NN("p"), NN("d")))
        results = list(store.match(object=NN("b")))
        assert len(results) == 2

    def test_match_combined(self):
        store = TripleStore()
        store.add(T(NN("a"), NN("p"), NN("b")))
        store.add(T(NN("a"), NN("p"), NN("c")))
        store.add(T(NN("x"), NN("p"), NN("b")))
        results = list(store.match(subject=NN("a"), predicate=NN("p")))
        assert len(results) == 2

    def test_match_with_literal_object(self):
        """Predicate index is keyed on NamedNode; literal predicate falls back to full scan."""
        store = TripleStore()
        lit = Literal("hello", language="en")
        store.add(T(NN("a"), NN("label"), lit))
        results = list(store.match(predicate=NN("label"), object=lit))
        assert len(results) == 1

    def test_match_variable_predicate_not_indexed(self):
        """Variable predicate triggers full scan (not indexed)."""
        store = TripleStore()
        store.add(T(NN("a"), NN("p"), NN("b")))
        store.add(T(NN("c"), NN("q"), NN("d")))
        results = list(store.match(predicate=Variable("P")))
        assert len(results) == 2


class TestIteration:
    def test_iter(self):
        store = TripleStore()
        t1 = T(NN("a"), NN("p"), NN("b"))
        store.add(t1)
        assert list(store) == [t1]

    def test_triples_frozenset(self):
        store = TripleStore()
        store.add(T(NN("a"), NN("p"), NN("b")))
        store.add(T(NN("c"), NN("q"), NN("d")))
        assert len(store.triples()) == 2
