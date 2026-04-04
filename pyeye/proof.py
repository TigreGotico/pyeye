"""Proof trace output — records and serializes derivation steps.

When `explain=True` is passed to `execute()`, every derivation is
recorded as a ``ProofStep`` and assembled into a ``ProofTree``.

Public types
------------
``ProofStep`` — a single derivation step
``ProofTree`` — a tree of proof steps with a root triple and children
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pyeye.term import Triple
from pyeye.parser import Rule


@dataclass(frozen=True)
class ProofStep:
    """A single derivation step."""
    conclusion: Triple
    premise: list[Triple] | None  # the body patterns that were proven
    rule: Rule | None
    chaining: str = "forward"  # "forward" or "backward"
    source: str = ""

    def __str__(self) -> str:
        rule_src = self.rule.source if self.rule else "?"
        return f"{self.conclusion}  (from {rule_src}, {self.chaining})"


@dataclass
class ProofTree:
    """A proof tree with a root triple and child proof trees."""
    root: Triple
    children: list[ProofTree] = field(default_factory=list)
    rule: Rule | None = None
    chaining: str = "forward"

    def __str__(self, indent: int = 0) -> str:
        prefix = "  " * indent
        lines = [f"{prefix}{self.root}"]
        for child in self.children:
            lines.append(child.__str__(indent + 1))
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------

def serialize_n3(trees: list[ProofTree]) -> str:
    """Serialize proof trees to N3 triples describing the derivation."""
    from pyeye.term import NamedNode
    lines: list[str] = []
    prefix = "@prefix proof: <http://eulersharp.sourceforge.net/2003/03swap/proof#> ."
    lines.append(prefix)
    lines.append("")

    counter = 0
    for tree in trees:
        lines.extend(_tree_to_n3(tree, counter))
        counter += len(_count_nodes(tree))

    return "\n".join(lines) + "\n"


def _tree_to_n3(tree: ProofTree, base_id: int) -> list[str]:
    """Convert a proof tree to N3 triples."""
    from pyeye.term import NamedNode, Existential
    lines: list[str] = []
    step_id = Existential(f"proof-step-{base_id}")

    # Conclusion triple
    s = _term_to_n3_str(tree.root.subject)
    p = _term_to_n3_str(tree.root.predicate)
    o = _term_to_n3_str(tree.root.object)
    lines.append(f"{step_id} proof:conclusion <<{s} {p} {o}>> .")
    lines.append(f"{step_id} proof:chaining \"{tree.chaining}\" .")

    if tree.rule and tree.rule.source:
        lines.append(f"{step_id} proof:source \"{tree.rule.source}\" .")

    # Children
    for i, child in enumerate(tree.children):
        child_id = Existential(f"proof-step-{base_id + 1 + i}")
        lines.append(f"{step_id} proof:hasChild {child_id} .")

    return lines


def _count_nodes(tree: ProofTree) -> list[int]:
    """Count nodes in a proof tree (for ID allocation)."""
    result = [1]
    for child in tree.children:
        result.extend(_count_nodes(child))
    return result


def _term_to_n3_str(term) -> str:
    """Convert a term to an N3 string representation."""
    from pyeye.term import NamedNode, Literal, Variable, Existential, TripleTerm, FormulaTerm, PathTerm
    if isinstance(term, NamedNode):
        return f"<{term.value}>"
    if isinstance(term, Literal):
        return f'"{term.value}"'
    if isinstance(term, Variable):
        return f"?{term.name}"
    if isinstance(term, Existential):
        return f"_:{term.name}"
    if isinstance(term, TripleTerm):
        return f"<<{_term_to_n3_str(term.subject)} {_term_to_n3_str(term.predicate)} {_term_to_n3_str(term.object)}>>"
    if isinstance(term, FormulaTerm):
        args = " ".join(_term_to_n3_str(a) for a in term.args)
        return f"(|{_term_to_n3_str(term.functor)} {args}|)"
    if isinstance(term, PathTerm):
        parts = [_term_to_n3_str(term.terms[0])]
        for i, t in enumerate(term.terms[1:]):
            op = "!" if not term.directions or term.directions[i] == "forward" else "^"
            parts.append(f" {op} {_term_to_n3_str(t)}")
        return "".join(parts)
    return str(term)


def serialize_dot(trees: list[ProofTree]) -> str:
    """Serialize proof trees to DOT (Graphviz) format."""
    lines = ["digraph proof {", '  rankdir=TB;', '  node [shape=box, fontname="monospace"];', ""]

    counter = 0
    for tree in trees:
        lines.extend(_tree_to_dot(tree, counter))
        counter += sum(1 for _ in _flatten_tree(tree))

    lines.append("}")
    return "\n".join(lines) + "\n"


def _flatten_tree(tree: ProofTree) -> list[ProofTree]:
    """Flatten a proof tree into a list."""
    result = [tree]
    for child in tree.children:
        result.extend(_flatten_tree(child))
    return result


def _tree_to_dot(tree: ProofTree, base_id: int) -> list[str]:
    """Convert a proof tree to DOT nodes and edges."""
    lines: list[str] = []
    node_id = f"n{base_id}"
    label = str(tree.root).replace('"', '\\"')
    lines.append(f'  {node_id} [label="{label}"];')

    for i, child in enumerate(tree.children):
        child_id = f"n{base_id + 1 + i}"
        lines.append(f"  {node_id} -> {child_id};")

    # Recurse (offset IDs by children already counted)
    offset = len(tree.children)
    for i, child in enumerate(tree.children):
        sub_offset = sum(len(_flatten_tree(c)) for c in tree.children[:i])
        lines.extend(_tree_to_dot(child, base_id + 1 + sub_offset))

    return lines


def serialize_html(trees: list[ProofTree]) -> str:
    """Serialize proof trees to HTML with collapsible branches."""
    lines = [
        "<!DOCTYPE html>",
        '<html><head><style>',
        "body { font-family: monospace; margin: 2em; }",
        ".proof { margin-left: 1em; }",
        ".step { margin: 0.2em 0; }",
        "details { margin-left: 1em; }",
        "summary { cursor: pointer; }",
        "</style></head><body>",
        "<h1>Proof Trace</h1>",
    ]

    for tree in trees:
        lines.append('<div class="proof">')
        lines.extend(_tree_to_html(tree))
        lines.append("</div>")

    lines.extend(["</body></html>"])
    return "\n".join(lines)


def _tree_to_html(tree: ProofTree) -> list[str]:
    """Convert a proof tree to HTML elements."""
    lines: list[str] = []
    conclusion = str(tree.root)
    if tree.children:
        lines.append("<details open>")
        lines.append(f"<summary><span class=\"step\">{conclusion}</span></summary>")
        for child in tree.children:
            lines.append('<div class="proof">')
            lines.extend(_tree_to_html(child))
            lines.append("</div>")
        lines.append("</details>")
    else:
        lines.append(f'<div class="step">{conclusion}</div>')
    return lines
