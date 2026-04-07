# pyeye Conformance Report

**Date:** 2026-04-06
**pyeye location:** `/mnt/homelab/Workspace/pyeye/`
**eyeling test suite:** `/mnt/homelab/Workspace/external repos/eyeling/`
**eye.pl reasoning examples:** `/mnt/homelab/Workspace/external repos/eye/reasoning/`

---

## Executive Summary

pyeye **passes 0 of 175 eyeling example tests** (0%). All 175 examples either crash with a parse/runtime error (141 cases), produce wrong output (32 cases), or time out (2 cases).

The failures are dominated by a small number of structural bugs — most critically a **DJITI (pattern reordering) bug that breaks all builtin evaluation when variables appear in builtin arguments** — combined with a **backward-rule tokenizer bug** and missing support for several common N3 syntactic constructs.

---

## Section 1 — Eyeling Test Suite Results (175 examples)

### 1.1 Overall Counts

| Status | Count | Percentage |
|--------|-------|-----------|
| PASS | 0 | 0.0% |
| FAIL (wrong content) | 32 | 18.3% |
| ERROR (crash/parse) | 141 | 80.6% |
| TIMEOUT (>15 s) | 2 | 1.1% |
| **Total** | **175** | |

**Note on "PASS_EXTRA_PREFIXES":** Two tests (`alignment-demo.n3`, `minimal-skos-alignment.n3`) produce semantically correct triples but include extra unused `@prefix` declarations. They would pass if prefix emission were filtered to only used prefixes.

---

### 1.2 Error Category Breakdown (141 ERROR cases)

| Category | Count | Root Cause |
|----------|-------|-----------|
| Backward rule `<=` tokenizer bug | 40 | See Bug #1 |
| `TypeError: unhashable type 'list'` | 50 | See Bug #2 |
| Prefixed-name datatype not supported (`xsd:date`) | 15 | See Bug #3 |
| `false` literal not allowed in rule body | 7 | See Bug #4 |
| Unexpected DOT (rule-inside-formula as subject) | 16 | See Bug #5 |
| Unexpected SC (complex semicolon usage) | 8 | See Bug #6 |
| Nested `=>` / unexpected RBR | 3 | See Bug #5 (variant) |
| Other | 2 | See Bug #7, #8 |

---

### 1.3 FAIL (wrong output) — 32 cases

These tests ran without crashing but produced wrong answers.

| Test | Expected | Actual | Root Cause |
|------|----------|--------|-----------|
| `witch.n3` | `:DUCK a :BURNS .` (×6) | `:DUCK rdf:type :BURNS .` (×6) | Serialization: no `a` shorthand |
| `schema-foaf-mapping.n3` | `ex:alice a foaf:Person .` | `ex:alice rdf:type foaf:Person .` | Same |
| `crypto-builtins-tests.n3` | `:ok a :Pass .` (×4) | `rdf:type` expansion | Same |
| `family-cousins.n3` | `:Adam :generation 0 .` (×13) | Only `:Adam :generation "0"^^xsd:integer .` | Bug #9 (DJITI reordering) — math:sum never fires |
| `similar.n3` | `:test :is true .` | All similar pairs (×6), no `:test` | Bug #9 — backward rule not applied, wrong closure |
| `zebra.n3` | `:german :eats :fish .` | empty | Bug #9 — constraint builtins fail |
| `reordering.n3` | `:test :is true .` | empty | Bug #9 |
| `faltings-genus2-finiteness.n3` | 3 triples | empty | Bug #9 |
| `good-cobbler.n3` | 3 triples | empty | Bug #9 |
| `light-eaters.n3` | 13 triples | 1 triple | Bug #9 |
| `lldm.n3` | 38 triples | empty | Bug #9 (math builtins) |
| `spectral-week.n3` | 14 triples | empty | Bug #9 (math builtins) |
| `list-iterate.n3` | 5 triples | empty | Bug #10 (list:iterate stub) |
| `list-map.n3` | 4 triples | empty | Bug #10 (list:map) |
| `list-builtins-tests.n3` | 15 triples | 4 triples | Bugs #9, #10 |
| `log-uri.n3` | 2 triples | empty | Bug #11 (log:uri bidirectionality) |
| `log-pan-rt-soe.n3` | 7 triples | 1 triple | Bug #11 (log builtins) |
| `reaching-out.n3` | 8 triples | 1 triple | Bug #11 (log:semantics) |
| `log-skolem.n3` | `:Result :skolem genid:...` | `:Result :skolem _:sk-1 .` | Bug #12 (Skolem IRI format) |
| `existential-rule.n3` | `:Plato :is _:sk_1 .` | `:Plato : _:B .` | Bug #12 |
| `jsonterm.n3` | `ex:test ex:is true .` | empty | JSON-term builtin not supported |
| `jsonterm-advanced.n3` | 6 triples | empty | Same |
| `deep-taxonomy-10..100000.n3` | LLM-prose expected, not N3 | N3 triples | Expected output is explanation text, not comparable N3 |
| `takeuchi.n3` | 1004 triples | empty | Bug #9 (recursive rules with math) |
| `alignment-demo.n3` | N3 (correct) | +`@prefix list:`, `@prefix log:` | Minor: unused prefix emission |
| `minimal-skos-alignment.n3` | N3 (correct) | +`@prefix skos:` | Same |
| `collection.n3` | empty expected | extra blank prefix | Spurious prefix emitted |

---

### 1.4 TIMEOUT

- `monkey.n3` — exceeded 15 s (recursive rule causing infinite loop)
- `topaz-markov-mill.n3` — exceeded 15 s (large state space)

---

## Section 2 — eye.pl Reasoning Examples (15 representative)

| Example | Status | Notes |
|---------|--------|-------|
| `backward/backward.n3` (basic backward) | RAN (wrong) | Runs but produces no derived triples; Bug #1 prevents `<=` rules from parsing in most cases |
| `bmi/bmi_instances.n3 + bmi_rules.n3` | ERROR | Bug #3: `xsd:dateTime` in typed literal |
| `blogic/input/beetle12.n3` (BLOGIC negation) | ERROR | Bug #5: rule-inside-formula |
| `blogic/input/fibonacci.n3` | ERROR | Bug #5 |
| `4number/4number.n3` (list math) | FAIL | Bug #9: `(a b c) math:sum` never fires |
| `4color/4color_rules.n3` (graph coloring) | ERROR | Bug #5 |
| `bnode-scope/test1.n3` | ERROR | Bug #2: unhashable list |
| `3outof5/sample.n3` (list 3-of-5) | ERROR | Bug #5 |
| `bi/abc.n3 + biA.n3` | ERROR | Bug #5 |
| `beam-bending-safety` | ERROR | Bug #1: `<=` with `>` later in file |
| `ackermann/ackermann.n3` | FAIL | missing all 12 answers (recursive backward) |
| `braking-safety-worlds` | ERROR | Bug #1 |
| `access-control-policy` | ERROR | Bug #2 |
| `allen/allen.n3` (interval calc) | ERROR | Bug #2 |

**Pass rate: 0/15 (0%)**

---

## Section 3 — Confirmed Semantic Bugs (Wrong Answers)

### Bug #9 — DJITI pattern reordering breaks builtin evaluation [CRITICAL]

**Root cause:** `_djiti_order()` in `engine.py:304` sorts body patterns by store-match count. Builtins never appear in the triple store, so they get count=0 and are sorted to the FRONT. But if a builtin requires a variable (e.g., `?X math:greaterThan 3`) that is only bound by a preceding store-match pattern (`:a :v ?X`), moving the builtin first causes it to execute with `?X` unbound. The `_unground()` guard then returns `None`, silently discarding the binding.

**Evidence:**
```
# Rule: { :a :v ?X . ?X math:greaterThan 3 . } => { :test :t true . }.
# Data: :a :v 5 .
# DJITI reorders to: [ ?X math:greaterThan 3, :a :v ?X ]
# ?X is unbound at evaluation of math:greaterThan -> returns None -> no derivation
```

**Affected:** `family-cousins.n3`, `similar.n3`, `zebra.n3`, `reordering.n3`, `faltings-genus2-finiteness.n3`, `good-cobbler.n3`, `light-eaters.n3`, `lldm.n3`, `spectral-week.n3`, `takeuchi.n3`, plus all 40 `<=` tokenizer cases that do parse (some backward rules use the same builtins).

**Impact:** Any rule where builtins (`math:*`, `log:*`, `list:*`) appear after the data pattern that binds their inputs produces zero derivations.

**Fix required:** DJITI must not move builtin patterns before the patterns that bind their input variables. Builtins should be sorted _after_ the patterns that supply their bound variables, or DJITI should be aware of variable dependency.

---

### Bug #12 — Skolem/existential IRI format wrong

**Root cause:** pyeye generates blank-node-style existentials (`_:sk-1`, `_:B`) for existentially quantified variables, but eye.pl generates deterministic Skolem IRIs with a stable namespace (`genid:32007e38-...`).

**Evidence (`log-skolem.n3`):**
```diff
- :Result :skolem genid:32007e38-bd28-5f18-4712-ae1df708a5d4 .
+ :Result :skolem _:sk-1 .
```

**Evidence (`existential-rule.n3`):**
```diff
- :Plato :is _:sk_1 .
+ :Plato : _:B .
```
Also: the predicate is emitted as `:` (empty local name) instead of `:is` — a second serialization defect.

---

### Bug — `rdf:type` not serialised as `a`

**Root cause:** `N3Writer` in `output.py` emits the full IRI `<http://www.w3.org/1999/02/22-rdf-syntax-ns#type>` instead of the `a` shorthand.

**Affected:** `witch.n3`, `schema-foaf-mapping.n3`, `crypto-builtins-tests.n3`. All correct semantically but fail exact string comparison.

---

## Section 4 — Missing Features (Parser Failures)

### Bug #1 — Backward rule tokenizer bug [CRITICAL — 40 files]

**Root cause:** The tokenizer defines `IRI` as `<[^>]+>` (matches `<` then any non-`>` chars including newlines). When `<=` appears in a file that also has a `>` character anywhere later in the text, the regex greedily matches from `<` in `<=` all the way to the next `>`, creating a multi-line "IRI" token containing `{ body }. => {`.

**Condition:** Fires when `<=` appears AND there is a `>` character somewhere after it in the same file (common in any file that also has `=>` forward rules or `<IRI>` literals later).

**Fix required:** Move `IMPB` (`<=`) to appear before `IRI` in the `specs` list in `tokenize()`, **or** change the IRI regex to `<(?!-)(?:[^>])*>` (not matching `<-` or `<=`).

**Files failing:** 40 eyeling examples + many eye.pl examples.

---

### Bug #2 — `TypeError: unhashable type: 'list'` [CRITICAL — 50 files]

**Root cause:** Somewhere in the store or unification code, a Python `list` object is used as a dictionary key or set member. Most likely triggered by RDF list nodes (`rdf:first`/`rdf:rest`) being stored in a hashable structure.

**Files failing:** 50 eyeling examples including `socrates.n3`, `cobalt-kepler-kitchen.n3`, `dog.n3`, `e-computable-real.n3`, `euler-identity.n3`, and many more.

---

### Bug #3 — Prefixed-name datatypes not supported in typed literals [15 files]

**Root cause:** The parser's `_item()` method handles `"value"^^<IRI>` but not `"value"^^prefix:local`. After `^^`, only a full `<IRI>` token is accepted; a prefixed name (e.g., `xsd:date`, `xsd:integer`, `xsd:dateTime`) raises `ParseError: Expected IRI, got KW`.

**Evidence:**
```n3
:x :birth "1990-01-01"^^xsd:date.  # ParseError
:x :birth "1990-01-01"^^<http://www.w3.org/2001/XMLSchema#date>.  # Works
```

**Files failing:** `allen-interval-calculus.n3`, `annotation.n3`, `context-association.n3`, `decimal-*.n3`, `delfour.n3`, `ershov-mixed-computation.n3`, `godel-incompleteness.n3`, `ill-formed-literals.n3`, `kronecker.n3`, `time.n3`, `traffic-skos-aggregate.n3`, `void.n3`, `wind-turbine.n3` + eye.pl bmi examples.

---

### Bug #4 — Boolean `false` literal in rule body raises ParseError [7 files]

**Root cause:** The parser's `_do_formula_top()` expects `LBR` (`{`) after `=>` or `<=`, but the literal `false` is tokenized as a separate `FALSE` token and the parser raises `ParseError: Expected LBR, got FALSE`.

**Affected pattern:**
```n3
{ :a :b :c } => false.   # fails: "Expected LBR, got FALSE"
```

**Files failing:** `bmi.n3`, `french-cities.n3`, `fuse.n3`, `liar.n3`, `parcellocker.n3`, `pn-junction-tunneling.n3`, `resto.n3`.

---

### Bug #5 — Rule-inside-formula (formula containing `=>`) not parsed [16 files + 4 eye.pl]

**Root cause:** The parser does not allow `{ { body } => { head }. }` where a rule appears inside a formula used as a triple subject. When parsing the formula, after parsing the inner rule's head `}`, it encounters the final `.` and raises `ParseError: Unexpected DOT`.

**Affected pattern:**
```n3
{ { :a :b :c . } => { :d :e :f . }. } a :PASS.   # fails
```

**Files failing:** `dining-philosophers.n3`, `doctor-advice-work-conflict.n3`, `easter.n3`, `log-conclusion.n3`, `log-not-includes.n3`, `odrl-dpv-*`, `paraconsistent-animals.n3`, `quoted-head-unquote*.n3`, `turing.n3`, `two-two-four.n3`, etc.

---

### Bug #6 — Unexpected semicolons in certain positions [8 files]

**Root cause:** Semicolon-based predicate lists fail in specific syntactic positions (possibly inside formula bodies with complex nesting or adjacent to certain patterns).

**Files failing:** `math-builtins-tests.n3`, `sudoku.n3`, `transcendental-*.n3`, `transistor-switch.n3`.

---

### Bug #7 — `=` (owl:sameAs) not supported in subject position [1 file]

**Files failing:** `equals.n3` — `ParseError: Unexpected EQ '=' at <string>:11`.

---

### Bug #8 — String builtin formatting error [1 file]

**Files failing:** `string-builtins-tests.n3` — `TypeError: not all arguments converted during string formatting`. A `%`-based formatting call in a string builtin receives more arguments than format slots.

---

### Bug #10 — `list:iterate` is a stub; `list:map` functional but may fail due to Bug #9

**Root cause:** `list_iterate` returns `[]` unconditionally (stub):
```python
def list_iterate(args, engine) -> list[Triple] | None:
    if _unground(args): return None
    return []   # ← stub
```
`list:map` has an implementation but may fail due to Bug #9 (DJITI) when the list variable is bound by a prior pattern.

**Files failing:** `list-iterate.n3`, `list-map.n3`, and 11/15 `list-builtins-tests.n3` sub-tests.

---

### Bug #11 — Several `log:*` builtins use `_unground()` incorrectly for output variables

**Root cause:** Builtins like `log:uri` call `_unground(args)` which returns `True` if ANY argument is a variable — including the OUTPUT variable that the builtin is supposed to bind. This causes the builtin to return `None` even when all input args are ground.

**Example:**
```python
def log_uri(args, engine) -> Term | None:
    if _unground(args): return None   # args[1] is Variable -> returns None!
    ...
```

The correct check would be: only verify that INPUT arguments are ground, not the output.

**Affected builtins:** `log:uri`, `list:length`, and any other builtin that binds a result into a variable object.

**Files failing:** `log-uri.n3`, `log-pan-rt-soe.n3`, `reaching-out.n3`.

---

### Bug — Integer literals parsed incorrectly when immediately followed by `.`

**Root cause:** The NUM regex `[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?` matches `0.` (integer with trailing dot) as a single token, treating it as a floating-point literal. In N3/Turtle, the trailing `.` is the statement terminator, not a decimal point.

When a triple ends with an integer value touching the period (`:a :gen 0.` vs `:a :gen 0 .`), the `0.` is tokenized as a double instead of `0` + `.`.

**Consequence:** Integers in some positions get datatype `xsd:double` (value `"0."`) instead of `xsd:integer`.

---

## Section 5 — Confirmed Correct Behaviour

The following features work as expected in isolation:

- Basic forward chaining (single-step, no builtins)
- Prefix declarations (`@prefix`, `PREFIX`)
- RDF list construction `(a b c)` — stored as rdf:first/rdf:rest chains
- `@forSome` / `@forAll` quantifiers (basic)
- `math:greaterThan` / `math:lessThan` when both args appear **directly** in rule body (not after a variable-binding pattern — Bug #9 exception)
- `log:equalTo` / `log:notEqualTo`
- Simple blank nodes `[]` and named blank nodes `_:foo`
- RDFS entailment (`--entail` flag)
- OWL 2 RL entailment (`--entail-owl` flag)
- `log:onNegativeSurface` basic negation (parsed and evaluated)
- Backward chaining `<=` when no `>` character follows later in the file (Bug #1 exception)

---

## Section 6 — Prioritised Fix List

| Priority | Bug | Impact | Description |
|----------|-----|--------|-------------|
| P0 | Bug #9 (DJITI) | 100+ tests | Builtins must not be sorted before their dependency patterns |
| P0 | Bug #1 (tokenizer `<=`) | 40 tests | IRI regex must not match `<=` |
| P0 | Bug #2 (unhashable list) | 50 tests | List terms must be hashable or stored differently |
| P1 | Bug #3 (prefixed datatypes) | 15 tests | Parse `^^prefix:local` after `^^` |
| P1 | Bug #5 (rule-in-formula) | 16 tests | Allow `{ {body} => {head}. }` as triple subject |
| P1 | Bug #4 (`false` in rule) | 7 tests | Accept `false` as rule consequent |
| P2 | `a`/`rdf:type` serialization | 3 tests | Emit `a` shorthand in N3Writer |
| P2 | Bug #10 (`list:iterate` stub) | 3 tests | Implement list:iterate |
| P2 | Bug #11 (output var `_unground`) | 3 tests | Fix _unground check in functional builtins |
| P2 | Bug #12 (Skolem IRI format) | 2 tests | Use stable genid: namespace |
| P3 | Bug #6 (semicolons) | 8 tests | Complex semicolon handling in formulas |
| P3 | Bug #8 (string formatting) | 1 test | Fix % formatting in string builtins |
| P3 | Integer literal + `.` | side effect | Change NUM regex to not greedily consume trailing dot |

---

## Appendix — Test Methodology

Tests were run using the Python API:
```python
from pyeye import execute
r = execute(rule_strings=[n3_text])
```

Each test had a 15-second timeout. Outputs were compared after:
1. Stripping trailing whitespace from each line
2. Removing blank lines
3. Sorting lines (N3 triples are order-independent)

`@prefix` lines were compared separately from content triples to distinguish serialization issues from semantic errors. A test is reported as PASS only when the sorted non-prefix content lines match exactly.

Eye.pl expected outputs use a proof-trace format (not plain triples), so they were compared where possible and otherwise reported as `RAN` with output size.
