"""
21 — Direct Engine API
=======================
The ``execute()`` function covers most use cases, but the ``Engine`` class
can be used directly for fine-grained control: inspecting derived triples,
querying the store, building the engine programmatically, and reusing it
across multiple runs.

Key classes and methods:
  - Engine(builtins, max_steps, timeout_seconds)
  - engine.add_triple(triple) → bool     — add a fact
  - engine.add_rule(rule)                — add a rule
  - engine.run()                         — forward chain to fixpoint
  - engine.store.match(s, p, o)          — query the store
  - engine.derived_triples               — only rule-derived facts
  - engine.step_count                    — how many steps were taken
  - engine.backward_chain(query_triple)  — BC query
  - parse_n3(text)                       — parse N3 text to doc

Building triples directly:
  - Triple(subject, predicate, object)
  - NamedNode("http://...")
  - Literal("value", datatype=NamedNode("..."))
  - Variable("name")
"""

from pyeye.engine import Engine
from pyeye.parser import parse_n3, Rule
from pyeye.term import NamedNode, Literal, Variable, Triple, Formula
from pyeye.output import N3Writer

BASE = "http://example.org/"
XSD  = "http://www.w3.org/2001/XMLSchema#"

def nn(local: str) -> NamedNode:
    return NamedNode(BASE + local)

def lit_int(n: int) -> Literal:
    return Literal(str(n), datatype=NamedNode(XSD + "integer"))

# ---------------------------------------------------------------------------
# Example 1: Build engine programmatically (no N3 parsing)
# ---------------------------------------------------------------------------
print("=== Programmatic Engine (no N3) ===")

engine = Engine()

# Add facts as Python objects
for name, age in [("alice", 32), ("bob", 17), ("carol", 45)]:
    engine.add_triple(Triple(nn(name), nn("name"), Literal(name)))
    engine.add_triple(Triple(nn(name), nn("age"), lit_int(age)))

# Add a rule: age >= 18 → isAdult
adult_pred = NamedNode("http://www.w3.org/2000/10/swap/math#greaterThan")
engine.add_rule(Rule(
    body=Formula((
        Triple(Variable("P"), nn("age"), Variable("A")),
        Triple(Variable("A"), adult_pred, lit_int(17)),
    )),
    head=Formula((
        Triple(Variable("P"), nn("isAdult"), Literal("true", datatype=NamedNode(XSD + "boolean"))),
    )),
))

engine.run()

print("Derived triples:")
for t in engine.derived_triples:
    print(" ", t)

print(f"Steps: {engine.step_count}")


# ---------------------------------------------------------------------------
# Example 2: Parse N3 then use Engine directly
# ---------------------------------------------------------------------------
print("\n=== Parse N3 then Engine ===")

n3_text = """
@prefix : <http://example.org/> .
@prefix math: <http://www.w3.org/2000/10/swap/math#> .

:widget  :price 120 .
:gadget  :price 45 .
:doohick :price 300 .

{ ?Item :price ?P . ?P math:greaterThan 99 } => { ?Item :premium true } .
{ ?Item :price ?P . ?P math:lessThan 100 }   => { ?Item :budget true } .
"""

engine2 = Engine()
doc = parse_n3(n3_text)
for triple in doc.triples:
    engine2.add_triple(triple)
for rule in doc.rules:
    engine2.add_rule(rule)
engine2.run()

# Serialize output using N3Writer
writer = N3Writer()
print(writer.write_triples(engine2.derived_triples))


# ---------------------------------------------------------------------------
# Example 3: Query the store directly
# ---------------------------------------------------------------------------
print("=== Direct Store Queries ===")

# Match all :price triples
price_pred = nn("price")
print("All prices:")
for t in engine2.store.match(predicate=price_pred):
    print(f"  {t.subject.value.split('/')[-1]} → {t.object.value}")

# Count triples
print(f"Total triples in store: {len(engine2.store)}")
print(f"Derived triples: {len(engine2.derived_triples)}")

# Check specific triple existence
widget_premium = Triple(nn("widget"), nn("premium"),
                         Literal("true", datatype=NamedNode(XSD + "boolean")))
print(f"widget :premium true in store: {engine2.store.contains(widget_premium)}")


# ---------------------------------------------------------------------------
# Example 4: Backward chaining via Engine.backward_chain()
# ---------------------------------------------------------------------------
print("\n=== Backward Chain Query ===")

bc_text = """
@prefix : <http://example.org/bc#> .
@prefix log: <http://www.w3.org/2000/10/swap/log#> .

[] log:table :reachable .

:a :link :b .
:b :link :c .
:c :link :d .

{ ?X :reachable ?Y } <= { ?X :link ?Y } .
{ ?X :reachable ?Y } <= { ?X :reachable ?Z . ?Z :reachable ?Y } .
"""

engine3 = Engine()
doc3 = parse_n3(bc_text)
for t in doc3.triples:
    engine3.add_triple(t)
for r in doc3.rules:
    engine3.add_rule(r)
engine3.run()

query = Triple(
    NamedNode("http://example.org/bc#a"),
    NamedNode("http://example.org/bc#reachable"),
    Variable("Dest"),
)
answers = engine3.backward_chain(query)
print("From :a, reachable:")
for binding in answers:
    dest = binding.get("Dest", binding.get(next(iter(binding))))
    print(" ", dest)
