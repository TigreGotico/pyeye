"""Tests for the specialised meta/list builtins.

Covers ``log:callWithOptional``, ``log:collectAllIn``, ``log:forAllIn``,
``log:allPossibleCases``, ``list:member`` (generative / formula patterns),
``log:equalTo`` (unification), and ``rdf:first`` / ``rdf:rest`` list accessors.
These exercise the EYE proof-by-cases / scoring / policy patterns end-to-end.
"""

from __future__ import annotations

from pyeye import execute
from pyeye.parser import parse_n3
from pyeye.engine import Engine
from pyeye.builtins import (
    log_equalTo, rdf_first, rdf_rest, list_member, BindingsList,
)
from pyeye.term import NamedNode, Literal, Variable, ListTerm


NN = NamedNode
L = Literal
V = Variable


def _derive(rule_src: str) -> str:
    r = execute(rule_strings=[rule_src], timeout_seconds=10)
    return r.triples


# ---------------------------------------------------------------------------
# log:equalTo — unification semantics
# ---------------------------------------------------------------------------

class TestLogEqualToUnification:
    def test_binds_subject_variable(self):
        eng = Engine()
        eng._current_binding = {}
        x = V("X")
        res = log_equalTo([x, L("5")], eng)
        assert res is not None and res.value == "true"
        assert eng._current_binding[x.id] == L("5")

    def test_binds_object_variable(self):
        eng = Engine()
        eng._current_binding = {}
        y = V("Y")
        res = log_equalTo([NN("urn:a"), y], eng)
        assert res is not None and res.value == "true"
        assert eng._current_binding[y.id] == NN("urn:a")

    def test_ground_equal(self):
        res = log_equalTo([L("a"), L("a")], None)
        assert res is not None and res.value == "true"

    def test_ground_unequal(self):
        res = log_equalTo([L("a"), L("b")], None)
        assert res is not None and res.value == "false"

    def test_unground_no_engine_returns_none(self):
        assert log_equalTo([V("X"), L("a")], None) is None


# ---------------------------------------------------------------------------
# rdf:first / rdf:rest over native lists
# ---------------------------------------------------------------------------

class TestRdfListAccessors:
    def test_first(self):
        res = rdf_first([NN("urn:a"), NN("urn:b"), NN("urn:c"), V("x")], None)
        assert res == NN("urn:a")

    def test_rest(self):
        res = rdf_rest([NN("urn:a"), NN("urn:b"), NN("urn:c"), V("r")], None)
        assert res == ListTerm(items=(NN("urn:b"), NN("urn:c")))

    def test_first_direct_listterm(self):
        lst = ListTerm(items=(NN("urn:a"), NN("urn:b")))
        assert rdf_first([lst, V("x")], None) == NN("urn:a")

    def test_first_scenario(self):
        out = _derive(
            "@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>.\n"
            "@prefix : <http://example.org/#>.\n"
            "{ (:a :b :c) rdf:first ?x. } => { :s :first ?x. }.\n"
        )
        assert ":s" in out and ":first" in out and ":a" in out

    def test_rest_then_first_scenario(self):
        out = _derive(
            "@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>.\n"
            "@prefix : <http://example.org/#>.\n"
            "{ (:a :b :c) rdf:rest ?r. ?r rdf:first ?y. } => { :s :second ?y. }.\n"
        )
        assert ":second" in out and ":b" in out


# ---------------------------------------------------------------------------
# list:member — generative and formula-pattern
# ---------------------------------------------------------------------------

class TestListMember:
    def test_ground_member_true(self):
        res = list_member([NN("urn:a"), NN("urn:b"), NN("urn:a")], None)
        assert res is not None and res.value == "true"

    def test_ground_member_false(self):
        res = list_member([NN("urn:a"), NN("urn:b"), NN("urn:z")], None)
        assert res is not None and res.value == "false"

    def test_generative_variable(self):
        eng = Engine()
        eng._current_binding = {}
        v = V("M")
        res = list_member([NN("urn:a"), NN("urn:b"), v], eng)
        assert isinstance(res, BindingsList)
        vals = {str(b[v.id]) for b in res.bindings}
        assert vals == {"urn:a", "urn:b"}


# ---------------------------------------------------------------------------
# End-to-end EYE scenarios
# ---------------------------------------------------------------------------

class TestCallWithOptionalScoring:
    SCORE = """
@prefix log: <http://www.w3.org/2000/10/swap/log#>.
@prefix math: <http://www.w3.org/2000/10/swap/math#>.
@prefix : <http://example.org/#>.

:s :p1 true.
:s :p3 true.

{
    true log:callWithOptional {:s :p1 true. ?C1 log:equalTo 1}, {?C1 log:equalTo 0}.
    true log:callWithOptional {:s :p2 true. ?C2 log:equalTo 1}, {?C2 log:equalTo 0}.
    true log:callWithOptional {:s :p3 true. ?C3 log:equalTo 1}, {?C3 log:equalTo 0}.
    (?C1 ?C2 ?C3) math:sum ?C.
    ?C math:notLessThan 2.
} => {
    :s a :TwoOfThree.
}.
"""

    def test_two_of_three(self):
        out = _derive(self.SCORE)
        assert ":TwoOfThree" in out

    def test_optional_skipped_when_absent(self):
        # only p1 present → score 1 < 2 → not derived
        src = self.SCORE.replace(":s :p3 true.\n", "")
        out = _derive(src)
        assert ":TwoOfThree" not in out


class TestCollectAllInFilter:
    SRC = """
@prefix list: <http://www.w3.org/2000/10/swap/list#>.
@prefix string: <http://www.w3.org/2000/10/swap/string#>.
@prefix log: <http://www.w3.org/2000/10/swap/log#>.
@prefix : <http://example.org/#>.

:Let :param "Huey".
:Let :param "Dewey".
:Let :param "Louie".

{
    (?param { :Let :param ?param. ?param string:lessThan "Louie" } ?filtered) log:collectAllIn ?scope.
    ?filtered list:length 2.
} => {
    :result :is ?filtered.
}.
"""

    def test_filter_collects_two(self):
        out = _derive(self.SRC)
        assert ":result" in out and "Huey" in out and "Dewey" in out
        assert "Louie" not in out.split(":is")[-1]


class TestForAllInProofByCases:
    SRC = """
@prefix list: <http://www.w3.org/2000/10/swap/list#>.
@prefix log: <http://www.w3.org/2000/10/swap/log#>.
@prefix : <http://example.org/#>.

:water a :InorganicCompound.

{ ?A a :InorganicCompound. } => {
    (?A) log:allPossibleCases ( { ?A :is :solid } { ?A :is :liquid } { ?A :is :gas } )
}.

{ ?A :is :solid } => { ?A :is :observable }.
{ ?A :is :liquid } => { ?A :is :observable }.
{ ?A :is :gas } => { ?A :is :observable }.

{
    (?A) log:allPossibleCases ?B.
    (
        { ?B list:member { ?A :is ?C } }
        { { ?A :is ?C } => { ?A :is :observable } }
    ) log:forAllIn ?SCOPE.
} => {
    ?A :is :observable.
}.
"""

    def test_water_observable(self):
        out = _derive(self.SRC)
        assert ":observable" in out
