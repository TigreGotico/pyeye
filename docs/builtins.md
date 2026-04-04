# Builtins Reference

## What are builtins?

**Builtins** are built-in functions that the reasoner can call inside rule bodies. They let you do things like compare numbers, manipulate strings, check dates, and generate unique IDs — without writing any rules for them yourself.

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

### Example: String Operations

```n3
@prefix str: <http://www.w3.org/2000/10/swap/string#> .

{ ?Name str:startsWith "Dr." } => { ?Name :hasTitle true } .
```

If any name starts with "Dr.", mark it as having a title.

---

## All Builtins

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

### String: Text

**Namespace:** `http://www.w3.org/2000/10/swap/string#`

| Builtin | What it does | Example |
| :--- | :--- | :--- |
| `string:concatenation` | Join strings together | `("Hello" " " "World") string:concatenation ?R` → R="Hello World" |
| `string:contains` | Does text contain a substring? | `?Text string:contains "error"` → `true` if found |
| `string:length` | How many characters? | `?Text string:length ?N` → N=character count |
| `string:startsWith` | Does text start with a prefix? | `?Text string:startsWith "Dr."` → `true` or `false` |
| `string:endsWith` | Does text end with a suffix? | `?Email string:endsWith "@example.org"` → `true` or `false` |
| `string:equal` | Are two strings identical? | `?A string:equal ?B` → `true` if same text |

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
| `log:content` | Get all facts in the store | `log:content ?All` → all current triples |
| `log:equalTo` | Are two terms identical? | `?A log:equalTo ?B` → `true` if same |

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

Your custom function receives:
- `args` — a list of `Term` objects (the arguments from the rule body)
- `engine` — the reasoning engine (gives you access to the triple store)

Return a `Term` to bind the result to a variable, or `None` to skip.

---

## Source Code References

All builtins are defined in `pyeye/builtins.py`:

| Category | Namespace | Functions | Source |
| :--- | :--- | :--- | :--- |
| Math | `http://www.w3.org/2000/10/swap/math#` | 8 functions | `builtins.py:86-135` |
| String | `http://www.w3.org/2000/10/swap/string#` | 6 functions | `builtins.py:139-168` |
| Time | `http://www.w3.org/2000/10/swap/time#` | 5 functions | `builtins.py:171-200` |
| List | `http://www.w3.org/2000/10/swap/list#` | 2 functions | `builtins.py:205-271` |
| Log | `http://www.w3.org/2000/10/swap/log#` | 4 functions | `builtins.py:293-312` |
| Type | `http://www.w3.org/2000/10/swap/type#` | 4 functions | `builtins.py:316-339` |

The builtin protocol is defined at `pyeye/builtins.py:28`.
