# N3 Syntax Guide (Phase 1)

**Source:** `Parser` — `pyeye/parser.py:136`

This document describes the N3 syntax supported in Phase 1. Anything not listed here is deferred to Phase 2.

---

## Rules

### Forward Implication (`=>`)

```n3
{ ?X :parent ?Y } => { ?Y :child ?X } .
```

If the body (left of `=>`) matches, the head (right) is derived.

Source: `Parser._do_formula_top` — `pyeye/parser.py:223`

### Backward Implication (`<=`)

```n3
{ ?Y :child ?X } <= { ?X :parent ?Y } .
```

Equivalent to `=>` but with body and head reversed. This is syntactic sugar — the parser swaps them internally.

Source: `Parser._do_formula_top` — `pyeye/parser.py:230`

### Standalone Formula (data)

```n3
{ :alice :name "Alice" } .
```

A formula without `=>` or `<=` is treated as data triples.

Source: `Parser._do_formula_top` — `pyeye/parser.py:233`

---

## Terms

### Full IRI

```n3
<http://example.org/person/alice>
```

Source: `Parser._item` — `pyeye/parser.py:285`

### Prefixed Name

```n3
@prefix ex: <http://example.org/> .
ex:alice          # expands to <http://example.org/alice>
```

Source: `Parser._item` — `pyeye/parser.py:290`

### Default Prefix (empty prefix)

```n3
@prefix : <http://example.org/> .
:alice            # expands to <http://example.org/alice>
```

Source: `Parser._do_prefix` — `pyeye/parser.py:191`

### Variable

```n3
?X
?name
?some_variable
```

Variable names start with `?` followed by `[A-Za-z_]\w*`.

Source: `Parser._item` — `pyeye/parser.py:297`

### Blank Node (empty)

```n3
[]
```

Generates a fresh existential identifier (`_b1`, `_b2`, ...).

Source: `Parser._bnode` — `pyeye/parser.py:315`

### Blank Node (with content)

```n3
[ :name "Alice" ; :age 30 ]
```

The blank node becomes the subject of the enclosed triples.

Source: `Parser._bnode` — `pyeye/parser.py:315`

### Named Blank Node

```n3
_:myNode
```

Source: `Parser._item` — `pyeye/parser.py:300`

### RDF List

```n3
(:apple :banana :cherry)
```

Expands into `rdf:first`/`rdf:rest` linked list structure with anonymous blank nodes.

Source: `Parser._rdf_list` — `pyeye/parser.py:335`

### Empty List

```n3
()
```

Expands to the `rdf:nil` marker (`_:nil`).

Source: `Parser._rdf_list` — `pyeye/parser.py:339`

---

## Literals

### Plain String

```n3
"hello"
```

Source: `Parser._literal` — `pyeye/parser.py:358`

### Long String

```n3
'''multi
line
text'''
```

```n3
"""also multi
line"""
```

Source: `Parser._literal` — `pyeye/parser.py:358` (handles `LONGSTR` tokens)

### Datatype Literal

```n3
"42"^^<http://www.w3.org/2001/XMLSchema#integer>
```

Source: `Parser._literal` — `pyeye/parser.py:367`

### Language-Tagged Literal

```n3
"bonjour"@fr
```

Source: `Parser._literal` — `pyeye/parser.py:373`

### Bare Number

```n3
42       # typed as xsd:integer
3.14     # typed as xsd:double
1e10     # typed as xsd:double
```

Source: `Parser._literal` — `pyeye/parser.py:379`

---

## Punctuation

### `a` shorthand for `rdf:type`

```n3
?X a :Person .
```

Equivalent to `?X <http://www.w3.org/1999/02/22-rdf-syntax-ns#type> :Person .`

Source: `Parser._verb` — `pyeye/parser.py:256`

### Semicolon (`;`) — same subject, multiple predicates

```n3
:alice :name "Alice" ; :age 30 .
```

Equivalent to:
```n3
:alice :name "Alice" .
:alice :age 30 .
```

Source: `Parser._verb_obj_list` — `pyeye/parser.py:244`

### Comma (`,`) — same subject+predicate, multiple objects

```n3
:alice :knows :bob, :carol, :dave .
```

Equivalent to:
```n3
:alice :knows :bob .
:alice :knows :carol .
:alice :knows :dave .
```

Source: `Parser._obj_list` — `pyeye/parser.py:262`

### Period (`.`) — statement terminator

```n3
:a :p :b .
:c :q :d .
```

---

## Directives

### `@prefix`

```n3
@prefix ex: <http://example.org/> .
@prefix : <http://default.org/> .
```

Source: `Parser._do_prefix` — `pyeye/parser.py:187`

### `@base`

```n3
@base <http://example.org/> .
```

Sets the base URI for prefix expansion when no prefix matches.

Source: `Parser._do_base` — `pyeye/parser.py:201`

### `@forSome`

```n3
@forSome ?X .
```

Existential quantification — declares `?X` as existentially quantified within the containing formula. Phase 1: parsed and consumed, no semantic effect on reasoning.

Source: `Parser._do_quantifier` — `pyeye/parser.py:206`

### `@forAll`

```n3
@forAll ?X .
```

Universal quantification — declares `?X` as universally quantified. Phase 1: parsed and consumed, no semantic effect.

Source: `Parser._do_quantifier` — `pyeye/parser.py:206`

---

## Comments

```n3
# This is a comment
:a :p :b .  # inline comment
```

Source: tokenizer `HASH` pattern — `pyeye/parser.py:122`

---

## Not Supported in Phase 1

The following N3 features are deferred to Phase 2:

| Feature | Syntax | Status |
| :--- | :--- | :--- |
| Triple terms | `<< :a :p :b >>` | ❌ Phase 2 |
| Formula terms | `(:pred :a :b)` | ❌ Phase 2 |
| `is` sugar | `:Bob :child of :Alice` | ❌ Phase 2 |
| `has` sugar | `:Alice :parent has :Bob` | ❌ Phase 2 |
| `of` (inverse) | `:parent of :Alice` | ❌ Phase 2 |
| `^` reverse path | `:child^ :Alice` | ❌ Phase 2 |
| BLOGIC surfaces | `log:onNegativeSurface` | ❌ Phase 2 |
| Set syntax | `($ :a :b $)` | ❌ Phase 2 |
| `!` forward path (chained) | `:a ! :p ! :q` | Partial (single step works) |
| `<-` predicate inversion | `:Bob <- :child :Alice` | Partial (single step works) |
