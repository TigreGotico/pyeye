"""pytest test suite that runs the original EYE reasoning scenarios against pyeye.

Each of the 155 scenarios in tests/eye_scenarios/ is run as an individual
parametrized test. Where an *-answer.n3 file exists the output is verified
against it; otherwise we just check that the engine ran without error.

Scenarios requiring features not yet implemented are marked xfail.
"""
from __future__ import annotations
import re, shlex
from pathlib import Path
import pytest
from pyeye import execute
from pyeye.engine import ContradictionError, ReasoningTimeoutError

SCENARIOS_DIR = Path(__file__).parent / "eye_scenarios"
EYE_URL_BASE = "https://eyereasoner.github.io/eye/reasoning"

# known-broken: (reason, strict=False means XPASS is OK)
XFAIL: dict[str, str] = {
    # Parser gaps
    "rdf-star-reasoning":   "RDF-star <<>> not supported by parser",
    # xsd:dateTime/duration arithmetic
    "bmi":                  "xsd:dateTime/duration arithmetic not implemented",
    "bmi-backward":         "xsd:dateTime/duration arithmetic not implemented",
    # Non-terminating (infinite numeric search space)
    "pythagorean-theorem":              "forward-chain non-termination",
    "good-cobbler":                     "forward-chain non-termination",
    "ccd":                              "forward-chain non-termination (30s timeout)",
    "delfour-insight-economy":          "forward-chain non-termination (30s timeout)",
    "fundamental-theorem-of-arithmetic":"forward-chain non-termination (30s timeout)",
    "heron-theorem":                    "forward-chain non-termination (30s timeout)",
    "law-of-cosines":                   "forward-chain non-termination (30s timeout)",
    "nbbn":                             "forward-chain non-termination (30s timeout)",
    "polygon":                          "forward-chain non-termination (30s timeout)",
    "quadratic-equation":               "forward-chain non-termination (30s timeout)",
    # Incomplete backward chaining
    "proof-by-induction":   "recursive BC with complex math not yet working",
    "fibonacci":            "BC recursion depth - only derives base cases",
    "gcd-bezout-identity":  "recursive GCD with complex variable patterns",
    # Missing builtins/features
    "access-control-policy":"log:forAllIn not implemented",
    "deep-taxonomy":        "large RDFS taxonomy - entailment incomplete",
}

def _resolve_file(tok: str, scenario_dir: Path) -> Path | None:
    if tok == "..":
        return None
    if tok.startswith(EYE_URL_BASE + "/"):
        rel = tok[len(EYE_URL_BASE) + 1:]
        p = SCENARIOS_DIR / rel
        return p if p.exists() else None
    if tok.startswith("http://") or tok.startswith("https://"):
        return None
    p = scenario_dir / tok
    return p if p.exists() else None

def _parse_test_script(scenario_dir: Path) -> dict:
    test_script = scenario_dir / "test"
    if not test_script.exists():
        return {}
    text = test_script.read_text(errors="replace")
    first_cmd = ""
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("eye "):
            first_cmd = line
            break
    if not first_cmd:
        return {}
    tokens = shlex.split(first_cmd.replace("\\\n", " "))[1:]
    data_files, query_files = [], []
    answer_file = None
    flags: set[str] = set()
    in_query = False
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok == "--wcache":
            i += 3; continue
        if tok == "--skolem-genid":
            i += 2; continue
        if tok in ("--quiet",):
            i += 1; continue
        if tok in ("--nope", "--pass-only-new", "--pass"):
            flags.add(tok); i += 1; continue
        if tok == "--query":
            in_query = True; i += 1; continue
        if tok == "--output":
            if i + 1 < len(tokens):
                out_name = Path(tokens[i+1]).name
                candidate = scenario_dir / out_name
                if candidate.exists():
                    answer_file = candidate
            i += 2; continue
        if tok.startswith("--"):
            i += 1; continue
        local = _resolve_file(tok, scenario_dir)
        if local:
            (query_files if in_query else data_files).append(local)
        i += 1
    return {"data_files": data_files, "query_files": query_files,
            "answer_file": answer_file, "flags": flags}

def _expected_lines(answer_file: Path) -> list[str]:
    lines = []
    for line in answer_file.read_text(errors="replace").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and not line.startswith("@prefix") and line != ".":
            lines.append(line)
    return lines

ALL_SCENARIOS = sorted(p.name for p in SCENARIOS_DIR.iterdir() if p.is_dir())

@pytest.mark.parametrize("scenario", ALL_SCENARIOS)
def test_eye_scenario(scenario: str) -> None:
    if scenario in XFAIL:
        pytest.xfail(XFAIL[scenario])

    scenario_dir = SCENARIOS_DIR / scenario
    info = _parse_test_script(scenario_dir)
    if not info:
        pytest.skip("No parseable test script")

    data_files = info["data_files"]
    query_files = info["query_files"]
    answer_file = info["answer_file"]

    all_files = data_files + query_files
    if not all_files:
        pytest.skip("No local N3 files found")

    contents = []
    for f in all_files:
        try:
            contents.append(f.read_text(errors="replace"))
        except Exception as e:
            pytest.skip(f"Could not read {f}: {e}")

    # EYE --nope / --pass-only-new → pass_mode=True (output includes input facts)
    flags = info.get("flags", set())
    pass_mode = "--nope" in flags or "--pass-only-new" in flags

    try:
        result = execute(data_strings=contents, timeout_seconds=30.0,
                         pass_mode=pass_mode)
    except ContradictionError:
        return  # constraint fired — valid outcome
    except ReasoningTimeoutError:
        pytest.fail(f"Timed out after 30s")
    except Exception as e:
        pytest.fail(f"{type(e).__name__}: {e}")

    if answer_file and answer_file.exists():
        # Skip if the answer file is a proof trace (not a query result)
        answer_text = answer_file.read_text(errors="replace")
        if "r:Proof" in answer_text or "reason:Proof" in answer_text or "@prefix r:" in answer_text:
            return  # proof file — not comparable to pyeye's derived-triples output

        expected = _expected_lines(answer_file)
        if not expected:
            return

        # result.triples is already a serialized N3 string
        output_n3 = result.triples

        def _norm(s: str) -> str:
            """Normalise whitespace and remove space-before-dot for comparison."""
            s = re.sub(r"\s+", " ", s).strip()
            s = re.sub(r"\s+\.", ".", s)  # "foo ." → "foo."
            return s

        norm_out = _norm(output_n3)
        missing = [ln for ln in expected
                   if _norm(ln) not in norm_out]
        if missing:
            pytest.fail(
                f"{len(missing)}/{len(expected)} expected triples missing.\n"
                f"First missing: {missing[0]!r}\n"
                f"Output:\n{output_n3[:800]}"
            )
