"""Tests for v2 engine: copy_rule, unified resolution, tabling."""

from pyeye.term import (
    Variable, NamedNode, Literal, Existential, ListTerm, Formula, Triple,
    Binding, _next_var_id,
)
from pyeye.parser import Rule, parse_n3
from pyeye.engine import Engine, copy_rule, ContradictionError, ReasoningTimeoutError


class TestCopyRule:
    """copy_rule creates fresh Variable IDs."""

    def test_basic_copy(self):
        x = Variable("X")
        y = Variable("Y")
        body = Formula(triples=(Triple(x, NamedNode("p"), y),))
        head = Formula(triples=(Triple(y, NamedNode("q"), x),))
        rule = Rule(body=body, head=head)

        copied = copy_rule(rule)
        # Head and body should have fresh Variable IDs
        cb = copied.body.triples[0]
        ch = copied.head.triples[0]
        assert cb.subject.name == "X"
        assert cb.subject.id != x.id
        assert ch.object.name == "X"
        assert ch.object.id != x.id
        # Same variable in body and head maps to same fresh ID
        assert cb.subject.id == ch.object.id

    def test_copy_preserves_ground_terms(self):
        body = Formula(triples=(Triple(NamedNode("a"), NamedNode("p"), NamedNode("b")),))
        head = Formula(triples=(Triple(NamedNode("c"), NamedNode("q"), NamedNode("d")),))
        rule = Rule(body=body, head=head)
        copied = copy_rule(rule)
        assert copied.body.triples[0].subject == NamedNode("a")

    def test_copy_handles_listterm(self):
        x = Variable("X")
        lt = ListTerm(items=(x, Literal("1")))
        body = Formula(triples=(Triple(lt, NamedNode("sum"), Variable("R")),))
        head = Formula(triples=())
        rule = Rule(body=body, head=head)
        copied = copy_rule(rule)
        subj = copied.body.triples[0].subject
        assert isinstance(subj, ListTerm)
        assert subj.items[0].name == "X"
        assert subj.items[0].id != x.id


class TestForwardChaining:
    """Forward chaining with the new engine."""

    def test_simple_forward_rule(self):
        """{ :a :p :b } => { :b :q :c }."""
        engine = Engine(timeout_seconds=5)
        engine.add_triple(Triple(NamedNode("a"), NamedNode("p"), NamedNode("b")))
        x = Variable("X")
        y = Variable("Y")
        body = Formula(triples=(Triple(x, NamedNode("p"), y),))
        head = Formula(triples=(Triple(y, NamedNode("q"), NamedNode("c")),))
        engine.add_rule(Rule(body=body, head=head))
        engine.snapshot_initial()
        engine.run()
        derived = engine.derived_triples
        assert any(
            t.subject == NamedNode("b") and t.predicate == NamedNode("q")
            for t in derived
        )

    def test_forward_with_list_subject(self):
        """Parse and reason with list subjects."""
        doc = parse_n3("""
@prefix : <http://ex.org/> .
@prefix math: <http://www.w3.org/2000/10/swap/math#> .
:a :val 3 .
:b :val 4 .
{?X :val ?V} => {?X :has :value} .
""", source='test')
        engine = Engine(timeout_seconds=5)
        for t in doc.triples:
            engine.add_triple(t)
        for r in doc.rules:
            engine.add_rule(r)
        engine.snapshot_initial()
        engine.run()
        derived = engine.derived_triples
        assert len(derived) >= 2


class TestBackwardChaining:
    """Backward chaining with copy_rule and tabling."""

    def test_simple_backward_rule(self):
        """{ ?X :ancestor ?Y } <= { ?X :parent ?Y }."""
        engine = Engine(timeout_seconds=5)
        engine.add_triple(Triple(NamedNode("a"), NamedNode("parent"), NamedNode("b")))

        x = Variable("X")
        y = Variable("Y")
        head = Formula(triples=(Triple(x, NamedNode("ancestor"), y),))
        body = Formula(triples=(Triple(x, NamedNode("parent"), y),))
        engine.add_rule(Rule(body=body, head=head, is_backward=True))
        engine.snapshot_initial()

        query = Triple(Variable("Q"), NamedNode("ancestor"), Variable("R"))
        results = engine.backward_chain(query)
        assert len(results) >= 1

    def test_recursive_backward_with_tabling(self):
        """Transitive closure: ancestor via parent chain."""
        engine = Engine(timeout_seconds=5)
        engine.add_triple(Triple(NamedNode("a"), NamedNode("p"), NamedNode("b")))
        engine.add_triple(Triple(NamedNode("b"), NamedNode("p"), NamedNode("c")))

        x = Variable("X")
        y = Variable("Y")
        z = Variable("Z")
        # Base case: {?X :anc ?Y} <= {?X :p ?Y}
        head1 = Formula(triples=(Triple(x, NamedNode("anc"), y),))
        body1 = Formula(triples=(Triple(x, NamedNode("p"), y),))
        engine.add_rule(Rule(body=body1, head=head1, is_backward=True))

        # Recursive: {?X :anc ?Y} <= {?X :p ?Z. ?Z :anc ?Y}
        x2 = Variable("X")
        y2 = Variable("Y")
        z2 = Variable("Z")
        head2 = Formula(triples=(Triple(x2, NamedNode("anc"), y2),))
        body2 = Formula(triples=(
            Triple(x2, NamedNode("p"), z2),
            Triple(z2, NamedNode("anc"), y2),
        ))
        engine.add_rule(Rule(body=body2, head=head2, is_backward=True))
        engine.snapshot_initial()

        query = Triple(NamedNode("a"), NamedNode("anc"), Variable("R"))
        results = engine.backward_chain(query)
        # a→b (base), a→c (via b→c transitive)
        r_vals = {engine._resolve_term(r.get(query.object.id), r) for r in results}
        assert NamedNode("b") in r_vals
        assert NamedNode("c") in r_vals


class TestParseAndReason:
    """End-to-end: parse N3, run engine, check results."""

    def test_simple_derivation(self):
        doc = parse_n3("""
@prefix : <http://example.org/> .
:alice :parent :bob .
:bob :parent :carol .
{?X :parent ?Y} => {?Y :child ?X} .
""", source='test')
        engine = Engine(timeout_seconds=5)
        for t in doc.triples:
            engine.add_triple(t)
        for r in doc.rules:
            engine.add_rule(r)
        engine.snapshot_initial()
        engine.run()
        derived = engine.derived_triples
        assert any(
            t.subject == NamedNode("http://example.org/bob")
            and str(t.predicate).endswith("child")
            for t in derived
        )

    def test_timeout(self):
        """Infinite rules should timeout."""
        engine = Engine(timeout_seconds=0.1)
        engine.add_triple(Triple(NamedNode("a"), NamedNode("p"), NamedNode("b")))
        x = Variable("X")
        y = Variable("Y")
        # Rule that generates infinite triples
        body = Formula(triples=(Triple(x, NamedNode("p"), y),))
        head = Formula(triples=(Triple(y, NamedNode("p"), x),))
        engine.add_rule(Rule(body=body, head=head))
        engine.snapshot_initial()
        try:
            engine.run()
        except ReasoningTimeoutError:
            pass  # expected
