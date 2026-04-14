"""Tests for v2 parser: ListTerm emission, formula-local blank nodes."""

from pyeye.parser import parse_n3
from pyeye.term import (
    ListTerm, Variable, NamedNode, Literal, Existential, Formula, Triple,
)


class TestListTermEmission:
    """Parser emits ListTerm for (a b c) syntax."""

    def test_ground_list(self):
        doc = parse_n3('@prefix : <http://ex.org/> . :s :p (1 2 3) .', source='t')
        assert len(doc.triples) == 1
        obj = doc.triples[0].object
        assert isinstance(obj, ListTerm)
        assert len(obj.items) == 3

    def test_empty_list(self):
        doc = parse_n3('@prefix : <http://ex.org/> . :s :p () .', source='t')
        obj = doc.triples[0].object
        assert isinstance(obj, ListTerm)
        assert len(obj.items) == 0

    def test_no_rdf_first_rest_triples(self):
        """List syntax must NOT generate rdf:first/rdf:rest side-effect triples."""
        doc = parse_n3('@prefix : <http://ex.org/> . :s :p (1 2 3) .', source='t')
        assert len(doc.triples) == 1

    def test_nested_list(self):
        doc = parse_n3('@prefix : <http://ex.org/> . :s :p ((1 2) 3) .', source='t')
        obj = doc.triples[0].object
        assert isinstance(obj, ListTerm)
        assert len(obj.items) == 2
        assert isinstance(obj.items[0], ListTerm)
        assert len(obj.items[0].items) == 2

    def test_list_with_variables(self):
        doc = parse_n3('@prefix : <http://ex.org/> . :s :p (?X ?Y) .', source='t')
        obj = doc.triples[0].object
        assert isinstance(obj, ListTerm)
        assert isinstance(obj.items[0], Variable)
        assert isinstance(obj.items[1], Variable)

    def test_list_as_subject(self):
        doc = parse_n3("""
@prefix : <http://ex.org/> .
@prefix math: <http://www.w3.org/2000/10/swap/math#> .
{(?A ?B) math:sum ?C} => {:r :is ?C} .
""", source='t')
        body = doc.rules[0].body
        assert isinstance(body.triples[0].subject, ListTerm)

    def test_list_of_formulas(self):
        """Lists can contain formulas — used in log:allPossibleCases."""
        doc = parse_n3("""
@prefix : <http://ex.org/> .
:s :p ({:a :b :c} {:d :e :f}) .
""", source='t')
        obj = doc.triples[0].object
        assert isinstance(obj, ListTerm)
        assert len(obj.items) == 2
        assert isinstance(obj.items[0], Formula)
        assert isinstance(obj.items[1], Formula)


class TestFormulaLocalBlankNodes:
    """Blank node property triples inside formulas go into the formula."""

    def test_bnode_in_rule_body(self):
        doc = parse_n3("""
@prefix : <http://ex.org/> .
{[ :p ?X ] :q :r} => {:a :b :c} .
""", source='t')
        body = doc.rules[0].body
        # Body has 2 triples: _:b0 :p ?X and _:b0 :q :r
        assert len(body.triples) == 2
        # No document-level side-effect triples
        assert len(doc.triples) == 0

    def test_bnode_in_data_goes_to_document(self):
        """Blank nodes outside formulas still go to document level."""
        doc = parse_n3("""
@prefix : <http://ex.org/> .
[ :p :o ] :q :r .
""", source='t')
        # Document-level triples: _:b0 :p :o, _:b0 :q :r
        assert len(doc.triples) == 2


class TestPathExpansion:
    """Path expressions inside formulas expand into formula-local triples."""

    def test_path_in_rule_body(self):
        """Path expansion inside a formula body stays formula-local."""
        doc = parse_n3("""
@prefix : <http://ex.org/> .
{?X ! :p :q :r} => {:a :b :c} .
""", source='t')
        body = doc.rules[0].body
        # Path expansion creates an extra triple in the formula
        assert len(body.triples) >= 2

    def test_path_in_data(self):
        """Path expansion outside formulas goes to document level."""
        doc = parse_n3("""
@prefix : <http://ex.org/> .
:s ! :p :q :o .
""", source='t')
        assert len(doc.triples) >= 2


class TestBackwardRules:
    """Backward rules (<=) parsed correctly."""

    def test_backward_rule(self):
        doc = parse_n3("""
@prefix : <http://ex.org/> .
{?X :foo ?Y} <= {?Y :bar ?X} .
""", source='t')
        assert len(doc.rules) == 1
        assert doc.rules[0].is_backward

    def test_backward_rule_with_true_body(self):
        doc = parse_n3("""
@prefix : <http://ex.org/> .
{:a :b :c} <= true .
""", source='t')
        assert len(doc.rules) == 1
        assert doc.rules[0].is_backward
        assert len(doc.rules[0].body.triples) == 0
