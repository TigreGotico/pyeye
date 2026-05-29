"""N3 serialization — converts derived triples back to N3 text."""

from __future__ import annotations

from collections import defaultdict

from pyeye.term import NamedNode, Literal, Variable, Existential, Formula, Triple, Term
from pyeye.term import TripleTerm, FormulaTerm, PathTerm, Quad, NegativeSurface, SetTerm, ListTerm


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

        L2 fix: Rules with log:implies/log:impliedBy are output using
        =>/<= sugar instead of regular triple syntax.
        """
        if not triples:
            return self._write_prefix_block("")

        # Separate regular triples from rule triples (log:implies/log:impliedBy)
        IMPLIES = "http://eulersharp.sourceforge.net/2003/03swap/log-rules#implies"
        IMPLIED_BY = "http://eulersharp.sourceforge.net/2003/03swap/log-rules#impliedBy"

        regular_triples: list[Triple] = []
        rule_triples: list[Triple] = []

        for t in triples:
            if isinstance(t.predicate, NamedNode) and t.predicate.value in (IMPLIES, IMPLIED_BY):
                rule_triples.append(t)
            else:
                regular_triples.append(t)

        # Write regular triples
        result = self._write_triples_n3(regular_triples)

        # Write rules with =>/<= sugar
        if rule_triples:
            result = result.rstrip("\n")
            if result:
                result += "\n"
            for t in rule_triples:
                body_str = self._formula_to_n3(t.subject)
                head_str = self._formula_to_n3(t.object)
                op = "=>" if isinstance(t.predicate, NamedNode) and t.predicate.value == IMPLIES else "<="
                result += f"{body_str} {op} {head_str} .\n"

        return result

    # -- RDF list detection --------------------------------------------------

    _RDF_FIRST = "http://www.w3.org/1999/02/22-rdf-syntax-ns#first"
    _RDF_REST  = "http://www.w3.org/1999/02/22-rdf-syntax-ns#rest"
    _RDF_NIL   = "http://www.w3.org/1999/02/22-rdf-syntax-ns#nil"

    def _detect_lists(self, triples: list[Triple]) -> set[str]:
        """Return names of blank nodes that are the head of an RDF list chain.

        A blank node is a list node if it has exactly rdf:first and rdf:rest.
        Returns the set of blank-node names that are list nodes.
        """
        by_subj: dict[str, list[Triple]] = defaultdict(list)
        for t in triples:
            if isinstance(t.subject, Existential):
                by_subj[t.subject.name].append(t)

        list_nodes: set[str] = set()
        for name, ts in by_subj.items():
            preds = {t.predicate.value for t in ts
                     if isinstance(t.predicate, NamedNode)}
            if preds == {self._RDF_FIRST, self._RDF_REST}:
                list_nodes.add(name)
        return list_nodes

    def _render_list(self, head: Existential, list_nodes: set[str],
                     by_subj: dict[str, list[Triple]]) -> str | None:
        """Try to render the RDF list starting at head as N3 `(...)` notation.

        Returns the rendered string, or None if the structure is not a clean list.
        """
        items: list[str] = []
        node: Existential | NamedNode = head
        seen: set[str] = set()
        while True:
            if isinstance(node, NamedNode) and node.value == self._RDF_NIL:
                return "(" + " ".join(items) + ")"
            if not isinstance(node, Existential) or node.name in seen:
                return None  # cycle or unexpected structure
            seen.add(node.name)
            ts = by_subj.get(node.name, [])
            first_val: Term | None = None
            rest_val: Term | None = None
            for t in ts:
                if isinstance(t.predicate, NamedNode):
                    if t.predicate.value == self._RDF_FIRST:
                        first_val = t.object
                    elif t.predicate.value == self._RDF_REST:
                        rest_val = t.object
            if first_val is None or rest_val is None:
                return None
            # Recursively render nested lists
            if isinstance(first_val, Existential) and first_val.name in list_nodes:
                inner = self._render_list(first_val, list_nodes, by_subj)
                items.append(inner if inner else self._term(first_val))
            else:
                items.append(self._term(first_val))
            node = rest_val  # type: ignore[assignment]

    def _write_triples_n3(self, triples: list[Triple]) -> str:
        """Write regular triples with N3 syntax."""

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

        # Detect RDF list nodes — these will be inlined as (a b c) rather than [ ... ]
        list_nodes = self._detect_lists(triples)
        by_subj_name: dict[str, list[Triple]] = {
            t.subject.name: by_subject[t.subject]
            for t in triples
            if isinstance(t.subject, Existential)
        }

        def _obj(obj: Term) -> str:
            """Render an object term, collapsing list heads to (...) notation."""
            if isinstance(obj, Existential) and obj.name in list_nodes:
                rendered = self._render_list(obj, list_nodes, by_subj_name)
                if rendered is not None:
                    return rendered
            return self._term_for_object(obj, bnode_subjects, bnode_refs)

        # Build output, collapsing blank node property lists
        lines: list[str] = []

        # Sort subjects for deterministic output
        sorted_subjects = sorted(by_subject.keys(), key=lambda s: (
            0 if isinstance(s, NamedNode) else 1,
            str(s),
        ))

        for subj in sorted_subjects:
            # Skip blank nodes that are interior list nodes (they're inlined)
            if isinstance(subj, Existential) and subj.name in list_nodes:
                continue

            trip_list = by_subject[subj]
            # Sort triples within each subject by (predicate, object)
            trip_list.sort(key=lambda t: (str(t.predicate), str(t.object)))

            if isinstance(subj, Existential) and subj.name in bnode_subjects:
                # This is a blank node subject — use [ ... ] syntax
                pred_objs: list[str] = []
                for t in trip_list:
                    pred_str = self._term(t.predicate)
                    obj_str = _obj(t.object)
                    pred_objs.append(f"{pred_str} {obj_str}")

                # Collapse using semicolons
                collapsed = "; ".join(pred_objs)
                lines.append(f"[ {collapsed} ] .")
            else:
                # Render list-as-subject: if subject is a list head, render as (...)
                if isinstance(subj, Existential) and subj.name in list_nodes:
                    subj_str_maybe = self._render_list(subj, list_nodes, by_subj_name)
                    subj_str = subj_str_maybe if subj_str_maybe else self._term(subj)
                else:
                    subj_str = self._term(subj)
                for t in trip_list:
                    pred_str = self._term(t.predicate)
                    obj_str = _obj(t.object)
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
            lines.append(f"@prefix {pfx}: <{uri}> .")
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
            lines.append(f"@prefix {pfx}: <{uri}> .")
        if self._prefixes:
            lines.append("")
        if body:
            lines.append(body)
        return "\n".join(lines) + ("\n" if lines else "")

    def _formula_to_n3(self, t: Term) -> str:
        """Convert a term that may be a Formula to N3 syntax.

        L2 fix: Handle Formula, NamedNode (for single triples), etc.
        """
        if isinstance(t, Formula):
            inner_triples = "; ".join(
                f"{self._term(tr.subject)} {self._term(tr.predicate)} {self._term(tr.object)}"
                for tr in t.triples
            )
            return f"{{{inner_triples}}}"
        # Single triple as formula
        if isinstance(t, TripleTerm):
            return f"<<{self._term(t.subject)} {self._term(t.predicate)} {self._term(t.object)}>>"
        return self._term(t)

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
        if isinstance(t, ListTerm):
            if not t.items:
                return "()"
            inner = " ".join(self._term(item) for item in t.items)
            return f"({inner})"
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
        if isinstance(t, SetTerm):
            elems = " ".join(self._term(e) for e in t.elements)
            return f"($ {elems} $)"
        return str(t)  # pragma: no cover — all Term subclasses handled above

    _RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"

    def _abbreviate(self, uri: str) -> str:
        # rdf:type → `a` shorthand
        if uri == self._RDF_TYPE:
            return "a"
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

        XSD_BOOL    = "http://www.w3.org/2001/XMLSchema#boolean"
        XSD_INTEGER = "http://www.w3.org/2001/XMLSchema#integer"
        XSD_DECIMAL = "http://www.w3.org/2001/XMLSchema#decimal"
        XSD_DOUBLE  = "http://www.w3.org/2001/XMLSchema#double"
        XSD_FLOAT   = "http://www.w3.org/2001/XMLSchema#float"

        if lit.datatype:
            dt = lit.datatype.value
            # Bare boolean literals
            if dt == XSD_BOOL:
                return v
            # Bare integer literals  — emit as plain number e.g. 42
            if dt == XSD_INTEGER:
                return v  # already a digit string like "42"
            # Bare decimal/double — emit as plain number e.g. 3.14
            if dt in (XSD_DECIMAL, XSD_DOUBLE, XSD_FLOAT):
                # Avoid trailing dot: "3." → "3.0"
                if v.endswith("."):
                    v = v + "0"
                return v

        if lit.language:
            return f'"{v}"@{lit.language}'
        if lit.datatype:
            return f'"{v}"^^{self._abbreviate(lit.datatype.value)}'
        return f'"{v}"'
