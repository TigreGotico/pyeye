# Getting Started with pyeye

## What is this?

**pyeye** is a *reasoning engine*. You give it **facts** and **rules**, and it **derives new facts** automatically.

Think of it like this:

```
Facts:    "Alice is Bob's parent."
          "Bob is Carol's parent."

Rule:     "If X is Y's parent, then Y is X's child."

Result:   "Bob is Alice's child."     ← derived automatically
          "Carol is Bob's child."     ← derived automatically
```

The engine figures out consequences you didn't explicitly state. This is called **logical inference** or **forward chaining**.

---

## Key Concepts (explained simply)

### Facts are "triples"

Every fact has three parts: **Subject → Predicate → Object**.

| Subject | Predicate | Object |
| :--- | :--- | :--- |
| Alice | is parent of | Bob |
| Bob | is parent of | Carol |
| Sky | has color | blue |
| Water | boils at | 100°C |

In pyeye, these are written in a format called **N3** (Notation 3):

```n3
:alice :parent :bob .
:bob :parent :carol .
:sky :color :blue .
:water :boilsAt "100" .
```

The colon `:` is shorthand — you define what it means once, then reuse it everywhere. Think of it like defining a variable.

### Rules connect facts

A rule says: **"when you see this pattern, produce that pattern."**

```n3
{ ?X :parent ?Y } => { ?Y :child ?X } .
```

Read this as: *"Whenever you find that X is Y's parent, also record that Y is X's child."*

- `?X` and `?Y` are **variables** — they match any value.
- The part before `=>` is the **body** (what to look for).
- The part after `=>` is the **head** (what to produce).

### Reasoning is automatic

Once you load facts and rules, the engine:

1. **Scans** all facts looking for rule body matches
2. **Derives** new facts from the head of matching rules
3. **Repeats** — new facts might trigger more rules
4. **Stops** when nothing new can be derived (this is called a **fixpoint**)

The whole process is deterministic — same input always produces the same output.

---

## Installation

```bash
# Clone or navigate to the pyeye directory
cd /path/to/pyeye

# Create a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate

# Install pyeye
pip install -e .
```

That's it. The only dependency is `rdflib` (installed automatically), which is used to read data files.

**Requirement:** Python 3.11 or newer.

---

## Your First Rule (5 minutes)

### Step 1: Create a data file

Create a file called `family.ttl`:

```turtle
@prefix : <http://my-family.org/> .

:alice :parent :bob .
:bob :parent :carol .
```

This says: Alice is Bob's parent, and Bob is Carol's parent.

**What's `@prefix` doing?** It's like a find-and-replace. Everywhere you write `:something`, it expands to `http://my-family.org/something`. This gives every fact a unique web address (called an IRI) so there's never confusion about what `:alice` means.

### Step 2: Create a rule file

Create a file called `rules.n3`:

```n3
@prefix : <http://my-family.org/> .

{ ?X :parent ?Y } => { ?Y :child ?X } .
```

This says: if X is Y's parent, then Y is X's child.

**What are `?X` and `?Y`?** They're variables — placeholders that match any value. When the engine finds a fact matching the left side, it plugs the matched values into the right side.

### Step 3: Run it

```bash
pyeye --n3 family.ttl --query rules.n3 --pass
```

Output:

```n3
@prefix  <http://my-family.org/> .

:alice :parent :bob .
:bob :parent :carol .
:bob :child :alice .
:carol :child :bob .
```

The first two facts are your **input**. The last two are **derived** — the engine figured them out from your rule.

The `--pass` flag means "show me everything, including the original facts." Without it, you'd only see the two new derived facts.

### Step 4: Add another rule

Append a second rule to `rules.n3`:

```n3
@prefix : <http://my-family.org/> .

{ ?X :parent ?Y } => { ?Y :child ?X } .
{ ?X :parent ?Y . ?Y :parent ?Z } => { ?X :grandparent ?Z } .
```

Read the second rule: *"If X is Y's parent AND Y is Z's parent, then X is Z's grandparent."*

Notice the `.` between the two body patterns — it means "both must be true."

Run again:

```bash
pyeye --n3 family.ttl --query rules.n3 --pass
```

New output includes:

```n3
:alice :grandparent :carol .
```

The engine connected two facts through the shared variable `?Y` (Bob) and derived a grandparent relationship you never explicitly stated.

---

## Using pyeye from Python

The CLI is great for files, but you can also use pyeye as a Python library:

```python
from pyeye import execute

result = execute(
    data_strings=[
        """
        @prefix : <http://my-family.org/> .
        :alice :parent :bob .
        :bob :parent :carol .
        """,
    ],
    rule_strings=[
        """
        @prefix : <http://my-family.org/> .
        { ?X :parent ?Y } => { ?Y :child ?X } .
        { ?X :parent ?Y . ?Y :parent ?Z } => { ?X :grandparent ?Z } .
        """,
    ],
)

print(f"Derived {result.stats['derived']} triples in {result.stats['time_ms']:.1f}ms")

# Print all triples (input + derived)
for line in result.triples.strip().split("\n"):
    if line and not line.startswith("@prefix"):
        print(" ", line)
```

Output:

```
Derived 3 triples in 1.2ms
  :bob :child :alice .
  :carol :child :bob .
  :alice :grandparent :carol .
```

---

## Phase 2 Features

### RDFS Entailment: Implicit Type Inference

If your data includes type hierarchies, pyeye can derive implicit types:

```python
result = execute(
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
    entail=True,  # ← This enables RDFS entailment
)
```

RDFS derives `:fluffy rdf:type :Animal` from the subClassOf declaration. Then your user rule derives `:fluffy :isAlive true`.

### Backward Chaining: Start with a Question

Instead of deriving everything forward, ask a specific question:

```python
from pyeye.term import NamedNode, Variable, Triple

result = execute(
    data_strings=["@prefix : <http://ex.org/> .\n:alice :parent :bob ."],
    rule_strings=["@prefix : <http://ex.org/> .\n{?X :parent ?Y} => {?Y :child ?X} ."],
    query=Triple(
        NamedNode("http://ex.org/bob"),
        NamedNode("http://ex.org/child"),
        Variable("WhoIsChildOfBob"),
    ),
)

print(result.query_answers)
# [{'WhoIsChildOfBob': NamedNode('http://ex.org/alice')}]
```

### Proof Traces: Understand Why

Want to know **why** a fact was derived?

```python
result = execute(
    data_strings=["@prefix : <http://ex.org/> .\n:a :p :b ."],
    rule_strings=["@prefix : <http://ex.org/> .\n{?X :p ?Y} => {?X :q ?Y} ."],
    explain=True,
    explain_format="html",  # or "n3" or "dot"
)

print(result.explains)
# HTML string with collapsible proof tree
```

### Loading Remote Data

```python
result = execute(
    data_paths=["http://example.org/data.ttl"],
    rule_paths=["http://example.org/rules.n3"],
    cache_dir="/tmp/pyeye-cache",  # Cache remote files
)
```

HTTP loading includes SSRF protection: it rejects URLs targeting private IP ranges and non-HTTP schemes.

### Built-in Functions

pyeye includes 240 built-in functions for math, strings, dates, crypto, graphs, and more. All use the `e:` prefix (`http://eulersharp.sourceforge.net/2003/03swap/log-rules#`):

```python
result = execute(
    data_strings=[
        """
        @prefix : <http://shop.org/> .
        @prefix e: <http://eulersharp.sourceforge.net/2003/03swap/log-rules#> .
        :widget :price 50 .
        """,
    ],
    rule_strings=[
        """
        @prefix : <http://shop.org/> .
        @prefix e: <http://eulersharp.sourceforge.net/2003/03swap/log-rules#> .
        { ?Item :price ?P . ?P e:greaterThan "30" } => { ?Item :expensive true } .
        """,
    ],
)
# :widget :expensive true  (because 50 > 30)
```

See the [Builtins Reference](builtins.md) for the complete list with examples.

---

## What can you build with this?

### Example: Smart Home Rules

```n3
@prefix e: <http://eulersharp.sourceforge.net/2003/03swap/log-rules#> .

# If temperature is above 30, turn on AC
{ ?Room :temperature ?T . ?T e:greaterThan "30" } => { ?Room :acOn true } .

# If it's after 10pm and someone is in the room, dim lights
{ ?Room :occupied true . e:now ?Now . ?Now e:hours ?H . ?H e:greaterThan "22" }
    => { ?Room :lightsDimmed true } .
```

### Example: Business Logic

```n3
@prefix e: <http://eulersharp.sourceforge.net/2003/03swap/log-rules#> .

# If an order total is above $1000, flag for review
{ ?Order :total ?T . ?T e:greaterThan "1000" } => { ?Order :needsReview true } .

# If a customer has 3+ orders, mark as VIP
{ ?C :ordered ?A . ?C :ordered ?B . ?C :ordered ?D .
  ?A e:notEqualTo ?B . ?A e:notEqualTo ?D . ?B e:notEqualTo ?D }
    => { ?C :vip true } .
```

### Example: Family Trees (as above)

Parents → children → grandparents → siblings → etc. One set of rules, automatic derivation of all relationships.

---

## Next Steps

| If you want to... | Read this |
| :--- | :--- |
| Understand the N3 syntax in detail | [N3 Syntax Guide](n3-syntax.md) |
| Use built-in functions (math, strings, dates) | [Builtins Reference](builtins.md) |
| See every function and class | [API Reference](api.md) |
| Use the command-line tool | [CLI Reference](cli.md) |
| Troubleshoot problems | [FAQ](faq.md) |
| Run with untrusted N3 files | [Security](../SECURITY.md) |

---

## Glossary

| Term | What it means |
| :--- | :--- |
| **Triple** | A fact with three parts: subject, predicate, object. Like "Alice → parent → Bob." |
| **IRI** | A unique name for something, like a URL. `http://my-family.org/alice` |
| **Prefix** | A shortcut for an IRI. `:alice` instead of `http://my-family.org/alice` |
| **Variable** | A placeholder that matches any value. Written as `?X`, `?Y`, etc. |
| **Rule** | A pattern: "when you see this, produce that." Written as `{body} => {head}` |
| **Forward chaining** | The reasoning strategy: start with facts, apply rules, derive new facts, repeat |
| **Backward chaining** | Start with a question, find rules whose heads match, recursively prove their bodies |
| **Fixpoint** | The point where no more new facts can be derived — the engine stops |
| **Builtin** | A built-in function like math operations, string manipulation, or time functions |
| **N3** | "Notation 3" — the text format for writing facts and rules |
| **Turtle** | A simpler format for writing facts only (no rules). N3 extends Turtle with rules |
| **TriG** | Turtle with named graphs: `GRAPH <g> { ... }` |
| **Blank node** | An anonymous thing with a unique ID you don't control. Written as `[]` |
| **Existential** | Another name for a blank node or generated unique ID |
| **Skolem constant** | An auto-generated unique ID, named after the logician Skolem |
| **Deductive closure** | All facts — both original and derived — after reasoning completes |
