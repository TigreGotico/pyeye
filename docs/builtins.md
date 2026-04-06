# Builtins Reference

**Source:** `BUILTIN_REGISTRY` — `pyeye/builtins.py` (425 entries)

pyeye has **425 built-in functions** registered under two namespace families.

### Legacy `e:` namespace (eulersharp)

```
@prefix e: <http://eulersharp.sourceforge.net/2003/03swap/log-rules#> .
```

### Canonical W3C `swap:` namespaces (recommended for EYE/eyeling compatibility)

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

Both namespace styles are fully equivalent. `math:greaterThan` and `e:greaterThan` resolve to the same implementation. N3 files written for EYE or eyeling will work unchanged.

---

## How Builtins Work

Builtins appear as the **predicate** in a triple pattern inside a rule body:

```n3
{ SUBJECT e:builtinName OBJECT } => { HEAD } .
```

The **subject** provides input(s), the **object** either receives a result or acts as a comparison target.

### Pattern: filter (boolean test)

```n3
{ ?Price e:greaterThan "30" } => { :item :expensive true } .
```

If `?Price` is bound and greater than 30, the body matches and the head is derived.

### Pattern: compute (result bound to variable)

```n3
{ ?A e:plus ?B ?Sum } => { :result :total ?Sum } .
```

`?Sum` receives the computed value (A + B). The head uses it.

### Unground arguments

If any argument is an unbound variable when the engine evaluates the builtin, evaluation is **skipped** — the engine moves on and may retry later when variables are grounded.

### Builtins in body only

Builtins appear in the **body** of a rule (before `=>`). They evaluate conditions or compute values for use in the head. They do not create facts by themselves.

---

## The `e:` Prefix

All builtins share one namespace:

```
http://eulersharp.sourceforge.net/2003/03swap/log-rules#
```

In N3 files, declare it once:

```n3
@prefix e: <http://eulersharp.sourceforge.net/2003/03swap/log-rules#> .
```

Then use as `e:greaterThan`, `e:concatenation`, `e:md5`, etc.

---

## Math Builtins

**44 functions** for numeric operations.

Source: `pyeye/builtins.py` (functions `math_*`)

### Comparisons

| Builtin | What it does | Example body pattern |
|---|---|---|
| `e:equalTo` | Are two numbers equal? | `?X e:equalTo "5"` |
| `e:notEqualTo` | Are two numbers different? | `?X e:notEqualTo ?Y` |
| `e:lessThan` | Is first smaller? | `?X e:lessThan "100"` |
| `e:greaterThan` | Is first larger? | `?X e:greaterThan "30"` |
| `e:notLessThan` | Is first ≥ second? | `?X e:notLessThan "0"` |
| `e:notGreaterThan` | Is first ≤ second? | `?X e:notGreaterThan "100"` |

### Arithmetic

| Builtin | What it does | Example body pattern |
|---|---|---|
| `e:plus` | Add | `?A e:plus ?B ?Sum` |
| `e:minus` | Subtract | `?A e:minus ?B ?Diff` |
| `e:times` | Multiply | `?A e:times ?B ?Product` |
| `e:divide` | Divide (skips if divisor=0) | `?A e:divide ?B ?Quotient` |
| `e:sum` | Sum of list | `(2 3 4) e:sum ?S` → S=9 |
| `e:product` | Product of list | `(2 3 4) e:product ?P` → P=24 |
| `e:difference` | First minus second | `?A e:difference ?B ?D` |
| `e:quotient` | First divided by second | `?A e:quotient ?B ?Q` |
| `e:integerQuotient` | Integer division | `7 e:integerQuotient 3 ?Q` → Q=2 |
| `e:remainder` | Modulo | `7 e:remainder 3 ?R` → R=1 |
| `e:absoluteValue` | Absolute value | `"-5" e:absoluteValue ?A` → A=5 |
| `e:negation` | Negate | `"5" e:negation ?N` → N=-5 |
| `e:max` | Maximum of list | `(3 1 4 1 5) e:max ?M` → M=5 |
| `e:min` | Minimum of list | `(3 1 4 1 5) e:min ?M` → M=1 |

### Rounding

| Builtin | What it does | Example |
|---|---|---|
| `e:floor` | Round down | `"3.7" e:floor ?F` → F=3 |
| `e:ceiling` | Round up | `"3.2" e:ceiling ?C` → C=4 |
| `e:rounded` | Round to nearest integer | `"3.5" e:rounded ?R` → R=4 |
| `e:roundedTo` | Round to N decimal places | `"3.14159" e:roundedTo "2" ?R` → R=3.14 |

### Exponential and Logarithm

| Builtin | What it does | Example |
|---|---|---|
| `e:exponentiation` | Power | `"2" e:exponentiation "3" ?R` → R=8 |
| `e:logarithm` | Natural log | `?X e:logarithm ?L` → L=ln(X) |

### Trigonometry

| Builtin | What it does | Example |
|---|---|---|
| `e:sin` | Sine (radians) | `?X e:sin ?S` |
| `e:cos` | Cosine (radians) | `?X e:cos ?C` |
| `e:tan` | Tangent (radians) | `?X e:tan ?T` |
| `e:asin` | Arcsine | `?X e:asin ?A` |
| `e:acos` | Arccosine | `?X e:acos ?A` |
| `e:atan` | Arctangent | `?X e:atan ?A` |
| `e:atan2` | Arctangent of Y/X | `(?Y ?X) e:atan2 ?A` |
| `e:sinh` | Hyperbolic sine | `?X e:sinh ?S` |
| `e:cosh` | Hyperbolic cosine | `?X e:cosh ?C` |
| `e:tanh` | Hyperbolic tangent | `?X e:tanh ?T` |
| `e:asinh` | Inverse hyperbolic sine | `?X e:asinh ?A` |
| `e:acosh` | Inverse hyperbolic cosine | `?X e:acosh ?A` |
| `e:atanh` | Inverse hyperbolic tangent | `?X e:atanh ?A` |
| `e:degrees` | Radians to degrees | `?R e:degrees ?D` |
| `e:radians` | Degrees to radians | `?D e:radians ?R` |

### Statistics

| Builtin | What it does | Example |
|---|---|---|
| `e:avg` | Average of list | `(2 4 6) e:avg ?A` → A=4 |
| `e:std` | Standard deviation | `(2 4 4 4 5 5 7 9) e:std ?S` |
| `e:rms` | Root mean square | `(3 4) e:rms ?R` |
| `e:pcc` | Pearson correlation | interleaved pairs |
| `e:memberCount` | Count list elements | `(a b c) e:memberCount ?N` → N=3 |

### Example: Discount Calculator

```n3
@prefix : <http://shop.org/> .
@prefix e: <http://eulersharp.sourceforge.net/2003/03swap/log-rules#> .

:widget :price 50 ; :discount "0.1" .

{ ?Item :price ?P . ?Item :discount ?D .
  "1" e:minus ?D ?Factor .
  ?P e:times ?Factor ?Final }
    => { ?Item :finalPrice ?Final } .
```

Result: `:widget :finalPrice 45.0 .`

---

## String Builtins

**30 functions** for text operations.

Source: `pyeye/builtins.py` (functions `string_*` and `func_*`)

### Core String Operations

| Builtin | What it does | Example |
|---|---|---|
| `e:concatenation` | Join strings | `("Hello" " " "World") e:concatenation ?R` → R="Hello World" |
| `e:length` | Character count | `?Text e:length ?N` |
| `e:contains` | Contains substring? | `?Text e:contains "error"` |
| `e:startsWith` | Starts with prefix? | `?Text e:startsWith "Dr."` |
| `e:endsWith` | Ends with suffix? | `?Email e:endsWith "@corp.org"` |
| `e:equal` | Strings identical? | `?A e:equal ?B` |
| `e:matches` | Regex match | `?Text e:matches "^[A-Z].*"` |
| `e:notMatches` | Regex non-match | `?Text e:notMatches "^[0-9]"` |
| `e:replace` | Regex replace first | `?Text e:replace ("old" "new") ?R` |
| `e:replaceAll` | Regex replace all | `?Text e:replaceAll ("a" "b") ?R` |
| `e:substring` | Extract substring | `"hello" e:substring ("1" "3") ?R` → R="ell" |
| `e:join` | Join list with separator | `("a" "b" "c") e:join "," ?R` → R="a,b,c" |
| `e:format` | Format string | `"%s is %d" e:format (:alice 30) ?R` |
| `e:scrape` | Regex first match | `?Text e:scrape "([0-9]+)" ?R` |
| `e:scrapeAll` | All regex matches | `?Text e:scrapeAll "[0-9]+" ?R` |
| `e:search` | Find position | `?Text e:search "pattern" ?Pos` |
| `e:stringReverse` | Reverse string | `"hello" e:stringReverse ?R` → R="olleh" |
| `e:stringEscape` | Escape special chars | `?Text e:stringEscape ?R` |
| `e:capitalize` | Capitalize first letter | `"hello" e:capitalize ?R` → R="Hello" |
| `e:upperCase` | To uppercase | `"hello" e:upperCase ?R` → R="HELLO" |
| `e:lowerCase` | To lowercase | `"HELLO" e:lowerCase ?R` → R="hello" |
| `string:charAt` | Character at 0-based index | `"hello" string:charAt (0 ?C)` → C="h" |
| `string:setCharAt` | Replace character at index | `"hello" string:setCharAt (1 "a" ?R)` → R="hallo" |

### Case-Insensitive Comparisons

| Builtin | What it does |
|---|---|
| `e:equalIgnoringCase` | Equal regardless of case |
| `e:notEqualIgnoringCase` | Not equal regardless of case |
| `e:containsIgnoringCase` | Contains substring (case-insensitive) |
| `e:containsRoughly` | Contains (rough match, case-insensitive, whitespace-normalized) |
| `e:notContainsRoughly` | Does not contain (rough match) |

### String Ordering

| Builtin | What it does |
|---|---|
| `e:lessThan` | String lexicographic less-than |
| `e:greaterThan` | String lexicographic greater-than |
| `e:notLessThan` | String lexicographic ≥ |
| `e:notGreaterThan` | String lexicographic ≤ |

**Note:** `e:lessThan`, `e:greaterThan`, etc. dispatch to either math or string comparison depending on argument types.

### XPath-Style String Functions

These are also registered under the `e:` namespace:

| Builtin | What it does | Example |
|---|---|---|
| `e:concat` | Concatenate strings | `e:concat("Hello" " " "World") ?R` |
| `e:string-length` | String length | `e:string-length("hello") ?R` → R=5 |
| `e:upper-case` | Uppercase | `e:upper-case("hello") ?R` → R="HELLO" |
| `e:lower-case` | Lowercase | `e:lower-case("HELLO") ?R` → R="hello" |
| `e:substring-before` | Text before delimiter | `e:substring-before("a:b" ":") ?R` → R="a" |
| `e:substring-after` | Text after delimiter | `e:substring-after("a:b" ":") ?R` → R="b" |
| `e:translate` | Character substitution | `e:translate("abc" "abc" "xyz") ?R` → R="xyz" |
| `e:normalize-space` | Normalize whitespace | `e:normalize-space("  hi  ") ?R` → R="hi" |
| `e:tokenize` | Split string into list | `e:tokenize("a b c" " ") ?R` |

### XPath Predicate Comparisons

| Builtin | What it does |
|---|---|
| `e:less-than` | Lexicographic less-than |
| `e:greater-than` | Lexicographic greater-than |

### Example: Email Routing

```n3
@prefix : <http://users.org/> .
@prefix e: <http://eulersharp.sourceforge.net/2003/03swap/log-rules#> .

:alice :email "alice@corp.org" .
:bob   :email "bob@gmail.com" .

{ ?User :email ?E . ?E e:endsWith "@corp.org" }
    => { ?User :isInternal true } .

{ ?User :email ?E . ?E e:matches ".*@.*\\..*" }
    => { ?User :emailValid true } .
```

---

## List Builtins

**27 functions** for working with RDF lists (`rdf:first` / `rdf:rest` chains).

Source: `pyeye/builtins.py` (functions `list_*`)

Lists in N3 are written as `(item1 item2 item3)`.

| Builtin | What it does | Example |
|---|---|---|
| `e:in` | Is item in list? | `:apple e:in (:apple :banana)` |
| `e:length` | How many items? | `(:a :b :c) e:length ?N` → N=3 |
| `e:car` | First element | `_:list e:car ?First` |
| `e:cdr` | Tail (rest) | `_:list e:cdr ?Rest` |
| `e:first` | First element | `_:list e:first ?First` |
| `e:rest` | Tail (rest) | `_:list e:rest ?Rest` |
| `e:last` | Last element | `_:list e:last ?Last` |
| `e:select` | Nth element (1-indexed) | `_:list e:select "2" ?Item` |
| `e:memberAt` | Element at index | `_:list e:memberAt "0" ?Item` |
| `e:member` | Is item a member? | `:x e:member _:list` |
| `e:notMember` | Is item not a member? | `:x e:notMember _:list` |
| `e:append` | Append two lists | `(?L1 ?L2) e:append ?Result` |
| `e:remove` | Remove element | `(?Item ?List) e:remove ?Result` |
| `e:removeAt` | Remove at index | `(?List ?N) e:removeAt ?Result` |
| `e:removeDuplicates` | Deduplicate | `_:list e:removeDuplicates ?Result` |
| `e:reverse` | Reverse list | `_:list e:reverse ?Result` |
| `e:sort` | Sort list | `_:list e:sort ?Sorted` |
| `e:unique` | List of unique values | `_:list e:unique ?Result` |
| `e:permutation` | Generate permutations | `_:list e:permutation ?Perm` |
| `e:iterate` | Iterate with index | `_:list e:iterate (?Idx ?Item)` |
| `e:map` | Map function over list | complex |
| `e:isList` | Is this a list? | `?X e:isList ?R` |
| `e:firstRest` | Decompose into first+rest | `_:list e:firstRest (?F ?R)` |
| `e:intersection` | List intersection | `(?L1 ?L2) e:intersection ?Result` |
| `e:setEqualTo` | Sets equal? | `(?L1 ?L2) e:setEqualTo ?R` |
| `e:setNotEqualTo` | Sets not equal? | `(?L1 ?L2) e:setNotEqualTo ?R` |
| `e:multisetEqualTo` | Multisets equal? | `(?L1 ?L2) e:multisetEqualTo ?R` |
| `e:multisetNotEqualTo` | Multisets not equal? | `(?L1 ?L2) e:multisetNotEqualTo ?R` |

### Example: Shopping Cart

```n3
@prefix : <http://shop.org/> .
@prefix e: <http://eulersharp.sourceforge.net/2003/03swap/log-rules#> .

:order1 :items (:apple :banana :milk) .

{ ?Order :items ?Items . :apple e:in ?Items }
    => { ?Order :hasApples true } .

{ ?Order :items ?Items . ?Items e:length ?N }
    => { ?Order :itemCount ?N } .
```

---

## Log / Meta Builtins

**~44 functions** for engine operations, term manipulation, and meta-reasoning.

Source: `pyeye/builtins.py` (functions `log_*`)

All are available as both `e:<name>` (eulersharp) and `log:<name>` (canonical W3C swap).

| Builtin | What it does | Example |
|---|---|---|
| `e:equalTo` | Are two terms identical (same IRI/value)? | `?A e:equalTo ?B` |
| `e:notEqualTo` | Are two terms different? | `?A e:notEqualTo ?B` |
| `e:skolem` | Generate a unique skolem ID | `?Entity e:skolem ?ID` → ID="_:sk-1" |
| `e:uuid` | Generate a UUID | `e:uuid ?U` → U="550e8400-..." |
| `e:outputString` | Mark term for output | `?Msg e:outputString ?Out` |
| `e:content` | All triples in the store | `e:content ?All` |
| `e:n3String` | Convert term to N3 text | `:foo e:n3String ?S` → S=":foo" |
| `log:localN3String` | Serialize term using local/relative names | `?T log:localN3String ?S` |
| `e:implies` | Does premise imply conclusion? | `?A e:implies ?B` |
| `log:impliesAnswer` | Marks rule as producing answer triples (stub) | — |
| `log:isImpliedBy` | Backward implication (stub) | `?B log:isImpliedBy ?A` |
| `log:impliedBy` | Alias for `log:isImpliedBy` (eyeling spelling) | — |
| `e:forAllIn` | Collect all bindings for variable | returns store triples |
| `e:collectAllIn` | Collect all matching triples | returns store triples |
| `e:ask` | HTTP GET (SSRF-protected) | `"http://ex.org/data" e:ask ?Body` |
| `e:shell` | Execute safe command, return stdout | `"echo hi" e:shell ?Out` |
| `e:bound` | Is term bound? | `?X e:bound ?R` |
| `e:call` | Call a formula as a goal | `?Formula e:call ?R` |
| `e:callNotBind` | Call without binding variables (stub) | — |
| `e:callWithCleanup` | Call with cleanup action (stub) | — |
| `e:callWithCut` | Call with cut semantics (stub) | — |
| `e:callWithDisjunction` | Disjunctive call (stub) | — |
| `e:callWithOptional` | Optional call (stub) | — |
| `e:copy` | Copy term | `?T e:copy ?Copy` |
| `e:dtlit` | Create datatype literal | `(?Val ?Type) e:dtlit ?L` |
| `e:langlit` | Create language literal | `(?Val ?Lang) e:langlit ?L` |
| `e:localName` | Local name from IRI | `:foo e:localName ?N` → N="foo" |
| `e:namespace` | Namespace from IRI | `:foo e:namespace ?NS` |
| `e:rawType` | Get term type | `?X e:rawType ?T` → T="Literal" |
| `e:repeat` | Repeat N times | `"3" e:repeat ?I` → yields 0,1,2 |
| `e:satisfiable` | Is formula satisfiable? | complex |
| `e:triple` | Construct a triple | `(?S ?P ?O) e:triple ?T` |
| `e:version` | pyeye version string | `e:version ?V` |
| `e:conclusion` | Formula conclusion | complex |
| `e:conjunction` | Formula conjunction | complex |
| `e:graph` | Graph operations | complex |
| `e:hasPrefix` | Does IRI have prefix? | `?IRI e:hasPrefix ?NS` |
| `e:includes` | Formula includes triple? | `?F e:includes ?T` |
| `log:includesNotBind` | Includes check without binding (stub) | — |
| `e:notIncludes` | Formula doesn't include triple? | `?F e:notIncludes ?T` |
| `e:isBuiltin` | Is IRI a builtin? | `?P e:isBuiltin ?R` |
| `e:isomorphic` | Are two formulas isomorphic? | `?F1 e:isomorphic ?F2` |
| `e:notIsomorphic` | Are two formulas not isomorphic? | — |
| `e:parsedAsN3` | Parse string as N3 | `?Text e:parsedAsN3 ?F` |
| `e:becomes` | Retract old, assert new | `(?OldT ?NewT) e:becomes ?R` |
| `e:trace` | Log to stderr for debugging | `?Msg e:trace ?R` |
| `e:uri` | IRI as string | `?IRI e:uri ?S` |
| `log:allPossibleCases` | Collect all solutions (stub) | — |
| `log:dcg` | Definite Clause Grammar invocation (stub) | — |
| `log:ifThenElseIn` | Conditional reasoning in graph (stub) | — |
| `log:inferences` | Count of derived triples so far | `log:inferences ?N` |
| `log:query` | Execute a query formula (stub) | — |
| `log:table` | Tabling/memoisation directive (stub; always true) | `log:table ?P` |

### Unique ID Generator Example

```n3
@prefix : <http://tickets.org/> .
@prefix e: <http://eulersharp.sourceforge.net/2003/03swap/log-rules#> .

:issue1 :reported true .
:issue2 :reported true .

{ ?Issue :reported true . ?Issue e:skolem ?ID }
    => { ?Issue :ticketId ?ID } .
```

Each issue gets a different unique ID: `:issue1 :ticketId _:sk-1 .` etc.

---

## Type Builtins

**4 functions** for type checking and conversion.

Source: `pyeye/builtins.py` (functions `type_*`)

| Builtin | What it does | Example |
|---|---|---|
| `e:isLiteral` | Is this a Literal (not IRI)? | `"hello" e:isLiteral ?R` → R=true |
| `e:isNumeric` | Is this a numeric value? | `42 e:isNumeric ?R` → R=true |
| `e:str` | Convert term to plain string | `:foo e:str ?S` → S=":foo" |
| `e:iri` | Convert string to NamedNode | `"http://x.org/a" e:iri ?R` → R=\<http://x.org/a\> |

---

## Crypto Builtins

**4 hash functions.**

Source: `pyeye/builtins.py` (functions `crypto_*`)

| Builtin | What it does | Example |
|---|---|---|
| `e:md5` | MD5 hash | `"hello" e:md5 ?H` → H="5d41402abc4b..." |
| `e:sha` | SHA-1 hash | `"hello" e:sha ?H` |
| `e:sha256` | SHA-256 hash | `"hello" e:sha256 ?H` → H="2cf24dba..." |
| `e:sha512` | SHA-512 hash | `"hello" e:sha512 ?H` |

Also available: `e:hmac-sha` for HMAC computation.

---

## Time Builtins

**13 functions** for dates and clocks.

Source: `pyeye/builtins.py` (functions `time_*`)

| Builtin | `time:` alias | What it does | Example |
|---|---|---|---|
| `e:now` | — | Current date and time | `e:now ?Now` → Now="2026-04-06T12:00:00" |
| `e:localTime` | `time:localTime` | Current local time as ISO | `e:localTime ?T` |
| `e:in-seconds` | — | Unix timestamp | `e:in-seconds ?T` |
| `e:year` | `time:year` | Extract year | `"2026-04-06" e:year ?Y` → Y=2026 |
| `e:month` | `time:month` | Extract month | `"2026-04-06" e:month ?M` → M=4 |
| `e:day` | `time:day` | Extract day | `"2026-04-06" e:day ?D` → D=6 |
| `e:hours` | `time:hour` | Extract hours | `"2026-04-06T12:30:00" e:hours ?H` → H=12 |
| `e:minutes` | `time:minute` | Extract minutes | `"2026-04-06T12:30:00" e:minutes ?M` → M=30 |
| `e:seconds` | `time:second` | Extract seconds (float) | `"2026-04-06T12:30:45" e:seconds ?S` → S=45 |
| — | `time:timeZone` | Extract timezone offset | `"2026-04-06T12:00:00+02:00" time:timeZone ?Z` → Z="+02:00" |

> **Note on naming:** EYE uses `time:year`/`time:month`/`time:day` matching the eye.pl `swap/time` namespace.  
> eyeling adds `time:hour`, `time:minute`, `time:second`, `time:timeZone` — all four are now supported.  
> The legacy `e:hours`/`e:minutes`/`e:seconds` spellings are also kept for backwards compatibility.

---

## Graph Builtins

**9 functions** for named graph operations.

Source: `pyeye/builtins.py` (functions `graph_*`)

| Builtin | What it does | Example |
|---|---|---|
| `e:member` | Is triple in graph? | `:a e:member :graph1` |
| `e:notMember` | Is triple not in graph? | `:a e:notMember :graph1` |
| `e:length` | Number of triples in graph | `:g e:length ?N` |
| `e:difference` | Triples in A but not B | `(:g1 :g2) e:difference ?D` |
| `e:intersection` | Triples common to both | `(:g1 :g2) e:intersection ?I` |
| `e:union` | All triples from both | `(:g1 :g2) e:union ?U` |
| `e:statement` | Construct a triple | `(:s :p :o) e:statement ?T` |
| `e:renameBlanks` | Rename blank nodes in graph | `?G e:renameBlanks ?Result` |
| `e:list` | List all triples in graph | `:g e:list ?L` |

---

## E: (Engine/Evaluation) Builtins

**~85 specialized builtins** including dynamic rules, execution, and advanced operations.

Source: `pyeye/builtins.py` (functions `e_*`, `reason_*`, `var_*`)

### Safe Execution

| Builtin | What it does |
|---|---|
| `e:calculate` | Evaluate safe expression — uses `ast.literal_eval` (no `eval()`) |
| `e:exec` | Execute safe command, return exit code |
| `e:shell` | Execute safe command, return stdout |

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

### Reason / Proof Builtins

| Builtin | What it does |
|---|---|
| `e:because` | Evidence for a conclusion |
| `e:binding` | Variable binding record |
| `e:boundTo` | A variable is bound to a value |
| `e:component` | Component of a proof |
| `e:evidence` | Evidence chain |
| `e:gives` | Rule gives conclusion |
| `e:rule` | Reference to a rule |
| `e:source` | Source of a triple |
| `e:variable` | Variable reference |

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

### Variable Binding Helpers

| Builtin | What it does |
|---|---|
| `e:all_` | Collect all values |
| `e:qe_` | Quantifier-elimination helper |
| `e:v_` | Variable access |
| `e:x_` | Extended variable access |

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
                  "@prefix e: <http://eulersharp.sourceforge.net/2003/03swap/log-rules#> .\n"
                  "{ ?I :value ?V . ?V e:myDouble ?D } => { ?I :doubled ?D } ."],
    builtins={"http://eulersharp.sourceforge.net/2003/03swap/log-rules#myDouble": my_double},
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
