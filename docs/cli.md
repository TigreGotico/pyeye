# CLI Reference

The `pyeye` command runs N3 reasoning from the terminal without writing any Python code.

---

## Synopsis

```bash
pyeye [OPTIONS]
```

All output goes to **stdout**. Statistics and errors go to **stderr**.

---

## Basic usage

```bash
# Derive new facts from data and rules
pyeye --n3 data.ttl --query rules.n3

# Show input + derived (deductive closure)
pyeye --n3 data.ttl --query rules.n3 --pass

# Apply RDFS entailment
pyeye --n3 data.ttl --query rules.n3 --entail

# Apply OWL 2 RL entailment (superset of RDFS)
pyeye --n3 data.ttl --query rules.n3 --entail-owl

# Print statistics to stderr
pyeye --n3 data.ttl --query rules.n3 --statistics

# Proof trace in HTML
pyeye --n3 data.ttl --query rules.n3 --explain --explain-format html > proof.html
```

---

## Input flags

### `--n3 FILE`

Load a data file (N3 or Turtle). Repeatable — each `--n3` flag adds another file.

```bash
pyeye --n3 facts1.ttl --n3 facts2.ttl --query rules.n3
```

Both local file paths and `http://`/`https://` URLs are accepted. Remote files are fetched over the network. SSRF protection is active: URLs targeting private IP ranges are rejected.

### `--query FILE`

Load a rule file (N3). Repeatable. Rule files may also contain data triples — everything is parsed and loaded.

```bash
pyeye --n3 data.ttl --query rules1.n3 --query rules2.n3
```

---

## Output modes

### `--pass`

Output the deductive closure: input facts plus derived triples. Without this flag, only derived triples are printed.

```bash
pyeye --n3 data.ttl --query rules.n3 --pass
```

### `--pass-all`

Output input facts, rules, and derived triples.

```bash
pyeye --n3 data.ttl --query rules.n3 --pass-all
```

### `--nope`

No reasoning — parse and output the input facts only, with no derivation.

```bash
pyeye --n3 data.ttl --nope
```

Useful for validating that a file parses correctly.

### Summary

```
No flag:     only new facts the engine derived
--pass:      everything (input + derived)
--pass-all:  input + rules + derived
--nope:      only input (no reasoning)
```

---

## Reasoning control

### `--entail`

Apply RDFS entailment rules before user rules. Derives implicit triples from `rdfs:subClassOf`, `rdfs:subPropertyOf`, `rdfs:domain`, and `rdfs:range` declarations.

```bash
pyeye --n3 ontology.ttl --n3 data.ttl --query rules.n3 --entail
```

### `--entail-owl`

Apply OWL 2 RL entailment (includes RDFS). Adds reasoning for `owl:sameAs`, `owl:inverseOf`, transitive/symmetric/functional properties, class expressions, and property chains.

```bash
pyeye --n3 owl_data.ttl --query rules.n3 --entail-owl
```

### `--no-forward`

Skip forward chaining; use only backward chaining (requires `--query-goal`).

```bash
pyeye --n3 data.ttl --query rules.n3 --no-forward --query-goal "http://ex.org/a,http://ex.org/p,?X"
```

### `--max-inferences N`

Hard cap on the number of forward-chaining rule firings. The engine stops after N steps even if fixpoint has not been reached.

```bash
pyeye --n3 data.ttl --query rules.n3 --max-inferences 10000
```

### `--tactic NAME VALUE`

Set a reasoning tactic. Currently supported:

| Tactic | Description |
|--------|-------------|
| `limited-answer N` | Stop after N new derivations |

```bash
pyeye --n3 data.ttl --query rules.n3 --tactic limited-answer 100
```

### `--query-goal TRIPLE`

Backward-chain from a specific goal triple. The triple is specified as a comma-separated `S,P,O` string of full IRIs. Use `?Name` for variable positions.

```bash
pyeye --n3 data.ttl --query rules.n3 --query-goal "http://ex.org/bob,http://ex.org/child,?X"
```

One ground triple is printed per answer (the goal with the variables substituted). When `--query-goal` is set, the answer triples replace the normal derived-triple output.

---

## Proof and explanation

### `--explain`

Generate proof traces for each derived triple. Output format is controlled by `--explain-format`.

```bash
pyeye --n3 data.ttl --query rules.n3 --explain
```

### `--explain-format FORMAT`

Format for proof output. Only meaningful with `--explain`. Choices:

| Format | Output |
|--------|--------|
| `n3` | N3 proof triples (default) |
| `dot` | Graphviz DOT string |
| `html` | Collapsible HTML proof tree |

```bash
# HTML proof tree, redirected to file
pyeye --n3 data.ttl --query rules.n3 --explain --explain-format html > proof.html

# DOT for rendering with graphviz
pyeye --n3 data.ttl --query rules.n3 --explain --explain-format dot | dot -Tpng > proof.png
```

---

## Checking non-entailment

### `--not-entail`

Check that no entailment occurred at all. If any triple was derived, a `# not-entail check failed` line is printed to stderr (suppressed by `--quiet`). The exit code is unchanged.

### `--not-entail-triple S,P,O`

Check that a specific triple was NOT derived. The triple is specified as a comma-separated `S,P,O` string of full IRIs. A failed check (the triple WAS derived) is reported on stderr; the exit code is unchanged.

```bash
pyeye --n3 data.ttl --query rules.n3 --not-entail-triple \
    "http://ex.org/alice,http://ex.org/forbidden,http://ex.org/bob"
```

---

## Output and format

### `--prefix P=URL`

Register a prefix for output serialization. Repeatable. Use `=URL` (no name) for the default prefix.

```bash
pyeye --n3 data.ttl --query rules.n3 \
    --prefix "=http://example.org/" \
    --prefix "xsd=http://www.w3.org/2001/XMLSchema#"
```

The prefixes are used to abbreviate IRIs in the output N3.

---

## Caching

### `--cache-dir DIR`

Cache directory for remotely fetched N3 files. When set, HTTP/HTTPS URIs are fetched once and stored locally; subsequent runs use the cached version.

```bash
pyeye --n3 http://example.org/data.ttl --cache-dir ./.pyeye-cache
```

---

## Diagnostics

### `--statistics`

Print reasoning statistics to stderr after the run.

```bash
pyeye --n3 data.ttl --query rules.n3 --statistics
# stderr: # steps=42 derived=12 time=3.7ms
```

### `--quiet`

Suppress all stderr output (including statistics).

```bash
pyeye --n3 data.ttl --query rules.n3 --statistics --quiet
# no stderr output
```

---

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | Success |
| `1` | Error (parse error, file not found, blocked URL, malformed `--query-goal`, etc.) |

Errors are printed to stderr in the form `pyeye: error: <message>`.

---

## Stdout vs stderr

| Stream | Content |
|--------|---------|
| **stdout** | N3 output (the facts) |
| **stderr** | Error messages, statistics, not-entail reports |

The separation makes the N3 output pipeable:

```bash
pyeye --n3 data.ttl --query rules.n3 --pass | grep ":child"
pyeye --n3 data.ttl --query rules.n3 --statistics 2> stats.log
```

---

## Examples

### Derive facts from files

```bash
pyeye --n3 family.ttl --query ancestry_rules.n3
```

### Full deductive closure

```bash
pyeye --n3 family.ttl --query ancestry_rules.n3 --pass
```

### RDFS reasoning

```bash
pyeye --n3 ontology.owl --n3 instances.ttl --entail
```

### OWL 2 RL reasoning

```bash
pyeye --n3 wine.owl --n3 instances.ttl --entail-owl --pass
```

### Backward chaining query

```bash
pyeye --n3 graph.ttl --query graph_rules.n3 \
    --query-goal "http://example.org/a,http://example.org/reachable,?X"
```

### Proof trace

```bash
pyeye --n3 data.ttl --query rules.n3 --explain --explain-format html > proof.html
open proof.html
```

### Cap the run time and steps

```bash
pyeye --n3 data.ttl --query recursive_rules.n3 \
    --max-inferences 50000 \
    --statistics
```

### Multiple inputs

```bash
pyeye \
    --n3 base_facts.ttl \
    --n3 domain_data.ttl \
    --query core_rules.n3 \
    --query extension_rules.n3 \
    --entail \
    --pass \
    --statistics
```

### Remote files with caching

```bash
pyeye \
    --n3 http://example.org/shared_ontology.ttl \
    --n3 local_data.ttl \
    --cache-dir /tmp/pyeye-cache \
    --query rules.n3
```

### Check a constraint is not violated

```bash
# Derive, then verify :alice :forbidden :bob was NOT derived
pyeye --n3 data.ttl --query rules.n3 \
    --not-entail-triple "http://ex.org/alice,http://ex.org/forbidden,http://ex.org/bob" \
    --statistics
```
