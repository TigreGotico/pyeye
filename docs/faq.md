# FAQ

Common questions and troubleshooting for pyeye. Questions are ordered from beginner to advanced.

---

## Basics

### What are triples and why should I care?

A triple is a statement with exactly three parts: subject, predicate, object. Think of it as a row in a three-column table:

| Subject | Predicate | Object |
|---------|-----------|--------|
| `:alice` | `:age` | `30` |
| `:alice` | `:parent` | `:bob` |
| `:product1` | `:price` | `99.99` |

The entire pyeye data model is built on triples. Facts are triples. Derived facts are triples. Rules pattern-match triples and produce triples. Once you internalize this, the rest falls into place.

### Where do I start?

Read the [documentation index](index.md) — it includes a five-minute tutorial. Then look at `examples/01_hello_world/` in the repository and work through examples 01–08 in order.

### What is the difference between `data_strings` and `rule_strings`?

- `data_strings` is parsed as Turtle/N3 and all triples go into the fact store. If the string also contains rules (`{ body } => { head }`), those rules are collected too.
- `rule_strings` is parsed as N3 and any rules in it are collected; any data triples are also loaded.

In practice, `data_strings` is for facts and `rule_strings` is for rules. The distinction matters because rules in `data_strings` are picked up only when the parser falls back to N3 mode — it works, but cleaner to separate concerns.

### Does the order of rules matter?

For forward chaining: no. The engine repeatedly applies all rules until fixpoint — no new facts. Rules fire whenever their body matches, regardless of the order they were loaded.

For backward chaining: the order in which rules are tried can affect which solution is found first, but all solutions are eventually returned.

---

## Rule problems

### Why is my rule not firing?

Check these in order:

1. **All body variables must be bound before builtins are called.** If a builtin receives an unbound variable, it returns `None` and that binding is skipped. Reorder your body patterns so that facts bind variables before builtins use them.

2. **The fact pattern must exactly match.** `:alice :age 30` and `:alice :age "30"` are different triples. A plain `30` is an `xsd:integer`-typed literal; `"30"` is a plain string. Check your data.

3. **Your rule head may not be ground.** If a head triple still contains an unbound variable after applying the binding, the triple is not added to the store.

4. **Prefix mismatch.** `:age` in a data file and `:age` in a rule file expand to the same IRI only if they share the same `@prefix` declaration. If each file has a different base IRI for `:`, the predicates differ.

5. **Forward vs backward.** Rules written with `<=` are backward rules and only fire when `query=` is set. Rules with `=>` are forward rules and fire during `engine.run()`.

To debug, print `result.stats["steps"]` — if it is 0, no rules fired. Use `explain=True` to see which rules fired and why:

```python
result = execute(
    data_strings=[data],
    rule_strings=[rules],
    explain=True,
    explain_format="html",
    pass_mode=True,
)
print(result.triples)       # what was derived
print(result.stats)         # steps, derived count
```

### What is the difference between forward and backward chaining?

**Forward chaining** starts from facts and applies rules to derive all possible consequences. It runs to fixpoint: no new facts can be derived. Use it to compute derived properties, enrich a knowledge graph, or check constraints.

**Backward chaining** works in reverse: you give it a goal (a query pattern) and it works backward through rules to find what bindings satisfy the goal. Use it to answer questions without deriving everything.

```python
# Forward chaining (default)
result = execute(data_strings=[data], rule_strings=[rules])

# Backward chaining query: who are bob's children?
from pyeye.term import NamedNode, Variable, Triple
result = execute(
    data_strings=[data],
    rule_strings=[rules],
    query=Triple(
        NamedNode("http://ex.org/bob"),
        NamedNode("http://ex.org/child"),
        Variable("Who"),
    ),
)
for b in result.query_answers:
    print(b["Who"])
```

You can use both in the same call: forward chaining runs first, then backward chaining uses the enriched store.

### Why does my rule fire more times than expected?

Each unique binding of variables fires the rule once. If you have 3 items and your rule matches all of them, it fires 3 times. This is correct behavior.

If you see duplicate derived triples, the store deduplicates them — duplicate facts are silently ignored.

### Why does my recursive rule cause an infinite loop?

Forward-chaining recursive rules are safe as long as they produce a finite number of new triples. For example:

```n3
{ ?X :parent ?Y } => { ?Y :child ?X } .                  # safe — one output per input
{ ?X :parent ?Y . ?Y :parent ?Z } => { ?X :grandparent ?Z } .  # safe — finite depth
```

Rules become infinite when they always produce new, distinct triples:

```n3
# Dangerous! Each firing creates a new blank node
{ ?X :count ?N . () log:skolem ?NewNode }
    => { ?X :sequence ?NewNode } .
```

For backward-chaining recursive rules, use `log:table` to enable memoization:

```n3
[] log:table :reachable .
{ ?X :reachable ?Y } <= { ?X :link ?Y } .
{ ?X :reachable ?Y } <= { ?X :reachable ?Z . ?Z :reachable ?Y } .
```

Without `log:table`, a recursive backward rule on a cyclic graph will loop indefinitely. The 30-second timeout (`timeout_seconds=30.0` default) provides a safety net for forward chaining.

---

## Builtins

### How do I use math operations?

Arithmetic builtins use a **list subject** syntax: put the inputs in a parenthesized list, put the output in the object slot.

```n3
@prefix math: <http://www.w3.org/2000/10/swap/math#> .

# Multiply price by 0.9
{ ?I :price ?P . (?P 0.9) math:product ?Sale }
    => { ?I :salePrice ?Sale } .

# Add two values
{ ?O :a ?A ; :b ?B . (?A ?B) math:sum ?Total }
    => { ?O :total ?Total } .

# Three-way sum
{ ?O :x ?X ; :y ?Y ; :z ?Z . (?X ?Y ?Z) math:sum ?T }
    => { ?O :total ?T } .
```

Filter comparisons work differently — they take a single subject and fail if the condition is not met:

```n3
{ ?P :age ?A . ?A math:greaterThan 17 } => { ?P :isAdult true } .
```

Do not write `?A ?B math:product ?C` — that is not valid N3 syntax. The inputs must be in a list `(?A ?B)`.

### My builtin returns None when used in a rule but works when called standalone. Why?

When a builtin is called from a rule body, the engine appends the *object* of the triple (the output variable) as the last element of `args`. If the output slot is an unbound `Variable`, and you check `if _unground(args)` naively, you will count the output variable as an unground input and return `None`.

The internal helpers in pyeye strip the trailing output variable before checking for unground inputs. If you write a custom builtin, use this pattern:

```python
from pyeye.term import Variable

def my_fn(args, engine):
    # Strip trailing output variable
    inputs = args[:-1] if len(args) >= 2 and isinstance(args[-1], Variable) else args
    if any(isinstance(a, Variable) for a in inputs):
        return None   # inputs not yet bound
    # ... compute using inputs[0], inputs[1], etc.
```

### What does `log:onNegativeSurface` do?

It is negation-as-failure. A rule with a negative surface fires only when the enclosed pattern *cannot* be matched in the store.

```n3
# Fire if service has no timeout configured
{ ?Svc a :Service .
  _:neg log:onNegativeSurface { ?Svc :timeout ?Any } }
    => { ?Svc :timeout :default } .
```

This uses the closed-world assumption: "I cannot prove `:timeout` exists for this service, therefore it does not have one."

Rules: the blank node (`_:neg`) before `log:onNegativeSurface` is syntactically required. Each negative surface in a rule must have a unique blank node label. Using the same label for two negations in one rule causes them to be interpreted as the same blank node.

### How do I aggregate values?

Use `log:collectAllIn`. It collects all values of a template expression for all bindings of a pattern:

```n3
@prefix log:  <http://www.w3.org/2000/10/swap/log#> .
@prefix math: <http://www.w3.org/2000/10/swap/math#> .
@prefix list: <http://www.w3.org/2000/10/swap/list#> .

# Sum all salaries per department
{ ?Dept a :Department .
  (?Sal { ?E :dept ?Dept . ?E :salary ?Sal } ?Sals) log:collectAllIn ?Scope .
  ?Sals math:sum ?Total }
    => { ?Dept :totalSalary ?Total } .

# Count members
{ ?G a :Group .
  (1 { ?M :memberOf ?G } ?Members) log:collectAllIn ?Scope .
  ?Members list:length ?N }
    => { ?G :size ?N } .
```

The template (`?Sal`, `1`) is evaluated for each satisfying binding of the pattern formula. All results are collected into an RDF list bound to the output variable. Grouping comes from variables shared between the outer body and the inner pattern (`?Dept`, `?G`); the scope object (`?Scope`) must be a fresh variable used nowhere else in the rule.

### What is `log:collectAllIn`?

It is pyeye's aggregation builtin. Analogous to SQL's `GROUP BY` + `ARRAY_AGG`. The calling convention is:

```n3
(?Template { body-pattern } ?OutputList) log:collectAllIn ?Scope .
```

- `?Template` — what to collect (evaluated per binding)
- `{ body-pattern }` — a formula matched against the store
- `?OutputList` — receives the resulting RDF list
- `?Scope` — a **fresh variable** used nowhere else in the rule (grouping comes from variables the inner pattern shares with the outer body)

After the list is built, pass it to `list:length`, `math:sum`, `math:max`, etc.

### What is `log:skolem` for?

It creates a deterministic blank node identifier from a list of key terms. The same inputs always produce the same blank node within a reasoning run. Use it to:

- Model many-to-many relationships as reified nodes
- Create stable synthetic IDs from composite keys
- Avoid duplicate nodes when the same entity is derived multiple times

```n3
# Employment node = (person, company) pair
{ ?P :worksAt ?C . (?P ?C) log:skolem ?Emp }
    => { ?Emp a :Employment ;
              :employee ?P ;
              :employer ?C } .
```

Do NOT use `log:uuid` in forward-chaining rule bodies. UUIDs are non-deterministic; the engine generates a new one every pass and never reaches fixpoint.

### What is `log:table` for?

It tells the backward-chaining engine to memoize calls to a predicate. Without it, a recursive backward rule on data with cycles will loop forever:

```n3
[] log:table :reachable .
{ ?X :reachable ?Y } <= { ?X :link ?Y } .
{ ?X :reachable ?Y } <= { ?X :reachable ?Z . ?Z :reachable ?Y } .
```

The directive has no effect on forward chaining — forward-chaining already deduplicates through the triple store (adding an existing triple is a no-op).

---

## Output and queries

### How do I query for specific results?

Use the `query=` parameter to do backward chaining from a goal triple:

```python
from pyeye import execute
from pyeye.term import NamedNode, Variable, Triple

result = execute(
    data_strings=[data],
    rule_strings=[rules],
    query=Triple(
        NamedNode("http://example.org/bob"),
        NamedNode("http://example.org/child"),
        Variable("Who"),
    ),
)

for binding in result.query_answers:
    print(binding["Who"].value)
```

Each element of `query_answers` is a `dict[str, Term]` mapping variable name (without `?`) to a bound term.

You can also use forward chaining and then scan `result.triples` or query `engine.store`:

```python
from pyeye.engine import Engine
from pyeye.term import NamedNode

engine = Engine()
# ... load data and rules ...
engine.run()

for t in engine.store.match(predicate=NamedNode("http://example.org/isSenior")):
    print(t.subject.value)
```

### What is the difference between `entail=True` and `pass_mode=True`?

- `entail=True` — run RDFS entailment rules *before* your rules. This derives implicit triples from ontology declarations (`rdfs:subClassOf`, etc.). These derived triples go into the store and are available to your rules.
- `pass_mode=True` — include the input facts in the output. Without this, only rule-derived facts are printed.

They are independent. You can use both together:

```python
result = execute(data_strings=[data], rule_strings=[rules], entail=True, pass_mode=True)
# Output: original facts + RDFS-derived facts + rule-derived facts
```

### How do I add facts incrementally?

Use the `Engine` class directly and call `add_triple()` after `run()`:

```python
from pyeye.engine import Engine
from pyeye.parser import parse_n3
from pyeye.term import Triple, NamedNode, Literal

engine = Engine()

rules_doc = parse_n3(rules_n3)
for rule in rules_doc.rules:
    engine.add_rule(rule)
engine.snapshot_initial()
engine.run()

# Add a new fact — incremental re-evaluation fires automatically
engine.add_triple(Triple(
    NamedNode("http://ex.org/sensor1"),
    NamedNode("http://ex.org/temperature"),
    Literal("36"),
))

# All derived_triples now includes consequences of the new fact
print(len(engine.derived_triples))
```

You can also call `engine.run()` again after adding multiple facts for a fresh fixpoint computation.

### How do I see which triples are from rules vs. from input?

After `execute()`, `result.triples` contains only derived triples by default. Enable `pass_mode=True` to include input facts.

When using `Engine` directly, `engine.derived_triples` contains only rule-derived triples. `engine.store` contains everything.

---

## Debugging

### How do I debug a failing rule?

1. **Add `explain=True`** to `execute()` and look at the proof traces. Even if the rule does not fire, the proof output tells you what did fire.

2. **Print `result.stats`** — if `steps == 0`, no rules fired at all.

3. **Use `pass_mode=True`** — see the full deductive closure including input facts.

4. **Check for variable name typos** — `?X` and `?x` are different variables. A pattern that references `?X` will never match if the fact was bound using `?x`.

5. **Simplify the rule** — remove conditions one at a time until it fires. When it stops firing after removing one condition, that condition is the problem.

6. **Print the store directly** using the Engine API:

```python
from pyeye.engine import Engine
from pyeye.parser import parse_n3

engine = Engine()
doc = parse_n3(your_n3_text)
for t in doc.triples:
    engine.add_triple(t)
engine.snapshot_initial()
for rule in doc.rules:
    engine.add_rule(rule)
engine.run()

# Dump all store contents
for t in engine.store.match():
    print(t)
```

7. **Check builtin groundedness** — if your rule has a builtin and the rule does not fire, the builtin might be returning `None` because an input variable is still unbound. Reorder body patterns so all input variables are bound before the builtin is called.

### How do I trace builtin calls?

Use `log:trace` in the rule body:

```n3
@prefix log: <http://www.w3.org/2000/10/swap/log#> .

{ ?X :price ?P . ?P log:trace true . ?P math:greaterThan 100 }
    => { ?X :expensive true } .
```

`log:trace` prints its arguments to stderr and always succeeds.

### Why do I get a `ReasoningTimeoutError`?

The engine exceeded its 30-second wall-clock limit. Common causes:

1. A rule generates an unbounded number of new triples (e.g., a rule that produces a fresh blank node on every firing).
2. A recursive forward rule without a termination condition.
3. Very large data with many rule firings.

Fix options:
- Add a termination condition to the rule
- Use `log:skolem` with a deterministic key instead of `log:uuid` or bare `@forSome`
- Increase `timeout_seconds`
- Set `max_steps` to cap the number of firings
- Set `limit_answers` to stop after N derivations

```python
from pyeye import execute, ReasoningTimeoutError

try:
    result = execute(
        data_strings=[data],
        rule_strings=[rules],
        timeout_seconds=60.0,
        max_steps=100_000,
    )
except ReasoningTimeoutError as e:
    print(f"Timed out: {e}")
```

---

## Advanced

### Can I add my own builtins?

Yes. A builtin is a Python callable with this signature:

```python
def my_fn(args: list[Term], engine) -> Term | list[Triple] | MultiResult | None:
    ...
```

Register it when calling `execute()`:

```python
result = execute(
    data_strings=[data],
    rule_strings=[rules],
    builtins={"http://example.org/fn#myFn": my_fn},
)
```

Or use `register_derive_function()` and call it from N3 with `e:derive`:

```python
from pyeye.builtins import register_derive_function
register_derive_function("my_fn", my_fn)
```

```n3
@prefix e: <http://eulersharp.sourceforge.net/2003/03swap/log-rules#> .
{ ?X :val ?V . ("my_fn" ?V) e:derive ?Result }
    => { ?X :result ?Result } .
```

### What datatypes does pyeye support?

pyeye's numeric builtins (`math:`) coerce any literal to a float via Python's `float()`. XSD typed literals (`xsd:integer`, `xsd:double`, `xsd:boolean`, `xsd:date`, `xsd:dateTime`) are all stored as `Literal` with their datatype attached. Bare integers like `42` in N3 are parsed as `xsd:integer`; bare decimals like `3.14` as `xsd:decimal`; `true`/`false` as `xsd:boolean`.

For string operations, `string:` builtins extract the `.value` string from any `Literal` or `NamedNode`.

`math:difference` handles ISO 8601 date subtraction specially and returns fractional years.

### How do I use RDFS or OWL reasoning?

Pass `entail=True` for RDFS or `entail_owl=True` for OWL 2 RL:

```python
result = execute(
    data_strings=[ontology + instances],
    rule_strings=[rules],
    entail=True,       # adds rdfs:subClassOf, subPropertyOf, domain, range reasoning
)

result = execute(
    data_strings=[owl_data],
    rule_strings=[rules],
    entail_owl=True,   # adds OWL 2 RL: sameAs, inverseOf, symmetric/transitive, etc.
)
```

RDFS and OWL entailment run before your rules, so their derived triples are available to your rules.

### How do I handle named graphs?

Use TriG syntax in your data files:

```n3
GRAPH <http://example.org/graph/A> {
    :alice :knows :bob .
}
GRAPH <http://example.org/graph/B> {
    :bob :knows :carol .
}
```

Then use `graph:` builtins to query specific graphs, or use the `TripleStore.match(graph=...)` API.

### How do I generate proof traces?

Enable `explain=True` and choose a format:

```python
# HTML proof tree
result = execute(data_strings=[data], rule_strings=[rules],
                 explain=True, explain_format="html")
with open("proof.html", "w") as f:
    f.write(result.explains)

# Graphviz DOT
result = execute(data_strings=[data], rule_strings=[rules],
                 explain=True, explain_format="dot")
print(result.explains)

# Raw proof objects (for programmatic analysis)
result = execute(data_strings=[data], rule_strings=[rules],
                 explain=True, explain_format="n3")
for tree in result.explains:
    print(tree)
```

### What is `pass_mode` vs `pass_all`?

- `pass_mode=True` — output includes input facts + derived triples (deductive closure)
- `pass_all=True` — output includes input facts + rules + derived triples

### Can I load remote files?

Yes, pass HTTP/HTTPS URLs to `data_paths` or `rule_paths`:

```python
result = execute(
    data_paths=["http://example.org/data.ttl"],
    rule_paths=["http://example.org/rules.n3"],
    cache_dir="/tmp/pyeye-cache",
)
```

SSRF protection is active: URLs targeting private IP ranges, loopback addresses, and non-HTTP schemes are rejected.

### What is DJITI?

DJITI (Dynamic Join Iteration Tree Index) is pyeye's join-ordering optimization. When matching a rule body with multiple patterns, it sorts patterns by the number of store triples they match (ascending), so the most selective patterns are tried first. This reduces the combinatorial explosion of the nested join.

Enable `djiti_debug=True` to see which ordering is chosen for each rule application.

### How does incremental reasoning work?

When you call `engine.add_triple(t)` after rules have been loaded, the engine immediately evaluates which rules could fire for the new triple and derives any consequences. These cascade: if a derived triple triggers another rule, that fires too — all within the same `add_triple()` call.

You can also call `engine.run()` again after adding facts to recompute the full fixpoint.

### What are the limits on rule complexity?

There is no explicit limit on rule complexity, but:

- More body patterns = more work per rule (exponential in the worst case)
- Recursive rules with large data can be slow without DJITI ordering
- Very deep backward-chaining recursion is limited by the 30-second timeout and Python's default recursion limit

For production use, add `timeout_seconds` and `max_steps` as safety bounds.

### How do I serialize derived triples back to N3?

Use `N3Writer`:

```python
from pyeye.output import N3Writer

writer = N3Writer({"": "http://example.org/", "xsd": "http://www.w3.org/2001/XMLSchema#"})
n3_text = writer.write_triples(engine.derived_triples)
print(n3_text)
```

Or just use `result.triples` from `execute()`, which is already serialized N3.

### Why does my `list:in` check always fail?

`list:in` requires both arguments to be ground (bound). It does not enumerate list members — it checks membership. Both the item and the list must already be bound when `list:in` is called:

```n3
# Wrong: ?Item is unbound
{ :myList list:in ?Item } => { :result :has ?Item } .

# Right: check if a bound ?Role is in the allowed list
{ ?U :role ?R . ?R list:in (:admin :editor) }
    => { ?U :hasAccess true } .
```

Note the argument order: `item list:in list`, not `list list:in item`.

### Can I use pyeye as a constraint checker?

Yes. The typical pattern is:

1. Write rules that derive `:violation` triples when constraints are violated
2. Run the engine
3. Check `result.triples` for any `:violation` triples

```n3
# Required property constraint
{ ?P a :Person . _:n1 log:onNegativeSurface { ?P :name ?N } }
    => { ?P :violation "Missing required property :name" } .

# Value range constraint
{ ?P a :Person . ?P :age ?A . ?A math:lessThan 0 }
    => { ?P :violation "Age cannot be negative" } .
```

To assert a triple was NOT derived, use `not_entail=`:

```python
result = execute(
    data_strings=[data],
    rule_strings=[rules],
    not_entail=Triple(
        NamedNode("http://ex.org/someEntity"),
        NamedNode("http://ex.org/violation"),
        Variable("_"),    # any object
    ),
)
if result.stats["not_entail_failed"]:
    print("Constraint violated!")
```

### How do I combine pyeye with my existing Python data?

Convert your Python data to N3 triples and pass them as `data_strings`. The simplest approach is string formatting:

```python
BASE = "http://example.org/"

facts = []
for employee in employees:
    facts.append(f"<{BASE}{employee['id']}> a <{BASE}Employee> .")
    facts.append(f"<{BASE}{employee['id']}> <{BASE}salary> {employee['salary']} .")
    facts.append(f"<{BASE}{employee['id']}> <{BASE}dept> <{BASE}{employee['dept']}> .")

n3_data = "@prefix : <http://example.org/> .\n" + "\n".join(facts)

result = execute(data_strings=[n3_data], rule_strings=[rules])
```

For typed literals, use explicit type notation:

```python
facts.append(
    f'<{BASE}{emp["id"]}> <{BASE}salary> '
    f'"{emp["salary"]}"^^<http://www.w3.org/2001/XMLSchema#integer> .'
)
```

Or build triples programmatically with term types and use `N3Writer` to serialize:

```python
from pyeye.term import NamedNode, Literal, Triple
from pyeye.output import N3Writer
from pyeye.engine import Engine
from pyeye.parser import parse_n3

XSD = "http://www.w3.org/2001/XMLSchema#"

engine = Engine()
for emp in employees:
    subj = NamedNode(BASE + emp["id"])
    engine.add_triple(Triple(subj, NamedNode(BASE + "salary"),
                             Literal(str(emp["salary"]),
                                     datatype=NamedNode(XSD + "integer"))))

engine.snapshot_initial()
for rule in parse_n3(rules_n3).rules:
    engine.add_rule(rule)
engine.run()
```
