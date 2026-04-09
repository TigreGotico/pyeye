"""
11 — Proof Traces
=================
explain=True makes pyeye record the full derivation chain for every
derived triple. The proof can be serialised in three formats:
  - "n3"   — N3 triples (machine-readable, default)
  - "dot"  — Graphviz DOT (visualise with dot/xdot)
  - "html" — Interactive HTML (open in browser)

Concepts:
  - explain=True              — enable proof recording
  - explain_format="n3"|"dot"|"html"
  - result.explains           — list of proof trees / serialised strings
  - ProofTree dataclass       — root triple + child sub-proofs + rule

Use proof traces when:
  - Debugging unexpected inferences
  - Auditing results for compliance
  - Explaining a decision to a non-technical audience
"""

from pathlib import Path
from pyeye import execute

facts = """
@prefix : <http://example.org/> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

:Cat    rdfs:subClassOf :Animal .
:Animal rdfs:subClassOf :LivingThing .
:felix  a :Cat .
"""

rules = """
@prefix : <http://example.org/> .
@prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .

# Transitive subclass reasoning
{ ?A rdfs:subClassOf ?B . ?X a ?A } => { ?X a ?B } .
"""

# --- N3 proof trace ----------------------------------------------------------
print("=== N3 Proof Trace ===")
result_n3 = execute(
    data_strings=[facts],
    rule_strings=[rules],
    explain=True,
    explain_format="n3",
)
print(result_n3.triples)
print("\n--- Proof (N3) ---")
for tree in result_n3.explains:
    print(tree)  # N3 triples describing the derivation


# --- DOT proof trace ---------------------------------------------------------
print("\n=== DOT Proof Trace ===")
result_dot = execute(
    data_strings=[facts],
    rule_strings=[rules],
    explain=True,
    explain_format="dot",
)
dot_path = Path("/tmp/pyeye_proof.dot")
for i, dot in enumerate(result_dot.explains):
    p = Path(f"/tmp/pyeye_proof_{i}.dot")
    p.write_text(dot)
    print(f"Wrote {p}")
    print("Render with: dot -Tsvg", p, "-o proof.svg")


# --- HTML proof trace --------------------------------------------------------
print("\n=== HTML Proof Trace ===")
result_html = execute(
    data_strings=[facts],
    rule_strings=[rules],
    explain=True,
    explain_format="html",
)
html_path = Path("/tmp/pyeye_proof.html")
# The HTML output is one string per proof tree; combine them
combined = "\n\n".join(result_html.explains)
html_path.write_text(f"<html><body>{combined}</body></html>")
print(f"Wrote {html_path}")
print("Open in browser to view interactive proof tree")
