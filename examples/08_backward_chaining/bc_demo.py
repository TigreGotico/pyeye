"""
08 — Backward Chaining
=======================
Goal-directed reasoning: instead of deriving everything, ask a specific question
and let the engine search for a proof.

Concepts:
  - query=Triple(...)           — the goal to prove
  - result.query_answers        — list of variable bindings [{str: Term}, ...]
  - <= rules                    — backward-only rules (never run in forward pass)
  - [] log:table :predicate .   — memoize recursive predicates (avoid loops)
  - Variable(name)              — unbound query variable

When to use backward chaining:
  - The search space is large but the answer set is small
  - You have recursive predicates (ancestor, reachable, path)
  - You want specific answers, not all possible derivations
"""

from pyeye import execute, NamedNode, Variable, Triple

BASE = "http://example.org/"

def nn(local: str) -> NamedNode:
    return NamedNode(BASE + local)

# Example 1: Simple graph reachability
print("=== Reachability Query ===")

kb = """
@prefix : <http://example.org/> .
@prefix log: <http://www.w3.org/2000/10/swap/log#> .

# Memoize :reachable so recursive proof doesn't loop
[] log:table :reachable .

# Facts: directed edges
:a :edge :b .
:b :edge :c .
:c :edge :d .
:a :edge :e .

# Backward rules: reachable in 1 hop or transitively
{ ?X :reachable ?Y } <= { ?X :edge ?Y } .
{ ?X :reachable ?Y } <= { ?X :reachable ?Z . ?Z :reachable ?Y } .
"""

# Query: what is reachable FROM :a?
q = Triple(nn("a"), nn("reachable"), Variable("Dest"))

result = execute(rule_strings=[kb], query=q)
print("From :a, can reach:")
for binding in result.query_answers:
    print(" ", binding["Dest"])


# Example 2: Mixed forward + backward
print("\n=== Mixed: Forward Rules + Backward Query ===")

data = """
@prefix hr: <http://example.org/hr#> .

hr:alice hr:manages hr:bob .
hr:bob   hr:manages hr:carol .
hr:carol hr:manages hr:dave .
"""

rules = """
@prefix hr: <http://example.org/hr#> .
@prefix log: <http://www.w3.org/2000/10/swap/log#> .

# Forward rule: manager is a supervisor too
{ ?X hr:manages ?Y } => { ?X hr:supervisor ?Y } .

# Backward rule: reports-to is transitive
[] log:table hr:reportsTo .
{ ?X hr:reportsTo ?Y } <= { ?Y hr:manages ?X } .
{ ?X hr:reportsTo ?Y } <= { ?X hr:reportsTo ?Z . ?Z hr:reportsTo ?Y } .
"""

# Query: who does dave report to (all levels)?
q2 = Triple(nn("hr#dave"), nn("hr#reportsTo"), Variable("Boss"))
result2 = execute(data_strings=[data], rule_strings=[rules], query=q2)

print("dave reports to:")
for binding in result2.query_answers:
    print(" ", binding["Boss"])


# Example 3: Query with multiple variables
print("\n=== Multi-Variable Query ===")

kb3 = """
@prefix : <http://example.org/> .

:paris     :locatedIn :france .
:lyon      :locatedIn :france .
:berlin    :locatedIn :germany .
:munich    :locatedIn :germany .
:france    :locatedIn :europe .
:germany   :locatedIn :europe .
"""

rules3 = """
@prefix : <http://example.org/> .
@prefix log: <http://www.w3.org/2000/10/swap/log#> .

[] log:table :region .
{ ?X :region ?R } <= { ?X :locatedIn ?R } .
{ ?X :region ?R } <= { ?X :locatedIn ?M . ?M :region ?R } .
"""

# Query: what regions does paris belong to?
q3 = Triple(nn("paris"), nn("region"), Variable("R"))
result3 = execute(data_strings=[kb3], rule_strings=[rules3], query=q3)

print("paris is in regions:")
for b in result3.query_answers:
    print(" ", b["R"])
