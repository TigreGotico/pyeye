"""Tests for answer-table memoization (SLG-style tabling) in backward chaining.

These cover the cases that would loop forever or blow up exponentially without
answer sharing across depths: deep linear recursion, doubly-recursive (tree)
recursion with massive subgoal overlap, and a left-recursive transitive closure
over a cyclic graph (which must terminate, not loop).
"""

from __future__ import annotations

import sys
import time

import pytest

from pyeye.engine import Engine
from pyeye.parser import Rule, parse_n3
from pyeye.term import NamedNode, Variable, Triple, Formula, Literal

NN = NamedNode
V = Variable
T = Triple
F = Formula
XSD_INT = NamedNode("http://www.w3.org/2001/XMLSchema#integer")


def _int(n: int) -> Literal:
    return Literal(str(n), datatype=XSD_INT)


def _build(rules_n3: str, timeout: float = 30.0) -> Engine:
    eng = Engine(timeout_seconds=timeout)
    parsed = parse_n3(rules_n3)
    for r in parsed.rules:
        eng.add_rule(r)
    for t in parsed.triples:
        eng.add_triple(t)
    return eng


SUM_RULES = """
@prefix math: <http://www.w3.org/2000/10/swap/math#>.
@prefix : <https://example.org/ns#>.
0 :sum 0.
{ ?N :sum ?Sum } <= {
    ?N math:greaterThan 0.
    (?N 1) math:difference ?N1.
    ?N1 :sum ?Sum1.
    (?Sum1 ?N) math:sum ?Sum.
}.
"""


class TestLinearRecursionTabling:
    """A deep linear recursion stays tractable and answers correctly."""

    def test_deep_linear_recursion_terminates_fast(self):
        eng = _build(SUM_RULES)
        s = V("Sum")
        q = T(_int(2000), NN("https://example.org/ns#sum"), s)
        start = time.time()
        res = eng.backward_chain(q)
        elapsed = time.time() - start
        # sum 0..2000 = 2000*2001/2 = 2001000
        assert len(res) == 1
        assert res[0][s.id] == _int(2001000)
        # Without tabling this is quadratic-or-worse and blows the budget;
        # with tabling it is comfortably linear.
        assert elapsed < 10.0, f"too slow: {elapsed:.2f}s"

    def test_linear_recursion_scaling_is_subquadratic(self):
        """Doubling the depth must not quadruple the time."""
        def run(n: int) -> float:
            eng = _build(SUM_RULES)
            s = V("Sum")
            t0 = time.time()
            eng.backward_chain(T(_int(n), NN("https://example.org/ns#sum"), s))
            return time.time() - t0

        t_small = run(400)
        t_big = run(1600)  # 4x the depth
        # Quadratic would be ~16x; tabling keeps it well under that.
        assert t_big < t_small * 10 + 1.0


FIB_RULES = """
@prefix math: <http://www.w3.org/2000/10/swap/math#>.
@prefix : <https://example.org/ns#>.
0 :fib 0.
1 :fib 1.
{ ?N :fib ?F } <= {
    ?N math:greaterThan 1.
    (?N 1) math:difference ?N1.
    (?N 2) math:difference ?N2.
    ?N1 :fib ?F1.
    ?N2 :fib ?F2.
    (?F1 ?F2) math:sum ?F.
}.
"""


class TestTreeRecursionTabling:
    """Doubly-recursive fibonacci: exponential without tabling, linear with."""

    def test_fibonacci_with_overlap(self):
        eng = _build(FIB_RULES)
        f = V("F")
        # fib(30) = 832040 — 2.7M naive calls without memoization.
        q = T(_int(30), NN("https://example.org/ns#fib"), f)
        start = time.time()
        res = eng.backward_chain(q)
        elapsed = time.time() - start
        assert len(res) == 1
        assert res[0][f.id] == _int(832040)
        assert elapsed < 10.0, f"too slow: {elapsed:.2f}s"


PATH_RULES = """
@prefix : <https://example.org/ns#>.
:a :edge :b.
:b :edge :c.
:c :edge :a.
:c :edge :d.
{ ?X :path ?Y } <= { ?X :edge ?Y }.
{ ?X :path ?Y } <= { ?X :edge ?Z. ?Z :path ?Y }.
"""


class TestCyclicTransitiveClosure:
    """Left/right-recursive reachability over a CYCLIC graph must terminate and
    return the exact reachable set (no missing, no spurious answers)."""

    def test_cyclic_path_terminates_with_correct_answers(self):
        eng = _build(PATH_RULES)
        y = V("Y")
        ns = "https://example.org/ns#"
        start = time.time()
        res = eng.backward_chain(T(NN(ns + "a"), NN(ns + "path"), y))
        elapsed = time.time() - start
        reached = {r[y.id] for r in res}
        # From a: a->b->c->{a,d}; everything is reachable.
        assert reached == {NN(ns + "a"), NN(ns + "b"),
                           NN(ns + "c"), NN(ns + "d")}
        assert elapsed < 5.0, f"cyclic closure too slow/looping: {elapsed:.2f}s"

    def test_self_loop_terminates(self):
        rules = """
@prefix : <https://example.org/ns#>.
:a :edge :a.
{ ?X :reach ?Y } <= { ?X :edge ?Y }.
{ ?X :reach ?Y } <= { ?X :edge ?Z. ?Z :reach ?Y }.
"""
        eng = _build(rules)
        y = V("Y")
        ns = "https://example.org/ns#"
        res = eng.backward_chain(T(NN(ns + "a"), NN(ns + "reach"), y))
        assert {r[y.id] for r in res} == {NN(ns + "a")}


class TestTablingSoundness:
    """Tabling must not drop or invent answers vs. the expected answer set."""

    def test_multiple_answers_preserved(self):
        rules = """
@prefix : <https://example.org/ns#>.
:a :p :1. :a :p :2. :a :p :3.
{ ?X :q ?Y } <= { ?X :p ?Y }.
"""
        eng = _build(rules)
        y = V("Y")
        ns = "https://example.org/ns#"
        res = eng.backward_chain(T(NN(ns + "a"), NN(ns + "q"), y))
        assert {r[y.id] for r in res} == {NN(ns + "1"), NN(ns + "2"), NN(ns + "3")}

    def test_no_match_returns_empty(self):
        eng = _build(SUM_RULES)
        # Negative N has no proof (base is 0, rule needs N>0).
        res = eng.backward_chain(
            T(_int(-5), NN("https://example.org/ns#sum"), V("S")))
        assert res == []
