# Spec: pyeye — Python N3 Reasoner (Phase 2)

## Objective

Extend the Phase 1 forward-chaining reasoner into a complete, production-grade N3 reasoning engine. Phase 2 adds: full N3 grammar parsing (triple terms, formula terms, BLOGIC surfaces, `is`/`has` sugar), 200+ additional builtins (math trig, regex, crypto, graph operations, RIF/XPath), proof trace output with DOT/HTML export, backward chaining with tabling, TriG/named graph support, and performance optimizations (DJITI indexing, most-constrained-first join ordering). The `execute()` API remains compatible; new features are opt-in via additional parameters.

## Functional Requirements

### 2a. Full N3 Parser

1. Parse triple terms `<< S P O >>` (N3 reification) into a `TripleTerm` type that can appear as subject or object in other triples.
2. Parse formula terms `(| Functor Args |)` into a `FormulaTerm` type that can appear as subject or object.
3. Parse `is` syntactic sugar: `:Bob :child of :Alice` → `:Alice :child :Bob`.
4. Parse `has` syntactic sugar: `:Alice :parent has :Bob` → `:Alice :parent :Bob`.
5. Parse `of` (property inversion): `:child of :Bob` → `?X :child :Bob` where `?X` is the subject.
6. Parse BLOGIC negative surfaces: `log:onNegativeSurface { ... }` as a negation construct.
7. Parse set syntax `($ a b $)` as unordered collections (distinct from RDF lists).
8. Parse chained path expressions: `:a ! :p ! :q` (forward path composition) and `:a ^ :p` (reverse path).
9. The new parser must be backward-compatible with all Phase 1 syntax — every Phase 1 test must still pass.

### 2b. Extended Term Types

10. Add `TripleTerm(S, P, O)` as a new frozen dataclass that can appear as subject or object in triples.
11. Add `FormulaTerm(Functor: Term, Args: tuple[Term, ...])` as a new frozen dataclass.
12. Add `PathTerm(terms: tuple[Term, ...], direction: list[Literal["forward", "reverse"]])` for chained path expressions.
13. Update unification (`unify.py`) to handle the new term types recursively.
14. Update the N3 writer (`output.py`) to serialize all new term types back to valid N3.

### 2c. DJITI Indexing

15. Implement DJITI (Deep Just-In-Time Indexing): when matching a rule body with multiple triple patterns, reorder patterns so that the most-constrained pattern (fewest matching store triples) is matched first, reducing the combinatorial explosion of the nested join.
16. DJITI must be transparent to the user — same API, same output, just faster.
17. DJITI must be deterministic — same input always produces the same pattern order, preserving reproducible output.
18. Add a `--tactic djiti-debug` flag (or `execute(djiti_debug=True)`) that prints the chosen pattern order for each rule, for performance analysis.

### 2d. Remaining Builtins (~200)

19. Add all remaining EYE builtins, organized by namespace:

| Namespace | Count | Key functions |
| :--- | :--- | :--- |
| **e:** (log-rules) | ~60 | `e:calculate` (Python `eval`), `e:call` (call formula), `e:findall` (collect bindings), `e:exec` (run shell), `e:sha`, `e:random`, `e:csvTuple`, `e:becomes` (retract), `e:transaction`, `e:closure` |
| **math:** | ~20 | `sin`, `cos`, `tan`, `floor`, `ceiling`, `exponentiation`, `logarithm`, `avg`, `std`, `pcc`, `rms` |
| **string:** | ~10 | `matches` (regex), `replace`, `substring`, `scrape` |
| **list:** | ~15 | `select`, `remove`, `permutation`, `car`, `cdr` |
| **log:** | ~30 | `implies`, `isImpliedBy`, `conclusion`, `collectAllIn`, `includes`, `notIncludes`, `forAllIn`, `graph`, `semantics`, `shell`, `ask` (HTTP GET), `uuid`, `n3String` |
| **crypto:** | 4 | `md5`, `sha`, `sha256`, `sha512` |
| **graph:** | 8 | `member`, `length`, `difference`, `intersection`, `union`, `statement` |
| **RIF (func:/pred:)** | ~70 | XPath/XQuery functions: `func:concat`, `func:substring`, `pred:matches`, `func:add-dayTimeDuration`, etc. |
| **time:** | 4 | `localTime` (timezone-aware), `hours`, `minutes`, `seconds` |

20. The `e:derive` builtin must accept a list `[function_name, arg1, arg2, ...]` and call the corresponding Python function by name, returning the result as a term.
21. The `e:closure` builtin must test whether a formula is deductively closed within the current store.
22. The `e:becomes` builtin must support dynamic rule modification (retract-then-assert within a single step).

### 2e. Proof Trace Output

23. Record every derivation step in a `ProofStep` dataclass: `(conclusion: Triple, premise: Formula | None, rule: Rule, chaining: Literal["forward", "backward"], source: str)`.
24. Reconstruct proof trees from the step log: a `ProofTree` with `root: Triple`, `children: list[ProofTree]`.
25. Serialize proof trees to N3 (default): each proof step is a set of triples describing the derivation.
26. Serialize proof trees to DOT (graphviz format): `execute(explain=True, explain_format="dot")` returns a DOT string for graph visualization.
27. Serialize proof trees to HTML: `execute(explain=True, explain_format="html")` returns an HTML string with collapsible proof branches.
28. Proof recording must be opt-in (`explain=True`) — when disabled, proof recording overhead is zero.

### 2f. Backward Chaining / Tabling

29. Implement goal-directed reasoning: given a query triple (or formula), find rules whose heads unify with the query, then recursively prove their bodies.
30. Implement tabling (memoization): cache the results of sub-goals to prevent re-computation of the same query.
31. Backward chaining must be triggered explicitly via `execute(query=T("..."))` or the CLI `--query-goal` flag.
32. Backward chaining must work alongside forward chaining: `execute(data=..., rules=..., query=..., forward=True)` runs forward chaining first, then backward chains from the query against the derived store.

### 2g. TriG / Named Graphs

33. Parse TriG files (Turtle with named graphs): `GRAPH <g> { :a :p :b }`.
34. Store triples with graph IDs: `Quad(subject, predicate, object, graph)`.
35. Extend `match()` to accept an optional `graph` parameter for graph-scoped queries.
36. Add `graph:*` builtins: `graph:member`, `graph:difference`, `graph:intersection`, `graph:union`, `graph:statement`.
37. Default graph (no explicit graph ID) behaves as in Phase 1.

### 2h. Entailment Modes

38. Add `--entail` flag: before running user rules, apply RDFS entailment rules to derive implicit triples (subClassOf, subPropertyOf, domain, range).
39. Add `--not-entail` flag: check whether a specific triple is NOT entailed by the data + rules.
40. Entailment mode must be transparent: same output format, just more derived triples.

### 2i. HTTP Data Loading

41. Accept `http://` and `https://` URIs in `--n3`, `--query`, and `data_paths`.
42. Cache remote files locally (with `--wcache <uri> <path>` flag) to avoid re-downloading on every run.
43. HTTP loading must respect content-type: `text/turtle`, `text/n3`, `application/ld+json`.

### 2j. Performance

44. Most-constrained-first join ordering in `_match_triples_iter`: count matching store triples for each pattern and sort patterns ascending before the nested join.
45. Binding copy optimization: use persistent/immutable data structures or structural sharing to reduce `dict(b)` copy overhead.
46. Incremental reasoning: `Engine.add_triple()` after `run()` must support re-running without restarting from scratch (only rules affected by the new triple need re-evaluation).

### API Extensions

47. Extend `execute()` with new parameters (all optional, backward-compatible with Phase 1):
```python
def execute(
    # ... Phase 1 params ...
    # Phase 2 additions:
    explain: bool = False,
    explain_format: Literal["n3", "dot", "html"] = "n3",
    query: Triple | Formula | None = None,      # backward chaining target
    forward: bool = True,                        # run forward chain before backward
    entail: bool = False,                        # apply RDFS entailment first
    djiti_debug: bool = False,                   # print pattern order
    cache_dir: str | None = None,                # HTTP cache location
) -> Result:
```

48. Extend `Result` dataclass:
```python
@dataclass
class Result:
    triples: str
    stats: dict
    explains: list[ProofTree]  # populated when explain=True
    query_answers: list[Binding]  # populated when query is set
```

### CLI Extensions

49. Add CLI flags:
- `--entail` — enable RDFS entailment
- `--not-entail <triple>` — check non-entailment
- `--query-goal <triple>` — backward chain from this triple
- `--explain-format n3|dot|html` — proof output format
- `--wcache <uri> <path>` — cache remote file
- `--tactic djiti-debug` — print DJITI pattern ordering

## Non-Goals

- **OWL 2 RL full profile** — only RDFS entailment in Phase 2. OWL 2 is Phase 3.
- **Parallel/distributed reasoning** — single-process, single-threaded only.
- **GUI / web interface** — CLI and Python API only.
- **Persistent storage** — all data is in-memory. No on-disk triple store.
- **SPARQL endpoint** — no SPARQL query language support. The engine uses N3 rules, not SPARQL.
- **Machine learning integration** — no neural or statistical components.
- **Streaming / incremental real-time** — incremental reasoning (2j.46) is batch-level, not event-driven.

## Interfaces & Contracts

- **`pyeye.execute()`** — extended with `explain`, `explain_format`, `query`, `forward`, `entail`, `djiti_debug`, `cache_dir`. All new params default to off/None, preserving Phase 1 behavior.
- **`ProofTree`** — new dataclass: `root: Triple`, `children: list[ProofTree]`, `rule: Rule | None`, `chaining: str`.
- **`TripleTerm`** — new frozen dataclass: `subject: Term`, `predicate: Term`, `object: Term`. Hashable.
- **`FormulaTerm`** — new frozen dataclass: `functor: Term`, `args: tuple[Term, ...]`. Hashable.
- **`PathTerm`** — new frozen dataclass: `terms: tuple[Term, ...]`, `directions: list[str]`. Hashable.
- **`Quad`** — new frozen dataclass: `subject`, `predicate`, `object`, `graph: Term | None`. Hashable. Graph `None` = default graph.
- **`TripleStore`** — extended with `match(graph=...)` parameter. `add()` accepts `Quad` (stored in named graph) or `Triple` (stored in default graph).
- **`Engine`** — extended with `backward_chain(query)`, `apply_rdfs_entailment()`, and `proof_steps: list[ProofStep]` attribute.

## Acceptance Criteria

- [ ] Every Phase 1 test still passes (backward compatibility).
- [ ] Triple term parsing: `<< :a :p :b >> :wasSaidBy :alice .` parses without error and produces a `TripleTerm`.
- [ ] `is` sugar: `:Bob :child of :Alice .` parses to `:Alice :child :Bob .`.
- [ ] BLOGIC negative surface: `log:onNegativeSurface { :a :p :b }` parses and prevents derivation of the negated formula when `:a :p :b` is in the store.
- [ ] DJITI reordering: a rule with 3 body patterns over a store where pattern C matches 1 triple, pattern A matches 100, and pattern B matches 50 — DJITI orders them C, B, A (ascending by match count).
- [ ] 200+ new builtins registered and callable. At least one builtin from each new namespace (e:, math, string, list, log, crypto, graph, RIF, time) has a unit test.
- [ ] Proof tree: `execute(explain=True, ...)` returns a non-empty `explains` list with `ProofTree` objects. `explain_format="dot"` returns valid DOT syntax. `explain_format="html"` returns valid HTML.
- [ ] Backward chaining: `execute(query=Triple(...))` returns `query_answers` with at least one binding when the query matches derived facts.
- [ ] Tabling: a recursive rule (e.g., transitive closure) with backward chaining terminates via tabling (no infinite recursion).
- [ ] TriG parsing: `GRAPH <g1> { :a :p :b } GRAPH <g2> { :a :p :c }` stores triples in separate named graphs. `match(graph=NamedNode("g1"))` returns only `:a :p :b`.
- [ ] RDFS entailment: with `entail=True`, data `:Cat rdfs:subClassOf :Animal . :Fluffy a :Cat .` derives `:Fluffy a :Animal .` before user rules run.
- [ ] HTTP loading: `execute(data_paths=["http://example.org/data.ttl"])` fetches and parses the file. With `cache_dir="/tmp/cache"`, subsequent runs use the cached copy.
- [ ] Performance: on the EYE test suite (`test/` in the EYE repo), Phase 2 completes at least 50% of tests within 2× the runtime of EYE (Prolog) on the same machine.
- [ ] `pyeye --help` lists all new Phase 2 flags.
- [ ] `Result.explains` is always `[]` when `explain=False` (zero overhead when proofs are not requested).
- [ ] All new code has unit tests. Total test count ≥ 300 (Phase 1: 154).
