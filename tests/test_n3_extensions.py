"""Tests for Phase 2: BLOGIC negative surfaces and is/of sugar."""

from __future__ import annotations

import pytest

from pyeye.parser import parse_n3
from pyeye.engine import Engine
from pyeye.parser import Rule
from pyeye.term import (
    NamedNode, Variable, Triple, Formula, NegativeSurface, Literal, TripleTerm,
)
from pyeye import execute


NN = NamedNode
V = Variable
T = Triple
F = Formula
L = Literal
TT = TripleTerm


class TestNegativeSurface:
    """FR 2a.6: BLOGIC negative surfaces."""

    def test_parse_negative_surface(self):
        """`:S log:onNegativeSurface { :a :p :b }` parses correctly."""
        text = """
@prefix : <http://ex.org/> .
@prefix log: <http://eulersharp.sourceforge.net/2003/03swap/log-rules#> .
:S log:onNegativeSurface { :a :p :b } .
"""
        doc = parse_n3(text)
        assert len(doc.triples) == 1
        t = doc.triples[0]
        assert t.predicate == NN("http://eulersharp.sourceforge.net/2003/03swap/log-rules#onNegativeSurface")
        assert isinstance(t.object, Formula)

    def test_negative_surface_blocks_derivation(self):
        """If negated formula matches, rule body fails."""
        engine = Engine()
        # Data that matches the negated formula
        engine.add_triple(T(NN("http://x/a"), NN("http://x/p"), NN("http://x/b")))

        # Rule: if :a :p :b is NOT true, then derive something
        # Since :a :p :b IS true, the negation blocks this rule
        engine.add_rule(Rule(
            body=F((
                T(V("S"), NN("http://eulersharp.sourceforge.net/2003/03swap/log-rules#onNegativeSurface"),
                  F((T(NN("http://x/a"), NN("http://x/p"), NN("http://x/b")),))),
            )),
            head=F((T(NN("http://x/result"), NN("http://x/derived"), NN("http://x/yes")),)),
        ))
        engine.run()

        # Nothing should be derived because negation blocked it
        assert len(engine.derived_triples) == 0

    def test_negative_surface_allows_derivation(self):
        """If negated formula doesn't match, rule body succeeds."""
        engine = Engine()
        # Data: :a :p :c (NOT :a :p :b)
        engine.add_triple(T(NN("http://x/a"), NN("http://x/p"), NN("http://x/c")))

        # Rule: if :a :p :b is NOT true, then derive something
        engine.add_rule(Rule(
            body=F((
                T(V("S"), NN("http://eulersharp.sourceforge.net/2003/03swap/log-rules#onNegativeSurface"),
                  F((T(NN("http://x/a"), NN("http://x/p"), NN("http://x/b")),))),
            )),
            head=F((T(NN("http://x/result"), NN("http://x/derived"), NN("http://x/yes")),)),
        ))
        engine.run()

        # :a :p :b is NOT in store, so negation passes → derivation happens
        assert len(engine.derived_triples) == 1


class TestIsSugar:
    """FR 2a.3: `is` syntactic sugar."""

    def test_is_sugar(self):
        text = '@prefix : <http://ex.org/> .\n:Alice :name is "Alice" .'
        doc = parse_n3(text)
        assert len(doc.triples) == 1
        t = doc.triples[0]
        assert t.subject == NN("http://ex.org/Alice")
        assert t.object == L("Alice")


class TestOfSugar:
    """FR 2a.5: `of` syntactic sugar (property inversion)."""

    def test_of_sugar(self):
        """`:Bob :child of :Alice` → `:Alice :child :Bob`."""
        text = '@prefix : <http://ex.org/> .\n:Bob :child of :Alice .'
        doc = parse_n3(text)
        assert len(doc.triples) == 1
        t = doc.triples[0]
        assert t.subject == NN("http://ex.org/Alice")
        assert t.predicate == NN("http://ex.org/child")
        assert t.object == NN("http://ex.org/Bob")

    def test_of_with_semicolon(self):
        text = '@prefix : <http://ex.org/> .\n:Bob :child of :Alice ; :sibling of :Carol .'
        doc = parse_n3(text)
        assert len(doc.triples) == 2
        assert doc.triples[0].subject == NN("http://ex.org/Alice")
        assert doc.triples[1].subject == NN("http://ex.org/Carol")


class TestQueryOperator:
    """EYE ``=^`` query operator (filter rule, answer-only)."""

    def test_query_rule_parses(self):
        text = (
            '@prefix : <http://ex.org/> .\n'
            '{ ?T :hasAnomaly ?A } =^ { ?T :hasAnomaly ?A } .'
        )
        doc = parse_n3(text)
        assert len(doc.rules) == 1
        assert doc.rules[0].is_query is True

    def test_query_and_inference_rules_coexist(self):
        text = (
            '@prefix : <http://ex.org/> .\n'
            '{ ?T :a :x } => { ?T :hasAnomaly :y } .\n'
            '{ ?T :hasAnomaly ?A } =^ { ?T :hasAnomaly ?A } .'
        )
        doc = parse_n3(text)
        assert len(doc.rules) == 2
        assert [r.is_query for r in doc.rules] == [False, True]


class TestBnodeLabelledGraph:
    """N3-plus bnode/IRI-labelled graphs ``_:g { ... }``."""

    def test_bnode_graph_to_quads(self):
        text = (
            '@prefix : <http://ex.org/> .\n'
            '_:g { :a :b :c. :d :e :f. }'
        )
        doc = parse_n3(text)
        assert len(doc.quads) == 2
        gs = {q.graph for q in doc.quads}
        assert len(gs) == 1
        g = next(iter(gs))
        assert g.name == "g"
        q = doc.quads[0]
        assert q.subject == NN("http://ex.org/a")

    def test_iri_labelled_graph(self):
        text = (
            '@prefix : <http://ex.org/> .\n'
            ':myGraph { :a :b :c. }'
        )
        doc = parse_n3(text)
        assert len(doc.quads) == 1
        assert doc.quads[0].graph == NN("http://ex.org/myGraph")


class TestN3Quad:
    """N3 quad ``s p o g .`` — a 4th term names the graph."""

    def test_quad_with_bnode_graph(self):
        text = (
            '@prefix : <http://ex.org/> .\n'
            ':s :p :o _:g .'
        )
        doc = parse_n3(text)
        assert len(doc.triples) == 0
        assert len(doc.quads) == 1
        q = doc.quads[0]
        assert q.subject == NN("http://ex.org/s")
        assert q.object == NN("http://ex.org/o")
        assert q.graph.name == "g"

    def test_plain_triple_unaffected(self):
        text = '@prefix : <http://ex.org/> .\n:s :p :o .'
        doc = parse_n3(text)
        assert len(doc.triples) == 1
        assert len(doc.quads) == 0


class TestReifier:
    """RDF 1.2 reifier ``~`` is consumed without breaking the base triple."""

    def test_reifier_after_object(self):
        text = (
            '@prefix : <http://ex.org/> .\n'
            ':a :name "Alice" ~ :t .'
        )
        doc = parse_n3(text)
        assert len(doc.triples) == 1
        t = doc.triples[0]
        assert t.subject == NN("http://ex.org/a")
        assert t.object == L("Alice")

    def test_reifier_inside_triple_term(self):
        text = (
            '@prefix : <http://ex.org/> .\n'
            ':s :p << :g :h :i ~ :x >> .'
        )
        doc = parse_n3(text)
        assert len(doc.triples) == 1
        tt = doc.triples[0].object
        from pyeye.term import TripleTerm
        assert isinstance(tt, TripleTerm)
        assert tt.subject == NN("http://ex.org/g")
        assert tt.object == NN("http://ex.org/i")

    def test_bare_triple_term_statement(self):
        text = (
            '@prefix : <http://ex.org/> .\n'
            '<< :a :b :c ~ :r >> :p :o .'
        )
        doc = parse_n3(text)
        assert len(doc.triples) == 1
        from pyeye.term import TripleTerm
        assert isinstance(doc.triples[0].subject, TripleTerm)


class TestAnnotationBlocks:
    """RDF 1.2 annotation blocks ``{| ... |}`` are skipped, base triple kept."""

    def test_single_annotation(self):
        text = (
            '@prefix : <http://ex.org/> .\n'
            ':s :p :o {| :j :k |} .'
        )
        doc = parse_n3(text)
        assert len(doc.triples) == 1
        assert doc.triples[0].predicate == NN("http://ex.org/p")

    def test_repeated_annotations(self):
        text = (
            '@prefix : <http://ex.org/> .\n'
            ':liz :marriedTo :richard {| :from 1964 |} {| :from 1980 |} .'
        )
        doc = parse_n3(text)
        assert len(doc.triples) == 1


class TestPrefixedNameLexing:
    """Single-token PNAME lexing: digits mid-name, percent-escapes, ':'."""

    def test_percent_escape_local_name(self):
        text = (
            '@prefix res: <http://ex.org/> .\n'
            'res:COUNTRY_United%20States res:label "US" .'
        )
        doc = parse_n3(text)
        assert len(doc.triples) == 1
        assert doc.triples[0].subject == NN("http://ex.org/COUNTRY_United%20States")

    def test_digit_in_middle_of_local_name(self):
        text = (
            '@prefix res: <http://ex.org/> .\n'
            'res:AIRLINE_100 res:label "X" .'
        )
        doc = parse_n3(text)
        assert doc.triples[0].subject == NN("http://ex.org/AIRLINE_100")

    def test_colon_in_local_name(self):
        text = (
            '@prefix log: <http://l#> .\n'
            '@prefix : <http://ex.org/> .\n'
            ':a log:equalTo :b .'
        )
        doc = parse_n3(text)
        assert doc.triples[0].predicate == NN("http://l#equalTo")


class TestTripleTermReasoning:
    """RDF-star quoted triples (<< s p o >>) match facts and bind inner
    variables during backward/forward chaining."""

    def test_rule_body_tripleterm_matches_fact(self):
        """A rule body with a ground << >> subject fires when the fact exists."""
        engine = Engine()
        fact = T(TT(NN("bob"), NN("marriedTo"), NN("alice")), NN("since"), L("1999"))
        engine.add_triple(fact)
        engine.add_rule(Rule(
            body=F((T(TT(NN("bob"), NN("marriedTo"), NN("alice")), NN("since"), L("1999")),)),
            head=F((T(NN("TEST"), NN("PASS"), L("2")),)),
        ))
        engine.run()
        assert T(NN("TEST"), NN("PASS"), L("2")) in engine.derived_triples

    def test_rule_body_tripleterm_binds_inner_var(self):
        """A variable inside a << >> pattern binds to the matching fact's term."""
        engine = Engine()
        engine.add_triple(
            T(TT(NN("alice"), NN("marriedTo"), NN("bob")), NN("since"), L("1999"))
        )
        p = V("P")
        engine.add_rule(Rule(
            body=F((T(TT(NN("alice"), p, NN("bob")), NN("since"), L("1999")),)),
            head=F((T(NN("TEST"), NN("PASS"), L("3")),)),
        ))
        engine.run()
        assert T(NN("TEST"), NN("PASS"), L("3")) in engine.derived_triples

    def test_tripleterm_pattern_does_not_overmatch(self):
        """A << >> pattern must not match a fact with a different inner triple."""
        engine = Engine()
        engine.add_triple(
            T(TT(NN("alice"), NN("marriedTo"), NN("carol")), NN("since"), L("1999"))
        )
        engine.add_rule(Rule(
            body=F((T(TT(NN("alice"), NN("marriedTo"), NN("bob")), NN("since"), L("1999")),)),
            head=F((T(NN("TEST"), NN("FAIL"), L("x")),)),
        ))
        engine.run()
        assert T(NN("TEST"), NN("FAIL"), L("x")) not in engine.derived_triples

    def test_derive_tripleterm_in_head(self):
        """A rule can build a new << >> fact in its head from bound variables."""
        engine = Engine()
        engine.add_triple(
            T(TT(NN("alice"), NN("marriedTo"), NN("bob")), NN("since"), L("1999"))
        )
        s, o = V("S"), V("O")
        engine.add_rule(Rule(
            body=F((T(TT(s, NN("marriedTo"), o), NN("since"), L("1999")),)),
            head=F((T(TT(o, NN("marriedTo"), s), NN("since"), L("1999")),)),
        ))
        engine.run()
        derived = T(TT(NN("bob"), NN("marriedTo"), NN("alice")), NN("since"), L("1999"))
        assert derived in engine.derived_triples

    def test_n3_star_scenario_end_to_end(self):
        """Symmetric-relation RDF-star inference (the n3-star scenario shape)."""
        text = (
            '@prefix : <https://ex.org#>.\n'
            '{?p a :SymetricRelation. <<( ?s ?p ?o )>> ?p2 ?o2}'
            ' => {<<( ?o ?p ?s )>> ?p2 ?o2}.\n'
            ':marriedTo a :SymetricRelation.\n'
            ':alice :marriedTo :bob.\n'
            '<<( :alice :marriedTo :bob )>> :since "1999".\n'
            '{<<( :alice ?p :bob )>> :since "1999"} => {:TEST :PASS 3}.\n'
        )
        result = execute(rule_paths=None, data_strings=[text], pass_all=True,
                         timeout_seconds=10)
        assert ":TEST :PASS 3" in result.triples
