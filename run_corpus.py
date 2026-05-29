"""Standalone runner for the full EYE reasoning corpus.

Runs every discovered scenario through pyeye and reports PASS/FAIL/ERROR/
TIMEOUT/SKIP counts.  Each scenario runs in a worker subprocess so a hang or
hard crash in one scenario cannot take down the whole run.

Usage:
    python run_corpus.py            # full run, summary
    python run_corpus.py --verbose  # per-scenario lines
    python run_corpus.py --baseline # use legacy invocation (no query_paths)
"""
from __future__ import annotations

import sys
import json
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from tests.eye_scenarios import discover_scenarios  # noqa: E402
from tests.test_eye_corpus import _compare  # noqa: E402

TIMEOUT = 15.0
BASELINE = "--baseline" in sys.argv
VERBOSE = "--verbose" in sys.argv

WORKER = r'''
import sys, json
sys.path.insert(0, %(root)r)
from pyeye import execute, ReasoningTimeoutError
cfg = json.loads(sys.argv[1])
try:
    kw = dict(
        rule_paths=cfg["inputs"] or None,
        nope=cfg["nope"], pass_mode=cfg["pass_mode"], pass_all=cfg["pass_all"],
        pass_only_new=cfg["pass_only_new"],
        timeout_seconds=%(timeout)r,
        proof=cfg.get("proof", False),
        source_urls=cfg.get("source_urls") or None,
    )
    if %(baseline)s:
        # legacy: query file loaded as an ordinary rule file
        if cfg["query"]:
            kw["rule_paths"] = (cfg["inputs"] or []) + [cfg["query"]]
    else:
        if cfg["query"]:
            kw["query_paths"] = [cfg["query"]]
    r = execute(**kw)
    print("OK")
    print(r.triples)
except ReasoningTimeoutError:
    print("TIMEOUT")
except Exception as e:
    print("ERR " + type(e).__name__ + ": " + str(e)[:200])
'''


def main() -> None:
    scs = discover_scenarios()
    worker_src = WORKER % {
        "root": str(ROOT),
        "timeout": TIMEOUT,
        "baseline": "True" if BASELINE else "False",
    }
    results = []
    for sc in scs:
        if sc.skip_reason or sc.answer is None or not sc.answer.exists() or sc.strings:
            reason = (sc.skip_reason or
                      ("non-N3 output" if sc.strings else "no reference answer"))
            results.append((sc.name, "SKIP", reason))
            if VERBOSE:
                print(f"- SKIP    {sc.name}: {reason}")
            continue
        is_proof = sc.is_proof_answer
        cfg = json.dumps({
            "inputs": [str(p) for p in sc.inputs],
            "query": str(sc.query) if sc.query else None,
            "nope": sc.nope, "pass_mode": sc.pass_mode, "pass_all": sc.pass_all,
            "pass_only_new": sc.pass_only_new,
            "proof": is_proof,
            "source_urls": sc.source_urls,
        })
        try:
            proc = subprocess.run(
                [sys.executable, "-c", worker_src, cfg],
                capture_output=True, text=True, timeout=TIMEOUT + 20,
            )
            out = proc.stdout
        except subprocess.TimeoutExpired:
            results.append((sc.name, "TIMEOUT", "subprocess wall timeout"))
            if VERBOSE:
                print(f"T TIMEOUT {sc.name}")
            continue
        first, _, body = out.partition("\n")
        first = first.strip()
        if first == "TIMEOUT":
            status, detail = "TIMEOUT", f"exceeded {TIMEOUT}s"
        elif first.startswith("ERR "):
            status, detail = "ERROR", first[4:]
        elif first == "OK":
            expected = sc.answer.read_text(encoding="utf-8", errors="replace")
            ok, detail = _compare(body, expected)
            status = "PASS" if ok else "FAIL"
        else:
            status, detail = "ERROR", f"worker crashed: {proc.stderr[-200:]}"
        if is_proof and status != "PASS":
            status, detail = "PROOF", "proof-format reference output: " + detail
        results.append((sc.name, status, detail))
        if VERBOSE:
            sym = {"PASS": "✓", "FAIL": "✗", "ERROR": "E",
                   "TIMEOUT": "T"}.get(status, "?")
            print(f"{sym} {status:8s} {sc.name}: {detail[:80]}")
            sys.stdout.flush()

    counts = Counter(s for _, s, _ in results)
    total = len(results)
    plain = total - counts["SKIP"] - counts["PROOF"]
    print("\n" + "=" * 64)
    print(f"TOTAL {total} | SKIP {counts['SKIP']} | PROOF-format {counts['PROOF']}")
    print(f"PLAIN-ANSWER scenarios: {plain} | "
          f"PASS {counts['PASS']} FAIL {counts['FAIL']} "
          f"ERROR {counts['ERROR']} TIMEOUT {counts['TIMEOUT']}")
    rate = counts["PASS"] / plain * 100 if plain else 0
    print(f"PASS RATE (of plain-answer): {rate:.1f}%  "
          f"({counts['PASS']}/{plain})")
    print(f"PASS RATE (of all non-skip): "
          f"{counts['PASS'] / (total-counts['SKIP']) * 100:.1f}%  "
          f"({counts['PASS']}/{total-counts['SKIP']})")
    print("=" * 64)
    # dump failures grouped
    for st in ("FAIL", "ERROR", "TIMEOUT", "PROOF"):
        items = [(n, d) for n, s, d in results if s == st]
        if items:
            print(f"\n--- {st} ({len(items)}) ---")
            for n, d in items:
                print(f"  {n}: {d[:90]}")


if __name__ == "__main__":
    main()
