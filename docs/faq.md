# FAQ

## General

### What is pyeye?

A pure-Python forward-chaining N3 reasoner implementing the Euler Abstract Machine. It's a port of the [EYE reasoner](https://github.com/eyereasoner/eye) (SWI-Prolog) and [Eyeling](https://github.com/eyereasoner/eyeling) (JavaScript), targeting Phase 1 coverage: rules, builtins, and deductive closure.

### Why Python instead of Prolog or JS?

The EYE reasoner requires SWI-Prolog as a system dependency. Eyeling requires Node.js. A Python implementation can be imported as a library by any Python application (including the LEA voice assistant project) with no external runtime beyond `rdflib`.

### Is this production-ready?

Phase 1 is an MVP. It correctly handles forward chaining with variables, builtins, cycle detection, and step limits. It lacks:
- Full N3 grammar (triple terms, formula terms, BLOGIC)
- Backward chaining / tabling
- Proof graph output
- RETE-style performance optimization
- HTTP data loading

### What N3 standard does this follow?

The [Notation3 (N3) Logic](https://www.w3.org/TeamSubmission/n3/) specification. EYE is the reference implementation; pyeye targets EYE compatibility for the features it supports.

---

## Usage

### How do I load data from a URL?

Not supported in Phase 1. All data must be local files or inline strings:

```python
# Local file
execute(data_paths=["data.ttl"])

# Inline string
execute(data_strings=["@prefix : <http://ex.org/> .\n:a :p :b ."])
```

HTTP loading is planned for Phase 2.

### Why does my rule not fire?

Common causes:

1. **Prefix mismatch** — Rule predicates use different IRIs than data predicates. Check with `--pass` to see what the store actually contains.
2. **Unbound builtin args** — Builtins skip evaluation when arguments contain variables. Add a preceding triple pattern to ground them.
3. **Variable naming** — `?X` in the body and `?X` in the head must have the exact same spelling (case-sensitive).
4. **Cycle detection** — If the rule derives a triple that already exists in the store, it's silently skipped. This is intentional (prevents infinite loops).

### How do I see what's in the store?

Use `--pass` mode to output all triples (input + derived):

```bash
pyeye --n3 data.ttl --query rules.n3 --pass
```

Or programmatically:

```python
from pyeye import execute
r = execute(..., pass_mode=True)
print(r.triples)
```

### Why is my output empty?

By default, `execute()` outputs only **derived** triples (newly inferred facts). If you want to see input facts too, use `pass_mode=True`:

```python
r = execute(..., pass_mode=True)
```

---

## Performance

### How fast is pyeye?

For small rule sets (≤ 10 rules, ≤ 100 triples), expect sub-millisecond execution. The predicate-based index in `TripleStore` (`pyeye/store.py:27`) gives O(1) lookups when the predicate is a concrete `NamedNode`.

### Why is it slow with many rules?

The matching algorithm in Phase 1 is a naive nested loop: for each rule, for each body pattern, for each binding combination, scan the store. For rule bodies with 3+ patterns over large stores, this becomes O(n^k) where k is the number of patterns.

**Mitigations:**
- Keep rule bodies short (1-2 patterns when possible)
- Put the most selective pattern first (fewest matching triples)
- Use `max_steps` or `limit_answers` to cap execution

### Will there be a RETE implementation?

Yes — Phase 2 plans include DJITI indexing (ported from EYE) or a RETE-like discrimination network.

---

## Errors

### `pyeye: error: ...`

A clean error message from the CLI. Common causes:
- File not found
- Invalid N3 syntax
- rdflib parse error

### `ParseError: Expected X, got Y`

The hand-written N3 parser encountered unexpected syntax. Check the [Syntax Guide](syntax-guide.md) for what's supported.

### `AttributeError: 'Engine' object has no attribute ...`

This was a known bug in early versions (`log:skolem` referenced `_Skolem_counter` instead of `_skolem_counter`). Fixed in the audit commit.

### `TypeError: Instance and class checks can only be used with @runtime_checkable protocols`

This was a known bug where the `Term` protocol wasn't marked `@runtime_checkable`. Fixed in the audit commit.

---

## Known Limitations

| Limitation | Workaround | Phase |
| :--- | :--- | :--- |
| No HTTP data loading | Use `data_strings` with `requests.get().text` | 2 |
| No backward chaining | Restructure rules for forward chaining | 2 |
| No proof output | Use `--explain` (accepted, returns `[]`) | 2 |
| No TriG / named graphs | Flatten to single graph | 2 |
| No `is`/`has`/`of` sugar | Use explicit `:predicate` syntax | 2 |
| No triple terms `<< >>` | Use reification triples | 2 |
| `@forSome`/`@forAll` parsed but no semantic effect | Works for Phase 1 use cases | 2 |
| Builtin arg extraction is positional (subject + object) | Use scalar-style for math, list-style for strings | 1 |

---

## Development

### How do I run tests?

```bash
cd /path/to/pyeye
source .venv/bin/activate
python -m pytest tests/ -v
```

### How do I add a new builtin?

1. Add the function to `pyeye/builtins.py`:
   ```python
   def my_builtin(args: list[Term], engine: EngineProto) -> Term | None:
       if _unground(args):
           return None
       # ... compute ...
       return Literal("result")
   ```

2. Register it in `BUILTIN_REGISTRY`:
   ```python
   BUILTIN_REGISTRY["http://my.org/builtin"] = my_builtin
   ```

3. Add unit tests to `tests/test_fr_coverage.py` or a new test file.

4. Document it in `docs/builtins.md`.

### How do I contribute?

This project is developed locally for human review. All changes are committed on the `pyeye-phase1` branch. To contribute:
1. Fork the repository
2. Create a feature branch
3. Open a pull request
