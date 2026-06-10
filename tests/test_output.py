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


class TestRoundTrip:
    """Serializer output must parse back through pyeye's own parser with the
    same facts (serialize → parse → re-serialize is stable)."""

    def _roundtrip(self, triples):
        from pyeye.parser import parse_n3
        w = N3Writer()
        text = w.write_triples(triples)
        doc = parse_n3(text, source="roundtrip")
        return text, doc

    def test_bnode_property_list_referenced_keeps_label(self):
        """A bnode that is both subject and object keeps its _: label so the
        reference and the property list stay linked."""
        b = Existential("sk-20192690")
        triples = [
            T(NN("http://ex/q"), NN("http://ex/answer"), b),
            T(b, NN("http://ex/value"), L("2", datatype=NN("http://www.w3.org/2001/XMLSchema#integer"))),
            T(b, NN("http://www.w3.org/1999/02/22-rdf-syntax-ns#type"), NN("http://ex/Root")),
        ]
        text, doc = self._roundtrip(triples)
        assert len(doc.triples) == 3
        # the answer object and the property-list subject must be the same bnode
        objs = {t.object for t in doc.triples if t.predicate.value == "http://ex/answer"}
        subjs = {t.subject for t in doc.triples if t.predicate.value == "http://ex/value"}
        assert objs == subjs

    def test_bnode_label_with_hyphen_parses(self):
        """Skolem labels containing '-' (valid PN_CHARS) round-trip."""
        b = Existential("sk-123-456")
        triples = [
            T(b, NN("http://ex/p"), L("x")),
            T(b, NN("http://ex/q"), L("y")),
            T(NN("http://ex/s"), NN("http://ex/r"), b),
        ]
        text, doc = self._roundtrip(triples)
        assert len(doc.triples) == 3

    def test_unreferenced_bnode_property_list(self):
        """Unreferenced bnode subjects stay anonymous [ ... ] and parse."""
        b = Existential("b0")
        dt = NN("http://www.w3.org/2001/XMLSchema#double")
        triples = [
            T(b, NN("http://ex/value"), L("1.0", datatype=dt)),
            T(b, NN("http://www.w3.org/1999/02/22-rdf-syntax-ns#type"), NN("http://ex/RealRoot")),
        ]
        text, doc = self._roundtrip(triples)
        assert "[" in text and "]" in text
        assert len(doc.triples) == 2

    def test_datatyped_literal_roundtrip(self):
        dt = NN("http://ex/custom")
        triples = [T(NN("http://ex/a"), NN("http://ex/p"), L("v1", datatype=dt))]
        text, doc = self._roundtrip(triples)
        lit = doc.triples[0].object
        assert lit.value == "v1"
        assert lit.datatype.value == "http://ex/custom"

    def test_literal_escaping_roundtrip(self):
        """Backslashes, quotes, and newlines survive serialize → parse."""
        value = 'line1\nline2 \\ "quoted"\tend'
        triples = [T(NN("http://ex/a"), NN("http://ex/p"), L(value))]
        text, doc = self._roundtrip(triples)
        assert doc.triples[0].object.value == value

    def test_multi_triple_formula_roundtrip(self):
        """Formulas with several triples use '.' separators — ';' would
        chain onto the first subject and corrupt the graph."""
        from pyeye.term import Formula
        f = Formula((
            T(NN("http://ex/a"), NN("http://ex/p"), L("1", datatype=NN("http://www.w3.org/2001/XMLSchema#integer"))),
            T(NN("http://ex/b"), NN("http://ex/q"), L("2", datatype=NN("http://www.w3.org/2001/XMLSchema#integer"))),
        ))
        triples = [T(f, NN("http://ex/says"), NN("http://ex/x"))]
        text, doc = self._roundtrip(triples)
        inner = doc.triples[0].subject
        assert len(inner.triples) == 2
        subjects = {t.subject.value for t in inner.triples}
        assert subjects == {"http://ex/a", "http://ex/b"}

    def test_nested_formula_roundtrip(self):
        from pyeye.term import Formula
        innermost = Formula((T(NN("http://ex/x"), NN("http://ex/y"), NN("http://ex/z")),))
        outer = Formula((
            T(NN("http://ex/a"), NN("http://ex/believes"), innermost),
            T(NN("http://ex/a"), NN("http://ex/p"), NN("http://ex/b")),
        ))
        triples = [T(outer, NN("http://ex/states"), NN("http://ex/w"))]
        text, doc = self._roundtrip(triples)
        parsed_outer = doc.triples[0].subject
        assert len(parsed_outer.triples) == 2
