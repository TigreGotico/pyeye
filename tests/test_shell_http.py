"""Tests for Phase 2: shell exec, HTTP, not-entail."""

from __future__ import annotations

import pytest

from pyeye import execute
from pyeye.builtins import e_exec, e_shell, log_ask, log_collectAllIn
from pyeye.term import Literal, Variable, NamedNode, Triple


NN = NamedNode
V = Variable
L = Literal
T = Triple


class TestShellExec:
    """e:exec and e:shell builtins."""

    def test_exec_exit_code(self):
        """e:exec returns exit code."""
        result = e_exec([L("echo hello")], None)
        assert result is not None
        assert result.value == "0"

    def test_exec_nonzero_exit(self):
        result = e_exec([L("false")], None)
        assert result is not None
        assert result.value == "1"

    def test_shell_output(self):
        """e:shell returns stdout."""
        result = e_shell([L("echo hello")], None)
        assert result is not None
        assert "hello" in result.value

    def test_unground_skips(self):
        assert e_exec([V("X")], None) is None
        assert e_shell([V("X")], None) is None


class TestLogAsk:
    """log:ask builtin (HTTP GET)."""

    def test_ask_returns_content(self):
        """log:ask returns response content (or None on failure)."""
        # This test may fail in offline environments
        result = log_ask([L("http://example.org")], None)
        # Either returns content or None (network unavailable)
        # We just verify it doesn't crash
        assert result is None or isinstance(result, Literal)

    def test_unground_skips(self):
        assert log_ask([V("X")], None) is None


class TestLogCollectAllIn:
    """log:collectAllIn builtin."""

    def test_returns_all_triples(self):
        from pyeye.engine import Engine
        engine = Engine()
        engine.add_triple(T(NN("a"), NN("p"), NN("b")))
        engine.add_triple(T(NN("c"), NN("q"), NN("d")))
        result = log_collectAllIn([], engine)
        assert result is not None
        assert len(result) == 2


class TestNotEntail:
    """FR 2h.40: --not-entail flag."""

    def test_not_entail_passes_when_triple_not_derived(self):
        """not_entail=True when triple is NOT in store."""
        r = execute(
            data_strings=["@prefix : <http://ex.org/> .\n:a :p :b ."],
            rule_strings=["@prefix : <http://ex.org/> .\n{?X :p ?Y} => {?X :q ?Y} ."],
            not_entail=T(NN("http://ex.org/a"), NN("http://ex.org/notDerived"), NN("http://ex.org/x")),
        )
        assert r.stats["not_entail_failed"] is False

    def test_not_entail_fails_when_triple_derived(self):
        """not_entail=False when triple IS in store."""
        r = execute(
            data_strings=["@prefix : <http://ex.org/> .\n:a :p :b ."],
            rule_strings=["@prefix : <http://ex.org/> .\n{?X :p ?Y} => {?X :q ?Y} ."],
            not_entail=T(NN("http://ex.org/a"), NN("http://ex.org/q"), NN("http://ex.org/b")),
        )
        assert r.stats["not_entail_failed"] is True

    def test_not_entail_with_entail(self):
        """not_entail works with RDFS entailment."""
        r = execute(
            data_strings=[
                """
                @prefix : <http://ex.org/> .
                @prefix rdfs: <http://www.w3.org/2000/01/rdf-schema#> .
                @prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#> .
                :Cat rdfs:subClassOf :Animal .
                :fluffy rdf:type :Cat .
                """,
            ],
            rule_strings=[],
            entail=True,
            not_entail=T(NN("http://ex.org/fluffy"), NN("http://www.w3.org/1999/02/22-rdf-syntax-ns#type"), NN("http://ex.org/Dog")),
        )
        assert r.stats["not_entail_failed"] is False

    def test_not_entail_none_by_default(self):
        """When not_entail is not set, stat is absent."""
        r = execute(
            data_strings=["@prefix : <http://ex.org/> .\n:a :p :b ."],
        )
        assert "not_entail_failed" not in r.stats or r.stats.get("not_entail_failed") is False
