# pyeye — Documentation Index

| Document | Purpose |
| :--- | :--- |
| [getting-started.md](getting-started.md) | Installation, quickstart tutorial, first rule |
| [api-reference.md](api-reference.md) | `execute()`, `Engine`, term hierarchy — full API |
| [cli-reference.md](cli-reference.md) | CLI flags, exit codes, examples |
| [builtins.md](builtins.md) | Every builtin predicate with arity, namespace, and examples |
| [syntax-guide.md](syntax-guide.md) | N3 rule syntax supported in Phase 1 (and what's deferred) |
| [faq.md](faq.md) | Common questions, troubleshooting, known limitations |

## Source Code References

All documentation cites source code in the format `` `ClassName.method` — `path/to/file.py:LINE` ``. The authoritative source is:

| Module | Source |
| :--- | :--- |
| Term hierarchy | `pyeye/term.py` |
| Unification | `pyeye/unify.py` |
| Triple store | `pyeye/store.py` |
| Parser | `pyeye/parser.py` |
| Builtins | `pyeye/builtins.py` |
| Engine | `pyeye/engine.py` |
| Entry API | `pyeye/entry.py` |
| Output writer | `pyeye/output.py` |
| CLI | `pyeye/cli.py` |
