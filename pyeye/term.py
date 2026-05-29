"""N3 term hierarchy.

All term types are frozen/hashable so they can be used as dict keys
and set members.

Term hierarchy::

    Term (abstract base)
    ├── NamedNode        — <http://example.org/foo>
    ├── Literal          — "value"^^<datatype> or "value"@en
    ├── Variable         — ?name  (carries unique id for scoping)
    ├── Existential      — _:name (blank node / skolem)
    ├── Formula          — { ... } (nested conjunction of triples)
    ├── ListTerm         — (a b c) (native list, not rdf:first/rest)
    ├── TripleTerm       — << S P O >> (reified triple as a term)
    └── FormulaTerm      — (| Functor Args |) (formula as a term)

Variable scoping
----------------
Each Variable carries a unique ``id`` (int) in addition to its ``name``.
Two Variables with the same name but different IDs are distinct — this
mirrors Prolog's ``copy_term_nat/2`` where each rule application gets
genuinely fresh variables.  Bindings are keyed by ``Variable.id``, never
by ``Variable.name``, so nested backward-chaining never has name collisions.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


# ---------------------------------------------------------------------------
# Variable ID allocator (module-level, monotonically increasing)
# ---------------------------------------------------------------------------

_var_id_counter = itertools.count(1)


def _next_var_id() -> int:
    """Return a globally unique variable ID."""
    return next(_var_id_counter)


def reset_var_ids(start: int = 1) -> None:
    """Reset the global variable ID counter (for testing only)."""
    global _var_id_counter
    _var_id_counter = itertools.count(start)


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
    """A logical variable, e.g. ``?X``.

    Each Variable carries a unique ``id`` for scoping.  ``copy_rule``
    creates fresh Variables with new IDs so that recursive backward-chain
    applications never collide.  Bindings are keyed by ``id``, not ``name``.
    """
    name: str
    id: int = -1  # -1 = sentinel; replaced in __post_init__

    def __post_init__(self) -> None:
        if self.id == -1:
            object.__setattr__(self, "id", _next_var_id())

    def __str__(self) -> str:
        return f"?{self.name}"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Variable):
            return NotImplemented
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)


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

    def __post_init__(self) -> None:
        if isinstance(self.triples, list):
            object.__setattr__(self, "triples", tuple(self.triples))

    def __hash__(self) -> int:
        return hash(self.triples)

    def __str__(self) -> str:
        inner = "; ".join(str(t) for t in self.triples)
        return f"{{{inner}}}"


@dataclass(frozen=True)
class ListTerm:
    """A native N3 list ``(a b c)``.

    Stored as a tuple of items — no rdf:first/rdf:rest encoding.
    Unification handles ListTerm element-by-element.  Empty list is
    ``ListTerm(items=())``.
    """
    items: tuple[Term, ...] = ()

    def __post_init__(self) -> None:
        if isinstance(self.items, list):
            object.__setattr__(self, "items", tuple(self.items))

    def __hash__(self) -> int:
        return hash(self.items)

    def __str__(self) -> str:
        inner = " ".join(str(i) for i in self.items)
        return f"({inner})"

    def __len__(self) -> int:
        return len(self.items)

    def __iter__(self):
        return iter(self.items)

    def is_ground(self) -> bool:
        """Return True if no item contains a Variable."""
        for item in self.items:
            if isinstance(item, Variable):
                return False
            if isinstance(item, ListTerm) and not item.is_ground():
                return False
        return True


# ---------------------------------------------------------------------------
# Extended term types (RDF-star, formula terms)
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
        return not any(
            isinstance(t, Variable)
            for t in (self.subject, self.predicate, self.object)
        )


@dataclass(frozen=True)
class FormulaTerm:
    """A formula as a term: ``(| Functor Args |)``."""
    functor: Term
    args: tuple[Term, ...] = ()

    def __hash__(self) -> int:
        return hash((self.functor, self.args))

    def __str__(self) -> str:
        args_str = " ".join(str(a) for a in self.args)
        return f"(|{self.functor} {args_str}|)"

    def is_ground(self) -> bool:
        if isinstance(self.functor, Variable):
            return False
        return not any(isinstance(a, Variable) for a in self.args)


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
            if isinstance(t, (TripleTerm, FormulaTerm)):
                if not t.is_ground():
                    return False
            if isinstance(t, ListTerm) and not t.is_ground():
                return False
        return True


# ---------------------------------------------------------------------------
# Quad (TriG / named graphs)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class NegativeSurface:
    """A BLOGIC negation: ``log:onNegativeSurface { ... }``.

    When a rule body contains a negative surface, the rule fires only if
    the enclosed formula CANNOT be matched against the store.
    """
    formula: Formula

    def __hash__(self) -> int:
        return hash(self.formula)

    def __str__(self) -> str:
        return f"~{self.formula}"

    def is_ground(self) -> bool:
        return all(t.is_ground() for t in self.formula.triples)


@dataclass(frozen=True)
class Quad:
    """A named-graph triple: ``(S P O G)``."""
    subject: Term
    predicate: Term
    object: Term
    graph: Term | None = None

    def __hash__(self) -> int:
        return hash((self.subject, self.predicate, self.object, self.graph))

    def __str__(self) -> str:
        return f"({self.subject} {self.predicate} {self.object} in {self.graph or 'default'})"

    def to_triple(self) -> Triple:
        return Triple(self.subject, self.predicate, self.object)


# ---------------------------------------------------------------------------
# Set (unordered collections)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SetTerm:
    """An unordered set: ``($ a b c $)``."""
    elements: tuple[Term, ...]

    def __hash__(self) -> int:
        return hash(frozenset(hash(e) for e in self.elements))

    def __str__(self) -> str:
        elems = " ".join(str(e) for e in self.elements)
        return f"($ {elems} $)"

    def is_ground(self) -> bool:
        return not any(isinstance(e, Variable) for e in self.elements)


# ---------------------------------------------------------------------------
# Binding type — keyed by Variable.id (int), NOT Variable.name (str)
# ---------------------------------------------------------------------------

Binding = dict[int, Term]
