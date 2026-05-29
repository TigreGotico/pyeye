"""Auto-discovery of EYE ``reasoning/`` scenarios from their ``test`` scripts.

Each scenario directory under the upstream EYE ``reasoning/`` corpus ships a
``test`` shell script encoding the exact ``eye`` invocation that produced the
reference output checked into the repo.  We parse the FIRST ``eye`` command in
that script (the answer-producing run) to recover:

  * the list of input files (data + rule files),
  * the optional ``--query`` file,
  * the output mode (``--nope`` / ``--pass`` / ``--pass-all`` / ``--pass-only-new``),
  * the ``--output`` reference file (the expected answer).

This module is the single source of truth for the parametrised pytest suite in
``test_eye_reasoning.py`` and for the standalone baseline runner.
"""

from __future__ import annotations

import re
import shlex
from dataclasses import dataclass, field
from pathlib import Path

EYE_REASONING = Path(
    "/mnt/homelab/Workspace/external repos/eye/reasoning"
)

# URLs in the test scripts look like
#   https://eyereasoner.github.io/eye/reasoning/<scenario>/<file>
_URL_PREFIXES = (
    "https://eyereasoner.github.io/eye/reasoning/",
    "http://josd.github.io/eye/reasoning/",
    "https://josd.github.io/eye/reasoning/",
)

# Batch test-runners / non-N3-answer scenarios that iterate over an ``input/``
# directory or emit Prolog-VM / TriG / image output — out of scope for the
# N3-answer conformance suite.
_OUT_OF_SCOPE = {
    "arcus": "meta test-runner (delegates to other scenarios via $1)",
    "arvol": "batch --prolog runner over input/*.pl",
    "blogic": "batch runner over input/ dir",
    "lingua": "batch --rdf-trig-output runner over input/",
    "nexus": "meta test-runner (delegates to other scenarios)",
    "sequents": "batch runner over input/ dir",
    "image": "uses swipl -x ype.pvm, not eye",
    "fuse": "expects inconsistency reported on stderr (2> .err), no N3 answer",
}

_OUTPUT_MODE_FLAGS = {
    "--nope",
    "--pass",
    "--pass-all",
    "--pass-only-new",
}

# Flags that take a following value argument (so we skip that value when
# scanning for positional input files).
_FLAGS_WITH_VALUE = {
    "--skolem-genid",
    "--wcache",
    "--query",
    "--output",
    "--proof",
    "--tactic",
    "--n",
    "--hmac-key",
    "--strings",
    "--entail",
}


@dataclass
class Scenario:
    name: str
    inputs: list[Path] = field(default_factory=list)   # data + rule files
    query: Path | None = None
    answer: Path | None = None                          # reference output file
    nope: bool = False
    pass_mode: bool = False
    pass_all: bool = False
    pass_only_new: bool = False
    strings: bool = False                               # --strings: non-N3 output
    raw_cmd: str = ""
    skip_reason: str | None = None                      # set if undiscoverable


def _url_to_local(scenario_dir: Path, token: str) -> Path | None:
    """Map a test-script token to a local file path, or None if not a file."""
    for pref in _URL_PREFIXES:
        if token.startswith(pref):
            return EYE_REASONING / token[len(pref):]
    if token in {"..", ".", ""} or token.startswith("-"):
        return None
    # bare relative filename / relative path (lives under the scenario dir)
    return (scenario_dir / token)


def _first_eye_command(test_text: str) -> str | None:
    for line in test_text.splitlines():
        line = line.strip()
        if line.startswith("eye ") or line == "eye":
            return line
    return None


def parse_test_script(scenario_dir: Path) -> Scenario:
    name = scenario_dir.name
    test_path = scenario_dir / "test"
    sc = Scenario(name=name)
    if name in _OUT_OF_SCOPE:
        sc.skip_reason = _OUT_OF_SCOPE[name]
        return sc
    if not test_path.exists():
        sc.skip_reason = "no test script"
        return sc
    cmd = _first_eye_command(test_path.read_text(encoding="utf-8", errors="replace"))
    if cmd is None:
        sc.skip_reason = "no eye command in test script"
        return sc
    sc.raw_cmd = cmd

    try:
        tokens = shlex.split(cmd)
    except ValueError:
        tokens = cmd.split()

    # Drop leading 'eye'
    if tokens and tokens[0] == "eye":
        tokens = tokens[1:]

    # Strip a trailing shell redirection ('> file' or '| cwm > file'); the
    # redirect target is the reference answer when no --output flag is present.
    redirect_target: str | None = None
    if ">" in tokens:
        gt = tokens.index(">")
        if gt + 1 < len(tokens):
            redirect_target = tokens[gt + 1]
        tokens = tokens[:gt]
    if "|" in tokens:
        tokens = tokens[: tokens.index("|")]

    i = 0
    seen_dotdot = False
    while i < len(tokens):
        tok = tokens[i]
        if tok in _OUTPUT_MODE_FLAGS:
            if tok == "--nope":
                sc.nope = True
            elif tok == "--pass":
                sc.pass_mode = True
            elif tok == "--pass-all":
                sc.pass_all = True
            elif tok == "--pass-only-new":
                sc.pass_only_new = True
            i += 1
            continue
        if tok == "--query":
            if i + 1 < len(tokens):
                sc.query = _url_to_local(scenario_dir, tokens[i + 1])
            i += 2
            continue
        if tok == "--output":
            if i + 1 < len(tokens):
                p = _url_to_local(scenario_dir, tokens[i + 1])
                sc.answer = p
            i += 2
            continue
        if tok == "..":
            seen_dotdot = True
            i += 1
            continue
        if tok == "--strings":
            sc.strings = True
            i += 1
            continue
        if tok in _FLAGS_WITH_VALUE:
            i += 2
            continue
        if tok.startswith("-"):
            # unknown bare flag, no value
            i += 1
            continue
        # positional token: candidate input file.  When the script uses the
        # ``.. <url>`` convention we only count tokens after ``..``; otherwise
        # (bare relative filenames) every positional is an input.
        p = _url_to_local(scenario_dir, tok)
        if p is not None:
            sc.inputs.append(p)
        i += 1

    # Expand shell globs (e.g. ``*.n3``) and keep only existing files.
    expanded: list[Path] = []
    for p in sc.inputs:
        if "*" in p.name or "?" in p.name:
            expanded.extend(sorted(p.parent.glob(p.name)))
        else:
            expanded.append(p)
    # Drop the answer file itself if it got globbed in (e.g. issue148-answer.n3
    # matched by *.n3) and any non-existent paths.
    seen = set()
    sc.inputs = []
    for p in expanded:
        if p.exists() and p not in seen:
            sc.inputs.append(p)
            seen.add(p)

    if sc.answer is None and redirect_target is not None:
        sc.answer = scenario_dir / redirect_target

    # Never feed the reference answer file back in as an input (can happen when
    # a glob like ``*.n3`` matches ``<name>-answer.n3``).
    if sc.answer is not None:
        sc.inputs = [p for p in sc.inputs if p.resolve() != sc.answer.resolve()]

    return sc


def discover_scenarios() -> list[Scenario]:
    out: list[Scenario] = []
    for d in sorted(EYE_REASONING.iterdir()):
        if not d.is_dir():
            continue
        if d.name in {"prepare"}:
            continue
        sc = parse_test_script(d)
        out.append(sc)
    return out


if __name__ == "__main__":
    scs = discover_scenarios()
    print(f"discovered {len(scs)} scenarios")
    miss_answer = [s.name for s in scs if s.answer is None or not s.answer.exists()]
    miss_inputs = [s.name for s in scs if not s.inputs]
    print(f"with answer file: {sum(1 for s in scs if s.answer and s.answer.exists())}")
    print(f"missing answer file: {len(miss_answer)} -> {miss_answer}")
    print(f"no inputs discovered: {len(miss_inputs)} -> {miss_inputs}")
