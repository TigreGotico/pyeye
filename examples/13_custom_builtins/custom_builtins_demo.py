"""
13 — Custom Builtins
====================
pyeye's builtin registry is extensible. You can register Python functions
as custom predicates and use them in N3 rules just like math: or string:.

Concepts:
  - Builtin signature: fn(args: list[Term], engine) -> Term | None
  - The engine always calls: fn([input1, ..., inputN, output_var], engine)
  - args[-1] is the object (output variable or bound value)
  - args[:-1] are the inputs (from the subject: scalar or list expansion)
  - Return a Term on success (engine binds it to the output variable)
  - Return None on failure (pattern does not match)
  - builtins={"<iri>": my_fn} in execute()

Pattern for function-style builtins:
    ?S my:predicate ?Result
    → args = [resolved_S, Variable("Result")]
    → inputs = args[:-1] = [resolved_S]
    → return computed_value  (engine binds Result = computed_value)

Pattern for filter-style builtins (no output variable):
    ?S my:predicate ?Comparand
    → args = [resolved_S, resolved_comparand]
    → return Literal("true") to pass, None to fail
"""

from pyeye import execute
from pyeye.term import Literal, Variable, Term, NamedNode

# ---------------------------------------------------------------------------
# Helper: safely get inputs (strip trailing output Variable)
# ---------------------------------------------------------------------------

def _inputs(args: list[Term]) -> list[Term]:
    """Return input args, stripping the trailing output variable if present."""
    if len(args) >= 2 and isinstance(args[-1], Variable):
        return args[:-1]
    return args


# ---------------------------------------------------------------------------
# Custom builtin 1: my:isPalindrome
# Filter: succeeds iff the subject string is a palindrome.
# ---------------------------------------------------------------------------

def is_palindrome(args: list[Term], engine) -> Term | None:
    """Filter: return Literal("true") if args[0] is a palindrome."""
    if not args or isinstance(args[0], Variable):
        return None
    s = str(args[0].value).lower().replace(" ", "")
    if s == s[::-1]:
        return Literal("true", datatype=NamedNode("http://www.w3.org/2001/XMLSchema#boolean"))
    return None


# ---------------------------------------------------------------------------
# Custom builtin 2: my:rot13
# Function: computes ROT-13 of args[0], binds result to args[-1].
# ---------------------------------------------------------------------------

import codecs

def rot13_builtin(args: list[Term], engine) -> Term | None:
    """Compute ROT-13 of the input string and return result."""
    inputs = _inputs(args)
    if not inputs or isinstance(inputs[0], Variable):
        return None
    encoded = codecs.encode(str(inputs[0].value), "rot_13")
    return Literal(encoded)


# ---------------------------------------------------------------------------
# Custom builtin 3: my:wordCount
# Function: counts words in args[0], returns integer Literal.
# ---------------------------------------------------------------------------

def word_count(args: list[Term], engine) -> Term | None:
    """Count words in the input string."""
    inputs = _inputs(args)
    if not inputs or isinstance(inputs[0], Variable):
        return None
    n = len(str(inputs[0].value).split())
    return Literal(str(n), datatype=NamedNode("http://www.w3.org/2001/XMLSchema#integer"))


# ---------------------------------------------------------------------------
# Register and run
# ---------------------------------------------------------------------------

CUSTOM_BUILTINS = {
    "http://example.org/builtins#isPalindrome": is_palindrome,
    "http://example.org/builtins#rot13":        rot13_builtin,
    "http://example.org/builtins#wordCount":    word_count,
}

# Example 1: Palindrome detection
print("=== Palindrome Detection ===")

data = """
@prefix : <http://example.org/words#> .

:w1 :text "racecar" .
:w2 :text "hello" .
:w3 :text "level" .
:w4 :text "world" .
"""

rules = """
@prefix : <http://example.org/words#> .
@prefix my: <http://example.org/builtins#> .

{
    ?W :text ?T .
    ?T my:isPalindrome ?T
}
    => { ?W :isPalindrome true } .
"""

result = execute(
    data_strings=[data],
    rule_strings=[rules],
    builtins=CUSTOM_BUILTINS,
)
print(result.triples)


# Example 2: ROT-13 encoding
print("\n=== ROT-13 Encoding ===")

data2 = """
@prefix : <http://example.org/msg#> .

:msg1 :plaintext "Hello World" .
:msg2 :plaintext "Attack at dawn" .
"""

rules2 = """
@prefix : <http://example.org/msg#> .
@prefix my: <http://example.org/builtins#> .

{
    ?M :plaintext ?T .
    ?T my:rot13 ?Encoded
}
    => { ?M :encoded ?Encoded } .
"""

result2 = execute(
    data_strings=[data2],
    rule_strings=[rules2],
    builtins=CUSTOM_BUILTINS,
)
print(result2.triples)


# Example 3: Word count + classification
print("\n=== Word Count ===")

data3 = """
@prefix : <http://example.org/docs#> .

:doc1 :body "The quick brown fox jumps over the lazy dog" .
:doc2 :body "Hello world" .
"""

rules3 = """
@prefix : <http://example.org/docs#> .
@prefix my:   <http://example.org/builtins#> .
@prefix math: <http://www.w3.org/2000/10/swap/math#> .

{
    ?D :body ?T .
    ?T my:wordCount ?N
}
    => { ?D :wordCount ?N } .

{
    ?D :wordCount ?N .
    ?N math:greaterThan 5
}
    => { ?D :isLong true } .
"""

result3 = execute(
    data_strings=[data3],
    rule_strings=[rules3],
    builtins=CUSTOM_BUILTINS,
)
print(result3.triples)
