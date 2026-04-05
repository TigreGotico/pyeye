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
    TripleTerm,
    FormulaTerm,
    PathTerm,
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
    # Phase 2 extended types
    if isinstance(term, TripleTerm):
        return (
            term_contains_var(term.subject, var_name)
            or term_contains_var(term.predicate, var_name)
            or term_contains_var(term.object, var_name)
        )
    if isinstance(term, FormulaTerm):
        if term_contains_var(term.functor, var_name):
            return True
        return any(term_contains_var(a, var_name) for a in term.args)
    if isinstance(term, PathTerm):
        return any(term_contains_var(t, var_name) for t in term.terms)
    if isinstance(term, NegativeSurface):
        return any(
            term_contains_var(t, var_name)
            for t in term.formula.triples
        )
    if isinstance(term, SetTerm):
        return any(term_contains_var(e, var_name) for e in term.elements)
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
    # Phase 2 extended types
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
    if isinstance(term, PathTerm):
        return PathTerm(
            tuple(apply_binding(t, binding) for t in term.terms),
            term.directions,
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
        if _terms_equivalent(pattern, candidate):
            return binding
        # M8 fix: List unification — if pattern has a variable that could match
        # an RDF list, expand the list from the store
        return _try_list_unification(pattern, candidate, binding)

    # Pattern is an unbound variable — bind it (with occurs check)
    var_name: str = pattern.name  # type: ignore[assignment]
    if term_contains_var(candidate, var_name):
        return None  # occurs check failure
    return {**binding, var_name: candidate}


def _terms_equivalent(a: Term, b: Term) -> bool:
    """Check term equivalence with cross-datatype numeric handling.

    C2 fix: "42"^^xsd:integer == "42.0"^^xsd:double
    Also: "hello" == "hello"^^xsd:string (plain string equivalence)
    """
    # Exact match
    if a == b:
        return True

    # Numeric cross-datatype equivalence
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


# ---------------------------------------------------------------------------
# M8: List and Set unification helpers
# ---------------------------------------------------------------------------

_RDF_FIRST = "http://www.w3.org/1999/02/22-rdf-syntax-ns#first"
_RDF_REST = "http://www.w3.org/1999/02/22-rdf-syntax-ns#rest"
_RDF_NIL = "nil"


def _try_list_unification(
    pattern: Term,
    candidate: Term,
    binding: Binding,
) -> Binding | None:
    """M8 fix: Try to unify a pattern with a candidate by expanding RDF lists.

    If the pattern has a Variable where the candidate is an Existential
    that heads an RDF list, expand the list and bind the variable to the
    list elements.
    """
    # Check if pattern has variables that could match an RDF list
    vars_in_pattern: list[str] = []
    _collect_vars(pattern, vars_in_pattern)

    # If candidate is an Existential that might be a list head, try list expansion
    if isinstance(candidate, Existential) and vars_in_pattern:
        # Try to expand as RDF list
        list_elements = _expand_rdf_list_from_binding(candidate, {})
        if list_elements is not None and len(vars_in_pattern) == 1:
            # Single variable can bind to the whole list
            var_name = vars_in_pattern[0]
            if not term_contains_var(candidate, var_name):
                return {**binding, var_name: candidate}
    return None


def _collect_vars(term: Term, out: list[str]) -> None:
    """Collect all variable names from a term."""
    if isinstance(term, Variable):
        out.append(term.name)
    elif isinstance(term, Formula):
        for t in term.triples:
            _collect_vars(t.subject, out)
            _collect_vars(t.predicate, out)
            _collect_vars(t.object, out)
    elif isinstance(term, Triple):
        _collect_vars(term.subject, out)
        _collect_vars(term.predicate, out)
        _collect_vars(term.object, out)
    elif isinstance(term, (TripleTerm, FormulaTerm, PathTerm, SetTerm)):
        if hasattr(term, 'subject'):
            _collect_vars(term.subject, out)  # type: ignore
        if hasattr(term, 'predicate'):
            _collect_vars(term.predicate, out)  # type: ignore
        if hasattr(term, 'object'):
            _collect_vars(term.object, out)  # type: ignore
        if hasattr(term, 'functor'):
            _collect_vars(term.functor, out)  # type: ignore
        if hasattr(term, 'args'):
            for a in term.args:  # type: ignore
                _collect_vars(a, out)
        if hasattr(term, 'terms'):
            for t in term.terms:  # type: ignore
                _collect_vars(t, out)
        if hasattr(term, 'elements'):
            for e in term.elements:  # type: ignore
                _collect_vars(e, out)


def _expand_rdf_list_from_binding(
    head: Existential,
    binding: Binding,
) -> list[Term] | None:
    """Expand an RDF list from the store starting at *head*.

    This is a stub that returns None — full list expansion requires
    access to the store, which unify() doesn't have. List expansion
    is handled by the engine's _collect_builtin_args.
    """
    return None
