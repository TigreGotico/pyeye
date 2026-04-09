"""
04 — String Builtins
====================
Use the string: namespace for text manipulation inside rules.

Concepts:
  - string:concatenation   — join strings
  - string:length          — string length
  - string:upperCase       — uppercase
  - string:lowerCase       — lowercase
  - string:contains        — substring test
  - string:startsWith      — prefix test
  - string:matches         — regex test
  - string:replace         — substitute

Builtin input syntax:
    { (?a ?b) string:concatenation ?result }   → result = a + b
    { ?s string:length ?n }                    → n = len(s)
    { ?s string:contains ?sub }               → filter: sub in s
"""

from pyeye import execute

# Example 1: Build full names from first/last
print("=== Full Name Assembly ===")

data = """
@prefix : <http://example.org/people#> .

:alice :firstName "Alice" ; :lastName "Smith" .
:bob   :firstName "Bob"   ; :lastName "Jones" .
:carol :firstName "Carol" ; :lastName "Williams" .
"""

rules = """
@prefix : <http://example.org/people#> .
@prefix string: <http://www.w3.org/2000/10/swap/string#> .

{
    ?P :firstName ?F .
    ?P :lastName ?L .
    (?F " " ?L) string:concatenation ?Full
}
    => { ?P :fullName ?Full } .
"""

result = execute(data_strings=[data], rule_strings=[rules])
print(result.triples)


# Example 2: Tag classification using string patterns
print("\n=== Tag Classification ===")

data2 = """
@prefix : <http://example.org/tags#> .

:post1 :tag "python-tutorial" .
:post2 :tag "java-spring-boot" .
:post3 :tag "python-advanced" .
:post4 :tag "rust-systems" .
"""

rules2 = """
@prefix : <http://example.org/tags#> .
@prefix string: <http://www.w3.org/2000/10/swap/string#> .

# Posts tagged "python-*" are Python content
{
    ?Post :tag ?T .
    ?T string:startsWith "python"
}
    => { ?Post :language "Python" } .

# Posts tagged "*-tutorial" are beginner content
{
    ?Post :tag ?T .
    ?T string:matches ".*-tutorial$"
}
    => { ?Post :level "beginner" } .
"""

result2 = execute(data_strings=[data2], rule_strings=[rules2])
print(result2.triples)


# Example 3: Build IRIs from string parts
print("\n=== IRI Construction ===")

data3 = """
@prefix : <http://example.org/> .

:product1 :category "electronics" ; :id "42" .
:product2 :category "books"       ; :id "17" .
"""

rules3 = """
@prefix : <http://example.org/> .
@prefix string: <http://www.w3.org/2000/10/swap/string#> .

{
    ?P :category ?Cat .
    ?P :id ?Id .
    ("http://example.org/" ?Cat "/" ?Id) string:concatenation ?URL
}
    => { ?P :canonicalUrl ?URL } .
"""

result3 = execute(data_strings=[data3], rule_strings=[rules3])
print(result3.triples)
