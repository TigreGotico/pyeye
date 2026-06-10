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

    def test_execute_query_answers_keyed_by_variable_name(self):
        """execute() bindings are dict[str, Term] keyed by variable name."""
        r = execute(
            data_strings=["@prefix : <http://ex.org/> .\n:alice :age 30 ."],
            query=T(V("Who"), NN("http://ex.org/age"), V("Age")),
        )
        assert len(r.query_answers) == 1
        binding = r.query_answers[0]
        assert set(binding) == {"Who", "Age"}
        assert binding["Who"] == NN("http://ex.org/alice")


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


class TestBidirectionalBuiltins:
    """Builtins evaluable in both directions under backward chaining."""

    XSD_INT = NN("http://www.w3.org/2001/XMLSchema#integer")
    MATH = "http://www.w3.org/2000/10/swap/math#"
    LIST = "http://www.w3.org/2000/10/swap/list#"
    E = "http://eulersharp.sourceforge.net/2003/03swap/log-rules#"

    def _lit(self, n):
        return L(str(n), datatype=self.XSD_INT)

    def _lst(self, *items):
        from pyeye.term import ListTerm
        return ListTerm(tuple(items))

    def test_sum_inverse_binds_unknown(self):
        engine = Engine()
        d = V("D")
        goal = T(self._lst(d, self._lit(1)), NN(self.MATH + "sum"), self._lit(4))
        sols = engine._solve([goal], {})
        assert len(sols) == 1
        assert sols[0][d.id] == self._lit(3)

    def test_sum_ground_object_verifies(self):
        engine = Engine()
        goal = T(self._lst(self._lit(3), self._lit(1)), NN(self.MATH + "sum"),
                 self._lit(4))
        assert engine._solve([goal], {}) == [{}]
        bad = T(self._lst(self._lit(3), self._lit(1)), NN(self.MATH + "sum"),
                self._lit(5))
        assert engine._solve([bad], {}) == []

    def test_difference_inverse(self):
        engine = Engine()
        x = V("X")
        goal = T(self._lst(x, self._lit(2)), NN(self.MATH + "difference"),
                 self._lit(5))
        sols = engine._solve([goal], {})
        assert len(sols) == 1
        assert sols[0][x.id] == self._lit(7)

    def test_list_last_engine_call(self):
        engine = Engine()
        b = V("B")
        goal = T(self._lst(self._lit(3), self._lit(2), self._lit(1)),
                 NN(self.LIST + "last"), b)
        sols = engine._solve([goal], {})
        assert len(sols) == 1
        assert sols[0][b.id] == self._lit(1)

    def test_first_rest_construct_mode(self):
        engine = Engine()
        b, c, d = V("B"), V("C"), V("D")
        goal = T(b, NN(self.E + "firstRest"), self._lst(c, d))
        binding = {c.id: self._lit(6), d.id: self._lst(self._lit(7))}
        sols = engine._solve([goal], binding)
        assert len(sols) == 1
        assert sols[0][b.id] == self._lst(self._lit(6), self._lit(7))

    def test_conjunction_defers_unready_builtin(self):
        """A construct-mode goal listed first is revisited once inputs bind."""
        engine = Engine()
        b, c, d = V("B"), V("C"), V("D")
        goals = [
            T(b, NN(self.E + "firstRest"), self._lst(c, d)),
            T(self._lst(self._lit(5), self._lit(1)), NN(self.MATH + "sum"), c),
            T(self._lst(self._lit(9)), NN(self.LIST + "rest"), d),
        ]
        sols = engine._solve(goals, {})
        assert len(sols) == 1
        assert sols[0][b.id] == self._lst(self._lit(6))


class TestSelectAndSearch:
    """Nondeterministic list:select and search-style recursion."""

    XSD_INT = NN("http://www.w3.org/2001/XMLSchema#integer")
    LIST = "http://www.w3.org/2000/10/swap/list#"

    def _lit(self, n):
        return L(str(n), datatype=self.XSD_INT)

    def _lst(self, *items):
        from pyeye.term import ListTerm
        return ListTerm(tuple(items))

    def test_select_enumerates_removals(self):
        engine = Engine()
        q, rest = V("Q"), V("Rest")
        goal = T(self._lst(self._lit(1), self._lit(2), self._lit(3)),
                 NN(self.LIST + "select"), self._lst(q, rest))
        sols = engine._solve([goal], {})
        picked = {(str(b[q.id].value), len(b[rest.id].items)) for b in sols}
        assert picked == {("1", 2), ("2", 2), ("3", 2)}

    def test_first_rest_empty_list_fails(self):
        engine = Engine()
        y, ys = V("Y"), V("Ys")
        goal = T(self._lst(), NN(self.LIST + "firstRest"), self._lst(y, ys))
        assert engine._solve([goal], {}) == []

    def test_recursion_with_unbound_list_terminates(self):
        """A clause whose builtin refutes (empty list) must fail the clause
        rather than let sibling recursion run with an unbound argument."""
        from pyeye.parser import parse_n3
        src = """
        @prefix list: <http://www.w3.org/2000/10/swap/list#>.
        @prefix math: <http://www.w3.org/2000/10/swap/math#>.
        @prefix : <http://x/#>.
        {(?X ?N) :hit ?YYs} <= {
            ?YYs list:firstRest (?Y ?Ys).
            (?Y ?N) math:sum ?X.
        }.
        {(?X ?N) :hit ?YYs} <= {
            ?YYs list:firstRest (?Y ?Ys).
            (?N 1) math:sum ?N1.
            (?X ?N1) :hit ?Ys.
        }.
        """
        doc = parse_n3(src)
        engine = Engine(timeout_seconds=5)
        for r in doc.rules:
            engine.add_rule(r)
        goal = T(self._lst(self._lit(2), self._lit(1)), NN("http://x/#hit"),
                 self._lst(self._lit(1)))
        sols = engine._solve([goal], {})
        assert len(sols) == 1


def test_rule_goal_schedules_before_consumer_builtins():
    """A backward-rule goal producing variables runs before the builtins
    that consume them: it must not block on its own outputs."""
    rules = """
@prefix math: <http://www.w3.org/2000/10/swap/math#> .
@prefix c: <http://example.org/complex#> .
@prefix : <http://example.org/t#> .

{ ((2.718281828459045 0) (0 ?T)) c:exponentiation (?C ?S) . }
<=
{ ?T math:cos ?C . ?T math:sin ?S . } .

{
  ((2.718281828459045 0) (0 3.141592653589793)) c:exponentiation (?Re ?Im) .
  (?Re -1) math:difference ?dRe .
}
=>
{ :t :got ?dRe . } .
"""
    from pyeye import execute
    result = execute(rule_strings=[rules], nope=True, pass_only_new=True,
                     timeout_seconds=20)
    assert ":got 0.0" in result.triples or ":got 0 " in result.triples
