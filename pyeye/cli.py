"""CLI entry point — ``pyeye`` command."""

from __future__ import annotations

import sys
import argparse

from pyeye.entry import execute
from pyeye.parser import ParseError


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="pyeye",
        description="Pure-Python forward-chaining N3 reasoner",
    )
    parser.add_argument("--n3", action="append", default=[],
                        help="Load N3 data file (repeatable)")
    parser.add_argument("--query", action="append", default=[],
                        help="Load N3 rule file (repeatable)")
    parser.add_argument("--pass", dest="pass_mode", action="store_true",
                        help="Output deductive closure (input + derived)")
    parser.add_argument("--pass-all", dest="pass_all", action="store_true",
                        help="Closure + rules")
    parser.add_argument("--nope", action="store_true",
                        help="No derivation (pass-through)")
    parser.add_argument("--explain", action="store_true",
                        help="Include proof explanations")
    parser.add_argument("--tactic", nargs=2, action="append", default=[],
                        metavar=("NAME", "VALUE"),
                        help="Reasoning tactic (e.g. limited-answer N)")
    parser.add_argument("--max-inferences", type=int, default=-1,
                        help="Hard step cap")
    parser.add_argument("--prefix", action="append", default=[],
                        metavar="P=URL",
                        help="Register prefix for output")
    parser.add_argument("--quiet", action="store_true",
                        help="Suppress stderr")
    parser.add_argument("--statistics", action="store_true",
                        help="Print stats to stderr")
    # Phase 2 flags
    parser.add_argument("--entail", action="store_true",
                        help="Apply RDFS entailment before user rules")
    parser.add_argument("--not-entail", dest="not_entail", action="store_true",
                        help="Check non-entailment (Phase 2)")
    parser.add_argument("--query-goal", dest="query_goal", default=None,
                        metavar="TRIPLE",
                        help="Backward chain from this triple pattern (Phase 2)")
    parser.add_argument("--no-forward", dest="no_forward", action="store_true",
                        help="Skip forward chaining (backward only)")

    args = parser.parse_args()

    # Parse prefixes
    prefixes = {}
    for p in args.prefix:
        if "=" in p:
            k, v = p.split("=", 1)
            prefixes[k] = v

    # Parse tactics
    max_steps = args.max_inferences
    limit_answers = -1
    for name, value in args.tactic:
        if name == "limited-answer":
            limit_answers = int(value)

    try:
        result = execute(
            data_paths=args.n3 or None,
            rule_paths=args.query or None,
            explain=args.explain,
            max_steps=max_steps,
            limit_answers=limit_answers,
            prefixes=prefixes or None,
            nope=args.nope,
            pass_mode=args.pass_mode,
            pass_all=args.pass_all,
            entail=args.entail,
            forward=not args.no_forward,
        )
    except Exception as exc:
        # Catch parse errors, rdflib errors, and anything else
        print(f"pyeye: error: {exc}", file=sys.stderr)
        sys.exit(1)

    sys.stdout.write(result.triples)
    sys.stdout.flush()

    if args.statistics and not args.quiet:
        stats = result.stats
        print(
            f"# steps={stats['steps']} derived={stats['derived']} "
            f"time={stats['time_ms']:.1f}ms",
            file=sys.stderr,
        )

    sys.exit(0)


if __name__ == "__main__":
    main()
