"""Tests for Phase 2 parser features: triple terms, formula terms, paths, etc."""

from __future__ import annotations

import pytest

from pyeye.parser import parse_n3, parse_rules, ParseError
from pyeye.term import (
    NamedNode, Literal, Variable, Existential, Triple,
    TripleTerm, FormulaTerm, PathTerm, Formula,
)


NN = NamedNode
V = Variable
E = Existential
L = Literal
T = Triple
TT = TripleTerm
FT = FormulaTerm
PT = PathTerm
F = Formula


class TestTripleTerm:
    """FR 2a.1: Parse triple terms ``<< S P O >>``."""

    def test_simple_triple_term(self):
        text = '@prefix : <http://ex.org/> .\n:a :about << :x :p :y >> .'
        doc = parse_n3(text)
        assert len(doc.triples) == 1
        t = doc.triples[0]
        assert t.subject == NN("http://ex.org/a")
        assert t.predicate == NN("http://ex.org/about")
        assert isinstance(t.object, TripleTerm)
        assert t.object == TT(NN("http://ex.org/x"), NN("http://ex.org/p"), NN("http://ex.org/y"))

    def test_triple_term_as_subject(self):
        text = '@prefix : <http://ex.org/> .\n<< :x :p :y >> :wasStatedBy :alice .'
        doc = parse_n3(text)
        assert len(doc.triples) == 1
        t = doc.triples[0]
        assert isinstance(t.subject, TripleTerm)
        assert t.predicate == NN("http://ex.org/wasStatedBy")

    def test_triple_term_in_rule(self):
        text = """
@prefix : <http://ex.org/> .
{ ?S :claims << ?A :p ?B >> } => { ?S :assertsFact true } .
"""
        doc = parse_n3(text)
        assert len(doc.rules) == 1
        rule = doc.rules[0]
        # Body should contain a triple with a TripleTerm in it
        body_triple = rule.body.triples[0]
        assert isinstance(body_triple.object, TripleTerm)


class TestFormulaTerm:
    """FR 2a.2: Parse formula terms ``(| Functor Args |)``."""

    def test_simple_formula_term(self):
        text = '@prefix : <http://ex.org/> .\n:a :thinks (| :says :alice "hello" |) .'
        doc = parse_n3(text)
        assert len(doc.triples) == 1
        t = doc.triples[0]
        assert isinstance(t.object, FormulaTerm)
        assert t.object.functor == NN("http://ex.org/says")
        assert t.object.args == (NN("http://ex.org/alice"), L("hello"))

    def test_formula_term_no_args(self):
        text = '@prefix : <http://ex.org/> .\n:a :status (| :ok |) .'
        doc = parse_n3(text)
        t = doc.triples[0]
        assert isinstance(t.object, FormulaTerm)
        assert t.object.functor == NN("http://ex.org/ok")
        assert t.object.args == ()


class TestPathExpressions:
    """FR 2a.8: Parse chained path expressions ``:a ! :p ! :q``."""

    def test_single_forward_path(self):
        """`:a ! :p :target` — path in predicate position."""
        text = '@prefix : <http://ex.org/> .\n:a ! :p :target .'
        doc = parse_n3(text)
        assert len(doc.triples) == 1
        t = doc.triples[0]
        assert isinstance(t.predicate, PathTerm)
        assert len(t.predicate.terms) == 1
        assert t.predicate.terms[0] == NN("http://ex.org/p")
        assert t.predicate.directions == ("forward",)

    def test_reverse_path(self):
        """`:a ^ :parent :target` — reverse path."""
        text = '@prefix : <http://ex.org/> .\n:a ^ :parent :target .'
        doc = parse_n3(text)
        assert len(doc.triples) == 1
        t = doc.triples[0]
        assert isinstance(t.predicate, PathTerm)
        assert t.predicate.directions == ("reverse",)

    def test_chained_path(self):
        """`:a ! :p ! :q :target` — multiple path segments."""
        text = '@prefix : <http://ex.org/> .\n:a ! :p ! :q :target .'
        doc = parse_n3(text)
        t = doc.triples[0]
        assert isinstance(t.predicate, PathTerm)
        assert len(t.predicate.terms) == 2
        assert t.predicate.terms == (NN("http://ex.org/p"), NN("http://ex.org/q"))
        assert t.predicate.directions == ("forward", "forward")


class TestHasSugar:
    """FR 2a.4: Parse `has` syntactic sugar: `:Alice :parent has :Bob`."""

    def test_has_sugar(self):
        """`:Alice :parent has :Bob` → `:Alice :parent :Bob`."""
        text = '@prefix : <http://ex.org/> .\n:Alice :parent has :Bob .'
        doc = parse_n3(text)
        assert len(doc.triples) == 1
        t = doc.triples[0]
        assert t.subject == NN("http://ex.org/Alice")
        assert t.predicate == NN("http://ex.org/parent")
        assert t.object == NN("http://ex.org/Bob")

    def test_has_with_semicolon(self):
        text = '@prefix : <http://ex.org/> .\n:Alice :name has "Alice" ; :age has 30 .'
        doc = parse_n3(text)
        assert len(doc.triples) == 2


class TestIsSugar:
    """FR 2a.3: Parse `is` syntactic sugar (same as `has`)."""

    def test_is_sugar(self):
        """`:Alice :name is "Alice"` → `:Alice :name "Alice"`."""
        text = '@prefix : <http://ex.org/> .\n:Alice :name is "Alice" .'
        doc = parse_n3(text)
        assert len(doc.triples) == 1
        t = doc.triples[0]
        assert t.subject == NN("http://ex.org/Alice")
        assert t.predicate == NN("http://ex.org/name")
        assert t.object == L("Alice")


class TestOfSugar:
    """FR 2a.5: Parse `of` syntactic sugar (property inversion)."""

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


class TestSetSyntax:
    """FR 2a.7: Parse set syntax ``($ a b $)``."""

    def test_set_parsed(self):
        """M5 fix: Sets are parsed as SetTerm, not RDF lists."""
        from pyeye.term import SetTerm
        text = '@prefix : <http://ex.org/> .\n:Alice :likes ($ :pizza :sushi $) .'
        doc = parse_n3(text)
        assert len(doc.triples) == 1
        t = doc.triples[0]
        assert isinstance(t.object, SetTerm)
        assert len(t.object.elements) == 2
        assert t.object.elements[0] == NN("http://ex.org/pizza")
        assert t.object.elements[1] == NN("http://ex.org/sushi")

    def test_empty_set(self):
        """M5 fix: Empty set is parsed as SetTerm with no elements."""
        from pyeye.term import SetTerm
        text = '@prefix : <http://ex.org/> .\n:Alice :likes ($ $) .'
        doc = parse_n3(text)
        t = doc.triples[0]
        assert isinstance(t.object, SetTerm)
        assert t.object.elements == ()


class TestBackwardCompatibility:
    """FR 2a.9: All Phase 1 syntax still works."""

    def test_phase1_rule(self):
        text = '@prefix : <http://ex.org/> .\n{?X :p ?Y} => {?Y :q ?X} .'
        doc = parse_n3(text)
        assert len(doc.rules) == 1

    def test_phase1_data(self):
        text = '@prefix : <http://ex.org/> .\n:a :p :b .\n:c :q :d .'
        doc = parse_n3(text)
        assert len(doc.triples) == 2

    def test_phase1_semicolon(self):
        text = '@prefix : <http://ex.org/> .\n:a :p :b ; :q :c .'
        doc = parse_n3(text)
        assert len(doc.triples) == 2

    def test_phase1_comma(self):
        text = '@prefix : <http://ex.org/> .\n:a :p :b, :c, :d .'
        doc = parse_n3(text)
        assert len(doc.triples) == 3

    def test_phase1_blank_node(self):
        text = '@prefix : <http://ex.org/> .\n:a :p [ :q :r ] .'
        doc = parse_n3(text)
        # Creates a blank node with :q :r
        assert any(t.predicate == NN("http://ex.org/q") for t in doc.triples)

    def test_phase1_list(self):
        text = '@prefix : <http://ex.org/> .\n:a :p (:x :y :z) .'
        doc = parse_n3(text)
        assert any(t.predicate == NN("http://www.w3.org/1999/02/22-rdf-syntax-ns#first")
                   for t in doc.triples)


class TestBooleanLiterals:
    """C1 fix: true/false parsed as xsd:boolean, not prefixed names."""

    def test_true_literal(self):
        text = '@prefix : <http://ex.org/> .\n:a :alive true .'
        doc = parse_n3(text)
        assert len(doc.triples) == 1
        t = doc.triples[0]
        assert t.object == L("true", datatype=NN("http://www.w3.org/2001/XMLSchema#boolean"))

    def test_false_literal(self):
        text = '@prefix : <http://ex.org/> .\n:a :alive false .'
        doc = parse_n3(text)
        assert len(doc.triples) == 1
        t = doc.triples[0]
        assert t.object == L("false", datatype=NN("http://www.w3.org/2001/XMLSchema#boolean"))

    def test_boolean_in_rule_body(self):
        text = '@prefix : <http://ex.org/> .\n{?X :alive true} => {?X :active true} .'
        doc = parse_n3(text)
        assert len(doc.rules) == 1
        rule = doc.rules[0]
        body_obj = rule.body.triples[0].object
        assert body_obj == L("true", datatype=NN("http://www.w3.org/2001/XMLSchema#boolean"))


class TestUnicodeNames:
    """C9 fix: Unicode characters in prefixed names."""

    def test_unicode_local_name(self):
        """ex:chañaral should parse correctly."""
        text = '@prefix ex: <http://ex.org/> .\nex:chañaral :label "Chañaral" .'
        doc = parse_n3(text)
        assert len(doc.triples) == 1
        t = doc.triples[0]
        assert t.subject == NN("http://ex.org/chañaral")

    def test_unicode_variable(self):
        """Unicode variable names should work."""
        text = '@prefix : <http://ex.org/> .\n{?Ñame :p ?Val} => {?Ñame :q ?Val} .'
        doc = parse_n3(text)
        assert len(doc.rules) == 1
        rule = doc.rules[0]
        assert rule.body.triples[0].subject.name == "Ñame"


class TestIRIValidation:
    """M2 fix: IRI validation rejects forbidden characters."""

    def test_valid_iri(self):
        """Valid IRI should parse without error."""
        text = '@prefix : <http://ex.org/> .\n:a :p :b .'
        doc = parse_n3(text)
        assert len(doc.triples) == 1

    def test_forbidden_brace(self):
        """IRI with { should be rejected."""
        from pyeye.parser import ParseError
        with pytest.raises(ParseError, match="Forbidden character"):
            parse_n3('@prefix : <http://ex.org/> .\n<a{b> :p :c .')

    def test_forbidden_pipe(self):
        """IRI with | should be rejected."""
        from pyeye.parser import ParseError
        with pytest.raises(ParseError, match="Forbidden character"):
            parse_n3('@prefix : <http://ex.org/> .\n<a|b> :p :c .')

    def test_forbidden_backslash(self):
        """IRI with \\ should be rejected."""
        from pyeye.parser import ParseError
        with pytest.raises(ParseError, match="Forbidden character"):
            parse_n3('@prefix : <http://ex.org/> .\n<a\\b> :p :c .')
