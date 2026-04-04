# Status: pyeye Phase 2 — Full Feature Parity

## Phase 1 Baseline

- [x] 154 tests pass
- [x] All Phase 1 acceptance criteria met
- [x] Core architecture stable

## Phase 2 Progress

### 2a/2b. Extended Term Types + Full N3 Parser
- [x] Add `TripleTerm`, `FormulaTerm`, `PathTerm`, `Quad`, `NegativeSurface` dataclasses
- [x] Update unification for new term types (including NegativeSurface)
- [x] Update N3 writer for new term types + TriG output + NegativeSurface
- [x] Parser: triple terms `<< S P O >>`
- [x] Parser: formula terms `(| Functor Args |)`
- [x] Parser: `has` / `is` syntactic sugar
- [x] Parser: `of` syntactic sugar (property inversion)
- [x] Parser: BLOGIC negative surfaces
- [x] Parser: set syntax `($ a b $)` (as list, full semantics Phase 2b)
- [x] Parser: chained path expressions `!` / `^`
- [x] Backward compatibility: all 183 Phase 1 tests pass

### 2c. DJITI Indexing
- [x] Most-constrained-first join ordering
- [x] Deterministic pattern ordering
- [x] `djiti_debug` flag

### 2d. Remaining Builtins (124 total, up from 30)
- [x] Math: floor, ceiling, exponentiation, logarithm, sin, cos, tan
- [x] Math: avg, std, pcc (Pearson correlation), rms
- [x] String: regex matches, replace, substring
- [x] Crypto: md5, sha, sha256, sha512
- [x] List: car, cdr, select, remove
- [x] Log: uuid, n3String, implies, forAllIn, ask, shell, collectAllIn
- [x] Graph: member, length, difference, intersection, union, statement
- [x] Time: hours, minutes, seconds, localTime
- [x] E: calculate, findall, closure, becomes, transaction, exec, shell
- [x] RIF/XPath: concat, substring, string-length, upper/lower-case,
  contains, starts/ends-with, substring-before/after, translate,
  normalize-space, tokenize, equalTo, less/greater-than, matches

### 2e. Proof Trace Output
- [x] `ProofStep` dataclass
- [x] `ProofTree` dataclass
- [x] N3 serialization of proofs
- [x] DOT serialization of proofs
- [x] HTML serialization of proofs
- [x] Zero overhead when `explain=False`

### 2f. Backward Chaining / Tabling
- [x] `Engine.backward_chain(query)` method
- [x] Bidirectional unification (variable-to-variable binding)
- [x] Tabling (memoization) cache
- [x] `execute(query=...)` API extension
- [x] Recursive rule termination via tabling
- [x] `forward=True/False` flag

### 2g. TriG / Named Graphs
- [x] `Quad` dataclass
- [x] TriG parser (GRAPH <g> { ... })
- [ ] Graph-scoped `match(graph=...)` in store
- [ ] Full `graph:*` builtin implementations

### 2h. Entailment Modes
- [x] RDFS entailment (subClassOf, subPropertyOf, domain, range)
- [x] `execute(entail=True)` flag
- [x] `--not-entail-triple` flag

### 2i. HTTP Data Loading
- [x] HTTP/HTTPS URI support in `--n3`, `--query`
- [x] Local caching with `--wcache` / `cache_dir`

### 2j. Performance
- [ ] Binding copy optimization
- [ ] Incremental reasoning

## Blockers

_None identified._
