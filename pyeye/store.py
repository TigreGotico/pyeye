"""Triple store with predicate-based indexing.

The store keeps a flat ``set[Triple]`` for membership tests *and* a
predicate → triples index that accelerates pattern matching when the
predicate slot is bound (the most common case in rule bodies).

Public API
----------
``TripleStore``
    .. automethod:: add
    .. automethod:: contains
    .. automethod:: match
    .. automethod:: __len__
    .. automethod:: __iter__
    .. automethod:: triples
"""

from __future__ import annotations

from collections.abc import Iterator

from pyeye.term import Triple, Term, NamedNode


class TripleStore:
    """An in-memory triple store with a predicate-based index."""

    __slots__ = ("_triples", "_by_pred")

    def __init__(self) -> None:
        self._triples: set[Triple] = set()
        self._by_pred: dict[NamedNode, set[Triple]] = {}

    # -- mutators ----------------------------------------------------------------

    def add(self, triple: Triple) -> bool:
        """Add *triple* to the store.

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

    def contains(self, triple: Triple) -> bool:
        """Return ``True`` if *triple* is already in the store."""
        return triple in self._triples

    # -- queries -----------------------------------------------------------------

    def match(
        self,
        subject: Term | None = None,
        predicate: Term | None = None,
        object: Term | None = None,   # noqa: A002 — shadowing built-in is intentional
    ) -> Iterator[Triple]:
        """Yield all triples matching the given pattern.

        ``None`` means "match any".  When *predicate* is a concrete
        ``NamedNode`` the predicate index is used for a fast lookup;
        otherwise a full scan is performed.

        Non-``NamedNode`` predicates (e.g. ``Variable``) are treated as
        wildcards — the engine will handle further filtering via
        unification.
        """
        if predicate is not None and isinstance(predicate, NamedNode):
            candidates = self._by_pred.get(predicate, ())
        else:
            candidates = self._triples

        for t in candidates:
            if subject is not None and t.subject != subject:
                continue
            # Only filter on predicate if it's a NamedNode (exact match).
            # Variables and other term types are wildcards here.
            if predicate is not None and isinstance(predicate, NamedNode) and t.predicate != predicate:
                continue
            if object is not None and t.object != object:
                continue
            yield t

    # -- introspection -----------------------------------------------------------

    def __len__(self) -> int:
        return len(self._triples)

    def __iter__(self) -> Iterator[Triple]:
        return iter(self._triples)

    def triples(self) -> frozenset[Triple]:
        """Return a snapshot of all triples as a frozenset."""
        return frozenset(self._triples)
