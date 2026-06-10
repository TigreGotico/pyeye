"""Semantic N3 answer comparison for the EYE conformance corpus.

Both the pyeye output and the EYE reference answer are parsed with pyeye's own
N3 parser and reduced to canonical fact sets.  A scenario answer matches when
every expected fact is present in the actual output under some consistent
mapping of blank-ish labels (blank nodes, skolem genid IRIs, and quantified
variables) to actual terms — i.e. simple-entailment containment, so label
choices and statement order never matter.

Facts compare structurally: formulas as unordered triple sets, lists in order,
numeric literals by value.  If either side fails to parse, the caller falls
back to line-based comparison.
"""

from __future__ import annotations

import re

from pyeye.term import (
    Existential,
    Formula,
    FormulaTerm,
    ListTerm,
    Literal,
    NamedNode,
    NegativeSurface,
    Quad,
    SetTerm,
    Triple,
    TripleTerm,
    Variable,
)

_XSD = "http://www.w3.org/2001/XMLSchema#"
_GENID_RE = re.compile(r"/\.well-known/genid/|^bnode://|#_genid|/genid[#/]")

# A canonical term is a nested tuple structure; blank-ish terms become
# ("?", label) nodes that participate in the homomorphism search.
_BLANK = "?"


class _SearchBudget:
    """Caps the backtracking search so a pathological answer can't hang."""

    def __init__(self, steps: int = 200_000) -> None:
        self.steps = steps

    def tick(self) -> bool:
        self.steps -= 1
        return self.steps > 0


def _is_genid_iri(value: str) -> bool:
    return bool(_GENID_RE.search(value))


def _canon_iri(value: str) -> str:
    """Make machine-local file IRIs comparable.

    Reference answers embed absolute ``file://`` paths from the machine that
    generated them; pyeye emits paths from this checkout.  Both reduce to the
    scenario-relative tail (last two path segments) so they can match.
    """
    if not value.startswith("file://"):
        return value
    path, sep, frag = value.partition("#")
    tail = "/".join(path.rstrip("/").split("/")[-2:])
    return f"file://{tail}{sep}{frag}"


def _canon_literal(lit: Literal) -> tuple:
    dt = lit.datatype.value if lit.datatype else None
    value = lit.value
    if dt in (_XSD + "integer", _XSD + "long", _XSD + "int"):
        try:
            return ("lit", str(int(value)), _XSD + "integer", None)
        except ValueError:
            pass
    if dt in (_XSD + "decimal", _XSD + "double", _XSD + "float"):
        try:
            num = float(value)
            if num == int(num) and abs(num) < 1e15:
                text = str(int(num))
            else:
                text = repr(num)
            return ("lit", text, "num", None)
        except ValueError:
            pass
    if dt == _XSD + "string":
        dt = None
    return ("lit", value, dt, lit.language)


def canon(term) -> tuple:
    """Reduce a pyeye term to a canonical hashable structure."""
    if isinstance(term, NamedNode):
        if _is_genid_iri(term.value):
            return (_BLANK, "iri:" + term.value)
        return ("iri", _canon_iri(term.value))
    if isinstance(term, Literal):
        return _canon_literal(term)
    if isinstance(term, Existential):
        return (_BLANK, "bn:" + term.name)
    if isinstance(term, Variable):
        return (_BLANK, "var:" + term.name)
    if isinstance(term, ListTerm):
        return ("list", tuple(canon(i) for i in term.items))
    if isinstance(term, SetTerm):
        return ("set", frozenset(canon(e) for e in term.elements))
    if isinstance(term, TripleTerm):
        return ("tt", canon(term.subject), canon(term.predicate), canon(term.object))
    if isinstance(term, FormulaTerm):
        return ("ft", canon(term.functor), tuple(canon(a) for a in term.args))
    if isinstance(term, NegativeSurface):
        return ("neg", canon(term.formula))
    if isinstance(term, Formula):
        return ("graph", frozenset(_canon_triple(t) for t in term.triples))
    if isinstance(term, Quad):
        return ("quad", canon(term.subject), canon(term.predicate),
                canon(term.object), canon(term.graph) if term.graph else None)
    if isinstance(term, Triple):
        return _canon_triple(term)
    return ("raw", str(term))


def _canon_triple(t: Triple) -> tuple:
    return ("t", canon(t.subject), canon(t.predicate), canon(t.object))


def _is_ground(node) -> bool:
    if isinstance(node, frozenset):
        return all(_is_ground(e) for e in node)
    if not isinstance(node, tuple):
        return True
    if node and node[0] == _BLANK:
        return False
    return all(_is_ground(c) for c in node)


def _blank_labels(node, acc: set) -> None:
    if not isinstance(node, (tuple, frozenset)):
        return
    if isinstance(node, tuple) and node and node[0] == _BLANK:
        acc.add(node[1])
        return
    for c in node:
        _blank_labels(c, acc)


def _match(exp, act, mapping: dict, budget: _SearchBudget):
    """Match a canonical expected node against an actual node.

    Yields extended mappings (expected blank label -> actual canonical term).
    """
    if not budget.tick():
        return
    if isinstance(exp, tuple) and exp and exp[0] == _BLANK:
        label = exp[1]
        if label in mapping:
            if mapping[label] == act:
                yield mapping
            return
        new = dict(mapping)
        new[label] = act
        yield new
        return
    if isinstance(exp, frozenset):
        if not isinstance(act, frozenset):
            return
        yield from _match_set(tuple(exp), act, mapping, budget)
        return
    if isinstance(exp, tuple):
        if not isinstance(act, tuple) or len(exp) != len(act):
            return
        if exp and act and isinstance(exp[0], str) and exp[0] != act[0]:
            return
        yield from _match_seq(exp, act, mapping, budget)
        return
    if exp == act:
        yield mapping


def _match_seq(exps, acts, mapping, budget):
    if not exps:
        yield mapping
        return
    for m1 in _match(exps[0], acts[0], mapping, budget):
        yield from _match_seq(exps[1:], acts[1:], m1, budget)


def _match_set(exps, act_set, mapping, budget):
    """Match an unordered collection (formula contents) by backtracking."""
    if not exps:
        yield mapping
        return
    head, rest = exps[0], exps[1:]
    for candidate in act_set:
        for m1 in _match(head, candidate, mapping, budget):
            yield from _match_set(rest, act_set, m1, budget)


def _fact_key(fact):
    """Bucket key for a top-level fact: its tag plus ground predicate.

    A fact whose predicate is ground can only match facts with the same
    canonical predicate, so candidate selection narrows to that bucket.
    Facts with a blank predicate get key (tag, None) and match against
    every bucket of the same tag.
    """
    if not isinstance(fact, tuple) or not fact:
        return (None, None)
    tag = fact[0]
    if tag in ("t", "quad", "tt") and len(fact) >= 3:
        pred = fact[2]
        if isinstance(pred, tuple) and pred and pred[0] == _BLANK:
            return (tag, None)
        return (tag, pred)
    if tag == "rule" and len(fact) >= 2:
        return (tag, fact[1])
    return (tag, None)


def _match_facts(exps, buckets, all_facts, mapping, budget):
    """Containment search over top-level facts with bucketed candidates.

    At each step the *most constrained* remaining fact — the one with the
    fewest actual facts it can still match under the current mapping — is
    branched on first.  This unit-propagates chains of interlinked blank
    nodes instead of thrashing on interchangeable ones.
    """
    if not exps:
        yield mapping
        return
    best_i = -1
    best_cands: list = []
    for i, e in enumerate(exps):
        tag, pred = _fact_key(e)
        pool = all_facts if pred is None else buckets.get((tag, pred), ())
        cands = []
        for c in pool:
            for _m in _match(e, c, mapping, budget):
                cands.append(c)
                break
            if best_i != -1 and len(cands) >= len(best_cands):
                break
        if best_i == -1 or len(cands) < len(best_cands):
            best_i, best_cands = i, cands
            if not best_cands:
                return
            if len(best_cands) == 1:
                break
    head = exps[best_i]
    rest = exps[:best_i] + exps[best_i + 1:]
    for candidate in best_cands:
        for m1 in _match(head, candidate, mapping, budget):
            yield from _match_facts(rest, buckets, all_facts, m1, budget)


def _blank_signatures(facts: list) -> dict:
    """Stable structural signature per blank label (WL-style refinement).

    Each blank label's signature summarizes the facts it occurs in, with
    other blanks abstracted to their previous-round signature.  Labels whose
    final signature is unique within their graph can be aligned across two
    graphs directly, without search.
    """
    def render(node, sigs):
        if isinstance(node, frozenset):
            return ("set", frozenset(render(c, sigs) for c in node))
        if isinstance(node, tuple):
            if node and node[0] == _BLANK:
                return ("sig", sigs.get(node[1], 0))
            return tuple(render(c, sigs) if isinstance(c, (tuple, frozenset))
                         else c for c in node)
        return node

    labels: set = set()
    for f in facts:
        _blank_labels(f, labels)
    occurrences: dict = {lb: [] for lb in labels}
    for f in facts:
        in_fact: set = set()
        _blank_labels(f, in_fact)
        for lb in in_fact:
            occurrences[lb].append(f)
    sigs: dict = {lb: 0 for lb in labels}
    for _round in range(6):
        new_sigs = {}
        for lb in labels:
            marked = [render(f, {**sigs, lb: "self"}) for f in occurrences[lb]]
            new_sigs[lb] = hash(frozenset((m, marked.count(m)) for m in marked))
        if new_sigs == sigs:
            break
        sigs = new_sigs
    return sigs


def _substitute(node, mapping):
    """Replace mapped blank labels in a canonical node."""
    if isinstance(node, frozenset):
        return frozenset(_substitute(c, mapping) for c in node)
    if isinstance(node, tuple):
        if node and node[0] == _BLANK and node[1] in mapping:
            return mapping[node[1]]
        return tuple(_substitute(c, mapping) if isinstance(c, (tuple, frozenset))
                     else c for c in node)
    return node


def _signature_alignment(expected: list, actual_set: set) -> tuple[bool, str] | None:
    """Fast path: align blanks by unique structural signature, then verify.

    Sound (the verification is exact set containment after substitution);
    returns None when alignment is ambiguous or verification fails, so the
    caller falls back to the backtracking search.
    """
    exp_sigs = _blank_signatures(expected)
    act_sigs = _blank_signatures(list(actual_set))
    by_sig_exp: dict = {}
    for lb, s in exp_sigs.items():
        by_sig_exp.setdefault(s, []).append(lb)
    by_sig_act: dict = {}
    for lb, s in act_sigs.items():
        by_sig_act.setdefault(s, []).append(lb)
    mapping = {}
    for s, exp_lbs in by_sig_exp.items():
        act_lbs = by_sig_act.get(s, [])
        if len(exp_lbs) != 1 or len(act_lbs) != 1:
            return None
        mapping[exp_lbs[0]] = (_BLANK, act_lbs[0])
    missing = sum(1 for f in expected if _substitute(f, mapping) not in actual_set)
    if missing:
        return None
    return True, f"all {len(expected)} expected facts present " \
                 f"({len(mapping)} blanks aligned by signature)"


def _containment(expected: list, actual: list) -> tuple[bool, str]:
    """Every expected fact must match some actual fact consistently."""
    actual_set = set(actual)
    ground = [f for f in expected if _is_ground(f)]
    missing = [f for f in ground if f not in actual_set]
    if missing:
        return False, f"missing {len(missing)}/{len(expected)} (ground): " \
                      f"{_render(missing[0])[:120]}"
    nonground = [f for f in expected if not _is_ground(f)]
    if not nonground:
        return True, f"all {len(expected)} expected facts present"
    aligned = _signature_alignment(expected, actual_set)
    if aligned is not None:
        return aligned
    budget = _SearchBudget()
    buckets: dict = {}
    for f in actual_set:
        buckets.setdefault(_fact_key(f), []).append(f)
    # Most-constrained-first: facts with the fewest candidate matches (then
    # the fewest blank labels) prune the search fastest.
    def constraint(f):
        acc: set = set()
        _blank_labels(f, acc)
        tag, pred = _fact_key(f)
        n_cand = len(actual_set) if pred is None else len(buckets.get((tag, pred), ()))
        return (n_cand, len(acc))
    nonground.sort(key=constraint)
    for final in _match_facts(tuple(nonground), buckets, tuple(actual_set), {},
                              budget):
        return True, f"all {len(expected)} expected facts present " \
                     f"({len(nonground)} via blank mapping)"
    if budget.steps <= 0:
        return False, f"blank-mapping search budget exhausted " \
                      f"({len(nonground)} non-ground facts)"
    return False, f"no consistent blank mapping for {len(nonground)} facts: " \
                  f"{_render(nonground[0])[:120]}"


def _render(node) -> str:
    if isinstance(node, frozenset):
        return "{" + " . ".join(sorted(_render(c) for c in node)) + "}"
    if not isinstance(node, tuple):
        return str(node)
    if node and node[0] == _BLANK:
        return "_:" + str(node[1])
    if node and node[0] == "iri":
        return f"<{node[1]}>"
    if node and node[0] == "lit":
        return f'"{node[1]}"'
    return "(" + " ".join(_render(c) for c in node[1:]) + ")"


def document_facts(doc) -> list:
    """Canonical facts of a ParsedDocument: triples, quads, and rules."""
    facts = [_canon_triple(t) for t in doc.triples]
    facts.extend(canon(q) for q in doc.quads)
    for r in doc.rules:
        kind = "<=" if r.is_backward else "=>"
        facts.append(("rule", kind, canon(r.body), canon(r.head)))
    return facts


def compare_semantic(actual_text: str, expected_text: str) -> tuple[bool, str]:
    """Parse both sides and check expected ⊆ actual under blank mapping.

    Raises on parse failure so the caller can fall back to line comparison.
    """
    from pyeye.parser import parse_n3

    expected = document_facts(parse_n3(expected_text, source="expected"))
    actual = document_facts(parse_n3(actual_text, source="actual"))
    if not expected:
        if not actual:
            return True, "both empty"
        return False, f"expected empty, got {len(actual)} facts"
    return _containment(expected, actual)
