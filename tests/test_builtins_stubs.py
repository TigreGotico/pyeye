"""Tests for the newly implemented stub builtins.

Covers:
  - log:allPossibleCases
  - log:dcg
  - log:ifThenElseIn
  - log:impliesAnswer
  - log:includesNotBind
  - log:isImpliedBy / log:impliedBy
  - log:query
  - log:table
  - log:includes / log:notIncludes (were trivially wrong stubs)
"""

from __future__ import annotations

import pytest

from pyeye.builtins import (
    log_allPossibleCases,
    log_dcg,
    log_ifThenElseIn,
    log_impliesAnswer,
    log_includesNotBind,
    log_isImpliedBy,
    log_impliedBy,
    log_query,
    log_table,
    log_includes,
    log_notIncludes,
)
from pyeye.term import NamedNode, Literal, Variable, Existential, Triple, Formula
from pyeye.engine import Engine
from pyeye.store import TripleStore

NN = NamedNode
L = Literal
V = Variable
E = Existential
T = Triple


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_engine(*triples):
    """Build an Engine pre-loaded with *triples*."""
    e = Engine()
    for t in triples:
        e.store.add(t)
    return e


# ---------------------------------------------------------------------------
# log:table
# ---------------------------------------------------------------------------

class TestLogTable:
    def test_table_with_iri_arg_returns_true(self):
        result = log_table([NN("http://ex/myPred")], None)
        assert result is not None
        assert result.value == "true"

    def test_table_with_no_args_returns_true(self):
        # Directive with no predicate still succeeds
        result = log_table([], None)
        assert result is not None
        assert result.value == "true"

    def test_table_records_in_engine(self):
        e = Engine()
        e._tabled_predicates = set()
        log_table([NN("http://ex/p")], e)
        assert "http://ex/p" in e._tabled_predicates

    def test_table_unground_returns_true(self):
        # Even with a Variable arg, table is a directive and succeeds
        # (log:table ignores arg groundness — it's a directive)
        result = log_table([V("X")], None)
        # table always returns True regardless
        assert result is not None
        assert result.value == "true"


# ---------------------------------------------------------------------------
# log:allPossibleCases
# ---------------------------------------------------------------------------

class TestLogAllPossibleCases:
    def test_no_args_returns_none(self):
        assert log_allPossibleCases([], None) is None

    def test_returns_none_when_no_cases_in_store(self):
        # With no allPossibleCases triples in the store, returns None
        from pyeye.engine import Engine
        e = Engine()
        e._current_binding = {}
        result = log_allPossibleCases([V("X"), V("Y")], e)
        assert result is None

    def test_returns_cases_node_when_present(self):
        # With an allPossibleCases triple in the store, returns the cases list node
        from pyeye.engine import Engine
        from pyeye.parser import parse_n3
        e = Engine()
        parsed = parse_n3("""
@prefix log: <http://www.w3.org/2000/10/swap/log#>.
@prefix var: <http://www.w3.org/2000/10/swap/var#>.
@prefix : <urn:test:>.
(var:X) log:allPossibleCases ({ var:X a :A } { var:X a :B }).
""")
        for t in parsed.triples:
            e.add_triple(t)
        e._current_binding = {}
        result = log_allPossibleCases([V("X"), V("Y")], e)
        assert result is not None  # returns the cases list node


# ---------------------------------------------------------------------------
# log:dcg
# ---------------------------------------------------------------------------

class TestLogDcg:
    def test_no_args_returns_none(self):
        assert log_dcg([], None) is None

    def test_unground_returns_none(self):
        assert log_dcg([V("X"), V("Y")], None) is None

    def test_valid_dcg_string_returns_true(self):
        # A proper DCG rule contains -->
        result = log_dcg([L("pred"), L("sentence --> noun_phrase, verb_phrase.")], None)
        assert result is not None
        assert result.value == "true"

    def test_invalid_dcg_string_returns_false(self):
        # No --> means it's not a DCG rule
        result = log_dcg([L("pred"), L("not a dcg rule")], None)
        assert result is not None
        assert result.value == "false"

    def test_single_arg_with_dcg_arrow(self):
        result = log_dcg([L("s --> np, vp.")], None)
        assert result is not None
        assert result.value == "true"


# ---------------------------------------------------------------------------
# log:ifThenElseIn
# ---------------------------------------------------------------------------

class TestLogIfThenElseIn:
    def test_no_args_returns_none(self):
        assert log_ifThenElseIn([], None) is None

    def test_unground_returns_none(self):
        assert log_ifThenElseIn([V("X")], None) is None

    def test_true_condition_returns_then_branch(self):
        e = _make_engine()
        # Build [cond=true, then=then_val, else=else_val] as RDF list
        rdf_first = NN("http://www.w3.org/1999/02/22-rdf-syntax-ns#first")
        rdf_rest = NN("http://www.w3.org/1999/02/22-rdf-syntax-ns#rest")
        nil = E("nil")
        b0, b1, b2 = E("b0"), E("b1"), E("b2")
        e.store.add(T(b0, rdf_first, L("true")))
        e.store.add(T(b0, rdf_rest, b1))
        e.store.add(T(b1, rdf_first, L("then_result")))
        e.store.add(T(b1, rdf_rest, b2))
        e.store.add(T(b2, rdf_first, L("else_result")))
        e.store.add(T(b2, rdf_rest, nil))
        result = log_ifThenElseIn([b0, L("scope")], e)
        assert result is not None
        assert result.value == "then_result"

    def test_false_condition_returns_else_branch(self):
        e = _make_engine()
        rdf_first = NN("http://www.w3.org/1999/02/22-rdf-syntax-ns#first")
        rdf_rest = NN("http://www.w3.org/1999/02/22-rdf-syntax-ns#rest")
        nil = E("nil")
        b0, b1, b2 = E("c0"), E("c1"), E("c2")
        e.store.add(T(b0, rdf_first, L("false")))
        e.store.add(T(b0, rdf_rest, b1))
        e.store.add(T(b1, rdf_first, L("then_result")))
        e.store.add(T(b1, rdf_rest, b2))
        e.store.add(T(b2, rdf_first, L("else_result")))
        e.store.add(T(b2, rdf_rest, nil))
        result = log_ifThenElseIn([b0, L("scope")], e)
        assert result is not None
        assert result.value == "else_result"

    def test_non_list_arg_returns_arg(self):
        result = log_ifThenElseIn([L("hello")], None)
        assert result is not None
        assert result.value == "hello"


# ---------------------------------------------------------------------------
# log:impliesAnswer
# ---------------------------------------------------------------------------

class TestLogImpliesAnswer:
    def test_no_args_returns_none(self):
        assert log_impliesAnswer([], None) is None

    def test_unground_returns_none(self):
        assert log_impliesAnswer([V("X"), V("Y")], None) is None

    def test_with_args_returns_true(self):
        result = log_impliesAnswer([NN("http://ex/p"), NN("http://ex/q")], None)
        assert result is not None
        assert result.value == "true"

    def test_records_in_engine_answer_predicates(self):
        e = Engine()
        e._answer_predicates = set()
        log_impliesAnswer([NN("http://ex/p"), NN("http://ex/q")], e)
        assert "http://ex/p" in e._answer_predicates


# ---------------------------------------------------------------------------
# log:includesNotBind
# ---------------------------------------------------------------------------

class TestLogIncludesNotBind:
    def test_no_args_unground_returns_none(self):
        assert log_includesNotBind([V("X")], None) is None

    def test_literal_true_pattern_succeeds(self):
        e = _make_engine()
        result = log_includesNotBind([L("scope"), L("true")], e)
        assert result is not None
        assert result.value == "true"

    def test_named_node_pattern_found_in_store(self):
        p = NN("http://ex/p")
        e = _make_engine(T(NN("http://ex/s"), p, NN("http://ex/o")))
        result = log_includesNotBind([L("scope"), p], e)
        assert result is not None
        assert result.value == "true"

    def test_named_node_pattern_not_in_store(self):
        p = NN("http://ex/missing")
        e = _make_engine()
        result = log_includesNotBind([L("scope"), p], e)
        assert result is not None
        assert result.value == "false"

    def test_existential_subject_found(self):
        subj = E("myblank")
        e = _make_engine(T(subj, NN("http://ex/p"), L("val")))
        result = log_includesNotBind([L("scope"), subj], e)
        assert result is not None
        assert result.value == "true"


# ---------------------------------------------------------------------------
# log:isImpliedBy / log:impliedBy
# ---------------------------------------------------------------------------

class TestLogIsImpliedBy:
    def test_no_args_returns_none(self):
        assert log_isImpliedBy([], None) is None

    def test_unground_returns_none(self):
        assert log_isImpliedBy([V("X")], None) is None

    def test_named_node_in_store_as_predicate(self):
        p = NN("http://ex/p")
        e = _make_engine(T(NN("http://ex/s"), p, NN("http://ex/o")))
        result = log_isImpliedBy([p, L("premise")], e)
        assert result is not None
        assert result.value == "true"

    def test_named_node_in_derived_triples(self):
        e = _make_engine()
        t = T(NN("http://ex/s"), NN("http://ex/p"), NN("http://ex/o"))
        e._derived_triples = [t]
        result = log_isImpliedBy([NN("http://ex/s"), L("premise")], e)
        assert result is not None
        assert result.value == "true"

    def test_named_node_absent_returns_false(self):
        e = _make_engine()
        result = log_isImpliedBy([NN("http://ex/absent"), L("premise")], e)
        assert result is not None
        assert result.value == "false"

    def test_triple_in_store_returns_true(self):
        s = NN("http://ex/s")
        p = NN("http://ex/p")
        o = NN("http://ex/o")
        e = _make_engine(T(s, p, o))
        result = log_isImpliedBy([T(s, p, o), L("premise")], e)
        assert result is not None
        assert result.value == "true"

    def test_triple_not_in_store_returns_false(self):
        e = _make_engine()
        result = log_isImpliedBy(
            [T(NN("http://ex/x"), NN("http://ex/p"), NN("http://ex/y")), L("premise")],
            e
        )
        assert result is not None
        assert result.value == "false"


class TestLogImpliedBy:
    """log:impliedBy delegates to log:isImpliedBy."""

    def test_no_args_returns_none(self):
        assert log_impliedBy([], None) is None

    def test_named_node_in_store(self):
        p = NN("http://ex/q")
        e = _make_engine(T(NN("http://ex/a"), p, NN("http://ex/b")))
        result = log_impliedBy([p, L("premise")], e)
        assert result is not None
        assert result.value == "true"


# ---------------------------------------------------------------------------
# log:query
# ---------------------------------------------------------------------------

class TestLogQuery:
    def test_no_args_returns_none(self):
        assert log_query([], None) is None

    def test_unground_returns_none(self):
        assert log_query([V("X")], None) is None

    def test_named_node_query_returns_matching_triples(self):
        p = NN("http://ex/myPred")
        t1 = T(NN("http://ex/s1"), p, NN("http://ex/o1"))
        t2 = T(NN("http://ex/s2"), p, NN("http://ex/o2"))
        e = _make_engine(t1, t2)
        result = log_query([p], e)
        assert result is not None
        assert t1 in result
        assert t2 in result

    def test_named_node_no_matches_returns_empty(self):
        p = NN("http://ex/missing")
        e = _make_engine()
        result = log_query([p], e)
        assert result == []

    def test_existential_query_returns_triples_with_subject(self):
        subj = E("myblank")
        t1 = T(subj, NN("http://ex/p"), L("val"))
        e = _make_engine(t1)
        result = log_query([subj], e)
        assert result is not None
        assert t1 in result

    def test_formula_query_uses_match_formula(self):
        """Query with a Formula object uses engine._match_formula."""
        e = _make_engine(
            T(NN("http://ex/a"), NN("http://ex/type"), NN("http://ex/Thing"))
        )
        # Build a minimal Formula with one pattern triple
        pattern = T(V("S"), NN("http://ex/type"), NN("http://ex/Thing"))
        formula = Formula(triples=[pattern])
        result = log_query([formula], e)
        # Should return at least the matching triple
        assert result is not None
        assert len(result) >= 1

    def test_fallback_literal_returns_all_store_triples(self):
        """Any other term type returns all store triples."""
        t = T(NN("http://ex/s"), NN("http://ex/p"), NN("http://ex/o"))
        e = _make_engine(t)
        result = log_query([L("anything")], e)
        assert result is not None
        assert t in result


# ---------------------------------------------------------------------------
# log:includes (was a trivially-True stub)
# ---------------------------------------------------------------------------

class TestLogIncludes:
    def test_named_node_found(self):
        p = NN("http://ex/found")
        e = _make_engine(T(NN("http://ex/s"), p, NN("http://ex/o")))
        result = log_includes([L("scope"), p], e)
        assert result is not None
        assert result.value == "true"

    def test_named_node_not_found(self):
        p = NN("http://ex/missing")
        e = _make_engine()
        result = log_includes([L("scope"), p], e)
        assert result is not None
        assert result.value == "false"

    def test_literal_true_always_true(self):
        e = _make_engine()
        result = log_includes([L("scope"), L("true")], e)
        assert result is not None
        assert result.value == "true"

    def test_triple_pattern_found(self):
        s = NN("http://ex/s")
        p = NN("http://ex/p")
        o = NN("http://ex/o")
        e = _make_engine(T(s, p, o))
        result = log_includes([L("scope"), T(s, p, o)], e)
        assert result is not None
        assert result.value == "true"

    def test_triple_pattern_not_found(self):
        e = _make_engine()
        result = log_includes(
            [L("scope"), T(NN("http://ex/x"), NN("http://ex/p"), NN("http://ex/y"))],
            e
        )
        assert result is not None
        assert result.value == "false"

    def test_unground_returns_none(self):
        assert log_includes([V("X"), V("Y")], None) is None


# ---------------------------------------------------------------------------
# log:notIncludes (was a trivially-False stub)
# ---------------------------------------------------------------------------

class TestLogNotIncludes:
    def test_named_node_present_returns_false(self):
        p = NN("http://ex/found")
        e = _make_engine(T(NN("http://ex/s"), p, NN("http://ex/o")))
        result = log_notIncludes([L("scope"), p], e)
        assert result is not None
        assert result.value == "false"

    def test_named_node_absent_returns_true(self):
        p = NN("http://ex/missing")
        e = _make_engine()
        result = log_notIncludes([L("scope"), p], e)
        assert result is not None
        assert result.value == "true"

    def test_unground_returns_none(self):
        assert log_notIncludes([V("X"), V("Y")], None) is None


# ---------------------------------------------------------------------------
# Coverage for previously uncovered branches
# ---------------------------------------------------------------------------

class TestLogIncludesCoverage:
    def test_single_arg_no_pattern_returns_true(self):
        """log_includes with only one arg (pattern=None) returns True."""
        e = _make_engine()
        result = log_includes([L("scope")], e)
        assert result is not None
        assert result.value == "true"

    def test_existential_found_as_subject(self):
        subj = E("ex_subj")
        e = _make_engine(T(subj, NN("http://ex/p"), L("val")))
        result = log_includes([L("scope"), subj], e)
        assert result is not None
        assert result.value == "true"

    def test_existential_not_in_store(self):
        subj = E("ex_missing")
        e = _make_engine()
        result = log_includes([L("scope"), subj], e)
        assert result is not None
        assert result.value == "false"


class TestLogIfThenElseInCoverage:
    def test_named_node_condition_true_when_in_store(self):
        """NamedNode condition is true if it has triples in the store."""
        cond_node = NN("http://ex/cond")
        e = _make_engine(T(cond_node, NN("http://ex/p"), L("v")))
        rdf_first = NN("http://www.w3.org/1999/02/22-rdf-syntax-ns#first")
        rdf_rest = NN("http://www.w3.org/1999/02/22-rdf-syntax-ns#rest")
        nil = E("nil")
        b0, b1, b2 = E("nn0"), E("nn1"), E("nn2")
        e.store.add(T(b0, rdf_first, cond_node))
        e.store.add(T(b0, rdf_rest, b1))
        e.store.add(T(b1, rdf_first, L("then_val")))
        e.store.add(T(b1, rdf_rest, b2))
        e.store.add(T(b2, rdf_first, L("else_val")))
        e.store.add(T(b2, rdf_rest, nil))
        result = log_ifThenElseIn([b0, L("scope")], e)
        assert result is not None
        assert result.value == "then_val"

    def test_existential_condition_true_when_in_store(self):
        """Existential condition is true if it is a subject in the store."""
        cond_ex = E("cond_bnode")
        e = _make_engine(T(cond_ex, NN("http://ex/p"), L("v")))
        rdf_first = NN("http://www.w3.org/1999/02/22-rdf-syntax-ns#first")
        rdf_rest = NN("http://www.w3.org/1999/02/22-rdf-syntax-ns#rest")
        nil = E("nil")
        b0, b1, b2 = E("ex0"), E("ex1"), E("ex2")
        e.store.add(T(b0, rdf_first, cond_ex))
        e.store.add(T(b0, rdf_rest, b1))
        e.store.add(T(b1, rdf_first, L("then_val")))
        e.store.add(T(b1, rdf_rest, b2))
        e.store.add(T(b2, rdf_first, L("else_val")))
        e.store.add(T(b2, rdf_rest, nil))
        result = log_ifThenElseIn([b0, L("scope")], e)
        assert result is not None
        assert result.value == "then_val"


class TestLogIsImpliedByCoverage:
    def test_named_node_found_as_subject_in_store(self):
        """NamedNode that is a subject (not predicate) is also implied."""
        s = NN("http://ex/subj")
        e = _make_engine(T(s, NN("http://ex/p"), NN("http://ex/o")))
        # Not a predicate match — make sure predicate match fails first
        result = log_isImpliedBy([NN("http://ex/subj"), L("premise")], e)
        assert result is not None
        assert result.value == "true"

    def test_derived_triple_equality(self):
        """When a derived triple equals the conclusion term directly."""
        e = _make_engine()
        t = T(NN("http://ex/s"), NN("http://ex/p"), NN("http://ex/o"))
        e._derived_triples = [t]
        # Pass the triple itself as conclusion (not a NamedNode)
        result = log_isImpliedBy([t, L("premise")], e)
        assert result is not None
        assert result.value == "true"


class TestLogLocalN3StringCoverage:
    from pyeye.builtins import log_localN3String

    def test_named_node_with_prefix_shortening(self):
        """log:localN3String shortens IRIs when engine has _prefixes."""
        from pyeye.builtins import log_localN3String
        e = Engine()
        e._prefixes = {"ex": "http://example.org/"}
        result = log_localN3String([NN("http://example.org/Foo")], e)
        assert result is not None
        assert result.value == "ex:Foo"

    def test_named_node_no_matching_prefix(self):
        """log:localN3String returns full IRI when no prefix matches."""
        from pyeye.builtins import log_localN3String
        e = Engine()
        e._prefixes = {"other": "http://other.org/"}
        result = log_localN3String([NN("http://example.org/Foo")], e)
        assert result is not None
        assert result.value == "http://example.org/Foo"

    def test_named_node_no_prefixes_attr(self):
        """log:localN3String returns IRI string when no _prefixes attr."""
        from pyeye.builtins import log_localN3String
        result = log_localN3String([NN("http://example.org/Bar")], None)
        assert result is not None
        assert result.value == "http://example.org/Bar"
