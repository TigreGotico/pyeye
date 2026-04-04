# CLI Reference

**Source:** `main` — `pyeye/cli.py:9`

## Synopsis

```bash
pyeye [options]
```

## Flags

| Flag | Description |
| :--- | :--- |
| `--n3 <file>` | Load N3/Turtle data file. Repeatable. |
| `--query <file>` | Load N3 rule file. Repeatable. |
| `--pass` | Output deductive closure (input facts + derived triples). |
| `--pass-all` | Closure + rules. |
| `--nope` | No derivation — pass through input data only. |
| `--explain` | Include proof explanations. Phase 1: accepted but no-op. |
| `--tactic <name> <value>` | Reasoning tactic. Supported: `limited-answer N`. |
| `--max-inferences N` | Hard cap on inference steps. |
| `--prefix P=URL` | Register prefix for output serialization. Repeatable. |
| `--quiet` | Suppress stderr output. |
| `--statistics` | Print `steps=`, `derived=`, `time=` to stderr. |
| `--help` | Show help message. |

## Exit Codes

| Code | Meaning |
| :--- | :--- |
| `0` | Success |
| `1` | Error (parse error, file not found, invalid N3) |

Error messages are printed to stderr in the format:
```
pyeye: error: <description>
```

## Examples

### Basic derivation

```bash
pyeye --n3 data.ttl --query rules.n3
```

Outputs only newly derived triples.

### Pass-through (no derivation)

```bash
pyeye --n3 data.ttl --nope
```

### Include input facts in output

```bash
pyeye --n3 data.ttl --query rules.n3 --pass
```

### Limit derivations

```bash
pyeye --n3 data.ttl --query rules.n3 --tactic limited-answer 5
```

Stops after 5 new derived triples.

### Step cap

```bash
pyeye --n3 data.ttl --query rules.n3 --max-inferences 100
```

### Statistics

```bash
pyeye --n3 data.ttl --query rules.n3 --statistics
# steps=42 derived=12 time=3.7ms   ← stderr
```

### Quiet mode

```bash
pyeye --n3 data.ttl --query rules.n3 --statistics --quiet
# No stderr output
```

### Custom prefixes

```bash
pyeye --n3 data.ttl --query rules.n3 --prefix ex=http://example.org/ --pass
```

### Multiple data and rule files

```bash
pyeye --n3 facts1.ttl --n3 facts2.ttl --query rules1.n3 --query rules2.n3 --pass --statistics
```

## Stdout vs Stderr

| Stream | Content |
| :--- | :--- |
| **stdout** | N3 output (triples + prefix declarations) |
| **stderr** | Error messages, statistics (when `--statistics` is set) |

## Pipe Compatibility

pyeye reads from files only (not stdin). It writes N3 to stdout, so it can be piped:

```bash
pyeye --n3 data.ttl --query rules.n3 --pass | grep ":child"
pyeye --n3 data.ttl --query rules.n3 --nope | wc -l
```
