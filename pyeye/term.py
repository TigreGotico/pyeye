"""N3 term hierarchy.

All term types are frozen/hashable so they can be used as dict keys
and set members.

Term hierarchy::

    Term (abstract base)
    ├── NamedNode        — <http://example.org/foo>
    ├── Literal          — "value"^^<datatype> or "value"@en
    ├── Variable         — ?name
    ├── Existential      — _:name (blank node / skolem)
    ├── Formula          — { ... } (nested conjunction of triples)
    ├── TripleTerm       — << S P O >> (reified triple as a term)
    ├── FormulaTerm      — (| Functor Args |) (formula as a term)
    └── PathTerm         — :a ! :p ! :q  (chained path)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal as TypingLiteral, Protocol, runtime_checkable


# ---------------------------------------------------------------------------
# Term types
# ---------------------------------------------------------------------------

@runtime_checkable
class Term(Protocol):
    """Marker protocol — all N3 terms satisfy this."""
    ...


@dataclass(frozen=True)
class NamedNode:
    """An IRI, e.g. ``<http://example.org/ns#Alice>`` or ``:plays``."""
    value: str

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class Literal:
    """An RDF literal with optional datatype or language tag.

    Examples:
        Literal("42", datatype=NamedNode("http://www.w3.org/2001/XMLSchema#integer"))
        Literal("hello", language="en")
        Literal("plain")
    """
    value: str
    datatype: NamedNode | None = None
    language: str | None = None

    def __post_init__(self) -> None:
        if self.datatype is not None and self.language is not None:
            raise ValueError("Literal cannot have both datatype and language")

    def __str__(self) -> str:
        return f'"{self.value}"'


@dataclass(frozen=True)
class Variable:
    """A logical variable, e.g. ``?X``."""
    name: str

    def __str__(self) -> str:
        return f"?{self.name}"


@dataclass(frozen=True)
class Existential:
    """An existential / blank-node constant, e.g. ``_:genid-1``."""
    name: str

    def __str__(self) -> str:
        return f"_:{self.name}"


@dataclass(frozen=True)
class Formula:
    """A nested formula (conjunction of triples), e.g. ``{ :a :p :b }``."""
    triples: tuple[Triple, ...] = ()

    def __hash__(self) -> int:
        return hash(self.triples)

    def __str__(self) -> str:
        inner = "; ".join(str(t) for t in self.triples)
        return f"{{{inner}}}"


# ---------------------------------------------------------------------------
# Phase 2 extended term types
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TripleTerm:
    """A reified triple that can appear as subject or object: ``<< S P O >>``.

    Example: ``<< :alice :knows :bob >> :wasSaidBy :charlie .``
    """
    subject: Term
    predicate: Term
    object: Term

    def __hash__(self) -> int:
        return hash((self.subject, self.predicate, self.object))

    def __str__(self) -> str:
        return f"<<{self.subject} {self.predicate} {self.object}>>"

    def is_ground(self) -> bool:
        """Return True if no component contains a Variable."""
        return not any(
            isinstance(t, Variable)
            for t in (self.subject, self.predicate, self.object)
        )


@dataclass(frozen=True)
class FormulaTerm:
    """A formula as a term: ``(| Functor Args |)``.

    Example: ``(| :says :alice "hello" |)`` as the object of another triple.
    """
    functor: Term
    args: tuple[Term, ...] = ()

    def __hash__(self) -> int:
        return hash((self.functor, self.args))

    def __str__(self) -> str:
        args_str = " ".join(str(a) for a in self.args)
        return f"(|{self.functor} {args_str}|)"

    def is_ground(self) -> bool:
        """Return True if no component contains a Variable."""
        if isinstance(self.functor, Variable):
            return False
        return not any(isinstance(a, Variable) for a in self.args)


@dataclass(frozen=True)
class PathTerm:
    """A chained path expression: ``:a ! :p ! :q`` or ``:a ^ :p``.

    ``directions`` contains "forward" for ``!`` and "reverse" for ``^``.
    """
    terms: tuple[Term, ...]
    directions: tuple[TypingLiteral["forward", "reverse"], ...] = ()

    def __post_init__(self) -> None:
        # Auto-fill directions: one per term (each term has a direction)
        if len(self.directions) != len(self.terms):
            object.__setattr__(
                self, "directions",
                tuple(["forward"] * len(self.terms))
            )

    def __hash__(self) -> int:
        return hash((self.terms, self.directions))

    def __str__(self) -> str:
        parts = [str(self.terms[0])]
        for i, t in enumerate(self.terms[1:]):
            op = "!" if not self.directions or self.directions[i] == "forward" else "^"
            parts.append(f" {op} {t}")
        return "".join(parts)

    def is_ground(self) -> bool:
        """Return True if no component contains a Variable."""
        return not any(isinstance(t, Variable) for t in self.terms)


# ---------------------------------------------------------------------------
# Triple
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Triple:
    """An RDF triple ``(subject, predicate, object)``."""
    subject: Term
    predicate: Term
    object: Term

    def __str__(self) -> str:
        return f"({self.subject} {self.predicate} {self.object})"

    def is_ground(self) -> bool:
        """Return True if no component contains a Variable."""
        for t in (self.subject, self.predicate, self.object):
            if isinstance(t, Variable):
                return False
            # Phase 2: check nested term types
            if isinstance(t, (TripleTerm, FormulaTerm, PathTerm)):
                if not t.is_ground():
                    return False
        return True


# ---------------------------------------------------------------------------
# Quad (Phase 2: TriG / named graphs)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Quad:
    """A named-graph triple: ``(S P O G)``."""
    subject: Term
    predicate: Term
    object: Term
    graph: Term | None = None  # None = default graph

    def __hash__(self) -> int:
        return hash((self.subject, self.predicate, self.object, self.graph))

    def __str__(self) -> str:
        return f"({self.subject} {self.predicate} {self.object} in {self.graph or 'default'})"

    def to_triple(self) -> Triple:
        """Convert to a Triple (loses graph info)."""
        return Triple(self.subject, self.predicate, self.object)


# Backwards-compatible type alias used by the parser and engine.
Binding = dict[str, Term]
