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
    """An in-memory triple/quad store with multi-key indexing.

    Triples are indexed by predicate, subject, and object for fast
    lookups under various query patterns. Quads are stored and indexed
    by graph ID separately.
    """

    __slots__ = ("_triples", "_by_pred", "_by_subj", "_by_obj", "_quads", "_quads_by_graph")

    def __init__(self) -> None:
        # Default graph (triples) — dict[Triple, None] preserves insertion order
        self._triples: dict[Triple, None] = {}
        self._by_pred: dict[Term, dict[Triple, None]] = {}
        # M9 fix: Subject and object indexes for fast lookup
        self._by_subj: dict[Term, dict[Triple, None]] = {}
        self._by_obj: dict[Term, dict[Triple, None]] = {}
        # Named graphs (quads)
        self._quads: dict[Quad, None] = {}
        self._quads_by_graph: dict[Term, dict[Quad, None]] = {}

    # -- mutators ----------------------------------------------------------------

    def add(self, triple: Triple) -> bool:
        """Add *triple* to the default graph.

        Returns ``True`` if the triple was genuinely new (not already
        present), ``False`` if it was a duplicate.
        """
        if triple in self._triples:
            return False
        self._triples[triple] = None
        # M9: Index by predicate, subject, and object
        self._by_pred.setdefault(triple.predicate, {})[triple] = None
        self._by_subj.setdefault(triple.subject, {})[triple] = None
        self._by_obj.setdefault(triple.object, {})[triple] = None
        return True

    def add_quad(self, quad: Quad) -> bool:
        """Add *quad* to a named graph.

        Returns ``True`` if the quad was genuinely new.
        """
        if quad in self._quads:
            return False
        self._quads[quad] = None
        graph = quad.graph
        if graph is not None:
            self._quads_by_graph.setdefault(graph, {})[quad] = None
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
        del self._triples[triple]
        # M9: Clean up all indexes
        pred = triple.predicate
        if pred in self._by_pred:
            self._by_pred[pred].pop(triple, None)
            if not self._by_pred[pred]:
                del self._by_pred[pred]
        subj = triple.subject
        if subj in self._by_subj:
            self._by_subj[subj].pop(triple, None)
            if not self._by_subj[subj]:
                del self._by_subj[subj]
        obj = triple.object
        if obj in self._by_obj:
            self._by_obj[obj].pop(triple, None)
            if not self._by_obj[obj]:
                del self._by_obj[obj]
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

        ``None`` means "match any".  Uses the most selective available
        index: subject, predicate, or object. Falls back to full scan
        only when all three are unbound.

        When *graph* is provided, only quads from that named graph are
        returned. When *graph* is ``None`` (default), the default graph
        (triples) is searched.
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
            # M9: Choose the most selective index
            candidates: dict[Triple, None] | None = None

            if subject is not None and subject in self._by_subj:
                candidates = self._by_subj[subject]
            if predicate is not None and predicate in self._by_pred:
                pred_set = self._by_pred[predicate]
                if candidates is None or len(pred_set) < len(candidates):
                    candidates = pred_set
            if object is not None and object in self._by_obj:
                obj_set = self._by_obj[object]
                if candidates is None or len(obj_set) < len(candidates):
                    candidates = obj_set

            if candidates is None:
                candidates = self._triples

            for t in candidates:
                if subject is not None and t.subject != subject:
                    continue
                if predicate is not None and t.predicate != predicate:
                    continue
                if object is not None and t.object != object:
                    continue
                yield t

    # -- introspection -----------------------------------------------------------

    def __len__(self) -> int:
        return len(self._triples) + len(self._quads)

    def __iter__(self) -> Iterator[Triple]:
        yield from self._triples.keys()
        for q in self._quads.keys():
            yield Triple(q.subject, q.predicate, q.object)

    def triples(self) -> frozenset[Triple]:
        """Return a snapshot of all triples (default graph only)."""
        return frozenset(self._triples.keys())

    def quads(self) -> frozenset[Quad]:
        """Return a snapshot of all quads (named graphs only)."""
        return frozenset(self._quads)
