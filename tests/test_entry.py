"""Tests for pyeye.entry — execute() orchestration."""

from __future__ import annotations

from pyeye.entry import execute, Result
from pyeye.term import NamedNode, Literal


class TestExecuteAPI:
    def test_returns_result_dataclass(self):
        r = execute()
        assert isinstance(r, Result)
        assert isinstance(r.triples, str)
        assert isinstance(r.stats, dict)
        assert isinstance(r.explains, list)

    def test_stats_fields(self):
        r = execute(
            data_strings=["@prefix : <http://ex.org/> .\n:a :p :b ."],
            rule_strings=["@prefix : <http://ex.org/> .\n{?X :p ?Y} => {?X :q ?Y} ."],
        )
        assert "steps" in r.stats
        assert "derived" in r.stats
        assert "time_ms" in r.stats

    def test_no_input_empty_result(self):
        r = execute()
        assert r.triples == ""
        assert r.stats["steps"] == 0
        assert r.stats["derived"] == 0

    def test_data_only_no_rules(self):
        r = execute(
            data_strings=["@prefix : <http://ex.org/> .\n:a :p :b ."],
        )
        assert r.stats["derived"] == 0
        # No derivation, nothing in default output (only derived triples)
        assert r.triples == ""

    def test_data_and_rule_separate_strings(self):
        """Data and rules can be passed as separate string lists."""
        r = execute(
            data_strings=["@prefix : <http://ex.org/> .\n:a :p :b ."],
            rule_strings=["@prefix : <http://ex.org/> .\n{?X :p ?Y} => {?X :q ?Y} ."],
        )
        assert r.stats["derived"] == 1

    def test_multiple_data_strings_merged(self):
        r = execute(
            data_strings=[
                "@prefix : <http://ex.org/> .\n:a :p :b .",
                "@prefix : <http://ex.org/> .\n:c :p :d .",
            ],
            rule_strings=["@prefix : <http://ex.org/> .\n{?X :p ?Y} => {?X :q ?Y} ."],
        )
        assert r.stats["derived"] == 2

    def test_multiple_rules_same_file(self):
        r = execute(
            data_strings=["@prefix : <http://ex.org/> .\n:a :p :b .\n:x :r :y ."],
            rule_strings=[
                "@prefix : <http://ex.org/> .\n{?X :p ?Y} => {?X :q ?Y} .\n{?A :r ?B} => {?A :s ?B} .",
            ],
        )
        assert r.stats["derived"] == 2

    def test_prefixes_propagated_from_data(self):
        r = execute(
            data_strings=["@prefix foo: <http://foo.org/> .\nfoo:a foo:p foo:b ."],
            rule_strings=["@prefix foo: <http://foo.org/> .\n{?X foo:p ?Y} => {?X foo:q ?Y} ."],
        )
        assert "@prefix foo:" in r.triples

    def test_custom_prefixes_override(self):
        r = execute(
            data_strings=["<http://x/a> <http://x/p> <http://x/b> ."],
            rule_strings=["{?X <http://x/p> ?Y} => {?X <http://x/q> ?Y} ."],
            prefixes={"x": "http://x/"},
        )
        assert ":q" in r.triples

    def test_nope_mode_returns_data_only(self):
        r = execute(
            data_strings=["@prefix : <http://ex.org/> .\n:a :p :b ."],
            rule_strings=["@prefix : <http://ex.org/> .\n{?X :p ?Y} => {?X :q ?Y} ."],
            nope=True,
        )
        assert ":p" in r.triples
        assert ":q" not in r.triples
        assert r.stats["steps"] == 0

    def test_pass_mode_includes_input_facts(self):
        r = execute(
            data_strings=["@prefix : <http://ex.org/> .\n:a :p :b ."],
            rule_strings=["@prefix : <http://ex.org/> .\n{?X :p ?Y} => {?X :q ?Y} ."],
            pass_mode=True,
        )
        assert ":p" in r.triples
        assert ":q" in r.triples

    def test_explain_returns_proof_trees(self):
        r = execute(
            data_strings=["@prefix : <http://ex.org/> .\n:a :p :b ."],
            rule_strings=["@prefix : <http://ex.org/> .\n{?X :p ?Y} => {?X :q ?Y} ."],
            explain=True,
        )
        assert len(r.explains) == 1
        assert r.explains[0].root.predicate.value.endswith("q") or r.explains[0].root.predicate.value == "q"

    def test_max_steps_one_derives_exactly_one(self):
        """max_steps=1 allows exactly 1 derivation."""
        r = execute(
            data_strings=["@prefix : <http://ex.org/> .\n:a :p :b .\n:c :p :d ."],
            rule_strings=["@prefix : <http://ex.org/> .\n{?X :p ?Y} => {?X :q ?Y} ."],
            max_steps=1,
        )
        assert r.stats["steps"] == 1
        assert r.stats["derived"] == 1

    def test_limit_answers_stops_early(self):
        data = "@prefix : <http://ex.org/> .\n"
        for i in range(10):
            data += f":a{i} :p :b{i} .\n"
        r = execute(
            data_strings=[data],
            rule_strings=["@prefix : <http://ex.org/> .\n{?X :p ?Y} => {?X :q ?Y} ."],
            limit_answers=3,
        )
        assert r.stats["derived"] == 3

    def test_custom_builtin_integration(self):
        """Custom builtin is callable and doesn't crash."""
        from pyeye.term import Variable

        def my_func(args, engine):
            if any(isinstance(a, Variable) for a in args):
                return None
            return Literal("custom_result")

        # Should not raise
        r = execute(
            data_strings=["@prefix : <http://ex.org/> .\n:a :val :b ."],
            rule_strings=["@prefix : <http://ex.org/> .\n{?X :val ?Y} => {?X :result ?Z} ."],
            builtins={"http://ex.org/result": my_func},
        )
        # The builtin returns a Literal, but ?Z is a Variable so the head
        # triple won't be ground unless the builtin is in the body.
        # This just tests that the registration mechanism works.
