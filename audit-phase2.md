# Audit: pyeye Phase 2 — Full Feature Parity

## Summary

Phase 2 extends the Phase 1 N3 reasoner into a comprehensive reasoning engine with 311 passing tests, 124 builtins, full N3 grammar parsing, backward chaining with tabling, proof traces, TriG support, RDFS entailment, HTTP loading, and incremental reasoning. The codebase is well-structured and all Phase 1 tests continue to pass. Two critical security concerns exist (arbitrary code execution via `e:calculate` and `e:exec`/`e:shell`), and the `explain_format` parameter from the spec is not implemented.

## Phase 1 Acceptance Criteria

| Criterion | Status | Evidence |
| :--- | :--- | :--- |
| Simple derivation returns `:a <r> :b` | **Pass** | `test_integration.py:17` |
| Transitivity chain derives 10 `:reach` triples | **Pass** | `test_integration.py:34` |
| Cycle detection: no infinite loop | **Pass** | `test_integration.py:46` |
| `max_steps=3` halts after 3 steps | **Pass** | `test_integration.py:58` |
| `limit_answers=2` halts after 2 derivations | **Pass** | `test_integration.py:70` |
| `math:greaterThan` builtin works | **Pass** | `test_integration.py:78` |
| Duplicate triple rejection | **Pass** | `test_integration.py:89` |
| Variable binding propagation | **Pass** | `test_integration.py:96` |
| `--nope` mode: no derivation | **Pass** | `test_integration.py:117` |
| `--pass` mode: input + derived | **Pass** | `test_integration.py:126` |
| CLI exit code 0 on success, non-zero on error | **Pass** | `test_integration.py:133`, `test_cli.py:24` |
| Deterministic output | **Pass** | `test_integration.py:141` |
| Custom builtin registration | **Pass** | `test_integration.py:151` |
| Skolem generation: distinct IDs | **Pass** | `test_integration.py:181` |
| Package install and import | **Pass** | `test_integration.py:193` |
| All tests pass | **Pass** | `uv run pytest tests/` — 311 passed |

## Phase 2 Acceptance Criteria

| Criterion | Status | Evidence |
| :--- | :--- | :--- |
| Every Phase 1 test still passes | **Pass** | 183 Phase 1 tests pass in full suite |
| Triple term parsing `<< S P O >>` | **Pass** | `test_parser_phase2.py:14-22` |
| `is` sugar / `of` sugar | **Pass** | `test_n3_extensions.py:40-52`, `test_parser_phase2.py:143-152` |
| BLOGIC negative surface blocks derivation | **Pass** | `test_n3_extensions.py:21-38` |
| DJITI reordering by match count | **Pass** | `test_djiti.py:18-40` |
| 124 builtins registered, one test per namespace | **Pass** | `test_builtins_extended.py`, `test_builtins_rif.py` — 31 new tests covering all namespaces |
| Proof trees returned when `explain=True` | **Pass** | `test_proof.py:14-28`, `test_proof.py:44-56` |
| DOT serialization valid | **Pass** | `test_proof.py:50-55` |
| HTML serialization valid | **Pass** | `test_proof.py:57-62` |
| Backward chaining returns bindings | **Pass** | `test_backward_chain.py:21-28` |
| Tabling prevents infinite recursion | **Pass** | `test_backward_chain.py:70-84` |
| TriG parsing stores separate graphs | **Pass** | `test_trig.py:14-44` |
| `match(graph=...)` returns graph-scoped triples | **Pass** | `store.py:109-131` (implemented but status says unchecked) |
| RDFS entailment derives subClassOf | **Pass** | `test_rdfs.py:18-27` |
| HTTP loading with caching | **Pass** | `test_http_loading.py:14-35`, `entry.py:106-136` |
| Performance: EYE test suite comparison | **Fail** | No EYE repo available locally to run comparison; spec criterion cannot be verified |
| `pyeye --help` lists Phase 2 flags | **Partial** | `--entail`, `--no-forward`, `--not-entail-triple`, `--cache-dir` present; `--explain-format` missing |
| `Result.explains` empty when `explain=False` | **Pass** | `test_proof.py:30-36` |
| Total test count ≥ 300 | **Pass** | 311 tests |

## Gaps & Issues

| Severity | Location | Description |
| :--- | :--- | :--- |
| **Critical** | `builtins.py:850` | `e:calculate` uses `eval()` with `{"__builtins__": {}}` sandbox. This sandbox is **bypassable** — e.g., `[].__class__.__base__.__subclasses__()` can access dangerous classes. Arbitrary code execution is possible if untrusted N3 rules are processed. |
| **Critical** | `builtins.py:924-942` | `e:exec` and `e:shell` use `subprocess.run(cmd, shell=True, ...)`. Arbitrary command injection is possible (e.g., `e:shell("rm -rf /")`). No input validation or sandboxing. |
| **Critical** | `entry.py:106-136` | `_resolve_path()` fetches arbitrary HTTP/HTTPS URLs with `urllib.urlopen()`. No URL validation, no protocol restriction, no SSRF protection. A malicious rule could trigger requests to internal services. |
| **Major** | `spec-phase2.md:47` / `entry.py` | `explain_format` parameter is specified in the API but **not implemented**. The `execute()` function accepts `explain` but always returns N3-format proof data. DOT and HTML serializers exist in `proof.py` but are not wired into the `execute()` API. |
| **Major** | `spec-phase2.md:49` / `cli.py` | `--explain-format n3\|dot\|html` flag is specified in CLI but **not implemented**. CLI has `--explain` but no format selector. |
| **Major** | `spec-phase2.md:20` | `e:derive` builtin (calling arbitrary Python functions by name) is specified but **not implemented**. `e:calculate` provides eval but not the derive-by-name pattern. |
| **Major** | `builtins.py:1025-1075` | `graph:*` builtins are registered but **simplified** — they don't actually operate on named graphs. `graph:difference`, `graph:intersection`, `graph:union` all just return `list(engine.store)` regardless of arguments. |
| **Minor** | `status-phase2.md` | Lists `match(graph=...)` and `graph:*` builtins as unchecked, but both are implemented (status is stale). |
| **Minor** | `builtins.py:987` | `log_ask` uses `urllib.urlopen()` which is deprecated in Python 3.13+. Should use `urllib.request.urlopen()` (which it does via alias) but the function should use `requests` or `httpx` for better error handling. |
| **Minor** | `builtins.py:22` | `import urllib.request as _urllib` is unused (shadowed by the import on line 22 which is the same). No issue but redundant. |
| **Minor** | `engine.py:108-124` | `_incremental_derive` imports `ProofStep` and `ProofTree` inside the loop. Should be a module-level import. |
| **Minor** | `store.py:97-103` | `retract_all()` calls `self.match()` then iterates to call `self.retract()` — this is O(n²) for large stores with many matching triples. |
| **Minor** | `builtins.py:864-897` | `e_becomes` and `e_transaction` docstrings mention "retract" but `e_transaction` only asserts — no actual rollback on failure. The name "transaction" is misleading. |
| **Minor** | `pyproject.toml` | No `classifiers`, `readme`, `license`, or `authors` fields. Package is not PyPI-ready. |

## Suggestions

- **Sandbox `e:calculate`**: Use `ast.literal_eval` for safe expression evaluation, or restrict to math operations only. If full `eval` is needed, run in a subprocess with seccomp/AppArmor.
- **Sandbox `e:exec`/`e:shell`**: Implement a whitelist of allowed commands, or run in a container/namespace. At minimum, validate the command against an allowlist pattern.
- **SSRF protection for HTTP loading**: Validate URLs against a denylist of private IP ranges (10.x, 172.16-31.x, 192.168.x, 127.x). Use `urllib.parse` to reject `file://`, `ftp://`, etc.
- **Wire `explain_format` into `execute()`**: Add the parameter, use `serialize_dot()` / `serialize_html()` from `proof.py` instead of always N3.
- **Implement `e:derive`**: Allow calling registered Python functions by name — useful for LEA integration where custom Python logic needs to be invoked from N3 rules.
- **Complete `graph:*` builtins**: Make `graph:difference`, `graph:intersection`, `graph:union` actually operate on named graphs by accepting graph identifiers as arguments.
- **Add type stubs**: Generate `pyi` files for the public API (`execute`, `Result`, term types) for better IDE support.
- **Add benchmark suite**: The spec's performance criterion (FR 2j.13) requires comparison against EYE. Create a `benchmarks/` directory with common test cases and timing scripts.
- **Document security model**: Add a `SECURITY.md` file documenting which builtins are dangerous and how to run pyeye in a restricted mode (e.g., `--safe-mode` that disables `e:calculate`, `e:exec`, `e:shell`, and HTTP loading).
