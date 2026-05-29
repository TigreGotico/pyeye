"""Tests for pyeye.parser — N3 rule parser."""

from __future__ import annotations

import pytest

from pyeye.parser import parse_n3, parse_rules, ParseError, load_data_string
from pyeye.term import NamedNode, Literal, Variable, Existential, Formula, Triple


NN = NamedNode
V = Variable
E = Existential
L = Literal
T = Triple
F = Formula

# -- parse_n3 basics ---------------------------------------------------------

class TestParseN3:
    def test_empty(self):
        doc = parse_n3("")
        assert doc.triples == []
        assert doc.rules == []

    def test_comments_only(self):
        doc = parse_n3("# just a comment\n# another")
        assert doc.triples == []
        assert doc.rules == []

    # -- prefix / base -------------------------------------------------------

    def test_prefix(self):
        doc = parse_n3('@prefix ex: <http://example.org/> .')
        assert doc.prefixes["ex"] == "http://example.org/"

    def test_prefix_with_colon(self):
        doc = parse_n3('@prefix : <http://example.org/> .')
        assert doc.prefixes[""] == "http://example.org/"

    def test_base(self):
        doc = parse_n3('@base <http://example.org/> .')
        assert doc.base == "http://example.org/"

    # -- simple rule ---------------------------------------------------------

    def test_simple_rule(self):
        text = """
@prefix : <http://example.org/> .
{:a :p :b} => {:a :q :b} .
"""
        doc = parse_n3(text)
        assert len(doc.rules) == 1
        rule = doc.rules[0]
        assert rule.body == F([T(NN("http://example.org/a"), NN("http://example.org/p"), NN("http://example.org/b"))])
        assert rule.head == F([T(NN("http://example.org/a"), NN("http://example.org/q"), NN("http://example.org/b"))])

    # -- variables in rules --------------------------------------------------

    def test_rule_with_variables(self):
        text = """
@prefix : <http://ex.org/> .
{?X :parent ?Y} => {?Y :child ?X} .
"""
        doc = parse_n3(text)
        rule = doc.rules[0]
        # Variables carry fresh ids, so compare by name (and check head reuses
        # the same Variable instances the body introduced).
        b_subj = rule.body.triples[0].subject
        b_obj = rule.body.triples[0].object
        assert isinstance(b_subj, Variable) and b_subj.name == "X"
        assert isinstance(b_obj, Variable) and b_obj.name == "Y"
        assert rule.head.triples[0].subject == b_obj  # ?Y shared by id
        assert rule.head.triples[0].object == b_subj  # ?X shared by id

    # -- reversed rule (<=) --------------------------------------------------

    def test_reversed_rule(self):
        text = """
@prefix : <http://ex.org/> .
{?Y :child ?X} <= {?X :parent ?Y} .
"""
        doc = parse_n3(text)
        rule = doc.rules[0]
        # <= reverses: body should be ?X :parent ?Y
        assert rule.body.triples[0].predicate == NN("http://ex.org/parent")
        assert rule.head.triples[0].predicate == NN("http://ex.org/child")

    # -- multi-triple body/head ----------------------------------------------

    def test_multi_triple_body(self):
        text = """
@prefix : <http://ex.org/> .
{?X :parent ?Y . ?Y :sibling ?Z} => {?X :parent ?Z} .
"""
        doc = parse_n3(text)
        rule = doc.rules[0]
        assert len(rule.body.triples) == 2
        assert len(rule.head.triples) == 1

    # -- semicolon syntax ----------------------------------------------------

    def test_semicolon_syntax(self):
        text = """
@prefix : <http://ex.org/> .
{?X :p ?Y} => {?X :a :b ; :c :d} .
"""
        doc = parse_n3(text)
        rule = doc.rules[0]
        assert len(rule.head.triples) == 2
        h_subj = rule.head.triples[0].subject
        assert isinstance(h_subj, Variable) and h_subj.name == "X"
        assert rule.head.triples[1].predicate == NN("http://ex.org/c")

    # -- 'a' as rdf:type -----------------------------------------------------

    def test_a_shorthand(self):
        text = """
@prefix : <http://ex.org/> .
{?X a :Person} => {?X :alive true} .
"""
        doc = parse_n3(text)
        rule = doc.rules[0]
        from rdflib.namespace import RDF
        assert rule.body.triples[0].predicate == NN(str(RDF.type))

    # -- blank nodes ---------------------------------------------------------

    def test_blank_node_empty(self):
        text = """
@prefix : <http://ex.org/> .
{[] :p :o} => {:a :q :b} .
"""
        doc = parse_n3(text)
        rule = doc.rules[0]
        assert isinstance(rule.body.triples[0].subject, Existential)

    def test_blank_node_with_content(self):
        text = """
@prefix : <http://ex.org/> .
{[ :p :o ] :q :r} => {:a :b :c} .
"""
        doc = parse_n3(text)
        assert len(doc.rules) == 1
        # The blank node and its content live inside the rule body (formula-local),
        # not in the top-level document triples.
        body = doc.rules[0].body.triples
        assert any(isinstance(t.subject, Existential) for t in body)
        # The bnode's content triple [ :p :o ] appears in the body.
        assert any(t.predicate == NN("http://ex.org/p") for t in body)

    # -- literals ------------------------------------------------------------

    def test_plain_string_literal(self):
        text = """
@prefix : <http://ex.org/> .
{?X :name ?N} => {?N :len ?L} .
"""
        doc = parse_n3(text)
        assert len(doc.rules) == 1  # parses without error

    def test_datatype_literal(self):
        text = """
@prefix : <http://ex.org/> .
{?X :val ?V} => {?X :ok true} .
"""
        doc = parse_n3(text)
        assert len(doc.rules) == 1

    def test_language_tag_literal(self):
        text = """
@prefix : <http://ex.org/> .
{?X :label ?L} => {:a :b :c} .
"""
        doc = parse_n3(text)
        assert len(doc.rules) == 1

    # -- RDF lists -----------------------------------------------------------

    def test_rdf_list(self):
        text = """
@prefix : <http://ex.org/> .
{:a :list (:x :y :z)} => {:a :hasList true} .
"""
        from pyeye.term import ListTerm
        doc = parse_n3(text)
        rule = doc.rules[0]
        list_node = rule.body.triples[0].object
        # Lists are native ListTerms, not rdf:first/rdf:rest chains.
        assert isinstance(list_node, ListTerm)
        assert list_node.items == (
            NN("http://ex.org/x"), NN("http://ex.org/y"), NN("http://ex.org/z"),
        )

    def test_empty_list(self):
        from pyeye.term import ListTerm
        text = """
@prefix : <http://ex.org/> .
{:a :list ()} => {:a :empty true} .
"""
        doc = parse_n3(text)
        rule = doc.rules[0]
        assert rule.body.triples[0].object == ListTerm(())

    # -- backwards rule ------------------------------------------------------

    def test_backward_rule_operator(self):
        text = "@prefix : <http://x.org/> .\n{?A :r ?B} <= {?B :inv ?A} ."
        doc = parse_n3(text)
        assert len(doc.rules) == 1
        # Reversed: body is ?B :inv ?A, head is ?A :r ?B
        assert doc.rules[0].body.triples[0].predicate == NN("http://x.org/inv")

    # -- multiple rules ------------------------------------------------------

    def test_multiple_rules(self):
        text = """
@prefix : <http://ex.org/> .
{?X :p ?Y} => {?Y :q ?X} .
{?A :r ?B} => {?B :s ?A} .
"""
        doc = parse_n3(text)
        assert len(doc.rules) == 2

    # -- standalone formula (data) -------------------------------------------

    def test_standalone_formula_as_data(self):
        text = """
@prefix : <http://ex.org/> .
{:a :p :b} .
"""
        doc = parse_n3(text)
        assert len(doc.triples) == 1
        assert len(doc.rules) == 0


# -- parse_rules shortcut ----------------------------------------------------

class TestParseRules:
    def test_returns_only_rules(self):
        text = """
@prefix : <http://ex.org/> .
:a :p :b .
{?X :p ?Y} => {?Y :q ?X} .
"""
        rules = parse_rules(text)
        assert len(rules) == 1


# -- load_data_string (rdflib) -----------------------------------------------

class TestLoadDataString:
    def test_load_turtle(self):
        doc = load_data_string("@prefix : <http://ex.org/> .\n:a :p :b .")
        assert len(doc.triples) == 1

    def test_load_multiple(self):
        doc = load_data_string("""
@prefix : <http://ex.org/> .
:a :p :b .
:c :q :d .
""")
        assert len(doc.triples) == 2


# -- error handling ----------------------------------------------------------

class TestParseErrors:
    def test_unexpected_token(self):
        with pytest.raises(ParseError):
            parse_n3("{:a :p :b} => {:a :q")  # missing } and .

    def test_expected_formula_brace(self):
        with pytest.raises(ParseError):
            parse_n3("@prefix : <http://x.org/> .\n=> {:a :b :c} .")
