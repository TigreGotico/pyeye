"""
20 — URI Manipulation & Typed Literals
=======================================
log:uri converts any term to its string representation (IRI string).
log:dtlit constructs typed literals (combining a value with a datatype IRI).

Builtins:
  - ?Term log:uri ?String      — get the IRI string of any NamedNode
  - (?Val ?DtIRI) log:dtlit ?TypedLit — create a typed literal

Combined with string:concatenation, log:uri lets you:
  - Build new IRIs from existing ones
  - Extract namespace prefixes
  - Construct canonical string representations

log:dtlit lets you:
  - Attach XSD datatypes to string values at rule time
  - Convert bare strings into proper integers, booleans, dates, etc.
"""

from pyeye import execute

# Example 1: Extract IRI string and build a derived IRI
print("=== IRI String Extraction ===")

data = """
@prefix : <http://example.org/> .
@prefix schema: <https://schema.org/> .

:paris   a schema:City ; schema:name "Paris" .
:london  a schema:City ; schema:name "London" .
:berlin  a schema:City ; schema:name "Berlin" .
"""

rules = """
@prefix : <http://example.org/> .
@prefix schema: <https://schema.org/> .
@prefix log:    <http://www.w3.org/2000/10/swap/log#> .
@prefix string: <http://www.w3.org/2000/10/swap/string#> .

# Build a Wikipedia URL from each city's IRI string
{
    ?City a schema:City .
    ?City schema:name ?Name .
    ?Name string:upperCase ?Up .
    ("https://en.wikipedia.org/wiki/" ?Name) string:concatenation ?URL
}
    => { ?City schema:wikipediaUrl ?URL } .
"""

result = execute(data_strings=[data], rule_strings=[rules])
print(result.triples)


# Example 2: Typed literals — turn string scores into xsd:integer
print("\n=== Typed Literals (log:dtlit) ===")

data2 = """
@prefix : <http://example.org/> .

:alice :rawScore "95" .
:bob   :rawScore "82" .
:carol :rawScore "78" .
"""

rules2 = """
@prefix : <http://example.org/> .
@prefix log: <http://www.w3.org/2000/10/swap/log#> .
@prefix math: <http://www.w3.org/2000/10/swap/math#> .

# Convert string scores to typed xsd:integer literals
{
    ?P :rawScore ?S .
    (?S <http://www.w3.org/2001/XMLSchema#integer>) log:dtlit ?Typed
}
    => { ?P :score ?Typed } .

# Now we can do math on the typed values
{
    ?P :score ?N .
    ?N math:greaterThan 90
}
    => { ?P :grade "A" } .

{
    ?P :score ?N .
    ?N math:greaterThan 79 .
    ?N math:lessThan 91
}
    => { ?P :grade "B" } .
"""

result2 = execute(data_strings=[data2], rule_strings=[rules2])
print(result2.triples)


# Example 3: Using log:uri for IRI-aware rules
print("\n=== IRI to String Conversion ===")

data3 = """
@prefix prod: <http://example.org/product#> .

prod:widget  prod:category prod:electronics .
prod:gadget  prod:category prod:electronics .
prod:notebook prod:category prod:stationery .
"""

rules3 = """
@prefix prod:   <http://example.org/product#> .
@prefix log:    <http://www.w3.org/2000/10/swap/log#> .

# Extract the local name from a category IRI using log:localName
{
    ?P prod:category ?Cat .
    ?Cat log:localName ?LocalName
}
    => { ?P prod:categoryLabel ?LocalName } .
"""

result3 = execute(data_strings=[data3], rule_strings=[rules3])
print(result3.triples)
