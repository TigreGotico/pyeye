"""
05 — List Builtins
==================
RDF lists and the list: namespace.

Concepts:
  - RDF list syntax: (:a :b :c)
  - list:length    — count elements
  - list:in        — filter: test if a *known* item is in a list
  - list:select    — get element at 1-based index
  - list:member    — enumerate elements (or test membership)
  - list:first     — head of list

Note on list:in — it requires both the item and the list to be bound.
To iterate over list members, use list:member with an unbound item.

Note on RDF lists: a list literal like (:a :b :c) is stored as a native
list value; the list: builtins operate on it directly.
"""

from pyeye import execute

# Example 1: List length
print("=== List Length ===")

data = """
@prefix : <http://example.org/> .

:team1 :members (:alice :bob :carol) .
:team2 :members (:dave :eve) .
"""

rules = """
@prefix : <http://example.org/> .
@prefix list: <http://www.w3.org/2000/10/swap/list#> .
@prefix math: <http://www.w3.org/2000/10/swap/math#> .

# Count members
{
    ?Team :members ?List .
    ?List list:length ?N
}
    => { ?Team :size ?N } .

# Large teams (>2 members)
{
    ?Team :size ?N .
    ?N math:greaterThan 2
}
    => { ?Team :isLarge true } .
"""

result = execute(data_strings=[data], rule_strings=[rules])
print(result.triples)


# Example 2: list:in as membership filter
print("\n=== Membership Test (filter) ===")

data2 = """
@prefix : <http://example.org/> .

:team    :members (:alice :bob :carol) .
:request :user    :alice .
:request :user    :dave .    # not in team
"""

rules2 = """
@prefix : <http://example.org/> .
@prefix list: <http://www.w3.org/2000/10/swap/list#> .

# Grant access only if user is in the team member list
{
    :team :members ?List .
    ?Request :user ?U .
    ?U list:in ?List        # filter: succeeds only if U is in List
}
    => { ?Request :accessGranted true } .
"""

result2 = execute(data_strings=[data2], rule_strings=[rules2])
print(result2.triples)
# Expect: only alice's request grants access


# Example 3: list:select — get element at index (1-based)
print("\n=== Element at Index (list:select, 1-based) ===")

data3 = """
@prefix : <http://example.org/> .

:board :directors (:alice :bob :carol :dave) .
"""

rules3 = """
@prefix : <http://example.org/> .
@prefix list: <http://www.w3.org/2000/10/swap/list#> .

# First director (index 1) is chair
{
    ?B :directors ?List .
    (?List 1) list:select ?Chair
}
    => { ?B :chair ?Chair } .

# Second director (index 2) is vice-chair
{
    ?B :directors ?List .
    (?List 2) list:select ?ViceChair
}
    => { ?B :viceChair ?ViceChair } .
"""

result3 = execute(data_strings=[data3], rule_strings=[rules3])
print(result3.triples)


# Example 4: Enumerate list members and assert them individually
print("\n=== Enumerate Members & Assert Individually ===")
# list:member yields one binding per list element when the item is unbound.

data4 = """
@prefix : <http://example.org/> .

:playlist :tracks (:trackA :trackB :trackC) .
"""

rules4 = """
@prefix : <http://example.org/> .
@prefix list: <http://www.w3.org/2000/10/swap/list#> .

# One :hasTrack fact per list element
{
    ?PL :tracks ?L .
    ?L list:member ?T
}
    => { ?PL :hasTrack ?T } .

# And the total count
{
    ?PL :tracks ?L .
    ?L list:length ?N
}
    => { ?PL :trackCount ?N } .
"""

result4 = execute(data_strings=[data4], rule_strings=[rules4])
print(result4.triples)
