# Architecture: pyeye vs EYE and eyeling

pyeye is a pure-Python reimplementation of the EYE N3 reasoner. Its two
reference implementations are:

- **EYE** — `eye.pl`, SWI-Prolog (~14.4k lines). The Euler Abstract Machine
  (EAM): forward chaining over `=>` rules whose premises are proved by Prolog's
  native backward resolution, with backward `<=` rules compiled to Prolog
  clauses.
- **eyeling** — `eyeling.js`, JavaScript (~12.8k lines). A faithful port of EYE
  that does not rely on a Prolog substrate: it implements its own term model,
  trail-based unification, an iterative backward prover with goal tabling, and
  an agenda-driven forward-chaining fixpoint.

pyeye follows eyeling's shape (no Prolog substrate, explicit term model and
unifier) while making Python-idiomatic data-structure choices. This page maps
each subsystem across the three and states where pyeye diverges and why. Design
per-area conformance gaps are in the corpus harness (`run_corpus.py`,
`tests/test_eye_corpus.py`).

---

## 1. Term representation

| Concept | EYE (`eye.pl`) | eyeling (`eyeling.js`) | pyeye (`term.py`) |
| --- | --- | --- | --- |
| IRI | Prolog atom | `Iri{value}`, interned, `__tid` | `NamedNode(value)` frozen dataclass |
| Literal | atom / number | `Literal{value}` (datatype/lang in lexical), interned | `Literal(value, datatype, language)` |
| Variable | Prolog var | `Var{name}` | `Variable(name, id)` |
| Blank node | `_:` atom / var | `Blank{label}`, interned | `Existential(name)` |
| List | Prolog list `[..]` | `ListTerm{elems}`, `OpenListTerm{prefix,tailVar}` | `ListTerm(items: tuple)` |
| Formula/graph | conjunction `(A,B)` | `GraphTerm{triples}` | `Formula(triples: tuple)` |
| Triple | `P(S,O)` compound | `Triple{s,p,o}` | `Triple(subject, predicate, object)` |
| RDF-star triple term | — | — (N3 uses graphs) | `TripleTerm(s,p,o)` |

All pyeye terms are **frozen dataclasses**, hashable by value. This gives the
same O(1) set/dict membership eyeling gets from its `__tid` interning, without a
separate intern table — Python's hash of an immutable dataclass is the
equivalent. pyeye additionally carries `NegativeSurface`, `FormulaTerm`, and
`SetTerm` for N3-plus surfaces; eyeling models negation through `log:`
predicates rather than a dedicated term.

**Divergence — variable identity.** EYE uses opaque Prolog variable identity;
eyeling keys substitutions by variable *name* (string) and relies on a trail to
scope rule applications. pyeye gives every `Variable` a unique integer `id` and
keys bindings by that id (`Binding = dict[int, Term]`). This is the single most
consequential data-structure choice: it removes the name-collision class of bugs
when the same rule is applied at multiple recursion depths, at the cost of
needing an explicit fresh-variable copy per rule application (`copy_rule` in
`engine.py`) rather than a trail mark.

---

## 2. Store and indexing

| | EYE | eyeling | pyeye |
| --- | --- | --- | --- |
| Facts | Prolog clause DB | array + hidden indexes | `TripleStore` (`store.py`) |
| Index | first-argument indexing | `__byPred`, `__byPS`, `__byPO`, wildcard maps, `__keySet` | dict-of-sets keyed by predicate, plus subject/object maps |
| Membership | `clause/2` | `__keySet` O(1) | set membership O(1) |
| Rules | `implies/3` facts + `:-` clauses | array + `__byHeadPred` | `Rule` list on the engine |

pyeye and eyeling agree on the strategy: index primarily by predicate, then
narrow by subject or object, choosing the smaller candidate list. pyeye's
indexing is coarser (it does not maintain separate predicate-subject *and*
predicate-object two-level maps as aggressively as eyeling), which matters only
for performance on large fact sets, not correctness.

---

## 3. Unification and bindings

| | EYE | eyeling | pyeye (`unify.py`) |
| --- | --- | --- | --- |
| Mechanism | native Prolog `=/2` | `unifyTermTrail` (mutating) + `unifyTerm` (pure) | `unify` / `unify_terms` (pure) |
| Bindings | Prolog bindings | `{name: Term}` + **trail** | `{Variable.id: Term}`, copy-on-extend |
| Occurs check | yes | `containsVarTerm` | `term_contains_var` |
| Backtracking | native | `undoTo(mark)` trail unwind | none — pure functional dicts |
| List unification | native | element-wise + open-list tail | element-wise on `ListTerm` |
| Cross-datatype numeric eq | — | value-equivalence in unify | `_literals_equivalent` |

**Divergence — no trail.** eyeling mutates a shared substitution and unwinds it
on backtrack via a trail; this keeps a single binding object alive across the
whole proof. pyeye instead threads immutable binding dicts and produces extended
copies. This is simpler and avoids a whole class of trail-management bugs, but it
means a binding's size grows with the depth of the resolution that produced it
(see §5).

---

## 4. Rules: forward, backward, query

All three represent a rule as premise + conclusion + a forward/backward flag.

- `{B} => {H}` and `log:implies` → **forward** rule.
- `{H} <= {B}` and `log:impliedBy` → **backward** rule.
- query rules (`log:query` / `--query` files, EYE's `impliesAnswer`) →
  evaluated against the final store and their conclusions emitted as the answer
  set, without being added to the closure.

pyeye stores forward and backward rules in one list and distinguishes them with
`Rule.is_backward`; `run()` applies forward rules to fixpoint while
`_resolve_bc` uses any rule head as a backward resolution target. EYE keeps the
two physically separate (EAM `implies/3` facts vs Prolog `:-` clauses); eyeling
keeps one `Rule` array and a `__byHeadPred` index for backward lookup. pyeye is
closer to eyeling here.

**Rule-producing rules.** EYE asserts derived clauses; pyeye promotes a derived
`{body} log:implies {head}` triple into a new `Rule` during forward chaining
(`_apply_rule`), deduplicated by structural hash. This covers the common case
but not the full nested-rule meta-reasoning EYE gets for free from `assertz`
(e.g. a rule whose *premise* contains another rule to be matched against the
rule base).

---

## 5. Core reasoning algorithm

This is where the three differ most.

**EYE — Euler Abstract Machine** (`eam/1`, ~line 5272). Select a forward rule
`P => C`; prove `P ∧ ¬C` by Prolog backward resolution; if it holds, assert `C`
and clear the `brake`; loop until `brake` stays set. Loop detection is the
"Euler path": a `brake` flag halts when a pass derives nothing, `cc/ccd`
deduplicate ground conclusions so isomorphic facts are never re-asserted, and a
`recursion/1` depth counter bounds regress.

**eyeling — iterative prover + agenda fixpoint.** Backward chaining
(`proveGoals`, ~line 7527) is an **explicit stack machine** (frame kinds `node`,
`ruleIter`, `factIter`, `deltaIter`, `undo`) — no host-language recursion, so
proof depth is unbounded. Loop detection is a trail-backed **visited multiset**
plus a cheap guard that avoids re-entering a visited goal through a rule premise;
**goal tabling** (`__goalTable`) memoizes answers for goals that have no
loop-check ancestor. Forward chaining (`forwardChain`, ~line 8192) is an
agenda-driven saturation with a two-phase loop that toggles scoped builtins
(e.g. `log:collectAllIn`) so a closure is complete before scope-sensitive
builtins read it.

**pyeye — recursive prover + rule-sweep fixpoint** (`engine.py`).
`run()` sweeps all forward rules each pass, applying `_match_formula` to each
body and asserting ground heads, repeating until a pass derives nothing (the
analogue of EYE's brake). A per-pass `processed` set of `(rule, binding)` pairs,
and a cross-pass `global_processed` set for `@forSome` rules, prevent
re-firing. Backward resolution (`_resolve_bc`) is **directly recursive in
Python**: for a goal it tries store matches, then unifies the goal against every
rule head and recursively matches the body. Loop detection is an **on-stack
goal-key set** (`_bc_stack`) that returns `[]` for a goal already being proved,
plus a **tabling cache** (`_tabling_cache`) keyed by a structural goal key.

### Divergences and their consequences

1. **Recursion model.** pyeye recurses on the Python stack where eyeling uses an
   explicit frame stack. Deep recursive scenarios therefore require raising the
   interpreter recursion limit and remain bounded by it; eyeling and EYE are
   not. This is the structural reason the deep-recursion corpus scenarios
   (`ackermann`, `takeuchi`, `gcd-bezout-identity`, `deep-taxonomy`, `edt`) are
   the hardest cluster.

2. **Binding accumulation → O(depth²).** Because pyeye threads immutable
   bindings (no trail) and `_match_patterns_sequential` carries the caller's
   binding into each sub-goal, a binding accumulates every intermediate
   variable introduced down a recursive chain. Resolving and copying an
   O(depth)-sized binding at every one of O(depth) levels makes a *linear*
   (accumulator-style) recursion run in quadratic time. `_resolve_bc` mitigates
   this by **projecting** each answer onto the goal's own variables plus the
   caller's keys and deduplicating before caching — the practical equivalent of
   tabling's answer-table sharing — but the binding still threads into sub-goals
   at full size, so the projection bounds the *answer* set, not the *input*. A
   complete fix aligns with eyeling: resolve a rule body in a fresh scope (the
   goal pattern already carries the caller's substitution) and merge only the
   goal-relevant answers back. This is the main outstanding engine divergence.

3. **Loop-detection semantics.** pyeye's on-stack set *cuts* a goal that is
   already on the stack (returns no answers for that branch). eyeling's visited
   multiset *allows* controlled re-entry (needed for sibling goals in some Horn
   patterns) and only suppresses immediate self-re-entry through a premise.
   pyeye's coarser cut is safe for termination but can under-derive on rule sets
   that legitimately re-enter a goal at a different binding.

4. **Scoped-builtin phasing.** EYE and eyeling complete the relevant closure
   before evaluating scope-sensitive builtins (`log:collectAllIn`,
   `log:forAllIn`, `log:callWithOptional`). pyeye evaluates builtins inline
   during body matching, ordered by its DJITI pass (`_djiti_order`, see §6)
   rather than by a global two-phase fixpoint. This is why the
   collect/forall/optional family is the largest single FAIL cluster in the
   corpus: the builtin reads an incomplete closure.

---

## 6. Builtin dispatch and ordering

| | EYE | eyeling | pyeye (`builtins.py`) |
| --- | --- | --- | --- |
| Registry | per-predicate Prolog clauses | `evalBuiltin` switch, ~88 builtins | `BUILTIN_REGISTRY: {IRI: fn}` |
| Result shape | bindings | array of substitution deltas | `Term` / `list[Term]` / `MultiResult` / bool |
| Ordering | DJITI (deep just-in-time indexing) | `allowDeferredBuiltins` rotation | `_djiti_order` most-constrained-first + producer→consumer topological sort |
| Integer math | GNU Prolog bignums | BigInt | Python `int`, preserved via `_num_exact` |

pyeye registers a superset of eyeling's namespaces (math, string, list, log,
time, crypto, plus rdf/rdfs/owl helpers). Dispatch is a flat IRI→function dict,
matching eyeling's switch.

**Ordering.** Both EYE and eyeling reorder body goals so a builtin fires only
once its inputs are bound. pyeye's `_djiti_order` reproduces this with a
two-stage pass: store patterns first (fewest candidate matches first), then
builtins and deferred patterns scheduled by a greedy topological sort keyed on
unbound *input* variables — so a producer builtin (e.g. `log:collectAllIn`
binding a list) schedules before its consumer (`math:sum` over that list). A
store pattern whose input is produced by a builtin is deferred so it cannot
greedily match an unrelated fact first.

**Integer math.** pyeye preserves arbitrary-precision integers: `_num_exact`
returns a Python `int` for `xsd:integer` operands and arithmetic stays in
integer space (`math:sum`, `math:product`, `math:difference`, `math:plus`,
`math:minus`, `math:times`), with `_typed_num_result` emitting `xsd:integer`
when all inputs are integers. This matches eyeling's BigInt behavior and is
required for scenarios whose answers are hundreds of digits (`fibonacci`,
`goldbach`, `kaprekar`). General `_num_val` still returns float for genuinely
real-valued operations (trig, division, durations, dates).

---

## 7. Path expressions

All three **compile path expressions away at parse time** rather than evaluating
them at runtime — `x!p` becomes a fresh node `b` plus a triple `x p b`, and
`x^p` becomes `b p x`, with the path's value being the final fresh node.

- eyeling introduces a fresh **blank** `_:bN` per step.
- pyeye introduces a fresh **`Variable`** per step (`_maybe_path` in
  `parser.py`).

**Divergence and rationale.** In a rule body the path node is an *output slot*
to be bound (often by a builtin — e.g. `(?X 1)!math:difference` binds the
difference, which then feeds a recursive call). A blank node is a constant and
cannot receive a builtin's result, so pyeye uses a logic `Variable`, which both
unifies against the store like a blank would and can be bound by a builtin.
`_maybe_path` is applied uniformly after every term — including composite terms
(lists, formulas, blank-node groups, triple/formula/set terms) — so a path that
hangs off a list subject such as `(?X 1)!math:difference` compiles correctly
rather than leaving a dangling operator. `PathTerm` is therefore not part of the
resolved term model; paths never reach the engine.

---

## 8. Proof output

| | EYE | eyeling | pyeye (`proof.py`) |
| --- | --- | --- | --- |
| Form | RDF `reason:`/`r:Proof` graph with skolem genids | human-readable stdout comments | `ProofStep` / `ProofTree`, internal |

pyeye builds an internal proof tree (premises, rule, chaining direction, child
trees) when run with `explain=True`, structurally close to EYE's `prfstep`
records. It does not yet serialize that tree into EYE's `reason:`-vocabulary RDF
proof graph. The corpus scenarios whose reference output is a full proof trace
(24 of them — `bmi`, `crypto`, `graph`, `zebra`, …) are tracked as a separate
cluster precisely because matching them needs this serializer, not because the
underlying reasoning differs.

---

## 9. Summary of intentional divergences

| Area | pyeye choice | vs reference | Reason |
| --- | --- | --- | --- |
| Variable identity | integer `id`, bindings keyed by id | eyeling keys by name + trail | removes depth-collision bugs without a trail |
| Backtracking | pure immutable bindings | eyeling trail unwind | simpler; no trail bookkeeping |
| Term identity | frozen dataclass hash | eyeling `__tid` intern table | same O(1) equality, no intern table |
| Path node | fresh `Variable` | eyeling fresh blank | path node must be bindable by builtins |
| Rule storage | one list + `is_backward` | EYE separate clause DB | closer to eyeling; uniform resolution |

## 10. Summary of outstanding gaps (engine-level)

| Gap | Effect | Reference behavior to adopt |
| --- | --- | --- |
| Recursive Python prover | depth bounded by interpreter limit | eyeling explicit frame stack |
| Binding threaded into sub-goals at full size | O(depth²) on linear recursion | resolve body in fresh scope, merge goal-relevant answers |
| On-stack cut loop detection | can under-derive on legitimate re-entry | eyeling visited multiset with controlled re-entry |
| Inline (non-phased) scoped builtins | `collectAllIn`/`forAllIn` read incomplete closure | EYE/eyeling two-phase scoped fixpoint |
| No `reason:` proof serializer | 24 proof-format scenarios unmatched | EYE `r:Proof` graph output |

See the corpus harness for the current per-scenario status.
