"""Engine/builtin/parser behaviours aligned with EYE corpus semantics."""

from __future__ import annotations

from pyeye import execute
from pyeye.engine import Engine
from pyeye.parser import parse_n3
from pyeye.term import (
    Existential,
    ListTerm,
    Literal,
    NamedNode,
    Triple,
    Variable,
)


def _lit(v: str, dt: str) -> Literal:
    return Literal(v, datatype=NamedNode(f"http://www.w3.org/2001/XMLSchema#{dt}"))


def _run(src: str) -> Engine:
    doc = parse_n3(src)
    eng = Engine()
    for t in doc.triples:
        eng.store.add(t)
    for r in doc.rules:
        eng.add_rule(r)
    eng.run()
    return eng


class TestBuiltinGoalDeferral:
    """A builtin goal scheduled before the goal that binds its inputs is
    retried instead of falsifying the conjunction (euler-identity check4)."""

    def test_equalto_before_binder(self):
        eng = _run("""
@prefix : <http://example.org/#>.
@prefix math: <http://www.w3.org/2000/10/swap/math#>.
:m1 :value 6 .
{
  :m1 :value ?A .
  ?A math:equalTo ?B .
  (2 3) math:product ?B .
}
=>
{ :check :ok true . } .
""")
        assert any("check" in str(t.subject) for t in eng._derived_triples)

    def test_unsatisfiable_builtin_still_fails(self):
        eng = _run("""
@prefix : <http://example.org/#>.
@prefix math: <http://www.w3.org/2000/10/swap/math#>.
:m1 :value 6 .
{
  :m1 :value ?A .
  ?A math:equalTo 7 .
}
=>
{ :check :ok true . } .
""")
        assert not eng._derived_triples


class TestExponentiationModes:
    def test_inverse_exponent(self):
        # (10 ?C) math:exponentiation 1000 → ?C = 3 (control-system)
        eng = _run("""
@prefix : <http://example.org/#>.
@prefix math: <http://www.w3.org/2000/10/swap/math#>.
:d :measurement 1000 .
{
  :d :measurement ?D .
  (10 ?C) math:exponentiation ?D .
}
=>
{ :d :log ?C . } .
""")
        vals = [t.object.value for t in eng._derived_triples]
        assert any(abs(float(v) - 3.0) < 1e-12 for v in vals)

    def test_unit_base_stays_integer(self):
        from pyeye.builtins import math_exponentiation
        r = math_exponentiation([_lit("1", "integer"), _lit("0.5", "double")], None)
        assert r.value == "1"
        assert r.datatype.value.endswith("integer")

    def test_zero_base_positive_exponent(self):
        from pyeye.builtins import math_exponentiation
        r = math_exponentiation([_lit("0", "integer"), _lit("0.5", "double")], None)
        assert r.value == "0"
        assert r.datatype.value.endswith("integer")


class TestLogSkolem:
    def test_same_key_same_skolem_across_rules(self):
        eng = _run("""
@prefix : <http://example.org/#>.
@prefix log: <http://www.w3.org/2000/10/swap/log#>.
{ ?A :loves ?B . } <= { (?A) log:skolem ?B . } .
{ ?B :is :lonely . } <= { (?A) log:skolem ?B . } .
{ :bob :loves ?X . ?X :is :lonely . } => { :found :it ?X . } .
:seed :p :o .
""")
        assert any("found" in str(t.subject) for t in eng._derived_triples)

    def test_inverse_recovers_key(self):
        from pyeye.builtins import log_skolem, BindingsList
        eng = Engine()
        bob = NamedNode("http://example.org/#bob")
        out = Variable("S")
        sk = log_skolem([bob, out], eng)
        assert isinstance(sk, Existential)
        # Inverse: unbound key, bound skolem → recover :bob
        key = Variable("A")
        res = log_skolem([key, sk], eng)
        assert isinstance(res, BindingsList)
        assert res.bindings[0][key.id] == bob


class TestVariableRuleHead:
    """``{ :Einstein :says ?phi } => ?phi`` asserts the bound formula (qiana)."""

    def test_head_var_asserts_formula(self):
        eng = _run("""
@prefix : <https://eyereasoner.github.io/ns#>.
{ :Einstein :says ?phi } => ?phi .
:Einstein :says { { ?x a :glitter } => { ?x :notNecessarilyA :gold } } .
:northStar a :glitter .
""")
        facts = {str(t) for t in eng.store}
        assert any("notNecessarilyA" in f and "northStar" in f for f in facts)


class TestRulesAreStatements:
    def test_meta_rule_derives_rule(self):
        # {{?x :p :a} => {?x :q :b}} => {{?x :r :c} => {?x :s :d}} applied
        # to the ground rule {:e :p :a} => {:e :q :b} (iq scenario)
        eng = _run("""
@prefix : <http://example.org/test#>.
{:e :p :a} => {:e :q :b}.
{{?x :p :a} => {?x :q :b}} => {{?x :r :c} => {?x :s :d}}.
""")
        derived = [r for r in eng._rules if r.source == "derived"]
        assert any(":r" in str(r.body) or "#r" in str(r.body) for r in derived)

    def test_pass_all_echoes_rules(self, tmp_path):
        f = tmp_path / "r.n3"
        f.write_text("""@prefix : <http://example.org/test#>.
:a :valid true.
{ ?X :valid true } => { :all :is :satisfied } .
""")
        r = execute(rule_paths=[str(f)], nope=True, pass_all=True)
        assert "=>" in r.triples

    def test_implicit_universal_fact_becomes_backward_rule(self):
        doc = parse_n3("""@prefix : <http://example.org/test#>.
?x :loves _:y .
""")
        assert len(doc.triples) == 1
        bw = [r for r in doc.rules if r.is_backward]
        assert len(bw) == 1
        assert not bw[0].body.triples
        assert len(bw[0].head.triples) == 1


class TestUniversalizedRuleIris:
    def test_forall_iri_in_rule_becomes_variable(self):
        doc = parse_n3("""@prefix : <http://example.org/test#>.
@base <http://example.org/doc>.
:a :valid true .
{
  @forAll <#X> .
  <#X> :valid true .
} => {
  :all :is :satisfied .
} .
""")
        rule = doc.rules[0]
        assert isinstance(rule.body.triples[0].subject, Variable)

    def test_var_namespace_in_rule_becomes_variable(self):
        doc = parse_n3("""@prefix : <http://example.org/test#>.
@prefix var: <http://www.w3.org/2000/10/swap/var#>.
{ var:qu_1 :valid true } => { :all :is :satisfied } .
""")
        rule = doc.rules[0]
        assert isinstance(rule.body.triples[0].subject, Variable)

    def test_var_namespace_in_plain_triple_stays_iri(self):
        doc = parse_n3("""@prefix : <http://example.org/test#>.
@prefix var: <http://www.w3.org/2000/10/swap/var#>.
var:X :is :constantHere .
""")
        subj = doc.triples[0].subject
        assert isinstance(subj, NamedNode)
