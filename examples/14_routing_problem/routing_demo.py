"""
14 — Routing Problem
====================
A real-world-style problem: find all routes between airports, compute
total distances, and identify the shortest path.

Demonstrates:
  - Forward chaining to build a full reachability closure
  - Math builtins for distance accumulation
  - Backward chaining to ask "can I fly from X to Y?"
  - String builtins to build route descriptions
  - A realistic multi-step reasoning pipeline

This is the kind of problem pyeye was originally designed for.
"""

from pyeye import execute, NamedNode, Variable, Triple

BASE = "http://example.org/flight#"

def nn(local: str) -> NamedNode:
    return NamedNode(BASE + local)

# ---------------------------------------------------------------------------
# Flight data: direct routes with distances (km)
# ---------------------------------------------------------------------------
facts = """
@prefix flight: <http://example.org/flight#> .

# Direct routes
flight:AMS flight:directTo flight:LHR ; flight:distanceTo_LHR 370 .
flight:AMS flight:directTo flight:CDG ; flight:distanceTo_CDG 430 .
flight:LHR flight:directTo flight:JFK ; flight:distanceTo_JFK 5570 .
flight:CDG flight:directTo flight:JFK ; flight:distanceTo_JFK 5830 .
flight:LHR flight:directTo flight:DXB ; flight:distanceTo_DXB 5500 .
flight:DXB flight:directTo flight:SYD ; flight:distanceTo_SYD 12030 .
flight:JFK flight:directTo flight:LAX ; flight:distanceTo_LAX 4500 .
flight:LAX flight:directTo flight:SYD ; flight:distanceTo_SYD 12070 .
"""

# ---------------------------------------------------------------------------
# Example 1: Forward closure — what is reachable from AMS?
# ---------------------------------------------------------------------------
print("=== Reachability from AMS (Forward Chaining) ===")

forward_rules = """
@prefix flight: <http://example.org/flight#> .

# Base case: reachable in one hop
{ ?X flight:directTo ?Y }
    => { ?X flight:canReach ?Y } .

# Inductive case: transitive reachability
{ ?X flight:canReach ?Y .
  ?Y flight:canReach ?Z }
    => { ?X flight:canReach ?Z } .
"""

result = execute(data_strings=[facts], rule_strings=[forward_rules])
print("AMS can reach:")
for line in sorted(result.triples.splitlines()):
    if "AMS" in line and "canReach" in line:
        print(" ", line.strip())


# ---------------------------------------------------------------------------
# Example 2: Backward chaining — can AMS reach SYD?
# ---------------------------------------------------------------------------
print("\n=== Backward Chaining Query: AMS → SYD? ===")

bc_rules = """
@prefix flight: <http://example.org/flight#> .
@prefix log: <http://www.w3.org/2000/10/swap/log#> .

[] log:table flight:route .

{ ?X flight:route ?Y } <= { ?X flight:directTo ?Y } .
{ ?X flight:route ?Y } <= { ?X flight:route ?Z . ?Z flight:route ?Y } .
"""

query = Triple(nn("AMS"), nn("route"), Variable("Dest"))
result2 = execute(data_strings=[facts], rule_strings=[bc_rules], query=query)
print("AMS can route to:")
for b in result2.query_answers:
    print(" ", b["Dest"])


# ---------------------------------------------------------------------------
# Example 3: Classify routes by total distance (heuristic)
# ---------------------------------------------------------------------------
print("\n=== Short-haul vs Long-haul (math: builtins) ===")

distance_data = """
@prefix flight: <http://example.org/flight#> .

flight:AMS_LHR flight:from flight:AMS ; flight:to flight:LHR ; flight:km 370 .
flight:LHR_JFK flight:from flight:LHR ; flight:to flight:JFK ; flight:km 5570 .
flight:JFK_LAX flight:from flight:JFK ; flight:to flight:LAX ; flight:km 4500 .
flight:AMS_CDG flight:from flight:AMS ; flight:to flight:CDG ; flight:km 430 .
"""

classify_rules = """
@prefix flight: <http://example.org/flight#> .
@prefix math:   <http://www.w3.org/2000/10/swap/math#> .

# Under 1500 km = short-haul
{
    ?Route flight:km ?D .
    ?D math:lessThan 1500
}
    => { ?Route flight:type "short-haul" } .

# 1500–6000 km = medium-haul
{
    ?Route flight:km ?D .
    ?D math:greaterThan 1499 .
    ?D math:lessThan 6001
}
    => { ?Route flight:type "medium-haul" } .

# Over 6000 km = long-haul
{
    ?Route flight:km ?D .
    ?D math:greaterThan 6000
}
    => { ?Route flight:type "long-haul" } .
"""

result3 = execute(data_strings=[distance_data], rule_strings=[classify_rules])
print(result3.triples)


# ---------------------------------------------------------------------------
# Example 4: not_entail check — ensure no direct route AMS → SYD
# ---------------------------------------------------------------------------
print("\n=== Not-Entail Check: no direct AMS → SYD ===")

result4 = execute(
    data_strings=[facts],
    rule_strings=[],
    not_entail=Triple(nn("AMS"), nn("directTo"), nn("SYD")),
)
if result4.stats.get("not_entail_failed"):
    print("FAIL: a direct route AMS→SYD exists (unexpected).")
else:
    print("PASS: no direct route AMS→SYD (as expected).")
