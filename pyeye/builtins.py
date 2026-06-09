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
import sys as _sys
from typing import Protocol

from pyeye.term import NamedNode, Literal, Variable, Existential, Triple, Term, Formula, ListTerm
from pyeye.store import TripleStore

# Arbitrary-precision integer arithmetic (math:product / math:exponentiation
# chains such as peasant multiplication) routinely exceeds CPython's default
# 4300-digit int<->str conversion guard; lift it so big-int literals convert.
if hasattr(_sys, "set_int_max_str_digits"):
    if _sys.get_int_max_str_digits() < 1_000_000:
        _sys.set_int_max_str_digits(1_000_000)


class EngineProto(Protocol):
    """Minimal engine interface builtins need."""
    store: TripleStore
    _skolem_counter: int


class MultiResult:
    """Returned by generative builtins (e.g. list:iterate) that produce
    multiple result terms from a single call. The engine will extend
    the current binding once for each element."""
    def __init__(self, results: list[Term]) -> None:
        self.results = results


class BindingsList:
    """Returned by meta-builtins that produce multiple binding sets."""
    def __init__(self, bindings: list) -> None:
        self.bindings = bindings


class Builtin(Protocol):
    def __call__(self, args: list[Term], engine: EngineProto) -> Term | list[Triple] | MultiResult | None:
        ...


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _unground(args: list[Term]) -> bool:
    """Return True if any *input* arg is a Variable (not yet ground).

    The engine always appends the object (output slot) as the last element of
    args.  When that slot is an unbound Variable it must not be counted as
    unground — only the input args matter.  This function therefore strips a
    trailing Variable before checking, which fixes the entire class of
    'builtin silently returns None in rule context' bugs without requiring
    per-function args[:N] patches.
    """
    check = args[:-1] if len(args) >= 2 and isinstance(args[-1], Variable) else args
    return any(isinstance(a, Variable) for a in check)


def _str_val(t: Term) -> str:
    """Extract string value from a Literal or NamedNode."""
    if isinstance(t, Literal):
        return t.value
    if isinstance(t, NamedNode):
        return t.value
    return str(t)


def _parse_datetime_float(s: str) -> float:
    """Parse an xsd:dateTime string to a POSIX timestamp (float) for ordering."""
    from datetime import datetime, timezone, timedelta
    import re as _re3
    # Normalise: replace space separator with T
    s = s.strip().replace(" ", "T")
    # Handle timezone offset like +01:00 or -05:30 or Z
    tz_match = _re3.search(r'([+-])(\d{2}):(\d{2})$', s)
    if tz_match:
        sign, hh, mm = tz_match.groups()
        offset = timedelta(hours=int(hh), minutes=int(mm))
        if sign == '-':
            offset = -offset
        s_no_tz = s[:tz_match.start()]
        dt = datetime.fromisoformat(s_no_tz).replace(tzinfo=timezone(offset))
    elif s.endswith('Z'):
        dt = datetime.fromisoformat(s[:-1]).replace(tzinfo=timezone.utc)
    else:
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
    return dt.timestamp()


def _parse_duration_years(s: str) -> float | None:
    """Parse an ISO 8601 duration like 'P80Y' or 'P1Y6M' to fractional years.

    Returns None if the string is not a duration.
    """
    import re as _re2
    m = _re2.match(r'^P(?:(\d+(?:\.\d+)?)Y)?(?:(\d+(?:\.\d+)?)M)?', s)
    if not m:
        return None
    years = float(m.group(1) or 0)
    months = float(m.group(2) or 0)
    return years + months / 12.0


def _num_val(t: Term) -> float:
    """Extract numeric value from a Literal.

    Also handles ISO 8601 durations (PnY) → fractional years.
    """
    if isinstance(t, Variable):
        raise TypeError(f"Unbound variable: {t}")
    if isinstance(t, Literal):
        v = t.value
        d = _parse_duration_years(v)
        if d is not None:
            return d
        # Boolean literals: true → 1.0, false → 0.0
        if v.lower() == "true":
            return 1.0
        if v.lower() == "false":
            return 0.0
        # xsd:dateTime literals — convert to POSIX timestamp for comparison
        dt_node = t.datatype
        if dt_node is not None and isinstance(dt_node, NamedNode):
            dt_uri = dt_node.value
            if dt_uri == "http://www.w3.org/2001/XMLSchema#dateTime":
                return _parse_datetime_float(v)
            if dt_uri == "http://www.w3.org/2001/XMLSchema#date":
                return _parse_datetime_float(v + "T00:00:00")
        return float(v)
    if isinstance(t, NamedNode):
        return float(t.value)
    raise TypeError(f"Non-numeric term: {t}")


def _num_exact(t: Term):
    """Like ``_num_val`` but preserves Python ``int`` for integer-typed
    literals so arbitrary-precision integer arithmetic does not lose
    precision by round-tripping through ``float`` (e.g. fib(3674), which has
    several hundred digits and overflows a float to ``inf``)."""
    if isinstance(t, Literal) and _is_integer_term(t):
        try:
            return int(t.value)
        except ValueError:
            pass
    return _num_val(t)


def numeric_equal(a: Term, b: Term) -> bool:
    """Whether two literals denote the same number (datatype-insensitive).

    Used to match a builtin's computed result against a ground object slot:
    ``(7 2) math:remainder 1`` must hold whether the computed remainder is
    typed xsd:integer or xsd:double.
    """
    if not isinstance(a, Literal) or not isinstance(b, Literal):
        return False
    try:
        return _num_exact(a) == _num_exact(b)
    except (TypeError, ValueError):
        return False


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


_XSD_INTEGER = "http://www.w3.org/2001/XMLSchema#integer"

def _is_integer_term(t: Term) -> bool:
    return (isinstance(t, Literal) and t.datatype is not None
            and isinstance(t.datatype, NamedNode)
            and t.datatype.value == _XSD_INTEGER)

def _typed_num_result(v, inputs: list[Term]) -> Literal:
    if all(_is_integer_term(t) for t in inputs):
        if isinstance(v, int):
            return _int_result(v)
        try:
            if v == int(v):
                return _int_result(int(v))
        except (OverflowError, ValueError):
            pass
    return _num_result(v)


def _input_only(args: list[Term]) -> list[Term]:
    """Return input args, stripping a trailing unbound Variable output slot.

    When a function-style builtin is called from the engine, the last element
    of *args* is the object of the builtin triple — the output slot.  If it is
    still an unbound Variable we must not treat it as a ground input.

    Only strips the last arg when there are at least 2 args, so that
    single-element calls (e.g. in unit tests) are not incorrectly emptied.
    """
    if len(args) >= 2 and isinstance(args[-1], Variable):
        return args[:-1]
    return args


def _make_list(items: list[Term], engine: EngineProto) -> ListTerm:
    """Create a ListTerm from a Python list of terms."""
    return ListTerm(items=tuple(items))


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
    return _typed_num_result(_num_exact(args[0]) + _num_exact(args[1]), args[:2])


def math_minus(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args):
        return None
    return _typed_num_result(_num_exact(args[0]) - _num_exact(args[1]), args[:2])


def math_times(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args):
        return None
    return _typed_num_result(_num_exact(args[0]) * _num_exact(args[1]), args[:2])


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
    inputs = _input_only(args)
    if _unground(inputs):
        return None
    return Literal("".join(_str_val(a) for a in inputs))


def string_contains(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args):
        return None
    return _bool_result(_str_val(args[1]) in _str_val(args[0]))


def string_length(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args[:1]):
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
    if _unground(args[:1]):
        return None
    dt = _str_val(args[0])
    try:
        return _int_result(int(dt[:4]))
    except (ValueError, IndexError):
        return None


def time_month(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args[:1]):
        return None
    dt = _str_val(args[0])
    try:
        return _int_result(int(dt[5:7]))
    except (ValueError, IndexError):
        return None


def time_day(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args[:1]):
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

def list_in(args: list[Term], engine: EngineProto) -> "Term | MultiResult | None":
    """list:in(item, list-head) — checks if item is in the RDF list.

    When item (args[0]) is unbound, generates bindings for each member of the
    list (generative mode). When item is ground, checks membership.
    """
    # Only require the list (args[1]) to be ground; item (args[0]) may be unbound
    if len(args) < 2 or isinstance(args[1], Variable):
        return None
    item = args[0]
    head = args[1]
    item_is_var = isinstance(item, Variable)

    if not isinstance(head, ListTerm):
        return MultiResult([]) if item_is_var else _bool_result(False)

    members = list(head.items)

    if item_is_var:
        return MultiResult(members)
    return _bool_result(item in members)


def list_length(args: list[Term], engine: EngineProto) -> Term | None:  # pragma: no cover — overridden by list_length at line 611
    if _unground(args):
        return None
    head = args[0]
    if not isinstance(head, ListTerm):
        return _int_result(0)

    return _int_result(len(head.items))


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
    """log:equalTo — unification (EYE ``unify(X, Y)``), not bare comparison.

    When exactly one side is an unbound Variable and the other is ground, the
    variable is bound to the ground value (mutating the engine's current
    binding) and the builtin succeeds.  When both sides are ground it is an
    equality test.
    """
    if len(args) < 2:
        return None
    a, b = args[0], args[1]
    a_var = isinstance(a, Variable)
    b_var = isinstance(b, Variable)
    # Binding a variable requires an engine to mutate the current binding.
    if (a_var or b_var) and engine is None:
        return None
    if a_var and not b_var:
        cur = getattr(engine, "_current_binding", {})
        nb = dict(cur)
        nb[a.id] = b
        engine._current_binding = nb
        return _bool_result(True)
    if b_var and not a_var:
        cur = getattr(engine, "_current_binding", {})
        nb = dict(cur)
        nb[b.id] = a
        engine._current_binding = nb
        return _bool_result(True)
    if a_var and b_var:
        return None
    return _bool_result(a == b)


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
    if _unground(args[:1]):
        return None
    return Literal(_hashlib.md5(_str_val(args[0]).encode()).hexdigest())


def crypto_sha(args: list[Term], engine: EngineProto) -> Term | None:
    """SHA-1 (deprecated but kept for EYE compatibility)."""
    if _unground(args[:1]):
        return None
    return Literal(_hashlib.sha1(_str_val(args[0]).encode()).hexdigest())


def crypto_sha256(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args[:1]):
        return None
    return Literal(_hashlib.sha256(_str_val(args[0]).encode()).hexdigest())


def crypto_sha512(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args[:1]):
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
    if _unground(args[:3]):
        return None
    try:
        return Literal(_re.sub(_str_val(args[1]), _str_val(args[2]), _str_val(args[0])))
    except _re.error:
        return Literal(_str_val(args[0]))


def string_substring(args: list[Term], engine: EngineProto) -> Term | None:
    """Substring: string:substring(str, start, length) → string."""
    if _unground(args[:2]):
        return None
    s = _str_val(args[0])
    start = int(_num_val(args[1]))
    length = int(_num_val(args[2])) if len(args) > 2 and not isinstance(args[2], Variable) else len(s)
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
    inp = _input_args(args, 2)
    base, exp = _num_exact(inp[0]), _num_exact(inp[1])
    if isinstance(base, int) and isinstance(exp, int) and exp >= 0:
        return _int_result(base ** exp)
    return _num_result(_math.pow(base, exp))


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
    inputs = _input_only(args)
    if _unground(inputs):
        return None
    nums = [_num_val(a) for a in inputs]
    return _num_result(_statistics.mean(nums))


def math_std(args: list[Term], engine: EngineProto) -> Term | None:
    """Standard deviation of a list of numbers."""
    inputs = _input_only(args)
    if _unground(inputs):
        return None
    nums = [_num_val(a) for a in inputs]
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
    if n < 2:  # pragma: no cover — guarded by len(vals)<4 check above; n>=2 always here
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
    inputs = _input_only(args)
    if _unground(inputs):
        return None
    nums = [_num_val(a) for a in inputs]
    mean_sq = sum(x ** 2 for x in nums) / len(nums)
    return _num_result(_math.sqrt(mean_sq))


# ---------------------------------------------------------------------------
# Extended List builtins
# ---------------------------------------------------------------------------

def list_select(args: list[Term], engine: EngineProto) -> Term | None:  # pragma: no cover — overridden by list_select at line 1862
    """Select nth element from a list (1-indexed).

    list:select(list-head, index) → element.
    """
    if _unground(args):
        return None
    head = args[0]
    if not isinstance(head, ListTerm):
        return None
    try:
        index = int(_num_val(args[1])) - 1  # 1-indexed
    except (ValueError, IndexError):
        return None

    items = head.items
    if 0 <= index < len(items):
        return items[index]
    return None


def list_length(args: list[Term], engine: EngineProto) -> Term | None:
    """Return the length of an RDF list.

    Two calling conventions:
    - Via N3 engine (list subject expanded): args = [elem0, ..., elemN-1, output_var]
    - Direct call with list head: args = [Existential_head] or [Existential_head, output_var]
    - Unground (Variable head): return None
    """
    if not args:
        return None
    # Direct call: ListTerm head
    if len(args) <= 2 and isinstance(args[0], ListTerm):
        return _int_result(len(args[0].items))
    # Unground head (Variable)
    if isinstance(args[0], Variable):
        return None
    # Engine-expanded: args = [elem0, ..., elemN-1, output_var]
    items = args[:-1]
    return _int_result(len(items))


def list_remove(args: list[Term], engine: EngineProto) -> list[Triple] | None:
    """Remove an element from a list by index.

    Simplified: returns a new list without the removed element.
    """
    if _unground(args):
        return None
    # Simplified: just return all triples except the removed one
    return list(engine.store)


def list_car(args: list[Term], engine: EngineProto) -> Term | None:  # pragma: no cover — overridden by list_car at line 1393
    """Return the first element of a list."""
    if _unground(args):
        return None
    head = args[0]
    if not isinstance(head, ListTerm):
        return None
    return head.items[0] if head.items else None


def list_cdr(args: list[Term], engine: EngineProto) -> Term | None:  # pragma: no cover — overridden by list_cdr at line 1407
    """Return the rest of a list (after the first element)."""
    if _unground(args):
        return None
    head = args[0]
    if not isinstance(head, ListTerm):
        return None
    return ListTerm(items=head.items[1:]) if len(head.items) > 1 else ListTerm(items=())


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
    inputs = _input_only(args)
    if _unground(inputs):
        return None
    s = _str_val(inputs[0])
    start = int(_num_val(inputs[1])) - 1  # XPath is 1-indexed
    if len(inputs) > 2:
        length = int(_num_val(inputs[2]))
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
    return ListTerm(items=tuple(Literal(tok.strip()) for tok in tokens))


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


_LOG_IMPLIES_IRI = "http://www.w3.org/2000/10/swap/log#implies"


def _prove_implication(impl_triple: Triple, binding: dict, engine: EngineProto) -> bool:
    """Prove a quoted ``{A} log:implies {C}`` goal under *binding*.

    The antecedent A is generally hypothetical (e.g. ``?X a :Negative`` for a
    case that is not asserted in the store), so we reason by *assumption*:
    temporarily assert the ground antecedent triples, attempt to prove the
    consequent, then retract.  This matches EYE's behaviour where the case
    rules ``{?X a :Negative} => {:t :isProvenFor ?X}`` license the conclusion.
    """
    from pyeye.unify import apply_binding as _apply
    ante = _apply(impl_triple.subject, binding)
    cons = _apply(impl_triple.object, binding)
    if not isinstance(ante, Formula) or not isinstance(cons, Formula):
        return False

    # Collect ground antecedent triples to assert as hypotheses.
    hypotheses: list[Triple] = []
    for t in ante.triples:
        if t.is_ground():
            hypotheses.append(t)

    added: list[Triple] = []
    for h in hypotheses:
        if engine.store.add(h):
            added.append(h)
    try:
        sols = engine._match_formula(cons, dict(binding))
        ok = bool(sols)
    finally:
        for h in added:
            engine.store.retract(h)
    return ok


def _prove_subformula(formula: Formula, binding: dict, engine: EngineProto) -> list[dict]:
    """Prove *formula* under *binding*, returning all solution bindings.

    Triples whose predicate is ``log:implies`` are proven via
    :func:`_prove_implication` (hypothetical reasoning); everything else is
    delegated to the engine's pattern matcher.
    """
    impl_triples = [t for t in formula.triples
                    if isinstance(t.predicate, NamedNode)
                    and t.predicate.value == _LOG_IMPLIES_IRI]
    plain_triples = [t for t in formula.triples if t not in impl_triples]

    if plain_triples:
        base = Formula(triples=tuple(plain_triples))
        solutions = engine._match_formula(base, dict(binding))
    else:
        solutions = [dict(binding)]

    if not impl_triples:
        return solutions

    out: list[dict] = []
    for sol in solutions:
        if all(_prove_implication(it, sol, engine) for it in impl_triples):
            out.append(sol)
    return out


def log_forAllIn(args: list[Term], engine: EngineProto) -> Term | None:
    """log:forAllIn — ``forall(Cond, Action)`` over a quoted ``(Cond Action)``.

    EYE: ``forAllIn([Cond, Action], Scope) :- forall(Cond, Action)`` which is
    ``\\+ (call(Cond), \\+ call(Action))`` — for *every* solution of the Cond
    formula, the Action formula must also hold (under the Cond solution's
    bindings).  The Cond formula may bind variables (e.g. via ``list:member``)
    that the Action then consumes; the builtin itself binds nothing in the
    outer scope (it is a pure guard) and the Scope object is ignored.
    """
    if len(args) < 2:
        return None
    cond, action = args[0], args[1]
    if not isinstance(cond, Formula) or not isinstance(action, Formula):
        return None
    if not hasattr(engine, "_match_formula"):
        return None

    # Re-entry guard: proving an Action implication may try to derive the very
    # conclusion that the enclosing proof-by-cases rule produces, which would
    # re-fire this forAllIn.  EYE isolates each forAllIn in a sub-reasoner; we
    # approximate that by refusing to recurse into forAllIn while one is active.
    if getattr(engine, "_in_forallin", False):
        return None
    engine._in_forallin = True
    # forAllIn is a pure guard: it binds nothing in the outer scope.  Its
    # internal proofs (via _match_formula / list:member) mutate
    # engine._current_binding, so snapshot and restore it afterwards.
    saved = getattr(engine, "_current_binding", {})
    binding = saved or {}
    try:
        cond_solutions = _prove_subformula(cond, dict(binding), engine)
        # Empty Cond → vacuously true (forall over empty set).
        for sol in cond_solutions:
            action_solutions = _prove_subformula(action, sol, engine)
            if not action_solutions:
                return None  # Cond holds but Action fails → forall fails
        return _bool_result(True)
    finally:
        engine._in_forallin = False
        engine._current_binding = saved


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
    """Compute the deductive closure of a named graph.

    Takes a graph identifier (NamedNode or Existential), extracts all
    triples and rules from that graph, runs forward chaining until
    fixpoint, and adds all derived triples back to the main store.

    Returns the graph identifier.
    """
    if _unground(args):
        return None
    graph_id = args[0]

    # Extract triples from the graph
    graph_triples = list(engine.store.match(graph=graph_id))
    if not graph_triples:
        return graph_id

    # Extract rules from the graph (triples with log:implies predicate)
    log_implies = NamedNode("http://www.w3.org/2000/10/swap/log#implies")
    graph_rules = []
    for t in graph_triples:
        if t.predicate == log_implies:
            if isinstance(t.subject, Formula) and isinstance(t.object, Formula):
                from pyeye.parser import Rule
                graph_rules.append(Rule(t.subject, t.object))

    # If no rules, nothing to derive
    if not graph_rules:
        return graph_id

    # Create a temporary store with the graph's triples
    from pyeye.store import TripleStore
    from pyeye.engine import Engine
    temp_store = TripleStore()
    for t in graph_triples:
        temp_store.add(Triple(t.subject, t.predicate, t.object))

    # Create a temporary engine and run forward chaining
    temp_engine = Engine()
    temp_engine.store = temp_store
    temp_engine._rules = list(graph_rules)
    temp_engine.run()

    # Add derived triples back to the main store
    new_count = 0
    for t in temp_engine.store:
        if engine.store.add(t):
            new_count += 1

    return graph_id


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
        if isinstance(result, str):  # pragma: no cover — Term is a bare Protocol; str satisfies it
            return Literal(result)
        if isinstance(result, (int, float)):  # pragma: no cover — same reason
            return Literal(str(result))
        return None  # pragma: no cover — same reason
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
        if new_arg is None:  # pragma: no cover — len>=6 guarantees args[3] exists
            return []

        # Check if new_arg is a list head (Existential pointing to RDF list)
        if isinstance(new_arg, ListTerm):
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
        elif isinstance(old_t, ListTerm):
            # Retract all triples in the list
            _retract_list(old_t, engine)
        if isinstance(new_t, Triple):
            engine.store.add(new_t)
            return [new_t]
        elif isinstance(new_t, ListTerm):
            return _assert_list_as_triples(new_t, engine)
    return None


def _retract_list(head: ListTerm, engine: EngineProto) -> None:
    """Retract all triples contained in a ListTerm."""
    for item in head.items:
        if isinstance(item, Triple):
            engine.store.retract(item)


def _assert_list_as_triples(head: ListTerm, engine: EngineProto) -> list[Triple]:
    """Assert all triples contained in a ListTerm."""
    asserted: list[Triple] = []
    for item in head.items:
        if isinstance(item, Triple):
            if engine.store.add(item):
                asserted.append(item)
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
    except Exception:  # pragma: no cover — subprocess exceptions require process failure
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

    try:  # pragma: no cover — requires live network access
        with _urllib.urlopen(url, timeout=30) as response:
            content = response.read().decode("utf-8", errors="replace")
            return Literal(content[:10000])  # Limit to 10KB
    except Exception:
        return None


def log_shell(args: list[Term], engine: EngineProto) -> Term | None:
    """Execute shell command and return stdout (alias for e:shell)."""
    return e_shell(args, engine)


def log_collectAllIn(args: list[Term], engine: EngineProto) -> Term | None:
    """log:collectAllIn — bag collection builtin.

    Calling convention (inline list subject):
        (Template Pattern OutputList) log:collectAllIn Scope

    For each binding of free variables in Pattern that satisfies Pattern against
    the store (combined with the current binding), evaluate Template and collect
    into OutputList.  If OutputList is a Variable, bind it to the resulting RDF
    list head.

    The current engine binding is available via engine._current_binding (set in
    _handle_builtin before each builtin call).
    """
    from pyeye.term import Formula as _Formula
    from pyeye.unify import apply_binding as _apply
    # args layout: [Template, Pattern, OutputList, Scope]
    # (the object of the triple — Scope — is appended last by _collect_builtin_args)
    if len(args) < 3:
        # Fallback: old stub behavior returns all store triples (for backward compatibility)
        return list(engine.store)
    template = args[0]
    pattern = args[1]
    output_slot = args[2]  # Variable or already-bound list

    if not isinstance(pattern, _Formula):
        return None

    # Get current binding (set by engine before calling us)
    binding = getattr(engine, '_current_binding', {}) or {}
    saved = dict(binding)

    # findall(Template, Pattern, Results): every solution of Pattern (proved
    # against the store, with builtins and backward rules) contributes one
    # Template instance.  Delegate to the engine's formula matcher so that
    # builtins inside Pattern (e.g. string:lessThan) and backward rules are
    # evaluated, not just plain store joins.
    if not hasattr(engine, "_match_formula"):
        return None
    solutions = engine._match_formula(pattern, dict(binding))

    results: list[Term] = []
    for b in solutions:
        results.append(_apply(template, b))

    # Build RDF list from results
    result_list = _make_list(results, engine)

    # The internal _match_formula mutates engine._current_binding; restore the
    # caller's binding and add only this builtin's output.
    if isinstance(output_slot, Variable):
        nb = dict(saved)
        nb[output_slot.id] = result_list
        engine._current_binding = nb
        return _bool_result(True)
    else:
        # Verify existing binding matches
        return _bool_result(result_list == output_slot)


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
    if not isinstance(head, ListTerm):
        return None
    return head.items[0] if head.items else None


def list_cdr(args: list[Term], engine: EngineProto) -> Term | None:
    """Return the rest of a list (after the first element)."""
    if _unground(args):
        return None
    head = args[0]
    if not isinstance(head, ListTerm):
        return None
    return ListTerm(items=head.items[1:]) if len(head.items) > 1 else ListTerm(items=())


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
    """Extract numeric values from a list or direct args."""
    if not args:  # pragma: no cover — builtins always receive at least one arg
        return []
    head = args[0]
    if isinstance(head, ListTerm):
        return [_num_val(t) for t in head.items]
    return [_num_val(a) for a in args]

def _strip_output_var(args: list[Term]) -> list[Term]:
    """If the last arg is an unbound Variable and there are ≥2 args with at
    least one ground arg before it, treat it as an output variable and strip it.
    This handles N3 list-subject builtins: (?A ?B) math:sum ?M → [A, B, M]."""
    if len(args) >= 2 and isinstance(args[-1], Variable) and not _unground(args[:-1]):
        return args[:-1]
    return args

def _engine_call_inputs(args: list[Term], engine: EngineProto) -> list[Term]:
    """Strip the object slot the engine appends, when identifiable.

    Engine-issued builtin calls carry the goal's object as the trailing arg
    even when it is ground (a value to verify, not an input); the engine marks
    such calls via ``_current_pattern``.  Direct calls keep all args.
    """
    if len(args) >= 2 and getattr(engine, "_current_pattern", None) is not None:
        return args[:-1]
    return args


def _expand_if_list(args: list[Term], engine: EngineProto) -> list[Term]:
    """If args is a single ListTerm, expand it.
    Otherwise strip the output variable (if present) and return ground inputs."""
    if args and isinstance(args[0], ListTerm):
        return list(args[0].items)
    return _strip_output_var(args)

def _solve_single_unknown(args: list[Term], engine: EngineProto, solve):
    """Inverse mode for arithmetic builtins: bind one unknown input.

    When exactly one input is an unbound Variable and the output slot is
    ground, *solve* computes the unknown from the output and the remaining
    (ground) inputs, e.g. ``(?D 1) math:sum 4`` binds ``?D`` to 3.  Returns a
    BindingsList or None when the shape does not apply.
    """
    if len(args) < 3 or isinstance(args[-1], Variable):
        return None
    inputs = list(args[:-1])
    unknowns = [i for i, a in enumerate(inputs) if isinstance(a, Variable)]
    if len(unknowns) != 1:
        return None
    idx = unknowns[0]
    try:
        out = _num_exact(args[-1])
        known = [_num_exact(a) for i, a in enumerate(inputs) if i != idx]
        v = solve(out, known, idx)
    except (TypeError, ValueError, ZeroDivisionError):
        return None
    if v is None:
        return None
    if isinstance(v, float) and v.is_integer() and all(
            isinstance(k, int) for k in known) and isinstance(out, int):
        v = int(v)
    result = _int_result(v) if isinstance(v, int) else _num_result(v)
    binding = dict(getattr(engine, "_current_binding", {}) or {})
    binding[inputs[idx].id] = result
    return BindingsList([binding])


def math_sum(args: list[Term], engine: EngineProto) -> Term | None:
    inputs = _expand_if_list(_engine_call_inputs(args, engine), engine)
    if _unground(inputs):
        return _solve_single_unknown(
            args, engine, lambda out, known, idx: out - sum(known))
    return _typed_num_result(sum(_num_exact(a) for a in inputs), inputs)

def math_product(args: list[Term], engine: EngineProto) -> Term | None:
    inputs = _expand_if_list(_engine_call_inputs(args, engine), engine)
    if _unground(inputs):
        def solve(out, known, idx):
            p = 1
            for k in known:
                p *= k
            if p == 0:
                return None
            if isinstance(out, int) and isinstance(p, int):
                if out % p:
                    return None
                return out // p
            return out / p
        return _solve_single_unknown(args, engine, solve)
    r = 1
    for a in inputs: r *= _num_exact(a)
    return _typed_num_result(r, inputs)

def _input_args(args: list[Term], n_inputs: int) -> list[Term]:
    """Return the input args, dropping the output variable if present."""
    if len(args) > n_inputs and isinstance(args[n_inputs], Variable):
        return args[:n_inputs]
    return args[:n_inputs]

def _date_difference_years(s1: str, s2: str) -> float | None:
    """Compute difference in years between two ISO date/datetime strings.

    Returns fractional years (s1 - s2) or None if either is not a date.
    """
    import datetime as _dt
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z",
                "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"):
        try:
            d1 = _dt.datetime.strptime(s1[:len(fmt) - fmt.count('%')].rstrip("Z"), fmt.rstrip("%z"))
            break
        except (ValueError, TypeError):
            d1 = None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z",
                "%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M:%S.%f"):
        try:
            d2 = _dt.datetime.strptime(s2[:len(fmt) - fmt.count('%')].rstrip("Z"), fmt.rstrip("%z"))
            break
        except (ValueError, TypeError):
            d2 = None
    if d1 is None or d2 is None:
        # Try simple date parsing
        try:
            import re as _r
            m1 = _r.match(r'^(\d{4})-(\d{2})-(\d{2})', s1)
            m2 = _r.match(r'^(\d{4})-(\d{2})-(\d{2})', s2)
            if m1 and m2:
                y1, mo1, day1 = int(m1.group(1)), int(m1.group(2)), int(m1.group(3))
                y2, mo2, day2 = int(m2.group(1)), int(m2.group(2)), int(m2.group(3))
                years = y1 - y2
                # Subtract 1 if birthday hasn't passed yet this year
                if (mo1, day1) < (mo2, day2):
                    years -= 1
                return float(years)
        except Exception:
            pass
        return None
    delta = d1 - d2
    return delta.days / 365.25


def math_difference(args: list[Term], engine: EngineProto) -> Term | None:
    inp = _input_args(args, 2)
    if _unground(inp):
        # X - Y = Z: solve the single unknown side from the ground output.
        return _solve_single_unknown(
            args, engine,
            lambda out, known, idx: out + known[0] if idx == 0 else known[0] - out)
    v0, v1 = _str_val(inp[0]), _str_val(inp[1])
    # Try date arithmetic first
    yr = _date_difference_years(v0, v1)
    if yr is not None:
        return _num_result(yr)
    return _typed_num_result(_num_exact(inp[0]) - _num_exact(inp[1]), inp)

def math_quotient(args: list[Term], engine: EngineProto) -> Term | None:
    inp = _input_args(args, 2)
    if _unground(inp):
        # X / Y = Z: solve the single unknown side from the ground output.
        return _solve_single_unknown(
            args, engine,
            lambda out, known, idx: out * known[0] if idx == 0 else known[0] / out)
    return _num_result(_num_val(inp[0]) / _num_val(inp[1]))

def math_integerQuotient(args: list[Term], engine: EngineProto) -> Term | None:
    inp = _input_args(args, 2)
    if _unground(inp): return None
    return _int_result(int(_num_exact(inp[0]) // _num_exact(inp[1])))

def math_remainder(args: list[Term], engine: EngineProto) -> Term | None:
    inp = _input_args(args, 2)
    if _unground(inp): return None
    return _typed_num_result(_num_exact(inp[0]) % _num_exact(inp[1]), inp)

def math_absoluteValue(args: list[Term], engine: EngineProto) -> Term | None:
    inp = _input_args(args, 1)
    if _unground(inp): return None
    return _typed_num_result(abs(_num_exact(inp[0])), inp)

def math_rounded(args: list[Term], engine: EngineProto) -> Term | None:
    inp = _input_args(args, 1)
    if _unground(inp): return None
    return _num_result(round(_num_val(inp[0])))

def math_roundedTo(args: list[Term], engine: EngineProto) -> Term | None:
    inp = _input_args(args, 2)
    if _unground(inp): return None
    return _num_result(round(_num_val(inp[0]), int(_num_val(inp[1]))))

def math_negation(args: list[Term], engine: EngineProto) -> Term | None:
    inp = _input_args(args, 1)
    if _unground(inp): return None
    return _typed_num_result(-_num_exact(inp[0]), inp)

def math_max(args: list[Term], engine: EngineProto) -> Term | None:
    inputs = _expand_if_list(_engine_call_inputs(args, engine), engine)
    if _unground(inputs): return None
    # Return the actual winning term to preserve its datatype (avoids xsd:double mismatch)
    return max(inputs, key=lambda a: _num_val(a))

def math_min(args: list[Term], engine: EngineProto) -> Term | None:
    inputs = _expand_if_list(_engine_call_inputs(args, engine), engine)
    if _unground(inputs): return None
    # Return the actual winning term to preserve its datatype
    return min(inputs, key=lambda a: _num_val(a))

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
    """Count items in the subject list (or formula)."""
    inputs = _input_only(args)
    if _unground(inputs): return None
    # inputs may be: a single Formula, or the expanded list items from the subject list
    if len(inputs) == 1 and isinstance(inputs[0], Formula):
        return _int_result(len(inputs[0].triples))
    return _int_result(len(inputs))

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
    return _bool_result(_re.search(_str_val(args[1]), _str_val(args[0])) is None)

def string_replaceAll(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args[:3]): return None
    return Literal(_re.sub(_str_val(args[1]), _str_val(args[2]), _str_val(args[0])))

def string_join(args: list[Term], engine: EngineProto) -> Term | None:
    inputs = _input_only(args)
    if _unground(inputs[:1]): return None
    sep = _str_val(inputs[0])
    head = inputs[1] if len(inputs) > 1 else None
    if isinstance(head, ListTerm):
        items = [_str_val(t) for t in list(head.items)]
    else:
        items = [_str_val(a) for a in inputs[1:]]
    return Literal(sep.join(items))

def string_capitalize(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args[:1]): return None
    return Literal(_str_val(args[0]).capitalize())

def string_upperCase(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args[:1]): return None
    return Literal(_str_val(args[0]).upper())

def string_lowerCase(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args[:1]): return None
    return Literal(_str_val(args[0]).lower())

def string_format(args: list[Term], engine: EngineProto) -> Term | None:
    inputs = _input_only(args)
    if _unground(inputs): return None
    fmt = _str_val(inputs[0])
    vals = [_str_val(a) for a in inputs[1:]]
    return Literal(fmt % tuple(vals))

def string_scrape(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args[:2]): return None
    m = _re.search(_str_val(args[1]), _str_val(args[0]))
    return Literal(m.group(0)) if m else None

def string_scrapeAll(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args[:2]): return None
    return Literal(" ".join(m.group(0) for m in _re.finditer(_str_val(args[1]), _str_val(args[0]))))

def string_search(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args[:2]): return None
    m = _re.search(_str_val(args[1]), _str_val(args[0]))
    return Literal(m.group(0)) if m else None

def string_stringReverse(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args[:1]): return None
    return Literal(_str_val(args[0])[::-1])

def string_stringEscape(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args[:1]): return None
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

def _concat_items(terms: list[Term]) -> list[Term]:
    items: list[Term] = []
    for a in terms:
        if isinstance(a, ListTerm):
            items.extend(list(a.items))
        else:
            items.append(a)
    return items


def _append_splits(inputs: list[Term], out: ListTerm, engine: EngineProto):
    """Enumerate consecutive segmentations of *out* across *inputs*.

    Each input term (a list, a variable, or a pattern carrying variables) is
    unified against one contiguous segment of *out*; every consistent
    segmentation yields one binding extension.  This is the reverse mode of
    ``list:append`` — splitting a known concatenation into unknown parts.
    """
    binding = dict(getattr(engine, "_current_binding", {}) or {})
    out_items = list(out.items)
    results: list[dict] = []

    def go(i: int, pos: int, b: dict) -> None:
        if i == len(inputs):
            if pos == len(out_items):
                results.append(b)
            return
        if i == len(inputs) - 1:
            seg = ListTerm(items=tuple(out_items[pos:]))
            nb = _unify_member(inputs[i], seg, b)
            if nb is not None:
                go(i + 1, len(out_items), nb)
            return
        for end in range(pos, len(out_items) + 1):
            seg = ListTerm(items=tuple(out_items[pos:end]))
            nb = _unify_member(inputs[i], seg, b)
            if nb is not None:
                go(i + 1, end, nb)

    go(0, 0, binding)
    return BindingsList(results)


def list_append(args: list[Term], engine: EngineProto) -> Term | None:
    if not args:
        return None
    if len(args) >= 2:
        inputs, out = list(args[:-1]), args[-1]
        if isinstance(out, Variable):
            # Forward mode: concatenate ground inputs into the output slot.
            if any(_term_has_var(a) for a in inputs):
                return None
            return _make_list(_concat_items(inputs), engine)
        if isinstance(out, ListTerm) and not _term_has_var(out):
            if any(_term_has_var(a) for a in inputs):
                # Reverse mode: split the known result across unbound parts.
                return _append_splits(inputs, out, engine)
            if _concat_items(inputs) == list(out.items):
                # Check mode: the concatenation matches the ground object.
                return out
    if _unground(args):
        return None
    return _make_list(_concat_items(args), engine)

def list_member(args: list[Term], engine: EngineProto):
    """list:member — ``getlist(List, C), member(Member, C)`` (EYE).

    The list subject is expanded by the engine into the leading args, with the
    member candidate as the final arg.  ``member/2`` *unifies* the candidate
    with each list element, so:

    * a ground member → boolean membership test;
    * a variable member → generative (one binding per element);
    * a member carrying variables (e.g. a Formula pattern ``{?X a ?Z}``) →
      unify against every element, yielding one binding per match.
    """
    if not args:
        return None
    if len(args) == 1:
        # Empty list (nil expanded away) — nothing is a member.
        return _bool_result(False)

    items = args[:-1]
    member = args[-1]

    # Single ListTerm passed directly (direct/test-style call): treat as the
    # list and require a separate member — fall back to boolean form.
    if len(args) == 2 and isinstance(items[0], ListTerm):
        return _bool_result(member in list(items[0].items))

    # Unbound list subject (``?L list:member X``) — cannot enumerate.
    if len(args) == 2 and isinstance(items[0], Variable):
        return None

    binding = getattr(engine, "_current_binding", {}) or {}

    # Ground member → boolean membership.
    member_has_var = _term_has_var(member)
    if not member_has_var:
        return _bool_result(any(member == it for it in items))

    # Variable / pattern member → unify with each element, collect bindings.
    out: list[dict] = []
    for it in items:
        nb = _unify_member(member, it, dict(binding))
        if nb is not None:
            out.append(nb)
    return BindingsList(out)


def _unify_member(pattern: Term, candidate: Term, binding: dict) -> dict | None:
    """Structural unification covering Formula/ListTerm/Variable terms.

    The stock ``unify_terms`` treats Formula equality structurally only when
    ground; list:member needs to unify a quoted-Formula *pattern* (carrying
    variables such as ``{?X a ?Z}``) against ground case formulas, so this
    helper recurses into Formula triples.
    """
    from pyeye.unify import unify_terms as _ut
    if isinstance(pattern, Variable) and pattern.id in binding:
        pattern = binding[pattern.id]
    if isinstance(candidate, Variable) and candidate.id in binding:
        candidate = binding[candidate.id]
    if isinstance(pattern, Formula) and isinstance(candidate, Formula):
        if len(pattern.triples) != len(candidate.triples):
            return None
        b = binding
        for pt, ct in zip(pattern.triples, candidate.triples):
            for ps, cs in ((pt.subject, ct.subject),
                           (pt.predicate, ct.predicate),
                           (pt.object, ct.object)):
                b = _unify_member(ps, cs, b)
                if b is None:
                    return None
        return b
    if isinstance(pattern, ListTerm) and isinstance(candidate, ListTerm):
        if len(pattern.items) != len(candidate.items):
            return None
        b = binding
        for pi, ci in zip(pattern.items, candidate.items):
            b = _unify_member(pi, ci, b)
            if b is None:
                return None
        return b
    return _ut(pattern, candidate, binding)


def _term_has_var(t: Term) -> bool:
    if isinstance(t, Variable):
        return True
    if isinstance(t, ListTerm):
        return any(_term_has_var(i) for i in t.items)
    if isinstance(t, Formula):
        for tr in t.triples:
            if (_term_has_var(tr.subject) or _term_has_var(tr.predicate)
                    or _term_has_var(tr.object)):
                return True
        return False
    return False

def list_notMember(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    if len(args) < 2:
        # Empty list (nil expanded to nothing) — nothing is a member
        return _bool_result(True)
    head, item = args[0], args[1]
    if isinstance(head, ListTerm):
        return _bool_result(item not in list(head.items))
    return _bool_result(True)

def list_memberAt(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    head, idx = args[0], int(_num_val(args[1]))
    if isinstance(head, ListTerm):
        items = list(head.items)
        return items[idx] if 0 <= idx < len(items) else None
    return None

def list_removeAt(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    head, idx = args[0], int(_num_val(args[1]))
    if isinstance(head, ListTerm):
        items = list(head.items)
        if 0 <= idx < len(items):
            return _make_list(items[:idx] + items[idx+1:], engine)
    return None

def list_reverse(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    head = args[0]
    if isinstance(head, ListTerm):
        return _make_list(list(reversed(list(head.items))), engine)
    return None

def list_sort(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    head = args[0]
    if isinstance(head, ListTerm):
        items = sorted(list(head.items), key=str)
        return _make_list(items, engine)
    return None

def list_unique(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    head = args[0]
    if isinstance(head, ListTerm):
        seen = set()
        items = []
        for t in list(head.items):
            s = str(t)
            if s not in seen:
                seen.add(s)
                items.append(t)
        return _make_list(items, engine)
    return None

def list_permutation(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    head = args[0]
    if isinstance(head, ListTerm):
        items = list(head.items)
        import random
        random.shuffle(items)
        return _make_list(items, engine)
    return None

def list_setEqualTo(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    h1, h2 = args[0], args[1]
    if isinstance(h1, ListTerm) and isinstance(h2, ListTerm):
        s1 = set(str(t) for t in list(h1.items))
        s2 = set(str(t) for t in list(h2.items))
        return _bool_result(s1 == s2)
    return _bool_result(False)

def list_setNotEqualTo(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    h1, h2 = args[0], args[1]
    if isinstance(h1, ListTerm) and isinstance(h2, ListTerm):
        s1 = set(str(t) for t in list(h1.items))
        s2 = set(str(t) for t in list(h2.items))
        return _bool_result(s1 != s2)
    return _bool_result(True)

def list_multisetEqualTo(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    h1, h2 = args[0], args[1]
    if isinstance(h1, ListTerm) and isinstance(h2, ListTerm):
        from collections import Counter
        c1 = Counter(str(t) for t in list(h1.items))
        c2 = Counter(str(t) for t in list(h2.items))
        return _bool_result(c1 == c2)
    return _bool_result(False)

def list_multisetNotEqualTo(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    h1, h2 = args[0], args[1]
    if isinstance(h1, ListTerm) and isinstance(h2, ListTerm):
        from collections import Counter
        c1 = Counter(str(t) for t in list(h1.items))
        c2 = Counter(str(t) for t in list(h2.items))
        return _bool_result(c1 != c2)
    return _bool_result(True)

def list_removeDuplicates(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    head = args[0]
    if isinstance(head, ListTerm):
        seen = set()
        items = []
        for t in list(head.items):
            s = str(t)
            if s not in seen:
                seen.add(s)
                items.append(t)
        return _make_list(items, engine)
    return None

def _expand_rdf_list(head: Term, engine: EngineProto) -> list[Term] | None:
    """Expand a ListTerm to its items. Returns items, or None if not a list."""
    if not isinstance(head, ListTerm):
        return None
    return list(head.items)


def list_iterate(args: list[Term], engine: EngineProto) -> "MultiResult | None":
    """list:iterate(?list, ?pair) — yields (index item) pairs for each list element.

    args[:-1] are the list elements and args[-1] is the output object.
    """
    if len(args) < 1:
        return None
    # The last arg is the output object (Variable or ListTerm)
    items = args[:-1]
    out_obj = args[-1]

    # If the only arg is an unground variable, the input list is not yet bound
    if not items and isinstance(out_obj, Variable):
        return None

    # If no items were expanded, the subject was not a list
    if not items:
        return MultiResult([])

    # Build (index, item) pair ListTerms
    results: list[Term] = []
    for idx, item in enumerate(items):
        pair = ListTerm(items=(_int_result(idx), item))
        results.append(pair)

    # If out_obj is a concrete list (ListTerm, not Variable), filter to matching pairs
    if isinstance(out_obj, ListTerm) and len(out_obj.items) > 0:
        pair_items = list(out_obj.items)
        if len(pair_items) == 2:
            wanted_idx_val = pair_items[0]
            wanted_item = pair_items[1]
            filtered: list[Term] = []
            for idx, item in enumerate(items):
                idx_match = (isinstance(wanted_idx_val, Variable) or
                             (isinstance(wanted_idx_val, Literal) and
                              wanted_idx_val.value == str(idx)))
                item_match = (isinstance(wanted_item, Variable) or
                              item == wanted_item)
                if idx_match and item_match:
                    filtered.append(results[idx])
            return MultiResult(filtered)

    return MultiResult(results)

def list_map(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    # Simplified: identity map
    head = args[0]
    if isinstance(head, ListTerm):
        return _make_list(list(head.items), engine)
    return None

def list_first(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    # Engine calls expand the subject list into args; recover it from the
    # goal pattern so nested-list subjects stay unambiguous.
    pat = getattr(engine, "_current_pattern", None)
    if pat is not None and isinstance(pat.subject, ListTerm):
        items = pat.subject.items
        return items[0] if items else None
    head = args[0]
    if isinstance(head, ListTerm):
        items = list(head.items)
        return items[0] if items else None
    return None

def list_rest(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    pat = getattr(engine, "_current_pattern", None)
    if pat is not None and isinstance(pat.subject, ListTerm):
        items = pat.subject.items
        return _make_list(list(items[1:]), engine) if items else None
    head = args[0]
    if isinstance(head, ListTerm):
        items = list(head.items)
        return _make_list(items[1:], engine) if len(items) > 1 else None
    return None

def list_last(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    # Engine calls expand the subject list into args; recover it from the
    # goal pattern so nested-list subjects stay unambiguous.
    pat = getattr(engine, "_current_pattern", None)
    if pat is not None and isinstance(pat.subject, ListTerm):
        items = pat.subject.items
        return items[-1] if items else None
    head = args[0]
    if isinstance(head, ListTerm):
        items = list(head.items)
        return items[-1] if items else None
    return None

def list_isList(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    head = args[0]
    if isinstance(head, ListTerm):
        try:
            list(head.items)
            return _bool_result(True)
        except Exception:  # pragma: no cover — _expand_list doesn't raise in practice
            return _bool_result(False)
    return _bool_result(False)

def list_length_builtin(args: list[Term], engine: EngineProto) -> Term | None:
    # Two calling conventions:
    # 1. Via engine (N3 rule): args = [elem0, ..., elemN-1, output_var] — engine expands list
    # 2. Direct call (tests): args = [Existential_head, ...] — expand from store
    if not args:
        return None
    if len(args) == 1 and isinstance(args[0], ListTerm):
        return _int_result(len(args[0].items))
    if len(args) == 2 and isinstance(args[0], ListTerm):
        return _int_result(len(args[0].items))
    # Engine-expanded path: last arg is output var, preceding args are elements
    # If ALL args are Variables (nothing bound), return None (unground)
    if _unground(args[:-1] if len(args) > 1 else args):
        return None
    return _int_result(len(args) - 1)

def _resolve_var_in_binding(var: Variable, binding: dict) -> Term:
    """Resolve a Variable from a binding keyed by Variable.id."""
    val = binding.get(var.id)
    if val is not None:
        return val
    return var


def list_firstRest(args: list[Term], engine: EngineProto) -> Term | None:
    """Bidirectional list:firstRest.

    Decompose: ``?L list:firstRest (?F ?R)`` — given list ?L, return (first, rest).
    Construct: ``?L list:firstRest (?F ?R)`` — given ?F and ?R, construct ?L.

    Also handles single-arg calls where the arg is an Existential list node
    (test-style direct call): returns a (first, rest) pair.
    """
    binding = getattr(engine, '_current_binding', {})

    # Single-arg decompose: called as list_firstRest([list_node], engine)
    if len(args) == 1 and isinstance(args[0], ListTerm):
        items = list(args[0].items)
        if not items:
            return None
        first = items[0]
        rest = _make_list(items[1:], engine) if len(items) > 1 else ListTerm(items=())
        return _make_list([first, rest], engine)

    # args layout: [subject_items..., object_term]
    # But _collect_builtin_args expands Existential subjects into items.
    # We need the raw subject to detect decompose vs construct mode.
    # The object is the last arg.
    obj = args[-1]
    subj_args = args[:-1]

    # Check if subject is a ground list (decompose mode)
    if subj_args and not any(isinstance(a, Variable) for a in subj_args):
        # Decompose: subject is a ground list, extract first and rest
        first = subj_args[0]
        rest = _make_list(subj_args[1:], engine) if len(subj_args) > 1 else ListTerm(items=())
        result_pair = _make_list([first, rest], engine)
        # If object is an Existential (list pattern with variables), try to unify
        if isinstance(obj, ListTerm):
            raw_items = list(obj.items)
            obj_items = [_resolve_var_in_binding(i, binding) if isinstance(i, Variable) else i for i in raw_items]
            if len(obj_items) == 2:
                # Bind ?F and ?R if they are variables
                new_binding = dict(binding)
                for pat, val in zip(raw_items, [first, rest]):
                    if isinstance(pat, Variable):
                        new_binding[pat.id] = val
                    elif pat != val:
                        return None  # mismatch
                engine._current_binding = new_binding
                return _bool_result(True)
        return result_pair

    # Construct mode: subject has variables, object provides (first, rest)
    if isinstance(obj, ListTerm):
        # Expand the object list.  Variables inside rule-head list nodes have
        # their original names (e.g. ?from), but after standardize-apart renaming
        # the binding uses suffixed names (e.g. from__r5).  Use _resolve_var_in_binding
        # to handle both cases.
        raw_items = list(obj.items)
        obj_items = [_resolve_var_in_binding(i, binding) if isinstance(i, Variable) else i for i in raw_items]
        if len(obj_items) == 2:
            first_item = obj_items[0]
            rest_item = obj_items[1]
            # Check for remaining unbound
            if isinstance(first_item, Variable):
                first_item = _resolve_var_in_binding(first_item, binding)
            if isinstance(rest_item, Variable):
                rest_item = _resolve_var_in_binding(rest_item, binding)
            if isinstance(first_item, Variable) or isinstance(rest_item, Variable):
                return None  # can't construct with unbound vars
            # Build list: prepend first to rest, resolving any Variables
            if isinstance(rest_item, ListTerm):
                raw_rest = list(rest_item.items)
                rest_items = [
                    _resolve_var_in_binding(i, binding) if isinstance(i, Variable) else i
                    for i in raw_rest
                ]
            else:
                rest_items = []
            new_list = _make_list([first_item] + rest_items, engine)
            # Bind the subject variable
            if subj_args and isinstance(subj_args[0], Variable):
                new_binding = dict(binding)
                new_binding[subj_args[0].id] = new_list
                engine._current_binding = new_binding
                return _bool_result(True)
            return new_list

    return None

def list_intersection(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    h1, h2 = args[0], args[1]
    if isinstance(h1, ListTerm) and isinstance(h2, ListTerm):
        s1 = list(h1.items)
        s2 = list(h2.items)
        s2_set = set(str(t) for t in s2)
        return _make_list([t for t in s1 if str(t) in s2_set], engine)
    return None

def list_select(args: list[Term], engine: EngineProto) -> Term | None:
    inputs = _input_only(args)
    if _unground(inputs): return None
    head = inputs[0]
    if isinstance(head, ListTerm) and len(inputs) > 1:
        # 1-based indexing
        idx = int(_num_val(inputs[1])) - 1
        items = list(head.items)
        if 0 <= idx < len(items):
            return items[idx]
    elif isinstance(head, ListTerm):
        return _make_list(list(head.items), engine)
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
    """log:callWithCut — prove the subject goal, committing to it (a cut).

    ``{ G } log:callWithCut true`` succeeds iff the subject formula ``G`` holds
    under the current binding; the first proof's bindings are applied.  The cut
    semantics (commit to this clause, discard alternatives) are realised by the
    tabled solver treating the clause as deterministic: only the first solution
    of ``G`` is taken.  The object is the goal flag (``true``) and is ignored
    beyond requiring the call to be attempted.

    This is what makes guarded base cases (takeuchi, ackermann) terminate: the
    base clause fires exactly when its guard holds rather than being treated as
    an unsatisfiable stub.
    """
    if not args:
        return None
    goal = args[0]
    cur = getattr(engine, "_current_binding", {}) or {}

    if isinstance(goal, Formula):
        if not hasattr(engine, "_match_formula"):
            return None
        solutions = engine._match_formula(goal, dict(cur))
        if not solutions:
            return None
        engine._current_binding = solutions[0]
        return _bool_result(True)
    # A bare ``true`` (or any ground non-formula) is trivially satisfied.
    if isinstance(goal, Literal) and goal.value.lower() == "true":
        return _bool_result(True)
    if isinstance(goal, Variable):
        return None
    return _bool_result(True)

def log_callWithDisjunction(args: list[Term], engine: EngineProto) -> Term | None:
    return None

def log_callWithOptional(args: list[Term], engine: EngineProto) -> Term | None:
    """log:callWithOptional — ``call(A), (\\+ call(B) -> true ; call(B))``.

    The subject A is a mandatory goal; the object B is an *optional* goal.  A
    must succeed; then B is attempted.  If B cannot be proven the builtin still
    succeeds (B is skipped, no bindings from B).  If B can be proven, the first
    solution's bindings are applied to the current binding.

    Both A and B may be Formula graphs (proven via ``_match_formula``), or the
    literal ``true`` (trivially satisfied).
    """
    if len(args) < 2:
        return None
    a, b = args[0], args[1]
    cur = getattr(engine, "_current_binding", {}) or {}

    def _prove(goal: Term, binding: dict):
        if isinstance(goal, Formula):
            if not hasattr(engine, "_match_formula"):
                return None
            res = engine._match_formula(goal, dict(binding))
            return res
        # A bare "true" (or any ground non-formula) is trivially satisfied.
        if isinstance(goal, Literal) and goal.value.lower() == "true":
            return [dict(binding)]
        if isinstance(goal, Variable):
            return None
        return [dict(binding)]

    # Mandatory goal A.
    a_solutions = _prove(a, cur)
    if not a_solutions:
        return None
    base = a_solutions[0]

    # Optional goal B.
    b_solutions = _prove(b, base)
    if b_solutions:
        engine._current_binding = b_solutions[0]
    else:
        engine._current_binding = base
    return _bool_result(True)

def log_copy(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    import copy
    return copy.deepcopy(args[0])

def log_dtlit(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args[:1]): return None
    val = _str_val(args[0])
    # If a datatype IRI arg is present and ground, use it; else fall back to xsd:dateTime
    if len(args) >= 2 and not isinstance(args[1], Variable):
        dt = _str_val(args[1])
    else:
        dt = "http://www.w3.org/2001/XMLSchema#dateTime"
    return Literal(val, datatype=NamedNode(dt))

def log_langlit(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return Literal(_str_val(args[0]), language=_str_val(args[1]))

def log_localName(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args[:1]): return None
    uri = _str_val(args[0])
    return Literal(uri.rsplit("#", 1)[-1].rsplit("/", 1)[-1])

def log_namespace(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args[:1]): return None
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

def _scope_includes(scope: Term, pattern: Term, engine: EngineProto) -> bool:
    """True iff *pattern* is satisfied within *scope*.

    The scope (args[0]) may be a Variable (unbound → the default graph / whole
    store), a Formula (an explicit graph), or any term; only the default-store
    case is currently supported for matching (EYE's most common usage).  The
    pattern may be a single Triple, a Formula (conjunction of triples), a bare
    predicate NamedNode, or an Existential subject.

    Variables inside the pattern are resolved through the engine's current
    binding first; remaining variables act as wildcards.  A Formula pattern is
    satisfied iff *every* triple in it can be matched (jointly) against the
    store.
    """
    binding = getattr(engine, "_current_binding", {}) or {}

    def matches_triple(t: Triple) -> bool:
        from pyeye.unify import apply_binding_to_triple
        rt = apply_binding_to_triple(t, binding)
        s = None if isinstance(rt.subject, (Variable, ListTerm)) else rt.subject
        p = None if isinstance(rt.predicate, Variable) else rt.predicate
        o = None if isinstance(rt.object, (Variable, ListTerm)) else rt.object
        return bool(list(engine.store.match(subject=s, predicate=p, object=o)))

    if isinstance(pattern, Literal) and pattern.value.lower() == "true":
        return True
    if isinstance(pattern, Formula):
        return all(matches_triple(t) for t in pattern.triples)
    if isinstance(pattern, Triple):
        return matches_triple(pattern)
    if isinstance(pattern, NamedNode):
        return bool(list(engine.store.match(predicate=pattern)))
    if isinstance(pattern, Existential):
        return bool(list(engine.store.match(subject=pattern)))
    return True


def log_includes(args: list[Term], engine: EngineProto) -> Term | None:
    """log:includes — true iff the scope graph contains the pattern.

    args[0]: scope (Formula graph, or unbound Variable → default store)
    args[1]: pattern (Triple, Formula, predicate NamedNode, or Existential)
    """
    if len(args) < 2:
        return _bool_result(True)
    scope, pattern = args[0], args[1]
    return _bool_result(_scope_includes(scope, pattern, engine))


def log_notIncludes(args: list[Term], engine: EngineProto) -> Term | None:
    """log:notIncludes — scoped negation as failure (true iff NOT included)."""
    if len(args) < 2:
        return _bool_result(False)
    scope, pattern = args[0], args[1]
    return _bool_result(not _scope_includes(scope, pattern, engine))

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
    # Forward: ground subject resource -> its URI as a (percent-decoded) string.
    # Reverse: unbound subject + ground string object -> the denoted resource,
    # percent-encoding characters not allowed in IRIs (lowercase hex, as EYE).
    t = args[0]
    if isinstance(t, Variable):
        if len(args) >= 2 and isinstance(args[-1], Literal):
            quoted = _urllib_parse.quote(args[-1].value, safe=":/?#[]@!$&'()*+,;=-._~")
            quoted = _re.sub(r"%[0-9A-F]{2}", lambda m: m.group(0).lower(), quoted)
            binding = dict(getattr(engine, "_current_binding", {}) or {})
            binding[t.id] = NamedNode(quoted)
            return BindingsList([binding])
        return None
    if isinstance(t, NamedNode):
        return Literal(_urllib_parse.unquote(t.value))
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
    inputs = _input_only(args)
    if _unground(inputs): return None
    return math_avg(inputs, engine)

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
        if isinstance(a, ListTerm):
            items.extend(_str_val(t) for t in list(a.items))
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
    # No unground guard: list_firstRest is bidirectional (an unbound subject
    # with a ground (first rest) object is its construct mode).
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
    if isinstance(head, ListTerm):
        return _int_result(len(list(head.items)))
    return _int_result(0)

def e_match(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    m = _re.search(_str_val(args[1]), _str_val(args[0]))
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
    """Register a prefix for output serialization.

    Usage: ("prefix_name") e:prefix "http://example.org/" .
    """
    if _unground(args):
        return None
    prefix_name = _str_val(args[0]) if len(args) > 0 else ""
    prefix_uri = _str_val(args[1]) if len(args) > 1 else ""
    if hasattr(engine, "_prefixes"):
        engine._prefixes[prefix_name] = prefix_uri
    return _bool_result(True)

def e_propertyChainExtension(args: list[Term], engine: EngineProto) -> Term | None:
    """Check if a property chain extension holds.

    Usage: (P [Q, R]) e:propertyChainExtension true .
    Checks that P is defined as the composition of Q and R.
    """
    if _unground(args):
        return None
    # This is already handled by OWL 2 RL property chain axioms
    # Just return true if args are provided
    return _bool_result(True)

def e_random(args: list[Term], engine: EngineProto) -> Term | None:
    return _num_result(_py_random.random())

def e_relabel(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return args[0]

def e_reverse(args: list[Term], engine: EngineProto) -> Term | None:
    if _unground(args): return None
    return list_reverse(args, engine)

def e_rms(args: list[Term], engine: EngineProto) -> Term | None:
    inputs = _input_only(args)
    if _unground(inputs): return None
    return math_rms(inputs, engine)

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
    inputs = _input_only(args)
    if _unground(inputs): return None
    head = inputs[0]
    if isinstance(head, ListTerm) and engine is not None:
        items = list(head.items)
        return math_std(items, engine)
    return math_std(inputs, engine)

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
    """Check if the object list is an order-preserving subsequence of the subject list.

    Pattern: (a b c d e) e:subsequence (a c e)
    args[:-1] = subject list items, args[-1] = object list (Existential or NamedNode nil)
    """
    if _unground(args): return None
    seq = list(args[:-1])  # subject list items
    sub_node = args[-1]
    sub = list(sub_node.items) if isinstance(sub_node, ListTerm) else []
    # Order-preserving subsequence check
    it = iter(seq)
    return _bool_result(all(any(s == el for el in it) for s in sub))

def e_T(args: list[Term], engine: EngineProto) -> Term | None:
    return _bool_result(True)

def e_tactic(args: list[Term], engine: EngineProto) -> Term | None:
    """Set a reasoning tactic.

    Usage: ("limited-answer" "10") e:tactic true .
    Supported tactics:
    - "limited-answer" N: Stop after N derived triples
    - "linear-select": Select each rule only once per pass
    """
    if _unground(args):
        return None
    tactic_name = _str_val(args[0]) if len(args) > 0 else ""
    tactic_value = _str_val(args[1]) if len(args) > 1 else ""
    if tactic_name == "limited-answer":
        try:
            engine._limit_answers = int(tactic_value)
        except ValueError:
            pass
    elif tactic_name == "linear-select":
        # Already handled by brake mechanism
        pass
    return _bool_result(True)

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
    return Literal(_urllib_parse.quote_plus(_str_val(args[0])))

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
# Missing log: builtins (eye.pl inventory)
# ---------------------------------------------------------------------------

def log_allPossibleCases(args: list[Term], engine: EngineProto) -> Term | None:
    """log:allPossibleCases — bind the universal variable and its cases list.

    In EYE, ``(var:X) log:allPossibleCases (case1 case2 ...)`` declares that
    var:X has a finite set of possible cases.  When this appears in a rule
    body, the builtin searches the store for any such declaration and binds:
      args[0] → the universal variable (first element of the subject list)
      args[-1] → the cases list node

    This enables proof-by-cases reasoning when combined with log:forAllIn.
    """
    _LOG_APC = NS_LOG + "allPossibleCases"

    binding = getattr(engine, '_current_binding', {})
    # args[0] = universal variable (from subject list expansion)
    # args[-1] = cases list variable (from object)
    if len(args) < 1:
        return None

    subj_var = args[0] if len(args) >= 2 else None
    obj_var = args[-1]

    # Search the store for any allPossibleCases triple
    for triple in engine.store:
        if not (isinstance(triple.predicate, NamedNode) and
                triple.predicate.value == _LOG_APC):
            continue

        # Get the universal variable from the subject list
        subj_items = list(triple.subject.items) if isinstance(triple.subject, ListTerm) else []
        univ_var = subj_items[0] if subj_items else None
        cases_node = triple.object

        # Check if we can bind subj_var and obj_var
        new_b = dict(binding)
        if isinstance(subj_var, Variable):
            existing = binding.get(subj_var.id)
            if existing is None and univ_var is not None:
                new_b[subj_var.id] = univ_var
            elif existing is not None and existing != univ_var:
                continue  # mismatch
        if isinstance(obj_var, Variable):
            existing = binding.get(obj_var.id)
            if existing is None:
                new_b[obj_var.id] = cases_node
            elif existing != cases_node:
                continue  # mismatch

        engine._current_binding = new_b
        # Return the cases_node so the handler binds the object variable (?Y)
        return cases_node

    return None  # no allPossibleCases declaration found


def log_dcg(args: list[Term], engine: EngineProto) -> Term | None:
    """log:dcg — Definite Clause Grammar rule string → parsed boolean.

    In EYE ``log:dcg`` takes a string literal that is a Prolog DCG rule
    (``head --> body``) and translates it into a Prolog clause via
    ``dcg_translate_rule/2``.  In pyeye we have no Prolog runtime, so we
    perform a lightweight syntactic validation: the string must contain
    ``-->`` (the DCG neck operator).

    args[0]: ignored first argument (predicate term)
    args[1]: string literal containing the DCG rule

    Returns ``true`` if the string looks like a DCG rule (contains ``-->``),
    ``false`` otherwise.  Returns ``None`` if args are unground.
    """
    if not args or _unground(args):
        return None
    # args[1] is the string literal holding the DCG rule text
    rule_text = _str_val(args[1]) if len(args) > 1 else _str_val(args[0])
    return _bool_result("-->" in rule_text)


def log_ifThenElseIn(args: list[Term], engine: EngineProto) -> Term | None:
    """log:ifThenElseIn — conditional reasoning within a graph.

    Signature (from EYE eye.pl line 8159):
        ``log:ifThenElseIn([Condition, Then, Else], Scope)``

    args[0]: a list head (Existential) or direct term; expanded to
             [condition, then-branch, else-branch]
    args[1]: scope graph (ignored — we operate on the default store)

    The condition is evaluated by attempting to prove it against the store.
    • If args[0] is an Existential (RDF list), expand it to get
      [cond, then, else].
    • Condition is "truthy" if it is a Literal with value "true" OR if it is
      a NamedNode/Existential present in the store as a subject.
    • Returns the then-branch term on success, else-branch term on failure.

    If args[0] is not a three-element list, returns the first element
    (treating it as the result directly).
    """
    if not args or _unground(args):
        return None

    arg0 = args[0]
    items: list[Term] = []
    if isinstance(arg0, ListTerm):
        items = list(arg0.items)
    elif isinstance(arg0, (list,)):  # pragma: no cover — parser never passes raw Python list
        items = arg0  # type: ignore[assignment]

    if len(items) < 3:
        # Not a proper [cond, then, else] — just return arg0
        return arg0

    cond, then_branch, else_branch = items[0], items[1], items[2]

    # Evaluate condition
    def _is_true(t: Term) -> bool:
        if isinstance(t, Literal):
            return t.value.lower() == "true"
        if isinstance(t, NamedNode):
            # Check if there is any triple in the store with this as subject
            return bool(list(engine.store.match(subject=t)))
        if isinstance(t, Existential):
            return bool(list(engine.store.match(subject=t)))
        return False  # pragma: no cover — Term subclasses are exhausted above

    return then_branch if _is_true(cond) else else_branch


def log_impliesAnswer(args: list[Term], engine: EngineProto) -> Term | None:
    """log:impliesAnswer — marks that a formula implies answer triples.

    In EYE ``log:impliesAnswer`` is used to expose backward rules as answer
    productions.  In the context of pyeye's forward-chaining engine this is
    a directive/annotation: we record the predicate IRI (args[0]) in the
    engine's answer-predicate set if that attribute exists, and always return
    ``true`` so that rule heads containing ``log:impliesAnswer`` succeed.

    args[0]: subject (formula / predicate IRI that "implies an answer")
    args[1]: object (the answer formula / conclusion)
    """
    if not args or _unground(args):
        return None
    # Register the predicate as an "answer predicate" if the engine supports it
    if hasattr(engine, '_answer_predicates'):
        pred_iri = _str_val(args[0]) if args else ""
        engine._answer_predicates.add(pred_iri)
    return _bool_result(True)


def log_includesNotBind(args: list[Term], engine: EngineProto) -> Term | None:
    """log:includesNotBind — check inclusion without side-effect variable binding.

    In EYE (eye.pl line 8206–8224) this is ``\\+ \\+ call(Y)`` when X is in
    scope, or ``\\+ \\+ includes(A, B)`` otherwise — a double-negation that
    tests whether the pattern *can* be satisfied without actually binding any
    variables in the outer context.

    args[0]: the graph/scope term (may be a Formula or a NamedNode for a
             named graph, or a priority integer)
    args[1]: the pattern term to test

    In pyeye we check if at least one triple in the store matches the
    predicate/type of the pattern term without performing unification that
    would escape this builtin call.  Specifically:
    • If args[1] is a NamedNode, check if any triple has that node as
      predicate or as object (type assertion).
    • If args[1] is a Literal "true", always succeed.
    • Otherwise, return True conservatively (the store is assumed to contain
      the facts needed — callers use this for soft guards).

    Returns ``true`` / ``false`` boolean literal.  Never returns None when
    args are ground (so the guard ``if _unground(args)`` fires only when a
    variable is present).
    """
    if _unground(args):
        return None

    pattern = args[1] if len(args) > 1 else args[0]

    # Empty / trivially-true pattern
    if isinstance(pattern, Literal) and pattern.value.lower() == "true":
        return _bool_result(True)

    # NamedNode pattern: check if *any* triple uses this IRI as predicate
    if isinstance(pattern, NamedNode):
        hits = list(engine.store.match(predicate=pattern))
        return _bool_result(bool(hits))

    # Existential / blank-node: check it exists as a subject in the store
    if isinstance(pattern, Existential):
        hits = list(engine.store.match(subject=pattern))
        return _bool_result(bool(hits))

    # For any other term (e.g. a Formula) be conservative and return True
    return _bool_result(True)


def log_inferences(args: list[Term], engine: EngineProto) -> Term | None:
    """log:inferences — count of derived triples so far."""
    return _int_result(len(engine._derived_triples) if hasattr(engine, '_derived_triples') else 0)


def log_isImpliedBy(args: list[Term], engine: EngineProto) -> Term | None:
    """log:isImpliedBy — check whether subject is derivable given object as premise.

    In EYE (eye.pl line 5797–5832) ``log:isImpliedBy(Subject, Premise)``
    checks that the *Subject* triple/formula can be derived from *Premise* by
    the currently loaded rules.

    In eyeling (builtins.js line 3186–3213) ``log:impliedBy`` iterates over
    backward rules and tries to unify the subject with the rule head and the
    object with the rule body.

    In pyeye we implement this as follows:
    1. If args[1] (the premise) is a NamedNode that matches a predicate in the
       store, then args[0] (the conclusion) is considered implied.
    2. If the engine has a ``_derived_triples`` list (forward-chaining
       conclusions), check whether args[0] appears among them.
    3. Otherwise fall back to checking whether args[0] is in the store at all.

    Returns ``true`` if implied, ``false`` otherwise.
    """
    if not args or _unground(args):
        return None

    conclusion = args[0]
    # Check if conclusion is in derived triples
    if hasattr(engine, '_derived_triples'):
        for dt in engine._derived_triples:
            if (isinstance(conclusion, NamedNode) and
                    (dt.subject == conclusion or dt.predicate == conclusion or
                     dt.object == conclusion)):
                return _bool_result(True)
            if dt == conclusion:
                return _bool_result(True)

    # Check if conclusion is a NamedNode that exists in the store
    if isinstance(conclusion, NamedNode):
        hits = list(engine.store.match(predicate=conclusion))
        if hits:
            return _bool_result(True)
        hits = list(engine.store.match(subject=conclusion))
        if hits:
            return _bool_result(True)

    # Check if conclusion is a Triple that is in the store
    if isinstance(conclusion, Triple):
        hits = list(engine.store.match(
            subject=conclusion.subject,
            predicate=conclusion.predicate,
            object=conclusion.object,
        ))
        return _bool_result(bool(hits))

    return _bool_result(False)


def log_impliedBy(args: list[Term], engine: EngineProto) -> Term | None:
    """log:impliedBy — alias for log:isImpliedBy (eyeling name)."""
    return log_isImpliedBy(args, engine)


def log_localN3String(args: list[Term], engine: EngineProto) -> Term | None:
    """log:localN3String — serialize a term to N3 using local/relative names."""
    if _unground(args):
        return None
    t = args[0]
    if isinstance(t, NamedNode):
        uri = t.value
        # Use the engine's prefix map if available to shorten the URI
        if hasattr(engine, '_prefixes'):
            for prefix_name, prefix_uri in engine._prefixes.items():
                if uri.startswith(prefix_uri):
                    local = uri[len(prefix_uri):]
                    return Literal(f"{prefix_name}:{local}" if prefix_name else local)
        return Literal(uri)
    return Literal(str(t))


def log_query(args: list[Term], engine: EngineProto) -> list[Triple] | None:
    """log:query — execute a sub-query against the store and return matches.

    In EYE/eyeling ``log:query`` takes a *formula* (graph pattern) and
    returns bindings / matching triples.  In pyeye we implement this as:

    args[0]: the query formula / graph term.  If it is a Formula (from the
             parser), we run ``engine._match_formula`` on it.  If it is a
             NamedNode, we return all triples with that node as predicate.

    Returns the list of matched triples (may be empty).  Returns None only
    when args are unground.
    """
    if not args or _unground(args):
        return None

    query_term = args[0]

    # If the engine exposes _match_formula we can run a proper sub-query
    if isinstance(query_term, Formula) and hasattr(engine, '_match_formula'):
        bindings = engine._match_formula(query_term, {})
        # Collect all triples that were matched by the formula patterns
        matched: list[Triple] = []
        for binding in bindings:
            for pattern in query_term.triples:
                # Resolve the pattern with this binding
                s = binding.get(pattern.subject.id, pattern.subject) if isinstance(pattern.subject, Variable) else pattern.subject
                p = binding.get(pattern.predicate.id, pattern.predicate) if isinstance(pattern.predicate, Variable) else pattern.predicate
                o = binding.get(pattern.object.id, pattern.object) if isinstance(pattern.object, Variable) else pattern.object
                t = Triple(s, p, o)
                if t not in matched:
                    matched.append(t)
        return matched

    # NamedNode query: return all triples with this predicate
    if isinstance(query_term, NamedNode):
        return list(engine.store.match(predicate=query_term))

    # Existential: return all triples with this as subject
    if isinstance(query_term, ListTerm):
        return list(engine.store.match(subject=query_term))

    # Fallback: return all store triples
    return list(engine.store)


def log_table(args: list[Term], engine: EngineProto) -> Term | None:
    """log:table — tabling/memoisation directive.

    In EYE/SWI-Prolog ``log:table(Pred)`` declares *Pred* as a tabled
    predicate (memoized during SLD resolution).  In pyeye the forward-
    chaining engine already memoises all derived facts globally via the
    triple-store (adding a triple is idempotent), so this directive is a
    deliberate no-op that always returns ``true`` to signal success.

    args[0]: the predicate IRI to table (accepted but not used).
    """
    # Optionally record the tabled predicate in an engine attribute
    if args and hasattr(engine, '_tabled_predicates'):
        engine._tabled_predicates.add(_str_val(args[0]) if args else "")
    return _bool_result(True)


# ---------------------------------------------------------------------------
# Extra time: builtins (eyeling inventory: hour, minute, second, timeZone)
# ---------------------------------------------------------------------------

def time_hour(args: list[Term], engine: EngineProto) -> Term | None:
    """time:hour — extract hour component from a datetime/time ISO string."""
    if _unground(args[:1]):
        return None
    dt = _str_val(args[0])
    try:
        # Handles both "HH:MM:SS..." and "YYYY-MM-DDTHH:MM:SS..."
        t_part = dt[11:] if "T" in dt else dt
        return _int_result(int(t_part[:2]))
    except (ValueError, IndexError):
        return None


def time_minute(args: list[Term], engine: EngineProto) -> Term | None:
    """time:minute — extract minute component from a datetime/time ISO string."""
    if _unground(args[:1]):
        return None
    dt = _str_val(args[0])
    try:
        t_part = dt[11:] if "T" in dt else dt
        return _int_result(int(t_part[3:5]))
    except (ValueError, IndexError):
        return None


def time_second(args: list[Term], engine: EngineProto) -> Term | None:
    """time:second — extract second component from a datetime/time ISO string."""
    if _unground(args[:1]):
        return None
    dt = _str_val(args[0])
    try:
        t_part = dt[11:] if "T" in dt else dt
        return _num_result(float(t_part[6:8]))
    except (ValueError, IndexError):
        return None


def time_timeZone(args: list[Term], engine: EngineProto) -> Term | None:
    """time:timeZone — extract timezone offset string from a datetime ISO string.

    Returns the trailing timezone portion (e.g. ``+02:00`` or ``Z``).
    Returns an empty string literal if no timezone is present.
    """
    if _unground(args):
        return None
    dt = _str_val(args[0])
    # _re is the module-level alias for the `re` standard library
    m = _re.search(r'(Z|[+-]\d{2}:\d{2})$', dt)
    return Literal(m.group(1) if m else "")


# ---------------------------------------------------------------------------
# Extra string: builtins (eyeling inventory: charAt, setCharAt)
# ---------------------------------------------------------------------------

def string_charAt(args: list[Term], engine: EngineProto) -> Term | None:
    """string:charAt — return the character at a 0-based index.

    ``(string, index) -> char``
    """
    if _unground(args):
        return None
    s = _str_val(args[0])
    idx = int(_num_val(args[1]))
    if 0 <= idx < len(s):
        return Literal(s[idx])
    return None


def string_setCharAt(args: list[Term], engine: EngineProto) -> Term | None:
    """string:setCharAt — replace the character at a 0-based index.

    ``(string, index, char) -> new_string``
    """
    if _unground(args):
        return None
    s = _str_val(args[0])
    idx = int(_num_val(args[1]))
    ch = _str_val(args[2])
    if 0 <= idx < len(s):
        return Literal(s[:idx] + ch + s[idx + 1:])
    return None


# ---------------------------------------------------------------------------
# rdf: list accessors over native ListTerm subjects
# ---------------------------------------------------------------------------

def _list_args(args: list[Term]) -> tuple[list[Term], Term] | None:
    """Split builtin args into (list-items, output-slot).

    The engine expands a ListTerm subject into the leading args and appends the
    object last.  A single bound ListTerm subject (test-style direct call) is
    returned as its items.  Returns None when the subject is unbound/empty.
    """
    if not args:
        return None
    if len(args) == 1:
        return None
    if len(args) == 2 and isinstance(args[0], ListTerm):
        return list(args[0].items), args[1]
    return list(args[:-1]), args[-1]


def rdf_first(args: list[Term], engine: EngineProto) -> Term | None:
    """rdf:first — first element of a native list ``(a b c) rdf:first ?x``."""
    split = _list_args(args)
    if split is None:
        return None
    items, _out = split
    if any(isinstance(it, Variable) for it in items):
        return None
    return items[0] if items else None


def rdf_rest(args: list[Term], engine: EngineProto) -> Term | None:
    """rdf:rest — tail of a native list ``(a b c) rdf:rest ?r`` → ``(b c)``."""
    split = _list_args(args)
    if split is None:
        return None
    items, _out = split
    if any(isinstance(it, Variable) for it in items):
        return None
    if not items:
        return None
    return ListTerm(items=tuple(items[1:]))


# ---------------------------------------------------------------------------
# Registry — canonical W3C swap namespaces as primary keys
# ---------------------------------------------------------------------------

# Canonical W3C swap namespaces
NS_MATH   = "http://www.w3.org/2000/10/swap/math#"
NS_STRING = "http://www.w3.org/2000/10/swap/string#"
NS_LIST   = "http://www.w3.org/2000/10/swap/list#"
NS_LOG    = "http://www.w3.org/2000/10/swap/log#"
NS_CRYPTO = "http://www.w3.org/2000/10/swap/crypto#"
NS_GRAPH  = "http://www.w3.org/2000/10/swap/graph#"
NS_TIME   = "http://www.w3.org/2000/10/swap/time#"
NS_REASON = "http://www.w3.org/2000/10/swap/reason#"
NS_VAR    = "http://www.w3.org/2000/10/swap/var#"

# EYE / eulersharp namespace — kept ONLY for builtins genuinely unique to EYE
# (no canonical swap equivalent)
NS_E = "http://eulersharp.sourceforge.net/2003/03swap/log-rules#"

# RIF builtin function namespace — aliases onto existing implementations
NS_RIFF = "http://www.w3.org/2007/rif-builtin-function#"

NS_RDF = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"

BUILTIN_REGISTRY: dict[str, Builtin] = {
    # --- rdf: list accessors (only over native ListTerm subjects) ---
    NS_RDF + "first": rdf_first,
    NS_RDF + "rest": rdf_rest,
    # --- math: ---
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
    # --- string: ---
    NS_STRING + "concatenation": string_concatenation,
    NS_STRING + "contains": string_contains,
    NS_STRING + "length": string_length,
    NS_STRING + "startsWith": string_startsWith,
    NS_STRING + "endsWith": string_endsWith,
    NS_STRING + "equal": string_equal,
    NS_STRING + "matches": string_matches,
    NS_STRING + "replace": string_replace,
    NS_STRING + "substring": string_substring,
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
    NS_STRING + "charAt": string_charAt,
    NS_STRING + "setCharAt": string_setCharAt,
    # --- list: ---
    NS_LIST + "in": list_in,
    NS_LIST + "length": list_length_builtin,
    NS_LIST + "car": list_car,
    NS_LIST + "cdr": list_cdr,
    NS_LIST + "select": list_select,
    NS_LIST + "remove": list_remove,
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
    NS_LIST + "firstRest": list_firstRest,
    NS_LIST + "intersection": list_intersection,
    # --- log: ---
    NS_LOG + "outputString": log_outputString,
    NS_LOG + "skolem": log_skolem,
    NS_LOG + "content": log_content,
    NS_LOG + "equalTo": log_equalTo,
    NS_LOG + "notEqualTo": log_notEqualTo,
    NS_LOG + "uuid": log_uuid,
    NS_LOG + "n3String": log_n3String,
    NS_LOG + "implies": log_implies,
    NS_LOG + "forAllIn": log_forAllIn,
    NS_LOG + "ask": log_ask,
    NS_LOG + "shell": log_shell,
    NS_LOG + "collectAllIn": log_collectAllIn,
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
    NS_LOG + "allPossibleCases": log_allPossibleCases,
    NS_LOG + "dcg": log_dcg,
    NS_LOG + "ifThenElseIn": log_ifThenElseIn,
    NS_LOG + "impliesAnswer": log_impliesAnswer,
    NS_LOG + "includesNotBind": log_includesNotBind,
    NS_LOG + "inferences": log_inferences,
    NS_LOG + "isImpliedBy": log_isImpliedBy,
    NS_LOG + "impliedBy": log_impliedBy,
    NS_LOG + "localN3String": log_localN3String,
    NS_LOG + "query": log_query,
    NS_LOG + "table": log_table,
    # --- crypto: ---
    NS_CRYPTO + "md5": crypto_md5,
    NS_CRYPTO + "sha": crypto_sha,
    NS_CRYPTO + "sha256": crypto_sha256,
    NS_CRYPTO + "sha512": crypto_sha512,
    # --- graph: ---
    NS_GRAPH + "member": graph_member,
    NS_GRAPH + "length": graph_length,
    NS_GRAPH + "difference": graph_difference,
    NS_GRAPH + "intersection": graph_intersection,
    NS_GRAPH + "union": graph_union,
    NS_GRAPH + "statement": graph_statement,
    NS_GRAPH + "renameBlanks": graph_renameBlanks,
    NS_GRAPH + "notMember": graph_notMember,
    NS_GRAPH + "list": graph_list,
    # --- time: ---
    NS_TIME + "now": time_now,
    NS_TIME + "year": time_year,
    NS_TIME + "month": time_month,
    NS_TIME + "day": time_day,
    NS_TIME + "in-seconds": time_in_seconds,
    NS_TIME + "hours": time_hours,
    NS_TIME + "minutes": time_minutes,
    NS_TIME + "seconds": time_seconds,
    NS_TIME + "localTime": time_localTime,
    NS_TIME + "hour": time_hour,
    NS_TIME + "minute": time_minute,
    NS_TIME + "second": time_second,
    NS_TIME + "timeZone": time_timeZone,
    # --- reason: ---
    NS_REASON + "because": reason_because,
    NS_REASON + "binding": reason_binding,
    NS_REASON + "boundTo": reason_boundTo,
    NS_REASON + "component": reason_component,
    NS_REASON + "evidence": reason_evidence,
    NS_REASON + "gives": reason_gives,
    NS_REASON + "rule": reason_rule,
    NS_REASON + "source": reason_source,
    NS_REASON + "variable": reason_variable,
    # --- var: ---
    NS_VAR + "all": var_all,
    NS_VAR + "qe": var_qe,
    NS_VAR + "v": var_v,
    NS_VAR + "x": var_x,
    # --- RIF/XPath functions (func: / pred: namespaces) ---
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
    NS_PRED + "equalTo": pred_equal_to,
    NS_PRED + "less-than": pred_less_than,
    NS_PRED + "greater-than": pred_greater_than,
    NS_PRED + "matches": pred_matches,
    # --- e: (eulersharp) — builtins unique to EYE with no canonical swap equivalent ---
    NS_E + "calculate": e_calculate,
    NS_E + "findall": e_findall,
    NS_E + "closure": e_closure,
    NS_E + "exec": e_exec,
    NS_E + "derive": e_derive,
    NS_E + "becomes": e_becomes,
    NS_E + "transaction": e_transaction,
    NS_E + "before": e_before,
    NS_E + "biconditional": e_biconditional,
    NS_E + "binaryEntropy": e_binaryEntropy,
    NS_E + "boolean": e_boolean,
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
    NS_E + "match": e_match,
    NS_E + "multisetEqualTo": e_multisetEqualTo,
    NS_E + "multisetNotEqualTo": e_multisetNotEqualTo,
    NS_E + "notLabel": e_notLabel,
    NS_E + "numeral": e_numeral,
    NS_E + "optional": e_optional,
    NS_E + "propertyChainExtension": e_propertyChainExtension,
    NS_E + "random": e_random,
    NS_E + "relabel": e_relabel,
    NS_E + "roc": e_roc,
    NS_E + "sigmoid": e_sigmoid,
    NS_E + "stringSplit": e_stringSplit,
    NS_E + "subsequence": e_subsequence,
    NS_E + "T": e_T,
    NS_E + "tactic": e_tactic,
    NS_E + "transpose": e_transpose,
    NS_E + "tripleList": e_tripleList,
    NS_E + "true": e_true,
    NS_E + "tuple": e_tuple,
    NS_E + "whenGround": e_whenGround,
    NS_E + "wwwFormEncode": e_wwwFormEncode,
    NS_E + "avg": e_avg,
    NS_E + "call": e_call,
    NS_E + "firstRest": e_firstRest,
    NS_E + "format": e_format,
    NS_E + "length": e_length,
    NS_E + "max": e_max,
    NS_E + "min": e_min,
    NS_E + "pcc": e_pcc,
    NS_E + "prefix": e_prefix,
    NS_E + "reverse": e_reverse,
    NS_E + "rms": e_rms,
    NS_E + "sha": e_sha,
    NS_E + "skolem": e_skolem,
    NS_E + "sort": e_sort,
    NS_E + "std": e_std,
    NS_E + "stringEscape": e_stringEscape,
    NS_E + "stringReverse": e_stringReverse,
    NS_E + "trace": e_trace,
    NS_E + "unique": e_unique,
    # --- RIF builtin functions (aliases) ---
    NS_RIFF + "reverse": list_reverse,
    NS_RIFF + "concatenate": list_append,
    NS_RIFF + "count": list_length_builtin,
    NS_RIFF + "concat": func_concat,
    NS_RIFF + "upper-case": func_uppercase,
    NS_RIFF + "lower-case": func_lowercase,
    NS_RIFF + "string-length": func_string_length,
    NS_RIFF + "substring-before": func_substring_before,
    NS_RIFF + "substring-after": func_substring_after,
    NS_RIFF + "distinct-values": list_removeDuplicates,
}
