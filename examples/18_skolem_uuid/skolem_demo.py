"""
18 — Skolem & UUID: Generating Identifiers
===========================================
When rules need to create new resources (not just assert properties of
existing ones), they need fresh, unique identifiers.

Two mechanisms:
  - log:skolem  — deterministic: same inputs → same blank node identifier
                  Useful for normalizing / deduplicating derived resources.
  - log:uuid    — non-deterministic: always fresh UUID.
                  WARNING: Do NOT use in forward-chaining rule bodies — each
                  iteration generates new UUIDs → new triples → no fixpoint.
                  Use log:uuid from Python (uuid module) and inject IDs as facts.

Syntax:
    (?arg1 ?arg2 ...) log:skolem ?BNode
    _:x log:uuid ?StringUUID

Use cases:
  - Materializing intermediate entities (e.g. a "relationship" node)
  - Canonical resource IDs from composite keys
  - Generating event/transaction identifiers
"""

from pyeye import execute

# Example 1: Materialize a "works-at" relationship node
# (subject + object → deterministic node for the relationship itself)
print("=== Materialized Relationship Nodes (log:skolem) ===")

data = """
@prefix hr:  <http://example.org/hr#> .
@prefix org: <http://example.org/org#> .

hr:alice  org:worksAt org:acme .
hr:bob    org:worksAt org:acme .
hr:carol  org:worksAt org:bigcorp .
"""

rules = """
@prefix hr:  <http://example.org/hr#> .
@prefix org: <http://example.org/org#> .
@prefix log: <http://www.w3.org/2000/10/swap/log#> .

# Create a unique Employment node for each (person, company) pair
{
    ?P org:worksAt ?C .
    (?P ?C) log:skolem ?Employment
}
    => {
        ?Employment a org:Employment .
        ?Employment org:employee ?P .
        ?Employment org:employer ?C .
    } .
"""

result = execute(data_strings=[data], rule_strings=[rules])
print(result.triples)
# Note: same person + company always generates the same skolem node


# Example 2: Idempotency — same input → same identifier
print("\n=== Idempotency of log:skolem ===")

data2 = """
@prefix : <http://example.org/> .

:alice :speaks :english .
:alice :speaks :french .
:bob   :speaks :english .
"""

rules2 = """
@prefix : <http://example.org/> .
@prefix log: <http://www.w3.org/2000/10/swap/log#> .

# Give each (person, language) pair a stable ID
{
    ?P :speaks ?L .
    (?P ?L) log:skolem ?SkillNode
}
    => {
        ?SkillNode a :LanguageSkill .
        ?SkillNode :person ?P .
        ?SkillNode :language ?L .
    } .
"""

result2 = execute(data_strings=[data2], rule_strings=[rules2])
print(result2.triples)


# Example 3: UUID generation via log:uuid
# NOTE: log:uuid is NON-DETERMINISTIC — each call returns a fresh UUID.
# This means forward-chaining rules containing log:uuid will NEVER reach
# fixpoint (each iteration generates new unique triples).
#
# The correct patterns are:
#   a) Use log:uuid in a backward-chaining context (query-time, one result)
#   b) Use log:uuid from Python via engine.add_triple() to mint IDs before reasoning
#   c) Use log:skolem for stable (deterministic) IDs instead

print("\n=== log:uuid: Correct Usage Patterns ===")

# Pattern A: Generate UUIDs in Python, inject as facts, then reason over them
import uuid as _uuid
from pyeye import execute, NamedNode, Literal, Triple
from pyeye.engine import Engine
from pyeye.parser import parse_n3

AUDIT = "http://example.org/audit#"
XSD   = "http://www.w3.org/2001/XMLSchema#"

events = [
    ("req1", "alice", "view-report"),
    ("req2", "bob",   "edit-record"),
]

engine = Engine()
for req_id, user, action in events:
    event_uuid = str(_uuid.uuid4())
    req   = NamedNode(AUDIT + req_id)
    pred_user   = NamedNode(AUDIT + "user")
    pred_action = NamedNode(AUDIT + "action")
    pred_evid   = NamedNode(AUDIT + "eventId")
    engine.add_triple(Triple(req, pred_user,   NamedNode(AUDIT + user)))
    engine.add_triple(Triple(req, pred_action, Literal(action)))
    engine.add_triple(Triple(req, pred_evid,   Literal(event_uuid)))

# Now add enrichment rules
rules3 = """
@prefix audit: <http://example.org/audit#> .
{ ?Req audit:action "view-report" } => { ?Req audit:severity "low" } .
{ ?Req audit:action "edit-record" } => { ?Req audit:severity "high" } .
"""
doc = parse_n3(rules3)
for rule in doc.rules:
    engine.add_rule(rule)
engine.run()

print("Audit events with UUIDs (minted in Python, enriched by rules):")
for t in engine.store.match():
    s = t.subject.value.split("#")[-1]
    p = t.predicate.value.split("#")[-1]
    o = t.object.value if hasattr(t.object, "value") else str(t.object)
    print(f"  {s}  {p}  {o!r}")
