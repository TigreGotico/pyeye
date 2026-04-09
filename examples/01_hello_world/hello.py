"""
01 — Hello World
================
The simplest possible inference: one fact, one rule, one derived fact.

Concepts:
  - execute()       the main entry point
  - data_strings    N3 text with facts
  - rule_strings    N3 text with rules (pattern => conclusion)
  - result.triples  the derived N3 output
"""

from pyeye import execute

# --- Facts -------------------------------------------------------------------
# A single fact: "The sky has colour blue."
facts = """
@prefix : <http://example.org/> .

:sky :colour :blue .
"""

# --- Rules -------------------------------------------------------------------
# "If something has a colour X, then it is coloured X."
rules = """
@prefix : <http://example.org/> .

{ ?Thing :colour ?C }
    => { ?Thing :isColoured ?C } .
"""

# --- Run inference -----------------------------------------------------------
result = execute(
    data_strings=[facts],
    rule_strings=[rules],
)

print("Derived triples:")
print(result.triples)
# Expected: :sky :isColoured :blue .

print("\nStats:", result.stats)
# {"steps": 1, "derived": 1, "time_ms": ...}
