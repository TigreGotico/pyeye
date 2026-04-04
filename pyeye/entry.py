"""Public API — ``execute()`` function.

Ties together parsing, loading, and reasoning into a single call.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import time
from pathlib import Path

from pyeye.term import Triple
from pyeye.parser import (
    parse_n3, load_data_string, load_data_file, ParsedDocument, Rule
)
from pyeye.builtins import Builtin
from pyeye.engine import Engine
from pyeye.output import N3Writer


@dataclass
class Result:
    """Output of a reasoning run."""
    triples: str = ""
    stats: dict = field(default_factory=dict)
    explains: list = field(default_factory=list)
    query_answers: list = field(default_factory=list)  # populated when query is set


def execute(
    data_paths: list[str] | None = None,
    data_strings: list[str] | None = None,
    rule_paths: list[str] | None = None,
    rule_strings: list[str] | None = None,
    builtins: dict[str, Builtin] | None = None,
    explain: bool = False,
    max_steps: int = -1,
    limit_answers: int = -1,
    prefixes: dict[str, str] | None = None,
    nope: bool = False,
    pass_mode: bool = False,
    pass_all: bool = False,
    djiti_debug: bool = False,
    query: Triple | None = None,
    forward: bool = True,
) -> Result:
    """Run N3 reasoning and return derived triples as N3 text.

    Parameters
    ----------
    data_paths :
        Paths to N3/Turtle data files (parsed via rdflib).
    data_strings :
        Inline N3/Turtle data strings.
    rule_paths :
        Paths to N3 rule files (may contain {P} => {C} rules).
    rule_strings :
        Inline N3 rule strings.
    builtins :
        Custom builtin registry (merged with the default set).
    explain :
        If True, collect proof explanations (Phase 2).
    max_steps :
        Hard cap on inference steps (-1 = unlimited).
    limit_answers :
        Stop after this many new derivations (-1 = unlimited).
    prefixes :
        Additional prefix mappings for output serialization.
    nope :
        If True, skip derivation — pass through data only.
    pass_mode :
        If True, output includes input facts + derived triples.
    pass_all :
        If True, output includes input facts, rules, and derived triples.
    djiti_debug :
        If True, log DJITI pattern ordering for each rule application.
    query :
        A Triple to backward-chain from. If set, the engine finds all
        bindings that satisfy the query. Results go in Result.query_answers.
    forward :
        If True (default), run forward chaining before backward chaining.
        Set to False for pure backward chaining.
    """
    start = time.monotonic()

    all_triples: list[Triple] = []
    all_rules: list[Rule] = []
    all_prefixes: dict[str, str] = dict(prefixes or {})

    # -- load data -----------------------------------------------------------
    if data_paths:
        for p in data_paths:
            doc = load_data_file(p)
            all_triples.extend(doc.triples)
            all_prefixes.update(doc.prefixes)

    if data_strings:
        for s in data_strings:
            doc = load_data_string(s)
            all_triples.extend(doc.triples)
            all_prefixes.update(doc.prefixes)

    # -- load rules ----------------------------------------------------------
    if rule_paths:
        for p in rule_paths:
            text = Path(p).read_text(encoding="utf-8")
            doc = parse_n3(text, source=p)
            all_rules.extend(doc.rules)
            all_prefixes.update(doc.prefixes)

    if rule_strings:
        for s in rule_strings:
            doc = parse_n3(s, source="<string>")
            all_rules.extend(doc.rules)
            all_prefixes.update(doc.prefixes)

    # -- nope mode -----------------------------------------------------------
    if nope:
        elapsed = time.monotonic() - start
        writer = N3Writer(all_prefixes)
        return Result(
            triples=writer.write_triples(all_triples),
            stats={"steps": 0, "derived": 0, "time_ms": elapsed * 1000},
        )

    # -- reason --------------------------------------------------------------
    engine = Engine(
        builtins=builtins,
        max_steps=max_steps,
        limit_answers=limit_answers,
        djiti_debug=djiti_debug,
        explain=explain,
    )

    # Add data triples
    for t in all_triples:
        engine.add_triple(t)

    # Snapshot baseline (input facts should not count as derived)
    engine.snapshot_initial()

    # Add rules
    for r in all_rules:
        engine.add_rule(r)

    # Run forward chaining (if enabled)
    if forward and not nope:
        engine.run()

    # Run backward chaining (if query is set)
    query_answers: list = []
    if query is not None and not nope:
        query_answers = engine.backward_chain(query)

    # Collect output
    elapsed = time.monotonic() - start
    writer = N3Writer(all_prefixes)

    if pass_mode or pass_all:
        # All triples in the store (input + derived)
        output_triples = list(engine.store)
    else:
        # Only derived triples
        output_triples = engine.derived_triples

    triples_text = writer.write_triples(output_triples)

    return Result(
        triples=triples_text,
        stats={
            "steps": engine.step_count,
            "derived": len(output_triples),
            "time_ms": elapsed * 1000,
        },
        explains=engine._proof_trees if explain else [],
        query_answers=query_answers,
    )
