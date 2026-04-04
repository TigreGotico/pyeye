"""Tests for Phase 2: DJITI indexing."""

from __future__ import annotations

import pytest

from pyeye.engine import Engine
from pyeye.parser import Rule
from pyeye.term import NamedNode, Variable, Triple, Formula


NN = NamedNode
V = Variable
T = Triple
F = Formula


class TestDJITIOrdering:
    """FR 2c.15-17: DJITI reorders patterns by constraint (most-constrained-first)."""

    def test_orders_by_match_count(self):
        """Pattern C matches 1 triple, A matches 100, B matches 50.
        DJITI should order them C, B, A."""
        engine = Engine(djiti_debug=True)

        # Create store: pattern C will match 1, B matches 2, A matches many
        # Pattern C: ?X :rare :value (matches 1)
        # Pattern B: ?X :uncommon :y (matches 2)
        # Pattern A: ?X :common :z (matches 3)
        engine.add_triple(T(NN("http://x/a"), NN("http://x/common"), NN("http://x/z")))
        engine.add_triple(T(NN("http://x/b"), NN("http://x/common"), NN("http://x/z")))
        engine.add_triple(T(NN("http://x/c"), NN("http://x/common"), NN("http://x/z")))
        engine.add_triple(T(NN("http://x/a"), NN("http://x/uncommon"), NN("http://x/y")))
        engine.add_triple(T(NN("http://x/b"), NN("http://x/uncommon"), NN("http://x/y")))
        engine.add_triple(T(NN("http://x/a"), NN("http://x/rare"), NN("http://x/value")))

        # 3-pattern rule body
        rule = Rule(
            body=F((
                T(V("X"), NN("http://x/common"), V("Z")),       # matches 3
                T(V("X"), NN("http://x/uncommon"), V("Y")),     # matches 2
                T(V("X"), NN("http://x/rare"), NN("http://x/value")),  # matches 1
            )),
            head=F((T(V("X"), NN("http://x/matches"), V("Y")),)),
        )
        engine.add_rule(rule)
        engine.run()

        # Check DJITI log
        assert len(engine._djiti_log) >= 1
        log = engine._djiti_log[0]
        # The rare pattern (matching 1) should come first
        assert log["counts"][0] == 1  # rare pattern first
        # Then uncommon (matching 2)
        assert log["counts"][1] == 2  # uncommon pattern second
        # Then common (matching 3)
        assert log["counts"][2] == 3  # common pattern last

    def test_deterministic_ordering(self):
        """Same input always produces same output."""
        engine1 = Engine(djiti_debug=True)
        engine2 = Engine(djiti_debug=True)

        for e in (engine1, engine2):
            e.add_triple(T(NN("a"), NN("p"), NN("b")))
            e.add_triple(T(NN("a"), NN("q"), NN("c")))
            e.add_rule(Rule(
                body=F((
                    T(V("X"), NN("q"), V("Y")),
                    T(V("X"), NN("p"), V("Z")),
                )),
                head=F((T(V("X"), NN("r"), V("Y")),)),
            ))
            e.run()

        assert engine1._djiti_log[0]["counts"] == engine2._djiti_log[0]["counts"]

    def test_correct_results_after_reordering(self):
        """DJITI reorders but doesn't change the results."""
        engine = Engine(djiti_debug=True)
        engine.add_triple(T(NN("a"), NN("p"), NN("b")))
        engine.add_triple(T(NN("a"), NN("q"), NN("c")))
        engine.add_rule(Rule(
            body=F((
                T(V("X"), NN("q"), V("Y")),
                T(V("X"), NN("p"), V("Z")),
            )),
            head=F((T(V("X"), NN("result"), V("Y")),)),
        ))
        engine.run()

        assert len(engine.derived_triples) == 1
        assert engine.derived_triples[0].subject == NN("a")
        assert engine.derived_triples[0].predicate == NN("result")
        assert engine.derived_triples[0].object == NN("c")

    def test_djiti_disabled_by_default(self):
        """When djiti_debug=False, no log is collected."""
        engine = Engine()  # default: djiti_debug=False
        engine.add_triple(T(NN("a"), NN("p"), NN("b")))
        engine.add_rule(Rule(
            body=F((T(V("X"), NN("p"), V("Y")),)),
            head=F((T(V("X"), NN("q"), V("Y")),)),
        ))
        engine.run()
        assert engine._djiti_log == []
