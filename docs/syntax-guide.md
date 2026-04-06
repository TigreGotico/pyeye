# N3 Syntax Guide

This document explains the **N3 (Notation 3)** text format that pyeye uses to write facts and rules. No prior knowledge of RDF, logic, or Semantic Web technologies is assumed.

---

## The Absolute Basics

### A single fact

```n3
:alice :knows :bob .
```

This is one **fact** (also called a **triple** because it has three parts):

| Part | Name | Meaning |
| :--- | :--- | :--- |
| `:alice` | **Subject** | Who the fact is about |
| `:knows` | **Predicate** | What the fact says about the subject |
| `:bob` | **Object** | The value or target of the fact |

The `.` at the end is like a period — it ends the statement.

### Defining shortcuts with `@prefix`

Writing full web addresses everywhere is tedious:

```n3
<http://example.org/people/alice> <http://example.org/relations/knows> <http://example.org/people/bob> .
```

Instead, define a **prefix** — a shortcut that expands to a full address:

```n3
@prefix : <http://example.org/> .

:alice :knows :bob .
# Expands to: <http://example.org/alice> <http://example.org/knows> <http://example.org/bob> .
```

You can have multiple prefixes:

```n3
@prefix person: <http://example.org/people/> .
@prefix rel: <http://example.org/relations/> .

person:alice rel:knows person:bob .
```

### Writing multiple facts about the same subject

Instead of repeating the subject:

```n3
:alice :age 30 .
:alice :name "Alice" .
:alice :city "Lisbon" .
```

Use a semicolon (`;`) to say "same subject, different predicate":

```n3
:alice :age 30 ;
       :name "Alice" ;
       :city "Lisbon" .
```

### Writing multiple facts about the same subject and predicate

Instead of repeating both:

```n3
:alice :knows :bob .
:alice :knows :carol .
:alice :knows :dave .
```

Use a comma (`,`) to say "same subject and predicate, different objects":

```n3
:alice :knows :bob, :carol, :dave .
```

---

## Rules: Making the Engine Think

### Your first rule

```n3
{ ?X :parent ?Y } => { ?Y :child ?X } .
```

Read this aloud: *"When you find that X is Y's parent, also record that Y is X's child."*

- The part in `{ }` before `=>` is the **body** — what pattern to look for.
- The part in `{ }` after `=>` is the **head** — what new fact to create.
- `?X` and `?Y` are **variables** — they match any value.

**How it works:** The engine scans all facts looking for a match. When it finds `:alice :parent :bob`, it sets `?X = :alice` and `?Y = :bob`, then creates the new fact `:bob :child :alice`.

### Rules with multiple conditions

```n3
{ ?X :parent ?Y . ?Y :parent ?Z } => { ?X :grandparent ?Z } .
```

The `.` between body patterns means **"both must be true."**

When the engine finds:
- `:alice :parent :bob` (matches `?X :parent ?Y` with X=alice, Y=bob)
- `:bob :parent :carol` (matches `?Y :parent ?Z` with Y=bob, Z=carol)

It derives: `:alice :grandparent :carol`

The shared variable `?Y` acts as a **bridge** — it must match the same value in both patterns.

### Reversed rules (`<=`)

```n3
{ ?Y :child ?X } <= { ?X :parent ?Y } .
```

This is exactly the same as `{ ?X :parent ?Y } => { ?Y :child ?X } .` — just written in reverse. The `<=` operator swaps the body and head automatically. Most people use `=>` because it reads more naturally ("if this, then that").

---

## Variables

Variables are placeholders written as `?` followed by a name:

```n3
?X
?Person
?some_variable
?camelCase
```

- Variable names are **case-sensitive**: `?X` ≠ `?x`
- Names can contain letters, numbers, and underscores
- The same variable name in a rule body means "must be the same value"
- Variables in the head get their values from the body match

### Example: variable scoping

```n3
{ ?Person :name ?Name . ?Person :age ?Age } => { ?Person :description ?Desc } .
```

Here `?Person` appears three times — it must be the same person in all three. `?Name`, `?Age`, and `?Desc` are different variables that each get their own value.

---

## Literals: Writing Values

### Plain text

```n3
:alice :name "Alice" .
```

Strings are written in double quotes.

### Numbers

```n3
:alice :age 30 .
:water :boilsAt 100 .
:pi :value 3.14 .
:avogadro :value 6.022e23 .
```

Whole numbers are typed as integers. Decimals and scientific notation are typed as doubles.

### Text with a language tag

```n3
:greeting :text "Hello"@en .
:greeting :text "Olá"@pt .
```

The `@en` or `@pt` tells you what language the text is in. Useful for multilingual applications.

### Text with a specific type

```n3
:event :date "2025-03-15"^^<http://www.w3.org/2001/XMLSchema#date> .
```

The `^^` followed by a type IRI says "this string should be interpreted as this specific type."

### Multi-line text

```n3
:book :description '''This is a
multi-line
description.''' .
```

Use triple quotes (`'''` or `"""`) for text spanning multiple lines.

---

## Blank Nodes: Anonymous Things

Sometimes you need to refer to something but you don't have a name for it.

### Empty blank node

```n3
:alice :knows [] .
```

`[]` means "someone" — an unnamed person. The engine creates a unique internal ID for it.

### Blank node with properties

```n3
:alice :livesIn [ :city "Lisbon" ; :country "Portugal" ] .
```

This says: Alice lives in some unnamed place, and that place is in Lisbon, Portugal.

**Why use this?** When you know facts about a thing but the thing itself doesn't need a name. Like saying "Alice lives in a city called Lisbon in a country called Portugal" without naming the city entity separately.

---

## Lists

```n3
:alice :favorites (:pizza :sushi :tacos) .
```

The parentheses create an ordered list. Behind the scenes, this expands into a chain of linked facts:

```
_:list1 :first :pizza ; :rest _:list2 .
_:list2 :first :sushi ; :rest _:list3 .
_:list3 :first :tacos ; :rest _:nil .
```

You usually don't need to think about this — just use `(...)` and the engine handles the rest.

### Empty list

```n3
:bob :favorites () .
```

An empty pair of parentheses means "nothing" — Bob has no favorites.

---

## The `a` Shorthand

```n3
:alice a :Person .
```

The letter `a` is shorthand for "is a type of" (technically, `rdf:type`). This is equivalent to:

```n3
:alice :type :Person .
```

You'll see `a` a lot in N3 examples because it's the standard way to declare types.

---

## Phase 2 Extended Syntax

### Triple Terms: Reifying a Triple

```n3
<< :alice :knows :bob >> :wasSaidBy :charlie .
```

The `<< S P O >>` syntax lets you treat a triple as a **value** that can be the subject or object of another triple. This is N3's way of talking about statements themselves.

**Source:** `Parser._triple_term` — `pyeye/parser.py`

### Formula Terms: A Formula as a Value

```n3
:alice :thinks (| :says :alice "hello" |) .
```

The `(| Functor Args |)` syntax lets you embed a formula inside another triple. The functor is the predicate name, and the args are the arguments.

**Source:** `Parser._formula_term` — `pyeye/parser.py`

### `has` Sugar: Skipping the Object Position

```n3
:Alice :parent has :Bob .
```

This is equivalent to `:Alice :parent :Bob .`. The `has` keyword is just syntactic sugar — it's skipped during parsing.

**Source:** `Parser._verb_obj_list` — `pyeye/parser.py:270`

### `is` Sugar: Same as `has`

```n3
:Alice :name is "Alice" .
```

Equivalent to `:Alice :name "Alice" .`. Like `has`, the `is` keyword is skipped.

### `of` Sugar: Property Inversion

```n3
:Bob :child of :Alice .
```

This **swaps** the subject and object: it's equivalent to `:Alice :child :Bob .`. The `of` keyword means "the predicate goes the other way."

With semicolons:
```n3
:Bob :child of :Alice ; :sibling of :Carol .
```

Expands to:
```n3
:Alice :child :Bob .
:Carol :sibling :Bob .
```

**Source:** `Parser._verb_obj_list` — `pyeye/parser.py:270`

### Path Expressions: Chained Predicates

```n3
:a ! :p ! :q :target .
```

The `!` operator chains predicates together. This means "follow :p, then follow :q." The reverse path operator `^` goes the other direction:

```n3
:a ^ :parent :target .
```

This means "find who is the parent of :a" — equivalent to `?X :parent :a`.

Chained paths:
```n3
:a ! :parent ! :sibling :target .
```

Meaning: find :a's parent's sibling.

**Source:** `Parser._path_expression` — `pyeye/parser.py`

### BLOGIC Negative Surfaces

```n3
@prefix log: <http://www.w3.org/2000/10/swap/log#> .

:S log:onNegativeSurface { :a :p :b } .
```

A negative surface says: "this rule body should only match if the enclosed formula does **NOT** match the store." If `:a :p :b` exists in the store, the negation blocks the rule. If it doesn't exist, the rule proceeds.

**Example:**
```n3
@prefix e: <http://eulersharp.sourceforge.net/2003/03swap/log-rules#> .
{ ?Person :age ?A . ?A e:greaterThan "17" .
  _:neg log:onNegativeSurface { ?Person :hasLicense true } }
    => { ?Person :cannotDrive true } .
```

This says: if someone is over 17 and does NOT have a license, they cannot drive.

**Source:** `Engine._match_triples_iter` — `pyeye/engine.py:194` (negation check in body matching)

### Set Syntax

```n3
:Alice :likes ($ :pizza :sushi :tacos $) .
```

Sets are like lists but unordered. In Phase 2, sets are treated like lists (converted to `rdf:first`/`rdf:rest` chains). Full set semantics (unordered membership testing) is planned for Phase 2b.

**Source:** `Parser._set_term` — `pyeye/parser.py`

### TriG Named Graphs

```n3
@prefix : <http://ex.org/> .

GRAPH :g1 {
    :alice :name "Alice" .
    :bob :name "Bob" .
}

GRAPH :g2 {
    :carol :name "Carol" .
}
```

The `GRAPH <id> { ... }` syntax stores triples in a named graph. You can query specific graphs:

```n3
{ ?S ?P ?O } => { ... } .  # queries default graph
{ GRAPH ?G { ?S ?P ?O } } => { ... } .  # queries named graph
```

**Source:** `Parser._do_graph` — `pyeye/parser.py:241`, `TripleStore.match(graph=...)` — `pyeye/store.py:100`

---

## Comments

```n3
# This is a full-line comment
:alice :name "Alice" .  # This is an inline comment
```

Comments are ignored by the engine. Use them to explain your rules to future readers (including yourself).

---

## Complete Example

Here's a complete N3 file with data and rules, using Phase 2 features:

```n3
@prefix : <http://my-ontology.org/> .
@prefix log: <http://www.w3.org/2000/10/swap/log#> .
@prefix e: <http://eulersharp.sourceforge.net/2003/03swap/log-rules#> .

# === DATA ===
:alice :parent :bob .
:bob :parent :carol .
:bob :sibling :dave .
:alice :age 65 .

# Negation: :alice does NOT have a driver's license
_:neg log:onNegativeSurface { :alice :hasLicense true } .

# === RULES ===

# Rule 1: parent → child
{ ?X :parent ?Y } => { ?Y :child ?X } .

# Rule 2: parent + parent → grandparent
{ ?X :parent ?Y . ?Y :parent ?Z } => { ?X :grandparent ?Z } .

# Rule 3: sibling of parent → aunt/uncle
{ ?X :sibling ?Y . ?Y :parent ?Z } => { ?X :auntOrUncleOf ?Z } .

# Rule 4: age-based rule with negation
{ ?X :age ?A . ?A e:greaterThan "60" .
  _:neg log:onNegativeSurface { ?X :hasLicense true } }
    => { ?X :needsRide true } .
```

After running this, the engine derives:

```
:bob :child :alice .
:carol :child :bob .
:alice :grandparent :carol .
:dave :auntOrUncleOf :carol .
:alice :needsRide true .  # Because age > 60 AND no license (negation passes)
```

---

## Quick Reference Card

| Syntax | Meaning | Example |
| :--- | :--- | :--- |
| `:foo` | Prefixed name | `:alice :knows :bob .` |
| `<http://...>` | Full IRI | `<http://x.org/a> :p <http://x.org/b> .` |
| `?X` | Variable | `{ ?X :p ?Y } => { ... }` |
| `"text"` | String literal | `:alice :name "Alice" .` |
| `42` | Integer | `:alice :age 42 .` |
| `3.14` | Decimal | `:pi :value 3.14 .` |
| `"text"@en` | Language-tagged | `:greeting :text "Hi"@en .` |
| `"text"^^<type>` | Datatype literal | `:date :value "2025-03-15"^^xsd:date .` |
| `[]` | Anonymous thing | `:alice :knows [] .` |
| `_:name` | Named blank node | `_:b1 :p :o .` |
| `(a b c)` | Ordered list | `:favorites (:a :b :c) .` |
| `a` | Type declaration | `:alice a :Person .` |
| `;` | Same subject | `:alice :age 30 ; :name "A" .` |
| `,` | Same subject+predicate | `:alice :knows :b, :c .` |
| `.` | End of statement | `:a :p :b .` |
| `# ...` | Comment | `# this is a comment` |
| `{ ... } => { ... }` | Rule | `{ ?X :p ?Y } => { ?Y :q ?X } .` |
| `{ ... } <= { ... }` | Reversed rule | `{ ?Y :q ?X } <= { ?X :p ?Y } .` |
| `@prefix p: <url>` | Prefix shortcut | `@prefix : <http://x.org/> .` |
| `<< S P O >>` | Triple term (Phase 2) | `<< :a :p :b >> :saidBy :c .` |
| `(| Functor Args |)` | Formula term (Phase 2) | `:a :thinks (| :says :a "hi" |) .` |
| `! :p` | Forward path (Phase 2) | `:a ! :p :target .` |
| `^ :p` | Reverse path (Phase 2) | `:a ^ :p :target .` |
| `has` | Sugar (Phase 2) | `:a :p has :b .` |
| `is` | Sugar (Phase 2) | `:a :p is :b .` |
| `of` | Property inversion (Phase 2) | `:b :p of :a .` |
| `($ a b $)` | Set (Phase 2) | `:a :likes ($ :x :y $) .` |
| `log:onNegativeSurface` | BLOGIC negation (Phase 2) | `_:n log:onNegativeSurface { ... } .` |
| `GRAPH <g> { ... }` | Named graph (Phase 2) | `GRAPH :g1 { :a :p :b . }` |

---

## Source Code References

All parsing is implemented in `Parser` — `pyeye/parser.py:168`. Specific methods:

| Feature | Method | Source |
| :--- | :--- | :--- |
| Tokenizer | `tokenize()` | `parser.py:102` |
| Prefix directive | `Parser._do_prefix()` | `parser.py:203` |
| Base directive | `Parser._do_base()` | `parser.py:221` |
| Quantifiers | `Parser._do_quantifier()` | `parser.py:226` |
| TriG graphs | `Parser._do_graph()` | `parser.py:241` |
| Rules | `Parser._do_formula_top()` | `parser.py:257` |
| Triple patterns | `Parser._verb_obj_list()` | `parser.py:270` |
| `a` shorthand | `Parser._verb()` | `parser.py:299` |
| Comma lists | `Parser._obj_list()` | `parser.py:304` |
| Variables, IRIs, literals | `Parser._item()` | `parser.py:311` |
| Triple terms | `Parser._triple_term()` | `parser.py:511` |
| Formula terms | `Parser._formula_term()` | `parser.py:521` |
| Path expressions | `Parser._path_expression()` | `parser.py:567` |
| Set syntax | `Parser._set_term()` | `parser.py:534` |
| Blank nodes | `Parser._bnode()` | `parser.py:460` |
| RDF lists | `Parser._rdf_list()` | `parser.py:478` |
| Literals | `Parser._literal()` | `parser.py:494` |
| Negative surfaces | Detected in engine during body matching | `engine.py:194` |
