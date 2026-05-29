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
        X, Y = V("X"), V("Y")
        engine.add_rule(Rule(
            body=F((T(X, NN("http://x/p"), Y),)),
            head=F((T(Y, NN("http://x/q"), X),)),
        ))
        # Add fact after rule is set
        engine.add_triple(T(NN("http://x/a"), NN("http://x/p"), NN("http://x/b")))
        # Should derive immediately
        assert len(engine.derived_triples) == 1
        assert engine.derived_triples[0].subject == NN("http://x/b")

    def test_multi_pattern_rule_partial_match(self):
        """Add triple that completes a multi-pattern rule body."""
        engine = Engine()
        X, Y, Z = V("X"), V("Y"), V("Z")
        engine.add_rule(Rule(
            body=F((
                T(X, NN("http://x/p"), Y),
                T(Y, NN("http://x/q"), Z),
            )),
            head=F((T(X, NN("http://x/r"), Z),)),
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
        X1, Y1 = V("X"), V("Y")
        engine.add_rule(Rule(
            body=F((T(X1, NN("http://x/p"), Y1),)),
            head=F((T(X1, NN("http://x/q"), Y1),)),
        ))
        # Rule 2: :q → :r
        X2, Y2 = V("X"), V("Y")
        engine.add_rule(Rule(
            body=F((T(X2, NN("http://x/q"), Y2),)),
            head=F((T(X2, NN("http://x/r"), Y2),)),
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
        X, Y = V("X"), V("Y")
        engine.add_rule(Rule(
            body=F((T(X, NN("http://x/p"), Y),)),
            head=F((T(Y, NN("http://x/q"), X),)),
        ))
        assert len(engine.derived_triples) == 0
        # But a full run would derive
        engine.run()
        assert len(engine.derived_triples) == 1

    def test_incremental_with_run(self):
        """Incremental + run() together."""
        engine = Engine()
        X, Y = V("X"), V("Y")
        engine.add_rule(Rule(
            body=F((T(X, NN("http://x/p"), Y),)),
            head=F((T(X, NN("http://x/q"), Y),)),
        ))
        # Add some facts incrementally
        engine.add_triple(T(NN("http://x/a"), NN("http://x/p"), NN("http://x/b")))
        engine.add_triple(T(NN("http://x/c"), NN("http://x/p"), NN("http://x/d")))
        # Run should not duplicate derivations
        engine.run()
        assert len(engine.derived_triples) == 2

    def test_incremental_multi_new_triple_completion(self):
        """M12 fix: Rule fires when last needed triple is added.

        Rule body has [A, B, C]. Existing store has A and B.
        When C is added incrementally, the rule should fire.
        """
        engine = Engine()
        X, Y, Z, W = V("X"), V("Y"), V("Z"), V("W")
        engine.add_rule(Rule(
            body=F((
                T(X, NN("http://x/p"), Y),
                T(Y, NN("http://x/q"), Z),
                T(Z, NN("http://x/r"), W),
            )),
            head=F((T(X, NN("http://x/derived"), W),)),
        ))
        # Add first two facts (not enough to fire)
        engine.add_triple(T(NN("http://x/a"), NN("http://x/p"), NN("http://x/b")))
        engine.add_triple(T(NN("http://x/b"), NN("http://x/q"), NN("http://x/c")))
        assert len(engine.derived_triples) == 0

        # Add third fact — completes the body, should fire
        engine.add_triple(T(NN("http://x/c"), NN("http://x/r"), NN("http://x/d")))
        assert len(engine.derived_triples) == 1
        assert engine.derived_triples[0].subject == NN("http://x/a")
        assert engine.derived_triples[0].object == NN("http://x/d")

    def test_incremental_cascading_multi_rules(self):
        """M12 fix: Multiple rules cascade from single incremental add."""
        engine = Engine()
        Xa, Ya = V("X"), V("Y")
        engine.add_rule(Rule(
            body=F((T(Xa, NN("http://x/p"), Ya),)),
            head=F((T(Xa, NN("http://x/q"), Ya),)),
        ))
        Xb, Yb = V("X"), V("Y")
        engine.add_rule(Rule(
            body=F((T(Xb, NN("http://x/q"), Yb),)),
            head=F((T(Xb, NN("http://x/r"), Yb),)),
        ))
        Xc, Yc = V("X"), V("Y")
        engine.add_rule(Rule(
            body=F((T(Xc, NN("http://x/r"), Yc),)),
            head=F((T(Xc, NN("http://x/s"), Yc),)),
        ))
        # Single add should cascade through all three rules
        engine.add_triple(T(NN("http://x/a"), NN("http://x/p"), NN("http://x/b")))
        assert len(engine.derived_triples) == 3
        preds = {t.predicate.value for t in engine.derived_triples}
        assert "http://x/q" in preds
        assert "http://x/r" in preds
        assert "http://x/s" in preds
