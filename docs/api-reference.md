# API Reference

This document describes every public function, class, and method in pyeye. If you're new here, start with the [Getting Started guide](getting-started.md) first — it explains the concepts before diving into code.

---

## `execute()` — The One Function You Need

**Source:** `execute` — `pyeye/entry.py:34`

This is the main entry point. You give it facts and rules, it gives you derived facts back.

```python
from pyeye import execute

result = execute(
    data_strings=["@prefix : <http://ex.org/> .\n:alice :parent :bob ."],
    rule_strings=["@prefix : <http://ex.org/> .\n{?X :parent ?Y} => {?Y :child ?X} ."],
)

print(result.triples)
# :bob :child :alice .
```

### Parameters

| Parameter | Type | Phase | What it does | Default |
| :--- | :--- | :--- | :--- | :--- |
| `data_paths` | `list[str]` | 1 | Load facts from N3/Turtle/TriG files | `None` |
| `data_strings` | `list[str]` | 1 | Load facts from inline N3 strings | `None` |
| `rule_paths` | `list[str]` | 1 | Load rules from N3 files | `None` |
| `rule_strings` | `list[str]` | 1 | Load rules from inline N3 strings | `None` |
| `builtins` | `dict` | 1 | Custom builtin registry (merged with defaults) | `None` |
| `explain` | `bool` | 2 | Collect proof explanations | `False` |
| `explain_format` | `Literal["n3", "dot", "html"]` | 2 | Proof output format | `"n3"` |
| `max_steps` | `int` | 1 | Hard cap on inference steps (`-1` = unlimited) | `-1` |
| `limit_answers` | `int` | 1 | Stop after N derived triples (`-1` = unlimited) | `-1` |
| `prefixes` | `dict` | 1 | Shortcuts for output formatting | `None` |
| `nope` | `bool` | 1 | Skip reasoning, just pass through data | `False` |
| `pass_mode` | `bool` | 1 | Include input facts in output | `False` |
| `pass_all` | `bool` | 1 | Include facts, rules, and derived | `False` |
| `djiti_debug` | `bool` | 2 | Log DJITI pattern ordering | `False` |
| `query` | `Triple` | 2 | Backward-chain from this goal triple | `None` |
| `forward` | `bool` | 2 | Run forward chaining before backward | `True` |
| `entail` | `bool` | 2 | Apply RDFS entailment first | `False` |
| `not_entail` | `Triple` | 2 | Check this triple is NOT entailed | `None` |
| `cache_dir` | `str` | 2 | Cache directory for remote N3 files | `None` |

### Return Value

**Source:** `Result` — `pyeye/entry.py:26`

```python
@dataclass
class Result:
    triples: str        # N3 output text
    stats: dict         # Performance info
    explains: list      # Proof trees (empty when explain=False)
    query_answers: list # Bindings from backward chaining (empty when query=None)
```

The `stats` dict always has these keys:

```python
{
    "steps": 5,              # Number of inference steps taken
    "derived": 3,            # Number of new triples derived
    "time_ms": 1.2,          # Total execution time in milliseconds
    "not_entail_failed": False,  # True if not_entail triple WAS found
}
```

### Common Patterns

**Simple derivation (output only new facts):**
```python
r = execute(
    data_strings=["@prefix : <http://ex.org/> .\n:a :p :b ."],
    rule_strings=["@prefix : <http://ex.org/> .\n{?X :p ?Y} => {?X :q ?Y} ."],
)
# r.triples = ":a :q :b ."
```

**Show everything (input + derived):**
```python
r = execute(
    data_strings=["@prefix : <http://ex.org/> .\n:a :p :b ."],
    rule_strings=["@prefix : <http://ex.org/> .\n{?X :p ?Y} => {?X :q ?Y} ."],
    pass_mode=True,
)
# r.triples = ":a :p :b .\n:a :q :b ."
```

**RDFS entailment before user rules:**
```python
r = execute(
    data_strings=[
        """
        @prefix : <http://ex.org/> .
        @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
        :Cat rdfs:subClassOf :Animal .
        :fluffy rdf:type :Cat .
        """,
    ],
    rule_strings=[
        """
        @prefix : <http://ex.org/> .
        @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
        { ?X rdf:type :Animal } => { ?X :isAlive true } .
        """,
    ],
    entail=True,
)
# RDFS derives :fluffy rdf:type :Animal
# Then user rule derives :fluffy :isAlive true
```

**Backward chaining from a goal:**
```python
from pyeye import execute
from pyeye.term import NamedNode, Variable, Triple

r = execute(
    data_strings=["@prefix : <http://ex.org/> .\n:alice :parent :bob ."],
    rule_strings=["@prefix : <http://ex.org/> .\n{?X :parent ?Y} => {?Y :child ?X} ."],
    query=Triple(
        NamedNode("http://ex.org/bob"),
        NamedNode("http://ex.org/child"),
        Variable("X"),
    ),
)
# r.query_answers = [{"X": NamedNode("http://ex.org/alice")}]
```

**Proof traces:**
```python
r = execute(
    data_strings=["@prefix : <http://ex.org/> .\n:a :p :b ."],
    rule_strings=["@prefix : <http://ex.org/> .\n{?X :p ?Y} => {?X :q ?Y} ."],
    explain=True,
)
print(r.explains)  # List[ProofTree]

# Or get DOT format for Graphviz:
r = execute(
    data_strings=["@prefix : <http://ex.org/> .\n:a :p :b ."],
    rule_strings=["@prefix : <http://ex.org/> .\n{?X :p ?Y} => {?X :q ?Y} ."],
    explain=True,
    explain_format="dot",
)
print(r.explains)  # DOT string for graphviz
```

**Not-entail check:**
```python
r = execute(
    data_strings=["@prefix : <http://ex.org/> .\n:a :p :b ."],
    rule_strings=["@prefix : <http://ex.org/> .\n{?X :p ?Y} => {?X :q ?Y} ."],
    not_entail=Triple(
        NamedNode("http://ex.org/a"),
        NamedNode("http://ex.org/notDerived"),
        NamedNode("http://ex.org/x"),
    ),
)
# r.stats["not_entail_failed"] is False (triple was NOT derived — check passed)
```

**Load data from HTTP:**
```python
r = execute(
    data_paths=["http://example.org/data.ttl"],
    rule_paths=["http://example.org/rules.n3"],
    cache_dir="/tmp/pyeye-cache",  # Cache remote files
)
```

---

## Term Types — Building Blocks

**Source:** `pyeye/term.py`

Everything in pyeye is built from **terms**. There are nine kinds:

### `NamedNode` — A Named Thing

An IRI (Internationalized Resource Identifier) — essentially a URL that names something.

```python
from pyeye import NamedNode

person = NamedNode("http://example.org/people/alice")
relation = NamedNode("http://example.org/relations/knows")
```

Source: `NamedNode` — `pyeye/term.py:36`

### `Literal` — A Value

Text, numbers, dates — anything that has a concrete value.

```python
from pyeye import Literal, NamedNode

# Plain text
name = Literal("Alice")

# Number
age = Literal("30", datatype=NamedNode("http://www.w3.org/2001/XMLSchema#integer"))

# Language-tagged text
greeting = Literal("bonjour", language="fr")
```

Source: `Literal` — `pyeye/term.py:45`

### `Variable` — A Placeholder

Used in rules to match any value.

```python
from pyeye import Variable

x = Variable("X")   # Written as ?X in N3 text
person = Variable("Person")
```

Source: `Variable` — `pyeye/term.py:66`

### `Existential` — An Anonymous Thing

A unique identifier that the engine creates internally.

```python
from pyeye import Existential

anon = Existential("genid-1")  # Written as _:genid-1 in N3
```

Source: `Existential` — `pyeye/term.py:75`

### `Formula` — A Group of Triples

A collection of triples wrapped in curly braces `{ ... }`.

```python
from pyeye import Formula, Triple, NamedNode

body = Formula((
    Triple(Variable("X"), NamedNode("http://ex.org/parent"), Variable("Y")),
))
# Represents: { ?X :parent ?Y }
```

Source: `Formula` — `pyeye/term.py:84`

### `Triple` — A Fact

Three terms: subject, predicate, object.

```python
from pyeye import Triple, NamedNode

fact = Triple(
    NamedNode("http://example.org/alice"),
    NamedNode("http://example.org/knows"),
    NamedNode("http://example.org/bob"),
)
# Represents: :alice :knows :bob .
```

| Method | What it does | Source |
| :--- | :--- | :--- |
| `is_ground()` | Returns `True` if the triple has no variables | `Triple.is_ground` — `pyeye/term.py:197` |

Source: `Triple` — `pyeye/term.py:184`

### Phase 2 Extended Types

#### `TripleTerm` — A Reified Triple

A triple that can appear as subject or object: `<< S P O >>`.

```python
from pyeye import TripleTerm, NamedNode

tt = TripleTerm(
    NamedNode("http://ex.org/alice"),
    NamedNode("http://ex.org/knows"),
    NamedNode("http://ex.org/bob"),
)
# Used as: << :alice :knows :bob >> :wasSaidBy :charlie .
```

Source: `TripleTerm` — `pyeye/term.py:101`

#### `FormulaTerm` — A Formula as a Term

`(| Functor Args |)` — a formula that can appear inside other triples.

```python
from pyeye import FormulaTerm, NamedNode, Literal

ft = FormulaTerm(
    NamedNode("http://ex.org/says"),
    (NamedNode("http://ex.org/alice"), Literal("hello")),
)
# Used as: :alice :thinks (| :says :alice "hello" |) .
```

Source: `FormulaTerm` — `pyeye/term.py:125`

#### `PathTerm` — A Chained Path

`:a ! :p ! :q` or `:a ^ :p` — chained path expressions.

```python
from pyeye import PathTerm, NamedNode

pt = PathTerm(
    (NamedNode("http://ex.org/p"), NamedNode("http://ex.org/q")),
    ("forward", "forward"),
)
# Used as: :a ! :p ! :q :target .
```

Source: `PathTerm` — `pyeye/term.py:148`

#### `Quad` — A Named-Graph Triple

`(S P O G)` — a triple with a graph identifier.

```python
from pyeye import Quad, NamedNode

q = Quad(
    NamedNode("http://ex.org/a"),
    NamedNode("http://ex.org/p"),
    NamedNode("http://ex.org/b"),
    NamedNode("http://ex.org/graph1"),
)
```

Source: `Quad` — `pyeye/term.py:233`

#### `NegativeSurface` — BLOGIC Negation

`log:onNegativeSurface { ... }` — a negation construct.

```python
from pyeye import NegativeSurface, Formula, Triple, NamedNode, Variable

ns = NegativeSurface(
    Formula((
        Triple(NamedNode("http://ex.org/a"), NamedNode("http://ex.org/p"), NamedNode("http://ex.org/b")),
    ))
)
```

Source: `NegativeSurface` — `pyeye/term.py:210`

---

## `Engine` — Low-Level Control

**Source:** `Engine` — `pyeye/engine.py:29`

Direct access to the reasoning engine. Use `execute()` for most cases; use `Engine` when you need fine-grained control.

```python
from pyeye.engine import Engine
from pyeye.parser import Rule
from pyeye.term import NamedNode, Variable, Triple, Formula

engine = Engine(
    builtins=None,         # custom builtin registry (optional)
    max_steps=100,         # hard step cap
    limit_answers=10,      # stop after N derivations
    djiti_debug=False,     # log DJITI pattern ordering
    explain=False,         # record proof traces
)

# Add facts
engine.add_triple(Triple(
    NamedNode("http://ex.org/alice"),
    NamedNode("http://ex.org/parent"),
    NamedNode("http://ex.org/bob"),
))

# Add rules
engine.add_rule(Rule(
    body=Formula((Triple(Variable("X"), NamedNode("http://ex.org/parent"), Variable("Y")),)),
    head=Formula((Triple(Variable("Y"), NamedNode("http://ex.org/child"), Variable("X")),)),
))

# Run forward chaining
engine.run()

# Access results
print(engine.derived_triples)   # List[Triple] — only rule-derived triples
print(engine.step_count)        # int — total inference steps
print(len(engine.store))        # int — total triples in store
```

### Methods

| Method | Description | Source |
| :--- | :--- | :--- |
| `add_triple(t) -> bool` | Add a fact. Returns `True` if new. Triggers incremental reasoning if rules exist. | `Engine.add_triple` — `pyeye/engine.py:65` |
| `add_rule(r)` | Add a rule for the next `run()` | `Engine.add_rule` — `pyeye/engine.py:62` |
| `snapshot_initial()` | Mark current store size as baseline (input facts) | `Engine.snapshot_initial` — `pyeye/engine.py:134` |
| `run()` | Forward chain to fixpoint or limit | `Engine.run` — `pyeye/engine.py:140` |
| `backward_chain(query)` | Goal-directed reasoning with tabling | `Engine.backward_chain` — `pyeye/engine.py:436` |

### Properties

| Property | Type | Description | Source |
| :--- | :--- | :--- | :--- |
| `store` | `TripleStore` | The triple store (read/write) | `Engine.store` — `pyeye/engine.py:39` |
| `derived_triples` | `list[Triple]` | Only rule-derived triples | `Engine.derived_triples` — `pyeye/engine.py:555` |
| `step_count` | `int` | Total inference steps taken | `Engine.step_count` — `pyeye/engine.py:560` |
| `_proof_steps` | `list[ProofStep]` | Proof step records (when explain=True) | — |
| `_proof_trees` | `list[ProofTree]` | Proof trees (when explain=True) | — |
| `_djiti_log` | `list[dict]` | DJITI pattern ordering log | — |

---

## Unification — Matching Patterns

**Source:** `pyeye/unify.py`

Unification is the engine's way of asking: *"Does this pattern match this fact? If so, what are the variable values?"*

```python
from pyeye.unify import unify, apply_binding, apply_binding_to_triple
from pyeye.term import Variable, NamedNode, Triple

# Does "?X :parent :bob" match ":alice :parent :bob"?
pattern = Triple(Variable("X"), NamedNode("http://ex.org/parent"), NamedNode("http://ex.org/bob"))
fact    = Triple(NamedNode("http://ex.org/alice"), NamedNode("http://ex.org/parent"), NamedNode("http://ex.org/bob"))

binding = unify(pattern, fact)
# binding = {"X": NamedNode("http://ex.org/alice")}
```

| Function | Signature | Description | Source |
| :--- | :--- | :--- | :--- |
| `unify` | `(pattern, candidate, binding) -> Binding | None` | Match pattern against candidate, extending binding. Returns `None` on failure. | `unify` — `pyeye/unify.py:48` |
| `apply_binding` | `(term, binding) -> Term` | Replace variables in term with bound values | `apply_binding` — `pyeye/unify.py:119` |
| `apply_binding_to_triple` | `(triple, binding) -> Triple` | Replace variables in triple with bound values | `apply_binding_to_triple` — `pyeye/unify.py:151` |
| `term_contains_var` | `(term, var_name) -> bool` | Occurs check helper | `term_contains_var` — `pyeye/unify.py:70` |

All unification enforces the **occurs check**: a variable cannot bind to a term containing itself.

---

## TripleStore — Where Facts Live

**Source:** `TripleStore` — `pyeye/store.py:27`

The triple store is an in-memory database for facts (and quads for named graphs). It has predicate-based and graph-based indexes for fast lookups.

```python
from pyeye.store import TripleStore
from pyeye.term import Triple, NamedNode, Quad

store = TripleStore()

# Add facts (default graph)
store.add(Triple(NamedNode("alice"), NamedNode("knows"), NamedNode("bob")))
store.add(Triple(NamedNode("alice"), NamedNode("knows"), NamedNode("carol")))

# Add named graph quads
store.add_quad(Quad(
    NamedNode("alice"), NamedNode("age"), Literal("30"),
    NamedNode("graph1"),
))

# Find all facts about a specific predicate
for t in store.match(predicate=NamedNode("knows")):
    print(t)

# Find all facts in a named graph
for t in store.match(graph=NamedNode("graph1")):
    print(t)

# Retract a fact
store.retract(Triple(NamedNode("alice"), NamedNode("knows"), NamedNode("bob")))
```

| Method | Signature | Description | Source |
| :--- | :--- | :--- | :--- |
| `add(triple) -> bool` | Add triple to default graph. `True` if new. | `TripleStore.add` — `pyeye/store.py:47` |
| `add_quad(quad) -> bool` | Add quad to named graph. `True` if new. | `TripleStore.add_quad` — `pyeye/store.py:62` |
| `contains(triple) -> bool` | Check if triple exists in default graph. | `TripleStore.contains` — `pyeye/store.py:75` |
| `match(s, p, o, graph)` | Pattern match. `None` = wildcard. Uses indexes when `p` or `graph` is bound. | `TripleStore.match` — `pyeye/store.py:100` |
| `retract(triple) -> bool` | Remove triple from default graph. `True` if found. | `TripleStore.retract` — `pyeye/store.py:79` |
| `retract_all(s, p, o) -> int` | Remove all matching triples. Returns count. | `TripleStore.retract_all` — `pyeye/store.py:94` |
| `__len__() -> int` | Number of triples + quads in store. | `TripleStore.__len__` — `pyeye/store.py:140` |
| `triples() -> frozenset[Triple]` | Snapshot of default graph triples. | `TripleStore.triples` — `pyeye/store.py:147` |
| `quads() -> frozenset[Quad]` | Snapshot of named graph quads. | `TripleStore.quads` — `pyeye/store.py:151` |

---

## Parsing — Reading N3 Text

**Source:** `pyeye/parser.py`

You usually don't need to call these directly — `execute()` handles parsing internally. But if you need to parse N3 text manually:

```python
from pyeye import parse_n3, parse_rules

# Parse N3 with rules
doc = parse_n3("@prefix : <http://ex.org/> .\n{?X :p ?Y} => {?Y :q ?X} .")
print(doc.rules)     # List[Rule]
print(doc.triples)   # List[Triple] — standalone formulas become triples
print(doc.quads)     # List[Quad] — TriG named graphs
print(doc.prefixes)  # Dict[str, str]

# Parse rules only
rules = parse_rules("{?X :p ?Y} => {?Y :q ?X} .")
```

`ParseError` is raised on malformed N3.

| Function | Signature | Description | Source |
| :--- | :--- | :--- | :--- |
| `parse_n3(text, source)` | `(str, str) -> ParsedDocument` | Parse N3/TriG with rules and data | `parse_n3` — `pyeye/parser.py:660` |
| `parse_rules(text, source)` | `(str, str) -> list[Rule]` | Extract rules only | `parse_rules` — `pyeye/parser.py:665` |
| `load_data_file(path)` | `(str | Path) -> ParsedDocument` | Load data via rdflib | `load_data_file` — `pyeye/parser.py:634` |
| `load_data_string(text)` | `(str) -> ParsedDocument` | Load data string via rdflib | `load_data_string` — `pyeye/parser.py:645` |

---

## Proof Traces

**Source:** `pyeye/proof.py`

When `explain=True` is passed to `execute()`, every derivation is recorded.

```python
from pyeye import execute
from pyeye.proof import serialize_n3, serialize_dot, serialize_html

r = execute(
    data_strings=["@prefix : <http://ex.org/> .\n:a :p :b ."],
    rule_strings=["@prefix : <http://ex.org/> .\n{?X :p ?Y} => {?X :q ?Y} ."],
    explain=True,
)

# r.explains is a list[ProofTree]

# Serialize to different formats
n3_text = serialize_n3(r.explains)
dot_text = serialize_dot(r.explains)
html_text = serialize_html(r.explains)
```

| Class / Function | Description | Source |
| :--- | :--- | :--- |
| `ProofStep` | A single derivation step: `(conclusion, premise, rule, chaining, source)` | `ProofStep` — `pyeye/proof.py:21` |
| `ProofTree` | A tree of proof steps with a root triple and children | `ProofTree` — `pyeye/proof.py:35` |
| `serialize_n3(trees)` | Serialize proofs to N3 triples | `serialize_n3` — `pyeye/proof.py:54` |
| `serialize_dot(trees)` | Serialize proofs to DOT (Graphviz) | `serialize_dot` — `pyeye/proof.py:127` |
| `serialize_html(trees)` | Serialize proofs to HTML (collapsible) | `serialize_html` — `pyeye/proof.py:168` |

---

## RDFS Entailment

**Source:** `apply_rdfs_entailment` — `pyeye/rdfs.py:28`

Applies RDFS inference rules to derive implicit triples:

- **subClassOf**: if A subClassOf B and X type A → X type B
- **subPropertyOf**: if P subPropertyOf Q and A P B → A Q B
- **domain**: if P domain D and A P B → A type D
- **range**: if P range R and A P B → B type R

```python
from pyeye.rdfs import apply_rdfs_entailment
from pyeye.store import TripleStore

store = TripleStore()
# ... add triples ...
count = apply_rdfs_entailment(store)
# count = number of new triples derived
```

---

## Output — Writing N3 Text

**Source:** `N3Writer` — `pyeye/output.py:9`

Convert triples back to N3 text for display or saving.

```python
from pyeye.output import N3Writer
from pyeye.term import NamedNode, Triple

w = N3Writer({"ex": "http://example.org/"})
text = w.write_triples([
    Triple(NamedNode("http://example.org/alice"),
           NamedNode("http://example.org/knows"),
           NamedNode("http://example.org/bob")),
])
print(text)
# @prefix ex: <http://example.org/> .
#
# ex:alice ex:knows ex:bob .
```

| Method | Description | Source |
| :--- | :--- | :--- |
| `write_triples(triples) -> str` | Serialize triples to N3, sorted by (subject, predicate, object) | `N3Writer.write_triples` — `pyeye/output.py:25` |
| `write_quads(quads) -> str` | Serialize quads to TriG text with named graphs | `N3Writer.write_quads` — `pyeye/output.py:50` |

---

## Builtins

**Source:** `BUILTIN_REGISTRY` — `pyeye/builtins.py:1267`

See the [Builtins Reference](builtins.md) for the full list with examples.

To see what's available:

```python
from pyeye import BUILTIN_REGISTRY

for iri in sorted(BUILTIN_REGISTRY):
    print(iri)
# http://www.w3.org/2000/10/swap/crypto#md5
# http://www.w3.org/2000/10/swap/crypto#sha256
# http://www.w3.org/2000/10/swap/graph#member
# http://www.w3.org/2000/10/swap/list#car
# http://www.w3.org/2000/10/swap/log#uuid
# http://www.w3.org/2007/XPath-functions#concat
# ... 93 total
```

To register custom functions for `e:derive`:

```python
from pyeye.builtins import register_derive_function
from pyeye.term import Literal

def my_double(args, engine):
    """Double a number."""
    return Literal(str(float(args[0].value) * 2))

register_derive_function("double", my_double)
```

---

## CLI

**Source:** `main` — `pyeye/cli.py:12`

See the [CLI Reference](cli-reference.md) for all flags and examples.

```bash
pyeye --n3 data.ttl --query rules.n3 --pass --statistics --entail --explain --explain-format html
```
