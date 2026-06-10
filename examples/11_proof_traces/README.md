# 11 — Proof Traces

**Topic:** Explain derivations
**Key concepts:** `explain=True`, HTML/DOT/N3 proof output

explain=True makes pyeye record the full derivation chain for every derived triple. The proof can be serialised in three formats: - "n3"   — N3 triples (machine-readable, default) - "dot"  — Graphviz DOT (visualise with dot/xdot) - "html" — Interactive HTML (open in browser)

Run:

```bash
python proof_demo.py
```

Back to the [examples index](../README.md).
