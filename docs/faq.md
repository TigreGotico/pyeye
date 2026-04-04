# FAQ

## Getting Started

### I have no idea what N3, RDF, or triples are. Where do I start?

Start with the [Getting Started guide](getting-started.md). The first section explains everything in plain English with no jargon.

In the simplest terms: pyeye lets you write **facts** (like "Alice is Bob's parent") and **rules** (like "if X is Y's parent, then Y is X's child"), and it automatically **figures out new facts** you didn't write down (like "Bob is Alice's child").

### Do I need to know programming to use pyeye?

No. You can use it entirely from the command line:

```bash
pyeye --n3 facts.ttl --query rules.n3
```

If you want to use it from Python, you only need to call one function: `execute()`.

### What's the difference between N3 and Turtle?

- **Turtle** is a format for writing facts only. Like a list of statements.
- **N3** extends Turtle with **rules** — "if you see this, then conclude that."

If your file has `=>` in it, it's N3. If it only has facts, it can be either.

### What can I build with this?

Anything where you have data and want to automatically derive new information from it:

- **Family trees**: parents → children → grandparents → siblings
- **Business rules**: "orders over $1000 need review"
- **Smart home**: "if temperature > 30°C, turn on AC"
- **Access control**: "if user is admin, allow access to /settings"
- **Data cleaning**: "if email doesn't contain @, mark as invalid"
- **Knowledge graphs**: connecting facts through shared variables to discover relationships

---

## Installation

### How do I install pyeye?

```bash
cd /path/to/pyeye
pip install -e .
```

That's it. The only dependency is `rdflib`, which is installed automatically.

### What Python version do I need?

Python 3.11 or newer. Check with `python --version`.

### I got an error during installation

Make sure you have a Python virtual environment set up:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

---

## Using pyeye

### My rule isn't firing. What's wrong?

The three most common causes:

1. **Prefix mismatch**: Your data uses `:alice` with one prefix, and your rule uses `:alice` with a different prefix. They look the same but have different full URLs. Use `--pass` to see what the engine actually sees.

2. **Variable names**: `?X` and `?x` are different variables (case-sensitive). Make sure the same variable name appears in both the body and head if you want them connected.

3. **Typo in predicate**: `:parent` vs `:parents` — one letter off, zero matches.

### Why is my output empty?

By default, pyeye only shows **new** facts derived by rules. If no rules fired, the output is empty.

To see everything (including your original facts), add `--pass`:

```bash
pyeye --n3 data.ttl --query rules.n3 --pass
```

Or from Python:

```python
r = execute(..., pass_mode=True)
```

### How do I see what's in the store?

Use `--pass` mode (CLI) or `pass_mode=True` (Python). This shows all facts — both the ones you provided and the ones the engine derived.

### Can I load data from a website?

Not yet. Phase 1 only supports local files and inline strings. HTTP loading is planned for Phase 2.

For now, download the file first:

```bash
curl -o data.ttl https://example.org/data.ttl
pyeye --n3 data.ttl --query rules.n3
```

### Can I use multiple data and rule files?

Yes. Repeat the flag as many times as you need:

```bash
pyeye --n3 file1.ttl --n3 file2.ttl --query rules1.n3 --query rules2.n3
```

---

## Understanding Behavior

### What does "forward chaining" mean?

It means the engine works **forward** from your facts, applying rules to derive new facts, and repeating until nothing new can be found.

Think of it like a detective who starts with clues and follows every lead until there are no new leads to follow.

The alternative (backward chaining) starts with a question and works backward to find supporting facts. pyeye doesn't do that — yet.

### What's a "fixpoint"?

The fixpoint is the moment when a full pass over all rules produces **zero new facts**. The engine stops because there's nothing left to derive.

With small rule sets, this happens in milliseconds. With large ones, you can use `--max-inferences` to stop early.

### Why don't I get infinite loops?

The engine keeps a record of every fact it has derived. If a rule tries to derive a fact that already exists, the engine skips it. This prevents rules like:

```n3
{ ?X :p ?Y } => { ?X :p ?Y } .
```

from running forever — the fact is already in the store, so nothing new is derived, and the engine reaches a fixpoint.

### Why is it slow with lots of data?

Phase 1 uses a straightforward matching strategy: for each rule, try each pattern against every fact in the store. With many rules and many facts, this is O(n × k) where n is the number of facts and k is the number of rule patterns.

**Quick fix:** Use `--max-inferences N` to cap execution.

**Long-term:** Phase 2 will add smarter indexing (DJITI) that dramatically reduces matching time.

---

## Errors

### `pyeye: error: ...`

The CLI caught a problem. Common causes:
- File doesn't exist
- N3 syntax is wrong
- A rule file has invalid syntax

The error message usually tells you what went wrong and where.

### `ParseError: Expected X, got Y`

The N3 parser hit something it didn't expect at a specific position. Check the [Syntax Guide](syntax-guide.md) for what's allowed.

### `TypeError: ... @runtime_checkable ...`

This was a known bug in early versions. Fixed in the audit commit. If you see it, update your code.

---

## Builtins

### What are builtins?

Built-in functions you can call inside rule bodies. Like `math:greaterThan` for comparing numbers, or `string:contains` for searching text.

See the [Builtins Reference](builtins.md) for the full list.

### How do I add my own builtin function?

```python
from pyeye import execute
from pyeye.term import Literal, Variable

def my_function(args, engine):
    # Check if all arguments have values (not variables)
    if any(isinstance(a, Variable) for a in args):
        return None  # Skip — arguments not ready
    # Do your computation
    result = str(args[0].value).upper()  # Example: uppercase
    return Literal(result)

r = execute(
    data_strings=["@prefix : <http://ex.org/> .\n:msg :text \"hello\" ."],
    rule_strings=["@prefix : <http://ex.org/> .\n{?M :text ?T} => {?M :upper ?U} ."],
    builtins={"http://ex.org/upper": my_function},
)
```

---

## Phase 1 vs Phase 2

### What's missing in Phase 1?

| Feature | Phase 1 | Phase 2 |
| :--- | :--- | :--- |
| Forward chaining | ✅ | ✅ |
| Backward chaining | ❌ | Planned |
| Math builtins | ✅ (8) | ✅ (+20 more) |
| String builtins | ✅ (6) | ✅ (+10 more) |
| Full N3 grammar | Partial | ✅ |
| HTTP data loading | ❌ | Planned |
| Proof output | ❌ | Planned |
| Named graphs (TriG) | ❌ | Planned |
| Performance (RETE/DJITI) | Basic index | Planned |

### Should I wait for Phase 2?

If you need basic rule-based reasoning now, Phase 1 is solid — 154 tests pass, the API is stable, and the core reasoning engine is correct.

If you need HTTP loading, full N3 syntax, or proof traces, Phase 2 will add those.

---

## Development

### How do I run the tests?

```bash
cd /path/to/pyeye
source .venv/bin/activate
python -m pytest tests/ -v
```

154 tests, all passing.

### How do I add a new builtin?

1. Add the function to `pyeye/builtins.py`
2. Register it in `BUILTIN_REGISTRY` at the bottom of the file
3. Add a test to `tests/test_fr_coverage.py`
4. Document it in `docs/builtins.md`

### How do I contribute?

1. Fork the repository
2. Create a feature branch
3. Add tests for your changes
4. Open a pull request
