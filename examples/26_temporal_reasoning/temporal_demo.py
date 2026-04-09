"""
26 — Temporal Reasoning
========================
Reason about time intervals expressed as integer minutes since midnight.
Detect meeting conflicts, check business-hours compliance, and order events.

Concepts:
  - Integer timestamps (minutes since midnight: 540 = 9am, 1080 = 6pm)
  - Overlap detection: two intervals [s1,e1] and [s2,e2] overlap iff s1<e2 AND s2<e1
  - Negation: outside business hours if start < 540 OR end > 1080
  - math:greaterThan / math:lessThan for comparisons
  - log:notEqualTo to avoid self-comparison
"""

from pyeye import execute

BASE = "http://example.org/cal#"

# ---------------------------------------------------------------------------
# Meeting data: start/end in minutes since midnight
# ---------------------------------------------------------------------------
data = """
@prefix cal: <http://example.org/cal#> .

cal:standup     a cal:Meeting ; cal:start 540  ; cal:end 570 .   # 9:00–9:30
cal:planning    a cal:Meeting ; cal:start 560  ; cal:end 660 .   # 9:20–11:00  ← conflicts with standup
cal:lunch       a cal:Meeting ; cal:start 720  ; cal:end 780 .   # 12:00–13:00
cal:review      a cal:Meeting ; cal:start 750  ; cal:end 840 .   # 12:30–14:00 ← conflicts with lunch
cal:afterhours  a cal:Meeting ; cal:start 1050 ; cal:end 1140 .  # 17:30–19:00 ← outside hours
cal:early       a cal:Meeting ; cal:start 480  ; cal:end 540 .   # 8:00–9:00   ← outside hours (starts before 9)
cal:solo        a cal:Meeting ; cal:start 900  ; cal:end 960 .   # 15:00–16:00 ← fine
"""

# ---------------------------------------------------------------------------
# Rules
# ---------------------------------------------------------------------------
rules = """
@prefix cal:  <http://example.org/cal#> .
@prefix math: <http://www.w3.org/2000/10/swap/math#> .
@prefix log:  <http://www.w3.org/2000/10/swap/log#> .

# Two distinct meetings conflict if their intervals overlap
# Overlap: S1 < E2  AND  S2 < E1
{
    ?M1 a cal:Meeting ; cal:start ?S1 ; cal:end ?E1 .
    ?M2 a cal:Meeting ; cal:start ?S2 ; cal:end ?E2 .
    ?M1 log:notEqualTo ?M2 .
    ?S1 math:lessThan ?E2 .
    ?S2 math:lessThan ?E1
}
    => { ?M1 cal:conflictsWith ?M2 } .

# Outside business hours: starts before 9am (540)
{
    ?M a cal:Meeting ; cal:start ?S .
    ?S math:lessThan 540
}
    => { ?M cal:outsideHours "starts before 9am" } .

# Outside business hours: ends after 6pm (1080)
{
    ?M a cal:Meeting ; cal:end ?E .
    ?E math:greaterThan 1080
}
    => { ?M cal:outsideHours "ends after 6pm" } .
"""

result = execute(data_strings=[data], rule_strings=[rules])

# Parse and display results
conflicts = {}
outside = {}

for line in result.triples.splitlines():
    line = line.strip().rstrip(" .")
    if "cal:conflictsWith" in line:
        parts = line.split()
        m1 = parts[0].split(":")[-1]
        m2 = parts[2].split(":")[-1]
        conflicts.setdefault(m1, []).append(m2)
    if "cal:outsideHours" in line:
        parts = line.split(None, 2)
        mtg = parts[0].split(":")[-1]
        reason = parts[2].strip('"')
        outside[mtg] = reason

print("=== Temporal Reasoning: Meeting Scheduler ===\n")

print("Conflict pairs (each shown once):")
seen = set()
for m1, others in sorted(conflicts.items()):
    for m2 in sorted(others):
        pair = tuple(sorted([m1, m2]))
        if pair not in seen:
            seen.add(pair)
            print(f"  {pair[0]}  ↔  {pair[1]}")

print(f"\nExpected conflicts: standup↔planning, lunch↔review")

print("\nMeetings outside business hours (9am–6pm):")
for mtg, reason in sorted(outside.items()):
    print(f"  {mtg}: {reason}")

print(f"\nExpected outside-hours: afterhours (ends after 6pm), early (starts before 9am)")
