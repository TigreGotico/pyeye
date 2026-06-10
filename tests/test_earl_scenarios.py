"""Exact-isomorphism conformance for the W3C EARL meta-suite scenarios.

The four EARL scenarios (``n3-dev``, ``turtle-dev``, ``rdf12``, ``rdf-star``)
load a pre-generated EARL report (``run-outcome.n3``) and re-emit it with
``--nope --pass``; the reference answer is the re-serialized report
(``run-outcome-pass.n3``).  The reports are large (739–8,792 facts) and almost
every fact involves a blank node (one ``earl:Assertion`` / ``earl:TestResult``
bnode pair per manifest entry), which puts them beyond the bounded
blank-mapping search in ``n3_compare`` — so the corpus suite tracks them as
expected failures.

This module proves the stronger property directly: pyeye's output graph is
*exactly isomorphic* to the reference.  Blank labels are canonicalized by
iterative neighbourhood-signature refinement; in these reports every blank
node ends up with a unique signature (each assertion chain is anchored by a
distinct ``earl:test`` IRI), so equality of the canonicalized fact multisets
is a sound and complete isomorphism check.

Uses the scenario copies vendored under ``tests/eye_scenarios/`` so the check
is hermetic (no dependency on the external corpus mount).
"""

from __future__ import annotations

import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pyeye import execute  # noqa: E402
from pyeye.parser import parse_n3  # noqa: E402
from tests.n3_compare import _BLANK, document_facts  # noqa: E402

SCENARIOS_DIR = Path(__file__).resolve().parent / "eye_scenarios"
EARL_SCENARIOS = ("n3-dev", "turtle-dev", "rdf12", "rdf-star")

_REFINEMENT_ROUNDS = 4


def _blank_label(node) -> str | None:
    if isinstance(node, tuple) and node and node[0] == _BLANK:
        return node[1]
    return None


def _term_key(node) -> str:
    return json.dumps(node, sort_keys=True, default=list)


def canonical_facts(facts) -> tuple[Counter, int]:
    """Canonicalize blank labels by signature refinement.

    Returns ``(fact_multiset, ambiguous)`` where *ambiguous* counts blank
    labels whose final signature is shared with another label.  When
    ``ambiguous == 0`` the canonical mapping is forced, so multiset equality
    between two graphs is exact isomorphism.
    """
    edges: dict[str, list[tuple[str, str, str | None, str]]] = {}
    for f in facts:
        if not (isinstance(f, tuple) and f and f[0] == "t"):
            continue
        _, s, p, o = f
        ls, lo = _blank_label(s), _blank_label(o)
        pk = _term_key(p)
        if ls is not None:
            edges.setdefault(ls, []).append(("s", pk, lo, _term_key(o)))
        if lo is not None:
            edges.setdefault(lo, []).append(("o", pk, ls, _term_key(s)))

    sig: dict[str, str] = {label: "" for label in edges}
    for _ in range(_REFINEMENT_ROUNDS):
        new_sig: dict[str, str] = {}
        for label, es in edges.items():
            parts = []
            for role, pk, other_label, other_key in es:
                other = ("N:" + sig[other_label]) if other_label is not None \
                    else other_key
                parts.append((role, pk, other))
            new_sig[label] = hashlib.md5(
                json.dumps(sorted(parts)).encode()).hexdigest()
        sig = new_sig

    ambiguous = sum(n for n in Counter(sig.values()).values() if n > 1)

    def replace(node):
        label = _blank_label(node)
        if label is not None:
            return (_BLANK, sig[label])
        if isinstance(node, tuple):
            return tuple(
                replace(c) if isinstance(c, (tuple, frozenset)) else c
                for c in node)
        if isinstance(node, frozenset):
            return frozenset(replace(c) for c in node)
        return node

    return Counter(replace(f) for f in facts), ambiguous


@pytest.mark.parametrize("name", EARL_SCENARIOS)
def test_earl_report_isomorphic(name: str):
    scenario = SCENARIOS_DIR / name
    outcome = scenario / "run-outcome.n3"
    reference = scenario / "run-outcome-pass.n3"

    result = execute(rule_paths=[str(outcome)], nope=True, pass_mode=True,
                     timeout_seconds=60)

    expected = document_facts(
        parse_n3(reference.read_text(encoding="utf-8"), source="expected"))
    actual = document_facts(parse_n3(result.triples, source="actual"))

    exp_canon, exp_ambiguous = canonical_facts(expected)
    act_canon, act_ambiguous = canonical_facts(actual)

    assert exp_ambiguous == 0, \
        f"{name}: {exp_ambiguous} ambiguous blank signatures in reference"
    assert act_ambiguous == 0, \
        f"{name}: {act_ambiguous} ambiguous blank signatures in output"

    missing = exp_canon - act_canon
    extra = act_canon - exp_canon
    assert not missing and not extra, (
        f"{name}: {sum(missing.values())} missing / {sum(extra.values())} "
        f"extra of {sum(exp_canon.values())} facts; first missing: "
        f"{next(iter(missing), None)}; first extra: {next(iter(extra), None)}"
    )
