# pyeye Documentation

**A pure-Python reasoning engine.** Give it facts and rules, it derives new facts automatically.

## Start Here

| If you're... | Start with... |
| :--- | :--- |
| **New to all of this** (don't know what N3/RDF/triples are) | [Getting Started](getting-started.md) — explains everything from scratch |
| **Familiar with the concepts** but new to pyeye | [Getting Started](getting-started.md) — skip to "Installation" |
| **Looking for a specific function** | [API Reference](api-reference.md) |
| **Wondering what syntax is allowed** | [Syntax Guide](syntax-guide.md) |
| **Using the command line** | [CLI Reference](cli-reference.md) |
| **Troubleshooting a problem** | [FAQ](faq.md) |

## Document Index

| Document | What's in it |
| :--- | :--- |
| [Getting Started](getting-started.md) | What pyeye is, key concepts explained, installation, 5-minute tutorial, examples you can copy |
| [Syntax Guide](syntax-guide.md) | Every N3 construct supported in Phase 1, with progressive examples from simple to complex |
| [Builtins](builtins.md) | All 30 built-in functions with what they do, how to use them, and full worked examples |
| [API Reference](api-reference.md) | Every public function, class, and method with parameter tables and code examples |
| [CLI Reference](cli-reference.md) | All command-line flags, exit codes, and real-world examples |
| [FAQ](faq.md) | Common questions, troubleshooting, "what's this?" explanations, known limitations |

## What is pyeye?

pyeye is a **reasoning engine**. You give it:

1. **Facts** — things you know (e.g., "Alice is Bob's parent")
2. **Rules** — patterns to follow (e.g., "if X is Y's parent, then Y is X's child")

And it produces:

3. **Derived facts** — things it figured out (e.g., "Bob is Alice's child")

It's written in Python, requires only one dependency (`rdflib`), and runs locally — no cloud, no API calls, no data leaving your machine.

## Quick Example

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
        "{ ?X :parent ?Y } => { ?Y :child ?X } .\n"
        "{ ?X :parent ?Y . ?Y :parent ?Z } => { ?X :grandparent ?Z } .\n",
    ],
)

print(result.triples)
# :bob :child :alice .
# :carol :child :bob .
# :alice :grandparent :carol .
```

Or from the command line:

```bash
pyeye --n3 family.ttl --query rules.n3 --pass --statistics
# steps=3 derived=3 time=1.2ms
```

## Project Structure

```
pyeye/
├── pyeye/             # Source code
│   ├── term.py        # Data types: NamedNode, Literal, Variable, Triple, etc.
│   ├── unify.py       # Pattern matching engine
│   ├── store.py       # In-memory triple database
│   ├── parser.py      # Reads N3 text into rules and facts
│   ├── builtins.py    # Built-in functions (math, strings, time, etc.)
│   ├── engine.py      # The reasoning loop (Euler Abstract Machine)
│   ├── entry.py       # execute() — the main API
│   ├── output.py      # Writes triples back to N3 text
│   └── cli.py         # Command-line interface
├── tests/             # 154 tests
├── docs/              # This documentation
├── spec.md            # Functional specification
├── plan.md            # Implementation plan
├── audit.md           # Code audit findings
└── status.md          # Development progress tracker
```

## Source Code References

All documentation cites source code in the format `` `ClassName.method` — `path/to/file.py:LINE` `` per the Zero-Stale Policy.

| Module | Source file |
| :--- | :--- |
| Term types | `pyeye/term.py` |
| Unification | `pyeye/unify.py` |
| Triple store | `pyeye/store.py` |
| N3 parser | `pyeye/parser.py` |
| Builtins | `pyeye/builtins.py` |
| Reasoning engine | `pyeye/engine.py` |
| Entry API | `pyeye/entry.py` |
| N3 writer | `pyeye/output.py` |
| CLI | `pyeye/cli.py` |
