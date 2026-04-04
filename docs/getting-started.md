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

print("Derived", result.stats["derived"], "triples in",
      result.stats["time_ms"]:.1f, "ms")

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

## What can you build with this?

### Example: Smart Home Rules

```n3
# If temperature is above 30, turn on AC
{ ?Room :temperature ?T . ?T math:greaterThan "30" } => { ?Room :acOn true } .

# If it's after 10pm and someone is in the room, dim lights
{ ?Room :occupied true . time:now ?Now . ?Now time:hour ?H . ?H math:greaterThan "22" }
    => { ?Room :lightsDimmed true } .
```

### Example: Business Logic

```n3
# If an order total is above $1000, flag for review
{ ?Order :total ?T . ?T math:greaterThan "1000" } => { ?Order :needsReview true } .

# If a customer has 3+ orders, mark as VIP
{ ?C :ordered ?A . ?C :ordered ?B . ?C :ordered ?D .
  FILTER(?A != ?B && ?A != ?D && ?B != ?D) } => { ?C :vip true } .
```

### Example: Family Trees (as above)

Parents → children → grandparents → siblings → etc. One set of rules, automatic derivation of all relationships.

---

## What's next?

| If you want to... | Read this |
| :--- | :--- |
| Understand the N3 syntax in detail | [Syntax Guide](syntax-guide.md) |
| Use built-in functions (math, strings, dates) | [Builtins Reference](builtins.md) |
| See every function and class | [API Reference](api-reference.md) |
| Use the command-line tool | [CLI Reference](cli-reference.md) |
| Troubleshoot problems | [FAQ](faq.md) |

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
| **Fixpoint** | The point where no more new facts can be derived — the engine stops |
| **Builtin** | A built-in function like math operations, string manipulation, or time functions |
| **N3** | "Notation 3" — the text format for writing facts and rules |
| **Turtle** | A simpler format for writing facts only (no rules). N3 extends Turtle with rules |
| **Blank node** | An anonymous thing with a unique ID you don't control. Written as `[]` |
| **Existential** | Another name for a blank node or generated unique ID |
| **Skolem constant** | An auto-generated unique ID, named after the logician Skolem |
| **Deductive closure** | All facts — both original and derived — after reasoning completes |
