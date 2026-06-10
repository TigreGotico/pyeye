# pyeye Troubleshooting Guide

Solutions to 25+ common problems. Each section covers symptoms, root cause, and fix.

---

## 1. Rule fires in isolation but produces nothing in execute()

**Symptom:** Testing a builtin standalone works, but the rule produces no triples.

**Root cause:** The builtin's unground check includes the output Variable appended by the engine.

```python
# BUG: _unground(args) checks ALL args, including the output Variable at args[-1]
def my_fn(args, engine):
    if _unground(args): return None  # always None in rule context!
    return Literal(compute(args[0]))
```

**Fix:** Check only input args:
```python
def my_fn(args, engine):
    if _unground(args[:1]): return None  # only check inputs
    return Literal(compute(args[0]))
```

---

## 2. Math computation produces no output

**Symptom:** `{ ?A :x ?V . ?V math:times 2 ?R }` — no derived triples.

**Root cause:** `math:times` is not valid. Binary math uses **list syntax**.

**Fix:**
```n3
# WRONG
{ ?V math:times 2 ?R }

# RIGHT — input args as a list, output var at end
{ (?V 2) math:product ?R }
```

All binary math operations use list syntax: `(?A ?B) math:sum ?C`, `math:difference`,
`math:product`, `math:quotient`, `math:remainder`.

---

## 3. string:concatenation produces nothing

**Symptom:** `{ (?A ?B) string:concatenation ?R }` works standalone but not in rules.

**Root cause:** The engine appends the output Variable making args = `[?A, ?B, Variable("R")]`.
`_unground(args)` returns True because `Variable("R")` is unbound.

**Fix:** The built-in `string:concatenation` handles this; for a **custom** concatenation-style builtin, check only the input slots (`args[:-1]`):

```python
def my_concat(args, engine):
    inputs = args[:-1] if len(args) >= 2 and isinstance(args[-1], Variable) else args
    if any(isinstance(a, Variable) for a in inputs): return None
    return Literal("".join(str(a.value) for a in inputs))
```

---

## 4. log:onNegativeSurface has no effect

**Symptom:** Rule with negation fires even when the negated formula IS derivable,
or never fires even when it is NOT derivable.

**Root cause A:** Blank node missing.

```n3
# WRONG — blank node is required
{ log:onNegativeSurface { ?S :hasX ?V } . ?S :default ?D } => { ?S :eff ?D } .

# RIGHT
{ _:neg log:onNegativeSurface { ?S :hasX ?V } . ?S :default ?D } => { ?S :eff ?D } .
```

**Root cause B:** Multiple negations share the same blank node.

```n3
# WRONG — _:neg used twice
{ _:neg log:onNegativeSurface { ?S :hasA ?V } .
  _:neg log:onNegativeSurface { ?S :hasB ?V } } => { ... } .

# RIGHT — distinct blank nodes
{ _:n1 log:onNegativeSurface { ?S :hasA ?V } .
  _:n2 log:onNegativeSurface { ?S :hasB ?V } } => { ... } .
```

---

## 5. log:uuid causes infinite loop / ReasoningTimeoutError

**Symptom:** `execute()` hangs or throws `ReasoningTimeoutError` when a rule uses `log:uuid`.

**Root cause:** `log:uuid` is non-deterministic — each call generates a fresh UUID,
so the derived triples are always new and fixpoint is never reached.

**Fix:** Never use `log:uuid` in forward-chaining rules. Generate UUIDs in Python
and inject as facts before calling `execute()`:

```python
import uuid
engine.add_triple(Triple(req, pred_eventId, Literal(str(uuid.uuid4()))))
```

Use `log:skolem` if you need **deterministic** blank nodes:
```n3
{ ?P :at ?C . (?P ?C) log:skolem ?Node } => { ?Node a :Employment } .
```

---

## 6. Infinite forward loop / ReasoningTimeoutError

**Symptom:** Rules produce new triples indefinitely; engine throws `ReasoningTimeoutError`
after 30 seconds (default).

**Diagnosis:**
- Check if any rule's head can match its own body (self-triggering rule)
- Check if two rules mutually trigger each other with growing data

**Fix options:**
1. Restructure rules to reach fixpoint (use different predicates for input/output)
2. Set a shorter timeout: `execute(..., timeout_seconds=5.0)`
3. Set a step limit: `execute(..., max_steps=10_000)`
4. Catch the exception: `except ReasoningTimeoutError: ...`

---

## 7. Backward chaining returns no results

**Symptom:** `result.query_answers` is empty even though forward chaining produces the relevant triples.

**Root cause A:** The query variable name doesn't match the binding keys. Bindings
are keyed by the variable name from the `query=` triple (without the `?`).

```python
query = Triple(Variable("Who"), pred, obj)
for b in result.query_answers:
    print(b["Who"])
```

**Root cause B:** Rule is forward-only (`=>`) but query expects backward (`<=`).
For BC queries, add `<=` backward rules or use `log:table` for tabled predicates.

**Root cause C:** Missing `log:table` on a recursive predicate causing infinite recursion.

```n3
[] log:table :reachable .
{ ?X :reachable ?Y } <= { ?X :link ?Y } .
{ ?X :reachable ?Y } <= { ?X :reachable ?Z . ?Z :reachable ?Y } .
```

---

## 8. list:in / list:select returns nothing

**Symptom:** `{ ?Item list:in :myList }` produces no results.

**Root cause:** `list:in` is a **filter**, not a generator. Both `?Item` and `:myList`
must be bound to specific values. You cannot use it to enumerate list elements.

```n3
# WRONG — tries to enumerate, fails
{ ?Item list:in :myList } => { ?Item :approved true } .

# RIGHT — check that a bound variable is in the list
{ ?Item :category ?Cat . ?Cat list:in :allowedCats } => { ?Item :approved true } .
```

For `list:select` (1-based index): both list and index must be bound:
```n3
{ (:alice :bob :carol) list:select 1 ?First }  # ?First = :alice
```

---

## 9. entail=True returns empty output

**Symptom:** `execute(data_strings=[data], entail=True)` returns an empty or very short result.

**Root cause:** `entail=True` applies the RDFS rules *before* user rules and puts the
entailed triples in the store, where your rules can match them — but they are not part
of the default (rule-derived only) output. To see them, pass `pass_mode=True`.

```python
# Output: only triples derived by YOUR rules (RDFS-entailed triples stay in the store)
result = execute(data_strings=[data], rule_strings=[rules], entail=True)

# Output: original facts + RDFS-entailed + rule-derived triples
result = execute(data_strings=[data], rule_strings=[rules], entail=True, pass_mode=True)
```

---

## 10. N3Writer constructor error

**Symptom:** `TypeError: N3Writer.__init__() got an unexpected keyword argument 'initial_size'`

**Root cause:** `N3Writer` only accepts an optional `prefixes` dict.

**Fix:**
```python
# WRONG
writer = N3Writer(store, initial_size=10)

# RIGHT
writer = N3Writer()
print(writer.write_triples(engine.derived_triples))
```

---

## 11. IRI substring matching fails in output parsing

**Symptom:** Parsing `result.triples` for a specific subject produces no matches.

**Root cause:** The N3 output uses **abbreviated** IRIs (`rbac:alice`) not full
URIs (`http://example.org/rbac#alice`).

**Fix:** Match the abbreviated form or both forms:

```python
# WRONG — checks for full IRI that isn't in abbreviated output
if "http://example.org/rbac#alice" in line: ...

# RIGHT — check abbreviated
if "rbac:alice " in line: ...

# OR — check both
if "rbac:alice " in line or "rbac#alice>" in line: ...
```

---

## 12. Transitive rules not closing over all ancestors

**Symptom:** `?A :ancestor ?C` is derived for one hop but not two.

**Root cause:** Only one transitivity rule is present. You need both direct
and transitive forms, or the rule needs to reference itself:

```n3
# Direct parent → ancestor
{ ?X :parent ?Y } => { ?X :ancestor ?Y } .

# Chain: X's ancestor's ancestor is X's ancestor
{ ?X :ancestor ?Y . ?Y :ancestor ?Z } => { ?X :ancestor ?Z } .
```

Without the second rule, the engine only fires once per chain link.

---

## 13. Custom builtin receives wrong number of args

**Symptom:** `IndexError` inside a custom builtin.

**Root cause:** The engine always appends the **output variable** as the last
element of `args`, even for 1-input builtins. A builtin expecting 1 arg gets 2.

**Fix:** Use `args[0]` for the input, ignore `args[-1]` (it's the output slot):

```python
def my_fn(args, engine):
    if len(args) < 1 or isinstance(args[0], Variable): return None
    val = args[0].value  # safe
    return Literal(result)
```

---

## 14. Rule with math comparison and computation together

**Symptom:** `{ ?V math:greaterThan 0 . (?V 2) math:product ?R }` — no output.

**Root cause:** Usually fine; if no output, check that `?V` is a **numeric** literal.
String literals like `"5"` without a numeric datatype may not compare correctly.

**Fix:** Ensure numeric data has an XSD datatype:

```n3
:x :score "95"^^xsd:integer .
# NOT
:x :score "95" .  # plain string, math comparisons may fail
```

---

## 15. time:now produces identical timestamps in a loop

**Symptom:** All events get the same timestamp when processed in a loop.

**Root cause:** `time:now` is evaluated once per rule firing. In forward chaining,
all events matching the same rule may get the same timestamp if processed in
the same fixpoint step.

**Fix:** Use Python's `datetime.now()` to generate timestamps before injecting:

```python
import datetime
ts = datetime.datetime.now().isoformat(timespec="seconds")
engine.add_triple(Triple(event_node, pred_timestamp, Literal(ts)))
```

---

## 16. log:skolem creates different nodes each run

**Symptom:** Expected `log:skolem` to be deterministic but blank node names differ.

**Root cause:** `log:skolem` determinism is based on the **values** of its input args.
If any input is itself a blank node, that blank node's internal name may vary.

**Fix:** Use only named nodes and literals as `log:skolem` inputs:

```n3
# BAD — blank node input makes skolem non-deterministic
{ ?BNode :value ?V . (?BNode ?V) log:skolem ?ID }

# GOOD — only named nodes and literals
{ ?P :at ?C . (?P ?C) log:skolem ?ID }
```

---

## 17. ReasoningTimeoutError in unit tests

**Symptom:** Tests pass locally but fail in CI with `ReasoningTimeoutError`.

**Root cause:** CI machines may be slower, causing the 30-second default to be hit.

**Fix:** Set a higher timeout for tests that are known to be complex, or lower
timeout for tests that should be fast:

```python
result = execute(..., timeout_seconds=120.0)  # complex ontology test
result = execute(..., timeout_seconds=5.0)    # should be fast; fail fast if not
```

---

## 18. Aggregation produces no output (log:collectAllIn)

**Symptom:** `log:collectAllIn` triple is in the rule but nothing is derived.

**Root cause A:** Wrong calling convention. The subject is a three-element list
`(?Template { pattern } ?OutputList)`; the object is the scope.

**Root cause B:** The scope (the object) is a variable that is also bound elsewhere
in the rule. The scope must be a **fresh** variable used nowhere else; grouping
comes from variables the inner pattern shares with the outer body.

```n3
# WRONG — scope ?G is bound by the first body pattern
{ ?G a :Group .
  (?V { ?X :group ?G . ?X :value ?V } ?L) log:collectAllIn ?G .
  ?L list:length ?N } => { ?G :count ?N } .

# RIGHT — fresh ?Scope variable
{ ?G a :Group .
  (?V { ?X :group ?G . ?X :value ?V } ?L) log:collectAllIn ?Scope .
  ?L list:length ?N } => { ?G :count ?N } .
```

---

## 19. OWL entailment not working as expected

**Symptom:** `entail_owl=True` but `owl:equivalentClass` not producing type propagation.

**Root cause:** `entail_owl=True` implements **OWL 2 RL** (rule-based subset), not full
OWL DL. Not all OWL axioms are supported.

Supported: `owl:inverseOf`, `owl:SymmetricProperty`, `owl:TransitiveProperty`,
`owl:sameAs`, `owl:equivalentClass` (basic), `owl:FunctionalProperty`.

Not supported: complex class expressions, cardinality restrictions, nominals.

---

## 20. Duplicate results in backward chaining

**Symptom:** `result.query_answers` contains the same binding multiple times.

**Root cause:** Multiple proof paths derive the same answer (e.g., via role hierarchy
both directly and transitively). This is correct behavior — the engine found multiple
proofs.

**Fix:** Deduplicate in application code:

```python
seen = set()
for b in result.query_answers:
    val = list(b.values())[0].value
    if val not in seen:
        seen.add(val)
        print(val)
```

---

## 21. log:dtlit does not create correctly typed literal

**Symptom:** `log:dtlit` creates `xsd:string` or `xsd:dateTime` instead of the
intended type.

**Root cause:** `log:dtlit` without a datatype argument defaults to `xsd:dateTime`.
To specify a type, pass the type IRI as a second argument in a list:

```n3
# Creates xsd:dateTime (default, single arg)
{ ?V log:dtlit ?Typed }

# Creates integer typed literal (specify type)
{ (?V "http://www.w3.org/2001/XMLSchema#integer") log:dtlit ?Typed }
```

---

## 22. Parse error with regex in string:scrape

**Symptom:** `ParseError: Unexpected RBR '}'` when using `string:scrape` with a
pattern containing `#` or `}`.

**Root cause:** The N3 parser treats `#` as a comment start and `}` as closing a
formula. Inside string literals these need proper escaping.

**Fix:** Avoid regex patterns with `#`, `}`, `{` in N3 strings. Use `log:localName`
for IRI fragment extraction instead of a regex, or pre-process the data in Python.

---

## 23. Missing facts for some subjects (list not exhausted)

**Symptom:** Some subjects have properties derived but others don't, even though
the data looks symmetric.

**Root cause:** A rule's body has multiple conditions and one condition only matches
certain subjects. Check each triple pattern independently.

**Diagnosis:** Use `explain=True` to trace which rules fired for which bindings:
```python
result = execute(..., explain=True)
print(result.proof_n3)
```

---

## 24. Engine.store.match() returns nothing

**Symptom:** `engine.store.match(predicate=p)` returns an empty iterator after `run()`.

**Root cause:** The store contains **all** triples (input + derived). If you're
looking for derived-only triples, check `engine.derived_triples` instead.

```python
# All triples (input + derived)
engine.store.match(predicate=pred)

# Only derived triples
[t for t in engine.derived_triples if t.predicate == pred]
```

---

## 25. Custom builtin registered but never called

**Symptom:** Rule uses the custom predicate but builtin function is never invoked.

**Root cause A:** The IRI in `builtins={}` doesn't exactly match the IRI in the N3 prefix declaration.

```python
# WRONG — prefix expands to different IRI
builtins={"http://example.org/fn#myFn": fn}
# But N3 uses @prefix fn: <http://example.org/func#>
# → actually "http://example.org/func#myFn"

# FIX — match exactly
builtins={"http://example.org/func#myFn": fn}
```

**Root cause B:** Builtin is registered as a predicate but used as subject or object in N3.
Builtins must be the **predicate** of the triple pattern in the rule body.

---

## Diagnostic Checklist

When a rule produces no output:

1. [ ] Is the data present? Print `result.triples` with `pass_mode=True` to see all facts
2. [ ] Does the rule body match the data? Test each triple pattern independently
3. [ ] Are builtins checking the right input args (`args[:N]` not `args`)?
4. [ ] Is `log:onNegativeSurface` using distinct blank nodes?
5. [ ] Are numeric literals properly typed (`^^xsd:integer` not plain strings)?
6. [ ] Is the predicate IRI in `builtins={}` an exact match?
7. [ ] Add `explain=True` and read the proof tree
8. [ ] Check the output for abbreviated vs full IRIs when parsing `result.triples`

---

## Issues from Examples 26–35

### math:max returns xsd:double but stored value is xsd:decimal — match fails (30)
**Symptom:** rule using `?Room sensor:maxConfidence ?MaxConf . ?S sensor:confidence ?MaxConf` finds nothing.
**Cause:** `math:max` always returns `xsd:double`; N3 integer/decimal literals have different datatypes.
**Fix:** Use negation instead — find the sensor with no other sensor having a higher confidence:
```n3
{ ?S :room ?Room ; :confidence ?C ; :temperature ?T .
  _:neg log:onNegativeSurface { ?S2 :room ?Room ; :confidence ?C2 . ?C2 math:greaterThan ?C } }
    => { ?Room :effectiveTemperature ?T } .
```

### N3 output uses full IRIs for some prefixes — parsing breaks (29)
**Symptom:** output lines like `<http://example.org/order#order1> wf:allowedNext wf:confirmed .` — splitting on `:` fails to extract local name.
**Cause:** pyeye abbreviates IRIs only when the prefix was declared in the rule/data string. Cross-file prefixes (e.g., `ord:` declared in data but not in rules) may appear as full IRIs.
**Fix:** Use a robust `local()` helper that handles both forms:
```python
def local(tok):
    return tok.strip("<>").split("#")[-1].split(":")[-1]
```

### collectAllIn burst counting undercounts events (35)
**Symptom:** want to count N events in a time window, but the rule only finds N-1 or N-2.
**Cause:** The "cluster" approach (storing only the anchor event of each pair) misses events that share a window but were not the lexically-first anchor.
**Fix:** Mark *both* events in each qualifying pair as `inBurst`, then collect all burst-marked events for the user:
```n3
{ ?E1 :inBurstWith ?F } => { ?E1 :inBurst true } .
{ ?E1 :inBurstWith ?F } => { ?F  :inBurst true } .
```

### "Valid" negation rule fails when combined with collectAllIn rules (28)
**Symptom:** a rule checking `_:neg log:onNegativeSurface { ?P :violation ?V }` doesn't fire even for entities with no violations, when `collectAllIn` rules are also present.
**Cause:** Almost always a `collectAllIn` whose scope is a bound rule variable (see item 18) — the broken aggregation rule corrupts the binding, so neither the violations nor the negation behave as expected.
**Fix:** Use a fresh scope variable in every `collectAllIn`. With that in place, negation over derived `:violation` facts works:
```n3
{ ?P a :Person .
  _:neg log:onNegativeSurface { ?P :violation ?V } }
    => { ?P :valid true } .
```
