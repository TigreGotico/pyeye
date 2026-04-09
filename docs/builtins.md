# Builtins Reference

pyeye ships with 280+ built-in functions organized into namespaces. Each builtin is a callable registered under a canonical IRI; in N3 you reference it by its prefixed name.

All examples below assume appropriate `@prefix` declarations at the top of the N3 document.

---

## Namespace prefixes

```n3
@prefix math:   <http://www.w3.org/2000/10/swap/math#> .
@prefix string: <http://www.w3.org/2000/10/swap/string#> .
@prefix list:   <http://www.w3.org/2000/10/swap/list#> .
@prefix log:    <http://www.w3.org/2000/10/swap/log#> .
@prefix time:   <http://www.w3.org/2000/10/swap/time#> .
@prefix crypto: <http://www.w3.org/2000/10/swap/crypto#> .
@prefix graph:  <http://www.w3.org/2000/10/swap/graph#> .
@prefix reason: <http://www.w3.org/2000/10/swap/reason#> .
@prefix e:      <http://eulersharp.sourceforge.net/2003/03swap/log-rules#> .
```

---

## How builtins work in rules

Builtins appear as the predicate of a triple in a rule body. There are two calling patterns:

### Filter builtins (no output variable)

The builtin tests a condition. If it returns `false` or `None`, the rule body fails for that binding.

```n3
# ?V must be greater than 10 for the rule to fire
{ ?Item :price ?V . ?V math:greaterThan 10 }
    => { ?Item :expensive true } .
```

### Computation builtins (output variable)

The builtin computes a result. The subject is a list of inputs; the object is the output variable.

```n3
# Multiply ?Price by 0.9, store result in ?Sale
{ ?Item :price ?Price . (?Price 0.9) math:product ?Sale }
    => { ?Item :salePrice ?Sale } .
```

### Why does my builtin return None?

If any *input* argument is still an unbound variable when the builtin is called, it returns `None` and the body pattern fails for that binding. Make sure all input variables are bound by earlier patterns in the rule body. The output variable (last argument) may be unbound — that is normal.

---

## math: — arithmetic and comparisons

Namespace: `http://www.w3.org/2000/10/swap/math#`

### Comparison filters (no output)

These return a boolean. When the boolean is `false`, the rule body fails.

| Builtin | Syntax | Description |
|---------|--------|-------------|
| `math:equalTo` | `?A math:equalTo ?B` | A == B (numeric) |
| `math:notEqualTo` | `?A math:notEqualTo ?B` | A != B (numeric) |
| `math:lessThan` | `?A math:lessThan ?B` | A < B |
| `math:greaterThan` | `?A math:greaterThan ?B` | A > B |
| `math:notLessThan` | `?A math:notLessThan ?B` | A >= B |
| `math:notGreaterThan` | `?A math:notGreaterThan ?B` | A <= B |

Examples:

```n3
{ ?P :age ?A . ?A math:greaterThan 17 } => { ?P :isAdult true } .
{ ?X :score ?S . ?S math:lessThan 60 } => { ?X :status :failing } .
```

### Arithmetic (two operands, one result)

These use the list subject syntax: `(?A ?B) math:op ?Result`.

| Builtin | Syntax | Result |
|---------|--------|--------|
| `math:plus` | `(?A ?B) math:plus ?C` | A + B |
| `math:minus` | `(?A ?B) math:minus ?C` | A - B |
| `math:times` | `(?A ?B) math:times ?C` | A * B |
| `math:divide` | `(?A ?B) math:divide ?C` | A / B |
| `math:difference` | `(?A ?B) math:difference ?C` | A - B (also supports ISO date subtraction → fractional years) |
| `math:quotient` | `(?A ?B) math:quotient ?C` | A / B (floating point) |
| `math:integerQuotient` | `(?A ?B) math:integerQuotient ?C` | A // B (integer division) |
| `math:remainder` | `(?A ?B) math:remainder ?C` | A % B |
| `math:exponentiation` | `(?A ?B) math:exponentiation ?C` | A ** B |
| `math:atan2` | `(?Y ?X) math:atan2 ?Angle` | atan2(Y, X) |
| `math:roundedTo` | `(?V ?N) math:roundedTo ?R` | round(V, N decimal places) |

### Arithmetic (variadic — list of any length)

These accept a list of any number of values.

| Builtin | Syntax | Result |
|---------|--------|--------|
| `math:sum` | `(?A ?B ?C ...) math:sum ?Total` | Sum of all elements |
| `math:product` | `(?A ?B ?C ...) math:product ?P` | Product of all elements |
| `math:max` | `(?A ?B ?C ...) math:max ?M` | Maximum |
| `math:min` | `(?A ?B ?C ...) math:min ?M` | Minimum |
| `math:avg` | `(?A ?B ?C ...) math:avg ?Mean` | Arithmetic mean |
| `math:std` | `(?A ?B ?C ...) math:std ?SD` | Sample standard deviation |
| `math:rms` | `(?A ?B ?C ...) math:rms ?R` | Root mean square |
| `math:memberCount` | `(?A ?B ...) math:memberCount ?N` | Count of arguments |
| `math:pcc` | `(?x1 ?y1 ?x2 ?y2 ...) math:pcc ?R` | Pearson correlation coefficient (interleaved x/y pairs) |

### Unary math

| Builtin | Syntax | Result |
|---------|--------|--------|
| `math:floor` | `?V math:floor ?N` | floor(V) → integer |
| `math:ceiling` | `?V math:ceiling ?N` | ceil(V) → integer |
| `math:rounded` | `?V math:rounded ?N` | round(V) → integer |
| `math:absoluteValue` | `?V math:absoluteValue ?A` | abs(V) |
| `math:negation` | `?V math:negation ?N` | -V |
| `math:logarithm` | `?V math:logarithm ?L` | ln(V) (natural log) |
| `math:sin` | `?V math:sin ?R` | sin(V) (radians) |
| `math:cos` | `?V math:cos ?R` | cos(V) (radians) |
| `math:tan` | `?V math:tan ?R` | tan(V) (radians) |
| `math:asin` | `?V math:asin ?R` | asin(V) |
| `math:acos` | `?V math:acos ?R` | acos(V) |
| `math:atan` | `?V math:atan ?R` | atan(V) |
| `math:sinh` | `?V math:sinh ?R` | sinh(V) |
| `math:cosh` | `?V math:cosh ?R` | cosh(V) |
| `math:tanh` | `?V math:tanh ?R` | tanh(V) |
| `math:acosh` | `?V math:acosh ?R` | acosh(V) |
| `math:asinh` | `?V math:asinh ?R` | asinh(V) |
| `math:atanh` | `?V math:atanh ?R` | atanh(V) |
| `math:degrees` | `?V math:degrees ?D` | radians → degrees |
| `math:radians` | `?V math:radians ?R` | degrees → radians |

### Date arithmetic

`math:difference` can subtract ISO 8601 date strings and returns fractional years:

```n3
# Age in years from birthdate
{ ?P :birthDate ?D . ("2024-01-15" ?D) math:difference ?Age }
    => { ?P :age ?Age } .
```

### Examples

```n3
# 10% discount
{ ?I :price ?P . (?P 0.9) math:product ?Sale }
    => { ?I :salePrice ?Sale } .

# VAT
{ ?I :price ?P . (?P 1.2) math:product ?WithVAT }
    => { ?I :priceWithVAT ?WithVAT } .

# Total of three components
{ ?O :partA ?A ; :partB ?B ; :partC ?C . (?A ?B ?C) math:sum ?Total }
    => { ?O :totalWeight ?Total } .

# Exponential growth
{ ?Pop :size ?N . (?N 1.05) math:product ?Next }
    => { ?Pop :nextYear ?Next } .
```

---

## string: — text manipulation

Namespace: `http://www.w3.org/2000/10/swap/string#`

### Equality and comparison

| Builtin | Syntax | Description |
|---------|--------|-------------|
| `string:equal` | `?A string:equal ?B` | A == B (string comparison) |
| `string:equalIgnoringCase` | `?A string:equalIgnoringCase ?B` | Case-insensitive equality |
| `string:notEqualIgnoringCase` | `?A string:notEqualIgnoringCase ?B` | Case-insensitive inequality |
| `string:lessThan` | `?A string:lessThan ?B` | Lexicographic A < B |
| `string:greaterThan` | `?A string:greaterThan ?B` | Lexicographic A > B |
| `string:notLessThan` | `?A string:notLessThan ?B` | A >= B (lexicographic) |
| `string:notGreaterThan` | `?A string:notGreaterThan ?B` | A <= B (lexicographic) |

### Search and matching

| Builtin | Syntax | Description |
|---------|--------|-------------|
| `string:contains` | `?Haystack string:contains ?Needle` | True if Needle is a substring of Haystack |
| `string:containsIgnoringCase` | `?H string:containsIgnoringCase ?N` | Case-insensitive substring check |
| `string:containsRoughly` | `?H string:containsRoughly ?N` | Approximate match (case-insensitive + small edit distance) |
| `string:notContainsRoughly` | `?H string:notContainsRoughly ?N` | Negation of containsRoughly |
| `string:startsWith` | `?S string:startsWith ?Prefix` | True if S starts with Prefix |
| `string:endsWith` | `?S string:endsWith ?Suffix` | True if S ends with Suffix |
| `string:matches` | `?S string:matches ?Pattern` | True if regex Pattern matches anywhere in S |
| `string:notMatches` | `?S string:notMatches ?Pattern` | Negation of matches |
| `string:scrape` | `(?S ?Pattern) string:scrape ?Match` | Return first regex match in S |
| `string:scrapeAll` | `(?S ?Pattern) string:scrapeAll ?Matches` | Return all matches joined by space |
| `string:search` | `(?S ?Pattern) string:search ?Match` | Alias for scrape |

### Transformation

| Builtin | Syntax | Description |
|---------|--------|-------------|
| `string:concatenation` | `(?A ?B ?C ...) string:concatenation ?R` | Concatenate all strings |
| `string:replace` | `(?S ?Pattern ?Repl) string:replace ?R` | Replace first regex match |
| `string:replaceAll` | `(?S ?Pattern ?Repl) string:replaceAll ?R` | Replace all regex matches |
| `string:substring` | `(?S ?Start ?Length) string:substring ?Sub` | Substring (0-based start, optional length) |
| `string:length` | `?S string:length ?N` | String length |
| `string:upperCase` | `?S string:upperCase ?U` | Convert to uppercase |
| `string:lowerCase` | `?S string:lowerCase ?L` | Convert to lowercase |
| `string:capitalize` | `?S string:capitalize ?C` | Capitalize first letter |
| `string:format` | `(?Fmt ?A ?B ...) string:format ?R` | printf-style formatting (`%s`, `%d`, etc.) |
| `string:join` | `(?Sep ?List) string:join ?R` | Join list elements with separator |
| `string:stringReverse` | `?S string:stringReverse ?R` | Reverse a string |
| `string:stringEscape` | `?S string:stringEscape ?E` | Unicode-escape a string |
| `string:charAt` | `(?S ?Index) string:charAt ?C` | Character at 0-based index |
| `string:setCharAt` | `(?S ?Index ?Char) string:setCharAt ?R` | Replace character at 0-based index |

### Examples

```n3
# Concatenate first and last name
{ ?P :first ?F . ?P :last ?L . (?F " " ?L) string:concatenation ?Full }
    => { ?P :fullName ?Full } .

# Match email pattern
{ ?U :email ?E . ?E string:matches "@example\\.com$" }
    => { ?U :isInternal true } .

# Normalize to uppercase
{ ?Code :raw ?R . ?R string:upperCase ?U }
    => { ?Code :normalized ?U } .

# Extract number from string "price:99"
{ ?I :rawData ?D . (?D "price:(\\d+)") string:scrape ?NumStr }
    => { ?I :priceStr ?NumStr } .
```

---

## list: — RDF list operations

Namespace: `http://www.w3.org/2000/10/swap/list#`

RDF lists are linked structures (like Python linked lists). The builtins work on the list head (the blank node returned by N3 list syntax).

### Membership

| Builtin | Syntax | Description |
|---------|--------|-------------|
| `list:in` | `?Item list:in ?List` | True if Item is in the list. **Both args must be bound.** |
| `list:member` | `?List list:member ?Item` | Alias with args reversed |
| `list:notMember` | `(?List ?Item) list:notMember true` | True if Item is NOT in the list |
| `list:isList` | `?L list:isList true` | True if ?L is a valid RDF list |

### Access

| Builtin | Syntax | Description |
|---------|--------|-------------|
| `list:length` | `?L list:length ?N` | Number of elements |
| `list:select` | `(?L ?Index) list:select ?Elem` | Element at 1-based index |
| `list:memberAt` | `(?L ?Index) list:memberAt ?Elem` | Element at 0-based index |
| `list:first` | `?L list:first ?Elem` | First element |
| `list:last` | `?L list:last ?Elem` | Last element |
| `list:car` | `?L list:car ?Elem` | First element (Lisp convention) |
| `list:cdr` | `?L list:cdr ?Rest` | Rest of list (Lisp convention) |
| `list:rest` | `?L list:rest ?Rest` | Rest of list |
| `list:firstRest` | `?L list:firstRest (?F ?R)` | Decompose into (first, rest) |

### Construction and transformation

| Builtin | Syntax | Description |
|---------|--------|-------------|
| `list:append` | `(?L1 ?L2 ...) list:append ?Combined` | Concatenate multiple lists |
| `list:reverse` | `?L list:reverse ?Rev` | Reverse a list |
| `list:sort` | `?L list:sort ?Sorted` | Lexicographic sort |
| `list:unique` | `?L list:unique ?Unique` | Remove duplicates (preserves order) |
| `list:removeDuplicates` | `?L list:removeDuplicates ?R` | Alias for unique |
| `list:removeAt` | `(?L ?Index) list:removeAt ?R` | Remove element at 0-based index |
| `list:remove` | `?L list:remove ?R` | Remove and return remaining store triples |
| `list:intersection` | `(?L1 ?L2) list:intersection ?R` | Elements common to both lists |
| `list:permutation` | `?L list:permutation ?P` | Random shuffle of elements |
| `list:map` | `?L list:map ?R` | Identity map (returns same list) |

### Set comparisons

| Builtin | Syntax | Description |
|---------|--------|-------------|
| `list:setEqualTo` | `(?L1 ?L2) list:setEqualTo true` | Same elements (ignoring order and duplicates) |
| `list:setNotEqualTo` | `(?L1 ?L2) list:setNotEqualTo true` | Not set-equal |
| `list:multisetEqualTo` | `(?L1 ?L2) list:multisetEqualTo true` | Same elements with same multiplicity |
| `list:multisetNotEqualTo` | `(?L1 ?L2) list:multisetNotEqualTo true` | Not multiset-equal |

### Iteration

| Builtin | Syntax | Description |
|---------|--------|-------------|
| `list:iterate` | `?L list:iterate ?Pair` | Yields `(index item)` pairs for each element. Returns `MultiResult` — the engine expands one binding per element. |

`list:iterate` example:

```n3
{ :colors :items ?L . ?L list:iterate ?Pair .
  ?Pair list:car ?Idx . ?Pair list:cdr ?ItemList .
  ?ItemList list:car ?Item }
    => { :colors :item ?Item . :colors :at ?Idx :item ?Item } .
```

### Important: `list:in` is a filter, not a generator

Both the item and the list must be bound before calling `list:in`. It checks membership, it does not enumerate elements:

```n3
# Wrong — ?Item is unbound, so list:in cannot enumerate
{ :myList list:in ?Item } => { :result :has ?Item } .

# Right — use list:iterate to enumerate
{ :myList a :Container . :myList :elements ?L .
  ?L list:iterate ?Pair .
  ?Pair list:car ?Idx . ?Pair list:cdr ?Rest . ?Rest list:car ?Item }
    => { :result :has ?Item } .

# Or: check membership when item is already bound
{ ?P :hobbies ?L . :reading list:in ?L }
    => { ?P :isReader true } .
```

### `list:select` is 1-based

```n3
{ ?L list:select 1 ?First }   # first element
{ ?L list:select 2 ?Second }  # second element
```

### Examples

```n3
# Count elements
{ ?G :members ?L . ?L list:length ?N }
    => { ?G :memberCount ?N } .

# Get first element
{ :queue :items ?L . ?L list:first ?Head }
    => { :queue :nextItem ?Head } .

# Membership check (both args bound)
{ ?U :role ?R . (:admin :superuser) list:in ?R }  # Wrong! list is bound, R is bound, but this is backward
```

Wait — `list:in` takes `(item list)` syntax: `item list:in list`. So:

```n3
# Check if user's role is in the allowed set
{ ?U :role ?R . ?R list:in (:admin :superuser) }
    => { ?U :hasAccess true } .

# Append two lists
{ :A :items ?L1 . :B :items ?L2 . (?L1 ?L2) list:append ?Combined }
    => { :merged :items ?Combined } .
```

---

## log: — logic and meta-operations

Namespace: `http://www.w3.org/2000/10/swap/log#`

The `log:` namespace contains logical operations, negation, aggregation, identifier generation, and meta-operations on the store.

### Equality

| Builtin | Syntax | Description |
|---------|--------|-------------|
| `log:equalTo` | `?A log:equalTo ?B` | True if A and B are the same term |
| `log:notEqualTo` | `?A log:notEqualTo ?B` | True if A and B are different terms |

Unlike `math:equalTo`, `log:equalTo` compares terms structurally — it works on IRIs, blank nodes, and literals, not just numbers.

```n3
# Ensure two items are different before comparing
{ ?A :fingerprint ?H . ?B :fingerprint ?H . ?A log:notEqualTo ?B }
    => { ?A :duplicateOf ?B } .
```

### `log:onNegativeSurface` — negation as failure

```n3
{ ?Svc a :Service .
  _:neg log:onNegativeSurface { ?Svc :timeout ?Any } }
    => { ?Svc :timeout :defaultTimeout } .
```

The rule fires only when `?Svc :timeout ?Any` cannot be matched. Each negative surface blank node must be unique within the rule. See [N3 Syntax — Negation](n3-syntax.md#negation) for details.

### `log:collectAllIn` — aggregate all matching values into a list

This is pyeye's primary aggregation builtin. It collects all values of a template expression for all bindings of a pattern, and returns them as an RDF list.

**Calling convention:**

```n3
(?Template { body pattern } ?OutputList) log:collectAllIn ?Scope .
```

- `?Template` — the term to collect (evaluated for each binding)
- `{ body pattern }` — a formula whose variables are matched against the store
- `?OutputList` — the resulting RDF list (output variable)
- `?Scope` — usually a variable or placeholder

Example — collect all salaries for a department:

```n3
{ ?Dept a :Department .
  (?Salary { ?E :dept ?Dept . ?E :salary ?Salary } ?SalList)
      log:collectAllIn ?Dept .
  ?SalList math:sum ?Total }
    => { ?Dept :totalSalary ?Total } .
```

Example — count members:

```n3
{ ?G a :Group .
  (1 { ?M :member ?G } ?Members) log:collectAllIn ?G .
  ?Members list:length ?N }
    => { ?G :memberCount ?N } .
```

### `log:skolem` — deterministic identifier generation

Generates a blank node (existential) from a list of key terms. The same inputs always produce the same blank node within a reasoning run.

```n3
{ ?P :worksAt ?C . (?P ?C) log:skolem ?Employment }
    => { ?Employment a :Employment ; :employee ?P ; :employer ?C } .
```

Use this to create synthetic identifiers from composite keys — for example, modelling a many-to-many relationship as a reified node.

**Do not use `log:uuid` in forward-chaining rule bodies.** UUID generation is non-deterministic; the engine would create a new UUID every pass and never reach fixpoint. Generate UUIDs in Python and inject them as facts before reasoning.

### `log:table` — memoization directive

```n3
[] log:table :reachable .
```

Declares `:reachable` as a tabled predicate for backward chaining. Prevents infinite loops in recursive backward rules. Has no effect on forward chaining.

### `log:forAllIn` — proof-by-cases

Checks that all possible cases (declared with `log:allPossibleCases`) are covered by rules. Advanced use — see EYE documentation for full semantics.

### `log:dtlit` — construct a typed literal

```n3
{ ?P :rawValue ?V .
  (?V "http://www.w3.org/2001/XMLSchema#integer") log:dtlit ?Typed }
    => { ?P :value ?Typed } .
```

The second argument is the datatype IRI as a string.

### `log:langlit` — construct a language-tagged literal

```n3
{ ?P :rawLabel ?L . (?L "en") log:langlit ?Tagged }
    => { ?P :label ?Tagged } .
```

### IRI manipulation

| Builtin | Syntax | Description |
|---------|--------|-------------|
| `log:localName` | `?IRI log:localName ?Local` | Fragment or last path segment of an IRI |
| `log:namespace` | `?IRI log:namespace ?NS` | Everything before the local name |
| `log:uri` | `?Node log:uri ?Str` | Serialize a node to its IRI string |
| `log:n3String` | `?Term log:n3String ?Str` | Serialize any term to N3 string |
| `log:localN3String` | `?Term log:localN3String ?Str` | N3 string using registered prefixes |
| `log:rawType` | `?Term log:rawType ?Type` | Term type IRI (log:URI, log:Literal, etc.) |

```n3
# Extract "Person" from <http://example.org/ns#Person>
{ :alice a ?Class . ?Class log:localName ?Name }
    => { :alice :className ?Name } .
```

### Type checking

| Builtin | Syntax | Description |
|---------|--------|-------------|
| `log:bound` | `?Term log:bound true` | True if ?Term is a ground (non-variable) term |
| `log:isBuiltin` | `?IRI log:isBuiltin true` | True if IRI is a registered builtin |
| `log:parsedAsN3` | `?Str log:parsedAsN3 true` | True if the string parses as valid N3 |

### Inference control

| Builtin | Syntax | Description |
|---------|--------|-------------|
| `log:implies` | `?Formula log:implies ?Head` | Check formula implies head |
| `log:impliesAnswer` | `?Pred log:impliesAnswer ?Head` | Mark predicate as answer producer |
| `log:isImpliedBy` | `?Conc log:isImpliedBy ?Prem` | Check conclusion is implied by premise |
| `log:impliedBy` | `?Conc log:impliedBy ?Prem` | Alias for isImpliedBy |
| `log:inferences` | `?X log:inferences ?N` | Count of derived triples so far |

### Graph operations

| Builtin | Syntax | Description |
|---------|--------|-------------|
| `log:includes` | `?Scope log:includes ?Pattern` | True if pattern is found in store |
| `log:notIncludes` | `?Scope log:notIncludes ?Pattern` | Negation of includes |
| `log:includesNotBind` | `?Scope log:includesNotBind ?Pattern` | Non-binding inclusion check |
| `log:content` | `?X log:content ?Triples` | Return all triples in the store |
| `log:query` | `?Formula log:query ?Results` | Sub-query against the store |
| `log:conjunction` | `?X log:conjunction ?Y` | Conjunction of formulas |
| `log:conclusion` | `?X log:conclusion ?Y` | Conclusion of a formula |
| `log:graph` | `?X log:graph ?Y` | Graph metadata |

### Miscellaneous

| Builtin | Syntax | Description |
|---------|--------|-------------|
| `log:uuid` | `?X log:uuid ?UUID` | Generate a UUID string. **Do not use in forward-chaining rule bodies.** |
| `log:outputString` | `?Str log:outputString ?Str` | Mark a string for output |
| `log:copy` | `?Term log:copy ?Copy` | Deep copy a term |
| `log:becomes` | `?Old log:becomes ?New` | Retract old triples, assert new |
| `log:version` | `?X log:version ?V` | Return pyeye version string |
| `log:trace` | `?X log:trace true` | Print args to stderr (debug) |
| `log:ask` | `?URL log:ask ?Body` | HTTP GET request, returns body (max 10KB, SSRF-protected) |
| `log:shell` | `?Cmd log:shell ?Out` | Run a safe allowlisted shell command, return stdout |
| `log:hasPrefix` | `(?URI ?Prefix) log:hasPrefix true` | True if URI starts with Prefix |
| `log:allPossibleCases` | `(?Var) log:allPossibleCases ?Cases` | Declare case list for proof-by-cases |
| `log:forAllIn` | `(?Conds) log:forAllIn ?Scope` | Check all cases are covered |
| `log:ifThenElseIn` | `(?Cond ?Then ?Else) log:ifThenElseIn ?Scope` | Conditional evaluation |
| `log:dcg` | `?Pred log:dcg ?Rule` | DCG rule validation |
| `log:repeat` | `?X log:repeat ?Y` | Always succeeds (repeat) |
| `log:satisfiable` | `?Formula log:satisfiable true` | Check satisfiability |
| `log:semantics` | `?X log:semantics true` | Semantic check (always true) |
| `log:triple` | `?X log:triple ?Info` | Triple metadata |
| `log:isomorphic` | `(?G1 ?G2) log:isomorphic true` | Check graph isomorphism |
| `log:notIsomorphic` | `(?G1 ?G2) log:notIsomorphic true` | Negation |
| `log:prefix` | `?X log:prefix ?P` | Prefix lookup |
| `log:phrase` | `?X log:phrase ?P` | DCG phrase |

---

## time: — date and time

Namespace: `http://www.w3.org/2000/10/swap/time#`

All time builtins work with ISO 8601 datetime strings like `"2024-01-15T10:30:00"`.

### Current time

| Builtin | Syntax | Description |
|---------|--------|-------------|
| `time:now` | `?X time:now ?Timestamp` | Current time as ISO 8601 string |
| `time:localTime` | `?X time:localTime ?Timestamp` | Current local time with timezone |
| `time:in-seconds` | `?X time:in-seconds ?Secs` | Current Unix timestamp (float) |

### Component extraction

All of these take a datetime string as subject and return an integer (or float for seconds).

| Builtin | Syntax | Description |
|---------|--------|-------------|
| `time:year` | `?DT time:year ?Y` | 4-digit year |
| `time:month` | `?DT time:month ?M` | Month (1–12) |
| `time:day` | `?DT time:day ?D` | Day of month (1–31) |
| `time:hour` | `?DT time:hour ?H` | Hour (0–23) |
| `time:minute` | `?DT time:minute ?Min` | Minute (0–59) |
| `time:second` | `?DT time:second ?S` | Second (float) |
| `time:hours` | `?DT time:hours ?H` | Alias for hour |
| `time:minutes` | `?DT time:minutes ?Min` | Alias for minute |
| `time:seconds` | `?DT time:seconds ?S` | Alias for second |
| `time:timeZone` | `?DT time:timeZone ?TZ` | Timezone string (e.g. `+02:00` or `Z`) |

### Examples

```n3
@prefix time: <http://www.w3.org/2000/10/swap/time#> .
@prefix math: <http://www.w3.org/2000/10/swap/math#> .

# Tag events with the current timestamp
{ ?Event a :IncomingEvent . _:t time:now ?TS }
    => { ?Event :receivedAt ?TS } .

# Extract year from a stored date
{ ?Doc :published ?DT . ?DT time:year ?Y }
    => { ?Doc :publishYear ?Y } .

# Check if event is in business hours
{ ?E :scheduledAt ?DT . ?DT time:hour ?H .
  ?H math:notLessThan 9 . ?H math:lessThan 17 }
    => { ?E :duringBusinessHours true } .
```

---

## crypto: — content hashing

Namespace: `http://www.w3.org/2000/10/swap/crypto#`

All hash builtins take a string subject and return a hex-encoded hash string as the object.

| Builtin | Syntax | Description |
|---------|--------|-------------|
| `crypto:md5` | `?Str crypto:md5 ?Hash` | MD5 hash (hex string) |
| `crypto:sha` | `?Str crypto:sha ?Hash` | SHA-1 hash (hex, deprecated) |
| `crypto:sha256` | `?Str crypto:sha256 ?Hash` | SHA-256 hash (hex) |
| `crypto:sha512` | `?Str crypto:sha512 ?Hash` | SHA-512 hash (hex) |

### Examples

```n3
@prefix crypto: <http://www.w3.org/2000/10/swap/crypto#> .

# Content fingerprint
{ ?Doc :content ?C . ?C crypto:sha256 ?Hash }
    => { ?Doc :fingerprint ?Hash } .

# Duplicate detection
{ ?A :fingerprint ?H . ?B :fingerprint ?H . ?A log:notEqualTo ?B }
    => { ?A :duplicateOf ?B } .

# MD5 for legacy systems
{ ?File :data ?D . ?D crypto:md5 ?Checksum }
    => { ?File :md5 ?Checksum } .
```

---

## graph: — named graph operations

Namespace: `http://www.w3.org/2000/10/swap/graph#`

These builtins operate on named graphs (TriG-style).

| Builtin | Syntax | Description |
|---------|--------|-------------|
| `graph:member` | `(?S ?P ?O) graph:member ?Graph` | True if triple (S P O) is in the graph |
| `graph:length` | `?Graph graph:length ?N` | Number of triples in the graph |
| `graph:difference` | `(?G1 ?G2) graph:difference ?Triples` | Triples in G1 but not G2 |
| `graph:intersection` | `(?G1 ?G2) graph:intersection ?Triples` | Triples in both G1 and G2 |
| `graph:union` | `(?G1 ?G2) graph:union ?Triples` | All triples from G1 and G2 |
| `graph:statement` | `(?S ?P ?O) graph:statement ?Triple` | Construct a triple term |
| `graph:renameBlanks` | `?G graph:renameBlanks ?G2` | Return graph with fresh blank node names |
| `graph:notMember` | `(?S ?P ?O) graph:notMember ?Graph` | Negation of member |
| `graph:list` | `?G graph:list ?List` | Return triples as a list |

---

## reason: — proof metadata

Namespace: `http://www.w3.org/2000/10/swap/reason#`

These builtins annotate proof traces. They are primarily used internally by pyeye's proof system and in conjunction with `explain=True`.

| Builtin | Description |
|---------|-------------|
| `reason:because` | Proof justification link |
| `reason:binding` | Variable binding in a proof step |
| `reason:boundTo` | Binding relationship |
| `reason:component` | Proof component |
| `reason:evidence` | Evidence for a conclusion |
| `reason:gives` | Rule application result |
| `reason:rule` | Rule reference |
| `reason:source` | Source of a fact or rule |
| `reason:variable` | Variable in a proof |

These are rarely used directly. Enable proof output with `explain=True` in `execute()` and inspect `result.explains`.

---

## e: — EYE extensions

Namespace: `http://eulersharp.sourceforge.net/2003/03swap/log-rules#`

The `e:` namespace contains extensions specific to the EYE reasoner that have no canonical W3C SWAP equivalent.

### Evaluation

| Builtin | Syntax | Description |
|---------|--------|-------------|
| `e:calculate` | `?Expr e:calculate ?Result` | Evaluate a safe Python expression (ast.literal_eval) |
| `e:derive` | `(?FnName ?A ?B ...) e:derive ?Result` | Call a registered Python function by name |
| `e:shell` | `?Cmd e:shell ?Output` | Run allowlisted shell command, return stdout |
| `e:exec` | `?Cmd e:exec ?ExitCode` | Run allowlisted shell command, return exit code |
| `e:fileString` | `?Path e:fileString ?Content` | Read file content as string |
| `e:closure` | `?GraphID e:closure ?GraphID` | Compute deductive closure of a named graph |
| `e:becomes` | `(?OldS ?OldP ?OldO ?NewS ?NewP ?NewO) e:becomes ?New` | Retract old, assert new |
| `e:transaction` | `?Triples e:transaction ?Result` | Atomic assert (simplified) |

`e:calculate` uses Python's `ast.literal_eval`, which only allows literals (strings, numbers, booleans, tuples, lists, dicts). No arbitrary code execution.

`e:derive` lets you call registered Python functions from N3:

```python
from pyeye.builtins import register_derive_function
from pyeye.term import Literal

def celsius_to_f(args, engine):
    c = float(args[0].value)
    return Literal(str(c * 9/5 + 32))

register_derive_function("c_to_f", celsius_to_f)
```

```n3
@prefix e: <http://eulersharp.sourceforge.net/2003/03swap/log-rules#> .

{ ?R :celsius ?C . ("c_to_f" ?C) e:derive ?F }
    => { ?R :fahrenheit ?F } .
```

### Math extensions

| Builtin | Description |
|---------|-------------|
| `e:avg` | Average (alias for math:avg) |
| `e:max` | Maximum (alias for math:max) |
| `e:min` | Minimum (alias for math:min) |
| `e:std` | Standard deviation |
| `e:rms` | Root mean square |
| `e:pcc` | Pearson correlation coefficient |
| `e:roc` | Receiver operating characteristic (simplified) |
| `e:binaryEntropy` | Binary entropy H(p) |
| `e:sigmoid` | Sigmoid function 1/(1+e^-x) |
| `e:epsilon` | Very small constant (1e-10) |
| `e:random` | Random float in [0,1] — **do not use in FC rules** |

### String extensions

| Builtin | Description |
|---------|-------------|
| `e:format` | printf-style format |
| `e:match` | Regex match → first match string |
| `e:stringEscape` | Unicode escape |
| `e:stringReverse` | Reverse string |
| `e:stringSplit` | Split string by regex pattern |
| `e:subsequence` | Check if one string contains another |
| `e:wwwFormEncode` | URL-encode a string |
| `e:csvTuple` | Join args as CSV string |
| `e:label` | Return label string |
| `e:notLabel` | True if labels are different |

### List extensions

| Builtin | Description |
|---------|-------------|
| `e:firstRest` | Alias for list:firstRest |
| `e:reverse` | Alias for list:reverse |
| `e:sort` | Alias for list:sort |
| `e:unique` | Alias for list:unique |
| `e:length` | List length |
| `e:cartesianProduct` | Cartesian product (simplified) |
| `e:multisetEqualTo` | Multiset equality |
| `e:multisetNotEqualTo` | Multiset inequality |
| `e:tripleList` | Triple as list |

### Logic/control

| Builtin | Description |
|---------|-------------|
| `e:T` | Always returns true |
| `e:F` | Always returns false (fails) |
| `e:true` | Always returns true |
| `e:fail` | Always returns None (fails) |
| `e:ignore` | Always returns true (ignore) |
| `e:boolean` | Parse "true"/"false" string to boolean |
| `e:conditional` | Conditional (simplified) |
| `e:biconditional` | Biconditional |
| `e:before` | True if first string is lexicographically before second |
| `e:whenGround` | Return arg if ground, else fail |
| `e:optional` | Return arg if ground |
| `e:call` | Alias for log:call |
| `e:finalize` | Finalization hook (always succeeds) |
| `e:tactic` | Set reasoning tactic (limited-answer N) |
| `e:prefix` | Register a prefix for output |
| `e:trace` | Print to stderr (debug) |
| `e:hmac-sha` | HMAC-SHA256 digest |
| `e:sha` | SHA-1 hash |
| `e:skolem` | Alias for log:skolem |

### Graph extensions

| Builtin | Description |
|---------|-------------|
| `e:graphCopy` | Copy a graph |
| `e:graphDifference` | Graph difference |
| `e:graphIntersection` | Graph intersection |
| `e:graphList` | Graph as list |
| `e:graphMember` | Check graph membership |
| `e:graphPair` | Graph pair |
| `e:compoundTerm` | Compound term |
| `e:tuple` | Tuple |
| `e:labelvars` | Label variables |
| `e:relabel` | Relabel |
| `e:transpose` | Transpose |
| `e:numeral` | Convert to numeric |
| `e:propertyChainExtension` | Property chain check |

---

## Special builtins in depth

### `log:onNegativeSurface` — negation as failure

```n3
{ ?X a :Config .
  _:neg log:onNegativeSurface { ?X :value ?Any } }
    => { ?X :hasMissingValue true } .
```

The enclosed formula must not be provable for the rule to fire. Each blank node label must be unique within a rule. Multiple negative surfaces in the same rule require different blank node labels:

```n3
{ ?Svc a :Service .
  _:n1 log:onNegativeSurface { ?Svc :host ?H } .
  _:n2 log:onNegativeSurface { ?Svc :port ?P } }
    => { ?Svc :misconfigured true } .
```

### `log:collectAllIn` — aggregation

Collects all values of a template for all bindings of a pattern. The result is an RDF list that can be passed to `list:length`, `math:sum`, etc.

```n3
# Count employees per department
{ ?Dept a :Department .
  (1 { ?E :dept ?Dept } ?Members) log:collectAllIn ?Dept .
  ?Members list:length ?N }
    => { ?Dept :headcount ?N } .

# Sum salaries
{ ?Dept a :Department .
  (?Sal { ?E :dept ?Dept . ?E :salary ?Sal } ?Sals) log:collectAllIn ?Dept .
  ?Sals math:sum ?Total }
    => { ?Dept :totalSalary ?Total } .
```

The pattern can reference variables bound earlier in the rule body:

```n3
# Group by company, count employees
{ ?Co a :Company .
  (1 { ?P :worksFor ?Co } ?Staff) log:collectAllIn ?Co .
  ?Staff list:length ?N }
    => { ?Co :staffSize ?N } .
```

### `log:skolem` — deterministic blank nodes

Creates a stable blank node from a composite key. The same combination of inputs always produces the same blank node identifier within a run. Use it to model many-to-many relationships as reified nodes:

```n3
# Create a stable Employment node for each (person, company) pair
{ ?P :worksAt ?C . (?P ?C) log:skolem ?Emp }
    => { ?Emp a :Employment ;
              :employee ?P ;
              :employer ?C } .
```

Without arguments, `log:skolem` generates a fresh unique blank node each time — do not use this in forward-chaining rules because the engine will create a new node every pass and never reach fixpoint.

### `log:table` — memoization

```n3
[] log:table :reachable .
{ ?X :reachable ?Y } <= { ?X :link ?Y } .
{ ?X :reachable ?Y } <= { ?X :reachable ?Z . ?Z :reachable ?Y } .
```

Marks `:reachable` for memoization during backward chaining. Without this, a recursive rule would loop indefinitely when the goal cannot be proved. `log:table` enables cycle detection by tracking which goals are currently on the call stack.

---

## Custom builtins

You can register your own Python functions as N3 builtins:

```python
from pyeye import execute
from pyeye.term import Variable, Literal, NamedNode
from pyeye.builtins import MultiResult

def celsius_to_fahrenheit(args, engine):
    # args[-1] is the output variable (appended by the engine)
    # args[:-1] are the input values
    if isinstance(args[0], Variable):
        return None   # input not bound yet — skip
    c = float(args[0].value)
    return Literal(str(c * 9/5 + 32))

result = execute(
    data_strings=["""
        @prefix : <http://example.org/> .
        @prefix fn: <http://example.org/fn#> .
        :reading1 :celsius "22" .
        :reading2 :celsius "37" .
    """],
    rule_strings=["""
        @prefix : <http://example.org/> .
        @prefix fn: <http://example.org/fn#> .
        { ?R :celsius ?C . ?C fn:celsiusToF ?F }
            => { ?R :fahrenheit ?F } .
    """],
    builtins={"http://example.org/fn#celsiusToF": celsius_to_fahrenheit},
)
```

### Builtin protocol

A builtin is a callable with signature:

```python
def my_builtin(args: list[Term], engine: EngineProto) -> Term | list[Triple] | MultiResult | None:
    ...
```

Return values:

| Return type | Effect |
|-------------|--------|
| `Term` | Function result — bound to the output variable |
| `list[Triple]` | Predicate result — each triple is added to the store |
| `MultiResult(results)` | Generative — the engine creates one binding per element |
| `None` | Fail — the body pattern does not match for this binding |

The engine appends the object of the builtin triple as the last element of `args`. If it is still a `Variable`, it is the unbound output slot. You should return a value to bind it, not `None`.

To check whether inputs are ground before computing:

```python
from pyeye.term import Variable

def my_fn(args, engine):
    # Check all input args (everything except the last output variable)
    input_args = args[:-1] if len(args) >= 2 and isinstance(args[-1], Variable) else args
    if any(isinstance(a, Variable) for a in input_args):
        return None  # unbound inputs — skip
    # ... compute result
```

### `MultiResult` — generating multiple bindings

When a builtin should yield multiple results (like a SQL `IN` clause), return `MultiResult`:

```python
from pyeye.builtins import MultiResult
from pyeye.term import Literal

def generate_options(args, engine):
    # Yields multiple values for the output variable
    options = ["option_a", "option_b", "option_c"]
    return MultiResult([Literal(o) for o in options])
```

The engine will fork the current binding once per element in `results`.
