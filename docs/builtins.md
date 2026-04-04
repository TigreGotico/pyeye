# Builtins Reference

## What are builtins?

**Builtins** are built-in functions that the reasoner can call inside rule bodies. They let you do things like compare numbers, manipulate strings, check dates, generate unique IDs, execute safe commands, and make HTTP requests — without writing any rules for them yourself.

Think of them like functions in a programming language that are always available. You don't need to define them; you just use them.

---

## How to Use a Builtin in a Rule

Builtins appear as **predicate** in a triple pattern inside a rule body. The general pattern is:

```n3
{ ARG1 builtin:Name ARG2 } => { RESULT } .
```

Where:
- `ARG1` and `ARG2` are the **inputs** (values or variables)
- `builtin:Name` is the **builtin predicate** (the function being called)
- `ARG2` can also be a **variable** that receives the result

### Example: Comparing Numbers

```n3
@prefix : <http://example.org/> .
@prefix math: <http://www.w3.org/2000/10/swap/math#> .

# Data
:room1 :temperature 35 .

# Rule: if temperature > 30, turn on AC
{ ?Room :temperature ?T . ?T math:greaterThan "30" } => { ?Room :acOn true } .
```

Here's what happens step by step:

1. The engine finds `:room1 :temperature 35` and sets `?Room = :room1`, `?T = 35`
2. It then evaluates `35 math:greaterThan "30"` → returns `true`
3. Since the whole body matched, it derives `:room1 :acOn true`

### Example: Using the Result

```n3
@prefix math: <http://www.w3.org/2000/10/swap/math#> .

# Calculate total from price and quantity
{ ?Item :price ?P . ?Item :quantity ?Q . ?P math:times ?Q ?Total }
    => { ?Item :totalCost ?Total } .
```

Here `?Total` is a variable that **receives** the result of `?P math:times ?Q`. The derived fact is `?Item :totalCost 150` (if price=50 and quantity=3).

---

## All Builtins

**Source:** `BUILTIN_REGISTRY` — `pyeye/builtins.py:1267`

There are **93 builtins** across 11 namespaces.

### Math: Numbers

**Namespace:** `http://www.w3.org/2000/10/swap/math#`

| Builtin | What it does | Example in a rule body |
| :--- | :--- | :--- |
| `math:equalTo` | Are two numbers equal? | `?X math:equalTo "5"` → `true` if X=5 |
| `math:lessThan` | Is the first number smaller? | `?X math:lessThan "100"` → `true` if X<100 |
| `math:greaterThan` | Is the first number bigger? | `?X math:greaterThan "30"` → `true` if X>30 |
| `math:notEqualTo` | Are two numbers different? | `?X math:notEqualTo ?Y` → `true` if X≠Y |
| `math:plus` | Add two numbers | `?A math:plus ?B ?Sum` → Sum = A+B |
| `math:minus` | Subtract | `?A math:minus ?B ?Diff` → Diff = A-B |
| `math:times` | Multiply | `?A math:times ?B ?Product` → Product = A×B |
| `math:divide` | Divide (skips if dividing by 0) | `?A math:divide ?B ?Quotient` → Quotient = A/B |
| `math:floor` | Round down to integer | `3.7 math:floor ?F` → F=3 |
| `math:ceiling` | Round up to integer | `3.2 math:ceiling ?C` → C=4 |
| `math:exponentiation` | Power | `2 math:exponentiation 3 ?R` → R=8 |
| `math:logarithm` | Natural logarithm | `?X math:logarithm ?L` → L=ln(X) |
| `math:sin` | Sine (radians) | `?X math:sin ?S` → S=sin(X) |
| `math:cos` | Cosine (radians) | `?X math:cos ?C` → C=cos(X) |
| `math:tan` | Tangent (radians) | `?X math:tan ?T` → T=tan(X) |
| `math:avg` | Average of numbers | `(2 4 6) math:avg ?A` → A=4 |
| `math:std` | Standard deviation | `(2 4 4 4 5 5 7 9) math:std ?S` → S≈2.14 |
| `math:pcc` | Pearson correlation | interleaved pairs → correlation coefficient |
| `math:rms` | Root mean square | `(3 4) math:rms ?R` → R≈3.54 |

Source range: `builtins.py:95-528`

#### Full math example: Discount calculator

```n3
@prefix : <http://shop.example.org/> .
@prefix math: <http://www.w3.org/2000/10/swap/math#> .

:widget :price 50 ; :discount 0.1 .

# Rule: calculate final price = price × (1 - discount)
{ ?Item :price ?P . ?Item :discount ?D .
  "1" math:minus ?D ?Factor .
  ?P math:times ?Factor ?Final }
    => { ?Item :finalPrice ?Final } .
```

Result: `:widget :finalPrice 45 .`

---

### String: Text Operations

**Namespace:** `http://www.w3.org/2000/10/swap/string#`

| Builtin | What it does | Example |
| :--- | :--- | :--- |
| `string:concatenation` | Join strings together | `("Hello" " " "World") string:concatenation ?R` → R="Hello World" |
| `string:contains` | Does text contain a substring? | `?Text string:contains "error"` → `true` if found |
| `string:length` | How many characters? | `?Text string:length ?N` → N=character count |
| `string:startsWith` | Does text start with a prefix? | `?Text string:startsWith "Dr."` → `true` or `false` |
| `string:endsWith` | Does text end with a suffix? | `?Email string:endsWith "@example.org"` → `true` or `false` |
| `string:equal` | Are two strings identical? | `?A string:equal ?B` → `true` if same text |
| `string:matches` | Regex match | `?Text string:matches "^[A-Z].*"` → `true` if starts with uppercase |
| `string:replace` | Regex replace | `?Text string:replace("old", "new") ?R` → R with substitutions |
| `string:substring` | Extract substring | `"hello" string:substring(1, 3) ?R` → R="ell" |

Source range: `builtins.py:150-186`

#### Full string example: Email validation

```n3
@prefix : <http://users.example.org/> .
@prefix str: <http://www.w3.org/2000/10/swap/string#> .

:user1 :email "alice@example.org" .
:user2 :email "bob@gmail.com" .

# Rule: flag emails from our domain
{ ?User :email ?E . ?E str:endsWith "@example.org" }
    => { ?User :isInternal true } .

# Rule: check email has content
{ ?User :email ?E . ?E str:length ?Len . ?Len math:greaterThan "5" }
    => { ?User :emailValid true } .
```

Results:
- `:user1 :isInternal true` (email ends with @example.org)
- `:user1 :emailValid true` (email is longer than 5 chars)
- `:user2 :emailValid true` (email is longer than 5 chars, but not internal)

---

### Time: Dates and Clocks

**Namespace:** `http://www.w3.org/2000/10/swap/time#`

| Builtin | What it does | Example |
| :--- | :--- | :--- |
| `time:now` | Current date and time | `time:now ?Now` → Now="2025-04-04T15:30:00" |
| `time:year` | Extract year from a date string | `"2025-03-15" time:year ?Y` → Y=2025 |
| `time:month` | Extract month | `"2025-03-15" time:month ?M` → M=3 |
| `time:day` | Extract day | `"2025-03-15" time:day ?D` → D=15 |
| `time:in-seconds` | Current Unix timestamp | `time:in-seconds ?T` → T=1712242200.0 |
| `time:hours` | Extract hours | `"2025-03-15T15:30:00" time:hours ?H` → H=15 |
| `time:minutes` | Extract minutes | `"2025-03-15T15:30:00" time:minutes ?M` → M=30 |
| `time:seconds` | Extract seconds | `"2025-03-15T15:30:45" time:seconds ?S` → S=45 |
| `time:localTime` | Current local time as ISO | `time:localTime ?T` → T="2025-04-04T15:30:00+01:00" |

Source range: `builtins.py:190-228,1081-1117`

#### Full time example: Late-night alerts

```n3
@prefix : <http://alerts.example.org/> .
@prefix time: <http://www.w3.org/2000/10/swap/time#> .
@prefix math: <http://www.w3.org/2000/10/swap/math#> .

# Rule: if it's after 10 PM, don't send notifications
{ time:now ?Now . ?Now time:month ?M . ?M math:equalTo "4" }
    => { :april :isCurrentMonth true } .
```

---

### List: Working with Ordered Data

**Namespace:** `http://www.w3.org/2000/10/swap/list#`

| Builtin | What it does | Example |
| :--- | :--- | :--- |
| `list:in` | Is an item in a list? | `:apple list:in (:apple :banana) ` → `true` |
| `list:length` | How many items in a list? | `(:a :b :c) list:length ?N` → N=3 |
| `list:car` | Return the first element | `_:list1 list:car ?First` → First = first item |
| `list:cdr` | Return the rest of a list | `_:list1 list:cdr ?Rest` → Rest = tail of list |
| `list:select` | Select nth element (1-indexed) | `_:list1 list:select "2" ?Item` → Item = 2nd element |
| `list:remove` | Remove element by index | Returns store triples without removed element |

Source range: `builtins.py:232-300,531-637`

#### Full list example: Shopping cart

```n3
@prefix : <http://shop.example.org/> .
@prefix list: <http://www.w3.org/2000/10/swap/list#> .

:order1 :items (:apple :banana :milk) .

# Rule: check if order contains a specific item
{ ?Order :items ?Items . :apple list:in ?Items }
    => { ?Order :hasApples true } .

# Rule: count items in the order
{ ?Order :items ?Items . ?Items list:length ?N }
    => { ?Order :itemCount ?N } .
```

Results:
- `:order1 :hasApples true`
- `:order1 :itemCount 3`

---

### Log: Engine Operations

**Namespace:** `http://www.w3.org/2000/10/swap/log#`

| Builtin | What it does | Example |
| :--- | :--- | :--- |
| `log:outputString` | Mark text for output | `?Msg log:outputString ?Out` → passes ?Msg through |
| `log:skolem` | Generate a unique ID | `?Entity log:skolem ?ID` → ID="_:sk-1" |
| `log:content` | Get all triples in the store | `log:content ?All` → all current triples |
| `log:equalTo` | Are two terms identical? | `?A log:equalTo ?B` → `true` if same |
| `log:uuid` | Generate a UUID | `log:uuid ?U` → U="550e8400-e29b-..." |
| `log:n3String` | Convert a term to N3 string | `:foo log:n3String ?S` → S=":foo" |
| `log:implies` | Check if premise implies conclusion | `?A log:implies ?B` → `true` if equal |
| `log:forAllIn` | Collect all bindings for a variable | Returns all store triples |
| `log:ask` | HTTP GET request (SSRF-protected) | `"http://example.org/data" log:ask ?Body` |
| `log:shell` | Execute safe command, return stdout | Alias for `e:shell` |
| `log:collectAllIn` | Collect all matching triples | Returns all store triples |

Source range: `builtins.py:303-327,814-840,1030-1072`

#### Full log example: Unique ticket generator

```n3
@prefix : <http://tickets.example.org/> .
@prefix log: <http://www.w3.org/2000/10/swap/log#> .

:issue1 :reported true .
:issue2 :reported true .

# Rule: assign a unique ID to each reported issue
{ ?Issue :reported true . ?Issue log:skolem ?ID }
    => { ?Issue :ticketId ?ID } .
```

Results:
- `:issue1 :ticketId _:sk-1`
- `:issue2 :ticketId _:sk-2`

Each issue gets a different unique ID.

---

### Type: Checking What Kind of Thing Something Is

**Namespace:** `http://www.w3.org/2000/10/swap/type#`

| Builtin | What it does | Example |
| :--- | :--- | :--- |
| `type:isLiteral` | Is this a text/value (not a name)? | `"hello" type:isLiteral ?R` → `true` |
| `type:isNumeric` | Is this a number? | `42 type:isNumeric ?R` → `true` |
| `type:str` | Convert to plain text | `:foo type:str ?R` → R=":foo" |
| `type:iri` | Convert text to a name/IRI | `"http://x.org/a" type:iri ?R` → R=<http://x.org/a> |

Source range: `builtins.py:331-361`

---

### Crypto: Hash Functions

**Namespace:** `http://www.w3.org/2000/10/swap/crypto#`

| Builtin | What it does | Example |
| :--- | :--- | :--- |
| `crypto:md5` | MD5 hash | `"hello" crypto:md5 ?H` → H="5d41402abc4b2a76b9719d911017c592" |
| `crypto:sha` | SHA-1 hash | `"hello" crypto:sha ?H` → SHA-1 hex string |
| `crypto:sha256` | SHA-256 hash | `"hello" crypto:sha256 ?H` → H="2cf24dba5fb0a3..." |
| `crypto:sha512` | SHA-512 hash | `"hello" crypto:sha512 ?H` → SHA-512 hex string |

Source range: `builtins.py:366-399`

---

### Graph: Named Graph Operations

**Namespace:** `http://www.w3.org/2000/10/swap/graph#`

| Builtin | What it does | Example |
| :--- | :--- | :--- |
| `graph:member` | Is a triple in a graph? | `:a :p :b graph:member ?R` → `true` if exists |
| `graph:length` | Number of triples in a graph | `:graph1 graph:length ?N` → N=triple count |
| `graph:difference` | Triples in A but not B | `:g1 :g2 graph:difference ?D` → D = A-B |
| `graph:intersection` | Triples common to both | `:g1 :g2 graph:intersection ?I` → I = A∩B |
| `graph:union` | All triples from both | `:g1 :g2 graph:union ?U` → U = A∪B |
| `graph:statement` | Construct a triple | `:a :p :b graph:statement ?T` → T=[Triple] |

Source range: `builtins.py:1124-1219`

---

### E: Dynamic Rules and Execution

**Namespace:** `http://eulersharp.sourceforge.net/2003/03swap/log-rules#`

| Builtin | What it does | Example |
| :--- | :--- | :--- |
| `e:calculate` | Evaluate safe expression (literals only) | `e:calculate("42") ?R` → R="42" |
| `e:findall` | Collect all store triples | `e:findall ?All` → all triples |
| `e:closure` | Check if formula is deductively closed | Returns `true` (simplified) |
| `e:becomes` | Retract old triple, assert new | `e:becomes(old, new)` → removes old, adds new |
| `e:transaction` | Atomic multi-triple assertion | `e:transaction(triple1, triple2)` |
| `e:exec` | Execute safe command, return exit code | `e:exec("ls -l /tmp") ?R` → R="0" |
| `e:shell` | Execute safe command, return stdout | `e:shell("echo hello") ?R` → R="hello\n" |
| `e:derive` | Call registered Python function | `e:derive("my_fn", arg1, arg2) ?R` |

Source range: `builtins.py:849-1025`

#### Safe command allowlist

`e:exec` and `e:shell` only permit these commands:

```
echo, date, uname, whoami, hostname, id, uptime,
cat, head, tail, wc, ls, find, stat, file, md5sum, sha256sum,
curl, wget, ping, dig, nslookup,
grep, awk, sed, sort, uniq, tr, cut,
bc, expr, df, free, ps
```

Commands not in this list are silently rejected. Shell injection is prevented by using `subprocess.run(..., shell=False)`.

---

### RIF/XPath Functions

**Namespace:** `http://www.w3.org/2007/XPath-functions#`

| Builtin | What it does | Example |
| :--- | :--- | :--- |
| `func:concat` | Concatenate strings | `func:concat("Hello", " ", "World") ?R` → R="Hello World" |
| `func:substring` | Extract substring (1-indexed) | `func:substring("hello world", 7, 5) ?R` → R="world" |
| `func:string-length` | String length | `func:string-length("hello") ?R` → R=5 |
| `func:upper-case` | Convert to uppercase | `func:upper-case("hello") ?R` → R="HELLO" |
| `func:lower-case` | Convert to lowercase | `func:lower-case("HELLO") ?R` → R="hello" |
| `func:contains` | String contains substring | `func:contains("hello world", "world") ?R` → R=`true` |
| `func:starts-with` | Starts with prefix | `func:starts-with("hello world", "hello") ?R` → R=`true` |
| `func:ends-with` | Ends with suffix | `func:ends-with("hello world", "world") ?R` → R=`true` |
| `func:substring-before` | Substring before delimiter | `func:substring-before("a:b", ":") ?R` → R="a" |
| `func:substring-after` | Substring after delimiter | `func:substring-after("a:b", ":") ?R` → R="b" |
| `func:translate` | Character translation | `func:translate("abc", "abc", "xyz") ?R` → R="xyz" |
| `func:normalize-space` | Normalize whitespace | `func:normalize-space("  hello   world  ") ?R` → R="hello world" |
| `func:tokenize` | Split string into list | `func:tokenize("a b c", " ") ?R` → R=list head |

Source range: `builtins.py:645-774`

### XPath Predicates

**Namespace:** `http://www.w3.org/2007/XPath-functions/pred#`

| Builtin | What it does | Example |
| :--- | :--- | :--- |
| `pred:equalTo` | Are two values equal? | `?X pred:equalTo ?Y` → `true` if X=Y |
| `pred:less-than` | Is first less than second? | `?X pred:less-than ?Y` → `true` if X<Y |
| `pred:greater-than` | Is first greater than second? | `?X pred:greater-than ?Y` → `true` if X>Y |
| `pred:matches` | Regex match | `?Text pred:matches "pattern" ?R` → `true` or `false` |

Source range: `builtins.py:777-807`

---

## Important Behavior

### Unground Arguments = Skip

If a builtin's arguments contain **variables** that haven't been assigned values yet, the builtin **skips** evaluation. It will be re-evaluated on the next pass if the variables become grounded.

```n3
{ ?X math:greaterThan ?Y } => { ?X :biggerThan ?Y } .
```

If `?X` and `?Y` have no numeric values from other patterns in the body, this builtin is skipped. This prevents errors and lets the engine continue with other rules.

### Builtins in the body only

Builtins are meant to appear in the **body** of a rule (before `=>`), not the head. They evaluate conditions or compute values; they don't create facts on their own. The result is used in the head through variable bindings.

### Multiple builtins in one rule

You can chain multiple builtins in a single rule body:

```n3
{ ?Item :price ?P .
  ?P math:times "0.9" ?Discounted .
  ?Discounted math:lessThan "100" }
    => { ?Item :onSale true } .
```

Each builtin is evaluated in order, and the result of one can feed into the next.

---

## Adding Your Own Builtins

If the built-in functions aren't enough, you can register your own:

```python
from pyeye import execute
from pyeye.term import Literal, Variable

def hash_fn(args, engine):
    """A custom hash function."""
    if any(isinstance(a, Variable) for a in args):
        return None  # skip if arguments aren't ready
    import hashlib
    return Literal(hashlib.sha256(args[0].value.encode()).hexdigest())

result = execute(
    data_strings=["@prefix : <http://ex.org/> .\n:msg :text \"hello\" ."],
    rule_strings=["@prefix : <http://ex.org/> .\n{?M :text ?T} => {?M :hash ?H} ."],
    builtins={"http://ex.org/hash": hash_fn},
)
```

### Custom Functions for e:derive

For `e:derive`, register functions that can be called by name from N3 rules:

```python
from pyeye.builtins import register_derive_function
from pyeye.term import Literal

def my_double(args, engine):
    """Double a number."""
    return Literal(str(float(args[0].value) * 2))

register_derive_function("double", my_double)
```

Then use in N3:

```n3
{ ?Item :value ?V } => { ?V e:derive("double", ?V) ?Doubled } .
```
