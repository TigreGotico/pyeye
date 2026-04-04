"""Structural unification for N3 terms.

Given a *pattern* triple (which may contain ``Variable`` slots) and a
*candidate* triple (typically ground, from the store), compute a
``Binding`` — a mapping from variable names to terms — that makes the
pattern match the candidate.

The unifier supports **occurs check**: a variable cannot bind to a term
that recursively contains the same variable (prevents infinite loops in
rule bodies that self-reference).

Public API
----------
``unify(pattern, candidate, binding) -> Binding | None``
    Extend *binding* with bindings that make *pattern* match *candidate*.
    Returns ``None`` if unification fails.

``term_contains_var(term, var_name) -> bool``
    Check whether a term (recursively) contains a variable with the given
    name — used for occurs check.

``apply_binding(term, binding) -> Term``
    Substitute all variables in *term* that appear in *binding*.
"""

from __future__ import annotations

from pyeye.term import (
    NamedNode,
    Literal,
    Variable,
    Existential,
    Formula,
    Triple,
    Binding,
    Term,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def unify(
    pattern: Triple,
    candidate: Triple,
    binding: Binding | None = None,
) -> Binding | None:
    """Try to unify *pattern* with *candidate* under existing *binding*.

    Returns an extended binding dict on success, or ``None`` on failure.
    """
    if binding is None:
        binding = {}

    # Unify predicate first (most selective, indexed in store)
    result = _unify_term(pattern.predicate, candidate.predicate, binding)
    if result is None:
        return None

    result = _unify_term(pattern.subject, candidate.subject, result)
    if result is None:
        return None

    result = _unify_term(pattern.object, candidate.object, result)
    if result is None:
        return None

    return result


def term_contains_var(term: Term, var_name: str) -> bool:
    """Return True if *term* recursively contains ``Variable(var_name)``."""
    if isinstance(term, Variable):
        return term.name == var_name
    if isinstance(term, (NamedNode, Literal, Existential)):
        return False
    if isinstance(term, Formula):
        return any(
            term_contains_var(t, var_name)
            for t in term.triples
        )
    if isinstance(term, Triple):
        return (
            term_contains_var(term.subject, var_name)
            or term_contains_var(term.predicate, var_name)
            or term_contains_var(term.object, var_name)
        )
    return False


def apply_binding(term: Term, binding: Binding) -> Term:
    """Return *term* with all variables substituted per *binding*."""
    if isinstance(term, Variable):
        return binding.get(term.name, term)
    if isinstance(term, Formula):
        return Formula(tuple([
            apply_binding_to_triple(t, binding)
            for t in term.triples
        ]))
    # NamedNode, Literal, Existential — ground, no substitution needed
    return term


def apply_binding_to_triple(triple: Triple, binding: Binding) -> Triple:
    """Apply *binding* to all components of *triple*."""
    return Triple(
        apply_binding(triple.subject, binding),
        apply_binding(triple.predicate, binding),
        apply_binding(triple.object, binding),
    )


# ---------------------------------------------------------------------------
# Internal unification engine
# ---------------------------------------------------------------------------

def _unify_term(
    pattern: Term,
    candidate: Term,
    binding: Binding,
) -> Binding | None:
    """Core unification dispatch."""
    # Resolve any already-bound variable in the pattern
    if isinstance(pattern, Variable) and pattern.name in binding:
        pattern = binding[pattern.name]

    # Pattern is a ground term — check equality
    if not isinstance(pattern, Variable):
        if pattern == candidate:
            return binding
        return None

    # Pattern is an unbound variable — bind it (with occurs check)
    var_name: str = pattern.name  # type: ignore[assignment]
    if term_contains_var(candidate, var_name):
        return None  # occurs check failure
    return {**binding, var_name: candidate}
