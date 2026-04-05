"""Tests for Phase 2: proof trace output."""

from __future__ import annotations

from pyeye import execute
from pyeye.proof import ProofTree, ProofStep, serialize_n3, serialize_dot, serialize_html
from pyeye.term import NamedNode, Variable, Triple, Formula, Existential
from pyeye.parser import Rule


NN = NamedNode
V = Variable
T = Triple
F = Formula


class TestProofTrees:
    """FR 2e.23-25: Proof trees recorded and returned."""

    def test_explain_returns_trees(self):
        r = execute(
            data_strings=["@prefix : <http://ex.org/> .\n:a :p :b ."],
            rule_strings=["@prefix : <http://ex.org/> .\n{?X :p ?Y} => {?X :q ?Y} ."],
            explain=True,
        )
        assert len(r.explains) == 1
        tree = r.explains[0]
        assert isinstance(tree, ProofTree)
        assert isinstance(tree.root, Triple)

    def test_no_explain_returns_empty(self):
        r = execute(
            data_strings=["@prefix : <http://ex.org/> .\n:a :p :b ."],
            rule_strings=["@prefix : <http://ex.org/> .\n{?X :p ?Y} => {?X :q ?Y} ."],
            explain=False,
        )
        assert r.explains == []

    def test_multiple_derived_multiple_trees(self):
        r = execute(
            data_strings=["@prefix : <http://ex.org/> .\n:a :p :b .\n:c :p :d ."],
            rule_strings=["@prefix : <http://ex.org/> .\n{?X :p ?Y} => {?X :q ?Y} ."],
            explain=True,
        )
        assert len(r.explains) == 2

    def test_tree_has_rule_reference(self):
        r = execute(
            data_strings=["@prefix : <http://ex.org/> .\n:a :p :b ."],
            rule_strings=["@prefix : <http://ex.org/> .\n{?X :p ?Y} => {?X :q ?Y} ."],
            explain=True,
        )
        tree = r.explains[0]
        assert tree.rule is not None
        assert tree.chaining == "forward"

    def test_multi_level_proof_tree(self):
        """M7 fix: Proof trees should have children for multi-step derivations."""
        r = execute(
            data_strings=["@prefix : <http://ex.org/> .\n:a :p :b ."],
            rule_strings=[
                "@prefix : <http://ex.org/> .\n{?X :p ?Y} => {?X :q ?Y} .\n{?X :q ?Y} => {?X :r ?Y} .",
            ],
            explain=True,
        )
        # Should have 2 derived triples: :a :q :b and :a :r :b
        assert len(r.explains) == 2, f"Expected 2 proof trees, got {len(r.explains)}: {r.explains}"

        # Find the proof tree for the second derivation (:a :r :b)
        # This should have the first proof tree as a child
        second_tree = None
        for tree in r.explains:
            if tree.root.predicate.value.endswith("r"):
                second_tree = tree
                break

        assert second_tree is not None
        # The second rule's body matches the first rule's head
        # So the proof tree should have children
        assert len(second_tree.children) >= 1, f"Expected children in second proof tree"
        # The child should be a proof tree for :a :q :b
        child = second_tree.children[0]
        assert isinstance(child, ProofTree)
        assert child.root.predicate.value.endswith("q")


class TestProofSerialization:
    """FR 2e.25-27: Serialize proofs to N3, DOT, and HTML."""

    def test_serialize_n3(self):
        r = execute(
            data_strings=["@prefix : <http://ex.org/> .\n:a :p :b ."],
            rule_strings=["@prefix : <http://ex.org/> .\n{?X :p ?Y} => {?X :q ?Y} ."],
            explain=True,
        )
        n3 = serialize_n3(r.explains)
        assert "proof:conclusion" in n3
        assert "proof:chaining" in n3
        assert "@prefix proof:" in n3

    def test_serialize_dot(self):
        r = execute(
            data_strings=["@prefix : <http://ex.org/> .\n:a :p :b ."],
            rule_strings=["@prefix : <http://ex.org/> .\n{?X :p ?Y} => {?X :q ?Y} ."],
            explain=True,
        )
        dot = serialize_dot(r.explains)
        assert "digraph proof {" in dot
        assert "n0" in dot

    def test_serialize_html(self):
        r = execute(
            data_strings=["@prefix : <http://ex.org/> .\n:a :p :b ."],
            rule_strings=["@prefix : <http://ex.org/> .\n{?X :p ?Y} => {?X :q ?Y} ."],
            explain=True,
        )
        html = serialize_html(r.explains)
        assert "<html>" in html
        assert "<details" in html or '<div class="step">' in html

    def test_empty_proof_serialization(self):
        """Serializing no proofs doesn't crash."""
        n3 = serialize_n3([])
        assert "proof:" in n3

        dot = serialize_dot([])
        assert "digraph proof {" in dot

        html = serialize_html([])
        assert "<html>" in html


class TestProofStepDataclass:
    """FR 2e.23: ProofStep dataclass."""

    def test_create_step(self):
        step = ProofStep(
            conclusion=T(NN("a"), NN("p"), NN("b")),
            premise=[T(V("X"), NN("q"), V("Y"))],
            rule=Rule(body=F((T(V("X"), NN("q"), V("Y")),)), head=F((T(V("X"), NN("r"), V("Y")),))),
            chaining="forward",
            source="test.n3",
        )
        assert str(step.conclusion) == str(T(NN("a"), NN("p"), NN("b")))
        assert step.chaining == "forward"

    def test_step_str(self):
        step = ProofStep(
            conclusion=T(NN("a"), NN("p"), NN("b")),
            premise=None,
            rule=Rule(body=F(()), head=F((T(V("X"), NN("p"), V("Y")),)), source="test.n3"),
            chaining="forward",
        )
        s = str(step)
        assert "forward" in s
        assert "test.n3" in s
