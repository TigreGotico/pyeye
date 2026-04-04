"""Curated builtin registry for Phase 1.

Each builtin is a callable that receives a list of bound argument terms
and the engine instance, and either:
- Returns a ``Term`` (function-style: the result is used in comparisons)
- Returns a ``list[Triple]`` (predicate-style: results are asserted)
- Returns ``None`` (skip — arguments not yet ground)

Public API
----------
``BUILTIN_REGISTRY: dict[str, Builtin]``
    Mapping from full IRI to builtin implementation.
"""

from __future__ import annotations

import hashlib as _hashlib
import re as _re
import math as _math
import time as _time
from typing import Protocol

from pyeye.term import NamedNode, Literal, Variable, Existential, Triple, Term, Formula
from pyeye.store import TripleStore


class EngineProto(Protocol):
    """Minimal engine interface builtins need."""
    store: TripleStore
    _skolem_counter: int


class Builtin(Protocol):
    def __call__(self, args: list[Term], engine: EngineProto) -> Term | list[Triple] | None:
        ...


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _unground(args: list[Term]) -> bool:
    """Return True if any arg is a Variable (not yet ground)."""
    return any(isinstance(a, Variable) for a in args)


def _str_val(t: Term) -> str:
    """Extract string value from a Literal or NamedNode."""
    if isinstance(t, Literal):
        return t.value
    if isinstance(t, NamedNode):
        return t.value
    return str(t)


def _num_val(t: Term) -> float:
    """Extract numeric value from a Literal."""
    if isinstance(t, Literal):
        return float(t.value)
    if isinstance(t, (NamedNode, Existential)):
        return float(t.value)
    return float(str(t))


def _bool_result(v: bool) -> Literal:
    """Return XSD boolean literal."""
    return Literal("true" if v else "false",
                   datatype=NamedNode("http://www.w3.org/2001/XMLSchema#boolean"))


def _num_result(v: float) -> Literal:
    """Return XSD double literal."""
    s = str(v)
    if "." not in s and "e" not in s:
        s = s + ".0"
    return Literal(s, datatype=NamedNode("http://www.w3.org/2001/XMLSchema#double"))


def _int_result(v: int) -> Literal:
    return Literal(str(v), datatype=NamedNode("http://www.w3.org/2001/XMLSchema#integer"))


# ---------------------------------------------------------------------------
# Math builtins
# ---------------------------------------------------------------------------

def math_equalTo(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args):
        return None
    return _bool_result(_num_val(args[0]) == _num_val(args[1]))


def math_lessThan(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args):
        return None
    return _bool_result(_num_val(args[0]) < _num_val(args[1]))


def math_greaterThan(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args):
        return None
    return _bool_result(_num_val(args[0]) > _num_val(args[1]))


def math_notEqualTo(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args):
        return None
    return _bool_result(_num_val(args[0]) != _num_val(args[1]))


def math_plus(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args):
        return None
    return _num_result(_num_val(args[0]) + _num_val(args[1]))


def math_minus(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args):
        return None
    return _num_result(_num_val(args[0]) - _num_val(args[1]))


def math_times(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args):
        return None
    return _num_result(_num_val(args[0]) * _num_val(args[1]))


def math_divide(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args):
        return None
    denom = _num_val(args[1])
    if denom == 0:
        return None
    return _num_result(_num_val(args[0]) / denom)


# ---------------------------------------------------------------------------
# String builtins
# ---------------------------------------------------------------------------

def string_concatenation(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args):
        return None
    return Literal("".join(_str_val(a) for a in args))


def string_contains(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args):
        return None
    return _bool_result(_str_val(args[1]) in _str_val(args[0]))


def string_length(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args):
        return None
    return _int_result(len(_str_val(args[0])))


def string_startsWith(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args):
        return None
    return _bool_result(_str_val(args[0]).startswith(_str_val(args[1])))


def string_endsWith(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args):
        return None
    return _bool_result(_str_val(args[0]).endswith(_str_val(args[1])))


def string_equal(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args):
        return None
    return _bool_result(_str_val(args[0]) == _str_val(args[1]))


# ---------------------------------------------------------------------------
# Time builtins
# ---------------------------------------------------------------------------

def time_now(args: list[Term], engine: EngineProto) -> Term | None:
    return Literal(_time.strftime("%Y-%m-%dT%H:%M:%S"))


def time_year(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args):
        return None
    dt = _str_val(args[0])
    try:
        return _int_result(int(dt[:4]))
    except (ValueError, IndexError):
        return None


def time_month(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args):
        return None
    dt = _str_val(args[0])
    try:
        return _int_result(int(dt[5:7]))
    except (ValueError, IndexError):
        return None


def time_day(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args):
        return None
    dt = _str_val(args[0])
    try:
        return _int_result(int(dt[8:10]))
    except (ValueError, IndexError):
        return None


def time_in_seconds(args: list[Term], engine: EngineProto) -> Term | None:
    return _num_result(_time.time())


# ---------------------------------------------------------------------------
# List builtins
# ---------------------------------------------------------------------------

def list_in(args: list[Term], engine: EngineProto) -> Term | None:
    """list:in(item, list-head) — checks if item is in the RDF list."""
    if _unground(args):
        return None
    item = args[0]
    head = args[1]
    if not isinstance(head, Existential):
        return _bool_result(False)

    rdf_first = NamedNode("http://www.w3.org/1999/02/22-rdf-syntax-ns#first")
    rdf_rest = NamedNode("http://www.w3.org/1999/02/22-rdf-syntax-ns#rest")
    nil = Existential("nil")

    cur = head
    visited: set[str] = set()
    while cur.name not in visited and cur.name != "nil":
        visited.add(cur.name)
        # Find first
        matches = list(engine.store.match(subject=cur, predicate=rdf_first))
        if matches:
            if matches[0].object == item:
                return _bool_result(True)
            cur = matches[0].object
        # Find rest
        rest_matches = list(engine.store.match(subject=cur, predicate=rdf_rest))
        if rest_matches:
            nxt = rest_matches[0].object
            if nxt == nil:
                break
            if isinstance(nxt, Existential):
                cur = nxt
            else:
                break
        else:
            break
    return _bool_result(False)


def list_length(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args):
        return None
    head = args[0]
    if not isinstance(head, Existential):
        return _int_result(0)

    rdf_rest = NamedNode("http://www.w3.org/1999/02/22-rdf-syntax-ns#rest")
    nil = Existential("nil")
    cur = head
    count = 0
    visited: set[str] = set()
    while cur.name not in visited and cur.name != "nil":
        visited.add(cur.name)
        count += 1
        matches = list(engine.store.match(subject=cur, predicate=rdf_rest))
        if matches:
            nxt = matches[0].object
            if nxt == nil:
                break
            if isinstance(nxt, Existential):
                cur = nxt
            else:
                break
        else:
            break
    return _int_result(count)


# ---------------------------------------------------------------------------
# Log builtins
# ---------------------------------------------------------------------------

def log_outputString(args: list[Term], engine: EngineProto) -> Term | None:
    """Mark a string for output. Returns the literal as-is."""
    if _unground(args):
        return None
    return args[0]


def log_skolem(args: list[Term], engine: EngineProto) -> Term:
    """Generate a fresh existential (skolem constant)."""
    engine._skolem_counter += 1
    return Existential(f"sk-{engine._skolem_counter}")


def log_content(args: list[Term], engine: EngineProto) -> list[Triple]:
    """Return all triples in the store (used for output)."""
    return list(engine.store)


def log_equalTo(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args):
        return None
    return _bool_result(args[0] == args[1])


# ---------------------------------------------------------------------------
# Type builtins
# ---------------------------------------------------------------------------

def type_isLiteral(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args):
        return None
    return _bool_result(isinstance(args[0], Literal))


def type_isNumeric(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args):
        return None
    if isinstance(args[0], Literal):
        try:
            float(args[0].value)
            return _bool_result(True)
        except (ValueError, TypeError):
            return _bool_result(False)
    return _bool_result(False)


def type_str(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args):
        return None
    return Literal(_str_val(args[0]))


def type_iri(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args):
        return None
    val = _str_val(args[0])
    return NamedNode(val)


# ---------------------------------------------------------------------------
# Crypto builtins
# ---------------------------------------------------------------------------

def crypto_md5(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args):
        return None
    return Literal(_hashlib.md5(_str_val(args[0]).encode()).hexdigest())


def crypto_sha(args: list[Term], engine: EngineProto) -> Term | None:
    """SHA-1 (deprecated but kept for EYE compatibility)."""
    if _unground(args):
        return None
    return Literal(_hashlib.sha1(_str_val(args[0]).encode()).hexdigest())


def crypto_sha256(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args):
        return None
    return Literal(_hashlib.sha256(_str_val(args[0]).encode()).hexdigest())


def crypto_sha512(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args):
        return None
    return Literal(_hashlib.sha512(_str_val(args[0]).encode()).hexdigest())


# ---------------------------------------------------------------------------
# Extended String builtins (regex)
# ---------------------------------------------------------------------------

def string_matches(args: list[Term], engine: EngineProto) -> Term | None:
    """Regex match: string:matches(haystack, pattern) → boolean."""
    if _unground(args):
        return None
    try:
        return _bool_result(bool(_re.search(_str_val(args[1]), _str_val(args[0]))))
    except _re.error:
        return _bool_result(False)


def string_replace(args: list[Term], engine: EngineProto) -> Term | None:
    """Regex replace: string:replace(haystack, pattern, replacement) → string."""
    if _unground(args):
        return None
    try:
        return Literal(_re.sub(_str_val(args[1]), _str_val(args[2]), _str_val(args[0])))
    except _re.error:
        return Literal(_str_val(args[0]))


def string_substring(args: list[Term], engine: EngineProto) -> Term | None:
    """Substring: string:substring(str, start, length) → string."""
    if _unground(args):
        return None
    s = _str_val(args[0])
    start = int(_num_val(args[1]))
    length = int(_num_val(args[2])) if len(args) > 2 else len(s)
    return Literal(s[start:start + length])


# ---------------------------------------------------------------------------
# Extended Math builtins
# ---------------------------------------------------------------------------

def math_floor(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args):
        return None
    return _int_result(int(_math.floor(_num_val(args[0]))))


def math_ceiling(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args):
        return None
    return _int_result(int(_math.ceil(_num_val(args[0]))))


def math_exponentiation(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args):
        return None
    return _num_result(_math.pow(_num_val(args[0]), _num_val(args[1])))


def math_logarithm(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args):
        return None
    val = _num_val(args[0])
    if val <= 0:
        return None
    return _num_result(_math.log(val))


def math_sin(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args):
        return None
    return _num_result(_math.sin(_num_val(args[0])))


def math_cos(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args):
        return None
    return _num_result(_math.cos(_num_val(args[0])))


def math_tan(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args):
        return None
    return _num_result(_math.tan(_num_val(args[0])))


# ---------------------------------------------------------------------------
# Extended Log builtins
# ---------------------------------------------------------------------------

import uuid as _uuid

def log_uuid(args: list[Term], engine: EngineProto) -> Term | None:
    """Generate a UUID."""
    return Literal(str(_uuid.uuid4()))


def log_n3String(args: list[Term], engine: EngineProto) -> Term | None:
    """Convert a term to its N3 string representation."""
    if _unground(args):
        return None
    return Literal(str(args[0]))


def log_implies(args: list[Term], engine: EngineProto) -> Term | None:
    """Check if premise implies conclusion (both are ground terms)."""
    if _unground(args):
        return None
    # Simple equality check for Phase 2
    return _bool_result(args[0] == args[1])


def log_forAllIn(args: list[Term], engine: EngineProto) -> list[Triple] | None:
    """Collect all bindings for a variable across matching triples.

    forAllIn(variable, pattern) → list of bindings.
    Simplified: returns all store triples that match the pattern.
    """
    # This is a simplified version that returns the store contents
    # Full implementation would need access to the rule's formula context
    return list(engine.store)


# ---------------------------------------------------------------------------
# E: builtins (log-rules namespace)
# ---------------------------------------------------------------------------

def e_calculate(args: list[Term], engine: EngineProto) -> Term | None:
    """Evaluate a Python expression: e:calculate("2 + 3") → "5"."""
    if _unground(args):
        return None
    try:
        result = eval(_str_val(args[0]), {"__builtins__": {}}, {})
        return Literal(str(result))
    except Exception:
        return None


def e_findall(args: list[Term], engine: EngineProto) -> list[Triple] | None:
    """Collect all store triples matching a pattern.

    Simplified: returns all triples in the store.
    """
    return list(engine.store)


def e_closure(args: list[Term], engine: EngineProto) -> Term | None:
    """Check if a formula is deductively closed (all its consequences exist).

    Simplified: always returns true for Phase 2.
    """
    return _bool_result(True)


def e_becomes(args: list[Term], engine: EngineProto) -> list[Triple] | None:
    """Retract-then-assert: retract all triples matching pattern, assert new ones.

    e:becomes(old_triple, new_triple) — removes old, adds new.
    Simplified: just asserts the new triple (retraction is complex in forward chain).
    """
    if _unground(args):
        return None
    if len(args) >= 2:
        # Retract old triple
        old_triple = args[0]
        if isinstance(old_triple, Triple):
            # Can't easily retract from indexed store in Phase 2
            # Just assert the new one
            pass
        # Assert new triple
        new_triple = args[1]
        if isinstance(new_triple, Triple):
            engine.store.add(new_triple)
            return [new_triple]
    return None


def e_transaction(args: list[Term], engine: EngineProto) -> list[Triple] | None:
    """Atomic retract-then-assert: all or nothing.

    Simplified: same as e:becomes for Phase 2 (no rollback).
    """
    if _unground(args):
        return None
    results: list[Triple] = []
    for arg in args:
        if isinstance(arg, Triple):
            if engine.store.add(arg):
                results.append(arg)
    return results if results else None


# ---------------------------------------------------------------------------
# Extended Time builtins
# ---------------------------------------------------------------------------

def time_hours(args: list[Term], engine: EngineProto) -> Term | None:
    """Extract hours from a datetime string."""
    if _unground(args):
        return None
    dt = _str_val(args[0])
    try:
        return _int_result(int(dt[11:13]))
    except (ValueError, IndexError):
        return None


def time_minutes(args: list[Term], engine: EngineProto) -> Term | None:
    """Extract minutes from a datetime string."""
    if _unground(args):
        return None
    dt = _str_val(args[0])
    try:
        return _int_result(int(dt[14:16]))
    except (ValueError, IndexError):
        return None


def time_seconds(args: list[Term], engine: EngineProto) -> Term | None:
    """Extract seconds from a datetime string."""
    if _unground(args):
        return None
    dt = _str_val(args[0])
    try:
        return _int_result(int(dt[17:19]))
    except (ValueError, IndexError):
        return None


def time_localTime(args: list[Term], engine: EngineProto) -> Term | None:
    """Get current local time as ISO string."""
    import datetime as _dt
    return Literal(_dt.datetime.now().astimezone().isoformat())


# ---------------------------------------------------------------------------
# Graph builtins
# ---------------------------------------------------------------------------

def graph_member(args: list[Term], engine: EngineProto) -> Term | None:
    """Check if a triple is a member of a graph."""
    if _unground(args):
        return None
    # Simplified: check if triple exists in store
    # Full implementation would check graph membership
    from pyeye.term import Triple as T_cls
    for t in engine.store:
        if (t.subject == args[0] and t.predicate == args[1] and
            (len(args) < 3 or t.object == args[2])):
            return _bool_result(True)
    return _bool_result(False)


def graph_length(args: list[Term], engine: EngineProto) -> Term | None:
    """Return the number of triples in the store (or graph)."""
    return _int_result(len(engine.store))


def graph_difference(args: list[Term], engine: EngineProto) -> list[Triple] | None:
    """Return triples in first graph but not in second.

    Simplified: returns all triples (single graph in Phase 2).
    """
    return list(engine.store)


def graph_intersection(args: list[Term], engine: EngineProto) -> list[Triple] | None:
    """Return triples common to both graphs.

    Simplified: returns all triples (single graph in Phase 2).
    """
    return list(engine.store)


def graph_union(args: list[Term], engine: EngineProto) -> list[Triple] | None:
    """Return all triples from both graphs.

    Simplified: returns all triples (single graph in Phase 2).
    """
    return list(engine.store)


def graph_statement(args: list[Term], engine: EngineProto) -> list[Triple] | None:
    """Construct a triple from components.

    graph_statement(s, p, o) → [Triple(s, p, o)].
    """
    if _unground(args):
        return None
    return [Triple(args[0], args[1], args[2])]


# ---------------------------------------------------------------------------
# List builtins (extended)
# ---------------------------------------------------------------------------

def list_car(args: list[Term], engine: EngineProto) -> Term | None:
    """Return the first element of a list."""
    if _unground(args):
        return None
    head = args[0]
    if not isinstance(head, Existential):
        return None
    rdf_first = NamedNode("http://www.w3.org/1999/02/22-rdf-syntax-ns#first")
    matches = list(engine.store.match(subject=head, predicate=rdf_first))
    if matches:
        return matches[0].object
    return None


def list_cdr(args: list[Term], engine: EngineProto) -> Term | None:
    """Return the rest of a list (after the first element)."""
    if _unground(args):
        return None
    head = args[0]
    if not isinstance(head, Existential):
        return None
    rdf_rest = NamedNode("http://www.w3.org/1999/02/22-rdf-syntax-ns#rest")
    matches = list(engine.store.match(subject=head, predicate=rdf_rest))
    if matches:
        return matches[0].object
    return None


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

NS_GRAPH = "http://www.w3.org/2000/10/swap/graph#"
NS_E = "http://eulersharp.sourceforge.net/2003/03swap/log-rules#"
NS_CRYPTO = "http://www.w3.org/2000/10/swap/crypto#"

NS_MATH = "http://www.w3.org/2000/10/swap/math#"
NS_STRING = "http://www.w3.org/2000/10/swap/string#"
NS_TIME = "http://www.w3.org/2000/10/swap/time#"
NS_LIST = "http://www.w3.org/2000/10/swap/list#"
NS_LOG = "http://www.w3.org/2000/10/swap/log#"
NS_TYPE = "http://www.w3.org/2000/10/swap/type#"

BUILTIN_REGISTRY: dict[str, Builtin] = {
    # Math
    NS_MATH + "equalTo": math_equalTo,
    NS_MATH + "lessThan": math_lessThan,
    NS_MATH + "greaterThan": math_greaterThan,
    NS_MATH + "notEqualTo": math_notEqualTo,
    NS_MATH + "plus": math_plus,
    NS_MATH + "minus": math_minus,
    NS_MATH + "times": math_times,
    NS_MATH + "divide": math_divide,
    NS_MATH + "floor": math_floor,
    NS_MATH + "ceiling": math_ceiling,
    NS_MATH + "exponentiation": math_exponentiation,
    NS_MATH + "logarithm": math_logarithm,
    NS_MATH + "sin": math_sin,
    NS_MATH + "cos": math_cos,
    NS_MATH + "tan": math_tan,
    # String
    NS_STRING + "concatenation": string_concatenation,
    NS_STRING + "contains": string_contains,
    NS_STRING + "length": string_length,
    NS_STRING + "startsWith": string_startsWith,
    NS_STRING + "endsWith": string_endsWith,
    NS_STRING + "equal": string_equal,
    NS_STRING + "matches": string_matches,
    NS_STRING + "replace": string_replace,
    NS_STRING + "substring": string_substring,
    # Time
    NS_TIME + "now": time_now,
    NS_TIME + "year": time_year,
    NS_TIME + "month": time_month,
    NS_TIME + "day": time_day,
    NS_TIME + "in-seconds": time_in_seconds,
    NS_TIME + "hours": time_hours,
    NS_TIME + "minutes": time_minutes,
    NS_TIME + "seconds": time_seconds,
    NS_TIME + "localTime": time_localTime,
    # List
    NS_LIST + "in": list_in,
    NS_LIST + "length": list_length,
    NS_LIST + "car": list_car,
    NS_LIST + "cdr": list_cdr,
    # Log
    NS_LOG + "outputString": log_outputString,
    NS_LOG + "skolem": log_skolem,
    NS_LOG + "content": log_content,
    NS_LOG + "equalTo": log_equalTo,
    NS_LOG + "uuid": log_uuid,
    NS_LOG + "n3String": log_n3String,
    NS_LOG + "implies": log_implies,
    NS_LOG + "forAllIn": log_forAllIn,
    # Type
    NS_TYPE + "isLiteral": type_isLiteral,
    NS_TYPE + "isNumeric": type_isNumeric,
    NS_TYPE + "str": type_str,
    NS_TYPE + "iri": type_iri,
    # Crypto
    NS_CRYPTO + "md5": crypto_md5,
    NS_CRYPTO + "sha": crypto_sha,
    NS_CRYPTO + "sha256": crypto_sha256,
    NS_CRYPTO + "sha512": crypto_sha512,
    # Graph
    NS_GRAPH + "member": graph_member,
    NS_GRAPH + "length": graph_length,
    NS_GRAPH + "difference": graph_difference,
    NS_GRAPH + "intersection": graph_intersection,
    NS_GRAPH + "union": graph_union,
    NS_GRAPH + "statement": graph_statement,
    # E: (log-rules)
    NS_E + "calculate": e_calculate,
    NS_E + "findall": e_findall,
    NS_E + "closure": e_closure,
    NS_E + "becomes": e_becomes,
    NS_E + "transaction": e_transaction,
}
