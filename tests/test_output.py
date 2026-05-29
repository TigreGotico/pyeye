"""Tests for pyeye.output — N3 serialization."""

from __future__ import annotations

import pytest

from pyeye.output import N3Writer
from pyeye.term import NamedNode, Literal, Variable, Existential, Triple


NN = NamedNode
L = Literal
T = Triple


class TestN3Writer:
    def test_empty(self):
        w = N3Writer()
        assert w.write_triples([]) == ""

    def test_single_triple(self):
        w = N3Writer()
        t = T(NN("http://ex/a"), NN("http://ex/p"), NN("http://ex/b"))
        result = w.write_triples([t])
        assert "<http://ex/a> <http://ex/p> <http://ex/b>" in result

    def test_prefix_abbreviation(self):
        w = N3Writer({"ex": "http://example.org/"})
        t = T(NN("http://example.org/a"), NN("http://example.org/p"), NN("http://example.org/b"))
        result = w.write_triples([t])
        assert "ex:a ex:p ex:b" in result
        assert "@prefix ex: <http://example.org/>" in result

    def test_empty_prefix(self):
        w = N3Writer({"": "http://default.org/"})
        t = T(NN("http://default.org/a"), NN("http://default.org/p"), NN("http://default.org/b"))
        result = w.write_triples([t])
        assert ":a :p :b" in result
        # Default prefix must keep its colon: "@prefix : <uri>" (valid N3).
        assert "@prefix : <http://default.org/>" in result

    def test_literal_plain(self):
        w = N3Writer()
        t = T(NN("http://ex/a"), NN("http://ex/label"), Literal("hello"))
        result = w.write_triples([t])
        assert '"hello"' in result

    def test_literal_datatype(self):
        w = N3Writer()
        dt = NN("http://www.w3.org/2001/XMLSchema#integer")
        t = T(NN("http://ex/a"), NN("http://ex/val"), Literal("42", datatype=dt))
        result = w.write_triples([t])
        # Integers serialized as bare numbers (N3/Turtle canonical form)
        assert ' 42 ' in result or result.strip().endswith(' 42 .')

    def test_literal_language(self):
        w = N3Writer()
        t = T(NN("http://ex/a"), NN("http://ex/label"), Literal("bonjour", language="fr"))
        result = w.write_triples([t])
        assert '"bonjour"@fr' in result

    def test_variable_in_output(self):
        w = N3Writer()
        t = T(Variable("X"), NN("http://ex/p"), NN("http://ex/b"))
        result = w.write_triples([t])
        assert "?X" in result

    def test_existential_in_output(self):
        w = N3Writer()
        t = T(NN("http://ex/a"), NN("http://ex/p"), Existential("genid-1"))
        result = w.write_triples([t])
        assert "_:genid-1" in result

    def test_deterministic_sort_order(self):
        """Triples are sorted by subject, then predicate, then object."""
        w = N3Writer()
        triples = [
            T(NN("http://z"), NN("http://p"), NN("http://x")),
            T(NN("http://a"), NN("http://q"), NN("http://y")),
            T(NN("http://a"), NN("http://p"), NN("http://x")),
        ]
        result = w.write_triples(triples)
        lines = [l for l in result.strip().split("\n") if l and not l.startswith("@prefix")]
        # Subject "a" before "z"; within "a", predicate "p" before "q"
        assert lines[0].startswith("<http://a>")
        assert "http://p" in lines[0]
        assert lines[1].startswith("<http://a>")
        assert "http://q" in lines[1]
        assert lines[2].startswith("<http://z>")

    def test_multiple_prefixes(self):
        w = N3Writer({"ex": "http://example.org/", "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#"})
        t1 = T(NN("http://example.org/a"), NN("http://www.w3.org/1999/02/22-rdf-syntax-ns#type"), NN("http://example.org/Person"))
        result = w.write_triples([t1])
        assert "@prefix ex:" in result
        assert "@prefix rdf:" in result
        # rdf:type is serialized as 'a' shorthand per N3/Turtle spec
        assert " a " in result

    def test_unmatched_uri_falls_back_to_full(self):
        """URIs not matching any prefix are rendered as full <...>."""
        w = N3Writer({"ex": "http://example.org/"})
        t = T(NN("http://other.org/x"), NN("http://example.org/p"), NN("http://example.org/y"))
        result = w.write_triples([t])
        assert "<http://other.org/x>" in result
        assert "ex:p ex:y" in result

    def test_escaped_quotes_in_literal(self):
        w = N3Writer()
        t = T(NN("http://ex/a"), NN("http://ex/says"), Literal('say "hi"'))
        result = w.write_triples([t])
        assert '"say \\"hi\\""' in result

    def test_formula_in_output(self):
        from pyeye.term import Formula
        w = N3Writer()
        inner = T(NN("http://ex/a"), NN("http://ex/p"), NN("http://ex/b"))
        t = T(NN("http://ex/x"), NN("http://ex/has"), Formula((inner,)))
        result = w.write_triples([t])
        assert "{<http://ex/a> <http://ex/p> <http://ex/b>}" in result

    def test_blank_node_property_list(self):
        """M10 fix: Blank node subjects are collapsed into [ ... ] syntax."""
        w = N3Writer({"ex": "http://ex.org/"})
        bnode = Existential("_b1")
        triples = [
            T(bnode, NN("http://ex.org/name"), L("Alice")),
            T(bnode, NN("http://ex.org/age"), L("30")),
        ]
        result = w.write_triples(triples)
        # Should use [ ... ] syntax instead of separate _:b1 lines
        assert "[" in result  # Blank node property list syntax
        assert "]" in result
        assert "ex:name" in result or ":name" in result
        assert "ex:age" in result or ":age" in result
        assert "_:b1" not in result  # Blank node should not appear as subject

    def test_multiple_blank_node_groups(self):
        """M10 fix: Multiple blank node subjects each get their own [ ... ]."""
        w = N3Writer({"ex": "http://ex.org/"})
        b1 = Existential("_b1")
        b2 = Existential("_b2")
        triples = [
            T(b1, NN("http://ex.org/name"), L("Alice")),
            T(b2, NN("http://ex.org/name"), L("Bob")),
        ]
        result = w.write_triples(triples)
        # Should have two separate [ ... ] blocks
        assert result.count("[") == 2

    def test_rule_output_implies_sugar(self):
        """L2 fix: Rules with log:implies are output with => sugar."""
        from pyeye.term import Formula
        w = N3Writer({"ex": "http://ex.org/"})
        body = Formula((
            T(NN("http://ex.org/X"), NN("http://ex.org/p"), NN("http://ex.org/Y")),
        ))
        head = Formula((
            T(NN("http://ex.org/Y"), NN("http://ex.org/q"), NN("http://ex.org/X")),
        ))
        log_implies = NN("http://eulersharp.sourceforge.net/2003/03swap/log-rules#implies")
        triples = [T(body, log_implies, head)]
        result = w.write_triples(triples)
        assert "=>" in result
        assert "{ex:X ex:p ex:Y}" in result
        assert "{ex:Y ex:q ex:X}" in result

    def test_rule_output_implied_by_sugar(self):
        """L2 fix: Rules with log:impliedBy are output with <= sugar."""
        from pyeye.term import Formula
        w = N3Writer()
        body = Formula((T(NN("http://ex.org/a"), NN("http://ex.org/p"), NN("http://ex.org/b")),))
        head = Formula((T(NN("http://ex.org/b"), NN("http://ex.org/q"), NN("http://ex.org/a")),))
        log_implied_by = NN("http://eulersharp.sourceforge.net/2003/03swap/log-rules#impliedBy")
        triples = [T(body, log_implied_by, head)]
        result = w.write_triples(triples)
        assert "<=" in result
