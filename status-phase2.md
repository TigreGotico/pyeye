# Status: pyeye Phase 2 — Full Feature Parity

## Phase 1 Baseline

- [x] 154 tests pass
- [x] All Phase 1 acceptance criteria met
- [x] Core architecture stable

## Phase 2 Progress

### 2a/2b. Extended Term Types + Full N3 Parser
- [x] Add `TripleTerm`, `FormulaTerm`, `PathTerm`, `Quad` dataclasses
- [x] Update unification for new term types
- [x] Update N3 writer for new term types + TriG output
- [x] Parser: triple terms `<< S P O >>`
- [x] Parser: formula terms `(| Functor Args |)`
- [x] Parser: `has` syntactic sugar
- [ ] Parser: `is` / `of` syntactic sugar
- [ ] Parser: BLOGIC negative surfaces
- [x] Parser: set syntax `($ a b $)` (as list, full semantics Phase 2b)
- [x] Parser: chained path expressions `!` / `^`
- [x] Backward compatibility: all 183 Phase 1 tests pass

### 2c. DJITI Indexing
- [x] Most-constrained-first join ordering
- [x] Deterministic pattern ordering
- [x] `djiti_debug` flag

### 2d. Remaining Builtins
- [ ] Math: trig, floor, ceiling, exponentiation, logarithm, stats
- [ ] String: regex matches, replace, substring, scrape
- [ ] List: select, remove, permutation, car, cdr
- [ ] Log: implies, isImpliedBy, collectAllIn, shell, ask, uuid, n3String
- [ ] Crypto: md5, sha, sha256, sha512
- [ ] Graph: member, length, difference, intersection, union, statement
- [ ] RIF/XPath: ~70 functions
- [ ] e: derive, calculate, call, findall, exec, becomes, transaction, closure

### 2e. Proof Trace Output
- [ ] `ProofStep` dataclass
- [ ] `ProofTree` dataclass
- [ ] N3 serialization of proofs
- [ ] DOT serialization of proofs
- [ ] HTML serialization of proofs
- [ ] Zero overhead when `explain=False`

### 2f. Backward Chaining / Tabling
- [ ] `Engine.backward_chain(query)` method
- [ ] Tabling (memoization) cache
- [ ] `execute(query=...)` API extension
- [ ] Recursive rule termination via tabling

### 2g. TriG / Named Graphs
- [ ] `Quad` dataclass
- [ ] TriG parser
- [ ] Graph-scoped `match(graph=...)`
- [ ] `graph:*` builtins

### 2h. Entailment Modes
- [ ] RDFS entailment rules
- [ ] `--entail` flag
- [ ] `--not-entail` flag

### 2i. HTTP Data Loading
- [ ] HTTP/HTTPS URI support in `--n3`, `--query`
- [ ] Local caching with `--wcache`

### 2j. Performance
- [ ] Binding copy optimization
- [ ] Incremental reasoning

## Blockers

_None identified._
