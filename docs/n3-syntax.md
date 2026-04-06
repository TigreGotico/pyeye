# N3 Syntax Guide

This guide covers the N3 (Notation 3) text format that pyeye uses to write facts and rules. No prior knowledge of RDF, logic, or Semantic Web is assumed.

All parsing is implemented in `Parser` — `pyeye/parser.py:168`.

---

## The Absolute Basics

### A single fact

```n3
:alice :knows :bob .
```

Every fact has three parts:

| Part | Name | Meaning |
| :--- | :--- | :--- |
| `:alice` | **Subject** | Who the fact is about |
| `:knows` | **Predicate** | What the fact says |
| `:bob` | **Object** | The value or target |

The `.` ends the statement. Missing it is the most common parse error.

### Defining shortcuts with `@prefix`

`Parser._do_prefix()` — `pyeye/parser.py:203`

Writing full web addresses everywhere is tedious:

```n3
<http://example.org/people/alice> <http://example.org/relations/knows> <http://example.org/people/bob> .
```

Instead, define a prefix shortcut:

```n3
@prefix : <http://example.org/> .

:alice :knows :bob .
# Expands to: <http://example.org/alice> <http://example.org/knows> <http://example.org/bob> .
```

Multiple prefixes:

```n3
@prefix person: <http://example.org/people/> .
@prefix rel:    <http://example.org/relations/> .

person:alice rel:knows person:bob .
```

### Semicolons and commas

```n3
# Semicolon: same subject, different predicates
:alice :age 30 ;
       :name "Alice" ;
       :city "Lisbon" .

# Comma: same subject and predicate, different objects
:alice :knows :bob, :carol, :dave .
```

---

## Rules

`Parser._do_formula_top()` — `pyeye/parser.py:257`

### Basic rule

```n3
{ ?X :parent ?Y } => { ?Y :child ?X } .
```

- The `{ }` before `=>` is the **body** — the pattern to look for
- The `{ }` after `=>` is the **head** — the new fact to create
- `?X` and `?Y` are **variables** that match any value

### Multiple body conditions

```n3
{ ?X :parent ?Y . ?Y :parent ?Z } => { ?X :grandparent ?Z } .
```

The `.` between body patterns means "both must be true." The shared variable `?Y` acts as a bridge.

### Reversed rules (`<=`)

```n3
{ ?Y :child ?X } <= { ?X :parent ?Y } .
```

Identical to `{ ?X :parent ?Y } => { ?Y :child ?X } .` — just written in reverse. Both forms are supported.

---

## Variables

`Parser._item()` — `pyeye/parser.py:311`

Variables are written as `?` followed by a name:

```n3
?X   ?Person   ?someVar   ?camelCase
```

- Variable names are case-sensitive: `?X` ≠ `?x`
- The same variable name in a rule body must match the same value everywhere it appears
- Variables in the head get their values from the body match

---

## Literals

### Strings

```n3
:alice :name "Alice" .
:book :description '''Multi-line
text''' .
```

Triple-quoted strings (`'''` or `"""`) span multiple lines.

### Numbers

```n3
:alice :age 30 .
:pi :value 3.14 .
:avogadro :value 6.022e23 .
```

### Language tags

```n3
:greeting :text "Hello"@en .
:greeting :text "Olá"@pt .
```

### Datatype literals

```n3
:event :date "2025-03-15"^^<http://www.w3.org/2001/XMLSchema#date> .
```

---

## Blank Nodes

`Parser._bnode()` — `pyeye/parser.py:460`

### Anonymous blank node

```n3
:alice :knows [] .
```

`[]` means "some unnamed thing." The engine creates a unique ID for it.

### Blank node with properties

```n3
:alice :livesIn [ :city "Lisbon" ; :country "Portugal" ] .
```

### Named blank node

```n3
_:b1 :p :o .
```

---

## RDF Lists

`Parser._rdf_list()` — `pyeye/parser.py:478`

```n3
:alice :favorites (:pizza :sushi :tacos) .
```

Parentheses create an ordered RDF list (`rdf:first` / `rdf:rest` chain). An empty list:

```n3
:bob :favorites () .
```

---

## Type Declaration Shorthand

```n3
:alice a :Person .
```

`a` is shorthand for `rdf:type`. Equivalent to `:alice rdf:type :Person .`

---

## Comments

```n3
# Full-line comment
:alice :name "Alice" .  # Inline comment
```

---

## Extended Syntax

### Triple Terms — Reifying a Triple

`Parser._triple_term()` — `pyeye/parser.py:511`

```n3
<< :alice :knows :bob >> :wasSaidBy :charlie .
```

The `<< S P O >>` syntax treats a triple as a value that can be the subject or object of another triple.

### Formula Terms

`Parser._formula_term()` — `pyeye/parser.py:521`

```n3
:alice :thinks (| :says :alice "hello" |) .
```

The `(| Functor Args |)` syntax embeds a formula inside another triple.

### `has`, `is`, `of` Sugar

`Parser._verb_obj_list()` — `pyeye/parser.py:270`

```n3
:Alice :parent has :Bob .       # Same as: :Alice :parent :Bob .
:Alice :name is "Alice" .       # Same as: :Alice :name "Alice" .
:Bob :child of :Alice .         # Same as: :Alice :child :Bob .  (swaps S and O)
```

`has` and `is` are skipped during parsing. `of` **swaps** subject and object.

### Path Expressions

`Parser._path_expression()` — `pyeye/parser.py:567`

```n3
:a ! :p ! :q :target .       # Forward chain: follow :p then :q from :a
:a ^ :parent :target .        # Reverse path: find who is parent of :a
```

`!` traverses forward along the predicate. `^` traverses in reverse.

### Set Syntax

`Parser._set_term()` — `pyeye/parser.py:534`

```n3
:Alice :likes ($ :pizza :sushi :tacos $) .
```

Sets use `($ ... $)` syntax. Treated as ordered lists internally.

### BLOGIC Negative Surfaces

Detected in `Engine._match_triples_iter` — `pyeye/engine.py:334`

```n3
@prefix log: <http://www.w3.org/2000/10/swap/log#> .

:S log:onNegativeSurface { :a :p :b } .
```

A negative surface fires its enclosing rule **only if** the enclosed formula does NOT match the store. Example:

```n3
{ ?Person :age ?A . ?A e:greaterThan "17" .
  _:neg log:onNegativeSurface { ?Person :hasLicense true } }
    => { ?Person :cannotDrive true } .
```

Derives `:cannotDrive` for anyone over 17 who does NOT have a license in the store.

### TriG Named Graphs

`Parser._do_graph()` — `pyeye/parser.py:241`

```n3
@prefix : <http://ex.org/> .

GRAPH :g1 {
    :alice :name "Alice" .
    :bob   :name "Bob" .
}

GRAPH :g2 {
    :carol :name "Carol" .
}
```

`GRAPH <id> { ... }` stores triples in a named graph. Access via `TripleStore.match(graph=...)`.

---

## Quick Reference Card

| Syntax | Meaning |
| :--- | :--- |
| `:foo` | Prefixed name |
| `<http://...>` | Full IRI |
| `?X` | Variable |
| `"text"` | String literal |
| `42` / `3.14` | Integer / decimal |
| `"text"@en` | Language-tagged literal |
| `"text"^^<type>` | Datatype literal |
| `[]` | Anonymous blank node |
| `_:name` | Named blank node |
| `(a b c)` | Ordered RDF list |
| `a` | `rdf:type` shorthand |
| `;` | Same subject, new predicate |
| `,` | Same subject + predicate, new object |
| `.` | End of statement |
| `# ...` | Comment |
| `{ ... } => { ... }` | Rule (forward) |
| `{ ... } <= { ... }` | Rule (reversed) |
| `@prefix p: <url>` | Prefix declaration |
| `<< S P O >>` | Triple term (reified triple) |
| `(| Functor Args |)` | Formula term |
| `! :p` | Forward path |
| `^ :p` | Reverse path |
| `has` / `is` | Syntactic sugar (no-op) |
| `of` | Property inversion |
| `($ a b $)` | Set syntax |
| `log:onNegativeSurface` | BLOGIC negation |
| `GRAPH <g> { ... }` | Named graph (TriG) |

---

## Complete Example

```n3
@prefix : <http://my-ontology.org/> .
@prefix log: <http://www.w3.org/2000/10/swap/log#> .
@prefix e: <http://eulersharp.sourceforge.net/2003/03swap/log-rules#> .

# === DATA ===
:alice :parent :bob .
:bob   :parent :carol .
:bob   :sibling :dave .
:alice :age 65 .

# Negation: alice does NOT have a driver's license
_:neg log:onNegativeSurface { :alice :hasLicense true } .

# === RULES ===
{ ?X :parent ?Y } => { ?Y :child ?X } .
{ ?X :parent ?Y . ?Y :parent ?Z } => { ?X :grandparent ?Z } .
{ ?X :sibling ?Y . ?Y :parent ?Z } => { ?X :auntOrUncleOf ?Z } .

# Age-based rule with negation
{ ?X :age ?A . ?A e:greaterThan "60" .
  _:neg log:onNegativeSurface { ?X :hasLicense true } }
    => { ?X :needsRide true } .
```

Derived facts:

```n3
:bob :child :alice .
:carol :child :bob .
:alice :grandparent :carol .
:dave :auntOrUncleOf :carol .
:alice :needsRide true .
```
