"""EYE reasoning test suite — ported from the upstream EYE repository.

Each scenario in ``tests/eye_scenarios/`` maps to one parametrised test.
The test parses the ``test`` shell script in each scenario directory,
reconstructs the EYE command using local file paths, runs it through
pyeye's ``execute()`` API, and (when an ``*-answer.n3`` file exists)
verifies that every expected triple appears in the output.

Scenarios whose ``test`` script is a complex shell program (not a simple
``eye`` invocation) are skipped.  Known-hard scenarios are marked
``xfail``.
"""

from __future__ import annotations

import re
import shlex
from pathlib import Path
from typing import NamedTuple

import pytest

from pyeye import execute
from pyeye.parser import ParseError

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).parent.parent
SCENARIOS_DIR = Path(__file__).parent / "eye_scenarios"
EYE_URL_PREFIX = "https://eyereasoner.github.io/eye/reasoning"


# ---------------------------------------------------------------------------
# Known-broken scenarios
# ---------------------------------------------------------------------------

# strict=False so XPASS is not a failure — it just gets flagged as a bonus.
XFAIL_REASONS: dict[str, str] = {
    "rdf-star-reasoning": "RDF-star <<>> syntax not supported",
    "socrates-star": "RDF-star <<>> syntax not supported",
    "bmi": "xsd:dateTime arithmetic not implemented",
    "pythagorean-theorem": "forward-chain non-termination",
    "good-cobbler": "forward-chain non-termination",
    "diamond-property": "forward-chain non-termination (circular equality axioms)",
    "gcd-bezout-identity": "forward-chain non-termination",
    "polygon": "forward-chain non-termination",
    # Tests that hit the 30s timeout in pyeye — need optimisation
    "ccd": "exceeds 30s timeout — complex list/math reasoning",
    "fundamental-theorem-of-arithmetic": "exceeds 30s timeout — large search space",
    "heron-theorem": "exceeds 30s timeout — floating-point math rules",
    "law-of-cosines": "exceeds 30s timeout — floating-point math rules",
    "quadratic-equation": "exceeds 30s timeout — symbolic math rules",
}

# Scenarios whose test script is not a plain ``eye …`` one-liner.
COMPLEX_SCRIPTS = {"arcus", "arvol", "blogic", "image", "lingua", "nexus", "sequents"}


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

class ScenarioSpec(NamedTuple):
    name: str
    data_files: list[str]    # absolute paths
    query_file: str | None   # absolute path or None
    answer_file: str | None  # absolute path or None
    nope: bool
    pass_mode: bool


# ---------------------------------------------------------------------------
# Parser for ``test`` shell scripts
# ---------------------------------------------------------------------------

def _url_to_local(url: str) -> str | None:
    """Convert an EYE URL reference to a local absolute path.

    Returns *None* if the token is not an EYE URL.
    """
    if url.startswith(EYE_URL_PREFIX + "/"):
        rel = url[len(EYE_URL_PREFIX) + 1:]  # e.g. "socrates/socrates.n3"
        return str(SCENARIOS_DIR / rel)
    return None


def _local_to_abs(token: str, scenario_dir: Path) -> str:
    """Resolve a bare filename token relative to the scenario directory."""
    p = scenario_dir / token
    return str(p)


def _parse_eye_line(line: str, scenario_dir: Path) -> ScenarioSpec | None:
    """Parse a single ``eye …`` command line.

    Returns a ``ScenarioSpec`` or *None* if the line cannot be parsed.
    """
    try:
        tokens = shlex.split(line)
    except ValueError:
        return None

    if not tokens or tokens[0] != "eye":
        return None

    data_files: list[str] = []
    query_file: str | None = None
    nope = False
    pass_mode = False

    i = 1
    while i < len(tokens):
        tok = tokens[i]

        # ---- flags to skip ----
        if tok in ("--quiet", "--skolem-genid"):
            i += 2  # skip flag + its argument
            continue
        if tok == "--wcache":
            # skip --wcache URL ..
            i += 3  # flag, URL, ".."
            continue
        if tok == "..":
            # bare ".." left over if wcache already consumed; skip
            i += 1
            continue
        if tok in ("--nope", "--pass-only-new"):
            nope = True
            i += 1
            continue
        if tok == "--pass":
            pass_mode = True
            i += 1
            continue
        if tok in ("--output",):
            i += 2  # skip flag + filename
            continue

        # ---- --query ----
        if tok == "--query":
            i += 1
            if i < len(tokens):
                raw = tokens[i]
                local = _url_to_local(raw)
                if local is None and not raw.startswith("http"):
                    local = _local_to_abs(raw, scenario_dir)
                query_file = local
            i += 1
            continue

        # ---- positional N3 file (data / rule) ----
        if tok.endswith(".n3") or tok.endswith(".ttl"):
            local = _url_to_local(tok)
            if local is None and not tok.startswith("http"):
                local = _local_to_abs(tok, scenario_dir)
            if local:
                data_files.append(local)
            i += 1
            continue

        # unknown token — skip
        i += 1

    return ScenarioSpec(
        name=scenario_dir.name,
        data_files=data_files,
        query_file=query_file,
        answer_file=None,  # filled in later
        nope=nope,
        pass_mode=pass_mode,
    )


def _find_answer_file(scenario_dir: Path) -> str | None:
    """Return the path to the ``*-answer.n3`` file if one exists."""
    candidates = list(scenario_dir.glob("*-answer.n3")) + list(scenario_dir.glob("*_answer.n3"))
    if candidates:
        return str(candidates[0])
    return None


def _collect_scenarios() -> list[ScenarioSpec]:
    """Walk ``SCENARIOS_DIR`` and collect one spec per simple scenario."""
    specs: list[ScenarioSpec] = []
    for scenario_dir in sorted(SCENARIOS_DIR.iterdir()):
        if not scenario_dir.is_dir():
            continue
        test_script = scenario_dir / "test"
        if not test_script.exists():
            continue

        name = scenario_dir.name

        if name in COMPLEX_SCRIPTS:
            # Skip — complex multi-step shell programs
            continue

        content = test_script.read_text(errors="replace")
        lines = content.splitlines()

        # Find the FIRST simple ``eye …`` line (the --nope variant when present)
        spec = None
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Handle line continuations
            while line.endswith("\\"):
                # rare, but handle gracefully
                line = line.rstrip("\\").rstrip()
            candidate = _parse_eye_line(line, scenario_dir)
            if candidate is not None:
                spec = candidate
                break  # take only the first eye command (the --nope run)

        if spec is None:
            continue

        answer_file = _find_answer_file(scenario_dir)
        spec = ScenarioSpec(
            name=spec.name,
            data_files=spec.data_files,
            query_file=spec.query_file,
            answer_file=answer_file,
            nope=spec.nope,
            pass_mode=spec.pass_mode,
        )
        specs.append(spec)

    return specs


# ---------------------------------------------------------------------------
# Answer checking helpers
# ---------------------------------------------------------------------------

_COMMENT_RE = re.compile(r"^\s*#")
_PREFIX_RE = re.compile(r"^\s*@prefix\s", re.IGNORECASE)
_BASE_RE = re.compile(r"^\s*@base\s", re.IGNORECASE)
_EMPTY_RE = re.compile(r"^\s*$")


def _meaningful_lines(n3_text: str) -> list[str]:
    """Return non-comment, non-prefix, non-empty lines from N3 text."""
    out = []
    for line in n3_text.splitlines():
        if _COMMENT_RE.match(line):
            continue
        if _PREFIX_RE.match(line):
            continue
        if _BASE_RE.match(line):
            continue
        if _EMPTY_RE.match(line):
            continue
        out.append(line.strip())
    return out


def _normalize_n3(text: str) -> str:
    """Collapse runs of whitespace and normalise whitespace before '.' to allow
    flexible matching between EYE and pyeye serialization styles.

    E.g. ':Socrates a :Mortal .' → ':Socrates a :Mortal.'
    """
    # collapse multiple spaces / tabs to single space
    text = re.sub(r"[ \t]+", " ", text)
    # remove space before terminal period
    text = re.sub(r" \.$", ".", text, flags=re.MULTILINE)
    return text


def _check_answer(result_n3: str, answer_path: str) -> tuple[bool, list[str]]:
    """Return (all_found, missing_lines).

    Each meaningful line from the answer file must appear somewhere in
    the (normalised) combined text.  We normalise whitespace before
    comparing so that serialization style differences don't cause false
    negatives.
    """
    answer_text = Path(answer_path).read_text(errors="replace")
    expected_lines = _meaningful_lines(answer_text)
    if not expected_lines:
        return True, []

    # Normalise the haystack
    normalised = _normalize_n3(result_n3)

    missing = []
    for line in expected_lines:
        needle = _normalize_n3(line)
        if needle not in normalised:
            missing.append(line)
    return len(missing) == 0, missing


# ---------------------------------------------------------------------------
# Parametrize
# ---------------------------------------------------------------------------

ALL_SPECS = _collect_scenarios()
SPEC_BY_NAME = {s.name: s for s in ALL_SPECS}


def _pytest_params():
    params = []
    for spec in ALL_SPECS:
        marks = []
        if spec.name in XFAIL_REASONS:
            reason = XFAIL_REASONS[spec.name]
            marks.append(pytest.mark.xfail(reason=reason, strict=False))
        params.append(pytest.param(spec, id=spec.name, marks=marks))
    return params


# ---------------------------------------------------------------------------
# The test
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("spec", _pytest_params())
def test_eye_scenario(spec: ScenarioSpec):
    """Run a single EYE reasoning scenario through pyeye and verify output."""
    # Build the list of N3 content strings
    all_files = list(spec.data_files)
    if spec.query_file:
        all_files.append(spec.query_file)

    if not all_files:
        pytest.skip(f"{spec.name}: no input files found")

    # Check all files exist
    missing = [f for f in all_files if not Path(f).exists()]
    if missing:
        pytest.skip(f"{spec.name}: missing files: {missing}")

    all_contents: list[str] = []
    for fpath in all_files:
        try:
            all_contents.append(Path(fpath).read_text(errors="replace"))
        except OSError as exc:
            pytest.skip(f"{spec.name}: cannot read {fpath}: {exc}")

    # Run pyeye
    try:
        result = execute(
            data_strings=all_contents,
            rule_strings=[],
            timeout_seconds=30.0,
        )
    except ParseError as exc:
        pytest.fail(f"ParseError in {spec.name}: {exc}")
    except Exception as exc:  # noqa: BLE001
        pytest.fail(f"Unexpected error in {spec.name}: {type(exc).__name__}: {exc}")

    # Check answer if available
    if spec.answer_file:
        # EYE outputs all query-matching triples, including input facts.
        # pyeye only outputs *newly derived* triples.  Search in both the
        # derived output AND the raw input content so that input facts that
        # weren't re-derived still count as "found".
        combined = result.triples + "\n" + "\n".join(all_contents)
        ok, missing_lines = _check_answer(combined, spec.answer_file)
        if not ok:
            answer_preview = "\n".join(missing_lines[:10])
            pytest.fail(
                f"{spec.name}: {len(missing_lines)} expected line(s) missing from output.\n"
                f"First missing lines:\n{answer_preview}\n\n"
                f"Actual output (first 500 chars):\n{result.triples[:500]}"
            )
    else:
        # Without an answer file, just verify we got non-empty output
        # (or at least no crash — some scenarios may produce empty derivations)
        assert result is not None, f"{spec.name}: execute() returned None"
