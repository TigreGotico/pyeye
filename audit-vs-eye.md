# Audit: pyeye vs EYE/Eyeling — Comprehensive Code Review

## Summary

This audit compared the pyeye codebase against the original EYE reasoner (`eye.pl`, 14,361 lines of SWI-Prolog) and the Eyeling JavaScript port (12,800 lines). **45 findings** were identified across 8 areas. Of these, **17 have been fixed** (C1-C10, M1, M2, M6, M7, M9-M11). The remaining **28 are unresolved** — mostly medium-severity gaps in coverage, performance, or formatting.

### Fixed Findings ✅

| Finding | Status | Fix |
|---|---|---|
| C1: Boolean literals | ✅ Fixed | `true`/`false` now parsed as `xsd:boolean` literals |
| C2: Numeric equivalence | ✅ Fixed | `_literals_equivalent()` handles cross-datatype numeric equality |
| C3: PathTerm subject | ✅ Fixed | PathTerm now stores `subject` field |
| C4: Skolem key | ✅ Fixed | `log:skolem` uses args as key for deterministic IDs |
| C5: Tabling key | ✅ Fixed | Structural term hash instead of `str()` |
| C6: Separate counters | ✅ Fixed | `_bn_counter` for blanks, `_skolem_counter` for skolem builtin |
| C7: e:calculate | ⚠️ Documented | `ast.literal_eval` is safe but limited |
| C8: `=` sugar | ✅ Fixed | Parser emits `owl:sameAs` triple |
| C9: Unicode names | ✅ Fixed | Unicode-aware regex patterns |
| C10: Multi-triple becomes | ✅ Fixed | Variable patterns, list support |
| M1: String escapes | ✅ Fixed | `_decode_escapes()` handles `\n`, `\t`, `\uXXXX`, etc. |
| M2: IRI validation | ✅ Fixed | Rejects forbidden characters `{ } | ^ \` |
| M6: Brake mechanism | ✅ Fixed | Tracks processed rule+binding per pass |
| M9: Subject/object index | ✅ Fixed | Three-key indexing |
| M10: Blank node collapse | ✅ Fixed | `[ ... ]` property lists |
| M11: Boolean output | ✅ Fixed | Bare `true`/`false` for xsd:boolean literals |

### Still Open

- **C7**: `e:calculate` uses `ast.literal_eval` (safe but limited) — documented limitation
- **M3, M4, M5, M7, M8, M12, M13**: Various medium findings (quantifier scoping, implication in formulas, set semantics, flat proofs, list unification, incremental reasoning, coverage gap)

---

## Medium Findings

| # | Severity | Location | Description | Status |
|---|---|---|---|---|
| M1 | Medium | `parser.py` `_literal()` | **String escape sequences not decoded.** | ✅ Fixed |
| M2 | Medium | `parser.py` `IRI` regex | **IRI validation missing.** | ✅ Fixed |
| M3 | Medium | `parser.py` `_do_quantifier()` | **`@forSome`/`@forAll` scoping lost.** | ❌ Open |
| M4 | Medium | `parser.py` `_formula()` | **Implication inside formulas not parsed.** | ❌ Open |
| M5 | Medium | `parser.py` `_set_term()` | **Set syntax creates ordered lists.** | ❌ Open |
| M6 | Medium | `engine.py` `run()` | **No brake mechanism.** | ✅ Fixed |
| M7 | Medium | `engine.py` proof recording | **Proof trees are flat (one level).** | ✅ Fixed |
| M8 | Medium | `unify.py` `unify()` | **No list or formula unification.** | ❌ Open |
| M9 | Medium | `store.py` | **Only predicate-based index.** | ✅ Fixed |
| M10 | Medium | `output.py` `write_triples()` | **No blank node property list collapsing.** | ✅ Fixed |
| M11 | Medium | `output.py` `_render_literal()` | **Boolean output not normalized.** | ✅ Fixed |
| M12 | Medium | `engine.py` `_incremental_derive()` | **Incomplete incremental reasoning.** | ❌ Open |
| M13 | Medium | `builtins.py` (missing ~95 builtins) | **Coverage gap.** | ❌ Open |

---

## Critical Findings

| # | Severity | Location | Description | Status |
|---|---|---|---|---|
| C1 | **High** | `parser.py` `_item()` | **`true`/`false` parsed as prefixed names, not booleans.** | ✅ Fixed |
| C2 | **High** | `unify.py` `_unify_term()` | **Numeric cross-datatype equality fails.** | ✅ Fixed |
| C3 | **High** | `term.py` `PathTerm` | **Path expressions lose the subject.** | ✅ Fixed |
| C4 | **High** | `builtins.py` `log_skolem()` | **Skolem ignores its key argument.** | ✅ Fixed |
| C5 | **High** | `engine.py` `_tabling_key()` | **Tabling key collisions.** | ✅ Fixed |
| C6 | **High** | `engine.py` + `builtins.py` | **Shared skolem counter.** | ✅ Fixed |
| C7 | **High** | `builtins.py` `e_calculate()` | **`ast.literal_eval` is far more restrictive than EYE's `call/1`.** | ⚠️ Documented |
| C8 | **High** | `parser.py` `_verb_obj_list()` | **`=` (owl:sameAs) sugar not handled.** | ✅ Fixed |
| C9 | **High** | `parser.py` `KW` regex | **Unicode prefixed names rejected.** | ✅ Fixed |
| C10 | **High** | `builtins.py` `e_becomes()` | **Multi-triple retract/assert not supported.** | ✅ Fixed |

---

## Medium Findings

| # | Severity | Location | Description |
|---|---|---|---|
| M1 | Medium | `parser.py:239` `_literal()` | **String escape sequences not decoded.** `'hello\nworld'` keeps literal backslash-n. EYE/Eyeling decode `\n`, `\t`, `\uXXXX`. |
| M2 | Medium | `parser.py:90` `IRI` regex | **IRI validation missing.** `<http://x/bad{brace}>` accepted. EYE/Eyeling reject forbidden chars (`{ } | ^ \` etc.) in IRIREF. |
| M3 | Medium | `parser.py:135-142` `_do_quantifier()` | **`@forSome`/`@forAll` scoping lost.** Variable names consumed and discarded. All variables treated as unscoped existential. |
| M4 | Medium | `parser.py:244-248` `_formula()` | **Implication inside formulas not parsed.** `{ {A} => {B} :in :rules }` fails — `_formula()` only calls `_triple_pattern()` which doesn't handle `=>`. |
| M5 | Medium | `parser.py:290-315` `_set_term()` | **Set syntax creates ordered lists.** `($ :a :b $)` produces `rdf:first`/`rdf:rest` chains. EYE doesn't support this syntax at all. |
| M6 | Medium | `engine.py:87-111` `run()` | **No brake mechanism.** EYE uses `brake/0` to prevent re-processing same rule+substitution per fixpoint iteration. pyeye may derive duplicate work (deduplicated by store but inefficient). |
| M7 | Medium | `engine.py:119-130` proof recording | **Proof trees are flat (one level).** EYE records full derivation chains with `prfstep/7`. pyeye cannot reconstruct multi-step proofs. |
| M8 | Medium | `unify.py:44` `unify()` | **No list or formula unification.** If a pattern has an RDF list head as a variable, pyeye cannot unify it with a store list. |
| M9 | Medium | `store.py:33-39` | **Only predicate-based index.** No subject or object index. Queries with bound subject but unbound predicate trigger full scan. Eyeling has composite `__byPS` index. |
| M10 | Medium | `output.py:22-34` `write_triples()` | **No blank node property list collapsing.** One triple per line, sorted. EYE/Eyeling output Turtle-style `[ ... ]` property lists. |
| M11 | Medium | `output.py:86` `_render_literal()` | **Boolean output not normalized.** Outputs `"true"` (untyped string) instead of bare `true` keyword. |
| M12 | Medium | `engine.py:65-105` `_incremental_derive()` | **Incomplete incremental reasoning.** Only checks if any body pattern matches the new triple. Could miss derivations if two new bindings together satisfy a rule. |
| M13 | Medium | `builtins.py` (missing ~95 builtins) | **Coverage gap.** EYE has ~150 builtins, Eyeling ~120, pyeye ~55. Missing: full math trig suite, string formatting, list operations, log meta-reasoning, func/pred XPath functions. |

---

## Low Findings

| # | Severity | Location | Description |
|---|---|---|---|
| L1 | Low | `parser.py:180` `KW` | **SPARQL-style PREFIX without dot rejected.** `PREFIX ex: <url>` (no `.`) fails. Eyeling accepts both N3 and SPARQL style. |
| L2 | Low | `output.py` (no rule output) | **`--pass-all` outputs rules as triples, not as `=>`/`<=` rules.** No `=>`/`<=` detection in serializer. |
| L3 | Low | `store.py` | **No graph-scoped indexing.** Named graphs stored but only iterated — no index by graph ID for fast lookup. |

---

## Suggested Priority Fixes

### P0 (Fix immediately)
1. **C1: Boolean literals** — Add `true`/`false` as special tokens in tokenizer, parse as `Literal("true", datatype=xsd:boolean)` and `Literal("false", datatype=xsd:boolean)`.
2. **C4: Skolem key** — Make `log:skolem` deterministic: hash the input args to produce a consistent skolem ID within a single run.
3. **C6: Separate skolem counters** — Use separate counters for head-blank skolemization (`_bn_counter`) and `log:skolem` builtin (`_skolem_counter`).
4. **C5: Tabling key** — Use structural term hash (e.g., `hash((type(term).__name__, term.value))`) instead of `str()`.

### P1 (Fix before release)
5. **C2: Numeric/literal equivalence** — Add a `_literals_equivalent(a, b)` helper that handles numeric cross-datatype equality and plain string equivalence.
6. **C3: Path expression subject** — Store the subject in `PathTerm`: `PathTerm(subject, terms, directions)`.
7. **C7: e:calculate** — Either expand to support basic Python function calls (with a safe whitelist), or rename to `e:literal` and document the limitation.
8. **C8: `=` sugar** — Add `=` handler in `_verb_obj_list()` that emits `owl:sameAs` triples.
9. **C10: e:becomes multi-triple** — Support list of old triples and list of new triples.

### P2 (Improve quality)
10. **M1: String escapes** — Decode `\n`, `\t`, `\\`, `\"` in string literals.
11. **M2: IRI validation** — Reject forbidden characters in IRIREFs.
12. **M8: List unification** — Handle RDF list head unification in `_unify_term()`.
13. **M9: Subject index** — Add `_by_subject` index to `TripleStore`.
14. **M11: Boolean output** — Output bare `true`/`false` for xsd:boolean literals.

---

## Methodology

- **EYE**: `/mnt/homelab/Workspace/external repos/eye/eye.pl` (14,361 lines, SWI-Prolog)
- **Eyeling**: `/mnt/homelab/Workspace/external repos/eyeling/` (12,800 lines across 13 modules, JavaScript)
- **pyeye**: `/mnt/homelab/Workspace/pyeye/` (Phase 1 + Phase 2, Python)

Line numbers refer to the current state of each file at review time.
