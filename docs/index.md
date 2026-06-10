# pyeye Documentation

**A pure-Python forward-chaining N3 reasoner.** Give it facts and rules, it derives new facts automatically.

**280+ builtins** · **Forward + backward chaining** · **RDFS + OWL 2 RL entailment** · **MIT licensed**

## Start here

| If you're... | Start with... |
| :--- | :--- |
| **New to all of this** (don't know what N3/RDF/triples are) | Read on — this page explains everything from scratch |
| **Looking for a specific function** | [API Reference](api.md) |
| **Wondering what syntax is allowed** | [N3 Syntax Guide](n3-syntax.md) |
| **Using the command line** | [CLI Reference](cli.md) |
| **Working with builtins** | [Builtins Reference](builtins.md) |
| **Troubleshooting a problem** | [FAQ](faq.md) |
| **Curious how pyeye relates to EYE/eyeling** | [Architecture](architecture-vs-eye.md) |
| **Running untrusted N3** | [Security](../SECURITY.md) — dangerous builtins, safe mode, SSRF protection |

## Document index

| Document | Role |
| :--- | :--- |
| [N3 Syntax](n3-syntax.md) | The language: triples, rules, lists, paths, negation, named graphs, RDF-star, sugar |
| [Builtins](builtins.md) | All built-in functions grouped by namespace, with calling conventions |
| [API Reference](api.md) | `execute()`, `Engine`, term types, store, parser, proofs |
| [CLI Reference](cli.md) | All command-line flags, exit codes, and examples |
| [FAQ](faq.md) | Common questions, troubleshooting, debugging recipes |
| [Architecture](architecture-vs-eye.md) | Subsystem-by-subsystem mapping to the EYE and eyeling reference reasoners |

The `examples/` directory in the repository contains 35 runnable, self-contained programs, from a single-fact hello-world to a full RBAC policy engine — see the [examples index](../examples/README.md).

---

## What is pyeye?

pyeye is a **reasoning engine**: you give it facts and rules written in a notation called N3, and it automatically derives new facts. It is a port of the EYE reasoner (originally written in Prolog, also ported to JavaScript as eyeling) and implements the same Euler Abstract Machine. The only runtime dependency is `rdflib`.

1. **Facts** — things you know (e.g., "Alice is Bob's parent")
2. **Rules** — patterns to follow (e.g., "if X is Y's parent, then Y is X's child")
3. **Derived facts** — things it figured out (e.g., "Bob is Alice's child")

Think of it as a declarative inference layer: instead of writing a chain of `if/elif/else` statements to propagate information through your data, you describe the relationships once as rules, and pyeye finds all the consequences. The rules are data, not code: store them in files, load them at runtime, combine multiple rule sets, and audit which rules fired.

Problems pyeye is well-suited for:

- Policy engines (RBAC, access control)
- Knowledge graph enrichment
- Configuration management with layered defaults
- Constraint validation (SHACL-like)
- Ontology reasoning (RDFS, OWL 2 RL)
- Event correlation and complex event processing

It runs locally — no cloud, no API calls, no data leaving your machine.

---

## Install

```bash
git clone https://github.com/TigreGotico/pyeye
cd pyeye
pip install -e .
```

Requires Python 3.11 or newer.

---

## Your first example

The smallest possible pyeye program: one fact, one rule, one derived triple.

```python
from pyeye import execute

result = execute(
    data_strings=["""
        @prefix : <http://example.org/> .
        :sky :colour :blue .
    """],
    rule_strings=["""
        @prefix : <http://example.org/> .
        { :sky :colour :blue } => { :sky :isColoured :blue } .
    """],
)

print(result.triples)
```

Output:

```
:sky :isColoured :blue .
```

`data_strings` holds your facts; `rule_strings` holds your rules. pyeye parses both, runs forward chaining until no new facts can be derived, and returns a `Result` object. `result.triples` is an N3 string of every derived fact.

---

## Mental model

**Facts are triples.** An RDF triple is a statement with exactly three parts: subject, predicate, object. Think of it as a row in a three-column table:

| Subject | Predicate | Object |
|---------|-----------|--------|
| `:alice` | `:parent` | `:bob` |
| `:bob` | `:age` | `42` |
| `:sky` | `:colour` | `:blue` |

In N3 notation, a triple looks like:

```n3
:alice :parent :bob .
```

The dot at the end terminates the statement. The `:` prefix is an abbreviation for a namespace (declared with `@prefix`). Full IRIs like `<http://example.org/alice>` are also valid.

**Rules are patterns with `=>`.** A rule has a body on the left and a head on the right, each written as `{ ... }`. Variables start with `?`. When the body matches something in the fact store, the head is derived as a new fact:

```n3
{ ?X :parent ?Y } => { ?Y :child ?X } .
```

Read this as: "For every X and Y where X is a parent of Y, conclude that Y is a child of X."

**The engine finds all consequences.** It applies every rule to every possible matching of facts, adds the new facts, then applies rules again — until no new facts emerge. This is called reaching a *fixpoint*. It is called *forward chaining* because you start from facts and move forward toward conclusions.

---

## Five-minute tour

### Step 1: Multiple facts

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

        { ?X :parent ?Y } => { ?Y :child ?X } .
        { ?X :parent ?Y . ?Y :parent ?Z } => { ?X :grandparent ?Z } .
    """],
)

print(result.triples)
```

Output (order may vary):

```n3
:bob   :child :alice .
:carol :child :bob .
:alice :grandparent :carol .
```

Three facts derived from two. The grandparent rule has two body patterns separated by a period — both must match simultaneously. The engine finds every combination of facts that satisfies all patterns.

### Step 2: Numeric comparisons

```python
result = execute(
    data_strings=["""
        @prefix : <http://example.org/> .
        :alice :age 70 .
        :bob   :age 45 .
    """],
    rule_strings=["""
        @prefix : <http://example.org/> .
        @prefix math: <http://www.w3.org/2000/10/swap/math#> .

        { ?P :age ?A . ?A math:greaterThan 65 } => { ?P :isSenior true } .
    """],
)

print(result.triples)
```

Output:

```n3
:alice :isSenior true .
```

`math:greaterThan` is a *builtin filter*: it does not produce a value, it just passes or fails. If it fails, the rule does not fire for that binding.

### Step 3: Computations

```python
result = execute(
    data_strings=["""
        @prefix : <http://example.org/> .
        :item1 :price 100 .
        :item2 :price 50  .
    """],
    rule_strings=["""
        @prefix : <http://example.org/> .
        @prefix math: <http://www.w3.org/2000/10/swap/math#> .

        { ?I :price ?P . (?P 0.9) math:product ?Sale }
            => { ?I :salePrice ?Sale } .
    """],
)

print(result.triples)
```

Output:

```n3
:item1 :salePrice 90.0 .
:item2 :salePrice 45.0 .
```

When a builtin computes a value, the inputs go into a list `(?P 0.9)` and the output goes into the variable after the builtin name (`?Sale`). The list syntax `(a b c)` is how N3 passes multiple arguments to builtins that produce results.

### Step 4: Include original facts in output

By default `result.triples` contains only *derived* facts. Pass `pass_mode=True` to include input facts:

```python
result = execute(
    data_strings=["""
        @prefix : <http://example.org/> .
        :alice :age 70 .
    """],
    rule_strings=["""
        @prefix : <http://example.org/> .
        @prefix math: <http://www.w3.org/2000/10/swap/math#> .
        { ?P :age ?A . ?A math:greaterThan 65 } => { ?P :isSenior true } .
    """],
    pass_mode=True,
)
print(result.triples)
# :alice :age 70 .
# :alice :isSenior true .
```

### Step 5: Statistics

```python
print(result.stats)
# {'steps': 1, 'derived': 1, 'time_ms': 0.8, 'not_entail_failed': False}
```

`steps` is the number of rule firings; `derived` is the number of new triples; `time_ms` is wall-clock time in milliseconds.

### From the command line

```bash
pyeye --n3 family.ttl --query rules.n3 --pass --statistics --entail
# steps=3 derived=3 time=1.2ms   ← printed to stderr
```

---

## Key features

| Feature | Description |
| :--- |---|
| Forward chaining | Euler Abstract Machine: apply rules until fixpoint |
| Backward chaining | Goal-directed reasoning with tabling (memoization) |
| Cycle detection | Prevents infinite loops when rules re-derive existing facts |
| Predicate indexing | Fast lookup when the predicate is a concrete NamedNode |
| DJITI indexing | Most-constrained-first join ordering for performance |
| Incremental reasoning | `add_triple()` after rules triggers immediate re-evaluation |
| RDFS entailment | subClassOf, subPropertyOf, domain, range inference |
| OWL 2 RL entailment | Transitive/symmetric/functional properties, sameAs, class constructors |
| 280+ builtins | `math:`, `string:`, `list:`, `log:`, `time:`, `crypto:`, `graph:`, `reason:`, `e:`, XPath/RIF function namespaces |
| Proof traces | N3, DOT (Graphviz), HTML, and EYE-compatible `reason:` proof output |
| Full N3 grammar | Triple terms, formula terms, paths, sets, has/is/of sugar, negative surfaces |
| TriG named graphs | `GRAPH <g> { ... }` syntax with graph-scoped queries |
| HTTP data loading | Remote files with caching, SSRF protection |
| Not-entail checking | Verify a triple is NOT derivable |

---

## What to read next

| Document | What you will learn |
|---|---|
| [N3 Syntax](n3-syntax.md) | Variables, lists, negation, backward rules, named graphs, RDF-star, blank nodes |
| [Builtins](builtins.md) | All built-in functions: math, string, list, time, crypto, log, graph |
| [API Reference](api.md) | Full `execute()` parameters, `Engine` class, term types, proof traces |
| [CLI Reference](cli.md) | Running pyeye from the command line |
| [FAQ](faq.md) | Common problems and troubleshooting |
