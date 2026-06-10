# pyeye

A pure-Python port of the [EYE](https://eulersharp.sourceforge.net/) N3 reasoning engine. Give it facts and rules in [Notation3](https://w3c.github.io/N3/spec/); it derives new facts automatically using forward and backward chaining.

**Python 3.11+ · MIT License · One dependency (`rdflib`)**

---

## What it does

pyeye is a **reasoning engine**. You write:

- **Facts** — things you know (`:alice :parent :bob .`)
- **Rules** — patterns to follow (`{ ?X :parent ?Y } => { ?Y :child ?X } .`)

And it produces:

- **Derived facts** — things it figured out (`:bob :child :alice .`)

It implements the Euler Abstract Machine with forward chaining, backward chaining, RDFS entailment, OWL 2 RL entailment, DJITI join ordering, proof tree output, and 280+ built-in functions across all standard W3C SWAP namespaces.

---

## Install

```bash
git clone https://github.com/TigreGotico/pyeye
cd pyeye
pip install -e .
```

Requires Python 3.11 or newer. The only runtime dependency is `rdflib >= 6.0`.

---

## Quick Start

### Python API

```python
from pyeye import execute

result = execute(
    data_strings=["""
        @prefix : <http://example.org/> .
        :alice :parent :bob .
        :bob   :parent :carol .
    """],
    rule_strings=["""
        @prefix : <http://example.org/> .
        { ?X :parent ?Y }                   => { ?Y :child ?X } .
        { ?X :parent ?Y . ?Y :parent ?Z }   => { ?X :grandparent ?Z } .
    """],
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
```

---

## Features

| Feature | Description |
|---|---|
| Forward chaining | Euler Abstract Machine — apply rules to fixpoint |
| Backward chaining | Goal-directed reasoning with tabling (memoization) |
| RDFS entailment | `subClassOf`, `subPropertyOf`, `domain`, `range` inference |
| OWL 2 RL entailment | `sameAs`, transitive/symmetric/functional properties, class constructors |
| DJITI indexing | Most-constrained-first join ordering for performance |
| Incremental reasoning | `add_triple()` triggers immediate re-evaluation |
| Proof traces | N3, DOT (Graphviz), and HTML proof tree output |
| 280+ builtins | `math:`, `log:`, `string:`, `list:`, `crypto:`, `time:`, `graph:`, `reason:`, `e:` |
| TriG named graphs | `GRAPH <g> { ... }` syntax |
| BLOGIC negation | `log:onNegativeSurface { ... }` — negation as failure |
| Not-entail checking | Verify a triple is NOT derivable |
| Triple terms | `<< S P O >>` — RDF-star reified triples |
| Path expressions | `!` (forward) and `^` (reverse) paths, compiled to intermediate triples at parse time |

---

## CLI Usage

```bash
# Derive new facts only
pyeye --n3 data.ttl --query rules.n3

# Show input + derived (deductive closure)
pyeye --n3 data.ttl --query rules.n3 --pass

# RDFS entailment before user rules
pyeye --n3 data.ttl --query rules.n3 --entail

# OWL 2 RL entailment (superset of RDFS)
pyeye --n3 data.ttl --query rules.n3 --entail-owl

# Proof tree (HTML)
pyeye --n3 data.ttl --query rules.n3 --explain --explain-format html > proof.html

# Backward chain from a goal
pyeye --n3 data.ttl --query rules.n3 --query-goal "http://ex.org/bob,http://ex.org/child,?X"

# Statistics
pyeye --n3 data.ttl --query rules.n3 --statistics
# → # steps=42 derived=12 time=3.7ms  (stderr)
```

See [docs/cli.md](docs/cli.md) for all flags.

---

## Python API

```python
from pyeye import execute
from pyeye.term import NamedNode, Variable, Triple

# RDFS entailment
result = execute(
    data_strings=["...rdfs:subClassOf triples..."],
    rule_strings=["...your rules..."],
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
# [{'X': NamedNode('http://ex.org/alice')}]  # keyed by variable name

# Proof trace
result = execute(data_strings=["..."], rule_strings=["..."], explain=True, explain_format="html")
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

## Builtins

Builtins use canonical W3C SWAP namespace URIs. The `e:` prefix is reserved for EYE-specific extensions with no SWAP equivalent.

```n3
@prefix :    <http://example.org/> .
@prefix math: <http://www.w3.org/2000/10/swap/math#> .
@prefix str:  <http://www.w3.org/2000/10/swap/string#> .
@prefix list: <http://www.w3.org/2000/10/swap/list#> .

:widget :price 50 ; :tags ("sale" "clearance") .

# Derive :expensive if price > 30
{ ?Item :price ?P . ?P math:greaterThan 30 } => { ?Item :expensive true } .

# Discounted price
{ ?Item :price ?P . (?P 0.9) math:product ?Final }
    => { ?Item :discountedPrice ?Final } .

# Tag count
{ ?Item :tags ?L . ?L list:length ?N }
    => { ?Item :tagCount ?N } .
```

| Namespace | Prefix | Count | Examples |
|---|---|---|---|
| `http://www.w3.org/2000/10/swap/math#` | `math:` | 44 | `greaterThan`, `sum`, `product`, `sin`, `floor` |
| `http://www.w3.org/2000/10/swap/log#` | `log:` | 44 | `skolem`, `content`, `onNegativeSurface`, `implies` |
| `http://www.w3.org/2000/10/swap/string#` | `string:` | 30 | `contains`, `concat`, `replace`, `matches` |
| `http://www.w3.org/2000/10/swap/list#` | `list:` | 27 | `in`, `length`, `append`, `sort`, `unique` |
| `http://www.w3.org/2000/10/swap/time#` | `time:` | 13 | `now`, `year`, `month`, `hour`, `timeZone` |
| `http://www.w3.org/2000/10/swap/crypto#` | `crypto:` | 5 | `md5`, `sha`, `sha256`, `sha512` |
| `http://www.w3.org/2000/10/swap/graph#` | `graph:` | 9 | `member`, `difference`, `union` |
| `http://www.w3.org/2000/10/swap/reason#` | `reason:` | 9 | `because`, `binding`, `rule`, `source` |
| `http://eulersharp.sourceforge.net/2003/03swap/log-rules#` | `e:` | ~45 | `calculate`, `findall`, `closure`, `exec`, `sigmoid` |

See [docs/builtins.md](docs/builtins.md) for the full list with descriptions and examples.

---

## N3 Syntax Example

```n3
@prefix :    <http://example.org/> .
@prefix math: <http://www.w3.org/2000/10/swap/math#> .
@prefix log:  <http://www.w3.org/2000/10/swap/log#> .

# Facts
:alice :parent :bob .
:bob   :parent :carol .
:alice :age 70 .

# Transitivity rule
{ ?X :parent ?Y }                   => { ?Y :child ?X } .
{ ?X :parent ?Y . ?Y :parent ?Z }   => { ?X :grandparent ?Z } .

# Rule with builtin + negation
{ ?X :age ?A . ?A math:greaterThan 65 .
  _:n log:onNegativeSurface { ?X :hasCar true } }
    => { ?X :needsTransport true } .
```

See [docs/n3-syntax.md](docs/n3-syntax.md) for the full syntax guide.

---

## Documentation

| Document | Content |
|---|---|
| [Documentation Index](docs/index.md) | Concepts, installation, step-by-step tutorial |
| [N3 Syntax](docs/n3-syntax.md) | Triples, rules, builtins, paths, surfaces, TriG, RDF-star |
| [Builtins](docs/builtins.md) | All 280+ built-in functions grouped by namespace |
| [API Reference](docs/api.md) | `execute()`, `Engine`, term types, store, parser, proofs |
| [CLI Reference](docs/cli.md) | All command-line flags with examples |
| [FAQ](docs/faq.md) | Common questions and troubleshooting |

---

## Architecture

```
pyeye/
├── term.py       NamedNode, Literal, Variable, Triple, Formula, ListTerm, TripleTerm
├── unify.py      Pattern matching and variable binding
├── store.py      In-memory triple/quad store with predicate + subject + object indexes
├── parser.py     Full N3 + TriG recursive-descent parser
├── builtins.py   280+ built-in functions (canonical W3C SWAP namespaces)
├── engine.py     Euler Abstract Machine: forward + backward chaining + DJITI
├── proof.py      ProofStep, ProofTree; N3 / DOT / HTML serializers
├── rdfs.py       RDFS entailment rules
├── owl.py        OWL 2 RL entailment rules
├── entry.py      execute() — the public API
├── output.py     N3Writer — serialize triples to N3 text
└── cli.py        pyeye CLI (argparse → execute())
```

Implementation lineage: **eye.pl** (Prolog) → **eyeling** (JavaScript) → **pyeye** (Python). pyeye follows eyeling's shape — an explicit term model and unifier rather than a Prolog substrate. See [docs/architecture-vs-eye.md](docs/architecture-vs-eye.md) for the subsystem-by-subsystem mapping.

---

## Conformance

pyeye is validated against the upstream EYE `reasoning/` scenario corpus
(`run_corpus.py [--only SUBSTR]`, `tests/test_eye_corpus.py`). Outputs are
compared semantically: both sides are parsed with pyeye's own N3 parser and
matched as canonical fact sets under a blank-node/skolem/variable mapping, so
label and serialization choices don't affect the verdict. It currently passes
**94 of 126** plain-answer EYE reasoning scenarios, including the four W3C
EARL meta-suite reports and eight full `r:Proof` proof-trace scenarios; every
non-passing scenario is listed in the suite's XFAIL registry with its
root-cause cluster (Prolog-interop builtins, dateTime interval reasoning,
output-structure mismatches, deep-recursion timeouts). The unit suite
(`tests/`, excluding the slow corpus) is green.

pyeye is an AI-assisted port: the code is written by [Claude](https://claude.ai)
(Anthropic) under human direction, against the EYE and eyeling source.

---

## License

MIT — see `LICENSE`.
