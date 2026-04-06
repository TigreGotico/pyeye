# CLI Reference

The `pyeye` command runs N3 reasoning from the terminal without writing any Python code.

`main` — `pyeye/cli.py:13`

## Synopsis

```bash
pyeye [options]
```

## The Two Files You Need

### Data file (`--n3`)

Contains facts in N3/Turtle or TriG format:

```turtle
@prefix : <http://my-family.org/> .

:alice :parent :bob .
:bob   :parent :carol .
```

### Rule file (`--query`)

Contains rules in N3 format:

```n3
@prefix : <http://my-family.org/> .

{ ?X :parent ?Y } => { ?Y :child ?X } .
{ ?X :parent ?Y . ?Y :parent ?Z } => { ?X :grandparent ?Z } .
```

---

## All Flags

### Input

| Flag | Description | Example |
| :--- | :--- | :--- |
| `--n3 <path\|url>` | Load facts from N3/Turtle/TriG file or HTTP URL. Repeatable. | `--n3 people.ttl --n3 places.ttl` |
| `--query <path\|url>` | Load rules from N3 file or HTTP URL. Repeatable. | `--query family.n3 --query business.n3` |
| `--cache-dir <dir>` | Cache directory for remote files. HTTP URLs are fetched once and stored as SHA-256 named files. | `--cache-dir /tmp/pyeye-cache` |

### Output

| Flag | Description |
| :--- | :--- |
| *(none)* | Default: show only newly derived facts |
| `--pass` | Show original facts + derived facts (deductive closure) |
| `--pass-all` | Show facts + rules + derived facts |
| `--nope` | Skip reasoning; re-emit data only (useful for validating/normalizing N3 files) |
| `--explain` | Include proof explanations in output |
| `--explain-format n3\|dot\|html` | Format for proof output (default: `n3`). Use `html` for browser view; `dot` for Graphviz. |

### Entailment

| Flag | Description |
| :--- | :--- |
| `--entail` | Apply RDFS entailment before user rules: derives implicit triples from `rdfs:subClassOf`, `rdfs:subPropertyOf`, `rdfs:domain`, `rdfs:range` |
| `--entail-owl` | Apply OWL 2 RL entailment (superset of `--entail`): also handles transitive/symmetric/functional properties, `owl:sameAs`, class constructors, property chains |

### Control

| Flag | Description | Example |
| :--- | :--- | :--- |
| `--max-inferences <N>` | Hard cap on total inference steps. Stops reasoning after N steps regardless of fixpoint. | `--max-inferences 1000` |
| `--tactic limited-answer <N>` | Stop after deriving N triples. | `--tactic limited-answer 10` |
| `--no-forward` | Skip forward chaining. Use with `--query-goal` for pure backward chaining. | |
| `--query-goal <S,P,O>` | Backward-chain from a goal triple. Comma-separated subject, predicate, object (use `?Name` for variables). | `--query-goal http://ex.org/bob,http://ex.org/child,?X` |
| `--not-entail-triple <S,P,O>` | Check that this triple (comma-separated IRIs) is NOT entailed. Sets exit flag if found. | `--not-entail-triple http://x/a,http://x/p,http://x/b` |

### Display

| Flag | Description | Example |
| :--- | :--- | :--- |
| `--prefix P=URL` | Register prefix shortcut for output formatting. | `--prefix ex=http://example.org/` |
| `--statistics` | Print timing and step count to stderr after reasoning. | `# steps=42 derived=12 time=3.7ms` |
| `--quiet` | Suppress all stderr output. | |
| `--help` | Show help message. | |

**Output mode summary:**

```
No flag:      Only newly derived facts
--pass:       Input facts + derived facts
--pass-all:   Input facts + rules + derived facts
--nope:       Input facts only (no reasoning)
```

---

## Exit Codes

| Code | Meaning |
| :--- | :--- |
| `0` | Reasoning completed (including `--not-entail-triple` check) |
| `1` | Error (file not found, parse error, blocked URL, etc.) |

Error messages go to stderr:

```
pyeye: error: at line 1 of <>:
Bad syntax (expected directive or statement) at ^ in:
"b''^b'=> {:a :b :c} .\n'"
```

---

## Stdout vs Stderr

| Stream | Content |
| :--- | :--- |
| **stdout** | N3 output (the derived or pass-through facts) |
| **stderr** | Error messages and `--statistics` output |

This separation lets you pipe N3 output while still seeing statistics and errors on the terminal.

---

## Examples

### Example 1: Derive new facts

```bash
pyeye --n3 data.ttl --query rules.n3
```

### Example 2: Show everything including input facts

```bash
pyeye --n3 data.ttl --query rules.n3 --pass
```

### Example 3: RDFS entailment

```bash
pyeye --n3 data.ttl --query rules.n3 --entail --pass --statistics
```

### Example 4: OWL 2 RL entailment

```bash
pyeye --n3 ontology.ttl --query rules.n3 --entail-owl --pass
```

### Example 5: Validate data without reasoning

```bash
pyeye --n3 messy-data.ttl --nope
```

Loads and re-emits the data. Useful for checking if N3/Turtle files parse correctly.

### Example 6: Proof traces as HTML

```bash
pyeye --n3 data.ttl --query rules.n3 --explain --explain-format html > proof.html
```

### Example 7: Backward chaining from a goal

```bash
pyeye --n3 data.ttl --query rules.n3 --query-goal http://ex.org/bob,http://ex.org/child,?X
```

Find all bindings for `?X` satisfying `:bob :child ?X`.

### Example 8: Not-entail check

```bash
pyeye --n3 data.ttl --query rules.n3 \
  --not-entail-triple http://ex.org/a,http://ex.org/forbidden,http://ex.org/b
```

Verifies that the specific triple is NOT derivable.

### Example 9: Cache remote files

```bash
pyeye --n3 http://example.org/data.ttl \
      --query http://example.org/rules.n3 \
      --cache-dir /tmp/cache
```

### Example 10: Limit derivations

```bash
pyeye --n3 big-data.ttl --query rules.n3 --tactic limited-answer 10
```

Stops after deriving the first 10 new facts.

### Example 11: Step cap

```bash
pyeye --n3 data.ttl --query rules.n3 --max-inferences 1000
```

### Example 12: Multiple data and rule files

```bash
pyeye --n3 people.ttl --n3 places.ttl --query family.n3 --query location.n3 --pass
```

### Example 13: Custom output prefixes

```bash
pyeye --n3 data.ttl --query rules.n3 --prefix ex=http://example.org/
```

Makes output use `ex:alice` instead of full IRIs.

### Example 14: Capture statistics only

```bash
pyeye --n3 data.ttl --query rules.n3 --statistics 2>&1 >/dev/null
```

### Example 15: Pipe N3 output

```bash
pyeye --n3 data.ttl --query rules.n3 --pass | grep ":child"
```
