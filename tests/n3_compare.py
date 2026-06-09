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
    budget = _SearchBudget()
    # Cheapest-first: facts with fewer blank labels prune the search faster.
    def blanks(f):
        acc: set = set()
        _blank_labels(f, acc)
        return len(acc)
    nonground.sort(key=blanks)
    for final in _match_set(tuple(nonground), frozenset(actual_set), {}, budget):
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
