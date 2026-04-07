# Builtins Reference

**Source:** `BUILTIN_REGISTRY` — `pyeye/builtins.py`

pyeye's built-in functions are registered under **canonical W3C swap namespaces** as the primary keys.

### Canonical W3C `swap:` namespaces

```n3
@prefix math:   <http://www.w3.org/2000/10/swap/math#> .
@prefix string: <http://www.w3.org/2000/10/swap/string#> .
@prefix list:   <http://www.w3.org/2000/10/swap/list#> .
@prefix log:    <http://www.w3.org/2000/10/swap/log#> .
@prefix crypto: <http://www.w3.org/2000/10/swap/crypto#> .
@prefix graph:  <http://www.w3.org/2000/10/swap/graph#> .
@prefix time:   <http://www.w3.org/2000/10/swap/time#> .
@prefix reason: <http://www.w3.org/2000/10/swap/reason#> .
```

### `e:` namespace (eulersharp — EYE-specific builtins only)

```
@prefix e: <http://eulersharp.sourceforge.net/2003/03swap/log-rules#> .
```

The `e:` namespace is retained **only** for builtins that are genuinely unique to EYE/eyeling and have no canonical swap equivalent (e.g. `e:calculate`, `e:tactic`, `e:sigmoid`, `e:binaryEntropy`, `e:derive`, `e:becomes`, `e:closure`, etc.).

All builtins that have a canonical swap equivalent are registered **only** under the canonical name: `math:greaterThan`, `log:skolem`, `string:contains`, `list:in`, etc.

---

## How Builtins Work

Builtins appear as the **predicate** in a triple pattern inside a rule body:

```n3
{ SUBJECT math:builtinName OBJECT } => { HEAD } .
```

The **subject** provides input(s), the **object** either receives a result or acts as a comparison target.

### Pattern: filter (boolean test)

```n3
{ ?Price math:greaterThan "30" } => { :item :expensive true } .
```

If `?Price` is bound and greater than 30, the body matches and the head is derived.

### Pattern: compute (result bound to variable)

```n3
{ ?A math:plus ?B ?Sum } => { :result :total ?Sum } .
```

`?Sum` receives the computed value (A + B). The head uses it.

### Unground arguments

If any argument is an unbound variable when the engine evaluates the builtin, evaluation is **skipped** — the engine moves on and may retry later when variables are grounded.

### Builtins in body only

Builtins appear in the **body** of a rule (before `=>`). They evaluate conditions or compute values for use in the head. They do not create facts by themselves.

---

## Math Builtins

**44 functions** for numeric operations. Registered under `math:` (`http://www.w3.org/2000/10/swap/math#`).

Source: `pyeye/builtins.py` (functions `math_*`)

### Comparisons

| Builtin | What it does | Example body pattern |
|---|---|---|
| `math:equalTo` | Are two numbers equal? | `?X math:equalTo "5"` |
| `math:notEqualTo` | Are two numbers different? | `?X math:notEqualTo ?Y` |
| `math:lessThan` | Is first smaller? | `?X math:lessThan "100"` |
| `math:greaterThan` | Is first larger? | `?X math:greaterThan "30"` |
| `math:notLessThan` | Is first ≥ second? | `?X math:notLessThan "0"` |
| `math:notGreaterThan` | Is first ≤ second? | `?X math:notGreaterThan "100"` |

### Arithmetic

| Builtin | What it does | Example body pattern |
|---|---|---|
| `math:plus` | Add | `?A math:plus ?B ?Sum` |
| `math:minus` | Subtract | `?A math:minus ?B ?Diff` |
| `math:times` | Multiply | `?A math:times ?B ?Product` |
| `math:divide` | Divide (skips if divisor=0) | `?A math:divide ?B ?Quotient` |
| `math:sum` | Sum of list | `(2 3 4) math:sum ?S` → S=9 |
| `math:product` | Product of list | `(2 3 4) math:product ?P` → P=24 |
| `math:difference` | First minus second | `?A math:difference ?B ?D` |
| `math:quotient` | First divided by second | `?A math:quotient ?B ?Q` |
| `math:integerQuotient` | Integer division | `7 math:integerQuotient 3 ?Q` → Q=2 |
| `math:remainder` | Modulo | `7 math:remainder 3 ?R` → R=1 |
| `math:absoluteValue` | Absolute value | `"-5" math:absoluteValue ?A` → A=5 |
| `math:negation` | Negate | `"5" math:negation ?N` → N=-5 |
| `math:max` | Maximum of list | `(3 1 4 1 5) math:max ?M` → M=5 |
| `math:min` | Minimum of list | `(3 1 4 1 5) math:min ?M` → M=1 |

### Rounding

| Builtin | What it does | Example |
|---|---|---|
| `math:floor` | Round down | `"3.7" math:floor ?F` → F=3 |
| `math:ceiling` | Round up | `"3.2" math:ceiling ?C` → C=4 |
| `math:rounded` | Round to nearest integer | `"3.5" math:rounded ?R` → R=4 |
| `math:roundedTo` | Round to N decimal places | `"3.14159" math:roundedTo "2" ?R` → R=3.14 |

### Exponential and Logarithm

| Builtin | What it does | Example |
|---|---|---|
| `math:exponentiation` | Power | `"2" math:exponentiation "3" ?R` → R=8 |
| `math:logarithm` | Natural log | `?X math:logarithm ?L` → L=ln(X) |

### Trigonometry

| Builtin | What it does | Example |
|---|---|---|
| `math:sin` | Sine (radians) | `?X math:sin ?S` |
| `math:cos` | Cosine (radians) | `?X math:cos ?C` |
| `math:tan` | Tangent (radians) | `?X math:tan ?T` |
| `math:asin` | Arcsine | `?X math:asin ?A` |
| `math:acos` | Arccosine | `?X math:acos ?A` |
| `math:atan` | Arctangent | `?X math:atan ?A` |
| `math:atan2` | Arctangent of Y/X | `(?Y ?X) math:atan2 ?A` |
| `math:sinh` | Hyperbolic sine | `?X math:sinh ?S` |
| `math:cosh` | Hyperbolic cosine | `?X math:cosh ?C` |
| `math:tanh` | Hyperbolic tangent | `?X math:tanh ?T` |
| `math:asinh` | Inverse hyperbolic sine | `?X math:asinh ?A` |
| `math:acosh` | Inverse hyperbolic cosine | `?X math:acosh ?A` |
| `math:atanh` | Inverse hyperbolic tangent | `?X math:atanh ?A` |
| `math:degrees` | Radians to degrees | `?R math:degrees ?D` |
| `math:radians` | Degrees to radians | `?D math:radians ?R` |

### Statistics

| Builtin | What it does | Example |
|---|---|---|
| `math:avg` | Average of list | `(2 4 6) math:avg ?A` → A=4 |
| `math:std` | Standard deviation | `(2 4 4 4 5 5 7 9) math:std ?S` |
| `math:rms` | Root mean square | `(3 4) math:rms ?R` |
| `math:pcc` | Pearson correlation | interleaved pairs |
| `math:memberCount` | Count list elements | `(a b c) math:memberCount ?N` → N=3 |

### Example: Discount Calculator

```n3
@prefix : <http://shop.org/> .
@prefix math: <http://www.w3.org/2000/10/swap/math#> .

:widget :price 50 ; :discount "0.1" .

{ ?Item :price ?P . ?Item :discount ?D .
  "1" math:minus ?D ?Factor .
  ?P math:times ?Factor ?Final }
    => { ?Item :finalPrice ?Final } .
```

Result: `:widget :finalPrice 45.0 .`

---

## String Builtins

**30+ functions** for text operations. Registered under `string:` (`http://www.w3.org/2000/10/swap/string#`).

Source: `pyeye/builtins.py` (functions `string_*` and `func_*`)

### Core String Operations

| Builtin | What it does | Example |
|---|---|---|
| `string:concatenation` | Join strings | `("Hello" " " "World") string:concatenation ?R` → R="Hello World" |
| `string:length` | Character count | `?Text string:length ?N` |
| `string:contains` | Contains substring? | `?Text string:contains "error"` |
| `string:startsWith` | Starts with prefix? | `?Text string:startsWith "Dr."` |
| `string:endsWith` | Ends with suffix? | `?Email string:endsWith "@corp.org"` |
| `string:equal` | Strings identical? | `?A string:equal ?B` |
| `string:matches` | Regex match | `?Text string:matches "^[A-Z].*"` |
| `string:notMatches` | Regex non-match | `?Text string:notMatches "^[0-9]"` |
| `string:replace` | Regex replace first | `?Text string:replace ("old" "new") ?R` |
| `string:replaceAll` | Regex replace all | `?Text string:replaceAll ("a" "b") ?R` |
| `string:substring` | Extract substring | `"hello" string:substring ("1" "3") ?R` → R="ell" |
| `string:join` | Join list with separator | `("a" "b" "c") string:join "," ?R` → R="a,b,c" |
| `string:format` | Format string | `"%s is %d" string:format (:alice 30) ?R` |
| `string:scrape` | Regex first match | `?Text string:scrape "([0-9]+)" ?R` |
| `string:scrapeAll` | All regex matches | `?Text string:scrapeAll "[0-9]+" ?R` |
| `string:search` | Find position | `?Text string:search "pattern" ?Pos` |
| `string:stringReverse` | Reverse string | `"hello" string:stringReverse ?R` → R="olleh" |
| `string:stringEscape` | Escape special chars | `?Text string:stringEscape ?R` |
| `string:capitalize` | Capitalize first letter | `"hello" string:capitalize ?R` → R="Hello" |
| `string:upperCase` | To uppercase | `"hello" string:upperCase ?R` → R="HELLO" |
| `string:lowerCase` | To lowercase | `"HELLO" string:lowerCase ?R` → R="hello" |
| `string:charAt` | Character at 0-based index | `"hello" string:charAt (0 ?C)` → C="h" |
| `string:setCharAt` | Replace character at index | `"hello" string:setCharAt (1 "a" ?R)` → R="hallo" |

### Case-Insensitive Comparisons

| Builtin | What it does |
|---|---|
| `string:equalIgnoringCase` | Equal regardless of case |
| `string:notEqualIgnoringCase` | Not equal regardless of case |
| `string:containsIgnoringCase` | Contains substring (case-insensitive) |
| `string:containsRoughly` | Contains (rough match, case-insensitive) |
| `string:notContainsRoughly` | Does not contain (rough match) |

### String Ordering

| Builtin | What it does |
|---|---|
| `string:lessThan` | String lexicographic less-than |
| `string:greaterThan` | String lexicographic greater-than |
| `string:notLessThan` | String lexicographic ≥ |
| `string:notGreaterThan` | String lexicographic ≤ |

### XPath-Style String Functions

Registered under the `func:` namespace (`http://www.w3.org/2007/XPath-functions#`):

| Builtin | What it does | Example |
|---|---|---|
| `func:concat` | Concatenate strings | `func:concat("Hello" " " "World") ?R` |
| `func:string-length` | String length | `func:string-length("hello") ?R` → R=5 |
| `func:upper-case` | Uppercase | `func:upper-case("hello") ?R` → R="HELLO" |
| `func:lower-case` | Lowercase | `func:lower-case("HELLO") ?R` → R="hello" |
| `func:substring-before` | Text before delimiter | `func:substring-before("a:b" ":") ?R` → R="a" |
| `func:substring-after` | Text after delimiter | `func:substring-after("a:b" ":") ?R` → R="b" |
| `func:translate` | Character substitution | `func:translate("abc" "abc" "xyz") ?R` → R="xyz" |
| `func:normalize-space` | Normalize whitespace | `func:normalize-space("  hi  ") ?R` → R="hi" |
| `func:tokenize` | Split string into list | `func:tokenize("a b c" " ") ?R` |

### XPath Predicate Comparisons

Registered under `pred:` (`http://www.w3.org/2007/XPath-functions/pred#`):

| Builtin | What it does |
|---|---|
| `pred:less-than` | Lexicographic less-than |
| `pred:greater-than` | Lexicographic greater-than |

### Example: Email Routing

```n3
@prefix : <http://users.org/> .
@prefix string: <http://www.w3.org/2000/10/swap/string#> .

:alice :email "alice@corp.org" .
:bob   :email "bob@gmail.com" .

{ ?User :email ?E . ?E string:endsWith "@corp.org" }
    => { ?User :isInternal true } .

{ ?User :email ?E . ?E string:matches ".*@.*\\..*" }
    => { ?User :emailValid true } .
```

---

## List Builtins

**27+ functions** for working with RDF lists (`rdf:first` / `rdf:rest` chains). Registered under `list:` (`http://www.w3.org/2000/10/swap/list#`).

Source: `pyeye/builtins.py` (functions `list_*`)

Lists in N3 are written as `(item1 item2 item3)`.

| Builtin | What it does | Example |
|---|---|---|
| `list:in` | Is item in list? | `:apple list:in (:apple :banana)` |
| `list:length` | How many items? | `(:a :b :c) list:length ?N` → N=3 |
| `list:car` | First element | `_:list list:car ?First` |
| `list:cdr` | Tail (rest) | `_:list list:cdr ?Rest` |
| `list:first` | First element | `_:list list:first ?First` |
| `list:rest` | Tail (rest) | `_:list list:rest ?Rest` |
| `list:last` | Last element | `_:list list:last ?Last` |
| `list:select` | Nth element (1-indexed) | `_:list list:select "2" ?Item` |
| `list:memberAt` | Element at index | `_:list list:memberAt "0" ?Item` |
| `list:member` | Is item a member? | `:x list:member _:list` |
| `list:notMember` | Is item not a member? | `:x list:notMember _:list` |
| `list:append` | Append two lists | `(?L1 ?L2) list:append ?Result` |
| `list:remove` | Remove element | `(?Item ?List) list:remove ?Result` |
| `list:removeAt` | Remove at index | `(?List ?N) list:removeAt ?Result` |
| `list:removeDuplicates` | Deduplicate | `_:list list:removeDuplicates ?Result` |
| `list:reverse` | Reverse list | `_:list list:reverse ?Result` |
| `list:sort` | Sort list | `_:list list:sort ?Sorted` |
| `list:unique` | List of unique values | `_:list list:unique ?Result` |
| `list:permutation` | Generate permutations | `_:list list:permutation ?Perm` |
| `list:iterate` | Iterate with index | `_:list list:iterate (?Idx ?Item)` |
| `list:map` | Map function over list | complex |
| `list:isList` | Is this a list? | `?X list:isList ?R` |
| `list:firstRest` | Decompose into first+rest | `_:list list:firstRest (?F ?R)` |
| `list:intersection` | List intersection | `(?L1 ?L2) list:intersection ?Result` |
| `list:setEqualTo` | Sets equal? | `(?L1 ?L2) list:setEqualTo ?R` |
| `list:setNotEqualTo` | Sets not equal? | `(?L1 ?L2) list:setNotEqualTo ?R` |
| `list:multisetEqualTo` | Multisets equal? | `(?L1 ?L2) list:multisetEqualTo ?R` |
| `list:multisetNotEqualTo` | Multisets not equal? | `(?L1 ?L2) list:multisetNotEqualTo ?R` |

### Example: Shopping Cart

```n3
@prefix : <http://shop.org/> .
@prefix list: <http://www.w3.org/2000/10/swap/list#> .

:order1 :items (:apple :banana :milk) .

{ ?Order :items ?Items . :apple list:in ?Items }
    => { ?Order :hasApples true } .

{ ?Order :items ?Items . ?Items list:length ?N }
    => { ?Order :itemCount ?N } .
```

---

## Log / Meta Builtins

**~50 functions** for engine operations, term manipulation, and meta-reasoning. Registered under `log:` (`http://www.w3.org/2000/10/swap/log#`).

Source: `pyeye/builtins.py` (functions `log_*`)

| Builtin | What it does | Example |
|---|---|---|
| `log:equalTo` | Are two terms identical (same IRI/value)? | `?A log:equalTo ?B` |
| `log:notEqualTo` | Are two terms different? | `?A log:notEqualTo ?B` |
| `log:skolem` | Generate a unique skolem ID | `?Entity log:skolem ?ID` → ID="_:sk-1" |
| `log:uuid` | Generate a UUID | `log:uuid ?U` → U="550e8400-..." |
| `log:outputString` | Mark term for output | `?Msg log:outputString ?Out` |
| `log:content` | All triples in the store | `log:content ?All` |
| `log:n3String` | Convert term to N3 text | `:foo log:n3String ?S` → S=":foo" |
| `log:localN3String` | Serialize term using local/relative names | `?T log:localN3String ?S` |
| `log:implies` | Does premise imply conclusion? | `?A log:implies ?B` |
| `log:impliesAnswer` | Marks rule as producing answer triples (stub) | — |
| `log:isImpliedBy` | Backward implication (stub) | `?B log:isImpliedBy ?A` |
| `log:impliedBy` | Alias for `log:isImpliedBy` (eyeling spelling) | — |
| `log:forAllIn` | Collect all bindings for variable | returns store triples |
| `log:collectAllIn` | Collect all matching triples | returns store triples |
| `log:ask` | HTTP GET (SSRF-protected) | `"http://ex.org/data" log:ask ?Body` |
| `log:shell` | Execute safe command, return stdout | `"echo hi" log:shell ?Out` |
| `log:bound` | Is term bound? | `?X log:bound ?R` |
| `log:call` | Call a formula as a goal | `?Formula log:call ?R` |
| `log:callNotBind` | Call without binding variables (stub) | — |
| `log:callWithCleanup` | Call with cleanup action (stub) | — |
| `log:callWithCut` | Call with cut semantics (stub) | — |
| `log:callWithDisjunction` | Disjunctive call (stub) | — |
| `log:callWithOptional` | Optional call (stub) | — |
| `log:copy` | Copy term | `?T log:copy ?Copy` |
| `log:dtlit` | Create datatype literal | `(?Val ?Type) log:dtlit ?L` |
| `log:langlit` | Create language literal | `(?Val ?Lang) log:langlit ?L` |
| `log:localName` | Local name from IRI | `:foo log:localName ?N` → N="foo" |
| `log:namespace` | Namespace from IRI | `:foo log:namespace ?NS` |
| `log:rawType` | Get term type | `?X log:rawType ?T` → T="Literal" |
| `log:repeat` | Repeat N times | `"3" log:repeat ?I` → yields 0,1,2 |
| `log:satisfiable` | Is formula satisfiable? | complex |
| `log:triple` | Construct a triple | `(?S ?P ?O) log:triple ?T` |
| `log:version` | pyeye version string | `log:version ?V` |
| `log:conclusion` | Formula conclusion | complex |
| `log:conjunction` | Formula conjunction | complex |
| `log:graph` | Graph operations | complex |
| `log:hasPrefix` | Does IRI have prefix? | `?IRI log:hasPrefix ?NS` |
| `log:includes` | Formula includes triple? | `?F log:includes ?T` |
| `log:includesNotBind` | Includes check without binding (stub) | — |
| `log:notIncludes` | Formula doesn't include triple? | `?F log:notIncludes ?T` |
| `log:isBuiltin` | Is IRI a builtin? | `?P log:isBuiltin ?R` |
| `log:isomorphic` | Are two formulas isomorphic? | `?F1 log:isomorphic ?F2` |
| `log:notIsomorphic` | Are two formulas not isomorphic? | — |
| `log:parsedAsN3` | Parse string as N3 | `?Text log:parsedAsN3 ?F` |
| `log:becomes` | Retract old, assert new | `(?OldT ?NewT) log:becomes ?R` |
| `log:trace` | Log to stderr for debugging | `?Msg log:trace ?R` |
| `log:uri` | IRI as string | `?IRI log:uri ?S` |
| `log:allPossibleCases` | Collect all solutions (stub) | — |
| `log:dcg` | Definite Clause Grammar invocation (stub) | — |
| `log:ifThenElseIn` | Conditional reasoning in graph (stub) | — |
| `log:inferences` | Count of derived triples so far | `log:inferences ?N` |
| `log:query` | Execute a query formula (stub) | — |
| `log:table` | Tabling/memoisation directive (stub; always true) | `log:table ?P` |

### Unique ID Generator Example

```n3
@prefix : <http://tickets.org/> .
@prefix log: <http://www.w3.org/2000/10/swap/log#> .

:issue1 :reported true .
:issue2 :reported true .

{ ?Issue :reported true . ?Issue log:skolem ?ID }
    => { ?Issue :ticketId ?ID } .
```

Each issue gets a different unique ID: `:issue1 :ticketId _:sk-1 .` etc.

---

## Type Builtins

**4 functions** for type checking and conversion. Registered under `log:` (W3C swap).

Source: `pyeye/builtins.py` (functions `type_*`)

| Builtin | What it does | Example |
|---|---|---|
| `log:isLiteral` | Is this a Literal (not IRI)? | `"hello" log:isLiteral ?R` → R=true |
| `log:isNumeric` | Is this a numeric value? | `42 log:isNumeric ?R` → R=true |
| `log:str` | Convert term to plain string | `:foo log:str ?S` → S=":foo" |
| `log:iri` | Convert string to NamedNode | `"http://x.org/a" log:iri ?R` → R=\<http://x.org/a\> |

---

## Crypto Builtins

**4 hash functions.** Registered under `crypto:` (`http://www.w3.org/2000/10/swap/crypto#`).

Source: `pyeye/builtins.py` (functions `crypto_*`)

| Builtin | What it does | Example |
|---|---|---|
| `crypto:md5` | MD5 hash | `"hello" crypto:md5 ?H` → H="5d41402abc4b..." |
| `crypto:sha` | SHA-1 hash | `"hello" crypto:sha ?H` |
| `crypto:sha256` | SHA-256 hash | `"hello" crypto:sha256 ?H` → H="2cf24dba..." |
| `crypto:sha512` | SHA-512 hash | `"hello" crypto:sha512 ?H` |

Also available under `e:`: `e:hmac-sha` for HMAC computation (EYE-specific, no canonical equivalent).

---

## Time Builtins

**13 functions** for dates and clocks. Registered under `time:` (`http://www.w3.org/2000/10/swap/time#`).

Source: `pyeye/builtins.py` (functions `time_*`)

| Builtin | What it does | Example |
|---|---|---|
| `time:now` | Current date and time | `time:now ?Now` → Now="2026-04-06T12:00:00" |
| `time:localTime` | Current local time as ISO | `time:localTime ?T` |
| `time:in-seconds` | Unix timestamp | `time:in-seconds ?T` |
| `time:year` | Extract year | `"2026-04-06" time:year ?Y` → Y=2026 |
| `time:month` | Extract month | `"2026-04-06" time:month ?M` → M=4 |
| `time:day` | Extract day | `"2026-04-06" time:day ?D` → D=6 |
| `time:hours` | Extract hours (plural form) | `"2026-04-06T12:30:00" time:hours ?H` → H=12 |
| `time:minutes` | Extract minutes (plural form) | `"2026-04-06T12:30:00" time:minutes ?M` → M=30 |
| `time:seconds` | Extract seconds (plural form) | `"2026-04-06T12:30:45" time:seconds ?S` → S=45 |
| `time:hour` | Extract hours (eyeling form) | `"T12:30:00" time:hour ?H` → H=12 |
| `time:minute` | Extract minutes (eyeling form) | `"T12:30:00" time:minute ?M` → M=30 |
| `time:second` | Extract seconds as float (eyeling form) | `"T12:30:45" time:second ?S` → S=45.0 |
| `time:timeZone` | Extract timezone offset | `"2026-04-06T12:00:00+02:00" time:timeZone ?Z` → Z="+02:00" |

---

## Graph Builtins

**9 functions** for named graph operations. Registered under `graph:` (`http://www.w3.org/2000/10/swap/graph#`).

Source: `pyeye/builtins.py` (functions `graph_*`)

| Builtin | What it does | Example |
|---|---|---|
| `graph:member` | Is triple in graph? | `:a graph:member :graph1` |
| `graph:notMember` | Is triple not in graph? | `:a graph:notMember :graph1` |
| `graph:length` | Number of triples in graph | `:g graph:length ?N` |
| `graph:difference` | Triples in A but not B | `(:g1 :g2) graph:difference ?D` |
| `graph:intersection` | Triples common to both | `(:g1 :g2) graph:intersection ?I` |
| `graph:union` | All triples from both | `(:g1 :g2) graph:union ?U` |
| `graph:statement` | Construct a triple | `(:s :p :o) graph:statement ?T` |
| `graph:renameBlanks` | Rename blank nodes in graph | `?G graph:renameBlanks ?Result` |
| `graph:list` | List all triples in graph | `:g graph:list ?L` |

---

## Reason Builtins

Registered under `reason:` (`http://www.w3.org/2000/10/swap/reason#`).

| Builtin | What it does |
|---|---|
| `reason:because` | Evidence for a conclusion |
| `reason:binding` | Variable binding record |
| `reason:boundTo` | A variable is bound to a value |
| `reason:component` | Component of a proof |
| `reason:evidence` | Evidence chain |
| `reason:gives` | Rule gives conclusion |
| `reason:rule` | Reference to a rule |
| `reason:source` | Source of a triple |
| `reason:variable` | Variable reference |

---

## E: (EYE-specific) Builtins

**Builtins unique to EYE/eyeling** with no canonical W3C swap equivalent. Registered under `e:` (`http://eulersharp.sourceforge.net/2003/03swap/log-rules#`).

Source: `pyeye/builtins.py` (functions `e_*`)

### Safe Execution

| Builtin | What it does |
|---|---|
| `e:calculate` | Evaluate safe expression — uses `ast.literal_eval` (no `eval()`) |
| `e:exec` | Execute safe command, return exit code |

**Command allowlist** for `e:exec` and `e:shell` — only these commands are permitted:

```
echo, date, uname, whoami, hostname, id, uptime,
cat, head, tail, wc, ls, find, stat, file, md5sum, sha256sum,
curl, wget, ping, dig, nslookup,
grep, awk, sed, sort, uniq, tr, cut,
bc, expr, df, free, ps
```

Shell injection is prevented by using `subprocess.run(..., shell=False)`. Commands not in the allowlist are silently rejected.

### Dynamic Rules

| Builtin | What it does |
|---|---|
| `e:findall` | Collect all store triples |
| `e:closure` | Check if formula is deductively closed |
| `e:derive` | Call a registered Python function by name |
| `e:becomes` | Retract old triple, assert new one |

### Control Flow

| Builtin | What it does |
|---|---|
| `e:call` | Call formula as goal |
| `e:callNotBind` | Call goal without binding |
| `e:callWithCleanup` | Call goal with cleanup handler |
| `e:callWithCut` | Call goal with cut (stop on first solution) |
| `e:callWithDisjunction` | Call either of two goals |
| `e:callWithOptional` | Call optional goal |
| `e:fail` | Always fails (forces backtracking) |
| `e:true` | Always succeeds |
| `e:optional` | Optional goal |
| `e:ignore` | Ignore result of goal |
| `e:whenGround` | Only proceed when argument is ground |

### Misc Advanced

| Builtin | What it does |
|---|---|
| `e:before` | Is first term before second? |
| `e:biconditional` | Biconditional logic |
| `e:binaryEntropy` | Binary entropy calculation |
| `e:boolean` | Boolean coercion |
| `e:cartesianProduct` | Cartesian product of lists |
| `e:compoundTerm` | Construct compound term |
| `e:conditional` | If-then-else |
| `e:cov` | Covariance |
| `e:csvTuple` | CSV row to list |
| `e:epsilon` | Machine epsilon |
| `e:F` | Boolean false |
| `e:T` | Boolean true |
| `e:fileString` | Read file as string |
| `e:finalize` | Finalization hook |
| `e:graphCopy` | Copy a graph |
| `e:graphDifference` | Graph difference |
| `e:graphIntersection` | Graph intersection |
| `e:graphList` | List of graphs |
| `e:graphMember` | Graph membership |
| `e:graphPair` | Graph pair operations |
| `e:label` | Label a variable |
| `e:labelvars` | Label multiple variables |
| `e:match` | Pattern match |
| `e:notLabel` | Negate label |
| `e:numeral` | Number → numeral string |
| `e:propertyChainExtension` | Property chain |
| `e:random` | Random number |
| `e:relabel` | Relabel variables |
| `e:roc` | ROC curve |
| `e:sigmoid` | Sigmoid function |
| `e:stringSplit` | Split string |
| `e:subsequence` | List subsequence |
| `e:tactic` | Reasoning tactic hint |
| `e:transpose` | Transpose matrix |
| `e:tripleList` | List of triples |
| `e:tuple` | Tuple construction |
| `e:wwwFormEncode` | URL-encode a string |

### Variable Binding Helpers (var: namespace)

Registered under `var:` (`http://www.w3.org/2000/10/swap/var#`):

| Builtin | What it does |
|---|---|
| `var:all` | Collect all values |
| `var:qe` | Quantifier-elimination helper |
| `var:v` | Variable access |
| `var:x` | Extended variable access |

---

## Registering Custom Builtins

### Method 1: Pass to `execute()`

```python
from pyeye import execute
from pyeye.term import Literal, Variable

def my_double(args, engine):
    """Double a number. Skip if not ground."""
    if any(isinstance(a, Variable) for a in args):
        return None  # not ready yet
    return Literal(str(float(args[0].value) * 2))

result = execute(
    data_strings=["@prefix : <http://ex.org/> .\n:item :value 21 ."],
    rule_strings=["@prefix : <http://ex.org/> .\n"
                  "@prefix ex: <http://ex.org/builtins#> .\n"
                  "{ ?I :value ?V . ?V ex:myDouble ?D } => { ?I :doubled ?D } ."],
    builtins={"http://ex.org/builtins#myDouble": my_double},
)
```

The custom registry is **merged** with the default builtins, so all 240 standard functions remain available.

### Method 2: `e:derive` — Call by Name

Register a Python function and call it by name from N3:

```python
from pyeye.builtins import register_derive_function
from pyeye.term import Literal

def triple_it(args, engine):
    return Literal(str(float(args[0].value) * 3))

register_derive_function("triple", triple_it)
```

Then in N3:

```n3
@prefix e: <http://eulersharp.sourceforge.net/2003/03swap/log-rules#> .
{ ?Item :value ?V } => { ?Item :tripled ?T . (?V "triple") e:derive ?T } .
```

### Builtin Function Signature

```python
def my_builtin(args: list[Term], engine: Engine) -> Term | list[Triple] | None:
    """
    args:   list of resolved argument Terms (subject and object, list-expanded)
    engine: the Engine instance (access engine.store for lookups)

    Return:
        Term         → result value (used as object in head or comparison)
        list[Triple] → triples to assert directly
        None         → skip (arguments not ready or condition failed)
    """
```
