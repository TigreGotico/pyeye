"""
22 — Incremental Reasoning
===========================
pyeye's ``Engine.add_triple()`` triggers incremental re-derivation: when
a new fact is added after ``run()`` has already been called, the engine
immediately checks which rules might fire for the new fact and derives
any new conclusions, without re-processing the entire store.

This makes the Engine suitable for streaming or live-update scenarios:
  - IoT sensor streams (each reading → new triple → new inferences)
  - Event-driven systems (each event fact → trigger rules)
  - Interactive knowledge base building

The key property: ``engine.derived_triples`` always reflects the complete
closure over all facts added so far.
"""

from pyeye.engine import Engine
from pyeye.parser import parse_n3
from pyeye.term import NamedNode, Literal, Triple
from pyeye.output import N3Writer

# ---------------------------------------------------------------------------
# Setup: define rules once, add facts incrementally
# ---------------------------------------------------------------------------

rules_n3 = """
@prefix sensor: <http://example.org/sensor#> .
@prefix math:   <http://www.w3.org/2000/10/swap/math#> .

# Classification rules
{ ?Reading sensor:temp ?T . ?T math:greaterThan 29 }
    => { ?Reading sensor:level "HOT" } .

{ ?Reading sensor:temp ?T . ?T math:lessThan 10 }
    => { ?Reading sensor:level "COLD" } .

{ ?Reading sensor:temp ?T .
  ?T math:greaterThan 9 .
  ?T math:lessThan 30 }
    => { ?Reading sensor:level "NORMAL" } .

# Alert if hot
{ ?R sensor:level "HOT" . ?R sensor:room ?Room }
    => { ?Room sensor:alert "TEMPERATURE_HIGH" } .
"""

engine = Engine()
doc = parse_n3(rules_n3)
for rule in doc.rules:
    engine.add_rule(rule)

print("=== Live Sensor Stream ===\n")

# Simulate incoming sensor readings
readings = [
    ("reading_001", "room_A", 22),
    ("reading_002", "room_B", 35),   # HOT
    ("reading_003", "room_A", 8),    # COLD
    ("reading_004", "room_B", 25),
    ("reading_005", "room_C", 31),   # HOT
]

SENSOR = "http://example.org/sensor#"
def nn(local: str) -> NamedNode:
    return NamedNode(SENSOR + local)

prev_derived = 0

for reading_id, room_id, temp_val in readings:
    reading = nn(reading_id)
    room    = nn(room_id)
    temp    = Literal(str(temp_val), datatype=NamedNode("http://www.w3.org/2001/XMLSchema#integer"))

    engine.add_triple(Triple(reading, nn("room"), room))
    engine.add_triple(Triple(reading, nn("temp"), temp))
    engine.run()

    new_count = len(engine.derived_triples)
    new_triples = engine.derived_triples[prev_derived:]
    prev_derived = new_count

    print(f"[{reading_id}] room={room_id} temp={temp_val}°C → {len(new_triples)} new derivation(s):")
    for t in new_triples:
        subj = t.subject.value.split("#")[-1]
        pred = t.predicate.value.split("#")[-1]
        obj  = t.object.value if hasattr(t.object, "value") else str(t.object)
        print(f"   {subj} {pred} {obj!r}")
    print()


# Final summary
print("=== Final Derived State ===")
alert_pred = nn("alert")
print("Active alerts:")
for t in engine.store.match(predicate=alert_pred):
    room = t.subject.value.split("#")[-1]
    print(f"  {room}: {t.object.value}")


# ---------------------------------------------------------------------------
# Example 2: Knowledge base building — add concepts one at a time
# ---------------------------------------------------------------------------
print("\n=== Knowledge Base Building ===")

kb_rules = """
@prefix : <http://example.org/kb#> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

# Transitive subClassOf
{ ?A rdfs:subClassOf ?B . ?B rdfs:subClassOf ?C } => { ?A rdfs:subClassOf ?C } .

# Type propagation
{ ?X a ?A . ?A rdfs:subClassOf ?B } => { ?X a ?B } .
"""

engine2 = Engine()
doc2 = parse_n3(kb_rules)
for rule in doc2.rules:
    engine2.add_rule(rule)

BASE = "http://example.org/kb#"
RDFS = "http://www.w3.org/2000/01/rdf-schema#"
RDF  = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"

subClassOf = NamedNode(RDFS + "subClassOf")
rdf_type   = NamedNode(RDF  + "type")

def concept(name): return NamedNode(BASE + name)

# Add hierarchy step by step
print("Step 1: GoldenRetriever ⊆ Dog")
engine2.add_triple(Triple(concept("GoldenRetriever"), subClassOf, concept("Dog")))
engine2.run()
print(f"  Derived: {len(engine2.derived_triples)} triples")

print("Step 2: Dog ⊆ Mammal")
engine2.add_triple(Triple(concept("Dog"), subClassOf, concept("Mammal")))
engine2.run()
print(f"  Derived: {len(engine2.derived_triples)} triples (now GoldenRetriever ⊆ Mammal too)")

print("Step 3: Mammal ⊆ Animal")
engine2.add_triple(Triple(concept("Mammal"), subClassOf, concept("Animal")))
engine2.run()
print(f"  Derived: {len(engine2.derived_triples)} triples")

print("Step 4: Add instance :rex a GoldenRetriever")
engine2.add_triple(Triple(concept("rex"), rdf_type, concept("GoldenRetriever")))
engine2.run()
print(f"  Derived: {len(engine2.derived_triples)} triples (rex is also Dog, Mammal, Animal)")

print("\nAll types of rex:")
for t in engine2.store.match(subject=concept("rex"), predicate=rdf_type):
    print(" ", t.object.value.split("#")[-1])
