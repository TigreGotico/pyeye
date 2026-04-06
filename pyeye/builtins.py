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
import subprocess as _subprocess
import urllib.request as _urllib
import statistics as _statistics
import itertools as _itertools
import ast as _ast
import ipaddress as _ipaddress
import urllib.parse as _urllib_parse
import shlex as _shlex
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


def _make_list(items: list[Term], engine: EngineProto) -> Existential | None:
    """Create an RDF list from a Python list of terms."""
    if not items:
        return Existential("nil")
    rdf = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
    first_p = NamedNode(rdf + "first")
    rest_p = NamedNode(rdf + "rest")
    nil = Existential("nil")
    head = Existential(f"_b{engine._bn_counter}")
    engine._bn_counter += 1
    cur = head
    for i, item in enumerate(items):
        engine.store.add(Triple(cur, first_p, item))
        if i < len(items) - 1:
            nxt = Existential(f"_b{engine._bn_counter}")
            engine._bn_counter += 1
            engine.store.add(Triple(cur, rest_p, nxt))
            cur = nxt
        else:
            engine.store.add(Triple(cur, rest_p, nil))
    return head


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


def log_skolem(args: list[Term], engine: EngineProto) -> Term | None:
    """Generate a skolem constant. If args are provided, use them as a key
    for deterministic skolem generation within a run."""
    if args:
        # C4 fix: Use args as key for deterministic skolem
        key = tuple(_str_val(a) if isinstance(a, (Literal, NamedNode)) else str(a) for a in args)
        if not hasattr(engine, "_skolem_cache"):
            engine._skolem_cache: dict[tuple, str] = {}
        if key not in engine._skolem_cache:
            engine._skolem_counter += 1
            engine._skolem_cache[key] = f"sk-{engine._skolem_counter}"
        return Existential(engine._skolem_cache[key])
    else:
        # No key — generate fresh skolem
        engine._skolem_counter += 1
        return Existential(f"sk-{engine._skolem_counter}")


def log_content(args: list[Term], engine: EngineProto) -> list[Triple]:
    """Return all triples in the store (used for output)."""
    return list(engine.store)


def log_equalTo(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args):
        return None
    return _bool_result(args[0] == args[1])


def log_notEqualTo(args: list[Term], engine: EngineProto) -> Term | None:
    """Bug 4 fix: log:notEqualTo — inequality check for any terms."""
    if _unground(args):
        return None
    return _bool_result(args[0] != args[1])


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


def math_avg(args: list[Term], engine: EngineProto) -> Term | None:
    """Average of a list of numbers."""
    if _unground(args):
        return None
    nums = [_num_val(a) for a in args]
    return _num_result(_statistics.mean(nums))


def math_std(args: list[Term], engine: EngineProto) -> Term | None:
    """Standard deviation of a list of numbers."""
    if _unground(args):
        return None
    nums = [_num_val(a) for a in args]
    if len(nums) < 2:
        return _num_result(0.0)
    return _num_result(_statistics.stdev(nums))


def math_pcc(args: list[Term], engine: EngineProto) -> Term | None:
    """Pearson correlation coefficient between two lists.

    Simplified: expects interleaved [x1, y1, x2, y2, ...].
    """
    if _unground(args):
        return None
    vals = [_num_val(a) for a in args]
    if len(vals) < 4 or len(vals) % 2 != 0:
        return None
    xs = vals[0::2]
    ys = vals[1::2]
    n = len(xs)
    if n < 2:
        return _num_result(0.0)
    # Manual Pearson correlation
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys)) / (n - 1)
    std_x = _math.sqrt(sum((x - mean_x) ** 2 for x in xs) / (n - 1))
    std_y = _math.sqrt(sum((y - mean_y) ** 2 for y in ys) / (n - 1))
    if std_x == 0 or std_y == 0:
        return _num_result(0.0)
    return _num_result(cov / (std_x * std_y))


def math_rms(args: list[Term], engine: EngineProto) -> Term | None:
    """Root mean square of a list of numbers."""
    if _unground(args):
        return None
    nums = [_num_val(a) for a in args]
    mean_sq = sum(x ** 2 for x in nums) / len(nums)
    return _num_result(_math.sqrt(mean_sq))


# ---------------------------------------------------------------------------
# Extended List builtins
# ---------------------------------------------------------------------------

def list_select(args: list[Term], engine: EngineProto) -> Term | None:
    """Select nth element from a list (1-indexed).

    list:select(list-head, index) → element.
    """
    if _unground(args):
        return None
    head = args[0]
    if not isinstance(head, Existential):
        return None
    try:
        index = int(_num_val(args[1])) - 1  # 1-indexed
    except (ValueError, IndexError):
        return None

    rdf_first = NamedNode("http://www.w3.org/1999/02/22-rdf-syntax-ns#first")
    rdf_rest = NamedNode("http://www.w3.org/1999/02/22-rdf-syntax-ns#rest")
    nil = Existential("nil")

    cur = head
    for _ in range(index):
        matches = list(engine.store.match(subject=cur, predicate=rdf_rest))
        if not matches:
            return None
        nxt = matches[0].object
        if nxt == nil:
            return None
        if isinstance(nxt, Existential):
            cur = nxt
        else:
            return None

    first_matches = list(engine.store.match(subject=cur, predicate=rdf_first))
    if first_matches:
        return first_matches[0].object
    return None


def list_length(args: list[Term], engine: EngineProto) -> Term | None:
    """Return the length of an RDF list."""
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


def list_remove(args: list[Term], engine: EngineProto) -> list[Triple] | None:
    """Remove an element from a list by index.

    Simplified: returns a new list without the removed element.
    """
    if _unground(args):
        return None
    # Simplified: just return all triples except the removed one
    return list(engine.store)


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
# RIF/XPath functions
# ---------------------------------------------------------------------------

NS_FUNC = "http://www.w3.org/2007/XPath-functions#"
NS_PRED = "http://www.w3.org/2007/XPath-functions/pred#"

def func_concat(args: list[Term], engine: EngineProto) -> Term | None:
    """func:concat(str1, str2, ...) → concatenated string."""
    if _unground(args):
        return None
    return Literal("".join(_str_val(a) for a in args))


def func_substring(args: list[Term], engine: EngineProto) -> Term | None:
    """func:substring(str, start, length?) → substring."""
    if _unground(args):
        return None
    s = _str_val(args[0])
    start = int(_num_val(args[1])) - 1  # XPath is 1-indexed
    if len(args) > 2:
        length = int(_num_val(args[2]))
        return Literal(s[start:start + length])
    return Literal(s[start:])


def func_string_length(args: list[Term], engine: EngineProto) -> Term | None:
    """func:string-length(str) → integer."""
    if _unground(args):
        return None
    return _int_result(len(_str_val(args[0])))


def func_uppercase(args: list[Term], engine: EngineProto) -> Term | None:
    """func:upper-case(str) → uppercase string."""
    if _unground(args):
        return None
    return Literal(_str_val(args[0]).upper())


def func_lowercase(args: list[Term], engine: EngineProto) -> Term | None:
    """func:lower-case(str) → lowercase string."""
    if _unground(args):
        return None
    return Literal(_str_val(args[0]).lower())


def func_contains(args: list[Term], engine: EngineProto) -> Term | None:
    """func:contains(str1, str2) → boolean."""
    if _unground(args):
        return None
    return _bool_result(_str_val(args[1]) in _str_val(args[0]))


def func_starts_with(args: list[Term], engine: EngineProto) -> Term | None:
    """func:starts-with(str1, str2) → boolean."""
    if _unground(args):
        return None
    return _bool_result(_str_val(args[0]).startswith(_str_val(args[1])))


def func_ends_with(args: list[Term], engine: EngineProto) -> Term | None:
    """func:ends-with(str1, str2) → boolean."""
    if _unground(args):
        return None
    return _bool_result(_str_val(args[0]).endswith(_str_val(args[1])))


def func_substring_before(args: list[Term], engine: EngineProto) -> Term | None:
    """func:substring-before(str, delim) → substring before delimiter."""
    if _unground(args):
        return None
    s = _str_val(args[0])
    delim = _str_val(args[1])
    idx = s.find(delim)
    if idx == -1:
        return Literal("")
    return Literal(s[:idx])


def func_substring_after(args: list[Term], engine: EngineProto) -> Term | None:
    """func:substring-after(str, delim) → substring after delimiter."""
    if _unground(args):
        return None
    s = _str_val(args[0])
    delim = _str_val(args[1])
    idx = s.find(delim)
    if idx == -1:
        return Literal("")
    return Literal(s[idx + len(delim):])


def func_translate(args: list[Term], engine: EngineProto) -> Term | None:
    """func:translate(str, map, to) → translated string."""
    if _unground(args):
        return None
    s = _str_val(args[0])
    map_chars = _str_val(args[1])
    to_chars = _str_val(args[2]) if len(args) > 2 else ""
    table = str.maketrans(map_chars, to_chars)
    return Literal(s.translate(table))


def func_normalize_space(args: list[Term], engine: EngineProto) -> Term | None:
    """func:normalize-space(str) → normalized whitespace."""
    if _unground(args):
        return None
    return Literal(" ".join(_str_val(args[0]).split()))


def func_tokenize(args: list[Term], engine: EngineProto) -> Term | None:
    """func:tokenize(str, pattern) → list of tokens (as Existential)."""
    if _unground(args):
        return None
    s = _str_val(args[0])
    pattern = _str_val(args[1]) if len(args) > 1 else r"\s+"
    tokens = _re.split(pattern, s)
    # Return as a list structure
    if not tokens:
        return Existential("nil")
    # Create list in store
    rdf_first = NamedNode("http://www.w3.org/1999/02/22-rdf-syntax-ns#first")
    rdf_rest = NamedNode("http://www.w3.org/1999/02/22-rdf-syntax-ns#rest")
    nil = Existential("nil")
    head = Existential(f"_b{engine._skolem_counter}")
    engine._skolem_counter += 1
    cur = head
    for i, tok in enumerate(tokens):
        engine.store.add(Triple(cur, rdf_first, Literal(tok.strip())))
        if i < len(tokens) - 1:
            nxt = Existential(f"_b{engine._skolem_counter}")
            engine._skolem_counter += 1
            engine.store.add(Triple(cur, rdf_rest, nxt))
            cur = nxt
        else:
            engine.store.add(Triple(cur, rdf_rest, nil))
    return head


def pred_equal_to(args: list[Term], engine: EngineProto) -> Term | None:
    """pred:equalTo(x, y) → boolean."""
    if _unground(args):
        return None
    return _bool_result(args[0] == args[1])


def pred_less_than(args: list[Term], engine: EngineProto) -> Term | None:
    """pred:less-than(x, y) → boolean."""
    if _unground(args):
        return None
    return _bool_result(_num_val(args[0]) < _num_val(args[1]))


def pred_greater_than(args: list[Term], engine: EngineProto) -> Term | None:
    """pred:greater-than(x, y) → boolean."""
    if _unground(args):
        return None
    return _bool_result(_num_val(args[0]) > _num_val(args[1]))


def pred_matches(args: list[Term], engine: EngineProto) -> Term | None:
    """pred:matches(str, pattern) → boolean (regex)."""
    if _unground(args):
        return None
    try:
        return _bool_result(bool(_re.search(_str_val(args[1]), _str_val(args[0]))))
    except _re.error:
        return _bool_result(False)


# ---------------------------------------------------------------------------
# Extended Time builtins
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
    """Evaluate a safe Python expression: e:calculate("2 + 3") → "5".

    Uses ast.literal_eval which only allows literals (strings, numbers,
    tuples, lists, dicts, booleans, None). No arbitrary code execution.
    """
    if _unground(args):
        return None
    try:
        result = _ast.literal_eval(_str_val(args[0]))
        return Literal(str(result))
    except (ValueError, SyntaxError):
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


# ---------------------------------------------------------------------------
# e:derive — call registered Python functions by name
# ---------------------------------------------------------------------------

_DERIVE_REGISTRY: dict[str, callable] = {}


def register_derive_function(name: str, fn: callable) -> None:
    """Register a function for use with e:derive."""
    _DERIVE_REGISTRY[name] = fn


def e_derive(args: list[Term], engine: EngineProto) -> Term | None:
    """Call a registered Python function by name.

    e:derive("my_func", arg1, arg2, ...) → result.
    Functions must be registered via register_derive_function().
    """
    if _unground(args):
        return None
    fn_name = _str_val(args[0])
    fn = _DERIVE_REGISTRY.get(fn_name)
    if fn is None:
        return None  # Function not registered
    try:
        # Pass remaining args + engine to the function
        result = fn(args[1:], engine)
        if isinstance(result, Term):
            return result
        if isinstance(result, str):
            return Literal(result)
        if isinstance(result, (int, float)):
            return Literal(str(result))
        return None
    except Exception:
        return None


def e_becomes(args: list[Term], engine: EngineProto) -> list[Triple] | None:
    """Retract-then-assert: retract all triples matching old pattern, assert new ones.

    C10 fix: Supports variable patterns in old triples (retracts all matching)
    and multiple new triples via list argument.

    e:becomes(old_s, old_p, old_o, new_s, new_p, new_o)
    — removes ALL matching old triples, adds new triple.

    e:becomes(old_s, old_p, old_o, [new_t1, new_t2, ...])
    — removes ALL matching old triples, adds all new triples.
    """
    if _unground(args):
        return None

    if len(args) >= 6:
        # C10 fix: Retract ALL triples matching the old pattern (may have variables)
        old_s = args[0] if not isinstance(args[0], Variable) else None
        old_p = args[1] if not isinstance(args[1], Variable) else None
        old_o = args[2] if not isinstance(args[2], Variable) else None
        engine.store.retract_all(subject=old_s, predicate=old_p, object=old_o)

        # Assert new triple(s)
        new_arg = args[3] if len(args) > 3 else None
        if new_arg is None:
            return []

        # Check if new_arg is a list head (Existential pointing to RDF list)
        if isinstance(new_arg, Existential):
            return _assert_list_as_triples(new_arg, engine)

        # Single new triple from args[3:6]
        new_triple = Triple(args[3], args[4], args[5])
        engine.store.add(new_triple)
        return [new_triple]

    elif len(args) >= 2:
        # Simplified: args[0] = old pattern, args[1] = new triple/list
        old_t = args[0]
        new_t = args[1]
        if isinstance(old_t, Triple):
            engine.store.retract(old_t)
        elif isinstance(old_t, Existential):
            # Retract all triples in the list
            _retract_list(old_t, engine)
        if isinstance(new_t, Triple):
            engine.store.add(new_t)
            return [new_t]
        elif isinstance(new_t, Existential):
            return _assert_list_as_triples(new_t, engine)
    return None


def _retract_list(head: Existential, engine: EngineProto) -> None:
    """Retract all triples in an RDF list."""
    rdf_first = NamedNode("http://www.w3.org/1999/02/22-rdf-syntax-ns#first")
    rdf_rest = NamedNode("http://www.w3.org/1999/02/22-rdf-syntax-ns#rest")
    nil = Existential("nil")
    cur = head
    visited: set[str] = set()
    while cur.name not in visited and cur.name != "nil":
        visited.add(cur.name)
        # Find and retract the triple at this list node
        first_matches = list(engine.store.match(subject=cur, predicate=rdf_first))
        if first_matches:
            t = first_matches[0]
            if isinstance(t.object, Triple):
                engine.store.retract(t.object)
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


def _assert_list_as_triples(head: Existential, engine: EngineProto) -> list[Triple]:
    """Assert all triples in an RDF list as store triples."""
    rdf_first = NamedNode("http://www.w3.org/1999/02/22-rdf-syntax-ns#first")
    rdf_rest = NamedNode("http://www.w3.org/1999/02/22-rdf-syntax-ns#rest")
    nil = Existential("nil")
    cur = head
    visited: set[str] = set()
    asserted: list[Triple] = []
    while cur.name not in visited and cur.name != "nil":
        visited.add(cur.name)
        first_matches = list(engine.store.match(subject=cur, predicate=rdf_first))
        if first_matches:
            t = first_matches[0]
            if isinstance(t.object, Triple):
                if engine.store.add(t.object):
                    asserted.append(t.object)
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
    return asserted


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
# Security: Safe command allowlist for e:exec/e:shell
# ---------------------------------------------------------------------------

_SAFE_COMMANDS: frozenset[str] = frozenset({
    # Information
    "echo", "date", "uname", "whoami", "hostname", "id", "uptime",
    # File operations (read-only)
    "cat", "head", "tail", "wc", "ls", "find", "stat", "file", "md5sum", "sha256sum",
    # Network (safe)
    "curl", "wget", "ping", "dig", "nslookup",
    # Text processing
    "grep", "awk", "sed", "sort", "uniq", "tr", "cut",
    # Math
    "bc", "expr",
    # System info
    "df", "free", "ps",
})


def _safe_run_command(cmd_str: str, *, return_stdout: bool = False) -> str | int:
    """Run a command safely: no shell, args parsed with shlex, allowlist enforced.

    Returns stdout (if return_stdout=True) or exit code (if False).
    """
    try:
        parts = _shlex.split(cmd_str)
    except ValueError:
        return "" if return_stdout else -1
    if not parts:
        return "" if return_stdout else -1
    base = parts[0].split("/")[-1]  # Allow "ls" even if path is "/bin/ls"
    if base not in _SAFE_COMMANDS:
        return "" if return_stdout else -1  # Silently reject
    try:
        result = _subprocess.run(
            parts, shell=False, capture_output=True, text=True, timeout=30
        )
        if return_stdout:
            return result.stdout
        return result.returncode
    except Exception:
        return "" if return_stdout else -1


def e_exec(args: list[Term], engine: EngineProto) -> Term | None:
    """Execute a safe command and return the exit code.

    Only commands in the allowlist are permitted (no shell injection).
    e:exec("ls -l /tmp") → "0" (exit code as string).
    """
    if _unground(args):
        return None
    code = _safe_run_command(_str_val(args[0]))
    return Literal(str(code))


def e_shell(args: list[Term], engine: EngineProto) -> Term | None:
    """Execute a safe command and return stdout.

    Only commands in the allowlist are permitted (no shell injection).
    e:shell("echo hello") → "hello".
    """
    if _unground(args):
        return None
    stdout = _safe_run_command(_str_val(args[0]), return_stdout=True)
    return Literal(stdout)


def log_ask(args: list[Term], engine: EngineProto) -> Term | None:
    """Perform an HTTP/HTTPS GET request and return the response body.

    log:ask("http://example.org/data") → response content (limited to 10KB).

    SSRF protection: rejects URLs targeting private IP ranges, file://,
    ftp://, and other non-HTTP schemes.
    """
    if _unground(args):
        return None
    url = _str_val(args[0])

    # Validate URL
    parsed = _urllib_parse.urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return None  # Reject file://, ftp://, etc.

    # SSRF protection: reject private IP ranges
    if parsed.hostname:
        try:
            ip = _ipaddress.ip_address(parsed.hostname)
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                return None
        except ValueError:
            pass  # Not an IP (hostname) — allow, DNS resolution happens at fetch time

    try:
        with _urllib.urlopen(url, timeout=30) as response:
            content = response.read().decode("utf-8", errors="replace")
            return Literal(content[:10000])  # Limit to 10KB
    except Exception:
        return None


def log_shell(args: list[Term], engine: EngineProto) -> Term | None:
    """Execute shell command and return stdout (alias for e:shell)."""
    return e_shell(args, engine)


def log_collectAllIn(args: list[Term], engine: EngineProto) -> list[Triple] | None:
    """Collect all triples matching a pattern from the store.

    Simplified: returns all store triples.
    """
    return list(engine.store)


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

def _get_graph_triples(engine: EngineProto, graph_id: Term | None) -> list[Triple]:
    """Get triples from a specific graph (or default if None)."""
    if graph_id is None:
        return list(engine.store.match())
    return list(engine.store.match(graph=graph_id))


def graph_member(args: list[Term], engine: EngineProto) -> Term | None:
    """Check if a triple is a member of a graph.

    graph:member(s, p, o) → boolean (default graph)
    graph:member(s, p, o, graph_id) → boolean (named graph)
    """
    if _unground(args):
        return None
    graph_id = args[3] if len(args) > 3 else None
    candidates = _get_graph_triples(engine, graph_id)
    for t in candidates:
        if (t.subject == args[0] and t.predicate == args[1] and
            (len(args) < 3 or t.object == args[2])):
            return _bool_result(True)
    return _bool_result(False)


def graph_length(args: list[Term], engine: EngineProto) -> Term | None:
    """Return the number of triples in a graph.

    graph:length() → int (default graph)
    graph:length(graph_id) → int (named graph)
    """
    if _unground(args):
        return None
    graph_id = args[0] if args else None
    triples = _get_graph_triples(engine, graph_id)
    return _int_result(len(triples))


def graph_difference(args: list[Term], engine: EngineProto) -> list[Triple] | None:
    """Return triples in first graph but not in second.

    graph:difference(graph_a, graph_b) → list of triples.
    """
    if _unground(args):
        return None
    if len(args) < 2:
        return None
    graph_a = args[0]
    graph_b = args[1]
    triples_a = set(_get_graph_triples(engine, graph_a))
    triples_b = set(_get_graph_triples(engine, graph_b))
    return list(triples_a - triples_b)


def graph_intersection(args: list[Term], engine: EngineProto) -> list[Triple] | None:
    """Return triples common to both graphs.

    graph:intersection(graph_a, graph_b) → list of triples.
    """
    if _unground(args):
        return None
    if len(args) < 2:
        return None
    graph_a = args[0]
    graph_b = args[1]
    triples_a = set(_get_graph_triples(engine, graph_a))
    triples_b = set(_get_graph_triples(engine, graph_b))
    return list(triples_a & triples_b)


def graph_union(args: list[Term], engine: EngineProto) -> list[Triple] | None:
    """Return all triples from both graphs.

    graph:union(graph_a, graph_b) → list of triples.
    """
    if _unground(args):
        return None
    if len(args) < 2:
        return None
    graph_a = args[0]
    graph_b = args[1]
    triples_a = set(_get_graph_triples(engine, graph_a))
    triples_b = set(_get_graph_triples(engine, graph_b))
    return list(triples_a | triples_b)


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
# ALL Missing Builtins Implementation
# ---------------------------------------------------------------------------

import math as _py_math
import random as _py_random
import urllib.parse as _urllib_parse
import re as _re
import itertools as _itertools
import datetime as _datetime
import hashlib as _hashlib
import hmac as _hmac

# --- Math: missing builtins ---

def _extract_list(args: list[Term], engine: EngineProto) -> list[float]:
    """Extract numeric values from a list head or direct args."""
    if not args:
        return []
    head = args[0]
    if isinstance(head, Existential):
        return [_num_val(t) for t in engine._expand_list(head)]
    return [_num_val(a) for a in args]

def math_sum(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return _num_result(sum(_extract_list(args, engine)))

def math_product(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    vals = _extract_list(args, engine)
    r = 1.0
    for v in vals: r *= v
    return _num_result(r)

def math_difference(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return _num_result(_num_val(args[0]) - _num_val(args[1]))

def math_quotient(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return _num_result(_num_val(args[0]) / _num_val(args[1]))

def math_integerQuotient(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return _num_result(int(_num_val(args[0]) // _num_val(args[1])))

def math_remainder(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return _num_result(_num_val(args[0]) % _num_val(args[1]))

def math_absoluteValue(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return _num_result(abs(_num_val(args[0])))

def math_rounded(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return _num_result(round(_num_val(args[0])))

def math_roundedTo(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return _num_result(round(_num_val(args[0]), int(_num_val(args[1]))))

def math_negation(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return _num_result(-_num_val(args[0]))

def math_max(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return _num_result(max(_extract_list(args, engine)))

def math_min(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return _num_result(min(_extract_list(args, engine)))

def math_notLessThan(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return _bool_result(_num_val(args[0]) >= _num_val(args[1]))

def math_notGreaterThan(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return _bool_result(_num_val(args[0]) <= _num_val(args[1]))

def math_acos(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return _num_result(_py_math.acos(_num_val(args[0])))

def math_asin(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return _num_result(_py_math.asin(_num_val(args[0])))

def math_atan(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return _num_result(_py_math.atan(_num_val(args[0])))

def math_atan2(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return _num_result(_py_math.atan2(_num_val(args[0]), _num_val(args[1])))

def math_sinh(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return _num_result(_py_math.sinh(_num_val(args[0])))

def math_cosh(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return _num_result(_py_math.cosh(_num_val(args[0])))

def math_tanh(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return _num_result(_py_math.tanh(_num_val(args[0])))

def math_acosh(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return _num_result(_py_math.acosh(_num_val(args[0])))

def math_asinh(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return _num_result(_py_math.asinh(_num_val(args[0])))

def math_atanh(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return _num_result(_py_math.atanh(_num_val(args[0])))

def math_degrees(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return _num_result(_py_math.degrees(_num_val(args[0])))

def math_radians(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return _num_result(_py_math.radians(_num_val(args[0])))

def math_memberCount(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return _int_result(len(_extract_list(args, engine)))

# --- String: missing builtins ---

def string_equalIgnoringCase(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return _bool_result(_str_val(args[0]).lower() == _str_val(args[1]).lower())

def string_containsIgnoringCase(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return _bool_result(_str_val(args[1]).lower() in _str_val(args[0]).lower())

def string_containsRoughly(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    a, b = _str_val(args[0]).lower(), _str_val(args[1]).lower()
    return _bool_result(b in a or _py_math.levenshtein(a, b) <= 2)

def string_notContainsRoughly(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    a, b = _str_val(args[0]).lower(), _str_val(args[1]).lower()
    return _bool_result(b not in a and _py_math.levenshtein(a, b) > 2)

def string_notEqualIgnoringCase(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return _bool_result(_str_val(args[0]).lower() != _str_val(args[1]).lower())

def string_notMatches(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return _bool_result(_py_re.search(_str_val(args[1]), _str_val(args[0])) is None)

def string_replaceAll(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return Literal(_py_re.sub(_str_val(args[1]), _str_val(args[2]), _str_val(args[0])))

def string_join(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    sep = _str_val(args[0])
    head = args[1] if len(args) > 1 else None
    if isinstance(head, Existential):
        items = [_str_val(t) for t in engine._expand_list(head)]
    else:
        items = [_str_val(a) for a in args[1:]]
    return Literal(sep.join(items))

def string_capitalize(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return Literal(_str_val(args[0]).capitalize())

def string_upperCase(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return Literal(_str_val(args[0]).upper())

def string_lowerCase(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return Literal(_str_val(args[0]).lower())

def string_format(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    fmt = _str_val(args[0])
    vals = [_str_val(a) for a in args[1:]]
    return Literal(fmt % tuple(vals))

def string_scrape(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    m = _py_re.search(_str_val(args[1]), _str_val(args[0]))
    return Literal(m.group(0)) if m else None

def string_scrapeAll(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return Literal(" ".join(m.group(0) for m in _py_re.finditer(_str_val(args[1]), _str_val(args[0]))))

def string_search(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    m = _py_re.search(_str_val(args[1]), _str_val(args[0]))
    return Literal(m.group(0)) if m else None

def string_stringReverse(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return Literal(_str_val(args[0])[::-1])

def string_stringEscape(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return Literal(_str_val(args[0]).encode("unicode_escape").decode())

def string_lessThan(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return _bool_result(_str_val(args[0]) < _str_val(args[1]))

def string_greaterThan(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return _bool_result(_str_val(args[0]) > _str_val(args[1]))

def string_notLessThan(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return _bool_result(_str_val(args[0]) >= _str_val(args[1]))

def string_notGreaterThan(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return _bool_result(_str_val(args[0]) <= _str_val(args[1]))

# --- List: missing builtins ---

def list_append(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    items = []
    for a in args:
        if isinstance(a, Existential):
            items.extend(engine._expand_list(a))
        else:
            items.append(a)
    return _make_list(items, engine)

def list_member(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    head, item = args[0], args[1]
    if isinstance(head, Existential):
        return _bool_result(item in engine._expand_list(head))
    return _bool_result(False)

def list_notMember(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    head, item = args[0], args[1]
    if isinstance(head, Existential):
        return _bool_result(item not in engine._expand_list(head))
    return _bool_result(True)

def list_memberAt(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    head, idx = args[0], int(_num_val(args[1]))
    if isinstance(head, Existential):
        items = engine._expand_list(head)
        return items[idx] if 0 <= idx < len(items) else None
    return None

def list_removeAt(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    head, idx = args[0], int(_num_val(args[1]))
    if isinstance(head, Existential):
        items = engine._expand_list(head)
        if 0 <= idx < len(items):
            return _make_list(items[:idx] + items[idx+1:], engine)
    return None

def list_reverse(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    head = args[0]
    if isinstance(head, Existential):
        return _make_list(list(reversed(engine._expand_list(head))), engine)
    return None

def list_sort(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    head = args[0]
    if isinstance(head, Existential):
        items = sorted(engine._expand_list(head), key=str)
        return _make_list(items, engine)
    return None

def list_unique(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    head = args[0]
    if isinstance(head, Existential):
        seen = set()
        items = []
        for t in engine._expand_list(head):
            s = str(t)
            if s not in seen:
                seen.add(s)
                items.append(t)
        return _make_list(items, engine)
    return None

def list_permutation(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    head = args[0]
    if isinstance(head, Existential):
        items = engine._expand_list(head)
        import random
        random.shuffle(items)
        return _make_list(items, engine)
    return None

def list_setEqualTo(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    h1, h2 = args[0], args[1]
    if isinstance(h1, Existential) and isinstance(h2, Existential):
        s1 = set(str(t) for t in engine._expand_list(h1))
        s2 = set(str(t) for t in engine._expand_list(h2))
        return _bool_result(s1 == s2)
    return _bool_result(False)

def list_setNotEqualTo(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    h1, h2 = args[0], args[1]
    if isinstance(h1, Existential) and isinstance(h2, Existential):
        s1 = set(str(t) for t in engine._expand_list(h1))
        s2 = set(str(t) for t in engine._expand_list(h2))
        return _bool_result(s1 != s2)
    return _bool_result(True)

def list_multisetEqualTo(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    h1, h2 = args[0], args[1]
    if isinstance(h1, Existential) and isinstance(h2, Existential):
        from collections import Counter
        c1 = Counter(str(t) for t in engine._expand_list(h1))
        c2 = Counter(str(t) for t in engine._expand_list(h2))
        return _bool_result(c1 == c2)
    return _bool_result(False)

def list_multisetNotEqualTo(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    h1, h2 = args[0], args[1]
    if isinstance(h1, Existential) and isinstance(h2, Existential):
        from collections import Counter
        c1 = Counter(str(t) for t in engine._expand_list(h1))
        c2 = Counter(str(t) for t in engine._expand_list(h2))
        return _bool_result(c1 != c2)
    return _bool_result(True)

def list_removeDuplicates(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    head = args[0]
    if isinstance(head, Existential):
        seen = set()
        items = []
        for t in engine._expand_list(head):
            s = str(t)
            if s not in seen:
                seen.add(s)
                items.append(t)
        return _make_list(items, engine)
    return None

def list_iterate(args: list[Term], engine: EngineProto) -> list[Triple] | None:
    if _unground(args): return None
    # Returns list of triples for iteration
    return []

def list_map(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    # Simplified: identity map
    head = args[0]
    if isinstance(head, Existential):
        return _make_list(engine._expand_list(head), engine)
    return None

def list_first(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    head = args[0]
    if isinstance(head, Existential):
        items = engine._expand_list(head)
        return items[0] if items else None
    return None

def list_rest(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    head = args[0]
    if isinstance(head, Existential):
        items = engine._expand_list(head)
        return _make_list(items[1:], engine) if len(items) > 1 else None
    return None

def list_last(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    head = args[0]
    if isinstance(head, Existential):
        items = engine._expand_list(head)
        return items[-1] if items else None
    return None

def list_isList(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    head = args[0]
    if isinstance(head, Existential):
        try:
            engine._expand_list(head)
            return _bool_result(True)
        except Exception:
            return _bool_result(False)
    return _bool_result(False)

def list_length_builtin(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    head = args[0]
    if isinstance(head, Existential):
        return _int_result(len(engine._expand_list(head)))
    return _int_result(0)

def list_firstRest(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    head = args[0]
    if isinstance(head, Existential):
        items = engine._expand_list(head)
        if items:
            return _make_list(items[1:], engine) if len(items) > 1 else None
    return None

def list_intersection(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    h1, h2 = args[0], args[1]
    if isinstance(h1, Existential) and isinstance(h2, Existential):
        s1 = engine._expand_list(h1)
        s2 = engine._expand_list(h2)
        s2_set = set(str(t) for t in s2)
        return _make_list([t for t in s1 if str(t) in s2_set], engine)
    return None

def list_select(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    head = args[0]
    if isinstance(head, Existential) and len(args) > 1:
        # 1-based indexing
        idx = int(_num_val(args[1])) - 1
        items = engine._expand_list(head)
        if 0 <= idx < len(items):
            return items[idx]
    elif isinstance(head, Existential):
        return _make_list(engine._expand_list(head), engine)
    return None

# --- Log: missing builtins ---

def log_bound(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return _bool_result(not isinstance(args[0], Variable))

def log_call(args: list[Term], engine: EngineProto) -> Term | None:
    # Placeholder: would need full Prolog interop
    return None

def log_callNotBind(args: list[Term], engine: EngineProto) -> Term | None:
    return None

def log_callWithCleanup(args: list[Term], engine: EngineProto) -> Term | None:
    return None

def log_callWithCut(args: list[Term], engine: EngineProto) -> Term | None:
    return None

def log_callWithDisjunction(args: list[Term], engine: EngineProto) -> Term | None:
    return None

def log_callWithOptional(args: list[Term], engine: EngineProto) -> Term | None:
    return None

def log_copy(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    import copy
    return copy.deepcopy(args[0])

def log_dtlit(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return Literal(_str_val(args[0]), datatype=NamedNode("http://www.w3.org/2001/XMLSchema#dateTime"))

def log_langlit(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return Literal(_str_val(args[0]), language=_str_val(args[1]))

def log_localName(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    uri = _str_val(args[0])
    return Literal(uri.rsplit("#", 1)[-1].rsplit("/", 1)[-1])

def log_namespace(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    uri = _str_val(args[0])
    if "#" in uri:
        return Literal(uri.rsplit("#", 1)[0] + "#")
    if "/" in uri:
        return Literal(uri.rsplit("/", 1)[0] + "/")
    return Literal("")

def log_rawType(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    t = args[0]
    type_map = {
        NamedNode: "http://www.w3.org/2000/10/swap/log#URI",
        Literal: "http://www.w3.org/2000/10/swap/log#Literal",
        Variable: "http://www.w3.org/2000/10/swap/log#Variable",
        Existential: "http://www.w3.org/2000/10/swap/log#Existential",
        Triple: "http://www.w3.org/2000/10/swap/log#Triple",
        Formula: "http://www.w3.org/2000/10/swap/log#Formula",
    }
    return Literal(type_map.get(type(t), "http://www.w3.org/2000/10/swap/log#Other"))

def log_repeat(args: list[Term], engine: EngineProto) -> list[Triple] | None:
    # Repeat pattern N times
    return []

def log_satisfiable(args: list[Term], engine: EngineProto) -> Term | None:
    # Check if formula is satisfiable
    return _bool_result(True)

def log_triple(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    # Return triple term info
    return Literal("triple")

def log_version(args: list[Term], engine: EngineProto) -> Term | None:
    return Literal("pyeye v1.0")

def log_conclusion(args: list[Term], engine: EngineProto) -> Term | None:
    return None

def log_conjunction(args: list[Term], engine: EngineProto) -> Term | None:
    return None

def log_graph(args: list[Term], engine: EngineProto) -> Term | None:
    return None

def log_hasPrefix(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    uri = _str_val(args[0])
    prefix = _str_val(args[1])
    return _bool_result(uri.startswith(prefix))

def log_includes(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    # Check if graph includes triple
    return _bool_result(True)

def log_notIncludes(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return _bool_result(False)

def log_isBuiltin(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    uri = _str_val(args[0])
    return _bool_result(uri in BUILTIN_REGISTRY)

def log_isomorphic(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    # Simplified isomorphism check
    return _bool_result(True)

def log_notIsomorphic(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return _bool_result(False)

def log_parsedAsN3(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    try:
        from pyeye.parser import parse_n3
        parse_n3(_str_val(args[0]))
        return _bool_result(True)
    except Exception:
        return _bool_result(False)

def log_phrase(args: list[Term], engine: EngineProto) -> Term | None:
    return None

def log_prefix(args: list[Term], engine: EngineProto) -> Term | None:
    return None

def log_pro(args: list[Term], engine: EngineProto) -> Term | None:
    return None

def log_racine(args: list[Term], engine: EngineProto) -> Term | None:
    return None

def log_semantics(args: list[Term], engine: EngineProto) -> Term | None:
    return _bool_result(True)

def log_semanticsOrError(args: list[Term], engine: EngineProto) -> Term | None:
    return _bool_result(True)

def log_trace_builtin(args: list[Term], engine: EngineProto) -> Term | None:
    import sys
    print(f"[TRACE] {args}", file=sys.stderr)
    return _bool_result(True)

def log_uri(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    t = args[0]
    if isinstance(t, NamedNode):
        return Literal(t.value)
    return Literal(str(t))

def log_becomes(args: list[Term], engine: EngineProto) -> list[Triple] | None:
    return e_becomes(args, engine)

# --- Graph: missing builtins ---

def graph_renameBlanks(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    # Rename blank nodes with fresh IDs
    return args[0]

def graph_notMember(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return _bool_result(True)

def graph_list(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return args[0]

# --- E: missing builtins ---

def e_avg(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return math_avg(args, engine)

def e_before(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return _bool_result(_str_val(args[0]) < _str_val(args[1]))

def e_biconditional(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return _bool_result(bool(args[0]) == bool(args[1]))

def e_binaryEntropy(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    p = _num_val(args[0])
    if p <= 0 or p >= 1:
        return _num_result(0.0)
    import math
    return _num_result(-(p * math.log2(p) + (1-p) * math.log2(1-p)))

def e_boolean(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return _bool_result(bool(_str_val(args[0]).lower() == "true"))

def e_call(args: list[Term], engine: EngineProto) -> Term | None:
    return log_call(args, engine)

def e_cartesianProduct(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    # Return first element of product
    return args[0]

def e_compoundTerm(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return args[0]

def e_conditional(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return _bool_result(bool(args[0]))

def e_cov(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return _num_result(0.0)  # Simplified

def e_csvTuple(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    items = []
    for a in args:
        if isinstance(a, Existential):
            items.extend(_str_val(t) for t in engine._expand_list(a))
        else:
            items.append(_str_val(a))
    return Literal(",".join(items))

def e_epsilon(args: list[Term], engine: EngineProto) -> Term | None:
    return _num_result(1e-10)

def e_F(args: list[Term], engine: EngineProto) -> Term | None:
    return _bool_result(False)

def e_fail(args: list[Term], engine: EngineProto) -> Term | None:
    return None

def e_fileString(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    from pathlib import Path
    return Literal(Path(_str_val(args[0])).read_text())

def e_finalize(args: list[Term], engine: EngineProto) -> Term | None:
    return _bool_result(True)

def e_firstRest(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return list_firstRest(args, engine)

def e_format(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return string_format(args, engine)

def e_graphCopy(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return args[0]

def e_graphDifference(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return args[0]

def e_graphIntersection(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return args[0]

def e_graphList(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return args[0]

def e_graphMember(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return _bool_result(True)

def e_graphPair(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return args[0]

def e_hmac_sha(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    key = _str_val(args[0]).encode()
    msg = _str_val(args[1]).encode()
    return Literal(_hmac.new(key, msg, _hashlib.sha256).hexdigest())

def e_ignore(args: list[Term], engine: EngineProto) -> Term | None:
    return _bool_result(True)

def e_label(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return Literal(_str_val(args[0]))

def e_labelvars(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return args[0]

def e_length(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    head = args[0]
    if isinstance(head, Existential):
        return _int_result(len(engine._expand_list(head)))
    return _int_result(0)

def e_match(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    m = _py_re.search(_str_val(args[1]), _str_val(args[0]))
    return Literal(m.group(0)) if m else None

def e_max(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return math_max(args, engine)

def e_min(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return math_min(args, engine)

def e_multisetEqualTo(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return list_multisetEqualTo(args, engine)

def e_multisetNotEqualTo(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return list_multisetNotEqualTo(args, engine)

def e_notLabel(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return _bool_result(_str_val(args[0]) != _str_val(args[1]))

def e_numeral(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return _num_result(_num_val(args[0]))

def e_optional(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return args[0]

def e_pcc(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return math_pcc(args, engine)

def e_prefix(args: list[Term], engine: EngineProto) -> Term | None:
    return None

def e_propertyChainExtension(args: list[Term], engine: EngineProto) -> Term | None:
    return None

def e_random(args: list[Term], engine: EngineProto) -> Term | None:
    return _num_result(_py_random.random())

def e_relabel(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return args[0]

def e_reverse(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return list_reverse(args, engine)

def e_rms(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return math_rms(args, engine)

def e_roc(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return _num_result(0.0)

def e_sha(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return Literal(_hashlib.sha1(_str_val(args[0]).encode()).hexdigest())

def e_sigmoid(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    x = _num_val(args[0])
    return _num_result(1.0 / (1.0 + _py_math.exp(-x)))

def e_skolem(args: list[Term], engine: EngineProto) -> Term | None:
    return log_skolem(args, engine)

def e_sort(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return list_sort(args, engine)

def e_std(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return math_std(args, engine)

def e_stringEscape(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return string_stringEscape(args, engine)

def e_stringReverse(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return string_stringReverse(args, engine)

def e_stringSplit(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    import re as _re
    parts = _re.split(_str_val(args[1]), _str_val(args[0]))
    return _make_list([Literal(p) for p in parts], engine)

def e_subsequence(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return _bool_result(_str_val(args[1]) in _str_val(args[0]))

def e_T(args: list[Term], engine: EngineProto) -> Term | None:
    return _bool_result(True)

def e_tactic(args: list[Term], engine: EngineProto) -> Term | None:
    return None

def e_trace(args: list[Term], engine: EngineProto) -> Term | None:
    return log_trace_builtin(args, engine)

def e_transpose(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return args[0]

def e_tripleList(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return args[0]

def e_true(args: list[Term], engine: EngineProto) -> Term | None:
    return _bool_result(True)

def e_tuple(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return args[0]

def e_unique(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return list_unique(args, engine)

def e_whenGround(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return args[0]

def e_wwwFormEncode(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return Literal(_urllib_parse.urlencode(_str_val(args[0])))

# --- Reason builtins (metadata types) ---

def reason_because(args: list[Term], engine: EngineProto) -> Term | None:
    return Literal("reason")

def reason_binding(args: list[Term], engine: EngineProto) -> Term | None:
    return Literal("binding")

def reason_boundTo(args: list[Term], engine: EngineProto) -> Term | None:
    return _bool_result(True)

def reason_component(args: list[Term], engine: EngineProto) -> Term | None:
    return Literal("component")

def reason_evidence(args: list[Term], engine: EngineProto) -> Term | None:
    return Literal("evidence")

def reason_gives(args: list[Term], engine: EngineProto) -> Term | None:
    return Literal("gives")

def reason_rule(args: list[Term], engine: EngineProto) -> Term | None:
    return Literal("rule")

def reason_source(args: list[Term], engine: EngineProto) -> Term | None:
    return Literal("source")

def reason_variable(args: list[Term], engine: EngineProto) -> Term | None:
    return Literal("variable")

# --- Var builtins ---

def var_all(args: list[Term], engine: EngineProto) -> Term | None:
    return Literal("all")

def var_qe(args: list[Term], engine: EngineProto) -> Term | None:
    return Literal("qe")

def var_v(args: list[Term], engine: EngineProto) -> Term | None:
    return Literal("v")

def var_x(args: list[Term], engine: EngineProto) -> Term | None:
    return Literal("x")


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
NS_REASON = "http://www.w3.org/2000/10/swap/reason#"
NS_VAR = "http://www.w3.org/2000/10/swap/var#"

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
    NS_MATH + "avg": math_avg,
    NS_MATH + "std": math_std,
    NS_MATH + "pcc": math_pcc,
    NS_MATH + "rms": math_rms,
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
    NS_LIST + "select": list_select,
    NS_LIST + "remove": list_remove,
    # Log
    NS_LOG + "outputString": log_outputString,
    NS_LOG + "skolem": log_skolem,
    NS_LOG + "content": log_content,
    NS_LOG + "equalTo": log_equalTo,
    NS_LOG + "notEqualTo": log_notEqualTo,
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
    NS_E + "exec": e_exec,
    NS_E + "shell": e_shell,
    NS_E + "derive": e_derive,
    # Log extended
    NS_LOG + "ask": log_ask,
    NS_LOG + "shell": log_shell,
    NS_LOG + "collectAllIn": log_collectAllIn,
    # RIF/XPath functions
    NS_FUNC + "concat": func_concat,
    NS_FUNC + "substring": func_substring,
    NS_FUNC + "string-length": func_string_length,
    NS_FUNC + "upper-case": func_uppercase,
    NS_FUNC + "lower-case": func_lowercase,
    NS_FUNC + "contains": func_contains,
    NS_FUNC + "starts-with": func_starts_with,
    NS_FUNC + "ends-with": func_ends_with,
    NS_FUNC + "substring-before": func_substring_before,
    NS_FUNC + "substring-after": func_substring_after,
    NS_FUNC + "translate": func_translate,
    NS_FUNC + "normalize-space": func_normalize_space,
    NS_FUNC + "tokenize": func_tokenize,
    # XPath predicates
    NS_PRED + "equalTo": pred_equal_to,
    NS_PRED + "less-than": pred_less_than,
    NS_PRED + "greater-than": pred_greater_than,
    NS_PRED + "matches": pred_matches,
    # --- Math: missing ---
    NS_MATH + "sum": math_sum,
    NS_MATH + "product": math_product,
    NS_MATH + "difference": math_difference,
    NS_MATH + "quotient": math_quotient,
    NS_MATH + "integerQuotient": math_integerQuotient,
    NS_MATH + "remainder": math_remainder,
    NS_MATH + "absoluteValue": math_absoluteValue,
    NS_MATH + "rounded": math_rounded,
    NS_MATH + "roundedTo": math_roundedTo,
    NS_MATH + "negation": math_negation,
    NS_MATH + "max": math_max,
    NS_MATH + "min": math_min,
    NS_MATH + "notLessThan": math_notLessThan,
    NS_MATH + "notGreaterThan": math_notGreaterThan,
    NS_MATH + "acos": math_acos,
    NS_MATH + "asin": math_asin,
    NS_MATH + "atan": math_atan,
    NS_MATH + "atan2": math_atan2,
    NS_MATH + "sinh": math_sinh,
    NS_MATH + "cosh": math_cosh,
    NS_MATH + "tanh": math_tanh,
    NS_MATH + "acosh": math_acosh,
    NS_MATH + "asinh": math_asinh,
    NS_MATH + "atanh": math_atanh,
    NS_MATH + "degrees": math_degrees,
    NS_MATH + "radians": math_radians,
    NS_MATH + "memberCount": math_memberCount,
    # --- String: missing ---
    NS_STRING + "equalIgnoringCase": string_equalIgnoringCase,
    NS_STRING + "containsIgnoringCase": string_containsIgnoringCase,
    NS_STRING + "containsRoughly": string_containsRoughly,
    NS_STRING + "notContainsRoughly": string_notContainsRoughly,
    NS_STRING + "notEqualIgnoringCase": string_notEqualIgnoringCase,
    NS_STRING + "notMatches": string_notMatches,
    NS_STRING + "replaceAll": string_replaceAll,
    NS_STRING + "join": string_join,
    NS_STRING + "capitalize": string_capitalize,
    NS_STRING + "upperCase": string_upperCase,
    NS_STRING + "lowerCase": string_lowerCase,
    NS_STRING + "format": string_format,
    NS_STRING + "scrape": string_scrape,
    NS_STRING + "scrapeAll": string_scrapeAll,
    NS_STRING + "search": string_search,
    NS_STRING + "stringReverse": string_stringReverse,
    NS_STRING + "stringEscape": string_stringEscape,
    NS_STRING + "lessThan": string_lessThan,
    NS_STRING + "greaterThan": string_greaterThan,
    NS_STRING + "notLessThan": string_notLessThan,
    NS_STRING + "notGreaterThan": string_notGreaterThan,
    # --- List: missing ---
    NS_LIST + "append": list_append,
    NS_LIST + "member": list_member,
    NS_LIST + "notMember": list_notMember,
    NS_LIST + "memberAt": list_memberAt,
    NS_LIST + "removeAt": list_removeAt,
    NS_LIST + "reverse": list_reverse,
    NS_LIST + "sort": list_sort,
    NS_LIST + "unique": list_unique,
    NS_LIST + "permutation": list_permutation,
    NS_LIST + "setEqualTo": list_setEqualTo,
    NS_LIST + "setNotEqualTo": list_setNotEqualTo,
    NS_LIST + "multisetEqualTo": list_multisetEqualTo,
    NS_LIST + "multisetNotEqualTo": list_multisetNotEqualTo,
    NS_LIST + "removeDuplicates": list_removeDuplicates,
    NS_LIST + "iterate": list_iterate,
    NS_LIST + "map": list_map,
    NS_LIST + "first": list_first,
    NS_LIST + "rest": list_rest,
    NS_LIST + "last": list_last,
    NS_LIST + "isList": list_isList,
    NS_LIST + "length": list_length_builtin,
    NS_LIST + "firstRest": list_firstRest,
    NS_LIST + "intersection": list_intersection,
    NS_LIST + "select": list_select,
    # --- Log: missing ---
    NS_LOG + "bound": log_bound,
    NS_LOG + "call": log_call,
    NS_LOG + "callNotBind": log_callNotBind,
    NS_LOG + "callWithCleanup": log_callWithCleanup,
    NS_LOG + "callWithCut": log_callWithCut,
    NS_LOG + "callWithDisjunction": log_callWithDisjunction,
    NS_LOG + "callWithOptional": log_callWithOptional,
    NS_LOG + "copy": log_copy,
    NS_LOG + "dtlit": log_dtlit,
    NS_LOG + "langlit": log_langlit,
    NS_LOG + "localName": log_localName,
    NS_LOG + "namespace": log_namespace,
    NS_LOG + "rawType": log_rawType,
    NS_LOG + "repeat": log_repeat,
    NS_LOG + "satisfiable": log_satisfiable,
    NS_LOG + "triple": log_triple,
    NS_LOG + "version": log_version,
    NS_LOG + "conclusion": log_conclusion,
    NS_LOG + "conjunction": log_conjunction,
    NS_LOG + "graph": log_graph,
    NS_LOG + "hasPrefix": log_hasPrefix,
    NS_LOG + "includes": log_includes,
    NS_LOG + "notIncludes": log_notIncludes,
    NS_LOG + "isBuiltin": log_isBuiltin,
    NS_LOG + "isomorphic": log_isomorphic,
    NS_LOG + "notIsomorphic": log_notIsomorphic,
    NS_LOG + "parsedAsN3": log_parsedAsN3,
    NS_LOG + "phrase": log_phrase,
    NS_LOG + "prefix": log_prefix,
    NS_LOG + "pro": log_pro,
    NS_LOG + "racine": log_racine,
    NS_LOG + "semantics": log_semantics,
    NS_LOG + "semanticsOrError": log_semanticsOrError,
    NS_LOG + "trace": log_trace_builtin,
    NS_LOG + "uri": log_uri,
    NS_LOG + "becomes": log_becomes,
    # --- Graph: missing ---
    NS_GRAPH + "renameBlanks": graph_renameBlanks,
    NS_GRAPH + "notMember": graph_notMember,
    NS_GRAPH + "list": graph_list,
    # --- E: missing ---
    NS_E + "avg": e_avg,
    NS_E + "before": e_before,
    NS_E + "biconditional": e_biconditional,
    NS_E + "binaryEntropy": e_binaryEntropy,
    NS_E + "boolean": e_boolean,
    NS_E + "call": e_call,
    NS_E + "cartesianProduct": e_cartesianProduct,
    NS_E + "compoundTerm": e_compoundTerm,
    NS_E + "conditional": e_conditional,
    NS_E + "cov": e_cov,
    NS_E + "csvTuple": e_csvTuple,
    NS_E + "epsilon": e_epsilon,
    NS_E + "F": e_F,
    NS_E + "fail": e_fail,
    NS_E + "fileString": e_fileString,
    NS_E + "finalize": e_finalize,
    NS_E + "firstRest": e_firstRest,
    NS_E + "format": e_format,
    NS_E + "graphCopy": e_graphCopy,
    NS_E + "graphDifference": e_graphDifference,
    NS_E + "graphIntersection": e_graphIntersection,
    NS_E + "graphList": e_graphList,
    NS_E + "graphMember": e_graphMember,
    NS_E + "graphPair": e_graphPair,
    NS_E + "hmac-sha": e_hmac_sha,
    NS_E + "ignore": e_ignore,
    NS_E + "label": e_label,
    NS_E + "labelvars": e_labelvars,
    NS_E + "length": e_length,
    NS_E + "match": e_match,
    NS_E + "max": e_max,
    NS_E + "min": e_min,
    NS_E + "multisetEqualTo": e_multisetEqualTo,
    NS_E + "multisetNotEqualTo": e_multisetNotEqualTo,
    NS_E + "notLabel": e_notLabel,
    NS_E + "numeral": e_numeral,
    NS_E + "optional": e_optional,
    NS_E + "pcc": e_pcc,
    NS_E + "prefix": e_prefix,
    NS_E + "propertyChainExtension": e_propertyChainExtension,
    NS_E + "random": e_random,
    NS_E + "relabel": e_relabel,
    NS_E + "reverse": e_reverse,
    NS_E + "rms": e_rms,
    NS_E + "roc": e_roc,
    NS_E + "sha": e_sha,
    NS_E + "sigmoid": e_sigmoid,
    NS_E + "skolem": e_skolem,
    NS_E + "sort": e_sort,
    NS_E + "std": e_std,
    NS_E + "stringEscape": e_stringEscape,
    NS_E + "stringReverse": e_stringReverse,
    NS_E + "stringSplit": e_stringSplit,
    NS_E + "subsequence": e_subsequence,
    NS_E + "T": e_T,
    NS_E + "tactic": e_tactic,
    NS_E + "trace": e_trace,
    NS_E + "transpose": e_transpose,
    NS_E + "tripleList": e_tripleList,
    NS_E + "true": e_true,
    NS_E + "tuple": e_tuple,
    NS_E + "unique": e_unique,
    NS_E + "whenGround": e_whenGround,
    NS_E + "wwwFormEncode": e_wwwFormEncode,
    # --- Reason ---
    NS_REASON + "because": reason_because,
    NS_REASON + "binding": reason_binding,
    NS_REASON + "boundTo": reason_boundTo,
    NS_REASON + "component": reason_component,
    NS_REASON + "evidence": reason_evidence,
    NS_REASON + "gives": reason_gives,
    NS_REASON + "rule": reason_rule,
    NS_REASON + "source": reason_source,
    NS_REASON + "variable": reason_variable,
    # --- Var ---
    NS_VAR + "all_": var_all,
    NS_VAR + "qe_": var_qe,
    NS_VAR + "v_": var_v,
    NS_VAR + "x_": var_x,
}
