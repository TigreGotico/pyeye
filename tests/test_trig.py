"""Tests for Phase 2: TriG named graph parsing."""

from __future__ import annotations

from pyeye.parser import parse_n3
from pyeye.term import NamedNode, Quad, Triple


NN = NamedNode


class TestTriGParsing:
    """FR 2g.33-34: TriG parsing and quad storage."""

    def test_single_graph(self):
        text = """
@prefix : <http://ex.org/> .
GRAPH :g1 {
    :alice :name "Alice" .
    :bob :name "Bob" .
}
"""
        doc = parse_n3(text)
        assert len(doc.quads) == 2
        assert all(q.graph == NN("http://ex.org/g1") for q in doc.quads)

    def test_multiple_graphs(self):
        text = """
@prefix : <http://ex.org/> .
GRAPH :g1 { :a :p :b . }
GRAPH :g2 { :c :q :d . }
"""
        doc = parse_n3(text)
        assert len(doc.quads) == 2
        assert doc.quads[0].graph == NN("http://ex.org/g1")
        assert doc.quads[1].graph == NN("http://ex.org/g2")

    def test_graph_with_prefix(self):
        text = """
@prefix ex: <http://ex.org/> .
GRAPH <http://graphs.example.org/people> {
    ex:alice ex:name "Alice" .
}
"""
        doc = parse_n3(text)
        assert len(doc.quads) == 1
        assert doc.quads[0].graph == NN("http://graphs.example.org/people")

    def test_graph_subject(self):
        text = """
@prefix : <http://ex.org/> .
GRAPH :myGraph {
    :alice :name "Alice" .
}
"""
        doc = parse_n3(text)
        assert len(doc.quads) == 1
        q = doc.quads[0]
        assert q.subject == NN("http://ex.org/alice")
        assert q.predicate == NN("http://ex.org/name")
        assert q.object.value == "Alice"
        assert q.graph == NN("http://ex.org/myGraph")

    def test_triples_and_graphs_mixed(self):
        """Default graph triples + named graphs."""
        text = """
@prefix : <http://ex.org/> .
:a :p :b .
GRAPH :g1 { :c :q :d . }
"""
        doc = parse_n3(text)
        assert len(doc.triples) == 1
        assert len(doc.quads) == 1
