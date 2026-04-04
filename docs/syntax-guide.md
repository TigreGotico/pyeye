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

## Comments

```n3
# This is a full-line comment
:alice :name "Alice" .  # This is an inline comment
```

Comments are ignored by the engine. Use them to explain your rules to future readers (including yourself).

---

## Complete Example

Here's a complete N3 file with data and rules:

```n3
@prefix : <http://my-ontology.org/> .

# === DATA ===
:alice :parent :bob .
:bob :parent :carol .
:bob :sibling :dave .
:alice :age 65 .

# === RULES ===

# Rule 1: parent → child
{ ?X :parent ?Y } => { ?Y :child ?X } .

# Rule 2: parent + parent → grandparent
{ ?X :parent ?Y . ?Y :parent ?Z } => { ?X :grandparent ?Z } .

# Rule 3: sibling of parent → aunt/uncle
{ ?X :sibling ?Y . ?Y :parent ?Z } => { ?X :auntOrUncleOf ?Z } .

# Rule 4: age-based rule
{ ?X :age ?A . ?A <http://www.w3.org/2000/10/swap/math#greaterThan> "60"^^<http://www.w3.org/2001/XMLSchema#integer> }
    => { ?X :senior true } .
```

After running this, the engine derives:

```
:bob :child :alice .
:carol :child :bob .
:alice :grandparent :carol .
:dave :auntOrUncleOf :carol .
:alice :senior true .
```

---

## What's NOT Supported (Yet)

Phase 1 covers the essentials above. The following N3 features are planned for Phase 2:

| Feature | Example | Status |
| :--- | :--- | :--- |
| Triple terms | `<< :a :p :b >> :wasSaidBy :alice .` | ❌ Phase 2 |
| Formula as value | `:rule :body (:pred :a :b) .` | ❌ Phase 2 |
| `is` sugar | `:Bob :child of :Alice .` | ❌ Phase 2 |
| `has` sugar | `:Alice :parent has :Bob .` | ❌ Phase 2 |
| Reverse path | `:child^ :Alice` | ❌ Phase 2 |
| BLOGIC negation | `log:onNegativeSurface { ... }` | ❌ Phase 2 |
| Set syntax | `($ :a :b $)` | ❌ Phase 2 |

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
| `[]` | Anonymous thing | `:alice :knows [] .` |
| `(a b c)` | Ordered list | `:favorites (:a :b :c) .` |
| `a` | Type declaration | `:alice a :Person .` |
| `;` | Same subject | `:alice :age 30 ; :name "A" .` |
| `,` | Same subject+predicate | `:alice :knows :b, :c .` |
| `.` | End of statement | `:a :p :b .` |
| `# ...` | Comment | `# this is a comment` |
| `{ ... } => { ... }` | Rule | `{ ?X :p ?Y } => { ?Y :q ?X } .` |
| `@prefix p: <url>` | Prefix shortcut | `@prefix : <http://x.org/> .` |

---

## Source Code References

All parsing is implemented in `Parser` — `pyeye/parser.py:136`. Specific methods:

| Feature | Method | Source |
| :--- | :--- | :--- |
| Tokenizer | `tokenize()` | `parser.py:93` |
| Prefix directive | `Parser._do_prefix()` | `parser.py:187` |
| Base directive | `Parser._do_base()` | `parser.py:201` |
| Quantifiers | `Parser._do_quantifier()` | `parser.py:206` |
| Rules | `Parser._do_formula_top()` | `parser.py:223` |
| Triple patterns | `Parser._verb_obj_list()` | `parser.py:244` |
| `a` shorthand | `Parser._verb()` | `parser.py:256` |
| Comma lists | `Parser._obj_list()` | `parser.py:262` |
| Variables, IRIs, literals | `Parser._item()` | `parser.py:285` |
| Blank nodes | `Parser._bnode()` | `parser.py:315` |
| RDF lists | `Parser._rdf_list()` | `parser.py:335` |
| Literals | `Parser._literal()` | `parser.py:358` |
