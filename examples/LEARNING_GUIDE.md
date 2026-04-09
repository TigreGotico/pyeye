# pyeye Learning Guide

Structured learning paths for three audiences. Each path builds on the previous one.

---

## Audience 1 — Beginner

**Goal:** Understand what pyeye does and be productive with forward chaining.

### Step 1 — Mental Model

pyeye is a **rule engine** for RDF data. You give it:
- **Facts** (N3/Turtle triples: subject predicate object)
- **Rules** (`{ body } => { head }`)

It derives all consequences by forward chaining until no new triples are produced.

Think of it like a spreadsheet that automatically fills in all cells that can be
computed from formulas, except the formulas can match any pattern in the data.

### Step 2 — Run Example 01

```bash
python examples/01_hello_world/hello.py
```

Understand:
- `execute()` is your main function
- `data_strings` holds facts
- `rule_strings` holds rules
- `result.triples` is the N3-serialized output

### Step 3 — Transitive Closure (Example 02)

The family tree example shows how a single recursive rule, applied repeatedly,
derives arbitrarily long chains of facts. This is the power of forward chaining.

Key insight: rules fire until fixpoint (no new triples). The engine handles
the loop — you just declare the relationship.

### Step 4 — Math and String Builtins (Examples 03, 04)

Two syntax patterns to know:

**Filter** (comparison — no output):
```n3
{ ?V math:greaterThan 99 }  # true/false check, no binding
```

**Computation** (list + output variable):
```n3
{ (?A ?B) math:product ?C }  # binds ?C to A×B
```

String concatenation always takes a list:
```n3
{ (?F " " ?L) string:concatenation ?Full }
```

### Step 5 — Backward Chaining (Example 08)

When you only need to answer a specific question (not derive everything),
use a `query=Triple(...)` argument. The engine searches backward from the goal.

Use `log:table` to prevent infinite recursion in recursive BC rules.

### Step 6 — Practice Project

Write rules to:
1. Define `siblingOf` from shared `parentOf`
2. Use `math:sum` to compute a total price for a shopping cart
3. Use `string:upperCase` to normalize a category name
4. Use a BC query to find all siblings of a specific person

---

## Audience 2 — Practitioner

**Goal:** Master the full `execute()` API, negation, aggregation, and real-world patterns.

### Step 1 — Entailment (Examples 06, 07)

`entail=True` activates built-in RDFS rules automatically. Use it when your data
has `rdfs:subClassOf` or `rdfs:domain`/`rdfs:range` and you want the engine to
reason over those.

`entail_owl=True` adds OWL 2 RL on top: `owl:inverseOf`, `owl:SymmetricProperty`,
`owl:sameAs`, etc.

`pass_mode=True` includes the original input facts in `result.triples` (useful
when you want both original + derived in one serialization).

### Step 2 — Negation as Failure (Examples 09, 24)

`log:onNegativeSurface` says "fire this rule only if the nested formula is NOT derivable."

```n3
{ _:neg log:onNegativeSurface { ?S :hasOverride ?V } . ?S :default ?D }
    => { ?S :effective ?D } .
```

**Critical rules:**
- Each `_:neg` blank node is syntactically required (not optional)
- Multiple negations in one rule need distinct blank nodes (`_:n1`, `_:n2`, ...)
- Negation is checked **per binding**, not globally

Use example 24 (config management) as a template for priority-based defaults.

### Step 3 — Aggregation (Examples 10, 19)

`log:collectAllIn` is the aggregation primitive:

```n3
{ ?G :salaries ?L .
  ?L log:collectAllIn { ?E :dept ?G . ?E :salary ?S } ?S .
  ?L math:sum ?Total .
  ?L list:length ?N .
  (?Total ?N) math:quotient ?Avg }
    => { ?G :avgSalary ?Avg } .
```

The blank node `?L` is the list that collects all `?S` values. Then standard
`math:` and `list:` builtins operate on it.

### Step 4 — Proof Traces (Example 11)

Use `explain=True` during development to understand why a triple was (or wasn't) derived:

```python
result = execute(..., explain=True)
# Open in browser:
with open("proof.html", "w") as f: f.write(result.proof_html)
```

### Step 5 — Named Graphs (Example 12)

TriG-format input with `GRAPH <iri> { ... }` blocks lets you reason over
multiple named datasets. Rules can be scoped per-graph or cross-graph.

### Step 6 — Custom Builtins (Example 13)

Extend the engine with domain functions. The protocol:

```python
def my_fn(args: list[Term], engine) -> Term | None:
    # args[:-1] = input args, args[-1] = output Variable (engine-appended)
    # Return None to skip (inputs unbound or computation failed)
    # Return a Term to bind the output variable
    ...
```

Register at `execute()` time: `builtins={"http://my.org/fn#myFn": my_fn}`.

### Step 7 — Real-World Pattern: Config Management

Study example 24 carefully. It shows the canonical pattern for:
- Layered configuration (high-priority overrides low-priority)
- Validation rules that flag invalid combinations
- Multiple negation conditions chained together

### Step 8 — Real-World Pattern: RBAC

Study example 25. It shows:
- Role hierarchy (transitive)
- Permission inheritance
- Explicit deny overriding any grant
- Backward-chaining for access queries

### Practice Projects

1. **Inventory system**: Track stock levels, fire alerts when below threshold,
   compute reorder quantities with math builtins
2. **Scheduling**: Given tasks with dependencies, derive execution order using
   transitive `dependsOn` and negation-based "ready" check
3. **Data quality**: Flag records with missing fields using `log:onNegativeSurface`

---

## Audience 3 — Advanced

**Goal:** Use the Engine API directly, integrate with streaming systems,
build production-grade reasoning pipelines.

### Step 1 — Direct Engine API (Example 21)

`execute()` is a convenience wrapper. The `Engine` class gives full control:

```python
from pyeye.engine import Engine
from pyeye.parser import parse_n3, Rule
from pyeye.term import NamedNode, Literal, Variable, Triple, Formula

engine = Engine(
    max_steps=100_000,
    timeout_seconds=120.0,
)
```

Build rules programmatically (no N3 parsing):
```python
from pyeye.parser import Rule
engine.add_rule(Rule(
    body=Formula((Triple(Variable("P"), pred_age, Variable("A")),
                  Triple(Variable("A"), math_gte, lit_int(18)))),
    head=Formula((Triple(Variable("P"), pred_adult, lit_bool(True)),)),
))
```

### Step 2 — Incremental Reasoning (Example 22)

The engine is designed for incremental use:

```python
engine.add_triple(new_fact)  # add one fact
engine.run()                 # re-derive only what's new
```

This is efficient for streaming pipelines: each new fact triggers only the
rules that could fire for it, not a full re-derivation from scratch.

**Sensor stream pattern:**
```python
prev = 0
for event in stream:
    engine.add_triple(event_triple(event))
    engine.run()
    new = engine.derived_triples[prev:]
    prev = len(engine.derived_triples)
    handle(new)
```

### Step 3 — Store Queries

The internal `TripleStore` supports pattern matching:

```python
# Match all triples with a specific predicate
for t in engine.store.match(predicate=pred_iri):
    ...

# Match subject + predicate
for t in engine.store.match(subject=subj_iri, predicate=pred_iri):
    ...

# Check existence
engine.store.contains(triple)

# Count
len(engine.store)
```

### Step 4 — Knowledge Graph Pipeline (Example 23)

pyeye fits naturally as the "reasoning layer" between raw data ingestion and
application queries:

```
Raw data → N3 facts → pyeye Engine → enriched triples → application
```

The engine adds implicit knowledge (type inheritance, compatibility links,
derived classifications) that would otherwise require manual curation or
imperative code.

### Step 5 — Production Considerations

**Timeout strategy:**
- Default: `timeout_seconds=30.0`
- For complex ontologies: `timeout_seconds=120.0`
- For streaming/incremental: `timeout_seconds=5.0` per `run()` call
- For unit tests: `timeout_seconds=10.0`

**Step limit vs. timeout:**
- `max_steps` counts forward-chaining iterations (rules fired)
- `timeout_seconds` uses wall-clock time
- Use `max_steps` for reproducible limits; `timeout_seconds` for interactive safety

**Memory:**
- `engine.derived_triples` grows monotonically — clear the engine and rebuild
  periodically for long-running streams
- Use `engine.store.match()` queries instead of serializing all triples when
  you only need specific facts

**Custom builtins performance:**
- Keep builtins side-effect-free and fast (they may fire hundreds of times)
- Cache expensive computations (network calls, heavy crypto) outside the engine
- Use `args[:N]` (not `_unground(args)`) to check input groundedness

### Step 6 — Builtin Bug Pattern

The most common pitfall when writing custom builtins:

```python
# WRONG: _unground(args) includes the output Variable appended by engine
def my_fn(args, engine):
    if _unground(args): return None  # BUG: always None in rules!

# RIGHT: check only input args
def my_fn(args, engine):
    if _unground(args[:1]): return None  # OK: only checks input
```

The engine appends the output Variable as the last element of `args` before
calling your function. Only the input slots need to be ground.

### Step 7 — Debugging Derivation Failures

If a rule fires in isolation but not in `execute()`:

1. Check that the rule body is satisfiable with the data
2. Add `explain=True` and read the proof trace
3. Test builtins with raw args: `my_fn([Literal("val"), Variable("Out")], None)`
4. Check abbreviated vs full IRI in output parsing
5. Check negation blank node uniqueness

### Practice Projects

1. **Event-driven alerting**: Streaming sensor data → incremental reasoning → alert rules
2. **Ontology-driven API**: Accept user queries as backward-chaining goals, return derived facts
3. **Policy engine**: RBAC + attribute-based access control using negation and aggregation
4. **Data lineage**: Track provenance of derived facts using named graphs and proof traces
5. **ETL enrichment**: Load raw data, apply domain rules, serialize enriched N3 for downstream

---

## Reference: Predicate Namespaces

| Prefix | URI | Purpose |
|--------|-----|---------|
| `math:` | `http://www.w3.org/2000/10/swap/math#` | Arithmetic, comparison |
| `string:` | `http://www.w3.org/2000/10/swap/string#` | String operations |
| `list:` | `http://www.w3.org/2000/10/swap/list#` | RDF list operations |
| `log:` | `http://www.w3.org/2000/10/swap/log#` | Logic, negation, aggregation |
| `time:` | `http://www.w3.org/2000/10/swap/time#` | Date/time |
| `crypto:` | `http://www.w3.org/2000/10/swap/crypto#` | SHA-256, MD5 |
| `rdfs:` | `http://www.w3.org/2000/01/rdf-schema#` | RDFS vocabulary |
| `owl:` | `http://www.w3.org/2002/07/owl#` | OWL vocabulary |
| `xsd:` | `http://www.w3.org/2001/XMLSchema#` | Datatypes |
