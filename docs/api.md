# API Reference

Complete reference for pyeye's public Python API. Start with [Getting Started](getting-started.md) if you are new.

---

## Quick imports

```python
# High-level API (most common)
from pyeye import execute, NamedNode, Variable, Triple, Literal

# Direct engine access
from pyeye.engine import Engine, ReasoningTimeoutError
from pyeye.parser import parse_n3
from pyeye.output import N3Writer
from pyeye.term import Existential, Formula, TripleTerm, PathTerm, Quad
from pyeye.store import TripleStore
from pyeye.builtins import MultiResult, register_derive_function
```

---

## `execute()` — the main entry point

```python
from pyeye.entry import execute

result = execute(
    data_paths=None,
    data_strings=None,
    rule_paths=None,
    rule_strings=None,
    builtins=None,
    explain=False,
    max_steps=-1,
    limit_answers=-1,
    timeout_seconds=30.0,
    prefixes=None,
    nope=False,
    pass_mode=False,
    pass_all=False,
    djiti_debug=False,
    query=None,
    forward=True,
    entail=False,
    entail_owl=False,
    not_entail=None,
    cache_dir=None,
    explain_format="n3",
)
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `data_paths` | `list[str] \| None` | `None` | Paths to N3/Turtle data files. File paths and `http://`/`https://` URLs are both accepted. |
| `data_strings` | `list[str] \| None` | `None` | Inline N3/Turtle data strings. |
| `rule_paths` | `list[str] \| None` | `None` | Paths to N3 rule files (may also contain data triples). |
| `rule_strings` | `list[str] \| None` | `None` | Inline N3 rule strings. |
| `builtins` | `dict[str, Builtin] \| None` | `None` | Custom builtins merged with the default registry. Keys are full IRIs. |
| `explain` | `bool` | `False` | If `True`, collect proof trees for each derived triple. |
| `max_steps` | `int` | `-1` | Hard cap on forward-chaining rule firings. `-1` means unlimited. |
| `limit_answers` | `int` | `-1` | Stop after this many new derivations. `-1` means unlimited. |
| `timeout_seconds` | `float \| None` | `30.0` | Wall-clock deadline for forward chaining. Raises `ReasoningTimeoutError` if exceeded. `None` disables the guard. |
| `prefixes` | `dict[str, str] \| None` | `None` | Additional prefix mappings for output N3 serialization. |
| `nope` | `bool` | `False` | Skip all reasoning; just parse and return the input facts. |
| `pass_mode` | `bool` | `False` | Include input facts in the output (deductive closure = input + derived). |
| `pass_all` | `bool` | `False` | Include input facts, rules, and derived triples in the output. |
| `djiti_debug` | `bool` | `False` | Log DJITI join-ordering decisions for each rule application. |
| `query` | `Triple \| None` | `None` | Backward-chain from this triple pattern. Variables in the pattern are bound by the engine. Results go in `Result.query_answers`. |
| `forward` | `bool` | `True` | If `False`, skip forward chaining (backward-only mode). |
| `entail` | `bool` | `False` | Apply RDFS entailment rules before user rules. Derives triples from `rdfs:subClassOf`, `rdfs:subPropertyOf`, `rdfs:domain`, `rdfs:range`. |
| `entail_owl` | `bool` | `False` | Apply OWL 2 RL entailment (implies `entail=True`). Adds `owl:sameAs`, `owl:inverseOf`, transitive/symmetric/functional property reasoning, class expressions. |
| `not_entail` | `Triple \| None` | `None` | If set, check that this triple is NOT entailed. Sets `result.stats["not_entail_failed"]` to `True` if the triple was derived. |
| `cache_dir` | `str \| None` | `None` | Directory for caching fetched remote N3 files. |
| `explain_format` | `"n3" \| "dot" \| "html"` | `"n3"` | Format for proof traces when `explain=True`. `"n3"` returns raw proof objects; `"dot"` returns a Graphviz DOT string; `"html"` returns a collapsible HTML page. |

### Return value: `Result`

```python
@dataclass
class Result:
    triples: str              # N3 text of derived (or all) triples
    stats: dict               # reasoning statistics
    explains: list | str      # proof traces (depends on explain_format)
    query_answers: list       # backward-chaining query results
```

#### `result.triples`

A string containing the N3 serialization of the output triples. What "output" means depends on the mode:

- Default: only rule-derived triples (facts the engine figured out)
- `pass_mode=True`: input facts + derived triples
- `pass_all=True`: input facts + rules + derived triples
- `nope=True`: input facts only (no reasoning)

#### `result.stats`

```python
{
    "steps": 42,               # number of rule firings
    "derived": 12,             # number of new triples added
    "time_ms": 3.7,            # wall-clock time in milliseconds
    "not_entail_failed": False # True if not_entail triple WAS derived (check failed)
}
```

#### `result.explains`

Proof traces. Only populated when `explain=True`. Content depends on `explain_format`:

- `"n3"` — list of `ProofTree` objects (internal representation)
- `"dot"` — Graphviz DOT string representing the full proof forest
- `"html"` — HTML string with collapsible proof tree, suitable for browser rendering

#### `result.query_answers`

List of binding dicts from backward chaining. Only populated when `query=` is set.

```python
result = execute(
    data_strings=["@prefix : <http://example.org/> . :alice :parent :bob ."],
    rule_strings=["@prefix : <http://example.org/> . { ?X :parent ?Y } => { ?Y :child ?X } ."],
    query=Triple(
        NamedNode("http://example.org/bob"),
        NamedNode("http://example.org/child"),
        Variable("Who"),
    ),
)

for binding in result.query_answers:
    print(binding["Who"].value)  # http://example.org/alice
```

Each element of `query_answers` is a `dict[str, Term]` mapping variable name (without `?`) to a bound term.

### Examples

```python
from pyeye import execute
from pyeye.term import NamedNode, Variable, Triple

# Basic reasoning
result = execute(
    data_strings=["@prefix : <http://ex.org/> . :a :b :c ."],
    rule_strings=["@prefix : <http://ex.org/> . { ?X :b ?Y } => { ?Y :backlink ?X } ."],
)
print(result.triples)

# RDFS entailment
result = execute(
    data_strings=["""
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        @prefix : <http://ex.org/> .
        :Dog rdfs:subClassOf :Animal .
        :rex a :Dog .
    """],
    entail=True,
    pass_mode=True,
)
# result.triples includes :rex a :Animal .

# Backward chaining query
result = execute(
    data_strings=["@prefix : <http://ex.org/> . :a :link :b . :b :link :c ."],
    rule_strings=["""
        @prefix : <http://ex.org/> .
        { ?X :reachable ?Y } <= { ?X :link ?Y } .
        { ?X :reachable ?Y } <= { ?X :reachable ?Z . ?Z :reachable ?Y } .
    """],
    query=Triple(
        NamedNode("http://ex.org/a"),
        NamedNode("http://ex.org/reachable"),
        Variable("Dest"),
    ),
)
for b in result.query_answers:
    print(b["Dest"])

# Proof trace (HTML)
result = execute(
    data_strings=["@prefix : <http://ex.org/> . :a :p :b ."],
    rule_strings=["@prefix : <http://ex.org/> . { ?X :p ?Y } => { ?Y :q ?X } ."],
    explain=True,
    explain_format="html",
)
with open("proof.html", "w") as f:
    f.write(result.explains)

# Not-entail check
result = execute(
    data_strings=["@prefix : <http://ex.org/> . :a :p :b ."],
    rule_strings=["@prefix : <http://ex.org/> . { ?X :p ?Y } => { ?Y :q ?X } ."],
    not_entail=Triple(
        NamedNode("http://ex.org/b"),
        NamedNode("http://ex.org/q"),
        NamedNode("http://ex.org/a"),
    ),
)
if result.stats["not_entail_failed"]:
    print("Triple WAS derived — check failed")

# Custom builtins
from pyeye.term import Literal

def my_fn(args, engine):
    if isinstance(args[0], Variable):
        return None
    return Literal(args[0].value.upper())

result = execute(
    data_strings=["@prefix : <http://ex.org/> . :x :val \"hello\" ."],
    rule_strings=["""
        @prefix : <http://ex.org/> .
        @prefix fn: <http://example.org/fn#> .
        { ?I :val ?V . ?V fn:upper ?U } => { ?I :upper ?U } .
    """],
    builtins={"http://example.org/fn#upper": my_fn},
)
```

---

## `Engine` — direct engine access

For fine-grained control, use the `Engine` class directly:

```python
from pyeye.engine import Engine
from pyeye.parser import parse_n3, Rule
from pyeye.term import NamedNode, Literal, Triple

engine = Engine(
    builtins=None,
    max_steps=-1,
    limit_answers=-1,
    djiti_debug=False,
    explain=False,
    timeout_seconds=30.0,
)
```

### Constructor parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `builtins` | `dict[str, Builtin] \| None` | `None` | Custom builtins merged into the default registry |
| `max_steps` | `int` | `-1` | Step cap (-1 = unlimited) |
| `limit_answers` | `int` | `-1` | Answer cap (-1 = unlimited) |
| `djiti_debug` | `bool` | `False` | Log DJITI ordering decisions |
| `explain` | `bool` | `False` | Collect proof trees |
| `timeout_seconds` | `float \| None` | `30.0` | Wall-clock timeout; `None` to disable |

### Methods

#### `engine.add_triple(triple: Triple) -> bool`

Add a fact triple to the store. Returns `True` if the triple was genuinely new (not already in the store). If rules have already been loaded, this also triggers incremental re-evaluation of rules that could derive new facts from the new triple.

```python
engine.add_triple(Triple(
    NamedNode("http://ex.org/alice"),
    NamedNode("http://ex.org/age"),
    Literal("30", datatype=NamedNode("http://www.w3.org/2001/XMLSchema#integer")),
))
```

#### `engine.add_rule(rule: Rule) -> None`

Add a forward or backward rule.

```python
doc = parse_n3("{ ?X :p ?Y } => { ?Y :q ?X } .")
for rule in doc.rules:
    engine.add_rule(rule)
```

#### `engine.run() -> None`

Run forward chaining to fixpoint (or until `max_steps` / `limit_answers` / `timeout_seconds` is reached). Call this after loading all data and rules.

#### `engine.backward_chain(query: Triple) -> list[dict]`

Run backward chaining from a goal triple. Returns a list of binding dicts, one per solution.

```python
bindings = engine.backward_chain(Triple(
    NamedNode("http://ex.org/alice"),
    NamedNode("http://ex.org/reachable"),
    Variable("Dest"),
))
for b in bindings:
    print(b["Dest"])
```

#### `engine.snapshot_initial() -> None`

Record the current store size as the baseline. Call after loading data but before adding rules, so that input facts are not counted as "derived."

### Properties and attributes

| Attribute | Type | Description |
|-----------|------|-------------|
| `engine.store` | `TripleStore` | The underlying triple store |
| `engine.derived_triples` | `list[Triple]` | Triples derived by rules (not input facts) |
| `engine.step_count` | `int` | Total number of rule firings so far |
| `engine._rules` | `list[Rule]` | Loaded rules (read-only by convention) |
| `engine._proof_trees` | `list[ProofTree]` | Proof trees (populated when `explain=True`) |

### Complete example

```python
from pyeye.engine import Engine
from pyeye.parser import parse_n3
from pyeye.term import NamedNode, Literal, Variable, Triple
from pyeye.output import N3Writer

BASE = "http://example.org/"
XSD = "http://www.w3.org/2001/XMLSchema#"

engine = Engine(timeout_seconds=60.0)

# Add facts
engine.add_triple(Triple(
    NamedNode(BASE + "alice"),
    NamedNode(BASE + "age"),
    Literal("70", datatype=NamedNode(XSD + "integer")),
))
engine.add_triple(Triple(
    NamedNode(BASE + "bob"),
    NamedNode(BASE + "age"),
    Literal("45", datatype=NamedNode(XSD + "integer")),
))

engine.snapshot_initial()

# Load rules
doc = parse_n3("""
    @prefix : <http://example.org/> .
    @prefix math: <http://www.w3.org/2000/10/swap/math#> .
    { ?P :age ?A . ?A math:greaterThan 65 } => { ?P :isSenior true } .
""")
for rule in doc.rules:
    engine.add_rule(rule)

engine.run()

# Query store
for t in engine.store.match(predicate=NamedNode(BASE + "isSenior")):
    print(t.subject.value, "is a senior")

# Serialize derived triples
writer = N3Writer({"": BASE, "xsd": XSD})
print(writer.write_triples(engine.derived_triples))

# Stats
print(f"Steps: {engine.step_count}, Derived: {len(engine.derived_triples)}")
```

### Incremental reasoning

The engine supports adding facts after `run()` has been called. Each `add_triple()` call triggers incremental re-evaluation of rules that might fire for the new triple:

```python
engine = Engine()
doc = parse_n3(rules_n3)
for rule in doc.rules:
    engine.add_rule(rule)
engine.snapshot_initial()
engine.run()

prev_count = len(engine.derived_triples)

# Add a new fact — engine incrementally re-evaluates
engine.add_triple(Triple(sensor_node, temp_pred, Literal("36")))

# Get only the new derivations
new_derivations = engine.derived_triples[prev_count:]
```

For stream processing, you can also call `engine.run()` again after adding batches of new facts:

```python
for batch in incoming_stream:
    for triple in batch:
        engine.add_triple(triple)
    engine.run()
    process(engine.derived_triples[prev_count:])
    prev_count = len(engine.derived_triples)
```

---

## `TripleStore` — the fact store

The triple store holds all facts (input and derived). It maintains indexes by predicate, subject, and object for fast pattern matching.

```python
from pyeye.store import TripleStore
from pyeye.term import NamedNode, Triple

store = TripleStore()
store.add(Triple(NamedNode("http://ex.org/a"), NamedNode("http://ex.org/p"), NamedNode("http://ex.org/b")))
```

### Methods

#### `store.add(triple: Triple) -> bool`

Add a triple. Returns `True` if new, `False` if already present.

#### `store.match(subject=None, predicate=None, object=None, graph=None) -> Iterator[Triple]`

Pattern-match triples. Any argument that is `None` acts as a wildcard:

```python
# All triples
for t in store.match():
    print(t)

# All triples with a specific predicate
for t in store.match(predicate=NamedNode("http://ex.org/age")):
    print(t.subject, t.object)

# All triples with a specific subject and predicate
results = list(store.match(
    subject=NamedNode("http://ex.org/alice"),
    predicate=NamedNode("http://ex.org/age"),
))
```

#### `store.contains(triple: Triple) -> bool`

Check if a triple is in the store.

#### `store.retract(triple: Triple) -> bool`

Remove a triple. Returns `True` if it was present.

#### `store.retract_all(subject=None, predicate=None, object=None) -> int`

Remove all triples matching the pattern. Returns the number removed.

#### `store.add_quad(quad: Quad) -> bool`

Add a named-graph quad (triple + graph context).

#### `__len__(store)` and `__iter__(store)`

```python
print(len(store))           # number of triples
for triple in store:        # iterate all triples
    print(triple)
```

---

## Term types

All term types are frozen dataclasses and are hashable. They live in `pyeye.term`.

### `NamedNode`

An IRI (global identifier).

```python
from pyeye.term import NamedNode

nn = NamedNode("http://example.org/alice")
nn.value  # "http://example.org/alice"
str(nn)   # "http://example.org/alice"
```

### `Literal`

An RDF literal — a string value with optional datatype or language tag.

```python
from pyeye.term import Literal, NamedNode

# Plain string
Literal("hello")

# Typed literal
Literal("42", datatype=NamedNode("http://www.w3.org/2001/XMLSchema#integer"))
Literal("3.14", datatype=NamedNode("http://www.w3.org/2001/XMLSchema#double"))
Literal("true", datatype=NamedNode("http://www.w3.org/2001/XMLSchema#boolean"))

# Language-tagged
Literal("Alice", language="en")
Literal("アリス", language="ja")

# Access fields
lit = Literal("42", datatype=NamedNode("http://www.w3.org/2001/XMLSchema#integer"))
lit.value     # "42"
lit.datatype  # NamedNode("http://www.w3.org/2001/XMLSchema#integer")
lit.language  # None
```

A Literal cannot have both `datatype` and `language`.

### `Variable`

A pattern variable (unbound slot in rules and queries).

```python
from pyeye.term import Variable

v = Variable("X")
v.name   # "X"
str(v)   # "?X"
```

### `Existential`

A blank node (anonymous resource, existential variable).

```python
from pyeye.term import Existential

bn = Existential("node1")
bn.name  # "node1"
str(bn)  # "_:node1"
```

### `Triple`

A subject-predicate-object triple. Used both as a fact in the store and as a pattern in rule bodies.

```python
from pyeye.term import Triple, NamedNode, Literal, Variable

# Ground triple (fact)
t = Triple(
    NamedNode("http://ex.org/alice"),
    NamedNode("http://ex.org/age"),
    Literal("30"),
)
t.subject    # NamedNode(...)
t.predicate  # NamedNode(...)
t.object     # Literal(...)
t.is_ground()  # True

# Pattern triple (for queries)
p = Triple(
    Variable("Person"),
    NamedNode("http://ex.org/age"),
    Variable("Age"),
)
p.is_ground()  # False
```

### `Formula`

A conjunction of triples — used in rule bodies and heads.

```python
from pyeye.term import Formula, Triple, NamedNode, Variable

f = Formula(triples=(
    Triple(Variable("X"), NamedNode("http://ex.org/p"), Variable("Y")),
    Triple(Variable("Y"), NamedNode("http://ex.org/q"), Variable("Z")),
))
```

### `TripleTerm`

An RDF-star reified triple — a triple that itself acts as a subject or object.

```python
from pyeye.term import TripleTerm, NamedNode

tt = TripleTerm(
    subject=NamedNode("http://ex.org/alice"),
    predicate=NamedNode("http://ex.org/knows"),
    object=NamedNode("http://ex.org/bob"),
)
str(tt)  # "<<http://ex.org/alice http://ex.org/knows http://ex.org/bob>>"
```

In N3: `<< :alice :knows :bob >> :source :survey .`

### `PathTerm`

A chained path expression: `:a ! :p ! :q` (forward) or `:a ^ :p` (reverse).

```python
from pyeye.term import PathTerm, NamedNode

path = PathTerm(
    subject=NamedNode("http://ex.org/alice"),
    terms=(NamedNode("http://ex.org/parent"), NamedNode("http://ex.org/name")),
    directions=("forward", "forward"),
)
```

### `Quad`

A named-graph triple (subject, predicate, object, graph).

```python
from pyeye.term import Quad, NamedNode

q = Quad(
    subject=NamedNode("http://ex.org/alice"),
    predicate=NamedNode("http://ex.org/age"),
    object=Literal("30"),
    graph=NamedNode("http://ex.org/graph/people"),
)
```

### `NegativeSurface`

Internal representation of a `log:onNegativeSurface` directive.

```python
from pyeye.term import NegativeSurface, Formula, Triple, NamedNode, Variable

ns = NegativeSurface(formula=Formula(triples=(
    Triple(Variable("X"), NamedNode("http://ex.org/timeout"), Variable("Any")),
)))
```

---

## `parse_n3()` — parse N3 text

```python
from pyeye.parser import parse_n3, ParsedDocument

doc: ParsedDocument = parse_n3(
    text: str,
    source: str = "<string>",
)
```

Returns a `ParsedDocument` with:

| Field | Type | Description |
|-------|------|-------------|
| `doc.triples` | `list[Triple]` | Ground fact triples |
| `doc.quads` | `list[Quad]` | Named-graph quads |
| `doc.rules` | `list[Rule]` | Parsed rules (forward and backward) |
| `doc.prefixes` | `dict[str, str]` | Prefix declarations from the document |

```python
from pyeye.parser import parse_n3

doc = parse_n3("""
    @prefix : <http://example.org/> .
    :alice :age 30 .
    { ?X :age ?A . ?A math:greaterThan 18 } => { ?X :isAdult true } .
""")

print(len(doc.triples))  # 1
print(len(doc.rules))    # 1
print(doc.prefixes)      # {'': 'http://example.org/'}
```

`ParseError` is raised on invalid N3 syntax.

### `Rule`

```python
from pyeye.parser import Rule

rule = Rule(
    body=Formula(...),      # body patterns
    head=Formula(...),      # head triples to derive
    source="<string>",      # for error messages
    is_backward=False,      # True for <= rules
    for_some=(),            # @forSome variable names
)
```

---

## `N3Writer` — serialize triples to N3

```python
from pyeye.output import N3Writer

writer = N3Writer(prefixes={"": "http://example.org/", "xsd": "http://www.w3.org/2001/XMLSchema#"})

triples_text = writer.write_triples(list_of_triples)   # str
quads_text   = writer.write_quads(list_of_quads)       # str
```

The writer uses the provided prefix map to abbreviate IRIs. If no prefix map is given, full IRIs are written.

```python
from pyeye.output import N3Writer
from pyeye.term import Triple, NamedNode, Literal

writer = N3Writer({"": "http://example.org/"})
triples = [
    Triple(NamedNode("http://example.org/alice"), NamedNode("http://example.org/age"), Literal("30")),
]
print(writer.write_triples(triples))
# :alice :age "30" .
```

---

## `ReasoningTimeoutError`

Raised by `engine.run()` when the wall-clock timeout is exceeded.

```python
from pyeye.engine import ReasoningTimeoutError
from pyeye import execute

try:
    result = execute(
        data_strings=[data],
        rule_strings=[recursive_rules],
        timeout_seconds=10.0,
    )
except ReasoningTimeoutError as e:
    print(f"Reasoning timed out: {e}")
    # Handle partial results or abort
```

Set `timeout_seconds=None` to disable the guard entirely — only do this if you are certain the rules terminate.

---

## Custom builtins protocol

### `Builtin` type

```python
from pyeye.builtins import Builtin

# A builtin is any callable matching this signature:
def my_builtin(args: list[Term], engine: EngineProto) -> Term | list[Triple] | MultiResult | None:
    ...
```

### `MultiResult`

Returned by generative builtins that produce multiple results from one call.

```python
from pyeye.builtins import MultiResult
from pyeye.term import Literal

def generate_colors(args, engine):
    return MultiResult([Literal("red"), Literal("green"), Literal("blue")])
```

The engine forks the current binding once per element — equivalent to a SQL `IN` or Prolog disjunction.

### `register_derive_function()`

Register a Python function for use with `e:derive`:

```python
from pyeye.builtins import register_derive_function
from pyeye.term import Literal

def square(args, engine):
    n = float(args[0].value)
    return Literal(str(n * n))

register_derive_function("square", square)
```

In N3:

```n3
@prefix e: <http://eulersharp.sourceforge.net/2003/03swap/log-rules#> .

{ ?X :value ?V . ("square" ?V) e:derive ?Sq }
    => { ?X :squared ?Sq } .
```

---

## Complete workflow example

```python
from pyeye import execute, ReasoningTimeoutError
from pyeye.term import NamedNode, Variable, Triple, Literal
from pyeye.engine import Engine
from pyeye.parser import parse_n3
from pyeye.output import N3Writer

BASE = "http://shop.org/"
MATH = "http://www.w3.org/2000/10/swap/math#"

# --- 1. High-level: execute() ---

result = execute(
    data_strings=[f"""
        @prefix : <{BASE}> .
        :widget :price 120 ; :category :electronics .
        :gadget :price 40  ; :category :electronics .
    """],
    rule_strings=[f"""
        @prefix : <{BASE}> .
        @prefix math: <{MATH}> .
        {{?P :category :electronics . ?P :price ?V . ?V math:greaterThan 100}}
            => {{?P :tier :premium}} .
        {{?P :tier :premium . ?P :price ?V . (?V 0.9) math:product ?Sale}}
            => {{?P :salePrice ?Sale}} .
    """],
    pass_mode=True,
    timeout_seconds=30.0,
)

print(result.triples)
print(result.stats)

# --- 2. Low-level: Engine ---

engine = Engine(explain=True)

doc = parse_n3(f"""
    @prefix : <{BASE}> .
    :widget :price 120 .
""")
for t in doc.triples:
    engine.add_triple(t)

engine.snapshot_initial()

rules_doc = parse_n3(f"""
    @prefix : <{BASE}> .
    @prefix math: <{MATH}> .
    {{?I :price ?P . ?P math:greaterThan 100}} => {{?I :premium true}} .
""")
for rule in rules_doc.rules:
    engine.add_rule(rule)

try:
    engine.run()
except ReasoningTimeoutError:
    print("Timeout!")

writer = N3Writer({"": BASE})
print(writer.write_triples(engine.derived_triples))
print(f"Steps: {engine.step_count}")

# --- 3. Incremental: add facts after run ---

engine.add_triple(Triple(
    NamedNode(BASE + "gizmo"),
    NamedNode(BASE + "price"),
    Literal("200"),
))
# Incremental re-evaluation fires automatically
print(writer.write_triples(engine.derived_triples))
```
