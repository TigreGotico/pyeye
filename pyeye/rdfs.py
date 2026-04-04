"""RDFS entailment rules.

Applies RDFS inference rules to derive implicit triples before
user-defined rules run. Implements:

- subClassOf: if A subClassOf B and X type A → X type B
- subPropertyOf: if P subPropertyOf Q and A P B → A Q B
- domain: if P domain D and A P B → A type D
- range: if P range R and A P B → B type R

Source: `apply_rdfs_entailment` — `pyeye/rdfs.py:14`
"""

from __future__ import annotations

from pyeye.term import NamedNode, Triple, Term
from pyeye.store import TripleStore


# RDFS vocabulary
RDF_TYPE = NamedNode("http://www.w3.org/1999/02/22-rdf-syntax-ns#type")
RDFS_SUBCLASSOF = NamedNode("http://www.w3.org/2000/01/rdf-schema#subClassOf")
RDFS_SUBPROPERTYOF = NamedNode("http://www.w3.org/2000/01/rdf-schema#subPropertyOf")
RDFS_DOMAIN = NamedNode("http://www.w3.org/2000/01/rdf-schema#domain")
RDFS_RANGE = NamedNode("http://www.w3.org/2000/01/rdf-schema#range")


def apply_rdfs_entailment(store: TripleStore) -> int:
    """Apply RDFS entailment rules to the store.

    Returns the number of new triples derived.

    The process iterates until fixpoint (no new triples derived).
    """
    total_new = 0

    while True:
        new_this_pass = 0
        to_add: list[Triple] = []

        # 1. subClassOf: if A subClassOf B and X type A → X type B
        for subclass_triple in list(store.match(predicate=RDFS_SUBCLASSOF)):
            class_a = subclass_triple.subject
            class_b = subclass_triple.object
            for type_triple in list(store.match(predicate=RDF_TYPE, object=class_a)):
                instance = type_triple.subject
                new_triple = Triple(instance, RDF_TYPE, class_b)
                to_add.append(new_triple)

        # 2. subPropertyOf: if P subPropertyOf Q and A P B → A Q B
        for subprop_triple in list(store.match(predicate=RDFS_SUBPROPERTYOF)):
            prop_p = subprop_triple.subject
            prop_q = subprop_triple.object
            for fact_triple in list(store.match(predicate=prop_p)):
                new_triple = Triple(fact_triple.subject, prop_q, fact_triple.object)
                to_add.append(new_triple)

        # 3. domain: if P domain D and A P B → A type D
        for domain_triple in list(store.match(predicate=RDFS_DOMAIN)):
            prop_p = domain_triple.subject
            domain_class = domain_triple.object
            for fact_triple in list(store.match(predicate=prop_p)):
                new_triple = Triple(fact_triple.subject, RDF_TYPE, domain_class)
                to_add.append(new_triple)

        # 4. range: if P range R and A P B → B type R
        for range_triple in list(store.match(predicate=RDFS_RANGE)):
            prop_p = range_triple.subject
            range_class = range_triple.object
            for fact_triple in list(store.match(predicate=prop_p)):
                new_triple = Triple(fact_triple.object, RDF_TYPE, range_class)
                to_add.append(new_triple)

        # Add all new triples
        for t in to_add:
            if store.add(t):
                new_this_pass += 1

        total_new += new_this_pass
        if new_this_pass == 0:
            break  # fixpoint

    return total_new
