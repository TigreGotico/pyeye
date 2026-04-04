"""Tests for Phase 2: RDFS entailment."""

from __future__ import annotations

import pytest

from pyeye import execute
from pyeye.rdfs import apply_rdfs_entailment
from pyeye.store import TripleStore
from pyeye.term import NamedNode, Triple


NN = NamedNode
T = Triple


class TestRDFSEntailment:
    """FR 2h.38-40: RDFS entailment modes."""

    def test_subclass_of(self):
        """If A subClassOf B and X type A → X type B."""
        store = TripleStore()
        store.add(T(NN("http://x/cat"), NN("http://www.w3.org/2000/01/rdf-schema#subClassOf"), NN("http://x/animal")))
        store.add(T(NN("http://x/fluffy"), NN("http://www.w3.org/1999/02/22-rdf-syntax-ns#type"), NN("http://x/cat")))
        count = apply_rdfs_entailment(store)
        assert count == 1
        # Fluffy should now be typed as animal
        assert store.contains(T(NN("http://x/fluffy"), NN("http://www.w3.org/1999/02/22-rdf-syntax-ns#type"), NN("http://x/animal")))

    def test_subproperty_of(self):
        """If P subPropertyOf Q and A P B → A Q B."""
        store = TripleStore()
        store.add(T(NN("http://x/hasChild"), NN("http://www.w3.org/2000/01/rdf-schema#subPropertyOf"), NN("http://x/hasRelative")))
        store.add(T(NN("http://x/alice"), NN("http://x/hasChild"), NN("http://x/bob")))
        count = apply_rdfs_entailment(store)
        assert count == 1
        assert store.contains(T(NN("http://x/alice"), NN("http://x/hasRelative"), NN("http://x/bob")))

    def test_domain(self):
        """If P domain D and A P B → A type D."""
        store = TripleStore()
        store.add(T(NN("http://x/hasChild"), NN("http://www.w3.org/2000/01/rdf-schema#domain"), NN("http://x/Parent")))
        store.add(T(NN("http://x/alice"), NN("http://x/hasChild"), NN("http://x/bob")))
        count = apply_rdfs_entailment(store)
        assert count == 1
        assert store.contains(T(NN("http://x/alice"), NN("http://www.w3.org/1999/02/22-rdf-syntax-ns#type"), NN("http://x/Parent")))

    def test_range(self):
        """If P range R and A P B → B type R."""
        store = TripleStore()
        store.add(T(NN("http://x/hasChild"), NN("http://www.w3.org/2000/01/rdf-schema#range"), NN("http://x/Person")))
        store.add(T(NN("http://x/alice"), NN("http://x/hasChild"), NN("http://x/bob")))
        count = apply_rdfs_entailment(store)
        assert count == 1
        assert store.contains(T(NN("http://x/bob"), NN("http://www.w3.org/1999/02/22-rdf-syntax-ns#type"), NN("http://x/Person")))

    def test_chained_entailment(self):
        """Multiple entailment rules chain together."""
        store = TripleStore()
        store.add(T(NN("http://x/cat"), NN("http://www.w3.org/2000/01/rdf-schema#subClassOf"), NN("http://x/animal")))
        store.add(T(NN("http://x/animal"), NN("http://www.w3.org/2000/01/rdf-schema#subClassOf"), NN("http://x/livingThing")))
        store.add(T(NN("http://x/fluffy"), NN("http://www.w3.org/1999/02/22-rdf-syntax-ns#type"), NN("http://x/cat")))
        count = apply_rdfs_entailment(store)
        # Should derive: fluffy type animal, fluffy type livingThing
        assert count == 2
        assert store.contains(T(NN("http://x/fluffy"), NN("http://www.w3.org/1999/02/22-rdf-syntax-ns#type"), NN("http://x/livingThing")))

    def test_no_rdfs_data(self):
        """No entailment when no RDFS declarations."""
        store = TripleStore()
        store.add(T(NN("http://x/a"), NN("http://x/p"), NN("http://x/b")))
        count = apply_rdfs_entailment(store)
        assert count == 0

    def test_execute_with_entail(self):
        """execute(entail=True) applies RDFS before user rules."""
        r = execute(
            data_strings=[
                """
                @prefix : <http://ex.org/> .
                @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
                @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
                :Cat rdfs:subClassOf :Animal .
                :fluffy rdf:type :Cat .
                """,
            ],
            rule_strings=[
                """
                @prefix : <http://ex.org/> .
                @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
                { ?X rdf:type :Animal } => { ?X :isAlive true } .
                """,
            ],
            entail=True,
        )
        # RDFS should derive :fluffy rdf:type :Animal
        # Then the user rule should derive :fluffy :isAlive true
        assert ":isAlive" in r.triples or "http://ex.org/isAlive" in r.triples
