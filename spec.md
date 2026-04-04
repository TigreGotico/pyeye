# Spec: pyeye — Python N3 Reasoner (Phase 1)

## Objective

Implement a pure-Python forward-chaining N3 reasoner that accepts N3 data files and N3 rule files, derives the deductive closure via the Euler Abstract Machine, and outputs the result as N3 text. The library must be importable as a Python package (`from pyeye import execute`) and runnable as a CLI tool (`pyeye --n3 data.n3 --query rules.n3`). Phase 1 covers the minimal feature set needed to run non-trivial rule sets — no tabling, no full N3 grammar, no proof graph output.

## Functional Requirements

### Data Ingestion
1. Parse N3/Turtle data files into an internal triple store using rdflib as the parser backend.
2. Accept data from file paths (`--n3`) and inline strings (`execute(data_strings=[...])`).
3. Resolve `@prefix` and `@base` directives in data files and propagate them to output serialization.

### Rule Parsing
4. Parse N3 rule files containing `{P} => {C}` (forward) and `{C} <= {P}` (backward) syntax using a hand-written recursive descent parser.
5. Parse variables (`?name`), blank nodes (`[]`, `_:name`), RDF lists `(a b c)`, and prefixed names in rule bodies and heads.
6. Parse `@forSome` (existential) and `@forAll` (universal) quantifier directives and scope them to the containing formula.
7. Load rules from file paths (`--query`) and inline strings (`execute(rule_strings=[...])`).

### Triple Store
8. Store triples in a set with a predicate-based index that accelerates pattern matching when the predicate is bound.
9. Reject duplicate triples (idempotent add — returns True only for genuinely new triples).
10. Support wildcard pattern matching on subject, predicate, and/or object (`None` = match any).

### Unification
11. Perform structural unification between a triple pattern (with Variable slots) and a ground triple from the store, producing a binding map.
12. Enforce occurs check: a variable cannot bind to a term containing itself.
13. Propagate bindings across successive pattern matches within a rule body (variable `?X` bound in the first pattern must match consistently in the second).

### Reasoning Engine
14. Implement the Euler Abstract Machine: iterate rules in order, match body patterns against the store, derive head instances, repeat until fixpoint (no new derivations in a full pass).
15. Detect and skip cycles: if a derived triple is already present in the store, do not re-assert it or re-fire the rule.
16. Respect `max_steps` limit: halt reasoning after N total inference steps.
17. Respect `limit_answers` tactic: halt after N new derivations (across all rules).
18. Process rules in a deterministic order (source file order) so that output is reproducible.

### Builtins
19. Evaluate builtin predicates appearing in rule bodies when all their arguments are ground. The following builtins must be supported:
    - **math:** `equalTo`, `lessThan`, `greaterThan`, `notEqualTo`
    - **string:** `concatenation`, `contains`, `length`, `startsWith`, `endsWith`, `equal`
    - **time:** `now`, `year`, `month`, `day`, `in-seconds`
    - **list:** `in` (membership), `length`
    - **log:** `outputString`, `skolem`, `content`
    - **type:** `isLiteral`, `isNumeric`, `str`, `iri`
20. Allow users to register custom builtins via `execute(builtins={iri: callable})`.
21. When a builtin's arguments are not yet ground (contain unbound variables), skip evaluation and let later pattern matches ground them.

### Output
22. Serialize all derived triples (not input facts, unless `--pass` or `--pass-all`) to N3 text with prefix abbreviation.
23. Sort output triples deterministically (by subject, then predicate, then object).
24. Support `--nope` mode: pass through input data with no derivation.

### API
25. Expose `execute()` function accepting: `data_paths`, `data_strings`, `rule_paths`, `rule_strings`, `builtins`, `explain`, `max_steps`, `limit_answers`, `prefixes`.
26. Return a `Result` dataclass with fields: `triples` (str), `stats` (dict with `steps`, `derived`, `time_ms`), `explains` (list, empty in Phase 1).

### CLI
27. Provide `pyeye` CLI command with flags: `--n3`, `--query`, `--pass`, `--pass-all`, `--nope`, `--tactic limited-answer N`, `--max-inferences N`, `--prefix`, `--quiet`, `--statistics`.
28. Exit code 0 on success, non-zero on parse error or step limit exceeded.

## Non-Goals

- **Backward chaining / tabling** — Phase 1 is forward-chaining only.
- **Full N3 grammar** — triple terms `<< >>`, formula terms `(| |)`, BLOGIC surfaces, `is`/`has` sugar, and set syntax are deferred to Phase 2.
- **Proof tracing / explanation trees** — the `explain` flag is accepted but returns an empty list. Proof recording is Phase 2.
- **TriG / named graphs** — single-graph operation only. Quad support is Phase 2.
- **Entailment modes** — no `--entail` / RDFS / OWL RL support in Phase 1.
- **Performance optimization** — no RETE network, no parallel rule application, no incremental reasoning. Predicate index is the only performance feature.
- **HTTP data loading** — no `http://` URI fetching in Phase 1. All inputs must be local files or strings.
- **EYE builtin parity** — the ~200 builtins beyond the curated ~40 listed above are Phase 2.

## Interfaces & Contracts

- **`pyeye.execute()`** — Python API. Input: N3 data + rules (paths or strings). Output: `Result(triples, stats, explains)`.
- **`pyeye` CLI** — `pyeye --n3 <file> --query <file> [--pass] [--nope] [--max-inferences N] [--tactic limited-answer N] [--statistics]`. Reads local files, writes N3 to stdout, stats to stderr.
- **Triple** — internal dataclass: `Triple(subject: Term, predicate: Term, object: Term)`. Hashable, equality by value.
- **Term hierarchy** — frozen dataclasses: `NamedNode(value)`, `Literal(value, datatype?, language?)`, `Variable(name)`, `Existential(name)`, `Formula(triples)`.
- **Builtin protocol** — `evaluate(args: list[Term], engine: Engine) -> Term | list[Triple] | None`. Return `None` to skip (unground args), return `Term` for function-style builtins, return `list[Triple]` for predicate-style builtins that assert into the store.
- **rdflib** — used internally for parsing N3 data files. Not exposed in the public API. Consumers of `pyeye` do not need to install or interact with rdflib directly.

## Acceptance Criteria

- [ ] `execute(data_strings=["<a> <p> <b>."], rule_strings=["{?X <p> ?Y} => {?X <r> ?Y}."])` returns `:a <r> :b` in the output triples.
- [ ] Transitivity chain: 5 rules of the form `{?A :next ?B} => {:A :reach ?B}` with data forming a 10-node chain derives exactly 10 `:reach` triples.
- [ ] Cycle detection: a rule `{?X :r ?Y} => {?X :r ?Y}` does not cause infinite looping; engine reaches fixpoint after 0 new derivations.
- [ ] `max_steps=3` halts the engine after exactly 3 inference steps, even if fixpoint is not reached.
- [ ] `limit_answers=2` halts after exactly 2 new derived triples.
- [ ] `math:greaterThan` builtin correctly evaluates `{?X :val ?V} {literal("5"^^xsd:integer) :val ?C} {math:greaterThan(?V, ?C)} => {?X :aboveFive true}`.
- [ ] Duplicate triple rejection: adding the same fact twice results in exactly one copy in the store.
- [ ] Variable binding propagation: in a rule body `{:A :p ?X} {:X :q ?Y}`, `?X` bound by the first pattern is consistently used to match the second pattern.
- [ ] `--nope` mode: output equals input data with no derived triples.
- [ ] `--pass` mode: output includes both input facts and derived triples.
- [ ] CLI exit code is 0 for successful runs, non-zero for unparseable N3 input.
- [ ] Output is deterministic: running the same inputs twice produces byte-identical N3 output.
- [ ] Custom builtin registration: `execute(builtins={"ex:double": double_fn})` allows a rule body to call `ex:double` and get the registered result.
- [ ] Skolem generation: two invocations of `log:skolem` in different rule firings produce distinct existential identifiers.
- [ ] Package installs via `pip install -e .` and `from pyeye import execute` works without errors.
- [ ] All tests pass with `pytest`.
