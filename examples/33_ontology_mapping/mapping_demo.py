"""
33 — Ontology Mapping / Schema Alignment
==========================================
Map between two vocabularies: schema.org and a local product ontology.
Input data uses schema.org terms; mapping rules derive local-ontology
equivalents so that both vocabularies work for queries.

Vocabulary mapping:
  schema:Product    ↔  local:Item
  schema:name       ↔  local:label
  schema:price      ↔  local:retailPrice
  schema:brand      ↔  local:manufacturer
  schema:Person     ↔  local:Customer
  schema:givenName  ↔  local:firstName
  schema:familyName ↔  local:lastName

Concepts:
  - Forward rules as schema bridges
  - Bidirectional: local data also maps to schema.org terms
  - Both vocabularies are queryable after inference
  - No OWL/RDFS entailment needed — pure N3 rules
"""

from pyeye import execute

# ---------------------------------------------------------------------------
# Input data in schema.org terms
# ---------------------------------------------------------------------------
schema_data = """
@prefix schema: <https://schema.org/> .
@prefix prod:   <http://example.org/product#> .
@prefix cust:   <http://example.org/customer#> .

prod:laptop01 a schema:Product ;
    schema:name  "UltraBook Pro" ;
    schema:price 1299 ;
    schema:brand "TechCorp" .

prod:mouse01  a schema:Product ;
    schema:name  "ErgoMouse X" ;
    schema:price 49 ;
    schema:brand "TechCorp" .

cust:alice a schema:Person ;
    schema:givenName  "Alice" ;
    schema:familyName "Nguyen" .
"""

# Local data already in local vocab
local_data = """
@prefix local:  <http://example.org/local#> .
@prefix prod:   <http://example.org/product#> .
@prefix cust:   <http://example.org/customer#> .

prod:keyboard01 a local:Item ;
    local:label        "MechKey 100" ;
    local:retailPrice  89 ;
    local:manufacturer "KeyCo" .

cust:bob a local:Customer ;
    local:firstName "Bob" ;
    local:lastName  "Smith" .
"""

# Mapping rules
rules = """
@prefix schema: <https://schema.org/> .
@prefix local:  <http://example.org/local#> .

# --- schema.org → local ---
{ ?P a schema:Product }                  => { ?P a local:Item } .
{ ?P schema:name ?N }                    => { ?P local:label ?N } .
{ ?P schema:price ?V }                   => { ?P local:retailPrice ?V } .
{ ?P schema:brand ?B }                   => { ?P local:manufacturer ?B } .
{ ?P a schema:Person }                   => { ?P a local:Customer } .
{ ?P schema:givenName ?N }               => { ?P local:firstName ?N } .
{ ?P schema:familyName ?N }              => { ?P local:lastName ?N } .

# --- local → schema.org ---
{ ?P a local:Item }                      => { ?P a schema:Product } .
{ ?P local:label ?N }                    => { ?P schema:name ?N } .
{ ?P local:retailPrice ?V }              => { ?P schema:price ?V } .
{ ?P local:manufacturer ?B }             => { ?P schema:brand ?B } .
{ ?P a local:Customer }                  => { ?P a schema:Person } .
{ ?P local:firstName ?N }               => { ?P schema:givenName ?N } .
{ ?P local:lastName ?N }                => { ?P schema:familyName ?N } .
"""

result = execute(
    data_strings=[schema_data, local_data],
    rule_strings=[rules],
)

# Collect items and customers from both vocabs
items = {}  # name → {price, manufacturer}
customers = {}  # firstName → lastName

def local_name(tok):
    return tok.strip("<>").split("#")[-1].split(":")[-1]

def strval(tok):
    if '"' in tok:
        return tok.split('"')[1]
    return tok

for line in result.triples.splitlines():
    line = line.strip().rstrip(" .")
    parts = line.split(None, 2) if line else []
    if len(parts) < 3:
        continue
    subj = local_name(parts[0])
    pred = parts[1]
    obj  = parts[2] if len(parts) > 2 else ""

    if "local:label" in pred or "schema:name" in pred:
        items.setdefault(subj, {})["name"] = strval(obj)
    elif "local:retailPrice" in pred or "schema:price" in pred:
        items.setdefault(subj, {})["price"] = strval(obj)
    elif "local:manufacturer" in pred or "schema:brand" in pred:
        items.setdefault(subj, {})["brand"] = strval(obj)
    elif "local:firstName" in pred or "schema:givenName" in pred:
        customers.setdefault(subj, {})["first"] = strval(obj)
    elif "local:lastName" in pred or "schema:familyName" in pred:
        customers.setdefault(subj, {})["last"] = strval(obj)

print("=== Ontology Mapping: schema.org ↔ local vocab ===\n")

print("All products (queryable via both vocabs after mapping):")
for pid, info in sorted(items.items()):
    name  = info.get("name", "?")
    price = info.get("price", "?")
    brand = info.get("brand", "?")
    print(f"  {pid:<15}  name={name!r}  price={price}  brand={brand}")

print("\nAll customers:")
for cid, info in sorted(customers.items()):
    print(f"  {cid:<10}  {info.get('first','')} {info.get('last','')}")

print()
print("Expected:")
print("  4 products total: laptop01, mouse01 (schema.org input) + keyboard01 (local input)")
print("  2 customers: alice (schema.org) + bob (local)")
print("  All queryable via either vocabulary after mapping rules fire")
