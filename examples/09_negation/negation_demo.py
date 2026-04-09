"""
09 — Negation as Failure (BLOGIC)
==================================
log:onNegativeSurface introduces negation: a sub-formula that must NOT
be provable for the containing rule to fire.

Concepts:
  - log:onNegativeSurface { ... } — succeeds iff formula is NOT derivable
  - Closed-world assumption: anything not known is assumed false
  - _:b is the blank node that "holds" the negative surface
  - Typically combined with positive patterns in the rule body

Syntax:
    {
        ?X :someProperty ?V .
        _:neg log:onNegativeSurface { ?X :otherProperty ?W }
    } => { ?X :result ... } .

The negative surface fires when the inner formula { ?X :otherProperty ?W }
is NOT derivable from the store.
"""

from pyeye import execute

# Example 1: Default values — apply if no override exists
print("=== Default Values ===")

data = """
@prefix : <http://example.org/config#> .

# Some items have an explicit timeout; others don't
:serviceA :timeout 30 .
:serviceB :timeout 60 .
:serviceC :name "svc-c" .   # No timeout!
:serviceD :name "svc-d" .   # No timeout!
"""

rules = """
@prefix : <http://example.org/config#> .
@prefix log: <http://www.w3.org/2000/10/swap/log#> .

# If a service has no explicit timeout, set default = 15
{
    ?Svc :name ?N .
    _:neg log:onNegativeSurface { ?Svc :timeout ?Any }
}
    => { ?Svc :timeout 15 } .
"""

result = execute(data_strings=[data], rule_strings=[rules], pass_mode=True)
for line in sorted(result.triples.splitlines()):
    if "timeout" in line:
        print(line)


# Example 2: Access control — allow if not blocked
print("\n=== Access Control ===")

data2 = """
@prefix ac: <http://example.org/ac#> .

ac:alice ac:role "admin" .
ac:bob   ac:role "user" .
ac:carol ac:role "user" .

# bob is explicitly banned from the report endpoint
ac:bob   ac:banned ac:reportEndpoint .
"""

rules2 = """
@prefix ac: <http://example.org/ac#> .
@prefix log: <http://www.w3.org/2000/10/swap/log#> .

# A user can access a resource if they have a role AND are not banned
{
    ?User ac:role ?R .
    _:neg log:onNegativeSurface { ?User ac:banned ac:reportEndpoint }
}
    => { ?User ac:canAccess ac:reportEndpoint } .
"""

result2 = execute(data_strings=[data2], rule_strings=[rules2])
print(result2.triples)
# Expect: :alice and :carol can access, not :bob


# Example 3: Mark incomplete records
print("\n=== Incomplete Records ===")

data3 = """
@prefix : <http://example.org/records#> .

:person1 :firstName "Alice" ; :lastName "Smith" ; :email "alice@example.org" .
:person2 :firstName "Bob" ; :lastName "Jones" .          # Missing email
:person3 :firstName "Carol" .                             # Missing last name + email
"""

rules3 = """
@prefix : <http://example.org/records#> .
@prefix log: <http://www.w3.org/2000/10/swap/log#> .

# Incomplete if email is missing
{
    ?P :firstName ?F .
    _:neg log:onNegativeSurface { ?P :email ?E }
}
    => { ?P :status "incomplete" } .

# Complete if all three fields present
{
    ?P :firstName ?F .
    ?P :lastName ?L .
    ?P :email ?E
}
    => { ?P :status "complete" } .
"""

result3 = execute(data_strings=[data3], rule_strings=[rules3])
print(result3.triples)
