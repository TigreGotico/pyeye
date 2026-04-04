# Getting Started with pyeye

## Installation

```bash
cd /path/to/pyeye
pip install -e .          # library + rdflib dependency
pip install -e ".[test]"  # + pytest for running tests
```

**Requirements:** Python 3.11+. The only runtime dependency is `rdflib` (used for parsing N3/Turtle data files).

## Quickstart

### 1. One-liner from Python

```python
from pyeye import execute

result = execute(
    data_strings=[
        "@prefix : <http://example.org/> .\n"
        ":alice :parent :bob .\n"
        ":bob :parent :carol .\n",
    ],
    rule_strings=[
        "@prefix : <http://example.org/> .\n"
        "{?X :parent ?Y} => {?Y :child ?X} .\n",
    ],
)

print(result.triples)
# @prefix  <http://example.org/> .
#
# :bob :child :alice .
```

### 2. From the CLI

Save data to `people.ttl`:

```turtle
@prefix : <http://example.org/> .
:alice :parent :bob .
:bob :parent :carol .
```

Save rules to `rules.n3`:

```n3
@prefix : <http://example.org/> .
{:X :parent ?Y} => {?Y :child ?X} .
```

Run:

```bash
pyeye --n3 people.ttl --query rules.n3 --pass
```

With statistics:

```bash
pyeye --n3 people.ttl --query rules.n3 --pass --statistics
# steps=2 derived=2 time=1.2ms   ← printed to stderr
```

## How Reasoning Works

pyeye implements the **Euler Abstract Machine** (EAM), a forward-chaining algorithm:

1. **Parse** data triples (via rdflib) and rule files (via hand-written parser)
2. **Store** triples in an indexed triple store (`pyeye/store.py`)
3. **Iterate** over rules in source order:
   - **Match** each body pattern against the store, accumulating variable bindings
   - **Instantiate** the head with resolved bindings
   - **Assert** new triples (duplicates are silently rejected)
4. **Repeat** until a full pass derives nothing (fixpoint)
5. **Output** derived triples as N3 text

Source: `Engine.run` — `pyeye/engine.py:66`, `Engine._apply_rule` — `pyeye/engine.py:78`

## Term Types

All terms are frozen (immutable) dataclasses, hashable for use in dicts and sets.

| Type | Constructor | Example |
| :--- | :--- | :--- |
| `NamedNode` | `NamedNode("http://ex.org/foo")` | `<http://ex.org/foo>` |
| `Literal` | `Literal("hello")` | `"hello"` |
| `Literal` | `Literal("42", datatype=...)` | `"42"^^xsd:integer` |
| `Literal` | `Literal("bonjour", language="fr")` | `"bonjour"@fr` |
| `Variable` | `Variable("X")` | `?X` |
| `Existential` | `Existential("genid-1")` | `_:genid-1` |
| `Formula` | `Formula((t1, t2))` | `{ ... }` |
| `Triple` | `Triple(s, p, o)` | — |

Source: `pyeye/term.py:12-83`

## Architecture Overview

```
execute()                    entry.py:34
├── load_data_file()         parser.py:459   (rdflib)
├── load_data_string()       parser.py:471   (rdflib)
├── parse_n3()               parser.py:484   (hand-written)
│   ├── tokenize()           parser.py:93
│   └── Parser.parse()       parser.py:143
├── Engine()                 engine.py:32
│   ├── Engine.add_triple()  engine.py:58
│   ├── Engine.add_rule()    engine.py:55
│   └── Engine.run()         engine.py:66
│       ├── _match_formula   engine.py:104
│       ├── _apply_rule      engine.py:78
│       └── _skolemize       engine.py:257
└── N3Writer.write_triples() output.py:25
```

## Next Steps

- [API Reference](api-reference.md) — detailed documentation of every public function
- [CLI Reference](cli-reference.md) — all command-line flags
- [Builtins](builtins.md) — every supported builtin predicate
- [Syntax Guide](syntax-guide.md) — N3 syntax supported in Phase 1
