# pyeye

A pure-Python port of the [EYE](https://eulersharp.sourceforge.net/) N3 reasoning engine. Give it facts and rules written in Notation3 (N3); it derives new facts automatically using forward and backward chaining.

**Python 3.11+ · MIT License · One dependency (`rdflib`)**

---

## What it does

pyeye is a **reasoning engine**. You write:

- **Facts** — things you know (`:alice :parent :bob .`)
- **Rules** — patterns to follow (`{ ?X :parent ?Y } => { ?Y :child ?X } .`)

And it produces:

- **Derived facts** — things it figured out (`:bob :child :alice .`)

It implements the Euler Abstract Machine with forward chaining, backward chaining, RDFS entailment, DJITI join ordering, proof tree output, and 240 built-in functions for math, strings, dates, crypto, graphs, and more.

---

## Install

```bash
git clone https://github.com/your-org/pyeye
cd pyeye
pip install -e .
```

Or from a wheel:

```bash
pip install pyeye
```

Requires Python 3.11 or newer. The only runtime dependency is `rdflib >= 6.0`.

---

## Quick Start

### Python API

```python
from pyeye import execute

result = execute(
    data_strings=[
        """
        @prefix : <http://example.org/> .
        :alice :parent :bob .
        :bob   :parent :carol .
        """,
    ],
    rule_strings=[
        """
        @prefix : <http://example.org/> .
        { ?X :parent ?Y }              => { ?Y :child ?X } .
        { ?X :parent ?Y . ?Y :parent ?Z } => { ?X :grandparent ?Z } .
        """,
    ],
)

print(result.triples)
# :bob   :child :alice .
# :carol :child :bob .
# :alice :grandparent :carol .

print(result.stats)
# {'steps': 4, 'derived': 3, 'time_ms': 1.4, 'not_entail_failed': False}
```

### Command line

```bash
pyeye --n3 family.ttl --query rules.n3 --pass --statistics
# facts + derived facts → stdout
# # steps=4 derived=3 time=1.4ms → stderr
```

---

## Features

| Feature | Description |
|---|---|
| Forward chaining | Euler Abstract Machine — apply rules to fixpoint |
| Backward chaining | Goal-directed reasoning with tabling (memoization) |
| RDFS entailment | subClassOf, subPropertyOf, domain, range inference |
| DJITI indexing | Most-constrained-first join ordering for performance |
| Incremental reasoning | `add_triple()` after rules triggers immediate re-evaluation |
| Proof traces | N3, DOT (Graphviz), and HTML proof tree output |
| HTTP data loading | Remote files with SHA-256 cache; SSRF protection built in |
| 240 builtins | Math (44), String (28), List (27), Log (34+), Crypto (4), Time (9), Graph (9), E/misc (85+) |
| TriG named graphs | `GRAPH <g> { ... }` syntax |
| BLOGIC negation | `log:onNegativeSurface { ... }` — negation as failure |
| Not-entail checking | Verify a triple is NOT derivable |
| Triple terms | `<< S P O >>` — reified triples |
| Path expressions | `!` (forward) and `^` (reverse) chained paths |

---

## CLI Usage

```bash
# Derive new facts only
pyeye --n3 data.ttl --query rules.n3

# Show input + derived (deductive closure)
pyeye --n3 data.ttl --query rules.n3 --pass

# RDFS entailment before user rules
pyeye --n3 data.ttl --query rules.n3 --entail

# Proof tree (HTML)
pyeye --n3 data.ttl --query rules.n3 --explain --explain-format html > proof.html

# Backward chain from a goal
pyeye --n3 data.ttl --query rules.n3 --query-goal http://ex.org/bob,http://ex.org/child,?X

# Limit and cap
pyeye --n3 data.ttl --query rules.n3 --max-inferences 1000 --tactic limited-answer 10

# Remote data with caching
pyeye --n3 http://example.org/data.ttl --cache-dir /tmp/cache

# Statistics
pyeye --n3 data.ttl --query rules.n3 --statistics
# → # steps=42 derived=12 time=3.7ms (stderr)
```

See [docs/cli.md](docs/cli.md) for all flags and examples.

---

## Python API Usage

```python
from pyeye import execute
from pyeye.term import NamedNode, Variable, Triple

# Forward chaining — basic
result = execute(
    data_strings=["@prefix : <http://ex.org/> .\n:a :p :b ."],
    rule_strings=["@prefix : <http://ex.org/> .\n{?X :p ?Y} => {?X :q ?Y} ."],
)

# RDFS entailment
result = execute(
    data_strings=["... rdfs:subClassOf triples ..."],
    rule_strings=["... your rules ..."],
    entail=True,
)

# Backward chaining from a goal
result = execute(
    data_strings=["@prefix : <http://ex.org/> .\n:alice :parent :bob ."],
    rule_strings=["@prefix : <http://ex.org/> .\n{?X :parent ?Y} => {?Y :child ?X} ."],
    query=Triple(
        NamedNode("http://ex.org/bob"),
        NamedNode("http://ex.org/child"),
        Variable("X"),
    ),
)
print(result.query_answers)
# [{'X': NamedNode('http://ex.org/alice')}]

# Proof trace
result = execute(
    data_strings=["..."],
    rule_strings=["..."],
    explain=True,
    explain_format="html",
)
# result.explains → HTML string

# Not-entail check
result = execute(
    data_strings=["..."],
    rule_strings=["..."],
    not_entail=Triple(
        NamedNode("http://ex.org/a"),
        NamedNode("http://ex.org/forbidden"),
        NamedNode("http://ex.org/b"),
    ),
)
# result.stats["not_entail_failed"] is True if the triple WAS derived
```

See [docs/api.md](docs/api.md) for the full API reference.

---

## Using Builtins

All built-in functions use the `e:` prefix:

```n3
@prefix : <http://shop.org/> .
@prefix e: <http://eulersharp.sourceforge.net/2003/03swap/log-rules#> .

:widget :price 50 .

# Derive :expensive if price > 30
{ ?Item :price ?P . ?P e:greaterThan "30" } => { ?Item :expensive true } .

# Calculate discounted price
{ ?Item :price ?P . ?P e:times "0.9" ?Final }
    => { ?Item :discountedPrice ?Final } .
```

See [docs/builtins.md](docs/builtins.md) for all 240 built-in functions with examples.

---

## N3 Syntax Example

```n3
@prefix : <http://example.org/> .
@prefix e: <http://eulersharp.sourceforge.net/2003/03swap/log-rules#> .

# Facts
:alice :parent :bob .
:bob   :parent :carol .
:alice :age 70 .

# Rules
{ ?X :parent ?Y }              => { ?Y :child ?X } .
{ ?X :parent ?Y . ?Y :parent ?Z } => { ?X :grandparent ?Z } .

# Rule with builtin and negation
{ ?X :age ?A . ?A e:greaterThan "65" .
  _:n e:onNegativeSurface { ?X :hasCar true } }
    => { ?X :needsTransport true } .
```

See [docs/n3-syntax.md](docs/n3-syntax.md) for the full syntax guide.

---

## Documentation

| Document | Content |
|---|---|
| [Getting Started](docs/getting-started.md) | Concepts, installation, step-by-step tutorial |
| [N3 Syntax](docs/n3-syntax.md) | Every N3 construct: triples, rules, builtins, paths, surfaces, TriG |
| [Builtins](docs/builtins.md) | All 240 built-in functions grouped by category |
| [API Reference](docs/api.md) | `execute()`, `Engine`, term types, store, parser, proofs |
| [CLI Reference](docs/cli.md) | All command-line flags with examples |
| [FAQ](docs/faq.md) | Common questions and troubleshooting |
| [Security](SECURITY.md) | Dangerous builtins, safe mode, SSRF protection |

---

## Architecture

```
pyeye/
├── pyeye/
│   ├── term.py      # NamedNode, Literal, Variable, Triple, Formula, TripleTerm, PathTerm, …
│   ├── unify.py     # Pattern matching and variable binding
│   ├── store.py     # In-memory triple/quad store with predicate + graph indexes
│   ├── parser.py    # Full N3 + TriG recursive-descent parser
│   ├── builtins.py  # 240 built-in functions (all under e: namespace)
│   ├── engine.py    # Euler Abstract Machine: forward + backward chaining
│   ├── proof.py     # ProofStep, ProofTree; N3 / DOT / HTML serializers
│   ├── rdfs.py      # RDFS entailment rules
│   ├── entry.py     # execute() — the public API
│   ├── output.py    # N3Writer — serialize triples to N3 text
│   └── cli.py       # pyeye CLI (argparse → execute())
└── tests/           # Test suite
```

This is a Python 3.11+ port of the reasoning chain:
**eye.pl** (Prolog) → **eyeling** (JavaScript) → **pyeye** (Python)

---

## License

MIT — see `pyproject.toml`.
