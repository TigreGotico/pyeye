"""Unit tests for the semantic corpus comparator (``tests/n3_compare.py``)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tests.n3_compare import compare_semantic  # noqa: E402


def ok(actual: str, expected: str) -> bool:
    passed, _ = compare_semantic(actual, expected)
    return passed


class TestGroundContainment:
    def test_identical(self):
        doc = "@prefix : <http://ex.org/>. :a :p :b."
        assert ok(doc, doc)

    def test_prefix_choice_is_irrelevant(self):
        assert ok("@prefix ex: <http://ex.org/>. ex:a ex:p ex:b.",
                  "@prefix : <http://ex.org/>. :a :p :b.")

    def test_extra_actual_triples_allowed(self):
        assert ok("@prefix : <http://ex.org/>. :a :p :b. :c :p :d.",
                  "@prefix : <http://ex.org/>. :a :p :b.")

    def test_missing_triple_fails(self):
        assert not ok("@prefix : <http://ex.org/>. :a :p :b.",
                      "@prefix : <http://ex.org/>. :a :p :b. :c :p :d.")

    def test_statement_order_is_irrelevant(self):
        assert ok("@prefix : <http://ex.org/>. :c :p :d. :a :p :b.",
                  "@prefix : <http://ex.org/>. :a :p :b. :c :p :d.")

    def test_both_empty(self):
        assert ok("@prefix : <http://ex.org/>.", "")

    def test_expected_empty_actual_not(self):
        assert not ok("@prefix : <http://ex.org/>. :a :p :b.", "")


class TestSyntaxForms:
    def test_predicate_list_semicolons(self):
        assert ok("@prefix : <http://ex.org/>. :a :p :b. :a :q :c.",
                  "@prefix : <http://ex.org/>. :a :p :b; :q :c.")

    def test_object_list_commas(self):
        assert ok("@prefix : <http://ex.org/>. :a :p :b, :c.",
                  "@prefix : <http://ex.org/>. :a :p :b. :a :p :c.")

    def test_list_term(self):
        assert ok("@prefix : <http://ex.org/>. :a :p (:x :y :z).",
                  "@prefix : <http://ex.org/>. :a :p (:x :y :z).")

    def test_list_order_matters(self):
        assert not ok("@prefix : <http://ex.org/>. :a :p (:y :x).",
                      "@prefix : <http://ex.org/>. :a :p (:x :y).")

    def test_formula_triple_order_is_irrelevant(self):
        assert ok("@prefix : <http://ex.org/>. :a :says {:x :p :y. :u :q :v}.",
                  "@prefix : <http://ex.org/>. :a :says {:u :q :v. :x :p :y}.")

    def test_rules_compare(self):
        rule = "@prefix : <http://ex.org/>. {?x :p ?y} => {?x :q ?y}."
        assert ok(rule, rule)


class TestLiterals:
    def test_integer_forms(self):
        assert ok('@prefix : <http://ex.org/>. :a :p 42.',
                  '@prefix x: <http://www.w3.org/2001/XMLSchema#>.'
                  '@prefix : <http://ex.org/>. :a :p "42"^^x:integer.')

    def test_decimal_trailing_zeros(self):
        assert ok('@prefix : <http://ex.org/>. :a :p 2.50.',
                  '@prefix : <http://ex.org/>. :a :p 2.5.')

    def test_plain_string_equals_xsd_string(self):
        assert ok('@prefix : <http://ex.org/>. :a :p "hi".',
                  '@prefix x: <http://www.w3.org/2001/XMLSchema#>.'
                  '@prefix : <http://ex.org/>. :a :p "hi"^^x:string.')

    def test_language_tags_matter(self):
        assert not ok('@prefix : <http://ex.org/>. :a :p "hi"@en.',
                      '@prefix : <http://ex.org/>. :a :p "hi"@fr.')


class TestBlankMapping:
    def test_bnode_label_mismatch_is_fine(self):
        assert ok("@prefix : <http://ex.org/>. _:sk_0 :p :b.",
                  "@prefix : <http://ex.org/>. _:e_1 :p :b.")

    def test_bnode_maps_to_named_term(self):
        assert ok("@prefix : <http://ex.org/>. :a :p :b.",
                  "@prefix : <http://ex.org/>. _:who :p :b.")

    def test_consistent_mapping_required(self):
        # _:x must map to the same term in both triples.
        assert ok("@prefix : <http://ex.org/>. :a :p :b. :b :q :a.",
                  "@prefix : <http://ex.org/>. :a :p _:x. _:x :q :a.")
        assert not ok("@prefix : <http://ex.org/>. :a :p :b. :c :q :a.",
                      "@prefix : <http://ex.org/>. :a :p _:x. _:x :q :a.")

    def test_genid_iri_treated_as_blank(self):
        assert ok(
            "@prefix : <http://ex.org/>. "
            "<https://eyereasoner.github.io/.well-known/genid/abc#t1> :p :b.",
            "@prefix : <http://ex.org/>. _:t :p :b.")

    def test_two_blanks_one_triple(self):
        assert ok("@prefix : <http://ex.org/>. :a :p :b.",
                  "@prefix : <http://ex.org/>. _:s :p _:o.")


class TestFallbackSignal:
    def test_unparseable_raises(self):
        with pytest.raises(Exception):
            compare_semantic("this is { not [ n3", "also } not ] n3 <<<")
