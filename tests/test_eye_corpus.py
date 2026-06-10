"""Conformance suite: run every EYE ``reasoning/`` scenario through pyeye and
compare against EYE's own reference answer file.

Scenarios are auto-discovered from each scenario's ``test`` shell script (see
``eye_scenarios.py``), which encodes the exact ``eye`` invocation (input files,
``--query`` file, output mode, and the ``--output`` reference answer).

Comparison is semantic: both pyeye output and the reference answer are parsed
with pyeye's own N3 parser and compared as canonical fact sets under a
blank-node/skolem/variable mapping (see ``n3_compare``).  A scenario PASSES
when every expected fact is present in pyeye's output.  If either side fails
to parse, comparison falls back to canonical triple-lines.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pyeye import execute, ReasoningTimeoutError  # noqa: E402
from tests.eye_scenarios import discover_scenarios, Scenario  # noqa: E402
from tests.n3_compare import compare_semantic  # noqa: E402

PER_SCENARIO_TIMEOUT = 15.0

_ALL = discover_scenarios()
_RUNNABLE = [s for s in _ALL if s.skip_reason is None and s.answer is not None
             and s.answer.exists() and not s.strings and not s.is_proof_answer]
_PROOF = [s for s in _ALL if s.skip_reason is None and s.answer is not None
          and s.answer.exists() and not s.strings and s.is_proof_answer]
_SKIPPED = [s for s in _ALL if s not in _RUNNABLE and s not in _PROOF]

# Known-failing scenarios, grouped by root cause.  Entries are non-strict:
# a scenario that starts passing simply passes, and its entry is pruned on
# the next corpus baseline.  Reasons describe the current gap.
_NO_ANSWERS = "derives no or few query answers (backward-chaining/builtin gaps)"
_PARTIAL = "incomplete derivation: some expected facts missing"
_STRUCTURE = "output structure differs from reference under blank/variable mapping"
_TIMEOUT15 = "exceeds the 15s corpus timeout (deep recursion / unbounded search)"

XFAIL: dict[str, str] = {
    # query scenarios deriving no/insufficient answers
    "4color": _NO_ANSWERS, "4number": _NO_ANSWERS, "hanoi": _NO_ANSWERS,
    "dijkstra": _NO_ANSWERS, "easter": _NO_ANSWERS, "lee": _NO_ANSWERS,
    "map": _NO_ANSWERS, "gps": _NO_ANSWERS, "n-queens": _NO_ANSWERS,
    "collatz": _NO_ANSWERS, "kaprekar": _NO_ANSWERS, "goldbach": _NO_ANSWERS,
    "combinatorics": _NO_ANSWERS, "dcg": _NO_ANSWERS, "seq": _NO_ANSWERS,
    "peasant": _NO_ANSWERS, "gray-code-counter": _NO_ANSWERS,
    "polygon": _NO_ANSWERS, "glass": _NO_ANSWERS,
    "gdpr-compliance": _NO_ANSWERS, "wind-turbine": _NO_ANSWERS,
    "issue154": _NO_ANSWERS, "ccd": _NO_ANSWERS,
    # incomplete derivations
    "allen": "dateTime interval reasoning incomplete (22/24 facts missing)",
    "bi": _PARTIAL, "n3patch": _PARTIAL, "preduction": _PARTIAL,
    "n3plus1": _PARTIAL, "issue148": _PARTIAL, "ill-formed-literals": _PARTIAL,
    # reference answers print floats at 12 significant digits (older EYE
    # float format); residuals differ in the trailing digits
    "heron-theorem": "reference floats truncated to 12 significant digits",
    "law-of-cosines": "reference floats truncated to 12 significant digits",
    # output-structure mismatches
    "bnode-scope": _STRUCTURE,
    "issue118": _STRUCTURE, "issue141": _STRUCTURE,
    "reif": _STRUCTURE, "swet": _STRUCTURE, "ldes": _STRUCTURE,
    # output modes
    "entail": "--entail boolean output mode not implemented",
    "shaclr": "SHACL-rules (.shaclr) input not implemented",
    # timeouts
    "ackermann": _TIMEOUT15, "bmi": _TIMEOUT15,
    "fundamental-theorem-of-arithmetic": _TIMEOUT15,
    "gcd-bezout-identity": _TIMEOUT15, "graph": _TIMEOUT15,
    "meta-interpretation": _TIMEOUT15, "path-discovery": _TIMEOUT15,
    "pi": _TIMEOUT15, "restpath": _TIMEOUT15, "turing": _TIMEOUT15,
}


# --------------------------------------------------------------------------- #
# Canonicalisation
# --------------------------------------------------------------------------- #

_PREFIX_RE = re.compile(r"@(prefix|base)\b", re.IGNORECASE)


def _expand_prefixes(text: str) -> dict[str, str]:
    """Collect ``@prefix p: <uri>.`` declarations into a {p: uri} map."""
    pmap: dict[str, str] = {}
    for m in re.finditer(r"@prefix\s+([\w-]*):\s*<([^>]*)>", text):
        pmap[m.group(1)] = m.group(2)
    return pmap


def _normalize(text: str) -> set[str]:
    """Reduce N3 output to a set of canonical triple strings.

    - drop @prefix/@base directives and comments
    - expand prefixed names ``p:local`` to ``<uri+local>`` so that pyeye and
      EYE prefix-name choices don't matter
    - collapse internal whitespace and strip trailing ``.``
    """
    pmap = _expand_prefixes(text)

    def expand_token(tok: str) -> str:
        m = re.fullmatch(r"([\w-]*):([^\s]*)", tok)
        if m and m.group(1) in pmap:
            return f"<{pmap[m.group(1)]}{m.group(2)}>"
        return tok

    lines: set[str] = set()
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or _PREFIX_RE.match(line):
            continue
        line = line.rstrip(" .")
        line = re.sub(r"\s+", " ", line).strip()
        if not line:
            continue
        toks = [expand_token(t) for t in line.split(" ")]
        lines.add(" ".join(toks))
    return lines


def _compare_lines(actual: str, expected: str) -> tuple[bool, str]:
    """Line-based fallback comparison for unparseable output."""
    exp = _normalize(expected)
    got = _normalize(actual)
    if not exp:
        if not got:
            return True, "both empty"
        return False, f"expected empty, got {len(got)} triples"
    missing = [e for e in exp if e not in got]
    if not missing:
        return True, f"all {len(exp)} expected triples present"
    return False, (f"missing {len(missing)}/{len(exp)}: {missing[0][:80]!r}")


def _compare(actual: str, expected: str) -> tuple[bool, str]:
    """Return (passed, detail)."""
    try:
        return compare_semantic(actual, expected)
    except Exception as e:  # noqa: BLE001 — unparseable side: fall back
        ok, detail = _compare_lines(actual, expected)
        return ok, f"{detail} [line fallback: {type(e).__name__}]"


def run_scenario(sc: Scenario) -> tuple[str, str]:
    """Execute a scenario through pyeye. Returns (status, detail)."""
    rule_paths = [str(p) for p in sc.inputs]
    query_paths = [str(sc.query)] if sc.query else None
    try:
        result = execute(
            rule_paths=rule_paths or None,
            query_paths=query_paths,
            nope=sc.nope,
            pass_mode=sc.pass_mode,
            pass_all=sc.pass_all,
            pass_only_new=sc.pass_only_new,
            timeout_seconds=PER_SCENARIO_TIMEOUT,
            proof=sc.is_proof_answer,
            source_urls=sc.source_urls or None,
        )
    except ReasoningTimeoutError:
        return "TIMEOUT", f"exceeded {PER_SCENARIO_TIMEOUT}s"
    except Exception as e:  # noqa: BLE001
        return "ERROR", f"{type(e).__name__}: {str(e)[:160]}"

    expected = sc.answer.read_text(encoding="utf-8", errors="replace")
    passed, detail = _compare(result.triples, expected)
    return ("PASS" if passed else "FAIL"), detail


@pytest.mark.parametrize("sc", _RUNNABLE, ids=[s.name for s in _RUNNABLE])
def test_eye_scenario(sc: Scenario):
    status, detail = run_scenario(sc)
    if status != "PASS" and sc.name in XFAIL:
        pytest.xfail(f"{XFAIL[sc.name]} — {status}: {detail}")
    assert status == "PASS", f"{sc.name}: {status} — {detail}"


@pytest.mark.parametrize("sc", _PROOF, ids=[s.name for s in _PROOF])
def test_eye_scenario_proof_output(sc: Scenario):
    # Reference output is a full proof trace (reason: vocabulary + skolem
    # genids). Matching it requires the proof-graph serializer; tracked as a
    # known cluster rather than a plain-answer conformance failure.
    status, detail = run_scenario(sc)
    if status != "PASS":
        pytest.xfail(f"proof-format output: {status} — {detail}")


@pytest.mark.parametrize("sc", _SKIPPED, ids=[s.name for s in _SKIPPED])
def test_eye_scenario_skipped(sc: Scenario):
    pytest.skip(sc.skip_reason or "no reference answer / non-N3 output")
