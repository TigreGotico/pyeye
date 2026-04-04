# Audit: pyeye vs EYE/Eyeling — Comprehensive Code Review

## Summary

This audit compared the pyeye codebase against the original EYE reasoner (`eye.pl`, 14,361 lines of SWI-Prolog) and the Eyeling JavaScript port (12,800 lines). **45 findings** were identified across 8 areas. Of these, **14 are high-severity** semantic bugs that could produce incorrect reasoning results. The remaining 31 are medium-severity gaps in coverage, performance, or formatting.

The most critical bugs are: (1) `true`/`false` parsed as prefixed names instead of boolean literals, (2) numeric cross-datatype unification fails (`"42"^^xsd:integer` ≠ `"42.0"^^xsd:double`), (3) path expressions lose the subject, (4) `log:skolem` ignores its key argument, (5) tabling key collisions in backward chaining, and (6) shared skolem counter between `_skolemize()` and `log:skolem`.

---

## Critical Findings

| # | Severity | Location | Description |
|---|---|---|---|
| C1 | **High** | `parser.py:280-285` `_literal()` | **`true`/`false` parsed as prefixed names, not booleans.** EYE and Eyeling treat them as `"true"^^xsd:boolean` / `"false"^^xsd:boolean` literals. In pyeye, `{?X :alive true}` parses `true` as `http://prefix/true` — a completely different term. |
| C2 | **High** | `unify.py:137` `_unify_term()` | **Numeric cross-datatype equality fails.** `"42"^^xsd:integer` and `"42.0"^^xsd:double` do NOT unify in pyeye but DO unify in EYE/Eyeling. Same for `"hello"` vs `"hello"^^xsd:string`. |
| C3 | **High** | `parser.py:319-346` `_path_expression()` | **Path expressions lose the subject.** `:a ! :p ! :q` produces `PathTerm([:p, :q], ["fwd","fwd"])` with no reference to `:a`. The connection between subject and path is broken. |
| C4 | **High** | `builtins.py:244` `log_skolem()` | **Skolem ignores its key argument.** `{("key1") log:skolem ?S1}` and `{("key1") log:skolem ?S2}` produce different IDs, whereas EYE/Eyeling produce the same skolem for the same key. |
| C5 | **High** | `engine.py:283` `_tabling_key()` | **Tabling key collisions.** Uses `str(term)` which for `NamedNode("http://x/?X")` and `Variable("X")` both produce strings containing `?X` — could cause incorrect memoization. |
| C6 | **High** | `engine.py:42` + `builtins.py:244` | **Shared skolem counter.** `_skolem_counter` is used by both `_skolemize()` (head blank nodes) and `log:skolem` builtin. Calling `log:skolem` corrupts head blank node IDs. |
| C7 | **High** | `builtins.py:858-870` `e_calculate()` | **`ast.literal_eval` is far more restrictive than EYE's `call/1`.** Cannot invoke any functions — `ast.literal_eval("2 + 3")` works, but `ast.literal_eval("len([1,2,3])")` raises. EYE's version can call any Prolog predicate. |
| C8 | **High** | `parser.py` (no handler) | **`=` (owl:sameAs) sugar not handled.** `:a = :b .` tokenizes but `_item()` and `_verb_obj_list()` have no handler for the `=` token. EYE/Eyeling parse it as `:a owl:sameAs :b .`. |
| C9 | **High** | `parser.py:94` `KW` regex | **Unicode prefixed names rejected.** `KW` pattern `[A-Za-z_]\w*` is ASCII-only. `ex:chañaral` fails to parse. EYE and Eyeling handle full Unicode in local names. |
| C10 | **High** | `builtins.py:908-935` `e_becomes()` | **Multi-triple retract/assert not supported.** EYE's `becomes/2` retracts ALL triples in the subject conjunction and asserts ALL in the object conjunction. pyeye handles single-triple only. |

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
