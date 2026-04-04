"""N3 term hierarchy.

All term types are frozen/hashable so they can be used as dict keys
and set members.

Term hierarchy::

    Term (abstract base)
    ├── NamedNode        — <http://example.org/foo>
    ├── Literal          — "value"^^<datatype> or "value"@en
    ├── Variable         — ?name
    ├── Existential      — _:name (blank node / skolem)
    └── Formula          — { ... } (nested conjunction of triples)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


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
        return not any(
            isinstance(t, Variable)
            for t in (self.subject, self.predicate, self.object)
        )


# Backwards-compatible type alias used by the parser and engine.
Binding = dict[str, Term]
