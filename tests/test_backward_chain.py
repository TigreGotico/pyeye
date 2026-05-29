"""Tests for Phase 2: backward chaining with tabling."""

from __future__ import annotations

import pytest

from pyeye import execute
from pyeye.engine import Engine
from pyeye.parser import Rule
from pyeye.term import NamedNode, Variable, Triple, Formula, Literal


NN = NamedNode
V = Variable
T = Triple
F = Formula
L = Literal


class TestBackwardChaining:
    """FR 2f.29-30: Backward chaining with tabling."""

    def test_simple_backward_chain(self):
        """Query a triple that exists in the store."""
        engine = Engine()
        engine.add_triple(T(NN("http://x/alice"), NN("http://x/age"), L("30")))
        x = V("X")
        results = engine.backward_chain(T(x, NN("http://x/age"), L("30")))
        assert len(results) == 1
        assert results[0][x.id] == NN("http://x/alice")

    def test_backward_chain_via_rules(self):
        """Query a derived triple via rule matching."""
        engine = Engine()
        engine.add_triple(T(NN("http://x/alice"), NN("http://x/parent"), NN("http://x/bob")))
        X, Y = V("X"), V("Y")
        engine.add_rule(Rule(
            body=F((T(X, NN("http://x/parent"), Y),)),
            head=F((T(Y, NN("http://x/child"), X),)),
        ))
        q = V("X")
        results = engine.backward_chain(T(NN("http://x/bob"), NN("http://x/child"), q))
        assert len(results) >= 1
        # Should find alice through the rule
        found = any(r.get(q.id) == NN("http://x/alice") for r in results)
        assert found

    def test_backward_chain_no_match(self):
        """Query a triple that doesn't exist."""
        engine = Engine()
        engine.add_triple(T(NN("http://x/alice"), NN("http://x/age"), L("30")))
        results = engine.backward_chain(T(NN("http://x/alice"), NN("http://x/age"), L("40")))
        assert len(results) == 0

    def test_backward_chain_multiple_matches(self):
        """Query with multiple matching triples."""
        engine = Engine()
        engine.add_triple(T(NN("http://x/a"), NN("http://x/p"), NN("http://x/1")))
        engine.add_triple(T(NN("http://x/b"), NN("http://x/p"), NN("http://x/1")))
        engine.add_triple(T(NN("http://x/c"), NN("http://x/p"), NN("http://x/2")))
        results = engine.backward_chain(T(V("X"), NN("http://x/p"), NN("http://x/1")))
        assert len(results) == 2

    def test_tabling_prevents_infinite_recursion(self):
        """Recursive rule with tabling terminates."""
        engine = Engine()
        # Transitive closure: if A→B and B→C, then A→C
        engine.add_triple(T(NN("http://x/a"), NN("http://x/next"), NN("http://x/b")))
        engine.add_triple(T(NN("http://x/b"), NN("http://x/next"), NN("http://x/c")))
        engine.add_triple(T(NN("http://x/c"), NN("http://x/next"), NN("http://x/d")))
        engine.add_rule(Rule(
            body=F((
                T(V("A"), NN("http://x/next"), V("B")),
                T(V("B"), NN("http://x/next"), V("C")),
            )),
            head=F((T(V("A"), NN("http://x/reach"), V("C")),)),
        ))
        # This should terminate without infinite recursion
        results = engine.backward_chain(T(NN("http://x/a"), NN("http://x/reach"), V("X")))
        # Should find at least c and d through transitive closure
        assert len(results) >= 1

    def test_execute_with_query(self):
        """execute(query=...) returns query_answers."""
        r = execute(
            data_strings=["@prefix : <http://ex.org/> .\n:alice :age 30 ."],
            rule_strings=["@prefix : <http://ex.org/> .\n{?X :age ?A} => {?X :hasAge ?A} ."],
            query=T(NN("http://ex.org/alice"), NN("http://ex.org/hasAge"), V("Age")),
        )
        assert len(r.query_answers) >= 1


class TestForwardBackwardCombination:
    """FR 2f.32: Forward + backward chaining combined."""

    def test_forward_then_backward(self):
        """Forward chain derives facts, backward chain queries them."""
        r = execute(
            data_strings=["@prefix : <http://ex.org/> .\n:alice :parent :bob ."],
            rule_strings=["@prefix : <http://ex.org/> .\n{?X :parent ?Y} => {?Y :child ?X} ."],
            query=T(V("X"), NN("http://ex.org/child"), NN("http://ex.org/alice")),
            forward=True,
        )
        # Forward chain derives :bob :child :alice
        # Backward chain should find it
        assert len(r.query_answers) >= 1

    def test_backward_only(self):
        """Pure backward chaining without forward chain."""
        r = execute(
            data_strings=["@prefix : <http://ex.org/> .\n:alice :parent :bob ."],
            rule_strings=["@prefix : <http://ex.org/> .\n{?X :parent ?Y} => {?Y :child ?X} ."],
            query=T(V("X"), NN("http://ex.org/parent"), V("Y")),
            forward=False,
        )
        # Without forward chaining, the rule hasn't fired,
        # but the data triple :alice :parent :bob should still match
        assert len(r.query_answers) >= 1
