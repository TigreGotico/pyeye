# CLI Reference

The `pyeye` command lets you run reasoning directly from the terminal, without writing any Python code.

**Source:** `main` — `pyeye/cli.py:9`

---

## Basic Usage

```bash
pyeye --n3 facts.ttl --query rules.n3
```

This reads facts from `facts.ttl`, applies rules from `rules.n3`, and prints the derived facts to the terminal.

---

## The Two Files You Need

### Data file (`--n3`)

Contains your facts. Can be `.ttl` (Turtle) or `.n3` (Notation 3) format:

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

## Flags Explained

### Input Flags

| Flag | What it does | Example |
| :--- | :--- | :--- |
| `--n3 <file>` | Load facts from a file. Use multiple times to load several files. | `--n3 people.ttl --n3 places.ttl` |
| `--query <file>` | Load rules from a file. Use multiple times for several rule files. | `--query family.n3 --query business.n3` |

### Output Flags

| Flag | What it does | When to use it |
| :--- | :--- | :--- |
| *(none)* | Show only **new** derived facts | Default — just see what the engine figured out |
| `--pass` | Show original facts + derived facts | When you want to see the complete picture |
| `--pass-all` | Show facts + rules + derived facts | For debugging — see everything the engine knows |
| `--nope` | Show facts only, skip reasoning | When you just want to validate/normalize your data |
| `--prefix P=URL` | Define a shortcut for output formatting | When you want `:alice` instead of full URLs in output |

**Think of it this way:**

```
No flag:     Only new facts the engine discovered
--pass:      Everything (input + new)
--nope:      Only input (ignore rules)
```

### Control Flags

| Flag | What it does | Example |
| :--- | :--- | :--- |
| `--max-inferences N` | Stop after N reasoning steps | `--max-inferences 100` — useful when you have lots of data and want to limit runtime |
| `--tactic limited-answer N` | Stop after N derived triples | `--tactic limited-answer 5` — only show the first 5 new facts |
| `--explain` | Collect proof traces | Phase 1: accepted but does nothing. Planned for Phase 2. |

### Display Flags

| Flag | What it does | Example output |
| :--- | :--- | :--- |
| `--statistics` | Print performance info to stderr | `# steps=42 derived=12 time=3.7ms` |
| `--quiet` | Suppress all stderr output | Use with `--statistics` to hide stats |
| `--help` | Show help message | Lists all flags |

---

## Exit Codes

| Code | What it means |
| :--- | :--- |
| `0` | Everything worked |
| `1` | Something went wrong (file not found, bad syntax, etc.) |

Error messages go to stderr and look like:

```
pyeye: error: at line 1 of <>:
Bad syntax (expected directive or statement) at ^ in:
"b''^b'=> {:a :b :c} .\n'"
```

---

## Examples

### Example 1: Quick test

```bash
pyeye --n3 data.ttl --query rules.n3 --statistics
```

Derive new facts and show how long it took.

### Example 2: Validate data without reasoning

```bash
pyeye --n3 messy-data.ttl --nope
```

Just load and re-emit the data. Useful for checking if your N3/Turtle files parse correctly.

### Example 3: See the complete picture

```bash
pyeye --n3 family.ttl --query family.n3 --pass
```

Show both the facts you provided and the facts the engine derived.

### Example 4: Limit how much reasoning happens

```bash
pyeye --n3 big-data.ttl --query rules.n3 --tactic limited-answer 10
```

Only derive the first 10 new facts, then stop. Useful for exploring large rule sets.

### Example 5: Cap the execution time

```bash
pyeye --n3 data.ttl --query rules.n3 --max-inferences 1000
```

Stop after 1000 inference steps. Prevents runaway reasoning on large datasets.

### Example 6: Pipe the output

```bash
pyeye --n3 data.ttl --query rules.n3 --pass | grep ":child"
pyeye --n3 data.ttl --query rules.n3 --statistics 2>&1 >/dev/null
```

pyeye writes N3 to stdout, so you can grep, count, or redirect it like any other command.

### Example 7: Custom output prefixes

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
