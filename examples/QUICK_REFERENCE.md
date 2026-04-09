# pyeye Quick Reference

Copy-paste patterns for common tasks.

---

## Imports

```python
# High-level API (most common)
from pyeye import execute, NamedNode, Variable, Triple, Literal

# Direct engine
from pyeye.engine import Engine, ReasoningTimeoutError
from pyeye.parser import parse_n3
from pyeye.output import N3Writer
```

---

## execute() — All Parameters

```python
result = execute(
    data_strings=["@prefix : <http://example.org/> . :x :y :z ."],  # inline N3 facts
    data_files=["facts.n3"],                                          # N3 files
    rule_strings=["{ ?A :y ?B } => { ?A :z ?B } ."],                 # inline rules
    rule_files=["rules.n3"],                                          # rule files
    query=Triple(Variable("S"), NamedNode("http://..."), Variable("O")),  # BC query
    entail=False,          # include RDFS-derived triples in output
    entail_owl=False,      # include OWL 2 RL derived triples
    pass_mode=False,       # include original facts in output
    explain=False,         # generate proof traces
    builtins={},           # dict of extra builtin functions
    max_steps=10_000,      # max forward-chaining iterations
    timeout_seconds=30.0,  # wall-clock timeout (None = unlimited)
)

# Result attributes
result.triples        # str: N3 serialization of derived triples
result.query_answers  # list[dict[str, Term]]: BC query bindings
result.stats          # dict: steps, derived, time_ms
result.proof_html     # str: HTML proof tree (explain=True only)
result.proof_dot      # str: Graphviz DOT (explain=True only)
result.proof_n3       # str: N3 proof (explain=True only)
```

---

## N3 Rule Syntax

```n3
@prefix : <http://example.org/> .
@prefix math: <http://www.w3.org/2000/10/swap/math#> .
@prefix log:  <http://www.w3.org/2000/10/swap/log#> .

# Forward rule: { body } => { head }
{ ?A :parent ?B . ?B :parent ?C } => { ?A :grandparent ?C } .

# Backward rule: { head } <= { body }
{ ?X :reachable ?Y } <= { ?X :link ?Y } .

# Math filter (comparison — no output variable)
{ ?P :price ?V . ?V math:greaterThan 99 } => { ?P :premium true } .

# Math computation (output variable)
{ ?P :price ?V . (?V 0.9) math:product ?Sale } => { ?P :salePrice ?Sale } .

# String
{ ?P :first ?F . ?P :last ?L . (?F " " ?L) string:concatenation ?Full }
    => { ?P :fullName ?Full } .

# Negation as failure
{ _:neg log:onNegativeSurface { ?S :hasOverride ?V } . ?S :default ?V }
    => { ?S :effective ?V } .

# Collect all matching values into a list
{ ?G :items ?L .
  ?L log:collectAllIn { ?X :group ?G . ?X :value ?V } ?V .
  ?L list:length ?N } => { ?G :count ?N } .
```

---

## Math Builtins

```n3
# Comparisons (filter — no result variable)
?V math:greaterThan 0
?V math:lessThan 100
?V math:greaterThanOrEqualTo 18
?V math:equalTo 42

# Arithmetic (list syntax — result variable at end)
(?A ?B) math:sum      ?C    # A + B = C
(?A ?B) math:difference ?C  # A - B = C
(?A ?B) math:product  ?C    # A * B = C
(?A ?B) math:quotient ?C    # A / B = C
(?A ?B) math:remainder ?C   # A % B = C

# Multi-item sum/product (list of any length)
(?A ?B ?C) math:sum ?Total

# Round / abs
?V math:ceiling ?R
?V math:floor   ?R
?V math:absoluteValue ?R
```

---

## String Builtins

```n3
# Concatenate (list of any length)
(?A " " ?B) string:concatenation ?Result

# Case conversion
?S string:upperCase   ?U
?S string:lowerCase   ?L
?S string:capitalize  ?C

# Pattern matching (result is "true" literal on match)
?S string:matches "^http" ?Bool

# Replace
(?S "old" "new") string:replace    ?Result  # first occurrence
(?S "old" "new") string:replaceAll ?Result  # all occurrences

# Substring (1-based)
(?S 1 5) string:substring ?Sub

# Length
?S string:length ?N

# Split / join
(?S " ") string:split  ?List
(?L " ") string:join   ?Result
```

---

## List Builtins

```n3
# Length
?L list:length ?N

# Membership filter (both args must be bound)
?Item list:in ?L

# Element at 1-based index
(?L 1) list:select ?First
(?L 2) list:select ?Second

# Append
(?L1 ?L2) list:append ?Combined

# Last element
?L list:last ?Last
```

---

## Backward Chaining

```python
from pyeye import execute, NamedNode, Variable, Triple

BASE = "http://example.org/"

result = execute(
    data_strings=[data],
    rule_strings=[rules],
    query=Triple(
        Variable("Who"),
        NamedNode(BASE + "canAccess"),
        NamedNode(BASE + "adminPanel"),
    ),
)

for binding in result.query_answers:
    who = binding.get("Who") or list(binding.values())[0]
    print(who.value)
```

Enable memoization for recursive predicates:
```n3
[] log:table :reachable .
{ ?X :reachable ?Y } <= { ?X :link ?Y } .
{ ?X :reachable ?Y } <= { ?X :reachable ?Z . ?Z :reachable ?Y } .
```

---

## Direct Engine API

```python
from pyeye.engine import Engine
from pyeye.parser import parse_n3
from pyeye.term import NamedNode, Literal, Variable, Triple
from pyeye.output import N3Writer

BASE = "http://example.org/"
XSD  = "http://www.w3.org/2001/XMLSchema#"

engine = Engine(timeout_seconds=60.0)

# Add facts directly
engine.add_triple(Triple(
    NamedNode(BASE + "alice"),
    NamedNode(BASE + "age"),
    Literal("32", datatype=NamedNode(XSD + "integer")),
))

# Parse and load N3
doc = parse_n3(rules_n3)
for t in doc.triples: engine.add_triple(t)
for r in doc.rules:   engine.add_rule(r)

engine.run()

# Query store
for t in engine.store.match(predicate=NamedNode(BASE + "isAdult")):
    print(t.subject.value)

# Serialize derived triples
print(N3Writer().write_triples(engine.derived_triples))

# Stats
print(engine.step_count)
print(len(engine.derived_triples))
```

---

## Incremental Reasoning

```python
engine = Engine()
# load rules once
for rule in parse_n3(rules).rules:
    engine.add_rule(rule)

# stream facts in
for sensor_reading in stream:
    engine.add_triple(Triple(sensor_reading.node, pred_temp, sensor_reading.value))
    engine.run()
    new = engine.derived_triples[prev_count:]
    prev_count = len(engine.derived_triples)
    process(new)
```

---

## Custom Builtins

```python
from pyeye.term import Variable, Literal

def celsius_to_fahrenheit(args, engine):
    # args[0] = input Celsius, args[-1] = output Variable (appended by engine)
    if isinstance(args[0], Variable): return None  # unbound
    c = float(args[0].value)
    return Literal(str(c * 9/5 + 32))

result = execute(
    data_strings=[data],
    rule_strings=[rules],
    builtins={"http://example.org/fn#celsiusToF": celsius_to_fahrenheit},
)
```

In N3:
```n3
@prefix fn: <http://example.org/fn#> .
{ ?Reading :celsius ?C . ?C fn:celsiusToF ?F } => { ?Reading :fahrenheit ?F } .
```

---

## RDFS / OWL Entailment

```python
# RDFS: subClassOf, subPropertyOf, domain, range
result = execute(data_strings=[rdfs_data], entail=True)

# OWL 2 RL: inverseOf, SymmetricProperty, TransitiveProperty, sameAs
result = execute(data_strings=[owl_data], entail_owl=True)

# Include original facts AND derived triples in output
result = execute(..., entail=True, pass_mode=True)
```

---

## Crypto Builtins

```n3
@prefix crypto: <http://www.w3.org/2000/10/swap/crypto#> .

# SHA-256 fingerprint
{ ?Doc :content ?C . ?C crypto:sha256 ?Hash } => { ?Doc :fingerprint ?Hash } .

# MD5
{ ?Doc :content ?C . ?C crypto:md5 ?Hash } => { ?Doc :md5 ?Hash } .

# Duplicate detection
{ ?A :fingerprint ?H . ?B :fingerprint ?H . ?A log:notEqualTo ?B }
    => { ?A :duplicateOf ?B } .
```

---

## Time Builtins

```n3
@prefix time: <http://www.w3.org/2000/10/swap/time#> .

# Current timestamp (ISO 8601 string)
_:t time:now ?Timestamp

# Component extraction (input must be ISO 8601 string)
?DT time:year   ?Y    # integer year
?DT time:month  ?M    # 1–12
?DT time:day    ?D    # 1–31
?DT time:hour   ?H    # 0–23
?DT time:minute ?Min  # 0–59
?DT time:second ?S    # float seconds
```

---

## Skolem (Deterministic IDs)

```n3
@prefix log: <http://www.w3.org/2000/10/swap/log#> .

# Create stable blank node from composite key
{ ?Person :worksAt ?Company . (?Person ?Company) log:skolem ?Employment }
    => { ?Employment a :Employment ; :employee ?Person ; :employer ?Company } .
```

Same inputs → same blank node, across runs and reasoning sessions.

---

## Error Handling

```python
from pyeye import execute, ReasoningTimeoutError

try:
    result = execute(
        data_strings=[data],
        rule_strings=[rules],
        timeout_seconds=10.0,   # raise after 10 seconds
        max_steps=50_000,       # raise after 50k steps
    )
except ReasoningTimeoutError as e:
    print(f"Reasoning timed out: {e}")
```

---

## Term Construction

```python
from pyeye.term import NamedNode, Literal, Variable, Triple, Formula

BASE = "http://example.org/"
XSD  = "http://www.w3.org/2001/XMLSchema#"

nn  = lambda local: NamedNode(BASE + local)
lit_int = lambda n: Literal(str(n), datatype=NamedNode(XSD + "integer"))
lit_str = lambda s: Literal(s)
lit_bool = lambda b: Literal("true" if b else "false", datatype=NamedNode(XSD + "boolean"))
var = lambda name: Variable(name)
```

---

## Patterns from Examples 26–35

### Interval overlap detection (26)
```n3
# Two intervals [S1,E1] and [S2,E2] overlap iff S1<E2 AND S2<E1
{ ?M1 :start ?S1 ; :end ?E1 . ?M2 :start ?S2 ; :end ?E2 .
  ?M1 log:notEqualTo ?M2 . ?S1 math:lessThan ?E2 . ?S2 math:lessThan ?E1 }
    => { ?M1 :conflictsWith ?M2 } .
```

### Cycle detection via transitive closure (27)
```n3
{ ?A g:edge ?B } => { ?A g:reaches ?B } .
{ ?A g:reaches ?B . ?B g:reaches ?C } => { ?A g:reaches ?C } .
{ ?N g:reaches ?N } => { ?N a g:CyclicNode } .
```

### Required property constraint (28)
```n3
{ ?P a :Person . _:n1 log:onNegativeSurface { ?P :name ?N } }
    => { ?P :violation "Missing required property :name" } .
```

### Cardinality constraint via collectAllIn (28)
```n3
{ ?P a :Person .
  (?N { ?P :name ?N } ?Names) log:collectAllIn ?P .
  ?Names list:length ?Count . ?Count math:greaterThan 1 }
    => { ?P :violation "Cardinality violation: :name must have exactly one value" } .
```

### State machine transition validation (29)
```n3
# Derive allowed next states
{ ?Order :currentState ?State . ?State :canTransitionTo ?Next }
    => { ?Order :allowedNext ?Next } .
# Flag invalid transitions with negation
{ ?Order :attemptTransition ?Target .
  _:neg log:onNegativeSurface { ?Order :allowedNext ?Target } }
    => { ?Order :transitionInvalid ?Target } .
```

### Max-confidence winner without math:max type mismatch (30)
```n3
# Use negation instead of math:max to find the winner
{ ?S :room ?Room ; :confidence ?C ; :temperature ?T .
  _:neg log:onNegativeSurface { ?S2 :room ?Room ; :confidence ?C2 . ?C2 math:greaterThan ?C } }
    => { ?Room :effectiveTemperature ?T } .
```

### Weighted scoring with math:product + math:sum (32)
```n3
{ ?A :income ?Inc . (?Inc 0.4) math:product ?W1 .
  ?A :credit ?CS  . (?CS  0.3) math:product ?W2 .
  (?W1 ?W2) math:sum ?Score }
    => { ?A :score ?Score } .
```

### Schema alignment bridge rules (33)
```n3
# schema.org → local
{ ?P a schema:Product } => { ?P a local:Item } .
{ ?P schema:name ?N }   => { ?P local:label ?N } .
# local → schema.org (bidirectional)
{ ?P a local:Item }     => { ?P a schema:Product } .
```

### BOM recursive cost roll-up (34)
```n3
# Leaf: unit values become totals
{ ?P :unitCost ?C } => { ?P :totalCost ?C } .
# Assembly: sum direct parts' totals
{ ?Asm :directPart ?Any .
  (?C { ?Asm :directPart ?P . ?P :totalCost ?C } ?Cs) log:collectAllIn ?Asm .
  ?Cs math:sum ?TC }
    => { ?Asm :totalCost ?TC } .
```

### Time-window burst detection (35)
```n3
# Mark events in the same burst window (< 120s apart)
{ ?E1 :user ?U ; :type :loginFail ; :timestamp ?T1 .
  ?E2 :user ?U ; :type :loginFail ; :timestamp ?T2 .
  ?E1 log:notEqualTo ?E2 . ?T2 math:greaterThan ?T1 .
  (?T2 ?T1) math:difference ?Gap . ?Gap math:lessThan 121 }
    => { ?E2 :inBurstWith ?E1 } .
# Count burst events; threshold ≥ 3 triggers alert
{ ?AnyE :user ?U ; :type :loginFail ; :inBurst true .
  (1 { ?E :user ?U ; :type :loginFail ; :inBurst true } ?Burst) log:collectAllIn ?U .
  ?Burst list:length ?N . ?N math:greaterThan 2 }
    => { ?U :alert "brute_force_detected" } .
```
