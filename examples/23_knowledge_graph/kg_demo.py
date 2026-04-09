"""
23 — Knowledge Graph Enrichment
=================================
A realistic scenario: enriching a product knowledge graph with derived
facts — synonyms, category hierarchies, compatibility links, and
marketing classifications — using forward chaining over a mix of
explicit facts and inference rules.

This demonstrates how pyeye can act as the "reasoning layer" in a
knowledge graph pipeline, adding implicit knowledge that would otherwise
require manual curation.

The pipeline:
  1. Raw product catalogue (facts)
  2. Category taxonomy (RDFS hierarchy)
  3. Enrichment rules (business logic)
  4. Result: fully enriched, navigable product graph
"""

from pyeye import execute

# ---------------------------------------------------------------------------
# Raw catalogue data
# ---------------------------------------------------------------------------
catalogue = """
@prefix prod:  <http://example.org/product#> .
@prefix cat:   <http://example.org/category#> .
@prefix brand: <http://example.org/brand#> .
@prefix rdfs:  <http://www.w3.org/2000/01/rdf-schema#> .

# Category hierarchy
cat:Laptop       rdfs:subClassOf cat:Computer .
cat:Desktop      rdfs:subClassOf cat:Computer .
cat:Computer     rdfs:subClassOf cat:Electronics .
cat:Smartphone   rdfs:subClassOf cat:MobileDevice .
cat:Tablet       rdfs:subClassOf cat:MobileDevice .
cat:MobileDevice rdfs:subClassOf cat:Electronics .

# Products
prod:p1 a cat:Laptop ;
    prod:brand brand:alpha ;
    prod:price 1200 ;
    prod:ram 16 ;
    prod:os "linux" .

prod:p2 a cat:Laptop ;
    prod:brand brand:beta ;
    prod:price 800 ;
    prod:ram 8 ;
    prod:os "windows" .

prod:p3 a cat:Desktop ;
    prod:brand brand:alpha ;
    prod:price 600 ;
    prod:ram 32 ;
    prod:os "linux" .

prod:p4 a cat:Smartphone ;
    prod:brand brand:alpha ;
    prod:price 950 ;
    prod:os "android" .

prod:p5 a cat:Tablet ;
    prod:brand brand:beta ;
    prod:price 450 ;
    prod:os "android" .
"""

# ---------------------------------------------------------------------------
# Enrichment rules
# ---------------------------------------------------------------------------
rules = """
@prefix prod:  <http://example.org/product#> .
@prefix cat:   <http://example.org/category#> .
@prefix rdfs:  <http://www.w3.org/2000/01/rdf-schema#> .
@prefix rdf:   <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
@prefix math:  <http://www.w3.org/2000/10/swap/math#> .
@prefix log:   <http://www.w3.org/2000/10/swap/log#> .

# 1. Inherit category ancestors (transitive subClassOf)
{ ?A rdfs:subClassOf ?B . ?P a ?A } => { ?P a ?B } .

# 2. Price tiers
{ ?P prod:price ?V . ?V math:lessThan 600 }    => { ?P prod:tier "budget" } .
{ ?P prod:price ?V . ?V math:greaterThan 999 }  => { ?P prod:tier "premium" } .
{ ?P prod:price ?V .
  ?V math:greaterThan 599 .
  ?V math:lessThan 1000 }                        => { ?P prod:tier "mid-range" } .

# 3. High RAM flag
{ ?P prod:ram ?R . ?R math:greaterThan 15 } => { ?P prod:highMemory true } .

# 4. Same-brand compatibility
{ ?A prod:brand ?B . ?C prod:brand ?B . ?A log:notEqualTo ?C }
    => { ?A prod:compatibleBrand ?C } .

# 5. Cross-OS flag
{ ?A prod:os "linux" } => { ?A prod:openSource true } .

# 6. Mobile products
{ ?P a cat:MobileDevice } => { ?P prod:formFactor "portable" } .
{ ?P a cat:Computer }     => { ?P prod:formFactor "stationary" } .
"""

print("=== Product Graph Enrichment ===")
result = execute(
    data_strings=[catalogue],
    rule_strings=[rules],
    entail=True,
)

# Filter to interesting derived properties
import re
sections = {
    "tiers":     r":tier",
    "portable":  r"formFactor",
    "openSource":r"openSource",
    "highMem":   r"highMemory",
}

for label, pattern in sections.items():
    matches = [l for l in result.triples.splitlines() if re.search(pattern, l)]
    if matches:
        print(f"\n--- {label} ---")
        for m in sorted(matches):
            print(" ", m.strip())


# ---------------------------------------------------------------------------
# Query: which premium electronics support android?
# ---------------------------------------------------------------------------
print("\n=== Query: Premium Android Devices ===")

query_rules = rules + """
@prefix prod: <http://example.org/product#> .
@prefix cat:  <http://example.org/category#> .

{ ?P prod:tier "premium" . ?P a cat:Electronics . ?P prod:os "android" }
    => { ?P prod:label "premium-android" } .
"""

result2 = execute(data_strings=[catalogue], rule_strings=[query_rules], entail=True)
for line in result2.triples.splitlines():
    if "premium-android" in line:
        print(" ", line.strip())
