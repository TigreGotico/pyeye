"""
27 — Graph Algorithms: Cycle Detection
========================================
Use forward-chaining transitive closure to compute reachability in a
directed graph. A node is cyclic if it can reach itself.

Concepts:
  - Transitive closure: if A→B and B→C then A reaches C
  - Cycle detection: node N is cyclic if N reaches N
  - log:notEqualTo: avoid trivial self-loops from the base step
  - Pure forward-chaining derivation, no backward chaining needed
"""

from pyeye import execute

# ---------------------------------------------------------------------------
# Graph data — directed edges
# Cycle: D→E→F→D
# Acyclic chain: A→B→C
# Cross edge: C→D (connects acyclic part into the cycle)
# ---------------------------------------------------------------------------
data = """
@prefix g: <http://example.org/graph#> .

g:A g:edge g:B .
g:B g:edge g:C .
g:C g:edge g:D .
g:D g:edge g:E .
g:E g:edge g:F .
g:F g:edge g:D .   # back-edge: creates cycle D→E→F→D
g:X g:edge g:Y .   # isolated acyclic edge
"""

rules = """
@prefix g:    <http://example.org/graph#> .
@prefix log:  <http://www.w3.org/2000/10/swap/log#> .

# Base: direct edge means reachable
{ ?A g:edge ?B } => { ?A g:reaches ?B } .

# Transitive: if A reaches B and B reaches C then A reaches C
{ ?A g:reaches ?B . ?B g:reaches ?C } => { ?A g:reaches ?C } .

# Cycle: a node is cyclic if it reaches itself
{ ?N g:reaches ?N } => { ?N a g:CyclicNode } .

# Acyclic: has outgoing edge but is not cyclic
{
    ?N g:edge ?Any .
    _:neg log:onNegativeSurface { ?N a g:CyclicNode }
}
    => { ?N a g:AcyclicNode } .
"""

result = execute(data_strings=[data], rule_strings=[rules])

cyclic = []
acyclic = []

for line in result.triples.splitlines():
    line = line.strip().rstrip(" .")
    if "g:CyclicNode" in line and " a " in line:
        node = line.split()[0].split(":")[-1]
        cyclic.append(node)
    if "g:AcyclicNode" in line and " a " in line:
        node = line.split()[0].split(":")[-1]
        acyclic.append(node)

print("=== Cycle Detection via Transitive Closure ===\n")
print("Graph edges: A→B→C→D→E→F→D (back-edge), X→Y")
print()
print(f"Cyclic nodes  : {sorted(set(cyclic))}")
print(f"Acyclic nodes : {sorted(set(acyclic))}")
print()
print("Expected cyclic : D, E, F")
print("Expected acyclic: A, B, C, X  (C leads into cycle but is not itself cyclic)")
