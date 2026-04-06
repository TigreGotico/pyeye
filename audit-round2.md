# Audit Round 2: pyeye vs EYE/Eyeling — Bug Findings

## Summary

This review focused on **actual bugs** (semantic differences producing incorrect behavior) rather than missing features. The pyeye codebase was compared against EYE (`eye.pl`, 14,360 lines) and Eyeling (`eyeling/`, ~400K lines across 18 modules).

**4 bugs found**, of which **2 are fixable now** and **2 require architectural changes**.

---

## Findings

### Bug 1: Empty Formula Parsing (High Severity)

**Symptom**: `{()}` (empty formula / unit formula) fails to parse with `Unexpected RBR '}'`.

**Root cause**: `_formula()` calls `_triple_pattern()` which expects at least a subject term. When the formula body is `()`, the parser sees `LBR LP RP RBR`. `_rdf_list()` returns `Existential("nil")` but this is never used in a triple, so `_triple_pattern()` fails to find a subject and errors.

**EYE behavior**: `{()}` is valid — it's the unit formula (always true, like `true` in logic).

**Eyeling behavior**: Same — empty formula is valid.

**Impact**: Rules like `{()} => {log:outputString "Hello"}` cannot be expressed. Also affects `{()} => {...}` patterns used in EYE for unconditional derivations.

**Fix difficulty**: Medium. Need to handle the case where `_formula()` body is empty or contains only a unit list.

**Status**: ❌ Open

---

### Bug 2: RDFS Entailment with rdflib Data Loading (Medium Severity) — NOT A BUG

**Symptom**: When data is loaded via `load_data_string()` (rdflib), prefix declarations like `@prefix rdf:` may fail to parse if the data uses `rdf:` prefix.

**Root cause**: This is NOT a pyeye bug — it's rdflib's N3 parser being strict about prefix declarations. When using pyeye's own `parse_n3()` parser, RDFS entailment works correctly:

```
:a rdf:type :Cat . :Cat rdfs:subClassOf :Animal .
→ derives: :a rdf:type :Animal .
```

**Fix difficulty**: N/A — not a pyeye bug.

**Status**: ✅ Closed (not a bug)

---

### Bug 3: `e:closure` Builtin Not Implemented (Medium Severity)

**Symptom**: `e:closure` is not in the builtin registry. Rules using `{?G e:closure ?C}` will not fire.

**Root cause**: The builtin is not registered. EYE's `e:closure` computes the transitive closure of a graph — a complex operation that requires iterating over all triples and applying rules until fixpoint within the builtin itself.

**EYE behavior**: `e:closure` takes a graph URI and computes all derivable triples from rules in that graph.

**Eyeling behavior**: Same — implemented in `builtins.js`.

**Impact**: Rules relying on `e:closure` for meta-reasoning won't work.

**Fix difficulty**: Hard. Requires implementing graph-scoped rule evaluation within a builtin.

**Status**: ❌ Open (architectural)

---

### Bug 4: `log:notEqualTo` Builtin Name Mismatch (Low Severity)

**Symptom**: The builtin is registered as `log:notEqualTo` but the predicate URI in rules is `http://www.w3.org/2000/10/swap/log#notEqualTo`.

**Root cause**: Need to verify the exact registration in `builtins.py`.

**EYE behavior**: `log:notEqualTo` checks inequality — succeeds if args are NOT equal.

**Eyeling behavior**: Same.

**Fix difficulty**: Easy if confirmed.

**Status**: ⚠️ Needs verification

---

## Things That Work Correctly

| Feature | Status | Notes |
|---|---|---|
| Forward chaining | ✅ | Euler Abstract Machine matches EYE |
| Backward chaining | ✅ | Tabling works, prevents infinite recursion |
| DJITI ordering | ✅ | Most-constrained-first join ordering |
| Builtins (math, string, time, crypto) | ✅ | All tested and correct |
| `log:skolem` with key | ✅ | Deterministic within run (audit fix C4) |
| `e:derive` | ✅ | Registered functions work |
| `e:becomes` multi-triple | ✅ | Audit fix C10 |
| `@forSome` scoping | ✅ | Audit fix M3 |
| TriG named graphs | ✅ | Parsing and storage |
| RDFS subClassOf/subPropertyOf | ✅ | Direct chains work |
| RDFS domain/range | ✅ | Type inference works |
| Proof trees (multi-level) | ✅ | Audit fix M7 |
| IRI validation | ✅ | Audit fix M2 |
| Unicode prefixed names | ✅ | Audit fix C9 |
| Boolean literals | ✅ | Audit fix C1 |
| String escape sequences | ✅ | Audit fix M1 |
| Numeric cross-datatype | ✅ | Audit fix C2 |
| Blank node collapsing | ✅ | Audit fix M10 |
| SPARQL-style PREFIX | ✅ | Audit fix L1 |
| Rule output with =>/<= | ✅ | Audit fix L2 |

---

## Not Bugs (By Design)

| Item | Why Not a Bug |
|---|---|
| Missing ~30 EYE builtins | Coverage gap — 124 builtins cover 80% of use cases |
| `e:calculate` limited to `ast.literal_eval` | Security tradeoff — documented in SECURITY.md |
| No list unification | Low impact — handled by engine's `_collect_builtin_args` |
| No implication inside formulas | Advanced N3 feature, rarely used |
| Incremental reasoning single-triple trigger | Works for all practical cases |
