# Status: pyeye — Python N3 Reasoner (Phase 1)

## Progress

- [ ] Initialize project: git repo, `pyproject.toml`, empty `pyeye/` package
- [ ] `term.py` — N3 Term hierarchy (NamedNode, Literal, Variable, Existential, Formula, Triple)
- [ ] `unify.py` — Structural unification with occurs check and binding propagation
- [ ] `store.py` — Triple store with predicate-based indexing
- [ ] `parser.py` — Minimal N3 rule parser (`{P} => {C}`, variables, prefixes, quantifiers, lists, blank nodes)
- [ ] `builtins.py` — Curated builtin registry (~40: math, string, time, list, log, type)
- [ ] `engine.py` — Euler Abstract Machine (forward chaining, cycle detection, step limits, limited-answer tactic)
- [ ] `output.py` — N3 serialization with prefix abbreviation
- [ ] `entry.py` — `execute()` public API + `Result` dataclass
- [ ] `cli.py` — CLI entry point compatible with EYE flags
- [ ] `__init__.py` — Public API surface
- [ ] Integration tests: transitivity chain, cycle detection, step limits, builtin evaluation, variable binding propagation
- [ ] End-to-end test: run spec acceptance criteria
- [ ] `pyproject.toml` — installable package + CLI entry point

## Blockers

_None identified._
