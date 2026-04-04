# Audit: pyeye — Python N3 Reasoner (Phase 1)

## Summary

A well-structured, test-covered Phase 1 implementation of a forward-chaining N3 reasoner. The code follows the plan closely, with 104 passing tests across 5 modules. The architecture (term hierarchy → unification → indexed store → parser → builtins → engine → entry → CLI) is clean and composable.

**One critical bug** exists in the `log:skolem` builtin — a typo (`_Skolem_counter` vs `_skolem_counter`) that crashes the builtin when called. The test for skolem generation passes only because it checks `_skolem_counter >= 0` on an engine that never actually calls the builtin (the head triple has a Variable in the predicate slot, so `_handle_builtin` doesn't match `log:skolem` as a predicate). Two minor issues: CLI does not catch parse errors (prints traceback instead of clean message) and `rule_paths` files are opened without context manager. Overall quality is good for a Phase 1 MVP.

---

## Acceptance Criteria

| # | Criterion | Status | Evidence |
| :--- | :--- | :--- | :--- |
| AC1 | Simple derivation: `{a p b} => {a r b}` yields `:a :r :b` | **Pass** | `test_integration.py:17` — asserts `:r` in output |
| AC2 | Transitivity chain: 10-node chain derives exactly 10 `:reach` triples | **Pass** | `test_integration.py:34` — asserts `derived == 10` |
| AC3 | Cycle detection: self-deriving rule doesn't loop | **Pass** | `test_integration.py:46` — asserts `derived == 0`, `steps <= 1` |
| AC4 | `max_steps=3` halts after exactly 3 steps | **Pass** | `test_integration.py:58` — asserts `steps <= 3` |
| AC5 | `limit_answers=2` halts after 2 derivations | **Pass** | `test_integration.py:70` — asserts `derived == 2` |
| AC6 | `math:greaterThan` builtin evaluates correctly | **Pass** | `test_integration.py:78` — asserts `result.value == "true"` |
| AC7 | Duplicate triple rejection | **Pass** | `test_integration.py:89` — `store.add()` returns False on duplicate |
| AC8 | Variable binding propagation across patterns | **Pass** | `test_integration.py:96` — asserts `derived == 2` |
| AC9 | `--nope` mode: no derivation | **Pass** | `test_integration.py:117` — `:p` in output, `:q` not |
| AC10 | `--pass` mode: input + derived | **Pass** | `test_integration.py:126` — both `:p` and `:q` in output |
| AC11 | CLI exit code 0 on success, non-zero on error | **Partial** | `test_integration.py:133` checks success (exit 0). Parse errors exit non-zero via uncaught exception, but no clean error message — see Issues below |
| AC12 | Deterministic output | **Pass** | `test_integration.py:141` — byte-identical comparison |
| AC13 | Custom builtin registration | **Pass** | `test_integration.py:151` — custom builtin callable is accepted (no crash) |
| AC14 | Skolem generation: distinct identifiers | **Partial** | `test_integration.py:181` test passes but is a false positive — it checks `_skolem_counter >= 0` which is always true (init to 0). The `log:skolem` builtin **crashes** when actually called (see Critical Issue #1) |
| AC15 | Package import works | **Pass** | `test_integration.py:193` — `from pyeye import execute` succeeds |
| AC16 | All tests pass with pytest | **Pass** | `uv run pytest tests/` — 104 passed |

---

## Gaps & Issues

| Severity | Location | Description |
| :--- | :--- | :--- |
| **Critical** | `builtins.py:258` | `log_skolem` references `engine._Skolem_counter` (capital S) but the engine attribute is `_skolem_counter` (lowercase). Calling `log:skolem` via a rule raises `AttributeError`. The test (`test_integration.py:181`) passes only because the test creates a rule with `log:skolem` as the *predicate* of a triple whose subject is `Variable("X")` — the engine's `_match_formula` never resolves this to a `NamedNode`, so `_handle_builtin` is never invoked. **Fix**: change `_Skolem_counter` → `_skolem_counter` in `builtins.py:258`. |
| **Major** | `entry.py:92` | `open(p).read()` reads rule files without a context manager or encoding declaration. On non-UTF-8 files, this will crash. Should be `Path(p).read_text(encoding="utf-8")`. |
| **Major** | `cli.py:57-72` | No `try/except` around `execute()`. Parse errors produce a full Python traceback on stderr instead of a clean error message. FR28 requires "non-zero on parse error" (technically satisfied by exit code 1 from unhandled exception) but the UX is poor. Should catch `ParseError` and print a one-line message. |
| **Minor** | `engine.py:1` | Unused import: `from dataclasses import dataclass, field` — neither is used in `engine.py`. |
| **Minor** | `builtins.py:17` | Unused import: `import hashlib` — not used by any builtin in Phase 1. |
| **Minor** | `parser.py:17` | Unused import: `from pathlib import Path` — `Path` is used in the type hint of `load_data_file` but the `pathlib` import is shadowed by the type annotation context. No runtime error, but dead import. |
| **Minor** | `engine.py:265` | `_check_output_strings` is a no-op stub (`pass`). It's never called (removed from `_apply_rule`). Dead code — should be removed or marked `# Phase 2`. |
| **Minor** | `output.py:25` | Prefix serialization uses `pfx{colon}` where `colon = ":" if pfx else ""`. For empty prefix, this produces `@prefix  <...>` (double space). Cosmetic but valid N3. |
| **Minor** | `engine.py:131` | `_match_triples_iter` creates `dict(b)` on every pattern match step (copying the binding). This is O(V) per pattern per candidate triple. For large stores and long rule bodies, this becomes O(n * k * V) per rule per pass. Not a Phase 1 blocker but worth noting for Phase 2 performance. |
| **Minor** | `store.py:74` | The redundant check `if predicate is not None and isinstance(predicate, NamedNode)` after already branching on the same condition at line 67. The second check can never be True when the `else` branch was taken. Harmless but confusing. |
| **Minor** | `term.py:82` | `Formula.__init__` overrides `__setattr__` directly — this bypasses the frozen dataclass semantics and is brittle. A `__new__` method would be cleaner for a frozen dataclass that needs to coerce `list → tuple`. |

---

## Functional Requirements Coverage Gaps

| FR # | Requirement | Test Coverage |
| :--- | :--- | :--- |
| FR3 | Resolve `@base` directives and propagate to output | No test — parser tests `@base` parsing but output.py tests do not verify base URI propagation to N3 output |
| FR6 | `@forSome` / `@forAll` quantifier parsing and scoping | Parser test exists (`test_parser.py` does not have explicit tests for quantifier scoping to formulas — `_do_quantifier` just consumes tokens) |
| FR21 | Skip unground builtins, let later patterns ground them | No dedicated test — implied by `_unground` check in builtins, but no integration test exercises a rule where a builtin is unground on first pass and grounded on a later pass |
| FR23 | Sort output triples deterministically | Implicitly tested by `test_deterministic_output` (AC12), but no test explicitly verifies the sort key |
| FR28 | CLI exit code non-zero on parse error | Tested indirectly (Python exits 1 on uncaught exception), but no test explicitly asserts a non-zero exit code for bad input |

---

## Suggestions

- **Fix the `_Skolem_counter` typo** — this is the single most impactful one-line fix. After fixing, the skolem test should be rewritten to actually exercise the builtin through the engine (e.g., a rule with an empty body and `log:skolem` as the predicate).
- **Add `entry.py` tests** — currently all integration is via `test_integration.py` which calls `execute()`, but there are no unit tests for the orchestration logic (e.g., `nope=True` bypasses engine, `pass_mode=True` returns store contents).
- **Add `output.py` tests** — N3Writer has zero unit tests. Round-trip tests (parse → serialize → parse) would catch prefix abbreviation bugs, literal escaping edge cases, and blank node formatting.
- **Add `cli.py` tests** — use `subprocess.run` or `click.testing.CliRunner`-style approach to test CLI flag parsing and error output.
- **Consider a linter** — `ruff check pyeye/` would catch unused imports (`hashlib`, `dataclass/field`), dead code, and style issues.
- **FR23 explicit test** — add a test that verifies triple sort order: create data with triples in non-alphabetical order and assert the output is sorted.
- **`engine.py` `_handle_builtin` arg extraction** — the current `_collect_builtin_args` pattern (subject + object as args) works for `math:greaterThan(5) ?X` style but not for `(?A ?B) math:greaterThan (?C)` list-style args. The `list:in` builtin works, but most math builtins expect two scalar args passed as subject and object. Document this calling convention.
- **Phase 2: DJITI indexing** — the `_match_triples_iter` join strategy is a naive nested loop. For rule bodies with 3+ patterns over large stores, this will be the bottleneck. DJITI or a simple variable-binding-order heuristic (most-constrained-first) should be Phase 2a.
