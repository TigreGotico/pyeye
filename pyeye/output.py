"""N3 serialization — converts derived triples back to N3 text."""

from __future__ import annotations

from collections import defaultdict

from pyeye.term import NamedNode, Literal, Variable, Existential, Formula, Triple, Term
from pyeye.term import TripleTerm, FormulaTerm, PathTerm, Quad, NegativeSurface


class N3Writer:
    """Serializes terms and triples to N3 text.

    M10 fix: Collapses blank node subjects into Turtle-style
    ``[ ... ]`` property lists and inlines singly-referenced blank
    node objects.
    """

    def __init__(self, prefixes: dict[str, str] | None = None) -> None:
        self._prefixes = dict(prefixes or {})
        self._rev: dict[str, str] = {}  # uri -> prefix:local
        for pfx, uri in self._prefixes.items():
            self._rev[uri] = pfx + ":"

    # -- public --------------------------------------------------------------

    def write_triples(self, triples: list[Triple]) -> str:
        """Serialize a list of triples to N3 text.

        M10 fix: Blank node subjects are collapsed into ``[ pred obj; ... ]``
        property lists. Blank node objects that are only used once are
        inlined.
        """
        if not triples:
            return self._write_prefix_block("")

        # Group triples by subject
        by_subject: dict[Term, list[Triple]] = defaultdict(list)
        for t in triples:
            by_subject[t.subject].append(t)

        # Identify blank node subjects and which are referenced as objects
        bnode_subjects: set[str] = set()
        bnode_refs: dict[str, int] = defaultdict(int)  # count of references as object

        for t in triples:
            if isinstance(t.subject, Existential):
                bnode_subjects.add(t.subject.name)
            if isinstance(t.object, Existential):
                bnode_refs[t.object.name] += 1

        # Build output, collapsing blank node property lists
        lines: list[str] = []

        # Sort subjects for deterministic output
        sorted_subjects = sorted(by_subject.keys(), key=lambda s: (
            0 if isinstance(s, NamedNode) else 1,
            str(s),
        ))

        for subj in sorted_subjects:
            trip_list = by_subject[subj]
            # Sort triples within each subject by (predicate, object)
            trip_list.sort(key=lambda t: (str(t.predicate), str(t.object)))

            if isinstance(subj, Existential) and subj.name in bnode_subjects:
                # This is a blank node subject — use [ ... ] syntax
                pred_objs: list[str] = []
                for t in trip_list:
                    pred_str = self._term(t.predicate)
                    obj_str = self._term_for_object(t.object, bnode_subjects, bnode_refs)
                    pred_objs.append(f"{pred_str} {obj_str}")

                # Collapse using semicolons
                collapsed = "; ".join(pred_objs)
                lines.append(f"[ {collapsed} ] .")
            else:
                # Normal subject
                subj_str = self._term(subj)
                for t in trip_list:
                    pred_str = self._term(t.predicate)
                    obj_str = self._term_for_object(t.object, bnode_subjects, bnode_refs)
                    lines.append(f"{subj_str} {pred_str} {obj_str} .")

        return self._write_prefix_block("\n".join(lines))

    def write_quads(self, quads: list[Quad]) -> str:
        """Serialize a list of quads to TriG text (named graphs)."""
        # Group by graph
        by_graph: dict[str | None, list[Triple]] = {}
        for q in quads:
            g = str(q.graph) if q.graph else None
            by_graph.setdefault(g, []).append(q.to_triple())

        lines: list[str] = []
        for pfx, uri in self._prefixes.items():
            colon = ":" if pfx else ""
            lines.append(f"@prefix {pfx}{colon} <{uri}> .")
        if self._prefixes:
            lines.append("")

        # Default graph first
        default = by_graph.pop(None, [])
        for t in sorted(default, key=lambda x: (str(x.subject), str(x.predicate), str(x.object))):
            lines.append(f"{self._term(t.subject)} {self._term(t.predicate)} {self._term(t.object)} .")

        # Named graphs
        for gname in sorted(by_graph.keys()):
            lines.append(f"\nGRAPH {gname} {{")
            for t in sorted(by_graph[gname], key=lambda x: (str(x.subject), str(x.predicate), str(x.object))):
                lines.append(f"  {self._term(t.subject)} {self._term(t.predicate)} {self._term(t.object)} .")
            lines.append("}")

        return "\n".join(lines) + ("\n" if lines else "")

    def _write_prefix_block(self, body: str) -> str:
        """Combine prefix declarations with body text."""
        lines: list[str] = []
        for pfx, uri in self._prefixes.items():
            colon = ":" if pfx else ""
            lines.append(f"@prefix {pfx}{colon} <{uri}> .")
        if self._prefixes:
            lines.append("")
        if body:
            lines.append(body)
        return "\n".join(lines) + ("\n" if lines else "")

    def _term_for_object(
        self,
        obj: Term,
        bnode_subjects: set[str],
        bnode_refs: dict[str, int],
    ) -> str:
        """Render an object term, inlining blank nodes where appropriate.

        M10 fix: If the object is a blank node that is also a subject
        with only one reference, inline it as ``[ ... ]``.
        """
        if isinstance(obj, Existential) and obj.name in bnode_subjects:
            if bnode_refs.get(obj.name, 0) <= 1:
                # This blank node is a subject — will be rendered separately
                return f"_:{obj.name}"
        return self._term(obj)

    # -- term rendering ------------------------------------------------------

    def _term(self, t: Term) -> str:
        if isinstance(t, NamedNode):
            return self._abbreviate(t.value)
        if isinstance(t, Literal):
            return self._render_literal(t)
        if isinstance(t, Variable):
            return f"?{t.name}"
        if isinstance(t, Existential):
            return f"_:{t.name}"
        if isinstance(t, Formula):
            inner = "; ".join(
                f"{self._term(tr.subject)} {self._term(tr.predicate)} {self._term(tr.object)}"
                for tr in t.triples
            )
            return f"{{{inner}}}"
        # Phase 2 extended types
        if isinstance(t, TripleTerm):
            return f"<<{self._term(t.subject)} {self._term(t.predicate)} {self._term(t.object)}>>"
        if isinstance(t, FormulaTerm):
            args_str = " ".join(self._term(a) for a in t.args)
            return f"(|{self._term(t.functor)} {args_str}|)"
        if isinstance(t, PathTerm):
            parts = [self._term(t.terms[0])]
            for i, term in enumerate(t.terms[1:]):
                op = "!" if not t.directions or t.directions[i] == "forward" else "^"
                parts.append(f" {op} {self._term(term)}")
            return "".join(parts)
        if isinstance(t, NegativeSurface):
            inner = "; ".join(
                f"{self._term(tr.subject)} {self._term(tr.predicate)} {self._term(tr.object)}"
                for tr in t.formula.triples
            )
            return f"{{{{{inner}}}}}"  # double braces for negation
        return str(t)

    def _abbreviate(self, uri: str) -> str:
        # Try registered prefixes
        for full_uri, short in self._rev.items():
            if uri.startswith(full_uri):
                local = uri[len(full_uri):]
                return short + local
        # Fallback: full IRI
        return f"<{uri}>"

    def _render_literal(self, lit: Literal) -> str:
        v = lit.value
        # Escape quotes
        v = v.replace('"', '\\"')

        # M11 fix: Normalize boolean output to bare true/false
        XSD_BOOL = "http://www.w3.org/2001/XMLSchema#boolean"
        if lit.datatype and lit.datatype.value == XSD_BOOL:
            return v  # bare true or false

        if lit.language:
            return f'"{v}"@{lit.language}'
        if lit.datatype:
            return f'"{v}"^^{self._abbreviate(lit.datatype.value)}'
        return f'"{v}"'
