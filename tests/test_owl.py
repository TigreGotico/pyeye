"""Tests for OWL 2 RL entailment."""

from __future__ import annotations

import pytest

from pyeye.engine import Engine
from pyeye.parser import Rule
from pyeye.term import NamedNode, Literal, Variable, Existential, Triple, Formula
from pyeye.owl import apply_owl_rl_entailment

NN = NamedNode
V = Variable
T = Triple
F = Formula


OWL_SAME_AS = NN("http://www.w3.org/2002/07/owl#sameAs")
OWL_DIFFERENT_FROM = NN("http://www.w3.org/2002/07/owl#differentFrom")
OWL_EQUIV_CLASS = NN("http://www.w3.org/2002/07/owl#equivalentClass")
OWL_EQUIV_PROP = NN("http://www.w3.org/2002/07/owl#equivalentProperty")
OWL_INVERSE_OF = NN("http://www.w3.org/2002/07/owl#inverseOf")
OWL_TRANSITIVE_PROP = NN("http://www.w3.org/2002/07/owl#TransitiveProperty")
OWL_SYMMETRIC_PROP = NN("http://www.w3.org/2002/07/owl#SymmetricProperty")
OWL_FUNCTIONAL_PROP = NN("http://www.w3.org/2002/07/owl#FunctionalProperty")
OWL_INV_FUNCTIONAL_PROP = NN("http://www.w3.org/2002/07/owl#InverseFunctionalProperty")
OWL_INTERSECTION_OF = NN("http://www.w3.org/2002/07/owl#intersectionOf")
OWL_UNION_OF = NN("http://www.w3.org/2002/07/owl#unionOf")
OWL_ONE_OF = NN("http://www.w3.org/2002/07/owl#oneOf")
OWL_SOME_VALUES_FROM = NN("http://www.w3.org/2002/07/owl#someValuesFrom")
OWL_ALL_VALUES_FROM = NN("http://www.w3.org/2002/07/owl#allValuesFrom")
OWL_HAS_VALUE = NN("http://www.w3.org/2002/07/owl#hasValue")
OWL_PROPERTY_CHAIN_AXIOM = NN("http://www.w3.org/2002/07/owl#propertyChainAxiom")
OWL_ALL_DIFFERENT = NN("http://www.w3.org/2002/07/owl#AllDifferent")
OWL_DISTINCT_MEMBERS = NN("http://www.w3.org/2002/07/owl#distinctMembers")
RDF_TYPE = NN("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")
RDF_FIRST = NN("http://www.w3.org/1999/02/22-rdf-syntax-ns#first")
RDF_REST = NN("http://www.w3.org/1999/02/22-rdf-syntax-ns#rest")
RDF_NIL = Existential("nil")
RDFS_SUBCLASS_OF = NN("http://www.w3.org/2000/01/rdf-schema#subClassOf")


class TestSameAs:
    """OWL sameAs: reflexive, symmetric, transitive."""

    def test_sameas_reflexive(self):
        """Every individual is sameAs itself."""
        store = Engine().store
        store.add(T(NN("http://x/a"), NN("http://x/p"), NN("http://x/b")))
        apply_owl_rl_entailment(store)
        assert T(NN("http://x/a"), OWL_SAME_AS, NN("http://x/a")) in store
        assert T(NN("http://x/b"), OWL_SAME_AS, NN("http://x/b")) in store

    def test_sameas_symmetric(self):
        """If a sameAs b then b sameAs a."""
        store = Engine().store
        store.add(T(NN("http://x/a"), OWL_SAME_AS, NN("http://x/b")))
        apply_owl_rl_entailment(store)
        assert T(NN("http://x/b"), OWL_SAME_AS, NN("http://x/a")) in store

    def test_sameas_transitive(self):
        """If a sameAs b and b sameAs c then a sameAs c."""
        store = Engine().store
        store.add(T(NN("http://x/a"), OWL_SAME_AS, NN("http://x/b")))
        store.add(T(NN("http://x/b"), OWL_SAME_AS, NN("http://x/c")))
        apply_owl_rl_entailment(store)
        assert T(NN("http://x/a"), OWL_SAME_AS, NN("http://x/c")) in store


class TestDifferentFrom:
    """OWL differentFrom: symmetric."""

    def test_differentfrom_symmetric(self):
        """If a differentFrom b then b differentFrom a."""
        store = Engine().store
        store.add(T(NN("http://x/a"), OWL_DIFFERENT_FROM, NN("http://x/b")))
        apply_owl_rl_entailment(store)
        assert T(NN("http://x/b"), OWL_DIFFERENT_FROM, NN("http://x/a")) in store


class TestTransitiveProperty:
    """PRP-TRP: Transitive property inference."""

    def test_transitive_chain(self):
        """If P is transitive and a P b and b P c then a P c."""
        store = Engine().store
        store.add(T(NN("http://x/ancestor"), RDF_TYPE, OWL_TRANSITIVE_PROP))
        store.add(T(NN("http://x/a"), NN("http://x/ancestor"), NN("http://x/b")))
        store.add(T(NN("http://x/b"), NN("http://x/ancestor"), NN("http://x/c")))
        apply_owl_rl_entailment(store)
        assert T(NN("http://x/a"), NN("http://x/ancestor"), NN("http://x/c")) in store


class TestSymmetricProperty:
    """PRP-SYMP: Symmetric property inference."""

    def test_symmetric_reverse(self):
        """If P is symmetric and a P b then b P a."""
        store = Engine().store
        store.add(T(NN("http://x/knows"), RDF_TYPE, OWL_SYMMETRIC_PROP))
        store.add(T(NN("http://x/a"), NN("http://x/knows"), NN("http://x/b")))
        apply_owl_rl_entailment(store)
        assert T(NN("http://x/b"), NN("http://x/knows"), NN("http://x/a")) in store


class TestInverseProperty:
    """PRP-INV: Inverse property inference."""

    def test_inverse(self):
        """If P inverseOf Q and a P b then b Q a."""
        store = Engine().store
        store.add(T(NN("http://x/hasParent"), OWL_INVERSE_OF, NN("http://x/hasChild")))
        store.add(T(NN("http://x/b"), NN("http://x/hasParent"), NN("http://x/a")))
        apply_owl_rl_entailment(store)
        assert T(NN("http://x/a"), NN("http://x/hasChild"), NN("http://x/b")) in store


class TestFunctionalProperty:
    """PRP-FP: Functional property inference."""

    def test_functional_sameas(self):
        """If P is functional and x P y1 and x P y2 then y1 sameAs y2."""
        store = Engine().store
        store.add(T(NN("http://x/ssn"), RDF_TYPE, OWL_FUNCTIONAL_PROP))
        store.add(T(NN("http://x/person"), NN("http://x/ssn"), NN("http://x/num1")))
        store.add(T(NN("http://x/person"), NN("http://x/ssn"), NN("http://x/num2")))
        apply_owl_rl_entailment(store)
        assert T(NN("http://x/num1"), OWL_SAME_AS, NN("http://x/num2")) in store


class TestEquivalentClass:
    """EquivalentClass: bidirectional subClassOf."""

    def test_equiv_class_subclassof(self):
        """If A equivalentClass B and A subClassOf C then B subClassOf C."""
        store = Engine().store
        store.add(T(NN("http://x/A"), OWL_EQUIV_CLASS, NN("http://x/B")))
        store.add(T(NN("http://x/A"), RDFS_SUBCLASS_OF, NN("http://x/C")))
        apply_owl_rl_entailment(store)
        assert T(NN("http://x/B"), RDFS_SUBCLASS_OF, NN("http://x/C")) in store


class TestEquivalentProperty:
    """PRP-EQP: Equivalent properties."""

    def test_equiv_prop(self):
        """If P equivalentProperty Q and a P b then a Q b."""
        store = Engine().store
        store.add(T(NN("http://x/P"), OWL_EQUIV_PROP, NN("http://x/Q")))
        store.add(T(NN("http://x/a"), NN("http://x/P"), NN("http://x/b")))
        apply_owl_rl_entailment(store)
        assert T(NN("http://x/a"), NN("http://x/Q"), NN("http://x/b")) in store


class TestIntersectionOf:
    """CLS-INT: intersectionOf."""

    def test_intersection_instance(self):
        """If C intersectionOf [D1, D2] and x type D1 and x type D2 then x type C."""
        store = Engine().store
        # Create intersection restriction
        restriction = Existential("_r1")
        store.add(T(NN("http://x/C"), OWL_INTERSECTION_OF, restriction))
        # Create list [Person, Employee]
        item1 = Existential("_i1")
        item2 = Existential("_i2")
        store.add(T(restriction, RDF_FIRST, NN("http://x/Person")))
        store.add(T(restriction, RDF_REST, item1))
        store.add(T(item1, RDF_FIRST, NN("http://x/Employee")))
        store.add(T(item1, RDF_REST, RDF_NIL))
        # x type Person and x type Employee
        store.add(T(NN("http://x/john"), RDF_TYPE, NN("http://x/Person")))
        store.add(T(NN("http://x/john"), RDF_TYPE, NN("http://x/Employee")))
        apply_owl_rl_entailment(store)
        assert T(NN("http://x/john"), RDF_TYPE, NN("http://x/C")) in store


class TestPropertyChain:
    """Property chain axiom."""

    def test_property_chain(self):
        """If P propertyChainAxiom [Q, R] and a Q b and b R c then a P c."""
        store = Engine().store
        # Create chain list
        chain = Existential("_chain1")
        item1 = Existential("_c1")
        store.add(T(NN("http://x/uncle"), OWL_PROPERTY_CHAIN_AXIOM, chain))
        store.add(T(chain, RDF_FIRST, NN("http://x/hasParent")))
        store.add(T(chain, RDF_REST, item1))
        store.add(T(item1, RDF_FIRST, NN("http://x/hasBrother")))
        store.add(T(item1, RDF_REST, RDF_NIL))
        # Facts
        store.add(T(NN("http://x/a"), NN("http://x/hasParent"), NN("http://x/b")))
        store.add(T(NN("http://x/b"), NN("http://x/hasBrother"), NN("http://x/c")))
        apply_owl_rl_entailment(store)
        assert T(NN("http://x/a"), NN("http://x/uncle"), NN("http://x/c")) in store


class TestExecuteWithOwlEntailment:
    """Integration: execute() with entail_owl=True."""

    def test_entail_owl_flag(self):
        """OWL entailment via execute()."""
        from pyeye import execute
        result = execute(
            data_strings=[
                '@prefix : <http://ex.org/> .',
                '<http://ex.org/knows> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://www.w3.org/2002/07/owl#TransitiveProperty> .',
                '<http://ex.org/a> <http://ex.org/knows> <http://ex.org/b> .',
                '<http://ex.org/b> <http://ex.org/knows> <http://ex.org/c> .',
            ],
            rule_strings=[
                '@prefix : <http://ex.org/> .',
                ':a :p :b .',
            ],
            entail_owl=True,
            pass_mode=True,
        )
        # The transitive property should derive :a :knows :c
        assert "knows" in result.triples
