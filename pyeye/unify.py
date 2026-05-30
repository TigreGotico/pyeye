"""Structural unification for N3 terms.

Given a *pattern* triple (which may contain ``Variable`` slots) and a
*candidate* triple (typically ground, from the store), compute a
``Binding`` — a mapping from ``Variable.id`` to terms — that makes the
pattern match the candidate.

The unifier supports **occurs check**: a variable cannot bind to a term
that recursively contains the same variable (prevents infinite loops in
rule bodies that self-reference).

Binding keys are ``Variable.id`` (int), NOT ``Variable.name`` (str).
This matches the fresh-ID scoping model in ``term.py``.

Public API
----------
``unify(pattern, candidate, binding) -> Binding | None``
``unify_terms(t1, t2, binding) -> Binding | None``
``term_contains_var(term, var_id) -> bool``
``apply_binding(term, binding) -> Term``
``apply_binding_to_triple(triple, binding) -> Triple``
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
    ListTerm,
    TripleTerm,
    FormulaTerm,
    NegativeSurface,
    SetTerm,
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

    result = unify_terms(pattern.predicate, candidate.predicate, binding)
    if result is None:
        return None
    result = unify_terms(pattern.subject, candidate.subject, result)
    if result is None:
        return None
    result = unify_terms(pattern.object, candidate.object, result)
    if result is None:
        return None
    return result


def unify_terms(
    pattern: Term,
    candidate: Term,
    binding: Binding,
) -> Binding | None:
    """Unify two terms, extending *binding*. Returns None on failure.

    Handles Variables (bind by id), ListTerms (element-by-element),
    Formulas (structural), and ground terms (equality).
    """
    # Resolve already-bound variables
    if isinstance(pattern, Variable) and pattern.id in binding:
        pattern = binding[pattern.id]
    if isinstance(candidate, Variable) and candidate.id in binding:
        candidate = binding[candidate.id]

    # Both are variables → bind pattern to candidate
    if isinstance(pattern, Variable) and isinstance(candidate, Variable):
        if pattern.id == candidate.id:
            return binding
        return {**binding, pattern.id: candidate}

    # Pattern is a variable → bind it (with occurs check)
    if isinstance(pattern, Variable):
        if term_contains_var(candidate, pattern.id):
            return None
        return {**binding, pattern.id: candidate}

    # Candidate is a variable → bind it (symmetric, for backward chaining)
    if isinstance(candidate, Variable):
        if term_contains_var(pattern, candidate.id):
            return None
        return {**binding, candidate.id: pattern}

    # Both are ListTerms → element-by-element
    if isinstance(pattern, ListTerm) and isinstance(candidate, ListTerm):
        if len(pattern.items) != len(candidate.items):
            return None
        b = binding
        for p_item, c_item in zip(pattern.items, candidate.items):
            b = unify_terms(p_item, c_item, b)
            if b is None:
                return None
        return b

    # ListTerm vs non-ListTerm → fail (except Variable, handled above)
    if isinstance(pattern, ListTerm) or isinstance(candidate, ListTerm):
        return None

    # Both TripleTerms (RDF-star quoted triples) → element-by-element
    if isinstance(pattern, TripleTerm) and isinstance(candidate, TripleTerm):
        b = unify_terms(pattern.predicate, candidate.predicate, binding)
        if b is None:
            return None
        b = unify_terms(pattern.subject, candidate.subject, b)
        if b is None:
            return None
        b = unify_terms(pattern.object, candidate.object, b)
        return b

    # TripleTerm vs non-TripleTerm → fail (except Variable, handled above)
    if isinstance(pattern, TripleTerm) or isinstance(candidate, TripleTerm):
        return None

    # Both ground → check equality (with numeric cross-type handling)
    if _terms_equivalent(pattern, candidate):
        return binding

    return None


def term_contains_var(term: Term, var_id: int) -> bool:
    """Return True if *term* recursively contains ``Variable`` with *var_id*."""
    if isinstance(term, Variable):
        return term.id == var_id
    if isinstance(term, (NamedNode, Literal, Existential)):
        return False
    if isinstance(term, ListTerm):
        return any(term_contains_var(item, var_id) for item in term.items)
    if isinstance(term, Formula):
        return any(
            term_contains_var(t.subject, var_id)
            or term_contains_var(t.predicate, var_id)
            or term_contains_var(t.object, var_id)
            for t in term.triples
        )
    if isinstance(term, Triple):
        return (
            term_contains_var(term.subject, var_id)
            or term_contains_var(term.predicate, var_id)
            or term_contains_var(term.object, var_id)
        )
    if isinstance(term, TripleTerm):
        return (
            term_contains_var(term.subject, var_id)
            or term_contains_var(term.predicate, var_id)
            or term_contains_var(term.object, var_id)
        )
    if isinstance(term, FormulaTerm):
        if term_contains_var(term.functor, var_id):
            return True
        return any(term_contains_var(a, var_id) for a in term.args)
    if isinstance(term, NegativeSurface):
        return any(
            term_contains_var(t.subject, var_id)
            or term_contains_var(t.predicate, var_id)
            or term_contains_var(t.object, var_id)
            for t in term.formula.triples
        )
    if isinstance(term, SetTerm):
        return any(term_contains_var(e, var_id) for e in term.elements)
    return False


def apply_binding(term: Term, binding: Binding) -> Term:
    """Return *term* with all variables substituted per *binding*.

    Follows Variable→Variable chains until a non-Variable is found.
    """
    if isinstance(term, Variable):
        seen: set[int] = set()
        while isinstance(term, Variable) and term.id in binding:
            if term.id in seen:
                break
            seen.add(term.id)
            term = binding[term.id]
        return term
    if isinstance(term, ListTerm):
        new_items = tuple(apply_binding(item, binding) for item in term.items)
        return ListTerm(items=new_items) if new_items != term.items else term
    if isinstance(term, Formula):
        new_triples = tuple(apply_binding_to_triple(t, binding) for t in term.triples)
        return Formula(triples=new_triples) if new_triples != term.triples else term
    if isinstance(term, TripleTerm):
        return TripleTerm(
            apply_binding(term.subject, binding),
            apply_binding(term.predicate, binding),
            apply_binding(term.object, binding),
        )
    if isinstance(term, FormulaTerm):
        return FormulaTerm(
            apply_binding(term.functor, binding),
            tuple(apply_binding(a, binding) for a in term.args),
        )
    if isinstance(term, NegativeSurface):
        return NegativeSurface(
            Formula(tuple(
                apply_binding_to_triple(t, binding)
                for t in term.formula.triples
            ))
        )
    if isinstance(term, SetTerm):
        return SetTerm(tuple(apply_binding(e, binding) for e in term.elements))
    return term


def apply_binding_to_triple(triple: Triple, binding: Binding) -> Triple:
    """Apply *binding* to all components of *triple*."""
    return Triple(
        apply_binding(triple.subject, binding),
        apply_binding(triple.predicate, binding),
        apply_binding(triple.object, binding),
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _terms_equivalent(a: Term, b: Term) -> bool:
    """Check term equivalence with cross-datatype numeric handling."""
    if a == b:
        return True
    if isinstance(a, Literal) and isinstance(b, Literal):
        return _literals_equivalent(a, b)
    return False


def _literals_equivalent(a: Literal, b: Literal) -> bool:
    """Check if two literals are equivalent, handling numeric and string rules."""
    XSD_INT = "http://www.w3.org/2001/XMLSchema#integer"
    XSD_DEC = "http://www.w3.org/2001/XMLSchema#decimal"
    XSD_DBL = "http://www.w3.org/2001/XMLSchema#double"
    XSD_STR = "http://www.w3.org/2001/XMLSchema#string"
    NUM_TYPES = {XSD_INT, XSD_DEC, XSD_DBL}

    dt_a = a.datatype.value if a.datatype else None
    dt_b = b.datatype.value if b.datatype else None

    # Plain string equivalence: "hello" == "hello"^^xsd:string
    if dt_a is None and dt_b == XSD_STR and a.value == b.value and not a.language and not b.language:
        return True
    if dt_b is None and dt_a == XSD_STR and a.value == b.value and not a.language and not b.language:
        return True

    # Numeric cross-datatype: "42"^^integer == "42.0"^^double
    if dt_a in NUM_TYPES and dt_b in NUM_TYPES:
        try:
            return float(a.value) == float(b.value)
        except (ValueError, TypeError):
            pass

    return False
