"""
10 — Aggregation: collectAllIn and forAllIn
============================================
log:collectAllIn collects all solutions to a sub-pattern into an RDF list,
then lets you use list: builtins (length, sum, member) on the results.

log:forAllIn asserts that a pattern holds for every member of a list.

Concepts:
  - (1 { <body-pattern> } ?List) log:collectAllIn ?Scope
      → ?List becomes a list of all objects bound by body-pattern
  - ?List math:sum ?Total             → sum the list
  - ?List list:length ?Count          → count elements
  - log:forAllIn                      → universal quantification over a list

Note: The scope variable (?Scope) must be an in-scope variable that makes
the pattern context-sensitive (typically the subject of the outer rule).
"""

from pyeye import execute

# Example 1: Count connections (degree in a graph)
print("=== Node Degree ===")

data = """
@prefix graph: <http://example.org/graph#> .

graph:a graph:edge graph:b .
graph:a graph:edge graph:c .
graph:a graph:edge graph:d .
graph:b graph:edge graph:c .
graph:c graph:edge graph:d .
"""

rules = """
@prefix graph: <http://example.org/graph#> .
@prefix log:   <http://www.w3.org/2000/10/swap/log#> .
@prefix list:  <http://www.w3.org/2000/10/swap/list#> .
@prefix math:  <http://www.w3.org/2000/10/swap/math#> .

{
    ?Node graph:edge ?Any .
    (1 { ?Node graph:edge ?Neighbour } ?Ns) log:collectAllIn ?Node .
    ?Ns list:length ?Degree
}
    => { ?Node graph:degree ?Degree } .
"""

result = execute(data_strings=[data], rule_strings=[rules])
print(result.triples)


# Example 2: Total order value (sum line items)
print("\n=== Order Total ===")

data2 = """
@prefix shop: <http://example.org/shop#> .

shop:order1 shop:item shop:item1, shop:item2, shop:item3 .
shop:item1  shop:price 29 .
shop:item2  shop:price 15 .
shop:item3  shop:price 8 .

shop:order2 shop:item shop:item4 .
shop:item4  shop:price 100 .
"""

rules2 = """
@prefix shop: <http://example.org/shop#> .
@prefix log:  <http://www.w3.org/2000/10/swap/log#> .
@prefix math: <http://www.w3.org/2000/10/swap/math#> .

{
    ?Order shop:item ?AnyItem .
    (?P { ?Order shop:item ?I . ?I shop:price ?P } ?Prices) log:collectAllIn ?Order .
    ?Prices math:sum ?Total
}
    => { ?Order shop:total ?Total } .
"""

result2 = execute(data_strings=[data2], rule_strings=[rules2])
print(result2.triples)


# Example 3: Require dog license (more than 4 dogs)
print("\n=== Dog License Threshold ===")

data3 = """
@prefix : <http://example.org/> .

:alice :hasDog :fido, :rex, :spot, :max, :bella .
:bob   :hasDog :scout .
"""

rules3 = """
@prefix : <http://example.org/> .
@prefix log:  <http://www.w3.org/2000/10/swap/log#> .
@prefix list: <http://www.w3.org/2000/10/swap/list#> .
@prefix math: <http://www.w3.org/2000/10/swap/math#> .

{
    ?Owner :hasDog ?Any .
    (1 { ?Owner :hasDog ?Dog } ?Dogs) log:collectAllIn ?Owner .
    ?Dogs list:length ?N .
    ?N math:greaterThan 4
}
    => { ?Owner :requiresDogLicense true } .
"""

result3 = execute(data_strings=[data3], rule_strings=[rules3])
print(result3.triples)
# Expect: :alice :requiresDogLicense true .  (bob has only 1 dog)
