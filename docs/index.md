# pyeye Documentation

**A pure-Python forward-chaining N3 reasoner.** Give it facts and rules, it derives new facts automatically.

**240 builtins** · **Forward + backward chaining** · **RDFS + OWL 2 RL entailment**

## Start Here

| If you're... | Start with... |
| :--- | :--- |
| **New to all of this** (don't know what N3/RDF/triples are) | [Getting Started](getting-started.md) — explains everything from scratch |
| **Familiar with the concepts** but new to pyeye | [Getting Started](getting-started.md) — skip to "Installation" |
| **Looking for a specific function** | [API Reference](api.md) |
| **Wondering what syntax is allowed** | [N3 Syntax Guide](n3-syntax.md) |
| **Using the command line** | [CLI Reference](cli.md) |
| **Working with builtins** | [Builtins Reference](builtins.md) — 240 functions under the `e:` namespace |
| **Troubleshooting a problem** | [FAQ](faq.md) |
| **Running untrusted N3** | [Security](../SECURITY.md) — dangerous builtins, safe mode, SSRF protection |

## Document Index

| Document | What's in it |
| :--- | :--- |
| [Getting Started](getting-started.md) | What pyeye is, key concepts explained, installation, 5-minute tutorial, backward chaining, proofs, entailment |
| [N3 Syntax](n3-syntax.md) | Every N3 construct: triple terms, formula terms, paths, sets, has/is/of sugar, BLOGIC, TriG |
| [Syntax Guide](syntax-guide.md) | Same as N3 Syntax — alternative entry point |
| [Builtins](builtins.md) | All 240 built-in functions grouped by category, all under the `e:` namespace |
| [API Reference](api.md) | Every public function, class, and method with parameter tables and code examples |
| [API Reference (alt)](api-reference.md) | Same as API Reference — alternative entry point |
| [CLI Reference](cli.md) | All command-line flags, exit codes, and real-world examples |
| [CLI Reference (alt)](cli-reference.md) | Same as CLI Reference — alternative entry point |
| [FAQ](faq.md) | Common questions, troubleshooting, "what's this?" explanations, security guidance |

## What is pyeye?

pyeye is a **reasoning engine**. You give it:

1. **Facts** — things you know (e.g., "Alice is Bob's parent")
2. **Rules** — patterns to follow (e.g., "if X is Y's parent, then Y is X's child")

And it produces:

3. **Derived facts** — things it figured out (e.g., "Bob is Alice's child")

It's written in Python, requires only one dependency (`rdflib`), and runs locally — no cloud, no API calls, no data leaving your machine.

## Key Features

| Feature | Description |
| :--- |---|
| Forward chaining | Euler Abstract Machine: apply rules until fixpoint |
| Backward chaining | Goal-directed reasoning with tabling (memoization) |
| Cycle detection | Prevents infinite loops when rules re-derive existing facts |
| Predicate indexing | O(1) lookup when predicate is a concrete NamedNode |
| DJITI indexing | Most-constrained-first join ordering for performance |
| Incremental reasoning | `add_triple()` after rules triggers immediate re-evaluation |
| RDFS entailment | subClassOf, subPropertyOf, domain, range inference |
| OWL 2 RL entailment | Transitive/symmetric/functional properties, sameAs, class constructors |
| 240 builtins | All under `e:` (`http://eulersharp.sourceforge.net/2003/03swap/log-rules#`): Math(44), String(28+), List(27), Log(34+), Crypto(5), Time(9), Graph(9), E/misc(89+) |
| Proof traces | N3, DOT (Graphviz), and HTML proof tree output |
| Full N3 grammar | Triple terms, formula terms, paths, sets, has/is/of sugar, BLOGIC |
| TriG named graphs | `GRAPH <g> { ... }` syntax with graph-scoped queries |
| HTTP data loading | Remote files with SHA-256 cache, SSRF protection |
| Not-entail checking | Verify a triple is NOT derivable |

## Quick Example

```python
from pyeye import execute

result = execute(
    data_strings=[
        """
        @prefix : <http://example.org/> .
        :alice :parent :bob .
        :bob :parent :carol .
        """,
    ],
    rule_strings=[
        """
        @prefix : <http://example.org/> .
        { ?X :parent ?Y } => { ?Y :child ?X } .
        { ?X :parent ?Y . ?Y :parent ?Z } => { ?X :grandparent ?Z } .
        """,
    ],
)

print(result.triples)
# :bob :child :alice .
# :carol :child :bob .
# :alice :grandparent :carol .
```

Or from the command line:

```bash
pyeye --n3 family.ttl --query rules.n3 --pass --statistics --entail
# steps=3 derived=3 time=1.2ms   ← printed to stderr
```

## Project Structure

```
pyeye/
├── pyeye/             # Source code
│   ├── term.py        # Data types: NamedNode, Literal, Variable, Triple, TripleTerm, FormulaTerm, PathTerm, Quad, NegativeSurface
│   ├── unify.py       # Pattern matching engine (forward + bidirectional unification)
│   ├── store.py       # In-memory triple/quad database with predicate + graph indexing
│   ├── parser.py      # Full N3 + TriG recursive descent parser
│   ├── builtins.py    # 240 built-in functions (all under the e: namespace)
│   ├── engine.py      # Euler Abstract Machine: forward/backward chaining, DJITI, incremental
│   ├── proof.py       # Proof trace: ProofStep, ProofTree, N3/DOT/HTML serializers
│   ├── rdfs.py        # RDFS entailment: subClassOf, subPropertyOf, domain, range
│   ├── owl.py         # OWL 2 RL entailment: sameAs, transitive/symmetric/functional, class constructors
│   ├── entry.py       # execute() — the main API
│   ├── output.py      # N3/TriG writer with prefix abbreviation
│   └── cli.py         # Command-line interface
├── tests/             # 312 tests
├── docs/              # This documentation
├── SECURITY.md        # Security model, dangerous builtins, safe mode
├── spec.md            # Phase 1 functional specification
├── spec-phase2.md     # Phase 2 functional specification
├── plan.md            # Implementation plan
├── audit.md           # Phase 1 code audit
├── audit-phase2.md    # Phase 2 code audit
└── status-phase2.md   # Development progress tracker
```

## Source Code References

All documentation cites source code in the format `` `ClassName.method` — `path/to/file.py:LINE` `` per the Zero-Stale Policy.

| Module | Source file |
| :--- | :--- |
| Term types | `pyeye/term.py` |
| Unification | `pyeye/unify.py` |
| Triple/quad store | `pyeye/store.py` |
| N3/TriG parser | `pyeye/parser.py` |
| Builtins (240 functions) | `pyeye/builtins.py` |
| Reasoning engine | `pyeye/engine.py` |
| Proof traces | `pyeye/proof.py` |
| RDFS entailment | `pyeye/rdfs.py` |
| OWL 2 RL entailment | `pyeye/owl.py` |
| Entry API | `pyeye/entry.py` |
| N3/TriG writer | `pyeye/output.py` |
| CLI | `pyeye/cli.py` |
