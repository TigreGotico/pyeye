"""
28 — Constraint Validation (SHACL-like)
=========================================
Validate RDF data against shape constraints and produce structured violation
reports — similar to SHACL (Shapes Constraint Language) but implemented
purely in N3 rules.

Constraints demonstrated:
  - Required property: every :Person must have :name
  - Required property: every :Person must have :email
  - Cardinality: every :Person must have exactly one :name (via collectAllIn + list:length)
  - Value type: :age must be a positive integer (> 0)

Concepts:
  - log:onNegativeSurface — fire if property is ABSENT
  - log:collectAllIn + list:length — count property values for cardinality
  - math:greaterThan — value type / range check
  - Structured violation triples: ?P :violation "message"
"""

from pyeye import execute

data = """
@prefix : <http://example.org/> .

# Valid person
:alice a :Person ; :name "Alice Smith" ; :email "alice@example.org" ; :age 30 .

# Missing email
:bob a :Person ; :name "Bob Jones" ; :age 25 .

# Missing name
:carol a :Person ; :email "carol@example.org" ; :age 22 .

# Has two names (cardinality violation)
:dave a :Person ; :name "Dave" ; :name "David" ; :email "dave@example.org" ; :age 40 .

# Missing name AND email
:eve a :Person ; :age 19 .

# Invalid age (zero is not a positive integer)
:frank a :Person ; :name "Frank" ; :email "frank@example.org" ; :age 0 .
"""

rules = """
@prefix :    <http://example.org/> .
@prefix log: <http://www.w3.org/2000/10/swap/log#> .
@prefix math: <http://www.w3.org/2000/10/swap/math#> .
@prefix list: <http://www.w3.org/2000/10/swap/list#> .

# --- Required property: :name ---
{
    ?P a :Person .
    _:n1 log:onNegativeSurface { ?P :name ?N }
}
    => { ?P :violation "Missing required property :name" } .

# --- Required property: :email ---
{
    ?P a :Person .
    _:n2 log:onNegativeSurface { ?P :email ?E }
}
    => { ?P :violation "Missing required property :email" } .

# --- Cardinality: exactly one :name ---
{
    ?P a :Person .
    (?N { ?P :name ?N } ?Names) log:collectAllIn ?Scope .
    ?Names list:length ?Count .
    ?Count math:greaterThan 1
}
    => { ?P :violation "Cardinality violation: :name must have exactly one value" } .

# --- Value type: :age must be > 0 ---
{
    ?P a :Person ; :age ?Age .
    _:n3 log:onNegativeSurface { ?Age math:greaterThan 0 }
}
    => { ?P :violation "Value constraint: :age must be a positive integer" } .

"""

result = execute(data_strings=[data], rule_strings=[rules])

# Collect results
violations = {}
valid = []

all_persons = {"alice", "bob", "carol", "dave", "eve", "frank"}

for line in result.triples.splitlines():
    line = line.strip().rstrip(" .")
    if ":violation" in line:
        parts = line.split(None, 2)
        person = parts[0].split(":")[-1]
        msg = parts[2].strip('"')
        violations.setdefault(person, []).append(msg)

# Anyone with no violations is valid
for p in all_persons:
    if p not in violations:
        valid.append(p)

print("=== SHACL-like Constraint Validation ===\n")

persons = ["alice", "bob", "carol", "dave", "eve", "frank"]
for p in persons:
    if p in violations:
        print(f"{p}: INVALID")
        for v in sorted(violations[p]):
            print(f"    violation: {v}")
    elif p in valid:
        print(f"{p}: valid")
    else:
        print(f"{p}: (no result)")

print()
print("Expected:")
print("  alice: valid")
print("  bob  : Missing email")
print("  carol: Missing name")
print("  dave : Cardinality violation (two names)")
print("  eve  : Missing name + email")
print("  frank: age must be positive integer")
