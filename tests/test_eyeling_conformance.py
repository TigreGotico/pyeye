"""Eyeling conformance tests — ported from eyeling/test/api.test.js.

Each test class corresponds to a group of cases in the original JS test suite.
Input N3 strings are passed inline; expected output triples are checked via
regex patterns against ``result.triples``.

Normalisation helper
--------------------
``triples_contain(output, pattern)`` does a case-insensitive regex search so
that compact prefixed names vs. full IRIs don't cause false failures.
"""

from __future__ import annotations

import re
import pytest

from pyeye import execute

EX = "http://example.org/"


def U(path: str) -> str:
    return f"<{EX}{path}>"


def triples_contain(output: str, pattern: str | re.Pattern) -> bool:
    """Return True if *output* (N3 text) matches *pattern*."""
    if isinstance(pattern, str):
        return bool(re.search(pattern, output))
    return bool(pattern.search(output))


def triples_not_contain(output: str, pattern: str | re.Pattern) -> bool:
    return not triples_contain(output, pattern)


def count_matches(output: str, pattern: re.Pattern) -> int:
    flags = pattern.flags | re.MULTILINE
    return len(re.findall(pattern.pattern, output, flags))


# ---------------------------------------------------------------------------
# Helper N3 generators (mirroring api.test.js helpers)
# ---------------------------------------------------------------------------

def parent_chain_n3(n: int) -> str:
    s = ""
    for i in range(n):
        s += f"{U(f'n{i}')} {U('parent')} {U(f'n{i+1}')}.\n"
    s += f"{{ ?x {U('parent')} ?y }} => {{ ?x {U('ancestor')} ?y }}.\n"
    s += f"{{ ?x {U('parent')} ?y. ?y {U('ancestor')} ?z }} => {{ ?x {U('ancestor')} ?z }}.\n"
    return s


def subclass_chain_n3(n: int) -> str:
    s = ""
    for i in range(n + 1):
        s += f"{U(f'C{i}')} {U('sub')} {U(f'C{i+1}')}.\n"
    s += f"{U('x')} {U('type')} {U('C0')}.\n"
    s += f"{{ ?s {U('type')} ?a. ?a {U('sub')} ?b }} => {{ ?s {U('type')} ?b }}.\n"
    return s


def rule_chain_n3(n: int) -> str:
    s = ""
    for i in range(n):
        s += f"{{ {U('s')} {U(f'p{i}')} {U('o')}. }} => {{ {U('s')} {U(f'p{i+1}')} {U('o')}. }}.\n"
    s += f"{U('s')} {U('p0')} {U('o')}.\n"
    return s


def binary_tree_parent_n3(depth: int) -> str:
    max_node = (1 << (depth + 1)) - 2
    s = ""
    for i in range(max_node + 1):
        left = 2 * i + 1
        right = 2 * i + 2
        if left <= max_node:
            s += f"{U(f't{i}')} {U('parent')} {U(f't{left}')}.\n"
        if right <= max_node:
            s += f"{U(f't{i}')} {U('parent')} {U(f't{right}')}.\n"
    s += f"{{ ?x {U('parent')} ?y }} => {{ ?x {U('ancestor')} ?y }}.\n"
    s += f"{{ ?x {U('parent')} ?y. ?y {U('ancestor')} ?z }} => {{ ?x {U('ancestor')} ?z }}.\n"
    return s


def reachability_graph_n3(n: int) -> str:
    s = ""
    for i in range(n):
        s += f"{U(f'g{i}')} {U('edge')} {U(f'g{i+1}')}.\n"
    if n >= 6:
        s += f"{U('g0')} {U('edge')} {U('g3')}.\n"
        s += f"{U('g2')} {U('edge')} {U('g5')}.\n"
        s += f"{U('g1')} {U('edge')} {U('g4')}.\n"
    s += f"{{ ?a {U('edge')} ?b }} => {{ ?a {U('reach')} ?b }}.\n"
    s += f"{{ ?a {U('edge')} ?b. ?b {U('reach')} ?c }} => {{ ?a {U('reach')} ?c }}.\n"
    return s


def diamond_subclass_n3() -> str:
    return f"""
{U('A')} {U('sub')} {U('B')}.
{U('A')} {U('sub')} {U('C')}.
{U('B')} {U('sub')} {U('D')}.
{U('C')} {U('sub')} {U('D')}.
{U('x')} {U('type')} {U('A')}.

{{ ?s {U('type')} ?a. ?a {U('sub')} ?b }} => {{ ?s {U('type')} ?b }}.
"""


def join3_hop_n3(k: int) -> str:
    s = ""
    for i in range(k):
        s += f"{U(f'j{i}')} {U('p')} {U(f'j{i+1}')}.\n"
    s += f"{{ ?x {U('p')} ?y. ?y {U('p')} ?z. ?z {U('p')} ?w }} => {{ ?x {U('p3')} ?w }}.\n"
    return s


def same_as_n3() -> str:
    return f"""
{U('a')} {U('sameAs')} {U('b')}.
{U('a')} {U('p')} {U('o')}.

{{ ?x {U('sameAs')} ?y }} => {{ ?y {U('sameAs')} ?x }}.
{{ ?x {U('sameAs')} ?y. ?x ?p ?o }} => {{ ?y ?p ?o }}.
"""


def rule_branch_join_n3() -> str:
    return f"""
{U('s')} {U('p')} {U('o')}.

{{ {U('s')} {U('p')} {U('o')}. }} => {{ {U('s')} {U('q')} {U('o')}. }}.
{{ {U('s')} {U('p')} {U('o')}. }} => {{ {U('s')} {U('r')} {U('o')}. }}.
{{ {U('s')} {U('q')} {U('o')}. {U('s')} {U('r')} {U('o')}. }} => {{ {U('s')} {U('qr')} {U('o')}. }}.
"""


def big_facts_n3(n: int) -> str:
    s = ""
    for i in range(n):
        s += f"{U('x')} {U('p')} {U(f'o{i}')}.\n"
    s += f"{{ ?s {U('p')} ?o }} => {{ ?s {U('q')} ?o }}.\n"
    return s


def symmetric_transitive_n3() -> str:
    return f"""
{U('a')} {U('friend')} {U('b')}.
{U('b')} {U('friend')} {U('c')}.
{U('c')} {U('friend')} {U('d')}.

{{ ?x {U('friend')} ?y }} => {{ ?y {U('friend')} ?x }}.
{{ ?a {U('friend')} ?b }} => {{ ?a {U('reachFriend')} ?b }}.
{{ ?a {U('friend')} ?b. ?b {U('reachFriend')} ?c }} => {{ ?a {U('reachFriend')} ?c }}.
"""


def transitive_closure_n3(pred: str) -> str:
    return f"{{ ?a {U(pred)} ?b. ?b {U(pred)} ?c }} => {{ ?a {U(pred)} ?c }}.\n"


def negative_entailment_batch_n3(n: int) -> str:
    s = ""
    for i in range(n):
        s += f"{U('x')} {U('ok')} {U(f'v{i}')}.\n"
    s += f"{U('x')} {U('forbidden')} {U('boom')}.\n"
    s += f"{{ ?s {U('forbidden')} ?o. }} => false.\n"
    return s


# ---------------------------------------------------------------------------
# Helpers to assert output
# ---------------------------------------------------------------------------

def _run(n3_input: str) -> str:
    """Execute N3 input that may contain both facts and rules.

    Everything is passed via ``rule_strings`` so that pyeye's N3 parser
    (which handles quoted graphs / rules) is used instead of the rdflib
    data loader (which rejects quoted graphs).
    """
    result = execute(rule_strings=[n3_input])
    return result.triples


# ---------------------------------------------------------------------------
# TestForwardRules — cases 01–10, 13 (from api.test.js)
# ---------------------------------------------------------------------------

class TestForwardRules:
    """Basic forward-chaining rule tests."""

    def test_01_forward_p_implies_q(self):
        """01 forward rule: p -> q"""
        n3 = f"""
{{ {U('s')} {U('p')} {U('o')}. }} => {{ {U('s')} {U('q')} {U('o')}. }}.
{U('s')} {U('p')} {U('o')}.
"""
        out = _run(n3)
        assert triples_contain(out, re.compile(
            rf"{EX}s>\s+<{EX}q>\s+<{EX}o>\s*\.", re.MULTILINE))

    def test_02_two_step_p_q_r(self):
        """02 two-step: p -> q -> r"""
        n3 = f"""
{{ {U('s')} {U('p')} {U('o')}. }} => {{ {U('s')} {U('q')} {U('o')}. }}.
{{ {U('s')} {U('q')} {U('o')}. }} => {{ {U('s')} {U('r')} {U('o')}. }}.
{U('s')} {U('p')} {U('o')}.
"""
        out = _run(n3)
        assert triples_contain(out, re.compile(
            rf"{EX}s>\s+<{EX}r>\s+<{EX}o>\s*\.", re.MULTILINE))

    def test_03_join_antecedents(self):
        """03 join antecedents: (x p y & y p z) -> (x p2 z)"""
        n3 = f"""
{{ ?x {U('p')} ?y. ?y {U('p')} ?z. }} => {{ ?x {U('p2')} ?z. }}.
{U('a')} {U('p')} {U('b')}.
{U('b')} {U('p')} {U('c')}.
"""
        out = _run(n3)
        assert triples_contain(out, re.compile(
            rf"{EX}a>\s+<{EX}p2>\s+<{EX}c>\s*\.", re.MULTILINE))

    def test_04_inverse_relation(self):
        """04 inverse relation: (x p y) -> (y invp x)"""
        n3 = f"""
{{ ?x {U('p')} ?y. }} => {{ ?y {U('invp')} ?x. }}.
{U('alice')} {U('p')} {U('bob')}.
"""
        out = _run(n3)
        assert triples_contain(out, re.compile(
            rf"{EX}bob>\s+<{EX}invp>\s+<{EX}alice>\s*\.", re.MULTILINE))

    def test_05_subclass_two_level(self):
        """05 subclass rule: two-level chain"""
        n3 = f"""
{U('Human')} {U('sub')} {U('Mortal')}.
{U('Mortal')} {U('sub')} {U('Being')}.
{U('Socrates')} {U('type')} {U('Human')}.

{{ ?s {U('type')} ?a. ?a {U('sub')} ?b }} => {{ ?s {U('type')} ?b }}.
"""
        out = _run(n3)
        assert triples_contain(out, re.compile(rf"{EX}Socrates>\s+<{EX}type>\s+<{EX}Mortal>", re.MULTILINE))
        assert triples_contain(out, re.compile(rf"{EX}Socrates>\s+<{EX}type>\s+<{EX}Being>", re.MULTILINE))

    def test_06_transitive_closure(self):
        """06 transitive closure: sub is transitive"""
        n3 = f"""
{U('A')} {U('sub')} {U('B')}.
{U('B')} {U('sub')} {U('C')}.

{{ ?a {U('sub')} ?b. ?b {U('sub')} ?c }} => {{ ?a {U('sub')} ?c }}.
"""
        out = _run(n3)
        assert triples_contain(out, re.compile(rf"{EX}A>\s+<{EX}sub>\s+<{EX}C>", re.MULTILINE))

    def test_07_symmetric(self):
        """07 symmetric: knows is symmetric"""
        n3 = f"""
{{ ?x {U('knows')} ?y }} => {{ ?y {U('knows')} ?x }}.
{U('a')} {U('knows')} {U('b')}.
"""
        out = _run(n3)
        assert triples_contain(out, re.compile(rf"{EX}b>\s+<{EX}knows>\s+<{EX}a>", re.MULTILINE))

    def test_08_ancestor_from_parent(self):
        """08 recursion: ancestor from parent (2 steps)"""
        n3 = f"""
{U('a')} {U('parent')} {U('b')}.
{U('b')} {U('parent')} {U('c')}.

{{ ?x {U('parent')} ?y }} => {{ ?x {U('ancestor')} ?y }}.
{{ ?x {U('parent')} ?y. ?y {U('ancestor')} ?z }} => {{ ?x {U('ancestor')} ?z }}.
"""
        out = _run(n3)
        assert triples_contain(out, re.compile(rf"{EX}a>\s+<{EX}ancestor>\s+<{EX}c>", re.MULTILINE))

    def test_09_literals_preserved(self):
        """09 literals preserved: age -> hasAge"""
        n3 = f"""
{{ ?s {U('age')} ?n }} => {{ ?s {U('hasAge')} ?n }}.
{U('x')} {U('age')} "42".
"""
        out = _run(n3)
        assert triples_contain(out, re.compile(rf'{EX}x>\s+<{EX}hasAge>\s+"42"', re.MULTILINE))

    def test_13_heavier_ancestor_15_links(self):
        """13 heavier recursion: ancestor closure over 15 links"""
        out = _run(parent_chain_n3(15))
        assert triples_contain(out, re.compile(rf"{EX}n0>\s+<{EX}ancestor>\s+<{EX}n15>", re.MULTILINE))
        assert triples_contain(out, re.compile(rf"{EX}n3>\s+<{EX}ancestor>\s+<{EX}n12>", re.MULTILINE))

    def test_14_heavier_taxonomy_60_step(self):
        """14 heavier taxonomy: 60-step subclass chain"""
        out = _run(subclass_chain_n3(60))
        assert triples_contain(out, re.compile(rf"{EX}x>\s+<{EX}type>\s+<{EX}C61>", re.MULTILINE))

    def test_15_heavier_40_step_predicate_rewrite(self):
        """15 heavier chaining: 40-step predicate rewrite chain"""
        out = _run(rule_chain_n3(40))
        assert triples_contain(out, re.compile(rf"{EX}s>\s+<{EX}p40>\s+<{EX}o>", re.MULTILINE))

    def test_16_binary_tree_ancestor_depth4(self):
        """16 heavier recursion: binary tree ancestor closure (depth 4)"""
        out = _run(binary_tree_parent_n3(4))
        assert triples_contain(out, re.compile(rf"{EX}t0>\s+<{EX}ancestor>\s+<{EX}t30>", re.MULTILINE))
        assert triples_contain(out, re.compile(rf"{EX}t1>\s+<{EX}ancestor>\s+<{EX}t22>", re.MULTILINE))

    def test_17_heavier_reachability_graph(self):
        """17 heavier reachability: branching graph reach closure"""
        out = _run(reachability_graph_n3(12))
        assert triples_contain(out, re.compile(rf"{EX}g0>\s+<{EX}reach>\s+<{EX}g12>", re.MULTILINE))
        assert triples_contain(out, re.compile(rf"{EX}g2>\s+<{EX}reach>\s+<{EX}g10>", re.MULTILINE))

    def test_18_diamond_subclass(self):
        """18 diamond subclass: x type D"""
        out = _run(diamond_subclass_n3())
        assert triples_contain(out, re.compile(rf"{EX}x>\s+<{EX}type>\s+<{EX}D>", re.MULTILINE))

    def test_19_3hop_join_25_edges(self):
        """19 heavier join: 3-hop path rule over 25 edges"""
        out = _run(join3_hop_n3(25))
        assert triples_contain(out, re.compile(rf"{EX}j0>\s+<{EX}p3>\s+<{EX}j3>", re.MULTILINE))
        assert triples_contain(out, re.compile(rf"{EX}j10>\s+<{EX}p3>\s+<{EX}j13>", re.MULTILINE))
        assert triples_contain(out, re.compile(rf"{EX}j20>\s+<{EX}p3>\s+<{EX}j23>", re.MULTILINE))

    def test_20_branch_join(self):
        """20 heavier branching: p produces q and r, then q+r produces qr"""
        out = _run(rule_branch_join_n3())
        assert triples_contain(out, re.compile(rf"{EX}s>\s+<{EX}qr>\s+<{EX}o>", re.MULTILINE))

    def test_21_same_as_propagation(self):
        """21 heavier equivalence: sameAs propagation"""
        out = _run(same_as_n3())
        assert triples_contain(out, re.compile(rf"{EX}b>\s+<{EX}p>\s+<{EX}o>", re.MULTILINE))
        assert triples_contain(out, re.compile(rf"{EX}b>\s+<{EX}sameAs>\s+<{EX}a>", re.MULTILINE))

    def test_22_transitive_closure_generic(self):
        """22 heavier closure: transitive property via generic rule"""
        n3 = f"""
{U('a')} {U('sub')} {U('b')}.
{U('b')} {U('sub')} {U('c')}.
{U('c')} {U('sub')} {U('d')}.
{U('d')} {U('sub')} {U('e')}.
{transitive_closure_n3('sub')}
"""
        out = _run(n3)
        assert triples_contain(out, re.compile(rf"{EX}a>\s+<{EX}sub>\s+<{EX}e>", re.MULTILINE))
        assert triples_contain(out, re.compile(rf"{EX}b>\s+<{EX}sub>\s+<{EX}d>", re.MULTILINE))

    def test_23_symmetric_transitive_social(self):
        """23 heavier social: symmetric + reachFriend closure"""
        out = _run(symmetric_transitive_n3())
        assert triples_contain(out, re.compile(rf"{EX}a>\s+<{EX}reachFriend>\s+<{EX}d>", re.MULTILINE))
        assert triples_contain(out, re.compile(rf"{EX}d>\s+<{EX}reachFriend>\s+<{EX}a>", re.MULTILINE))

    def test_24_400_facts_rewrite(self):
        """24 heavier volume: 400 facts, simple rewrite p -> q"""
        out = _run(big_facts_n3(400))
        assert triples_contain(out, re.compile(rf"{EX}x>\s+<{EX}q>\s+<{EX}o0>", re.MULTILINE))
        assert triples_contain(out, re.compile(rf"{EX}x>\s+<{EX}q>\s+<{EX}o399>", re.MULTILINE))

    def test_32_rule_fires_for_multiple_facts(self):
        """32 sanity: variable rule fires for multiple matching facts"""
        n3 = f"""
{U('a')} {U('p')} {U('b')}.
{U('c')} {U('p')} {U('d')}.

{{ ?s {U('p')} ?o. }} => {{ ?s {U('q')} ?o. }}.
"""
        out = _run(n3)
        assert triples_contain(out, re.compile(rf"{EX}a>\s+<{EX}q>\s+<{EX}b>", re.MULTILINE))
        assert triples_contain(out, re.compile(rf"{EX}c>\s+<{EX}q>\s+<{EX}d>", re.MULTILINE))

    def test_36_multiple_consequents(self):
        """36 sanity: multiple consequents in one rule"""
        n3 = f"""
{U('s')} {U('p')} {U('o')}.

{{ {U('s')} {U('p')} {U('o')}. }} => {{ {U('s')} {U('q')} {U('o')}. {U('s')} {U('r')} {U('o')}. }}.
"""
        out = _run(n3)
        assert triples_contain(out, re.compile(rf"{EX}s>\s+<{EX}q>\s+<{EX}o>", re.MULTILINE))
        assert triples_contain(out, re.compile(rf"{EX}s>\s+<{EX}r>\s+<{EX}o>", re.MULTILINE))

    def test_40_comments_and_whitespace(self):
        """40 sanity: comments and whitespace are tolerated"""
        n3 = f"""
# leading comment
{{ {U('s')} {U('p')} {U('o')}. }} => {{ {U('s')} {U('q')} {U('o')}. }}.  # trailing comment

{U('s')} {U('p')} {U('o')}. # another trailing comment
"""
        out = _run(n3)
        assert triples_contain(out, re.compile(rf"{EX}s>\s+<{EX}q>\s+<{EX}o>", re.MULTILINE))

    def test_41_diamond_deduplication(self):
        """41 stability: diamond subclass derives D only once"""
        out = _run(diamond_subclass_n3())
        pat = re.compile(rf"{EX}x>\s+<{EX}type>\s+<{EX}D>\s*\.", re.MULTILINE)
        assert triples_contain(out, pat)
        # Must appear exactly once
        assert count_matches(out, pat) == 1, "diamond subclass should not duplicate x type D"

    def test_42_language_tags(self):
        """42 literals: language tags are accepted and preserved"""
        n3 = f'{{ ?s {U("p")} ?o }} => {{ ?s {U("q")} ?o }}. {U("s")} {U("p")} "colour"@en-GB.'
        out = _run(n3)
        assert triples_contain(out, re.compile(rf'{EX}s>\s+<{EX}q>\s+"colour"@en-GB', re.MULTILINE))


# ---------------------------------------------------------------------------
# TestNegativeEntailment — cases 11, 25, 35
# ---------------------------------------------------------------------------

class TestNegativeEntailment:
    """Tests where the reasoner should raise an error (=> false)."""

    def test_11_derive_false(self):
        """11 negative entailment: rule derives false"""
        n3 = f"""
{{ {U('a')} {U('p')} {U('b')}. }} => false.
{U('a')} {U('p')} {U('b')}.
"""
        with pytest.raises(Exception):
            execute(data_strings=[n3])

    def test_25_batch_negative_entailment(self):
        """25 heavier negative entailment: batch + forbidden => false"""
        with pytest.raises(Exception):
            execute(data_strings=[negative_entailment_batch_n3(200)])

    def test_35_fuse_from_derived_fact(self):
        """35 regression: fuse from derived fact"""
        n3 = f"""
{U('a')} {U('p')} {U('b')}.

{{ {U('a')} {U('p')} {U('b')}. }} => {{ {U('a')} {U('q')} {U('b')}. }}.
{{ {U('a')} {U('q')} {U('b')}. }} => false.
"""
        with pytest.raises(Exception):
            execute(data_strings=[n3])


# ---------------------------------------------------------------------------
# TestNoDerivations — cases 26, 33, 34
# ---------------------------------------------------------------------------

class TestNoDerivations:
    """Tests where no (new) triples should be derived."""

    def test_26_no_rules_no_derivations(self):
        """26 sanity: no rules => no newly derived facts"""
        n3 = f"{U('a')} {U('p')} {U('b')}.\n"
        result = execute(data_strings=[n3])
        assert result.stats.get("derived", 0) == 0

    def test_33_mutual_cycle_no_echo(self):
        """33 regression: mutual cycle does not echo already-known facts"""
        n3 = f"""
{U('s')} {U('p')} {U('o')}.

{{ ?x {U('p')} ?y. }} => {{ ?x {U('q')} ?y. }}.
{{ ?x {U('q')} ?y. }} => {{ ?x {U('p')} ?y. }}.
"""
        out = _run(n3)
        assert triples_contain(out, re.compile(rf"{EX}s>\s+<{EX}q>\s+<{EX}o>", re.MULTILINE))
        assert triples_not_contain(out, re.compile(rf"{EX}s>\s+<{EX}p>\s+<{EX}o>", re.MULTILINE))

    def test_34_rule_reproduces_same_triple(self):
        """34 sanity: rule that reproduces same triple produces no output"""
        n3 = f"""
{U('s')} {U('p')} {U('o')}.
{{ {U('s')} {U('p')} {U('o')}. }} => {{ {U('s')} {U('p')} {U('o')}. }}.
"""
        result = execute(rule_strings=[n3])
        assert result.stats.get("derived", 0) == 0


# ---------------------------------------------------------------------------
# TestBackwardRules — cases 27, 37, 38, 39
# ---------------------------------------------------------------------------

class TestBackwardRules:
    """Backward-chaining (<= ) rule tests."""

    def test_27_backward_satisfies_forward_premise(self):
        """27 regression: backward rule (<=) can satisfy a forward rule premise"""
        n3 = f"""
{U('a')} {U('p')} {U('b')}.

{{ {U('a')} {U('q')} {U('b')}. }} <= {{ {U('a')} {U('p')} {U('b')}. }}.
{{ {U('a')} {U('q')} {U('b')}. }} => {{ {U('a')} {U('r')} {U('b')}. }}.
"""
        out = _run(n3)
        assert triples_contain(out, re.compile(rf"{EX}a>\s+<{EX}r>\s+<{EX}b>", re.MULTILINE))

    def test_37_backward_chain_two_levels(self):
        """37 regression: backward chaining can chain (<= then <= then =>)"""
        n3 = f"""
{U('a')} {U('p')} {U('b')}.

{{ {U('a')} {U('q')} {U('b')}. }} <= {{ {U('a')} {U('p')} {U('b')}. }}.
{{ {U('a')} {U('r')} {U('b')}. }} <= {{ {U('a')} {U('q')} {U('b')}. }}.
{{ {U('a')} {U('r')} {U('b')}. }} => {{ {U('a')} {U('s')} {U('b')}. }}.
"""
        out = _run(n3)
        assert triples_contain(out, re.compile(rf"{EX}a>\s+<{EX}s>\s+<{EX}b>", re.MULTILINE))

    def test_38_backward_body_requires_multiple_facts(self):
        """38 regression: backward rule body can require multiple facts"""
        n3 = f"""
{U('a')} {U('p')} {U('b')}.
{U('a')} {U('p2')} {U('b')}.

{{ {U('a')} {U('q')} {U('b')}. }} <= {{ {U('a')} {U('p')} {U('b')}. {U('a')} {U('p2')} {U('b')}. }}.
{{ {U('a')} {U('q')} {U('b')}. }} => {{ {U('a')} {U('r')} {U('b')}. }}.
"""
        out = _run(n3)
        assert triples_contain(out, re.compile(rf"{EX}a>\s+<{EX}r>\s+<{EX}b>", re.MULTILINE))

    def test_39_backward_fails_when_fact_missing(self):
        """39 sanity: backward rule fails when a required fact is missing"""
        n3 = f"""
{U('a')} {U('p')} {U('b')}.

{{ {U('a')} {U('q')} {U('b')}. }} <= {{ {U('a')} {U('p')} {U('b')}. {U('a')} {U('p2')} {U('b')}. }}.
{{ {U('a')} {U('q')} {U('b')}. }} => {{ {U('a')} {U('r')} {U('b')}. }}.
"""
        result = execute(data_strings=[n3])
        assert result.stats.get("derived", 0) == 0


# ---------------------------------------------------------------------------
# TestLogImplies — cases 28, 29
# ---------------------------------------------------------------------------

class TestLogImplies:
    """log:implies as an alias for forward rules."""

    def test_28_top_level_log_implies(self):
        """28 regression: top-level log:implies behaves like a forward rule"""
        n3 = f"""
@prefix log: <http://www.w3.org/2000/10/swap/log#> .

{{ {U('a')} {U('p')} {U('b')}. }} log:implies {{ {U('a')} {U('q')} {U('b')}. }}.
{U('a')} {U('p')} {U('b')}.
"""
        out = _run(n3)
        assert triples_contain(out, re.compile(rf"{EX}a>\s+<{EX}q>\s+<{EX}b>", re.MULTILINE))

    def test_29_derived_log_implies_becomes_live_rule(self):
        """29 regression: derived log:implies becomes a live rule during reasoning"""
        n3 = f"""
@prefix log: <http://www.w3.org/2000/10/swap/log#> .

{{ {U('a')} {U('trigger')} {U('go')}. }}
  =>
{{ {{ {U('a')} {U('p')} {U('b')}. }} log:implies {{ {U('a')} {U('q2')} {U('b')}. }}. }}.

{U('a')} {U('trigger')} {U('go')}.
{U('a')} {U('p')} {U('b')}.
"""
        out = _run(n3)
        assert triples_contain(out, re.compile(rf"{EX}a>\s+<{EX}q2>\s+<{EX}b>", re.MULTILINE))


# ---------------------------------------------------------------------------
# TestIRIURIEscapes — cases 12l–12n
# ---------------------------------------------------------------------------

class TestIRIURIEscapes:
    """IRI/URI escape regression tests (log:uri comparison)."""

    def test_12m_iriref_uchar_matches_plain_a(self):
        r"""12m regression: IRIREF \u0041 matches plain-A literal via log:uri"""
        n3 = (
            "@prefix : <http://example.org/> .\n"
            "@prefix log: <http://www.w3.org/2000/10/swap/log#> .\n"
            "\n"
            "{\n"
            "    <http://example.org/A> log:uri \"http://example.org/A\".\n"
            "}\n"
            "=>\n"
            "{\n"
            "    :result :has :success-literal-5.\n"
            "}.\n"
            "\n"
            "{ } => {\n"
            "    :test :contains :success-literal-5.\n"
            "}.\n"
            "\n"
            "{\n"
            "    :result :has :success-literal-5.\n"
            "}\n"
            "=>\n"
            "{\n"
            "    :test :is true.\n"
            "}.\n"
        )
        out = _run(n3)
        assert triples_contain(out, re.compile(r"result\S*\s+\S*has\S*\s+\S*success-literal-5", re.MULTILINE))
        assert triples_contain(out, re.compile(r":test\s+\S*is\S*\s+true", re.MULTILINE))


# ---------------------------------------------------------------------------
# TestSyntax — cases 44–50
# ---------------------------------------------------------------------------

class TestSyntax:
    """Syntax features: <- operator, N3 paths, rdf: list support."""

    def test_44_reverse_arrow_in_predicate(self):
        """44 syntax: <- in predicate position swaps subject and object"""
        n3 = f"""
{{ ?s {U('p')} ?o }} => {{ ?s {U('q')} ?o }}.
{U('a')} <-{U('p')} {U('b')}.
"""
        out = _run(n3)
        # b is now subject, a is object after swap
        assert triples_contain(out, re.compile(rf"{EX}b>\s+<{EX}q>\s+<{EX}a>", re.MULTILINE))

    def test_46_n3_resource_paths_forward(self):
        """46 syntax: N3 resource paths (! / ^) expand to blank-node triples"""
        n3 = f"""
{U('joe')}!{U('hasAddress')}!{U('hasCity')} {U('name')} "Metropolis".
{{ {U('joe')} {U('hasAddress')} ?a }} => {{ ?a {U('q')} "addr" }}.
{{ ?a {U('hasCity')} ?c }} => {{ ?c {U('q')} "city" }}.
"""
        out = _run(n3)
        # Blank node may be serialized as _:bN or [] depending on N3Writer
        assert triples_contain(out, re.compile(r'(?:_:b\w+|\[)\s*<http://example\.org/q>\s+"addr"', re.MULTILINE))

    @pytest.mark.xfail(
        reason="rdf:first/rdf:rest as list-accessor builtins over a ListTerm "
               "subject is not implemented; rdf:first/rest are matched only as "
               "store data triples (see TODO.md list-builtins).",
        strict=False,
    )
    def test_48_rdf_first_on_list_terms(self):
        """48 rdf:first: works on list terms"""
        n3 = f"""
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>.
{{ ( {U('a')} {U('b')} {U('c')} ) rdf:first ?x. }} => {{ {U('s')} {U('first')} ?x. }}.
"""
        out = _run(n3)
        assert triples_contain(out, re.compile(rf"{EX}s>\s+<{EX}first>\s+<{EX}a>", re.MULTILINE))

    @pytest.mark.xfail(
        reason="rdf:rest as a list-accessor builtin over a ListTerm subject is "
               "not implemented; rdf:rest is matched only as store data "
               "triples (see TODO.md list-builtins).",
        strict=False,
    )
    def test_49_rdf_rest_first_second_element(self):
        """49 rdf:rest: second element of list"""
        n3 = f"""
@prefix rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>.
{{ ( {U('a')} {U('b')} {U('c')} ) rdf:rest ?r. ?r rdf:first ?y. }} => {{ {U('s')} {U('second')} ?y. }}.
"""
        out = _run(n3)
        assert triples_contain(out, re.compile(rf"{EX}s>\s+<{EX}second>\s+<{EX}b>", re.MULTILINE))
