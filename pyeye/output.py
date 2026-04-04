"""N3 serialization — converts derived triples back to N3 text."""

from __future__ import annotations

from pyeye.term import NamedNode, Literal, Variable, Existential, Formula, Triple, Term
from pyeye.term import TripleTerm, FormulaTerm, PathTerm, Quad, NegativeSurface


class N3Writer:
    """Serializes terms and triples to N3 text."""

    def __init__(self, prefixes: dict[str, str] | None = None) -> None:
        self._prefixes = dict(prefixes or {})
        self._rev: dict[str, str] = {}  # uri -> prefix:local
        for pfx, uri in self._prefixes.items():
            self._rev[uri] = pfx + ":"

    # -- public --------------------------------------------------------------

    def write_triples(self, triples: list[Triple]) -> str:
        """Serialize a list of triples to N3 text."""
        lines: list[str] = []

        # Prefix declarations
        for pfx, uri in self._prefixes.items():
            colon = ":" if pfx else ""
            lines.append(f"@prefix {pfx}{colon} <{uri}> .")
        if self._prefixes:
            lines.append("")

        # Triples
        for t in sorted(triples, key=lambda x: (str(x.subject), str(x.predicate), str(x.object))):
            lines.append(f"{self._term(t.subject)} {self._term(t.predicate)} {self._term(t.object)} .")

        return "\n".join(lines) + ("\n" if lines else "")

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
        if lit.language:
            return f'"{v}"@{lit.language}'
        if lit.datatype:
            return f'"{v}"^^{self._abbreviate(lit.datatype.value)}'
        return f'"{v}"'
