"""Tests for Phase 2: incremental reasoning."""

from __future__ import annotations

import pytest

from pyeye.engine import Engine
from pyeye.parser import Rule
from pyeye.term import NamedNode, Variable, Triple, Formula


NN = NamedNode
V = Variable
T = Triple
F = Formula


class TestIncrementalReasoning:
    """FR 2j: Incremental reasoning — add triples after rules are set."""

    def test_single_pattern_rule(self):
        """Add triple triggers single-pattern rule."""
        engine = Engine()
        engine.add_rule(Rule(
            body=F((T(V("X"), NN("http://x/p"), V("Y")),)),
            head=F((T(V("Y"), NN("http://x/q"), V("X")),)),
        ))
        # Add fact after rule is set
        engine.add_triple(T(NN("http://x/a"), NN("http://x/p"), NN("http://x/b")))
        # Should derive immediately
        assert len(engine.derived_triples) == 1
        assert engine.derived_triples[0].subject == NN("http://x/b")

    def test_multi_pattern_rule_partial_match(self):
        """Add triple that completes a multi-pattern rule body."""
        engine = Engine()
        engine.add_rule(Rule(
            body=F((
                T(V("X"), NN("http://x/p"), V("Y")),
                T(V("Y"), NN("http://x/q"), V("Z")),
            )),
            head=F((T(V("X"), NN("http://x/r"), V("Z")),)),
        ))
        # Add first fact
        engine.add_triple(T(NN("http://x/a"), NN("http://x/p"), NN("http://x/b")))
        assert len(engine.derived_triples) == 0  # Not enough to fire
        # Add second fact — completes the body
        engine.add_triple(T(NN("http://x/b"), NN("http://x/q"), NN("http://x/c")))
        # Should derive immediately
        assert len(engine.derived_triples) == 1
        assert engine.derived_triples[0].object == NN("http://x/c")

    def test_cascading_incremental(self):
        """Derived facts trigger more rules incrementally."""
        engine = Engine()
        # Rule 1: :p → :q
        engine.add_rule(Rule(
            body=F((T(V("X"), NN("http://x/p"), V("Y")),)),
            head=F((T(V("X"), NN("http://x/q"), V("Y")),)),
        ))
        # Rule 2: :q → :r
        engine.add_rule(Rule(
            body=F((T(V("X"), NN("http://x/q"), V("Y")),)),
            head=F((T(V("X"), NN("http://x/r"), V("Y")),)),
        ))
        # Add fact
        engine.add_triple(T(NN("http://x/a"), NN("http://x/p"), NN("http://x/b")))
        # Should cascade through both rules
        assert len(engine.derived_triples) == 2
        preds = {t.predicate.value for t in engine.derived_triples}
        assert "http://x/q" in preds
        assert "http://x/r" in preds

    def test_no_derivation_before_rules(self):
        """Facts added before rules don't trigger incremental reasoning."""
        engine = Engine()
        # Add fact before rule
        engine.add_triple(T(NN("http://x/a"), NN("http://x/p"), NN("http://x/b")))
        assert len(engine.derived_triples) == 0
        # Now add rule — should not re-evaluate existing facts incrementally
        # (incremental only triggers on add_triple AFTER rules exist)
        engine.add_rule(Rule(
            body=F((T(V("X"), NN("http://x/p"), V("Y")),)),
            head=F((T(V("Y"), NN("http://x/q"), V("X")),)),
        ))
        assert len(engine.derived_triples) == 0
        # But a full run would derive
        engine.run()
        assert len(engine.derived_triples) == 1

    def test_incremental_with_run(self):
        """Incremental + run() together."""
        engine = Engine()
        engine.add_rule(Rule(
            body=F((T(V("X"), NN("http://x/p"), V("Y")),)),
            head=F((T(V("X"), NN("http://x/q"), V("Y")),)),
        ))
        # Add some facts incrementally
        engine.add_triple(T(NN("http://x/a"), NN("http://x/p"), NN("http://x/b")))
        engine.add_triple(T(NN("http://x/c"), NN("http://x/p"), NN("http://x/d")))
        # Run should not duplicate derivations
        engine.run()
        assert len(engine.derived_triples) == 2
