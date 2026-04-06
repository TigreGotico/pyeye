# API Reference

Every public function, class, and method in pyeye. If you are new here, start with the [Getting Started guide](getting-started.md) first.

---

## `execute()` — The One Function You Need

`execute` — `pyeye/entry.py:34`

The main entry point. Pass facts and rules, get derived facts back.

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

| Parameter | Type | Default | What it does |
| :--- | :--- | :--- | :--- |
| `data_paths` | `list[str] \| None` | `None` | Load facts from N3/Turtle/TriG files (local paths or HTTP URLs) |
| `data_strings` | `list[str] \| None` | `None` | Load facts from inline N3 strings |
| `rule_paths` | `list[str] \| None` | `None` | Load rules from N3 files (local paths or HTTP URLs) |
| `rule_strings` | `list[str] \| None` | `None` | Load rules from inline N3 strings |
| `builtins` | `dict \| None` | `None` | Custom builtin registry, merged with the default 240 |
| `explain` | `bool` | `False` | Collect proof explanations for each derived triple |
| `explain_format` | `"n3" \| "dot" \| "html"` | `"n3"` | Output format for proof traces |
| `max_steps` | `int` | `-1` | Hard cap on inference steps (`-1` = unlimited) |
| `limit_answers` | `int` | `-1` | Stop after N derived triples (`-1` = unlimited) |
| `prefixes` | `dict \| None` | `None` | Additional prefix shortcuts for N3 output |
| `nope` | `bool` | `False` | Skip reasoning; just load and re-emit data |
| `pass_mode` | `bool` | `False` | Include input facts in output alongside derived triples |
| `pass_all` | `bool` | `False` | Include input facts, rules, and derived triples in output |
| `djiti_debug` | `bool` | `False` | Log DJITI pattern ordering to `engine._djiti_log` |
| `query` | `Triple \| None` | `None` | Backward-chain from this goal triple |
| `forward` | `bool` | `True` | Run forward chaining before backward chaining |
| `entail` | `bool` | `False` | Apply RDFS entailment (subClassOf, subPropertyOf, domain, range) before user rules |
| `entail_owl` | `bool` | `False` | Apply OWL 2 RL entailment (superset of RDFS; adds transitive/symmetric/functional properties, class constructors, sameAs, etc.) |
| `not_entail` | `Triple \| None` | `None` | Check that this triple is NOT entailed; sets `stats["not_entail_failed"]` |
| `cache_dir` | `str \| None` | `None` | Cache directory for remote N3 files; HTTP URLs are fetched and stored as SHA-256 named files |

### Return value — `Result`

`Result` — `pyeye/entry.py:26`

```python
@dataclass
class Result:
    triples: str        # N3 text of derived (or all) triples
    stats: dict         # Performance and status information
    explains: list      # Proof trees (empty when explain=False)
    query_answers: list # Variable bindings from backward chaining
```

The `stats` dict always contains:

```python
{
    "steps": 5,               # Total inference steps taken
    "derived": 3,             # Triples in result output
    "time_ms": 1.2,           # Total wall-clock time in milliseconds
    "not_entail_failed": False # True if the not_entail triple WAS found
}
```

When `explain=True` and `explain_format="n3"`, `result.explains` is a `list[ProofTree]`. When `explain_format` is `"dot"` or `"html"`, it is a serialized string.

### Common patterns

**Derive new facts only (default):**

```python
r = execute(
    data_strings=["@prefix : <http://ex.org/> .\n:a :p :b ."],
    rule_strings=["@prefix : <http://ex.org/> .\n{?X :p ?Y} => {?X :q ?Y} ."],
)
# r.triples = ":a :q :b .\n"
```

**Show everything (input + derived):**

```python
r = execute(
    data_strings=["@prefix : <http://ex.org/> .\n:a :p :b ."],
    rule_strings=["@prefix : <http://ex.org/> .\n{?X :p ?Y} => {?X :q ?Y} ."],
    pass_mode=True,
)
# r.triples includes both ":a :p :b ." and ":a :q :b ."
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

**OWL 2 RL entailment:**

```python
r = execute(
    data_strings=[
        """
        @prefix : <http://ex.org/> .
        @prefix owl: <http://www.w3.org/2002/07/owl#> .
        :knows a owl:SymmetricProperty .
        :alice :knows :bob .
        """,
    ],
    rule_strings=[],
    entail_owl=True,
)
# OWL derives :bob :knows :alice (symmetric property)
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
    explain_format="dot",  # or "n3" or "html"
)
# r.explains → DOT string for Graphviz (or ProofTree list for "n3")
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

**Load data from HTTP with caching:**

```python
r = execute(
    data_paths=["http://example.org/data.ttl"],
    rule_paths=["http://example.org/rules.n3"],
    cache_dir="/tmp/pyeye-cache",
)
```

---

## Term Types

`pyeye/term.py`

Everything in pyeye is built from **terms**. All term types are frozen dataclasses (hashable, usable as dict keys).

### `NamedNode` — An IRI

`NamedNode` — `pyeye/term.py:36`

```python
from pyeye import NamedNode

person = NamedNode("http://example.org/people/alice")
```

Represents an IRI (Internationalized Resource Identifier) — the unique name for a resource.

### `Literal` — A Value

`Literal` — `pyeye/term.py:44`

```python
from pyeye import Literal, NamedNode

name    = Literal("Alice")
age     = Literal("30", datatype=NamedNode("http://www.w3.org/2001/XMLSchema#integer"))
bonjour = Literal("bonjour", language="fr")
```

A `Literal` cannot have both `datatype` and `language` set simultaneously.

### `Variable` — A Placeholder

`Variable` — `pyeye/term.py:65`

```python
from pyeye import Variable

x = Variable("X")    # Written ?X in N3 text
```

### `Existential` — A Blank Node

`Existential` — `pyeye/term.py:74`

```python
from pyeye import Existential

anon = Existential("genid-1")    # Written _:genid-1 in N3
```

### `Formula` — A Conjunction of Triples

`Formula` — `pyeye/term.py:83`

```python
from pyeye import Formula, Triple, NamedNode, Variable

body = Formula((
    Triple(Variable("X"), NamedNode("http://ex.org/parent"), Variable("Y")),
))
# Represents: { ?X :parent ?Y }
```

### `Triple` — A Fact

`Triple` — `pyeye/term.py:184` (approximate; see actual file)

```python
from pyeye import Triple, NamedNode

fact = Triple(
    NamedNode("http://example.org/alice"),
    NamedNode("http://example.org/knows"),
    NamedNode("http://example.org/bob"),
)
# Represents: :alice :knows :bob .
```

| Method | Returns | Source |
| :--- | :--- | :--- |
| `is_ground()` | `bool` — True if triple has no variables | `Triple.is_ground` — `pyeye/term.py` |

### `TripleTerm` — A Reified Triple

`TripleTerm` — `pyeye/term.py:100`

A triple used as subject or object: `<< S P O >>`.

```python
from pyeye import TripleTerm, NamedNode

tt = TripleTerm(
    NamedNode("http://ex.org/alice"),
    NamedNode("http://ex.org/knows"),
    NamedNode("http://ex.org/bob"),
)
# Used as: << :alice :knows :bob >> :wasSaidBy :charlie .
```

### `FormulaTerm` — A Formula as a Term

`FormulaTerm` — `pyeye/term.py:125` (approximate)

`(| Functor Args |)` — a formula embedded inside another triple.

```python
from pyeye import FormulaTerm, NamedNode, Literal

ft = FormulaTerm(
    NamedNode("http://ex.org/says"),
    (NamedNode("http://ex.org/alice"), Literal("hello")),
)
```

### `PathTerm` — A Chained Path

`PathTerm` — `pyeye/term.py:148` (approximate)

`:a ! :p ! :q` or `:a ^ :p` — chained path expressions.

### `Quad` — A Named-Graph Triple

`Quad` — `pyeye/term.py:233` (approximate)

```python
from pyeye import Quad, NamedNode

q = Quad(
    NamedNode("http://ex.org/a"),
    NamedNode("http://ex.org/p"),
    NamedNode("http://ex.org/b"),
    NamedNode("http://ex.org/graph1"),
)
```

### `NegativeSurface` — BLOGIC Negation

`NegativeSurface` — `pyeye/term.py:210` (approximate)

`log:onNegativeSurface { ... }` — the body only matches if the enclosed formula does NOT match the store.

### `SetTerm` — An Unordered Collection

`SetTerm` — `pyeye/__init__.py` (exported)

`($ a b c $)` — a set of terms. Treated as an ordered list internally in the current implementation.

---

## `Engine` — Low-Level Control

`Engine` — `pyeye/engine.py:29`

Direct access to the reasoning engine. Use `execute()` for most cases; use `Engine` when you need incremental loading or step-by-step control.

```python
from pyeye.engine import Engine
from pyeye.parser import Rule
from pyeye.term import NamedNode, Variable, Triple, Formula

engine = Engine(
    builtins=None,       # custom builtin registry (optional)
    max_steps=100,       # hard step cap (-1 = unlimited)
    limit_answers=10,    # stop after N derivations (-1 = unlimited)
    djiti_debug=False,   # log DJITI pattern ordering
    explain=False,       # record proof traces
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
print(engine.derived_triples)   # list[Triple] — only rule-derived triples
print(engine.step_count)        # int — total inference steps
print(len(engine.store))        # int — total triples in store
```

### Methods

| Method | Signature | Description | Source |
| :--- | :--- | :--- | :--- |
| `add_triple(t)` | `(Triple) -> bool` | Add a fact. Returns `True` if new. When rules are loaded, triggers incremental re-evaluation. | `Engine.add_triple` — `pyeye/engine.py:68` |
| `add_rule(r)` | `(Rule) -> None` | Add a rule for the next `run()` | `Engine.add_rule` — `pyeye/engine.py:65` |
| `snapshot_initial()` | `() -> None` | Mark current store size as baseline (input facts vs derived) | `Engine.snapshot_initial` — `pyeye/engine.py:146` |
| `run()` | `() -> None` | Forward-chain to fixpoint or limit | `Engine.run` — `pyeye/engine.py:152` |
| `backward_chain(query)` | `(Triple) -> list[dict]` | Goal-directed reasoning; returns list of variable binding dicts | `Engine.backward_chain` — `pyeye/engine.py:533` |

### Properties

| Property | Type | Description | Source |
| :--- | :--- | :--- | :--- |
| `store` | `TripleStore` | The triple store (read/write) | `Engine.store` — `pyeye/engine.py:40` |
| `derived_triples` | `list[Triple]` | Only rule-derived triples (excludes input facts) | `Engine.derived_triples` — `pyeye/engine.py:665` |
| `step_count` | `int` | Total inference steps taken | `Engine.step_count` — `pyeye/engine.py:670` |

---

## Unification

`pyeye/unify.py`

The engine matches rule body patterns against facts using unification. You can call these functions directly for custom pattern matching.

```python
from pyeye.unify import unify, apply_binding, apply_binding_to_triple
from pyeye.term import Variable, NamedNode, Triple

pattern = Triple(Variable("X"), NamedNode("http://ex.org/parent"), NamedNode("http://ex.org/bob"))
fact    = Triple(NamedNode("http://ex.org/alice"), NamedNode("http://ex.org/parent"), NamedNode("http://ex.org/bob"))

binding = unify(pattern, fact)
# binding = {"X": NamedNode("http://ex.org/alice")}
```

| Function | Signature | Description | Source |
| :--- | :--- | :--- | :--- |
| `unify` | `(pattern, candidate, binding={}) -> dict \| None` | Match pattern against candidate, extending binding. Returns `None` on failure. | `unify` — `pyeye/unify.py:48` |
| `apply_binding` | `(term, binding) -> Term` | Replace variables in term with bound values | `apply_binding` — `pyeye/unify.py:119` |
| `apply_binding_to_triple` | `(triple, binding) -> Triple` | Replace variables in all three positions | `apply_binding_to_triple` — `pyeye/unify.py:151` |
| `term_contains_var` | `(term, var_name) -> bool` | Occurs check helper | `term_contains_var` — `pyeye/unify.py:70` |

Unification enforces the **occurs check**: a variable cannot be bound to a term that contains itself.

---

## `TripleStore` — Where Facts Live

`TripleStore` — `pyeye/store.py:27`

An in-memory triple/quad store indexed by predicate, subject, and object for fast lookups.

```python
from pyeye.store import TripleStore
from pyeye.term import Triple, NamedNode, Literal, Quad

store = TripleStore()

# Add triples to the default graph
store.add(Triple(NamedNode("alice"), NamedNode("knows"), NamedNode("bob")))
store.add(Triple(NamedNode("alice"), NamedNode("knows"), NamedNode("carol")))

# Add triples to a named graph
store.add_quad(Quad(
    NamedNode("alice"), NamedNode("age"), Literal("30"),
    NamedNode("graph1"),
))

# Pattern match (None = wildcard)
for t in store.match(predicate=NamedNode("knows")):
    print(t)

# Named graph match
for t in store.match(graph=NamedNode("graph1")):
    print(t)

print(len(store))    # total triples + quads
```

| Method | Signature | Description | Source |
| :--- | :--- | :--- | :--- |
| `add(triple)` | `(Triple) -> bool` | Add to default graph. `True` if new. | `TripleStore.add` — `pyeye/store.py:50` |
| `add_quad(quad)` | `(Quad) -> bool` | Add to named graph. `True` if new. | `TripleStore.add_quad` — `pyeye/store.py:62` |
| `contains(triple)` | `(Triple) -> bool` | Check membership in default graph. | `TripleStore.contains` — `pyeye/store.py:75` |
| `match(s, p, o, graph)` | `(Term\|None, ...) -> Iterator[Triple\|Quad]` | Pattern match. `None` = wildcard. Uses predicate/subject/object indexes when bound. | `TripleStore.match` — `pyeye/store.py:100` |
| `retract(triple)` | `(Triple) -> bool` | Remove from default graph. `True` if found. | `TripleStore.retract` — `pyeye/store.py:79` |
| `retract_all(s, p, o)` | `(...) -> int` | Remove all matching triples. Returns count. | `TripleStore.retract_all` — `pyeye/store.py:94` |
| `__len__()` | `() -> int` | Total triples + quads. | `TripleStore.__len__` — `pyeye/store.py` |
| `__iter__()` | `() -> Iterator[Triple]` | Iterate default graph triples. | `TripleStore.__iter__` — `pyeye/store.py` |
| `triples()` | `() -> frozenset[Triple]` | Snapshot of default graph. | `TripleStore.triples` — `pyeye/store.py` |
| `quads()` | `() -> frozenset[Quad]` | Snapshot of named graph quads. | `TripleStore.quads` — `pyeye/store.py` |

---

## Parsing

`pyeye/parser.py`

`execute()` handles parsing internally. Call these directly only when you need to parse N3 text without running reasoning.

```python
from pyeye import parse_n3, parse_rules

doc = parse_n3("@prefix : <http://ex.org/> .\n{?X :p ?Y} => {?Y :q ?X} .")
print(doc.rules)     # list[Rule]
print(doc.triples)   # list[Triple]
print(doc.quads)     # list[Quad]
print(doc.prefixes)  # dict[str, str]
```

`ParseError` is raised on malformed N3.

| Function | Signature | Description | Source |
| :--- | :--- | :--- | :--- |
| `parse_n3(text, source)` | `(str, str) -> ParsedDocument` | Parse N3/TriG including rules | `parse_n3` — `pyeye/parser.py:660` |
| `parse_rules(text, source)` | `(str, str) -> list[Rule]` | Extract rules only | `parse_rules` — `pyeye/parser.py:665` |
| `load_data_file(path)` | `(str \| Path) -> ParsedDocument` | Load data via rdflib | `load_data_file` — `pyeye/parser.py:634` |
| `load_data_string(text)` | `(str) -> ParsedDocument` | Parse data string via rdflib | `load_data_string` — `pyeye/parser.py:645` |

---

## Proof Traces

`pyeye/proof.py`

When `explain=True` is passed to `execute()`, every derivation is recorded as a `ProofStep` and assembled into a `ProofTree`.

```python
from pyeye import execute
from pyeye.proof import serialize_n3, serialize_dot, serialize_html

r = execute(
    data_strings=["@prefix : <http://ex.org/> .\n:a :p :b ."],
    rule_strings=["@prefix : <http://ex.org/> .\n{?X :p ?Y} => {?X :q ?Y} ."],
    explain=True,
)
# r.explains is list[ProofTree] when explain_format="n3" (default)

# Serialize manually:
n3_text   = serialize_n3(r.explains)
dot_text  = serialize_dot(r.explains)
html_text = serialize_html(r.explains)
```

| Class / Function | Description | Source |
| :--- | :--- | :--- |
| `ProofStep` | Single derivation step: `conclusion`, `premise`, `rule`, `chaining`, `source` | `ProofStep` — `pyeye/proof.py:21` |
| `ProofTree` | Tree of steps: `root`, `children`, `rule`, `chaining` | `ProofTree` — `pyeye/proof.py:35` |
| `serialize_n3(trees)` | Serialize proofs to N3 triples | `serialize_n3` — `pyeye/proof.py:54` |
| `serialize_dot(trees)` | Serialize proofs to DOT (Graphviz) | `serialize_dot` — `pyeye/proof.py:127` |
| `serialize_html(trees)` | Serialize proofs to collapsible HTML | `serialize_html` — `pyeye/proof.py:168` |

---

## RDFS Entailment

`apply_rdfs_entailment` — `pyeye/rdfs.py:28`

Applies RDFS inference rules to derive implicit triples:

- **subClassOf**: if A subClassOf B and X type A, then X type B
- **subPropertyOf**: if P subPropertyOf Q and A P B, then A Q B
- **domain**: if P domain D and A P B, then A type D
- **range**: if P range R and A P B, then B type R

```python
from pyeye.rdfs import apply_rdfs_entailment
from pyeye.store import TripleStore

store = TripleStore()
# ... add triples ...
count = apply_rdfs_entailment(store)
# count = number of new triples derived
```

---

## OWL 2 RL Entailment

`apply_owl_rl_entailment` — `pyeye/owl.py:81`

Applies OWL 2 RL entailment rules (a superset of RDFS):

- **Individual equality**: `owl:sameAs` inference
- **Property characteristics**: transitive, symmetric, functional, inverse-functional, inverse-of
- **Class constructors**: intersectionOf, unionOf, someValuesFrom, allValuesFrom, hasValue, oneOf
- **Property chains**: `owl:propertyChainAxiom`

```python
from pyeye.owl import apply_owl_rl_entailment
from pyeye.store import TripleStore

store = TripleStore()
# ... add OWL axioms and data triples ...
count = apply_owl_rl_entailment(store)
# count = number of new triples derived
```

This is also accessible through `execute(entail_owl=True)`, which runs both OWL 2 RL and RDFS entailment.

---

## Output — Writing N3 Text

`N3Writer` — `pyeye/output.py:9`

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

`BUILTIN_REGISTRY` — `pyeye/builtins.py:2321`

See [builtins.md](builtins.md) for the full list with examples.

```python
from pyeye import BUILTIN_REGISTRY

print(len(BUILTIN_REGISTRY))    # 240

for iri in sorted(BUILTIN_REGISTRY):
    print(iri)
```

### Registering custom builtins

**Method 1 — pass to `execute()`:**

```python
from pyeye import execute
from pyeye.term import Literal, Variable

def my_double(args, engine):
    if any(isinstance(a, Variable) for a in args):
        return None  # not ground yet — skip
    return Literal(str(float(args[0].value) * 2))

result = execute(
    data_strings=["@prefix : <http://ex.org/> .\n:item :value 21 ."],
    rule_strings=[
        "@prefix : <http://ex.org/> .\n"
        "@prefix e: <http://eulersharp.sourceforge.net/2003/03swap/log-rules#> .\n"
        "{ ?I :value ?V . ?V e:myDouble ?D } => { ?I :doubled ?D } ."
    ],
    builtins={
        "http://eulersharp.sourceforge.net/2003/03swap/log-rules#myDouble": my_double
    },
)
# All 240 standard builtins remain available.
```

**Method 2 — `e:derive` by name:**

```python
from pyeye.builtins import register_derive_function
from pyeye.term import Literal

def triple_it(args, engine):
    return Literal(str(float(args[0].value) * 3))

register_derive_function("triple", triple_it)
```

Then in N3:

```n3
{ ?Item :value ?V . (?V "triple") e:derive ?T } => { ?Item :tripled ?T } .
```

### Builtin function signature

```python
def my_builtin(args: list[Term], engine: Engine) -> Term | list[Triple] | None:
    """
    args:   list of resolved argument Terms (subject and object, list-expanded)
    engine: the Engine instance (access engine.store for lookups)

    Return:
        Term         → result value (bound to object variable in head)
        list[Triple] → triples to assert directly
        None         → skip (arguments not ground, or condition not met)
    """
```
