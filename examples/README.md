# pyeye Examples — Tutorial Progression

A step-by-step tour of pyeye's N3 reasoning capabilities, from "Hello World" to
production-grade RBAC engines. Each example is self-contained — run any `.py` directly.

---

## Quick Start

```bash
cd /path/to/pyeye
pip install -e .
python examples/01_hello_world/hello.py
```

Run the whole suite:

```bash
for f in examples/*/; do echo "=== $f ==="; python "$f"/*.py; done
```

Python 3.11+ required.

---

## Example Index

| # | Directory | Topic | Key APIs / Concepts |
|---|-----------|-------|---------------------|
| 01 | `01_hello_world` | First inference | `execute()`, `data_strings`, `rule_strings`, `=>` |
| 02 | `02_family_tree` | Multi-hop reasoning | Chain rules, multi-triple bodies, transitive closure |
| 03 | `03_math_builtins` | Arithmetic & comparisons | `math:product`, `math:greaterThan`, list-arg syntax |
| 04 | `04_string_builtins` | Text manipulation | `string:concatenation`, `string:upperCase`, `string:matches` |
| 05 | `05_list_builtins` | RDF list operations | `list:length`, `list:in`, `list:select` |
| 06 | `06_rdfs_entailment` | Class hierarchies | `entail=True`, `rdfs:subClassOf`, domain/range |
| 07 | `07_owl_entailment` | OWL 2 RL properties | `entail_owl=True`, `owl:inverseOf`, `owl:sameAs` |
| 08 | `08_backward_chaining` | Goal-directed proof | `query=Triple(...)`, `log:table`, `<=` rules |
| 09 | `09_negation` | Negation as failure | `log:onNegativeSurface`, closed-world assumption |
| 10 | `10_aggregation` | Collect & count | `log:collectAllIn`, `log:forAllIn`, `list:length` |
| 11 | `11_proof_traces` | Explain derivations | `explain=True`, HTML/DOT/N3 proof output |
| 12 | `12_named_graphs` | Multiple graph contexts | TriG `GRAPH {}`, quad store, named-graph scoping |
| 13 | `13_custom_builtins` | Extend the engine | `builtins={}`, custom `fn(args, engine)` protocol |
| 14 | `14_routing_problem` | Real-world graph search | Transitive closure, route planning, `math:sum` |
| 15 | `15_peano_arithmetic` | Recursive arithmetic | Deep backward chaining, tabling, `ReasoningTimeoutError` |
| 16 | `16_crypto_builtins` | Content hashing | `crypto:sha256`, `crypto:md5`, duplicate detection |
| 17 | `17_time_builtins` | Date & time reasoning | `time:now`, `time:year`, `time:month`, `time:hour` |
| 18 | `18_skolem_uuid` | Identifier generation | `log:skolem` (deterministic), UUID via Python |
| 19 | `19_math_statistics` | Aggregate statistics | `log:collectAllIn` + `math:` for avg/min/max |
| 20 | `20_uri_typed_literals` | IRIs & typed data | `log:localName`, `log:namespace`, `log:dtlit` |
| 21 | `21_engine_api` | Direct Engine API | `Engine`, `add_triple`, `add_rule`, `backward_chain` |
| 22 | `22_incremental_reasoning` | Streaming / live updates | `engine.add_triple()` post-run, `derived_triples` |
| 23 | `23_knowledge_graph` | KG enrichment pipeline | Category hierarchy, price tiers, same-brand compat |
| 24 | `24_config_management` | Layered configuration | `log:onNegativeSurface` priority, config validation |
| 25 | `25_rbac_permissions` | Role-based access control | Role hierarchy, permission inheritance, deny override |
| 26 | `26_temporal_reasoning` | Temporal reasoning | Meeting conflict detection, business-hours checks, integer timestamps |
| 27 | `27_cycle_detection` | Graph cycle detection | Transitive closure, self-reachability, acyclic/cyclic classification |
| 28 | `28_constraint_validation` | SHACL-like constraint validation | Required properties, cardinality, value-range constraints, violation reports |
| 29 | `29_state_machine` | Workflow state machine | Allowed transitions, invalid-transition detection, terminal states |
| 30 | `30_belief_revision` | Multi-source belief revision | Confidence-weighted sensor fusion, conflict detection, max-confidence winner |
| 31 | `31_provenance_tracking` | Provenance tracking | Multi-source data integration, derivation tagging, conflict detection |
| 32 | `32_decision_scoring` | Multi-criteria scoring | Weighted composite score, tier assignment (approve/review/reject) |
| 33 | `33_ontology_mapping` | Ontology mapping | schema.org ↔ local vocab, bidirectional bridge rules, cross-vocabulary queries |
| 34 | `34_bill_of_materials` | Recursive BOM roll-up | Transitive part-of, collectAllIn sum, weight/cost propagation |
| 35 | `35_event_correlation` | Complex event processing | Burst detection, time-window correlation, multi-stage alert derivation |

---

## Learning Paths

### Beginner (01–05, 08)
Core reasoning, builtins, and querying. Covers 90% of everyday use.

### Practitioner (06–15)
Entailment, negation, aggregation, proofs, graphs, custom extensions, real-world problems.

### Advanced (16–25)
Crypto/time/URI builtins, programmatic engine, incremental reasoning, knowledge graph
pipelines, config engines, and RBAC policy engines.

---

## Example Walkthroughs

### 01 — Hello World

The minimal pyeye program: one fact, one rule, one derived triple.

```python
from pyeye import execute

result = execute(
    data_strings=["@prefix : <http://example.org/> . :sky :colour :blue ."],
    rule_strings=["@prefix : <http://example.org/> . { :sky :colour :blue } => { :sky :isColoured :blue } ."],
)
print(result.triples)
```

**Key concepts:** `execute()` is the main entry point. `data_strings` holds facts,
`rule_strings` holds `{ body } => { head }` rules.

---

### 02 — Family Tree

Demonstrates multi-hop transitive closure with recursive rules:

```n3
{ ?X fam:parent ?Y . ?Y fam:ancestor ?Z } => { ?X fam:ancestor ?Z } .
```

Two rules fire repeatedly until no new triples are derived (forward-chaining fixpoint).

---

### 03 — Math Builtins

Binary math operations use **list syntax**: `(?A ?B) math:product ?C`.
Filter comparisons bind nothing: `?V math:greaterThan 99`.

```n3
{ ?Item :price ?P . ?P math:greaterThan 99 } => { ?Item :premium true } .
{ ?Item :price ?P . (?P 0.9) math:product ?Sale } => { ?Item :salePrice ?Sale } .
```

---

### 04 — String Builtins

```n3
{ ?P :first ?F . ?P :last ?L . (?F " " ?L) string:concatenation ?Full }
    => { ?P :fullName ?Full } .
```

`string:concatenation` takes a **list** of strings and joins them.
Pattern matching: `?S string:matches "^python"` (a filter — passes or fails).

---

### 05 — List Builtins

`list:in` is a **filter** — both item and list must be bound (`?item list:in ?list`):

```n3
{ ?U :role ?R . ?R list:in (:admin :editor) } => { ?U :hasAccess true } .
```

`list:member` enumerates: `?list list:member ?item` yields one binding per element.
`list:select` is **1-based**: `(?list 1) list:select ?first`.
`list:length` counts elements: `?list list:length ?n`.

---

### 06 — RDFS Entailment

Pass `entail=True` to apply the RDFS entailment rules before user rules. The
entailed triples land in the store (available to your rules); add
`pass_mode=True` to see them in the output alongside the input facts.

```python
result = execute(data_strings=[rdfs_data], entail=True, pass_mode=True)
```

Built-in RDFS rules handle `rdfs:subClassOf`, `rdfs:subPropertyOf`, `rdfs:domain`,
and `rdfs:range` automatically.

---

### 07 — OWL 2 RL Entailment

`entail_owl=True` adds OWL 2 RL rules on top of RDFS: `owl:inverseOf`,
`owl:SymmetricProperty`, `owl:TransitiveProperty`, `owl:sameAs`, and more.

---

### 08 — Backward Chaining

Forward chaining derives all consequences; backward chaining answers a specific question:

```python
result = execute(
    data_strings=[data],
    rule_strings=[rules],
    query=Triple(NamedNode("...alice"), NamedNode("...reachable"), Variable("Dest")),
)
for binding in result.query_answers:
    print(binding["Dest"])
```

`log:table` memoizes predicates to prevent infinite recursion in BC mode:
```n3
[] log:table :reachable .
```

---

### 09 — Negation

`log:onNegativeSurface` implements negation-as-failure (closed-world assumption):

```n3
{ ?Svc cfg:env ?Env .
  _:neg log:onNegativeSurface { ?Svc cfg:timeout ?Any } .
  ?Env cfg:timeout ?V }
    => { ?Svc cfg:effective_timeout ?V } .
```

The blank node `_:neg` is syntactically required. The enclosed formula must
**not** be derivable for the rule to fire. Each candidate binding is checked
individually.

---

### 10 — Aggregation

`log:collectAllIn` gathers all values matching a pattern into an RDF list. The subject is `(?Template { pattern } ?OutputList)`; the object must be a fresh scope variable:

```n3
{ ?Dept a :Department .
  (?S { ?E :dept ?Dept . ?E :salary ?S } ?Sals) log:collectAllIn ?Scope .
  ?Sals math:sum ?Total }
    => { ?Dept :totalSalary ?Total } .
```

---

### 11 — Proof Traces

```python
result = execute(..., explain=True, explain_format="html")
print(result.explains)     # browser-viewable proof tree (or "dot" / "n3")
```

---

### 12 — Named Graphs

Use TriG-style input with `GRAPH <iri> { ... }` blocks. Rules can scope to specific
graphs using `log:graph` or cross-graph inference.

---

### 13 — Custom Builtins

Register domain-specific functions as N3 builtins:

```python
def my_builtin(args: list[Term], engine) -> Term | None:
    if not all(not isinstance(a, Variable) for a in args[:-1]):
        return None  # inputs unbound — skip
    return Literal(str(compute(args[0])))

result = execute(..., builtins={"http://example.org/fn#myFunc": my_builtin})
```

The engine passes all arguments (including the output variable) as `args`.
Check that **input** args are ground; return the output value.

---

### 14 — Routing Problem

Multi-hop graph traversal:

```n3
{ ?X flight:directTo ?Y } => { ?X flight:canReach ?Y } .
{ ?X flight:canReach ?Y . ?Y flight:canReach ?Z } => { ?X flight:canReach ?Z } .
```

Demonstrates how forward chaining naturally computes transitive closure over
route graphs without explicit iteration, plus a backward-chaining query and a
not-entail check.

---

### 15 — Peano Arithmetic

Backward-chaining-only rules (`<=`) for recursive addition. Shows `log:table`
for tabling and `ReasoningTimeoutError` when a rule creates an infinite loop:

```python
from pyeye import execute, ReasoningTimeoutError

try:
    result = execute(..., timeout_seconds=5.0)
except ReasoningTimeoutError as e:
    print(f"Caught: {e}")
```

Default timeout is 30 seconds. Pass `timeout_seconds=None` to disable.

---

### 16 — Crypto Builtins

Hash content with `crypto:sha256` or `crypto:md5` for fingerprinting and
duplicate detection:

```n3
{ ?Doc :content ?C . ?C crypto:sha256 ?Hash }
    => { ?Doc :fingerprint ?Hash } .

{ ?A :fingerprint ?H . ?B :fingerprint ?H . ?A log:notEqualTo ?B }
    => { ?A :duplicateOf ?B } .
```

---

### 17 — Time Builtins

`time:now` generates the current timestamp:
```n3
{ ?Event :action ?A . _:t time:now ?Now } => { ?Event :processedAt ?Now } .
```

Component extraction: `?DT time:year ?Y`, `time:month`, `time:day`, `time:hour`,
`time:minute`, `time:second`.

---

### 18 — Skolem & UUID

`log:skolem` creates **deterministic** blank nodes from a list of inputs —
same inputs always produce the same node:

```n3
{ ?P org:worksAt ?C . (?P ?C) log:skolem ?Employment }
    => { ?Employment a org:Employment ; org:employee ?P ; org:employer ?C } .
```

**Important:** Do NOT use `log:uuid` in forward-chaining rule bodies. It is
non-deterministic, so the engine never reaches fixpoint. Generate UUIDs in
Python and inject them as facts before reasoning:

```python
import uuid
engine.add_triple(Triple(req, pred_eventId, Literal(str(uuid.uuid4()))))
```

---

### 19 — Math Statistics

Combine `log:collectAllIn` with `math:sum`, `math:min`, `math:max`, and division
for aggregate statistics:

```n3
{ ?Dept a :Department .
  (?S { ?E :dept ?Dept . ?E :salary ?S } ?L) log:collectAllIn ?Scope .
  ?L math:sum ?Total . ?L list:length ?N .
  (?Total ?N) math:quotient ?Avg }
    => { ?Dept :avgSalary ?Avg } .
```

---

### 20 — URI & Typed Literals

Extract parts of IRIs with `log:localName` (fragment/path segment) and
`log:namespace` (everything before the local name).

Create typed literals with `log:dtlit`:
```n3
{ ?P :rawScore ?V . (?V "http://www.w3.org/2001/XMLSchema#integer") log:dtlit ?Typed }
    => { ?P :score ?Typed } .
```

---

### 21 — Direct Engine API

Use `Engine` directly for fine-grained control:

```python
from pyeye.engine import Engine
from pyeye.parser import parse_n3

engine = Engine(timeout_seconds=60.0)
doc = parse_n3(n3_text)
for triple in doc.triples: engine.add_triple(triple)
for rule in doc.rules:     engine.add_rule(rule)
engine.run()

# Query
for t in engine.store.match(predicate=NamedNode("...")):
    print(t)

# Serialize
from pyeye.output import N3Writer
print(N3Writer().write_triples(engine.derived_triples))
```

---

### 22 — Incremental Reasoning

Add facts one at a time after the engine has already run:

```python
engine.add_triple(Triple(sensor, pred_temp, Literal("35", datatype=xsd_int)))
engine.run()  # only processes new facts; existing derivations reused
new = engine.derived_triples[prev_count:]
```

Ideal for IoT streams, event-driven systems, and live knowledge base building.

---

### 23 — Knowledge Graph Enrichment

Use pyeye as a reasoning layer over a product catalogue:

- Category hierarchy via transitive `rdfs:subClassOf`
- Price tiers with `math:greaterThan` / `math:lessThan`
- Same-brand compatibility via `log:notEqualTo`
- Cross-OS labels, form factors

---

### 24 — Configuration Management

Layered config (service > environment > global defaults) using
`log:onNegativeSurface` for "use default only if no override exists":

```n3
{   ?Svc cfg:env ?Env .
    _:n1 log:onNegativeSurface { ?Svc cfg:timeout ?Any } .
    _:n2 log:onNegativeSurface { ?Env cfg:timeout ?Any } .
    cfg:defaults cfg:timeout ?V }
    => { ?Svc cfg:effective_timeout ?V } .
```

Each negation blank node must be distinct (`_:n1`, `_:n2`).

---

### 25 — RBAC Permissions

Full role-based access control policy engine:

- Role hierarchy with transitive `rbac:inheritsFrom`
- Permission inheritance (roles acquire parent permissions)
- Resource access decisions from effective permissions
- Ownership grants unconditional access
- Explicit DENY overrides all grants via `log:onNegativeSurface`
- Backward-chaining query: "who can access this resource?"

---

## Key Patterns

### Rule with math output
```n3
{ ?A :x ?X . (?X 2) math:product ?Y } => { ?A :doubled ?Y } .
```

### Priority-based default (negation)
```n3
{ _:neg log:onNegativeSurface { ?S :specific ?V } . ?S :default ?V }
    => { ?S :effective ?V } .
```

### Aggregation
```n3
{ ?G a :Group .
  (?V { ?X :group ?G . ?X :value ?V } ?L) log:collectAllIn ?Scope .
  ?L list:length ?N } => { ?G :count ?N } .
```

### Backward-chaining query
```python
result = execute(..., query=Triple(Variable("Who"), NamedNode(PRED), NamedNode(OBJ)))
for b in result.query_answers:
    print(b["Who"].value)
```

### Custom builtin
```python
def fn(args, engine):
    if isinstance(args[0], Variable): return None  # unbound input
    return Literal(process(args[0].value))

execute(..., builtins={"http://my.org/fn#process": fn})
```

---

## Safety Notes

| Risk | Mitigation |
|------|------------|
| Infinite forward loops | 30s default timeout; `ReasoningTimeoutError` raised |
| `log:uuid` in rules | Never use in FC rules — use Python `uuid` module instead |
| Negation scope bugs | Each `_:neg` blank node must be unique per rule |
| Missing `list:select` element | 1-based indexing; returns `None` if out of range |

---

## Common Mistakes

**Wrong:** `?V math:times 0.9 ?Result`
**Right:** `(?V 0.9) math:product ?Result`

**Wrong:** `() log:uuid ?ID` in a rule body
**Right:** generate UUID in Python, inject as `add_triple()`

**Wrong:** `list:in` as generator (`?Item list:in :myList`)
**Right:** both args must be bound — it's a membership filter

**Wrong:** checking `if user_uri not in line` against abbreviated N3 output
**Right:** check for `rbac:user` (abbreviated form) or parse the full IRI

---

## Troubleshooting

See [`TROUBLESHOOTING.md`](TROUBLESHOOTING.md) for 20+ common problems and solutions.

See [`QUICK_REFERENCE.md`](QUICK_REFERENCE.md) for copy-paste code patterns.

See [`LEARNING_GUIDE.md`](LEARNING_GUIDE.md) for structured learning paths.
