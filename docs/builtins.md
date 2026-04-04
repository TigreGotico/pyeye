# Builtins Reference

**Source:** `BUILTIN_REGISTRY` — `pyeye/builtins.py:336`

Each builtin is a callable registered under its full IRI. Builtins appear in rule bodies and are evaluated when all their arguments are ground. If arguments contain unbound variables, the builtin is skipped and re-evaluated on the next pass.

## Calling Convention

In Phase 1, builtins are invoked as triple patterns in rule bodies where the **predicate** is the builtin IRI. The **subject** provides the first argument(s), and the **object** provides the last argument or the result variable.

### Scalar args (subject + object)

```n3
{ ?V math:greaterThan "5"^^xsd:integer } => { ... }
```

Here `?V` and `"5"` are the two arguments to `math:greaterThan`.

### List args (RDF list as subject)

```n3
{ ("hello" "world") string:concatenation ?Result } => { ... }
```

The RDF list `( "hello" "world" )` is expanded into individual arguments.

---

## Math Builtins

**Namespace:** `http://www.w3.org/2000/10/swap/math#`

| Builtin | Arity | Arguments | Returns | Source |
| :--- | :--- | :--- | :--- | :--- |
| `math:equalTo` | 2 | `num1`, `num2` | `xsd:boolean` | `builtins.py:86` |
| `math:lessThan` | 2 | `num1`, `num2` | `xsd:boolean` | `builtins.py:92` |
| `math:greaterThan` | 2 | `num1`, `num2` | `xsd:boolean` | `builtins.py:98` |
| `math:notEqualTo` | 2 | `num1`, `num2` | `xsd:boolean` | `builtins.py:104` |
| `math:plus` | 2 | `num1`, `num2` | `xsd:double` | `builtins.py:110` |
| `math:minus` | 2 | `num1`, `num2` | `xsd:double` | `builtins.py:116` |
| `math:times` | 2 | `num1`, `num2` | `xsd:double` | `builtins.py:122` |
| `math:divide` | 2 | `num1`, `num2` | `xsd:double` (or skip if denom=0) | `builtins.py:128` |

### Examples

```n3
@prefix math: <http://www.w3.org/2000/10/swap/math#> .
@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .

# Check if temperature is above threshold
{ ?Temp math:greaterThan "100"^^xsd:integer } => { ?Temp :isBoiling true } .

# Compute sum
{ ?A math:plus ?B } => { ?Sum :result ?Sum } .
```

---

## String Builtins

**Namespace:** `http://www.w3.org/2000/10/swap/string#`

| Builtin | Arity | Arguments | Returns | Source |
| :--- | :--- | :--- | :--- | :--- |
| `string:concatenation` | 2+ | `str1`, `str2`, ... | concatenated string | `builtins.py:139` |
| `string:contains` | 2 | `haystack`, `needle` | `xsd:boolean` | `builtins.py:144` |
| `string:length` | 1 | `str` | `xsd:integer` | `builtins.py:149` |
| `string:startsWith` | 2 | `str`, `prefix` | `xsd:boolean` | `builtins.py:154` |
| `string:endsWith` | 2 | `str`, `suffix` | `xsd:boolean` | `builtins.py:159` |
| `string:equal` | 2 | `str1`, `str2` | `xsd:boolean` | `builtins.py:164` |

### Examples

```n3
@prefix str: <http://www.w3.org/2000/10/swap/string#> .

# Check if name starts with "Dr."
{ ?Name str:startsWith "Dr." } => { ?Name :hasTitle true } .

# String length
{ ?Name str:length ?Len } => { ?Name :charCount ?Len } .
```

---

## Time Builtins

**Namespace:** `http://www.w3.org/2000/10/swap/time#`

| Builtin | Arity | Arguments | Returns | Source |
| :--- | :--- | :--- | :--- | :--- |
| `time:now` | 0 | — | current datetime string | `builtins.py:171` |
| `time:year` | 1 | `datetime` (ISO) | `xsd:integer` | `builtins.py:175` |
| `time:month` | 1 | `datetime` (ISO) | `xsd:integer` | `builtins.py:182` |
| `time:day` | 1 | `datetime` (ISO) | `xsd:integer` | `builtins.py:189` |
| `time:in-seconds` | 0 | — | Unix timestamp (double) | `builtins.py:196` |

### Examples

```n3
@prefix time: <http://www.w3.org/2000/10/swap/time#> .

# Extract year from a date
{ "2025-03-15T10:30:00" time:year ?Y } => { :event :occurredIn ?Y } .
```

---

## List Builtins

**Namespace:** `http://www.w3.org/2000/10/swap/list#`

| Builtin | Arity | Arguments | Returns | Source |
| :--- | :--- | :--- | :--- | :--- |
| `list:in` | 2 | `item`, `list-head` | `xsd:boolean` | `builtins.py:205` |
| `list:length` | 1 | `list-head` | `xsd:integer` | `builtins.py:237` |

### Examples

```n3
@prefix list: <http://www.w3.org/2000/10/swap/list#> .

# Check membership
{ :apple list:in (:apple :banana :cherry) } => { :apple :inFruitBasket true } .

# List length
{ ?List list:length ?N } => { :basket :itemCount ?N } .
```

---

## Log Builtins

**Namespace:** `http://www.w3.org/2000/10/swap/log#`

| Builtin | Arity | Arguments | Returns | Source |
| :--- | :--- | :--- | :--- | :--- |
| `log:outputString` | 1 | `string` | the string (marked for output) | `builtins.py:293` |
| `log:skolem` | 1 | any subject term | fresh `Existential` (skolem) | `builtins.py:299` |
| `log:content` | 0 | — | all triples in store | `builtins.py:305` |
| `log:equalTo` | 2 | `term1`, `term2` | `xsd:boolean` | `builtins.py:309` |

### Examples

```n3
@prefix log: <http://www.w3.org/2000/10/swap/log#> .

# Generate a unique ID
{ ?Entity log:skolem ?ID } => { ?Entity :assignedId ?ID } .

# Term equality
{ ?A log:equalTo ?B } => { ?A :sameAs ?B } .
```

---

## Type Builtins

**Namespace:** `http://www.w3.org/2000/10/swap/type#`

| Builtin | Arity | Arguments | Returns | Source |
| :--- | :--- | :--- | :--- | :--- |
| `type:isLiteral` | 1 | `term` | `xsd:boolean` | `builtins.py:316` |
| `type:isNumeric` | 1 | `term` | `xsd:boolean` | `builtins.py:321` |
| `type:str` | 1 | `term` | plain string literal | `builtins.py:330` |
| `type:iri` | 1 | `string` | `NamedNode` | `builtins.py:335` |

---

## Custom Builtins

Register custom builtins via the `builtins` parameter of `execute()`:

```python
from pyeye import execute
from pyeye.term import Literal, Variable

def my_builtin(args, engine):
    if any(isinstance(a, Variable) for a in args):
        return None  # skip if unground
    # ... compute result ...
    return Literal("result")  # or list[Triple] to assert

result = execute(
    data_strings=["..."],
    rule_strings=["..."],
    builtins={"http://my.org/custom": my_builtin},
)
```

**Builtin protocol** — `Builtin` — `pyeye/builtins.py:28`:

```python
class Builtin(Protocol):
    def __call__(self, args: list[Term], engine: EngineProto) -> Term | list[Triple] | None:
        ...
```

| Return type | Behavior |
| :--- | :--- |
| `Term` | Function-style: result is compared with the pattern object or bound to a variable |
| `list[Triple]` | Predicate-style: triples are asserted into the store |
| `None` | Skip: arguments not yet ground, or condition not met |
