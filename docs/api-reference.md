# API Reference

## `execute()` — Main Entry Point

**Source:** `execute` — `pyeye/entry.py:34`

```python
def execute(
    data_paths: list[str] | None = None,
    data_strings: list[str] | None = None,
    rule_paths: list[str] | None = None,
    rule_strings: list[str] | None = None,
    builtins: dict[str, Builtin] | None = None,
    explain: bool = False,
    max_steps: int = -1,
    limit_answers: int = -1,
    prefixes: dict[str, str] | None = None,
    nope: bool = False,
    pass_mode: bool = False,
    pass_all: bool = False,
) -> Result
```

### Parameters

| Parameter | Purpose |
| :--- | :--- |
| `data_paths` | Paths to N3/Turtle data files (parsed via rdflib) |
| `data_strings` | Inline N3/Turtle data strings |
| `rule_paths` | Paths to N3 rule files (may contain `{P} => {C}` rules) |
| `rule_strings` | Inline N3 rule strings |
| `builtins` | Custom builtin registry (merged with defaults). Keys are full IRIs, values are callables |
| `explain` | If `True`, collect proof explanations. Phase 1: always returns `[]` |
| `max_steps` | Hard cap on inference steps. `-1` = unlimited |
| `limit_answers` | Stop after this many new derivations. `-1` = unlimited |
| `prefixes` | Additional prefix mappings for output serialization |
| `nope` | Skip derivation — pass through input data only |
| `pass_mode` | Output includes input facts + derived triples |
| `pass_all` | Output includes input facts, rules, and derived triples |

### Return Value

**Source:** `Result` — `pyeye/entry.py:22`

```python
@dataclass
class Result:
    triples: str    # N3 output text
    stats: dict     # {"steps": int, "derived": int, "time_ms": float}
    explains: list  # Always [] in Phase 1
```

### Example

```python
from pyeye import execute

r = execute(
    data_strings=["@prefix : <http://ex.org/> .\n:a :p :b ."],
    rule_strings=["@prefix : <http://ex.org/> .\n{?X :p ?Y} => {?X :q ?Y} ."],
)
assert r.stats["derived"] == 1
assert ":q" in r.triples
```

---

## `Engine` — Low-Level Access

**Source:** `Engine` — `pyeye/engine.py:32`

Direct access to the reasoning engine. Use `execute()` for most cases; use `Engine` when you need incremental control.

```python
from pyeye.engine import Engine
from pyeye.parser import Rule
from pyeye.term import NamedNode, Variable, Triple, Formula

e = Engine(
    builtins=None,        # custom builtin registry (optional)
    max_steps=-1,         # hard step cap
    limit_answers=-1,     # stop after N derivations
)

# Add data
e.add_triple(Triple(NamedNode("http://x/a"), NamedNode("http://x/p"), NamedNode("http://x/b")))

# Add rules
e.add_rule(Rule(
    body=Formula((Triple(Variable("X"), NamedNode("http://x/p"), Variable("Y")),)),
    head=Formula((Triple(Variable("X"), NamedNode("http://x/q"), Variable("Y")),)),
))

# Run
e.run()

# Access results
print(e.derived_triples)   # List[Triple] — only rule-derived triples
print(e.step_count)        # int — total inference steps
print(len(e.store))        # int — total triples in store
```

### Methods

| Method | Description | Source |
| :--- | :--- | :--- |
| `add_triple(t) -> bool` | Add a fact. Returns `True` if genuinely new | `engine.py:58` |
| `add_rule(r)` | Add a rule for the next `run()` | `engine.py:55` |
| `snapshot_initial()` | Mark current store size as baseline (input facts) | `engine.py:62` |
| `run()` | Forward chain to fixpoint or limit | `engine.py:66` |

### Properties

| Property | Type | Description | Source |
| :--- | :--- | :--- | :--- |
| `store` | `TripleStore` | The triple store (read/write) | `engine.py:39` |
| `derived_triples` | `list[Triple]` | Only rule-derived triples | `engine.py:273` |
| `step_count` | `int` | Total inference steps taken | `engine.py:278` |

---

## Term Hierarchy

**Source:** `pyeye/term.py`

All terms are `@dataclass(frozen=True)` and hashable. The `Term` protocol is `@runtime_checkable` for `isinstance()` checks.

### `NamedNode`

An IRI reference.

```python
from pyeye import NamedNode
nn = NamedNode("http://example.org/foo")
```

### `Literal`

An RDF literal with optional datatype or language tag.

```python
from pyeye import Literal, NamedNode

plain = Literal("hello")
typed = Literal("42", datatype=NamedNode("http://www.w3.org/2001/XMLSchema#integer"))
lang  = Literal("bonjour", language="fr")
```

**Constraint:** A `Literal` cannot have both `datatype` and `language` set simultaneously.

### `Variable`

A logical variable (e.g., `?X`).

```python
from pyeye import Variable
v = Variable("X")
```

### `Existential`

A blank node or skolem constant.

```python
from pyeye import Existential
e = Existential("genid-1")
```

### `Formula`

A nested formula (conjunction of triples).

```python
from pyeye import Formula, Triple, NamedNode
f = Formula((
    Triple(NamedNode("http://x/a"), NamedNode("http://x/p"), NamedNode("http://x/b")),
))
```

### `Triple`

An RDF triple `(subject, predicate, object)`.

```python
from pyeye import Triple, NamedNode
t = Triple(NamedNode("http://x/a"), NamedNode("http://x/p"), NamedNode("http://x/b"))
```

| Method | Description | Source |
| :--- | :--- | :--- |
| `is_ground() -> bool` | `True` if no component contains a `Variable` | `term.py:99` |

---

## Unification

**Source:** `pyeye/unify.py`

```python
from pyeye.unify import unify, apply_binding, apply_binding_to_triple
from pyeye.term import Variable, NamedNode, Triple, Binding
```

| Function | Signature | Description |
| :--- | :--- | :--- |
| `unify` | `(pattern: Triple, candidate: Triple, binding: Binding | None) -> Binding | None` | Unify pattern with candidate, extending binding. Returns `None` on failure. |
| `apply_binding` | `(term: Term, binding: Binding) -> Term` | Substitute variables in term |
| `apply_binding_to_triple` | `(triple: Triple, binding: Binding) -> Triple` | Substitute variables in triple |
| `term_contains_var` | `(term: Term, var_name: str) -> bool` | Occurs check helper |

All unification enforces the **occurs check**: a variable cannot bind to a term containing itself.

---

## Triple Store

**Source:** `TripleStore` — `pyeye/store.py:27`

```python
from pyeye.store import TripleStore
from pyeye.term import Triple, NamedNode

store = TripleStore()
store.add(Triple(NamedNode("a"), NamedNode("p"), NamedNode("b")))
```

| Method | Signature | Description |
| :--- | :--- | :--- |
| `add(triple) -> bool` | Add triple. `True` if new, `False` if duplicate |
| `contains(triple) -> bool` | Check membership |
| `match(s, p, o) -> Iterator[Triple]` | Pattern match. `None` = wildcard. Uses predicate index when `p` is `NamedNode` |
| `__len__() -> int` | Number of triples |
| `__iter__() -> Iterator[Triple]` | Iterate all triples |
| `triples() -> frozenset[Triple]` | Snapshot of all triples |

---

## Parsing

**Source:** `pyeye/parser.py`

```python
from pyeye import parse_n3, parse_rules, ParseError

# Parse N3 with rules
doc = parse_n3("@prefix : <http://ex.org/> .\n{?X :p ?Y} => {?X :q ?Y} .")
print(doc.rules)     # List[Rule]
print(doc.triples)   # List[Triple] — standalone formulas become triples
print(doc.prefixes)  # Dict[str, str]

# Parse rules only
rules = parse_rules("{?X :p ?Y} => {?X :q ?Y} .")
```

| Function | Signature | Description |
| :--- | :--- | :--- |
| `parse_n3(text, source)` | `(str, str) -> ParsedDocument` | Parse N3 with rules and data |
| `parse_rules(text, source)` | `(str, str) -> list[Rule]` | Extract rules only |
| `load_data_file(path)` | `(str | Path) -> ParsedDocument` | Load data via rdflib |
| `load_data_string(text)` | `(str) -> ParsedDocument` | Load data string via rdflib |

`ParseError` is raised on malformed N3.

---

## Output

**Source:** `N3Writer` — `pyeye/output.py:9`

```python
from pyeye.output import N3Writer
from pyeye.term import NamedNode, Triple

w = N3Writer({"ex": "http://example.org/"})
text = w.write_triples([Triple(NamedNode("http://example.org/a"), NamedNode("http://example.org/p"), NamedNode("http://example.org/b"))])
print(text)
# @prefix ex: <http://example.org/> .
#
# ex:a ex:p ex:b .
```

| Method | Description | Source |
| :--- | :--- | :--- |
| `write_triples(triples) -> str` | Serialize to N3, sorted by (subject, predicate, object) | `output.py:25` |

---

## Builtins

**Source:** `BUILTIN_REGISTRY` — `pyeye/builtins.py:336`

```python
from pyeye import BUILTIN_REGISTRY

print(list(BUILTIN_REGISTRY.keys()))
# ['http://www.w3.org/2000/10/swap/math#equalTo', ...]
```

See [builtins.md](builtins.md) for the full list with examples.

### Custom Builtins

```python
from pyeye import execute
from pyeye.term import Literal, Variable

def double_fn(args, engine):
    if any(isinstance(a, Variable) for a in args):
        return None  # unground — skip
    val = float(args[0].value)
    return Literal(str(val * 2), datatype=Literal("0").datatype)  # or NamedNode for xsd:double

r = execute(
    data_strings=["@prefix : <http://ex.org/> .\n:a :val 5 ."],
    rule_strings=["@prefix : <http://ex.org/> .\n{?X :val ?V} => {?X :doubled ?D} ."],
    builtins={"http://ex.org/doubled": double_fn},
)
```

The builtin protocol is defined at `pyeye/builtins.py:28`.
