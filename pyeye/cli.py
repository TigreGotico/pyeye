"""CLI entry point — ``pyeye`` command."""

from __future__ import annotations

import sys
import argparse

from pyeye.entry import execute
from pyeye.parser import ParseError
from pyeye.term import Triple


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
    parser.add_argument("--explain-format", dest="explain_format",
                        choices=["n3", "dot", "html"], default="n3",
                        help="Proof output format (default: n3)")
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
    parser.add_argument("--entail-owl", dest="entail_owl", action="store_true",
                        help="Apply OWL 2 RL entailment (includes RDFS)")
    parser.add_argument("--not-entail", dest="not_entail", action="store_true",
                        help="Check that no entailment occurred (Phase 2)")
    parser.add_argument("--not-entail-triple", dest="not_entail_triple", default=None,
                        metavar="S,P,O",
                        help="Check that this triple is NOT entailed (S,P,O comma-separated)")
    parser.add_argument("--query-goal", dest="query_goal", default=None,
                        metavar="TRIPLE",
                        help="Backward chain from this triple pattern (Phase 2)")
    parser.add_argument("--no-forward", dest="no_forward", action="store_true",
                        help="Skip forward chaining (backward only)")
    parser.add_argument("--cache-dir", dest="cache_dir", default=None,
                        metavar="DIR",
                        help="Cache directory for remote N3 files")

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

    # Parse not_entail triple (S,P,O comma-separated)
    not_entail_triple = None
    if args.not_entail_triple:
        from pyeye.term import NamedNode
        parts = args.not_entail_triple.split(",", 2)
        if len(parts) == 3:
            not_entail_triple = Triple(
                NamedNode(parts[0].strip()),
                NamedNode(parts[1].strip()),
                NamedNode(parts[2].strip()),
            )

    # Parse query goal (S,P,O comma-separated; ?Name marks a variable)
    query_triple = None
    if args.query_goal:
        from pyeye.term import NamedNode, Variable

        def _goal_term(text: str):
            text = text.strip()
            if text.startswith("?"):
                return Variable(text[1:])
            return NamedNode(text)

        parts = args.query_goal.split(",", 2)
        if len(parts) != 3:
            print("pyeye: error: --query-goal expects 'S,P,O' (comma-separated)",
                  file=sys.stderr)
            sys.exit(1)
        query_triple = Triple(*(_goal_term(p) for p in parts))

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
            entail_owl=args.entail_owl,
            query=query_triple,
            forward=not args.no_forward,
            not_entail=not_entail_triple,
            cache_dir=args.cache_dir,
            explain_format=args.explain_format,
        )
    except Exception as exc:
        # Catch parse errors, rdflib errors, and anything else
        print(f"pyeye: error: {exc}", file=sys.stderr)
        sys.exit(1)

    if args.explain:
        # Proof traces replace the normal triple output.
        if isinstance(result.explains, str):  # "dot" / "html" formats
            sys.stdout.write(result.explains)
        else:  # "n3" — raw ProofTree list
            from pyeye.proof import serialize_n3
            sys.stdout.write(serialize_n3(result.explains))
    elif query_triple is not None:
        # Print one ground triple per backward-chaining answer.
        from pyeye.output import N3Writer
        from pyeye.term import Variable

        def _subst(term, binding):
            if isinstance(term, Variable):
                return binding.get(term.name, term)
            return term

        answer_triples = [
            Triple(_subst(query_triple.subject, b),
                   _subst(query_triple.predicate, b),
                   _subst(query_triple.object, b))
            for b in result.query_answers
        ]
        sys.stdout.write(N3Writer(prefixes or None).write_triples(answer_triples))
    else:
        sys.stdout.write(result.triples)
    sys.stdout.flush()

    if not args.quiet:
        if args.not_entail and result.stats.get("derived", 0) > 0:
            print(f"# not-entail check failed: "
                  f"{result.stats['derived']} triple(s) derived",
                  file=sys.stderr)
        if not_entail_triple is not None and result.stats.get("not_entail_failed"):
            print("# not-entail check failed: triple was derived",
                  file=sys.stderr)

    if args.statistics and not args.quiet:
        stats = result.stats
        print(
            f"# steps={stats['steps']} derived={stats['derived']} "
            f"time={stats['time_ms']:.1f}ms",
            file=sys.stderr,
        )

    sys.exit(0)


if __name__ == "__main__":  # pragma: no cover — script entry point
    main()
