# Plan: Python Port of EYE Reasoner

## Architecture Decision

- **Two-phase approach**: Phase 1 = Eyeling-style core (parser + engine + curated builtins). Phase 2 = DJITI indexing, full N3 grammar, 250+ builtins, proof graph output.
- **Parser**: Use `rdflib` N3 parsing for Phase 1, with a migration path to a hand-written parser in Phase 2 for rule-body formula parsing (rdflib cannot parse N3 rules `{P} => {C}` — only data triples).

## The rdflib Caveat

`rdflib` parses N3/Turtle **data** (triples, literals, prefixed names) but **not N3 rules** (`{P} => {C}`, `@forSome`, `@forAll`, path expressions). This means:

- **Phase 1 parser**: rdflib handles data files (facts, ontologies). Rule files need a minimal hand-written parser for the `=>`/`<=` syntax, variable binding (`?X`), and formula blocks `{ ... }`. This is ~40% of the full parser but the most critical part.
- **Phase 2 parser**: Full N3 grammar including triple terms `<< >>`, formula terms `(| |)`, BLOGIC surfaces, `is`/`has` sugar.

---

## Phase 1: Core Engine (MVP)

**Goal**: Run a non-trivial N3 rule set end-to-end. Input: N3 data file + N3 rule file. Output: deduced triples in N3 format.

### Module Structure

```
pyeye/
├── __init__.py          # public API: execute()
├── term.py              # Term hierarchy: NamedNode, Literal, Variable, Existential, Formula
├── parser.py            # Minimal rule parser: N3 rules {P} => {C}, variables, formulas
├── store.py             # Triple store with predicate-based indexing
├── engine.py            # Euler Abstract Machine: forward chaining + tabling
├── unify.py             # Structural unification + substitution
├── builtins.py          # Curated builtins (~40): math, string, time, list
├── output.py            # N3 serialization
├── entry.py             # execute() API: orchestration
└── cli.py               # CLI: pyeye --n3 data.n3 --query rules.n3
```

### 1. `term.py` — N3 Term Hierarchy

Dataclasses mirroring Eyeling's structure:

```python
@dataclass(frozen=True)
class NamedNode:
    value: str  # full IRI

@dataclass(frozen=True)
class Literal:
    value: str
    datatype: NamedNode | None = None
    language: str | None = None

@dataclass(frozen=True)
class Variable:
    name: str

@dataclass(frozen=True)
class Existential:
    name: str  # blank node / skolem

@dataclass(frozen=True)
class Formula:
    triples: list[Triple]  # nested formula { ... }
```

**Key design**: All terms are frozen/hashable so they can be keys in dicts and members of sets.

### 2. `parser.py` — Minimal Rule Parser

Scope: parse N3 rule syntax, not full N3 data (rdflib handles data).

```
rule       → formula '=>' formula
           | formula '<=' formula

formula    → '{' statement_list '}'
           | triple_pattern

statement_list → statement ('.' statement)*

statement  → subject verb object_list
subject    → path_item | '[' ']' | '(' list ')'
verb       → path_item | 'a'
object_list → object (';' predicate object)*
object     → path_item | '[' ']' | '(' list ')' | formula
path_item  → IRI | VARIABLE | '_:' NAME | Literal
```

Supports:
- `{P} => {C}` and `{C} <= {P}` rule syntax
- Variables `?name`
- Blank nodes `[]` and `_:name`
- Lists `(a b c)`
- Prefixed names `:foo`, `ex:bar`
- `@prefix`, `@base` directives
- `@forSome` and `@forAll` quantifiers
- `!` forward path, `^` reverse path (Phase 2: full path expressions)

Does **not** support (deferred to Phase 2):
- Triple terms `<< S P O >>`
- Formula terms `(| Functor Args |)`
- `is` / `has` sugar
- BLOGIC / negative surfaces
- Set syntax `($ ... $)`

### 3. `store.py` — Triple Store with Indexing

Eyeling uses a flat `Set[Triple]` with linear scan. For Phase 1, add a simple predicate index to avoid the O(n) match on every triple pattern:

```python
class TripleStore:
    _triples: set[Triple]
    _by_pred: dict[NamedNode, set[Triple]]   # predicate → matching triples

    def add(self, triple: Triple) -> bool:
        """Returns True if triple was new (not already present)."""

    def match(self, s, p, o) -> Iterator[Triple]:
        """Pattern match with None as wildcard. Uses _by_pred if p is bound."""
```

This is a single-dict index — trivial to implement, gives 10-100x speedup on realistic rule sets.

### 4. `unify.py` — Structural Unification

Given a triple pattern `(s, p, o)` with possible `Variable` slots and a ground triple from the store, compute a `Binding` (dict[str, Term]):

```python
def unify(pattern: Triple, candidate: Triple, binding: Binding) -> Binding | None:
    """Returns extended binding if pattern matches candidate, else None."""
```

Handles:
- NamedNode == NamedNode (IRI equality)
- Literal == Literal (value + datatype + language)
- Variable binds to any ground term (occurs check)
- Existential == Existential (name equality)
- Formula == Formula (recursive triple-wise equality)

### 5. `engine.py` — Euler Abstract Machine

The core algorithm, ported from Eyeling's `engine.js` (which is a cleaner version of EYE's Prolog `eam/1`):

```python
class Engine:
    store: TripleStore
    rules: list[Rule]         # Rule = (body_formula, head_formula, source)
    derived: int              # count of new derivations per pass
    step_count: int           # total inference steps

    def run(self, max_steps: int = -1) -> None:
        """Forward chain to fixpoint."""
        while True:
            self.derived = 0
            for rule in self.rules:
                self._apply_rule(rule)
            if self.derived == 0:
                break  # fixpoint reached
            if max_steps > 0 and self.step_count >= max_steps:
                break

    def _apply_rule(self, rule: Rule) -> None:
        """Match body patterns against store, derive head if new."""
        bindings = self._match_formula(rule.body, {})
        for binding in bindings:
            head_instance = self._instantiate(rule.head, binding)
            if self.store.add(head_instance):
                self.derived += 1
                if self._explain:
                    self._record_proof(head_instance, rule, binding)
```

**Formula matching** (`_match_formula`): recursively match a conjunction of triple patterns against the store, accumulating bindings. This is the heart of the engine — it's essentially a nested join over the triple store.

**Tabling (backward chaining)**: Deferred to Phase 2. Phase 1 is pure forward chaining, which handles the majority of practical N3 rule sets.

### 6. `builtins.py` — Curated Builtins (~40)

Each builtin is a callable that receives bound arguments and returns asserted triples or a value:

```python
class Builtin(Protocol):
    def evaluate(self, args: list[Term], engine: Engine) -> Term | list[Triple]: ...
```

Phase 1 registry:

| Namespace | Builtins |
|---|---|
| **math:** | `plus`, `minus`, `times`, `divide`, `equalTo`, `lessThan`, `greaterThan`, `integer` |
| **string:** | `concatenation`, `contains`, `length`, `startsWith`, `endsWith`, `equal`, `format` |
| **time:** | `now`, `year`, `month`, `day`, `in-seconds`, `format-date-time` |
| **list:** | `in` (member), `length`, `sort`, `append` |
| **log:** | `uri`, `content`, `outputString`, `skolem`, `equalTo`, `instantiation` |
| **type:** | `isLiteral`, `isNumeric`, `isDateTime`, `str`, `iri` |

Key builtins that need special engine access:
- `log:skolem` — generates fresh existential constants (needs engine's skolem counter)
- `log:outputString` — marks triples for output (needs engine's output buffer)
- `log:content` — returns all triples in a named graph

**Custom builtins**: Users can register additional builtins via `execute(builtins={...})`. This is the extension point for domain-specific predicates.

### 7. `output.py` — N3 Serialization

Convert derived triples back to N3 text:
- Prefix collection and abbreviation (`<http://...#foo>` → `:foo`)
- Literal formatting (datatype suffixes, language tags)
- Blank node serialization (`_:genid-1`)
- Sorted, deduplicated output

### 8. `entry.py` — Public API

```python
@dataclass
class Result:
    triples: str       # N3 output text
    explains: list     # proof trees (empty if explain=False)
    stats: dict        # steps, derived, time_ms

def execute(
    data_paths: list[str] | None = None,
    data_strings: list[str] | None = None,
    rule_paths: list[str] | None = None,
    rule_strings: list[str] | None = None,
    builtins: dict[str, Builtin] | None = None,
    explain: bool = False,
    max_steps: int = -1,
    limit_answers: int = -1,
    prefixes: dict[str, str] | None = None,
) -> Result:
```

### 9. `cli.py` — CLI

```
pyeye --n3 data.n3 --query rules.n3 [options]

Options:
  --n3 <uri>         Load N3 data file (repeatable)
  --query <uri>      Load N3 rule file (repeatable)
  --pass             Output deductive closure (default)
  --pass-all         Closure + rules
  --nope             No derivation (pass-through)
  --explain          Include proof explanations
  --tactic limited-answer N   Stop after N derivations
  --max-inferences N          Hard step cap
  --prefix p=url     Register prefix
  --quiet            Suppress stderr
  --statistics       Print stats to stderr
```

---

## Phase 2: Full Feature Parity

### 2a. DJITI Indexing

Deep Just-In-Time Indexing — the optimization EYE uses to avoid re-scanning rules. Transforms rules so that variable bindings propagate efficiently through long rule bodies. Port from `eye.pl` lines ~5622-5770.

### 2b. Full N3 Parser

Replace the Phase 1 minimal parser with the complete N3 grammar:
- Triple terms `<< S P O >>` (N3 reification)
- Formula terms `(| Functor Args |)`
- BLOGIC / negative surfaces `log:onNegativeSurface`
- `is` and `has` syntactic sugar
- `of` (property inversion shorthand)
- Set syntax `($ a b $)`
- Full path expressions (nested `!`/`^`)

### 2c. Remaining Builtins (~200 more)

| Namespace | Count | Notes |
|---|---|---|
| **e:** (log-rules) | ~60 | `e:calculate` (Prolog eval), `e:call`, `e:findall`, `e:exec`, `e:sha`, `e:random`, `e:csvTuple`, `e:becomes`, `e:transaction`, `e:closure` |
| **math:** | ~20 | Trig functions, `floor`, `ceiling`, `exponentiation`, `logarithm`, `avg`, `std`, `pcc`, `rms` |
| **string:** | ~10 | `matches` (regex), `replace`, `substring`, `scrape` |
| **list:** | ~15 | `select`, `remove`, `permutation`, `car`, `cdr` |
| **log:** | ~30 | `implies`, `isImpliedBy`, `conclusion`, `collectAllIn`, `includes`, `notIncludes`, `forAllIn`, `graph`, `semantics`, `shell`, `ask`, `uuid`, `n3String` |
| **crypto:** | 4 | `md5`, `sha`, `sha256`, `sha512` |
| **graph:** | 8 | `member`, `length`, `difference`, `intersection`, `union`, `statement` |
| **RIF (func:/pred:)** | ~70 | XPath/XQuery functions |
| **time:** | 4 | `localTime` (timezone-aware) |

The `e:derive` builtin (calls arbitrary Python callables) is the most powerful — it makes the engine extensible at runtime without recompilation.

### 2d. Proof Graph Output

Port EYE's proof tracing + Eyeling's `explain.js`:
- `prfstep` records (conclusion, premise, rule, chaining direction, source)
- Proof tree reconstruction
- Output formats: N3 (default), DOT graph, HTML (Phase 2)

### 2e. Backward Chaining / Tabling

Goal-directed reasoning: given a query triple, find matching rule heads and recursively prove their bodies. With caching (tabling) to prevent re-computation.

### 2f. Entailment Modes

EYE's `--entail` / `--not-entail` flags. RDFS entailment as a first step, potentially OWL RL.

### 2g. TriG / Named Graphs

Full TriG parsing and quad store support. `graph:member`, `graph:difference`, etc.

### 2h. Performance

- RETE-like discrimination network for formula matching
- Parallel rule application (multiprocessing)
- Incremental reasoning (add triples without restarting)

---

## Dependency Strategy

### Phase 1
- **rdflib** — N3 data parsing, IRI/literal handling, prefix management
- **Python 3.11+** — dataclasses, type hints, `functools.singledispatch`

### Phase 2
- **lark** or **textx** — full N3 DCG grammar (if migrating away from rdflib for rule parsing)
- **networkx** — proof graph visualization (DOT output)
- **no Prolog dependency** — fully standalone Python

---

## Test Strategy

### Unit Tests
- Term equality / hashing
- Unification cases (success, failure, occurs check)
- Store indexing (add, match, duplicate rejection)
- Individual builtin evaluation
- Parser round-trips (parse → serialize → parse)

### Integration Tests
- Simple transitivity rule: `{:A :p :B} => {:A :r :B}` + data → expected output
- Multi-rule chain: 5 rules deriving intermediate facts
- Skolem generation: fresh existential for each `log:skolem` call
- `limited-answer` tactic: stops after N derivations
- Cycle detection: rule that would derive itself is correctly skipped

### Compatibility Tests
- Run the same N3 files through EYE (Prolog), Eyeling (JS), and pyeye (Python) — compare outputs
- Use EYE's test suite (`test/` directory in EYE repo)
- Use Eyeling's test fixtures (`test/fixtures/`)

---

## Risks & Mitigations

| Risk | Mitigation |
|---|---|
| **rdflib can't parse N3 rules** | Write minimal rule parser for Phase 1 (only `=>`/`<=`/`{}`/variables syntax, not full N3). This is ~400 lines vs. ~800 for the full grammar. |
| **Formula matching is exponential** | The join over formula body patterns can explode for long rules. Mitigation: DJITI-style variable binding propagation (Phase 2a), or cap rule body length in Phase 1. |
| **Builtins are a long tail** | Phase 1 has ~40 curated builtins covering 80% of practical use cases. The remaining 200 are added incrementally. |
| **Performance vs. EYE** | EYE benefits from 20+ years of SWI-Prolog optimization. Phase 1 target: correctness first, speed second. The predicate index in `store.py` prevents the worst O(n) pathologies. |
| **N3 spec ambiguity** | When in doubt, match EYE's behavior (it's the reference implementation). Keep a compatibility test suite. |

---

## Migration Path to LEA Integration

Once the Python reasoner exists, it plugs into the voice assistant pipeline as the **policy guardrail** (see `brainstorm.md` §17-18):

```
User voice → STT → NLU → entity linking → KG query
                                        ↓
                              EYE Python: check N3 rules
                                        ↓
                              Allowed? → Yes: speak answer
                                       → No:  speak denial with proof trace
```

The Python implementation is critical here — `eye` (Prolog) requires SWI-Prolog as a system dependency, and `eyeling` (JS) requires Node. A pure-Python reasoner has no external runtime requirements and can be imported as a library by any LEA skill.
