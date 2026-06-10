# N3 Syntax Guide

This guide covers the N3 (Notation 3) text format that pyeye uses to write facts and rules. No prior knowledge of RDF, logic programming, or the Semantic Web is assumed.

---

## Overview

N3 is a text format for writing graphs of statements. It extends the simpler Turtle format (which itself extends the even simpler N-Triples format). In pyeye you will use N3 for:

- **Data files** — facts that you load with `data_strings=` or `data_paths=`
- **Rule files** — `{ body } => { head }` rules loaded with `rule_strings=` or `rule_paths=`

The same file can contain both facts and rules.

---

## Triples: subject predicate object

The fundamental unit of N3 is a **triple**: a statement with exactly three parts.

```n3
<http://example.org/alice> <http://example.org/age> "30" .
```

This is verbose. N3 provides two abbreviation mechanisms:

### Prefix declarations

```n3
@prefix : <http://example.org/> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

:alice :age "30"^^xsd:integer .
```

`@prefix name: <IRI> .` declares that `name:` is an abbreviation for the IRI. `:` (colon with nothing before it) is the default prefix — typically your application namespace.

### Predicate-subject shorthand

Turtle and N3 let you group multiple predicates for the same subject using `;`, and multiple objects for the same predicate using `,`:

```n3
@prefix : <http://example.org/> .

:alice :age 30 ;
       :name "Alice" ;
       :parent :bob .

:alice :likes :cats , :dogs .
```

This is equivalent to four separate triples.

---

## IRIs and prefixed names

An **IRI** (Internationalized Resource Identifier) is a global name. In N3 syntax, IRIs go in angle brackets:

```n3
<http://example.org/alice>
<http://www.w3.org/1999/02/22-rdf-syntax-ns#type>
```

With a `@prefix` declaration, `prefix:localname` expands to the full IRI:

```n3
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
:alice rdf:type :Person .
# same as: <http://example.org/alice> <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> <http://example.org/Person>
```

The shorthand `a` is built-in for `rdf:type`:

```n3
:alice a :Person .
```

---

## Literals (values)

Literals represent actual data values, not resources.

### Strings

```n3
:alice :name "Alice Smith" .
:doc   :description "Multi-line\nstring" .
```

### Language-tagged strings

```n3
:alice :name "Alice"@en .
:alice :name "アリス"@ja .
```

### Typed literals

```n3
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

:item :count 42 .                              # bare integer
:item :price 9.99 .                            # bare decimal
:item :flag true .                             # boolean
:item :count "42"^^xsd:integer .               # explicit type
:item :created "2024-01-15"^^xsd:date .        # date
:item :timestamp "2024-01-15T10:30:00" .       # datetime string
```

Bare integers, decimals, and `true`/`false` are shorthand for the XSD typed equivalents. When you pass numbers to builtins like `math:greaterThan`, pyeye handles both bare numbers and typed literals.

---

## Rules: `{ body } => { head }`

A forward rule fires when all patterns in the body match the store simultaneously. It then adds all triples in the head to the store.

```n3
@prefix : <http://example.org/> .

{ ?X :parent ?Y } => { ?Y :child ?X } .
```

The body can have multiple patterns joined by `.`:

```n3
{ ?X :parent ?Y . ?Y :parent ?Z } => { ?X :grandparent ?Z } .
```

This fires once for every pair of (X, Z) such that there is a Y connecting them. With facts `:alice :parent :bob .` and `:bob :parent :carol .`, the rule produces `:alice :grandparent :carol .`

The head can also have multiple triples:

```n3
{ ?P :price ?V . ?V math:greaterThan 100 }
    => { ?P :expensive true . ?P :requiresApproval true } .
```

---

## Variables: `?Name`

Variables start with `?`. They are *pattern variables*: during matching, the engine tries every possible binding of each variable to a term in the store.

```n3
{ ?X :parent ?Y . ?Y :parent ?Z } => { ?X :grandparent ?Z } .
```

Variables are scoped to a single rule. The same variable name in two different rules is independent.

Variable names are case-sensitive. By convention, start them with an uppercase letter (`?X`, `?Person`, `?Amount`) but lowercase works too.

---

## Blank nodes: `_:name`

Blank nodes are anonymous resources — nodes with no global IRI. They are like local variables for data.

```n3
@prefix : <http://example.org/> .

# A blank node as subject
_:order1 :item :widget ; :qty 3 .

# Anonymous blank node with []
[] :item :gadget ; :qty 1 .

# Blank node with inline properties
:alice :livesIn [ :city "Lisbon" ; :country "Portugal" ] .
```

In rule bodies, blank nodes act as existential quantifiers: "there exists some _:n such that ...". In rule heads, blank nodes generate fresh anonymous nodes in the output.

**Important gotcha:** Do not reuse blank node labels across rules to mean the same node. In rule bodies, blank nodes inside `log:onNegativeSurface { }` are special (see Negation below). Each `_:neg` in a negation surface should have a unique name per rule.

---

## Lists: `(a b c)`

N3 supports RDF lists using parentheses:

```n3
@prefix : <http://example.org/> .

:alice :scores (90 85 92) .
:project :tags ("urgent" "Q1" "backend") .
:bob :scores () .                # the empty list
```

Internally this expands to a chain of `rdf:first` / `rdf:rest` triples — the same structure as a Lisp-style linked list.

Lists are used extensively with builtins that take multiple inputs:

```n3
@prefix math: <http://www.w3.org/2000/10/swap/math#> .

# (90 85 92) math:sum ?Total — adds all three numbers
{ :alice :scores ?L . ?L math:sum ?Total }
    => { :alice :totalScore ?Total } .
```

And for multi-argument builtins:

```n3
# (?price 0.9) math:product ?discounted
{ ?I :price ?P . (?P 0.9) math:product ?D }
    => { ?I :discountedPrice ?D } .
```

---

## Backward rules: `{ head } <= { body }`

A backward rule is the reverse of a forward rule: instead of starting from facts and deriving conclusions, the engine works backward from a goal.

```n3
{ ?X :reachable ?Y } <= { ?X :link ?Y } .
{ ?X :reachable ?Y } <= { ?X :reachable ?Z . ?Z :reachable ?Y } .
```

Backward rules are only used when you call `execute()` with a `query=` argument. The engine then works backward from the query to find what bindings satisfy it.

```python
from pyeye import execute
from pyeye.term import NamedNode, Variable, Triple

BASE = "http://example.org/"

result = execute(
    data_strings=["@prefix : <http://example.org/> . :a :link :b . :b :link :c ."],
    rule_strings=["""
        @prefix : <http://example.org/> .
        { ?X :reachable ?Y } <= { ?X :link ?Y } .
        { ?X :reachable ?Y } <= { ?X :reachable ?Z . ?Z :reachable ?Y } .
    """],
    query=Triple(
        NamedNode(BASE + "a"),
        NamedNode(BASE + "reachable"),
        Variable("Dest"),
    ),
)

for binding in result.query_answers:
    print(binding["Dest"].value)
# http://example.org/b
# http://example.org/c
```

Forward and backward rules can coexist in the same file. Forward rules run first (during `engine.run()`), then backward chaining is applied to the query.

---

## Negation: `log:onNegativeSurface`

N3 implements negation-as-failure (closed-world assumption) via `log:onNegativeSurface`. A negative surface fires only when the enclosed formula *cannot* be matched.

```n3
@prefix : <http://example.org/> .
@prefix log: <http://www.w3.org/2000/10/swap/log#> .

# Fire if ?Svc has no :timeout property
{ ?Svc a :Service .
  _:neg log:onNegativeSurface { ?Svc :timeout ?Any } }
    => { ?Svc :timeout :defaultTimeout } .
```

The blank node before `log:onNegativeSurface` is syntactically required. Use a unique blank node label for each negation in a rule — `_:neg1`, `_:neg2`, etc.:

```n3
{ ?Svc a :Service .
  _:n1 log:onNegativeSurface { ?Svc :host ?H } .
  _:n2 log:onNegativeSurface { ?Svc :port ?P } }
    => { ?Svc :status :misconfigured } .
```

**Important:** Negation-as-failure is closed-world. "I cannot derive X" is treated as "X is false." If your dataset is incomplete, this may give unexpected results.

---

## Named graphs: `GRAPH <iri> { ... }`

Named graphs allow you to associate triples with a specific context (a graph IRI). pyeye uses TriG syntax:

```n3
@prefix : <http://example.org/> .

GRAPH <http://example.org/graph/A> {
    :alice :knows :bob .
}

GRAPH <http://example.org/graph/B> {
    :bob :knows :carol .
}

# Triples without a GRAPH block go to the default graph
:carol :age 35 .
```

Rules match against the default graph. To test whether a (bound) triple is in a named graph, use the `graph:member` filter builtin:

```n3
{ ?S :checked true . (?S :name "Alice") graph:member :g1 }
    => { ?S :inTrustedGraph true } .
```

From Python, enumerate a named graph with `engine.store.match(graph=NamedNode(...))`. See [Builtins — graph:](builtins.md#graph--named-graph-operations) for the full list of graph builtins.

---

## RDF-star: `<< S P O >>`

RDF-star allows a triple itself to appear as the subject or object of another triple — useful for annotating statements.

```n3
@prefix : <http://example.org/> .

# Annotate the fact that alice knows bob with a source
<< :alice :knows :bob >> :source <http://example.org/survey/2024> .
<< :alice :knows :bob >> :confidence 0.95 .
```

The `<< S P O >>` syntax produces a `TripleTerm` in pyeye's internal representation.

---

## `has`, `is`, and `of` sugar

N3 allows three keywords that make statements read more like English:

```n3
:Alice :parent has :Bob .     # same as  :Alice :parent :Bob .
:Alice :name is "Alice" .     # same as  :Alice :name "Alice" .
```

`has` and `is` are simply skipped during parsing. `of` inverts the predicate — it swaps subject and object:

```n3
:Bob :child of :Alice .       # same as  :Alice :child :Bob .
```

---

## Formula terms: `(| Functor Args |)`

A formula term embeds a functor-with-arguments structure as a value inside a triple:

```n3
:alice :thinks (| :says :alice "hello" |) .
```

The first element is the functor; the rest are arguments. pyeye represents this as a `FormulaTerm`.

---

## Sets: `($ a b c $)`

Sets are unordered collections:

```n3
:Alice :likes ($ :pizza :sushi $) .
```

Unlike lists, element order does not matter for equality. pyeye represents this as a `SetTerm`.

---

## Multi-line strings and comments

Use triple quotes (`'''` or `"""`) for text spanning multiple lines:

```n3
:book :description '''This is a
multi-line description.''' .
```

Comments start with `#` and run to the end of the line:

```n3
# This is a full-line comment
:alice :name "Alice" .  # inline comment
```

---

## Datatypes in depth

### XSD namespace

Most data types come from the XML Schema Definition (XSD) namespace:

```n3
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

:ex :intVal   "42"^^xsd:integer .
:ex :floatVal "3.14"^^xsd:double .
:ex :boolVal  "true"^^xsd:boolean .
:ex :dateVal  "2024-01-15"^^xsd:date .
:ex :dtVal    "2024-01-15T10:30:00"^^xsd:dateTime .
:ex :strVal   "hello"^^xsd:string .
```

### Shorthand for common types

```n3
42        # same as "42"^^xsd:integer
3.14      # same as "3.14"^^xsd:decimal
true      # same as "true"^^xsd:boolean
false     # same as "false"^^xsd:boolean
"hello"   # plain string (no datatype)
```

### Creating typed literals in rules

Use `log:dtlit` to construct a typed literal in a rule head:

```n3
@prefix log: <http://www.w3.org/2000/10/swap/log#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

{ ?P :rawScore ?V .
  (?V "http://www.w3.org/2001/XMLSchema#integer") log:dtlit ?Typed }
    => { ?P :score ?Typed } .
```

---

## Path expressions: `!` and `^`

N3 supports path shorthand for following chains of predicates. A path expression is a *term* — it denotes the node reached by following the predicate — and can stand in any subject or object position.

Forward path (`!`) — `:alice!:parent` denotes alice's parent (the object of `:alice :parent ?`):

```n3
# Bind ?N to the name of alice's parent
{ :alice!:parent :name ?N } => { :alice :parentName ?N } .
```

Reverse path (`^`) — `:bob^:parent` denotes whoever has bob as their parent (the subject of `? :parent :bob`):

```n3
# Bind ?N to the name of a node whose :parent is :bob
{ :bob^:parent :name ?N } => { :found :name ?N } .
```

Paths can be chained:

```n3
# alice's parent's parent (grandparent)
{ :alice!:parent!:parent :name ?N } => { :alice :grandparentName ?N } .
```

Paths are syntactic sugar: the parser compiles each step into a fresh variable plus an auxiliary triple pattern, so they never reach the engine as a distinct term type.

---

## `log:table` — memoization for backward chaining

When using recursive backward rules, declare predicates as tabled to prevent infinite loops:

```n3
@prefix : <http://example.org/> .
@prefix log: <http://www.w3.org/2000/10/swap/log#> .

[] log:table :reachable .

{ ?X :reachable ?Y } <= { ?X :link ?Y } .
{ ?X :reachable ?Y } <= { ?X :reachable ?Z . ?Z :reachable ?Y } .
```

The `[] log:table :reachable .` directive tells the engine to memoize calls to the `:reachable` predicate during backward chaining. Without this, the recursive rule would loop indefinitely on cyclic graphs.

---

## `@forSome` — existential quantification

`@forSome` declares blank-node-like variables that are existentially quantified over the whole document. In practice, use `log:skolem` instead for generating fresh identifiers in rules — it is more predictable and produces deterministic output:

```n3
@prefix log: <http://www.w3.org/2000/10/swap/log#> .

{ ?P :worksAt ?C . (?P ?C) log:skolem ?Employment }
    => { ?Employment a :Employment ; :employee ?P ; :employer ?C } .
```

---

## Common gotchas

### Period at end of every statement

Every triple, rule, and prefix declaration must end with `.`:

```n3
# Wrong
:alice :age 30
{ ?X :parent ?Y } => { ?Y :child ?X }

# Right
:alice :age 30 .
{ ?X :parent ?Y } => { ?Y :child ?X } .
```

### Semicolons do not end a rule

A `;` groups predicates for the same subject — it does not terminate a statement. A `.` does:

```n3
:alice :name "Alice" ;
       :age  30 .     # period ends the statement, not the semicolon
```

Inside rule heads, `;` groups multiple head triples for the same subject:

```n3
{ ?P :price ?V . ?V math:greaterThan 100 }
    => { ?P :expensive true ; :requiresApproval true } .
```

### Blank nodes in rule bodies behave as existentials

In a rule body, `_:name` means "there exists some node with this local name." Two patterns using the same `_:name` must refer to the same node. Use this to join on anonymous nodes:

```n3
# Both patterns must match the same blank node
{ _:order :item ?I . _:order :qty ?Q }
    => { ?I :ordered ?Q } .
```

### Builtin argument ordering

Most computation builtins follow the pattern:

```n3
(input1 input2 ...) builtin:name ?output
```

The subject is a list of inputs. The object is the output variable. This is different from filter builtins, which take their single argument as the subject:

```n3
# Filter: subject is the value being tested, object is the comparand
?V math:greaterThan 100 .

# Computation: subject is input list, object is output variable
(?A ?B) math:sum ?C .
```

### Variables are untyped

Variables match any term: IRIs, literals, blank nodes. The builtin must handle what it receives. If a builtin receives a variable it cannot yet evaluate, it returns `None` and the rule body fails for that binding. This is not an error.

### N3 is case-sensitive

`:alice` and `:Alice` are different resources. Variable names like `?x` and `?X` are different variables.

### Prefixes are per-document

`@prefix` declarations apply to the document they appear in. If you load multiple data and rule files, each file can have its own prefix declarations. The serializer uses the merged set of all prefixes.

---

## Full working example

```n3
@prefix :     <http://example.org/shop#> .
@prefix math: <http://www.w3.org/2000/10/swap/math#> .
@prefix log:  <http://www.w3.org/2000/10/swap/log#> .
@prefix list: <http://www.w3.org/2000/10/swap/list#> .

# --- Facts ---
:widget :price 120 ; :category :electronics ; :tags ("sale" "featured") .
:gadget :price 40  ; :category :electronics .

# --- Rules ---

# Premium if price > 100 in the electronics category
{ ?P :category :electronics . ?P :price ?V . ?V math:greaterThan 100 }
    => { ?P :tier :premium } .

# Standard otherwise (using negation)
{ ?P :category :electronics .
  _:neg log:onNegativeSurface { ?P :tier :premium } }
    => { ?P :tier :standard } .

# 10% discount for premium items
{ ?P :tier :premium . ?P :price ?V .
  (?V 0.1) math:product ?D }
    => { ?P :discount ?D } .

# Count tags
{ ?P :tags ?L . ?L list:length ?N }
    => { ?P :tagCount ?N } .
```

Run it:

```python
from pyeye import execute

result = execute(
    data_strings=[n3_text],   # the block above
    rule_strings=[],           # rules are embedded in data_strings
)
print(result.triples)
```

Output (order may vary):

```n3
:widget :tier :premium .
:gadget :tier :standard .
:widget :discount 12.0 .
:widget :tagCount 2 .
```

---

## Quick reference card

| Syntax | Meaning | Example |
| :--- | :--- | :--- |
| `:foo` | Prefixed name | `:alice :knows :bob .` |
| `<http://...>` | Full IRI | `<http://x.org/a> :p <http://x.org/b> .` |
| `?X` | Variable | `{ ?X :p ?Y } => { ... }` |
| `"text"` | String literal | `:alice :name "Alice" .` |
| `42` / `3.14` | Number | `:alice :age 42 .` |
| `"text"@en` | Language-tagged | `:greeting :text "Hi"@en .` |
| `"text"^^xsd:date` | Typed literal | `:date :value "2025-03-15"^^xsd:date .` |
| `[]` | Anonymous blank node | `:alice :knows [] .` |
| `[ :p :o ]` | Blank node with properties | `:alice :livesIn [ :city "Lisbon" ] .` |
| `_:name` | Labelled blank node | `_:b1 :p :o .` |
| `(a b c)` | Ordered list | `:favorites (:a :b :c) .` |
| `a` | `rdf:type` shorthand | `:alice a :Person .` |
| `;` | Same subject | `:alice :age 30 ; :name "A" .` |
| `,` | Same subject+predicate | `:alice :knows :b, :c .` |
| `.` | End of statement | `:a :p :b .` |
| `# ...` | Comment | `# this is a comment` |
| `{ ... } => { ... }` | Forward rule | `{ ?X :p ?Y } => { ?Y :q ?X } .` |
| `{ ... } <= { ... }` | Backward rule | `{ ?Y :q ?X } <= { ?X :p ?Y } .` |
| `@prefix p: <url> .` | Prefix shortcut | `@prefix : <http://x.org/> .` |
| `<< S P O >>` | RDF-star triple term | `<< :a :p :b >> :saidBy :c .` |
| `(\| Functor Args \|)` | Formula term | `:a :thinks (\| :says :a "hi" \|) .` |
| `!` / `^` | Forward / reverse path | `{ :a!:p :name ?N } => { ... }` |
| `has` / `is` | Readability sugar (skipped) | `:a :p has :b .` |
| `of` | Property inversion | `:b :p of :a .` |
| `($ a b $)` | Set | `:a :likes ($ :x :y $) .` |
| `log:onNegativeSurface` | Negation as failure | `_:n log:onNegativeSurface { ... }` |
| `GRAPH <g> { ... }` | TriG named graph | `GRAPH :g1 { :a :p :b . }` |
| `[] log:table :pred .` | Memoize backward predicate | see [log:table](#logtable--memoization-for-backward-chaining) |
