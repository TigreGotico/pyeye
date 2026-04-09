"""
06 — RDFS Entailment
====================
entail=True activates RDFS reasoning: class hierarchies, property hierarchies,
domain/range constraints, and type propagation.

Concepts:
  - rdfs:subClassOf  — transitive class hierarchy
  - rdfs:subPropertyOf — property subsumption
  - rdfs:domain / rdfs:range — typing from property use
  - execute(..., entail=True) — activates RDFS rules
  - No explicit rules needed — RDFS axioms are built-in

All W3C RDFS entailment rules (rdf1, rdfs1-rdfs13) are applied automatically.
"""

from pyeye import execute

# Example 1: Class hierarchy propagation
print("=== Class Hierarchy ===")

data = """
@prefix : <http://example.org/zoo#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

# Hierarchy: LionCub ⊆ Lion ⊆ Cat ⊆ Animal ⊆ LivingThing
:LionCub rdfs:subClassOf :Lion .
:Lion    rdfs:subClassOf :Cat .
:Cat     rdfs:subClassOf :Animal .
:Animal  rdfs:subClassOf :LivingThing .

# One instance
:simba a :LionCub .
"""

result = execute(data_strings=[data], entail=True, pass_mode=True)
print(result.triples)
# Expect: simba a :Lion, :Cat, :Animal, :LivingThing (all up the chain)


# Example 2: Domain and range typing
print("\n=== Domain/Range Typing ===")

data2 = """
@prefix : <http://example.org/hr#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
@prefix rdf:  <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

# :manages: subject is a Manager, object is an Employee
:manages rdfs:domain :Manager .
:manages rdfs:range  :Employee .

# Just the raw triple — no explicit types
:alice :manages :bob .
"""

result2 = execute(data_strings=[data2], entail=True, pass_mode=True)
print(result2.triples)
# Expect: :alice a :Manager . :bob a :Employee .


# Example 3: Property hierarchy
print("\n=== Property Hierarchy ===")

data3 = """
@prefix : <http://example.org/geo#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

# :locatedIn is a sub-property of :relatedTo
:locatedIn  rdfs:subPropertyOf :relatedTo .
:borderingOn rdfs:subPropertyOf :relatedTo .

:paris    :locatedIn  :france .
:france   :borderingOn :germany .
"""

result3 = execute(data_strings=[data3], entail=True, pass_mode=True)
print(result3.triples)
# Expect: :paris :relatedTo :france .  :france :relatedTo :germany .
