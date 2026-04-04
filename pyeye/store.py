"""Triple store with predicate-based indexing and named graph support.

The store keeps triples (and quads for named graphs) in sets with
predicate-based indexes that accelerate pattern matching when the
predicate slot is bound (the most common case in rule bodies).

Public API
----------
``TripleStore``
    .. automethod:: add
    .. automethod:: add_quad
    .. automethod:: contains
    .. automethod:: match
    .. automethod:: __len__
    .. automethod:: __iter__
    .. automethod:: triples
    .. automethod:: quads
"""

from __future__ import annotations

from collections.abc import Iterator

from pyeye.term import Triple, Term, NamedNode, Quad


class TripleStore:
    """An in-memory triple/quad store with predicate-based indexing.

    Triples are stored in the default graph (graph=None). Quads are
    stored in named graphs and indexed separately. The ``match()``
    method can filter by graph when the *graph* parameter is provided.
    """

    __slots__ = ("_triples", "_by_pred", "_quads", "_quads_by_graph")

    def __init__(self) -> None:
        # Default graph (triples)
        self._triples: set[Triple] = set()
        self._by_pred: dict[NamedNode, set[Triple]] = {}
        # Named graphs (quads)
        self._quads: set[Quad] = set()
        self._quads_by_graph: dict[Term, set[Quad]] = {}

    # -- mutators ----------------------------------------------------------------

    def add(self, triple: Triple) -> bool:
        """Add *triple* to the default graph.

        Returns ``True`` if the triple was genuinely new (not already
        present), ``False`` if it was a duplicate.
        """
        if triple in self._triples:
            return False
        self._triples.add(triple)
        pred = triple.predicate
        if isinstance(pred, NamedNode):
            self._by_pred.setdefault(pred, set()).add(triple)
        return True

    def add_quad(self, quad: Quad) -> bool:
        """Add *quad* to a named graph.

        Returns ``True`` if the quad was genuinely new.
        """
        if quad in self._quads:
            return False
        self._quads.add(quad)
        graph = quad.graph
        if graph is not None:
            self._quads_by_graph.setdefault(graph, set()).add(quad)
        return True

    def contains(self, triple: Triple) -> bool:
        """Return ``True`` if *triple* is in the default graph."""
        return triple in self._triples

    def retract(self, triple: Triple) -> bool:
        """Remove *triple* from the default graph.

        Returns ``True`` if the triple was found and removed.
        """
        if triple not in self._triples:
            return False
        self._triples.discard(triple)
        pred = triple.predicate
        if isinstance(pred, NamedNode) and pred in self._by_pred:
            self._by_pred[pred].discard(triple)
            if not self._by_pred[pred]:
                del self._by_pred[pred]
        return True

    def retract_all(self, subject: Term | None = None,
                     predicate: Term | None = None,
                     object: Term | None = None) -> int:
        """Remove all matching triples. Returns count of removed triples."""
        to_remove = list(self.match(subject=subject, predicate=predicate, object=object))
        for t in to_remove:
            self.retract(t)
        return len(to_remove)

    # -- queries -----------------------------------------------------------------

    def match(
        self,
        subject: Term | None = None,
        predicate: Term | None = None,
        object: Term | None = None,   # noqa: A002 — shadowing built-in is intentional
        graph: Term | None = None,
    ) -> Iterator[Triple]:
        """Yield all triples matching the given pattern.

        ``None`` means "match any".  When *predicate* is a concrete
        ``NamedNode`` the predicate index is used for a fast lookup;
        otherwise a full scan is performed.

        When *graph* is provided, only quads from that named graph are
        returned. When *graph* is ``None`` (default), the default graph
        (triples) is searched. To search ALL graphs, pass ``graph=...``
        (any sentinel) — not yet supported; use separate calls.

        Non-``NamedNode`` predicates (e.g. ``Variable``) are treated as
        wildcards — the engine will handle further filtering via
        unification.
        """
        if graph is not None:
            # Named graph search
            candidates = self._quads_by_graph.get(graph, ())
            for q in candidates:
                if subject is not None and q.subject != subject:
                    continue
                if predicate is not None and q.predicate != predicate:
                    continue
                if object is not None and q.object != object:
                    continue
                yield Triple(q.subject, q.predicate, q.object)
        else:
            # Default graph (triples)
            if predicate is not None and isinstance(predicate, NamedNode):
                candidates = self._by_pred.get(predicate, ())
            else:
                candidates = self._triples

            for t in candidates:
                if subject is not None and t.subject != subject:
                    continue
                if object is not None and t.object != object:
                    continue
                yield t

    # -- introspection -----------------------------------------------------------

    def __len__(self) -> int:
        return len(self._triples) + len(self._quads)

    def __iter__(self) -> Iterator[Triple]:
        yield from self._triples
        for q in self._quads:
            yield Triple(q.subject, q.predicate, q.object)

    def triples(self) -> frozenset[Triple]:
        """Return a snapshot of all triples (default graph only)."""
        return frozenset(self._triples)

    def quads(self) -> frozenset[Quad]:
        """Return a snapshot of all quads (named graphs only)."""
        return frozenset(self._quads)
