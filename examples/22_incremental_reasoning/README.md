# 22 — Incremental Reasoning

**Topic:** Streaming / live updates
**Key concepts:** `engine.add_triple()` post-run, `derived_triples`

pyeye's ``Engine.add_triple()`` triggers incremental re-derivation: when a new fact is added after ``run()`` has already been called, the engine immediately checks which rules might fire for the new fact and derives any new conclusions, without re-processing the entire store.

Run:

```bash
python incremental_demo.py
```

Back to the [examples index](../README.md).
