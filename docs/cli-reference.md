# CLI Reference

The `pyeye` command lets you run reasoning directly from the terminal, without writing any Python code.

**Source:** `main` — `pyeye/cli.py:12`

## Synopsis

```bash
pyeye [options]
```

## The Two Files You Need

### Data file (`--n3`)

Contains your facts. Can be `.ttl` (Turtle), `.n3` (Notation 3), or TriG format.

```turtle
@prefix : <http://my-family.org/> .

:alice :parent :bob .
:bob :parent :carol .
```

### Rule file (`--query`)

Contains your rules. Must be `.n3` format:

```n3
@prefix : <http://my-family.org/> .

{ ?X :parent ?Y } => { ?Y :child ?X } .
{ ?X :parent ?Y . ?Y :parent ?Z } => { ?X :grandparent ?Z } .
```

---

## All Flags

### Input Flags

| Flag | Phase | Description | Example |
| :--- | :--- | :--- | :--- |
| `--n3 <file>` | 1 | Load facts from N3/Turtle/TriG file. Repeatable. | `--n3 people.ttl --n3 places.ttl` |
| `--query <file>` | 1 | Load rules from N3 file. Repeatable. | `--query family.n3 --query business.n3` |

### Output Flags

| Flag | Phase | Description | When to use it |
| :--- | :--- | :--- | :--- |
| *(none)* | 1 | Show only **new** derived facts | Default — just see what the engine figured out |
| `--pass` | 1 | Show original facts + derived facts | When you want to see the complete picture |
| `--pass-all` | 1 | Show facts + rules + derived facts | For debugging — see everything the engine knows |
| `--nope` | 1 | Show facts only, skip reasoning | When you just want to validate/normalize your data |
| `--explain` | 2 | Include proof explanations | When you need to understand **why** a fact was derived |
| `--explain-format n3\|dot\|html` | 2 | Proof output format (default: n3) | `--explain-format html` for browser view, `dot` for Graphviz |

### Control Flags

| Flag | Phase | Description | Example |
| :--- | :--- | :--- | :--- |
| `--max-inferences N` | 1 | Stop after N reasoning steps | `--max-inferences 100` — limit runtime |
| `--tactic limited-answer N` | 1 | Stop after N derived triples | `--tactic limited-answer 5` — only first 5 new facts |
| `--entail` | 2 | Apply RDFS entailment before user rules | `--entail` — derive subClassOf/subPropertyOf implications |
| `--entail-owl` | 2 | Apply OWL 2 RL entailment (superset of `--entail`) | `--entail-owl` — also derives transitive/symmetric/functional property implications, sameAs, class constructors |
| `--not-entail-triple S,P,O` | 2 | Check that this triple is NOT entailed | `--not-entail-triple http://x/a,http://x/p,http://x/b` |
| `--query-goal S,P,O` | 2 | Backward chain from this triple | `--query-goal http://x/bob,http://x/child,?X` |
| `--no-forward` | 2 | Skip forward chaining (backward only) | `--no-forward` with `--query-goal` for pure backward chaining |
| `--djiti-debug` via `--tactic` | 2 | Print DJITI pattern ordering | For performance analysis |

### Display Flags

| Flag | Phase | Description | Example output |
| :--- | :--- | :--- | :--- |
| `--prefix P=URL` | 1 | Define shortcut for output formatting | `--prefix ex=http://example.org/` |
| `--statistics` | 1 | Print performance info to stderr | `# steps=42 derived=12 time=3.7ms` |
| `--quiet` | 1 | Suppress all stderr output | Use with `--statistics` to hide stats |
| `--cache-dir DIR` | 2 | Cache directory for remote N3 files | `--cache-dir /tmp/pyeye-cache` |
| `--help` | 1 | Show help message | Lists all flags |

**Think of it this way:**

```
No flag:     Only new facts the engine discovered
--pass:      Everything (input + new)
--nope:      Only input (ignore rules)
--entail:    Input + RDFS-derived + new (from user rules)
```

## Exit Codes

| Code | Meaning |
| :--- | :--- |
| `0` | Everything worked |
| `1` | Something went wrong (file not found, bad syntax, blocked URL, etc.) |

Error messages go to stderr and look like:

```
pyeye: error: at line 1 of <>:
Bad syntax (expected directive or statement) at ^ in:
"b''^b'=> {:a :b :c} .\n'"
```

---

## Examples

### Example 1: Basic derivation

```bash
pyeye --n3 data.ttl --query rules.n3
```

Derive new facts and print them to stdout.

### Example 2: With RDFS entailment

```bash
pyeye --n3 data.ttl --query rules.n3 --entail --pass --statistics
```

Apply RDFS rules first, then user rules, show everything, and print timing.

### Example 3: Validate data without reasoning

```bash
pyeye --n3 messy-data.ttl --nope
```

Just load and re-emit the data. Useful for checking if your N3/Turtle files parse correctly.

### Example 4: Proof traces

```bash
pyeye --n3 data.ttl --query rules.n3 --explain --explain-format html > proof.html
```

Generate an HTML proof tree showing why each fact was derived.

### Example 5: Backward chaining from a goal

```bash
pyeye --n3 data.ttl --query rules.n3 --query-goal http://ex.org/bob,http://ex.org/child,?X
```

Find all bindings for `?X` where `:bob :child ?X` is true.

### Example 6: Not-entail check

```bash
pyeye --n3 data.ttl --query rules.n3 --not-entail-triple http://ex.org/a,http://ex.org/notDerived,http://ex.org/x
```

Verify that a specific triple is NOT derivable. Exit 0 if the check passes.

### Example 7: Cache remote files

```bash
pyeye --n3 http://example.org/data.ttl --query http://example.org/rules.n3 --cache-dir /tmp/cache
```

Fetch remote files and cache them locally for future runs.

### Example 8: Limit derivations

```bash
pyeye --n3 big-data.ttl --query rules.n3 --tactic limited-answer 10
```

Only derive the first 10 new facts, then stop. Useful for exploring large rule sets.

### Example 9: Step cap

```bash
pyeye --n3 data.ttl --query rules.n3 --max-inferences 1000
```

Stop after 1000 inference steps. Prevents runaway reasoning on large datasets.

### Example 10: Pipe the output

```bash
pyeye --n3 data.ttl --query rules.n3 --pass | grep ":child"
pyeye --n3 data.ttl --query rules.n3 --statistics 2>&1 >/dev/null
```

pyeye writes N3 to stdout, so you can grep, count, or redirect it like any other command.

### Example 11: Custom prefixes

```bash
pyeye --n3 data.ttl --query rules.n3 --pass --prefix ex=http://example.org/
```

Makes the output use `ex:alice` instead of full URLs.

---

## Stdout vs Stderr

| Stream | Content | Can be piped? |
| :--- | :--- | :--- |
| **stdout** | N3 output (the facts) | Yes — `pyeye ... \| grep ...` |
| **stderr** | Error messages, statistics | Yes — `pyeye ... 2> errors.log` |

This separation means you can pipe the N3 output while still seeing errors on your terminal.
