"""
07 — OWL 2 RL Entailment
=========================
entail_owl=True activates OWL 2 RL reasoning (a tractable subset of OWL 2
designed for rule-based engines). It implies entail=True (RDFS is included).

Concepts covered:
  - owl:inverseOf         — bidirectional properties
  - owl:SymmetricProperty — property equals its inverse
  - owl:TransitiveProperty — transitive closure
  - owl:sameAs            — individual identity
  - owl:FunctionalProperty — at most one value
  - owl:InverseFunctionalProperty
"""

from pyeye import execute

# Example 1: Inverse properties
print("=== owl:inverseOf ===")

data = """
@prefix : <http://example.org/org#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .

# Define inverse pair
:employs owl:inverseOf :employedBy .

# Fact in one direction only
:acme :employs :alice .
:acme :employs :bob .
"""

result = execute(data_strings=[data], entail_owl=True, pass_mode=True)
print(result.triples)
# Expect: :alice :employedBy :acme .  :bob :employedBy :acme .


# Example 2: Symmetric property
print("\n=== owl:SymmetricProperty ===")

data2 = """
@prefix : <http://example.org/social#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

:friendOf rdf:type owl:SymmetricProperty .

:alice :friendOf :bob .
:carol :friendOf :dave .
"""

result2 = execute(data_strings=[data2], entail_owl=True, pass_mode=True)
print(result2.triples)
# Expect: :bob :friendOf :alice .  :dave :friendOf :carol .


# Example 3: Transitive property
print("\n=== owl:TransitiveProperty ===")

data3 = """
@prefix : <http://example.org/regions#> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .

:isPartOf rdf:type owl:TransitiveProperty .

:wheel    :isPartOf :car .
:car      :isPartOf :fleet .
:fleet    :isPartOf :corporation .
"""

result3 = execute(data_strings=[data3], entail_owl=True, pass_mode=True)
print(result3.triples)
# Expect: :wheel :isPartOf :fleet .  :wheel :isPartOf :corporation .
#         :car   :isPartOf :corporation .


# Example 4: sameAs identity
print("\n=== owl:sameAs ===")

data4 = """
@prefix : <http://example.org/> .
@prefix owl: <http://www.w3.org/2002/07/owl#> .

# Two URIs for the same person
:alice           owl:sameAs :AliceSmith .
:alice           :age 30 .
:AliceSmith      :worksAt :AcmeCorp .
"""

result4 = execute(data_strings=[data4], entail_owl=True, pass_mode=True)
print(result4.triples)
# Expect: :AliceSmith :age 30 .  :alice :worksAt :AcmeCorp .
