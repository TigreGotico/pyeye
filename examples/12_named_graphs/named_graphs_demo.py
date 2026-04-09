"""
12 — Named Graphs (TriG)
=========================
pyeye supports TriG syntax for associating triples with a named graph IRI.
Rules can be graph-aware: match quads (triple + graph context).

Concepts:
  - GRAPH <iri> { ... }     — TriG named graph
  - store.match(..., graph=<iri>)  — query a specific graph
  - Quads: triple + graph identifier
  - Cross-graph reasoning: rules that read from one graph, write to default

Named graphs are useful for:
  - Provenance (where did this fact come from?)
  - Versioning (graph per snapshot)
  - Multi-tenant data (one graph per user/org)
  - Trust levels (facts from trusted vs. untrusted sources)
"""

from pyeye import execute
from pyeye.engine import Engine
from pyeye.parser import parse_n3
from pyeye.term import NamedNode, Triple

# Example 1: Loading TriG data with named graphs
print("=== TriG Named Graphs ===")

trig_data = """
@prefix : <http://example.org/> .

GRAPH :graph2024 {
    :alice :salary 80000 .
    :bob   :salary 75000 .
}

GRAPH :graph2025 {
    :alice :salary 85000 .
    :carol :salary 70000 .
}
"""

# Rules that run over the default graph
# (Named graph content is separately queryable)
result = execute(
    data_strings=[trig_data],
    rule_strings=[],  # no rules — just inspect what's loaded
)
print("Default graph triples:", result.triples or "(empty)")
print("Stats:", result.stats)


# Example 2: Direct engine — query named graphs
print("\n=== Querying Named Graphs via Engine API ===")

from pyeye.engine import Engine
from pyeye.parser import parse_n3

engine = Engine()
doc = parse_n3(trig_data)
for triple in doc.triples:
    engine.add_triple(triple)
for quad in doc.quads:
    engine.store.add_quad(quad)

graph_2025 = NamedNode("http://example.org/graph2025")
graph_2024 = NamedNode("http://example.org/graph2024")

print("2024 salaries:")
for t in engine.store.match(graph=graph_2024):
    print(" ", t)

print("2025 salaries:")
for t in engine.store.match(graph=graph_2025):
    print(" ", t)


# Example 3: Provenance — tag derived facts with their source graph
print("\n=== Provenance Tracking ===")

data = """
@prefix prov: <http://example.org/prov#> .

GRAPH prov:source_trusted {
    prov:alice prov:income 90000 .
    prov:bob   prov:income 50000 .
}

GRAPH prov:source_untrusted {
    prov:carol prov:income 999999 .
}
"""

rules = """
@prefix prov: <http://example.org/prov#> .
@prefix math: <http://www.w3.org/2000/10/swap/math#> .

# Only use trusted source for tax computation
# (we pattern-match from the default graph after quads are merged)
"""

# In practice: load, filter by graph in Python, derive from trusted only
engine2 = Engine()
doc2 = parse_n3(data)
for q in doc2.quads:
    engine2.store.add_quad(q)

trusted_graph = NamedNode("http://example.org/prov#source_trusted")
print("Trusted incomes:")
for t in engine2.store.match(graph=trusted_graph):
    print(" ", t)
