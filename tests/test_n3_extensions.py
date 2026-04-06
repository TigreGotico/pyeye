"""Tests for Phase 2: BLOGIC negative surfaces and is/of sugar."""

from __future__ import annotations

import pytest

from pyeye.parser import parse_n3
from pyeye.engine import Engine
from pyeye.parser import Rule
from pyeye.term import NamedNode, Variable, Triple, Formula, NegativeSurface, Literal
from pyeye import execute


NN = NamedNode
V = Variable
T = Triple
F = Formula
L = Literal


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
