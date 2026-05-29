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


# --------------------------------------------------------------------------- #
# EYE-compatible proof trace (reason: vocabulary)
# --------------------------------------------------------------------------- #

class TestEyeProofVocabulary:
    """``proof=True`` emits the SWAP reason# proof graph."""

    WITCH = """@prefix : <http://ex.org/w#>.
{ ?x a :BURNS. ?x a :WOMAN } => { ?x a :WITCH }.
:GIRL a :WOMAN.
{ ?x a :ISMADEOFWOOD } => { ?x a :BURNS }.
{ ?x a :FLOATS } => { ?x a :ISMADEOFWOOD }.
:DUCK a :FLOATS.
{ ?x a :FLOATS. ?x :SAMEWEIGHT ?y } => { ?y a :FLOATS }.
:DUCK :SAMEWEIGHT :GIRL.
"""
    GOAL = "@prefix : <http://ex.org/w#>.\n{ ?S a :WITCH } => { ?S a :WITCH }.\n"

    def _run(self, tmp_path):
        rules = tmp_path / "witch.n3"
        goal = tmp_path / "goal.n3"
        rules.write_text(self.WITCH)
        goal.write_text(self.GOAL)
        return execute(
            rule_paths=[str(rules)],
            query_paths=[str(goal)],
            proof=True,
            source_urls={str(rules): "http://src/witch.n3",
                         str(goal): "http://src/goal.n3"},
        )

    def test_emits_proof_header(self, tmp_path):
        out = self._run(tmp_path).triples
        assert "skolem:proof a r:Proof, r:Conjunction;" in out
        assert "r:component skolem:lemma1;" in out
        assert "@prefix r: <http://www.w3.org/2000/10/swap/reason#>." in out

    def test_genid_uuid(self, tmp_path):
        out = self._run(tmp_path).triples
        assert "8b98b360-9a70-4845-b52c-c675af60ad01" in out

    def test_inference_and_extraction_lemmas(self, tmp_path):
        out = self._run(tmp_path).triples
        assert "a r:Inference;" in out
        assert "a r:Extraction;" in out
        assert "r:because [ a r:Parsing; r:source <http://src/witch.n3>]." in out

    def test_conclusion_grounded(self, tmp_path):
        out = self._run(tmp_path).triples
        # the query variable ?S must be resolved to :GIRL in the conclusion
        assert ":GIRL a :WITCH." in out
        assert "?S a :WITCH" not in out

    def test_binding_to_girl(self, tmp_path):
        out = self._run(tmp_path).triples
        assert 'r:boundTo [ n3:uri "http://ex.org/w#GIRL"]' in out

    def test_evidence_list(self, tmp_path):
        out = self._run(tmp_path).triples
        assert "r:evidence (" in out
        # the SAMEWEIGHT rule has two body atoms → two evidence lemmas
        assert "r:rule skolem:lemma" in out

    def test_forall_extraction_rule(self, tmp_path):
        out = self._run(tmp_path).triples
        assert "@forAll var:x_0" in out
        assert "} => {" in out


class TestEyeProofSearch:
    """Unit-level checks of the proof DAG builder."""

    def test_build_proof_components(self):
        from pyeye.eye_proof import ProofKB, build_proof
        from pyeye.parser import parse_n3
        data = parse_n3(
            "@prefix : <http://e#>.\n:a :p :b.\n{?x :p ?y} => {?x :q ?y}.",
            source="d.n3")
        q = parse_n3("@prefix : <http://e#>.\n{?x :q ?y} => {?x :q ?y}.",
                     source="q.n3")
        kb = ProofKB(
            facts=[(t, "d.n3") for t in data.triples],
            rules=[(r, "d.n3") for r in data.rules],
        )
        proof = build_proof(kb, [(q.rules[0], "q.n3")])
        assert len(proof.components) == 1
        concl = proof.components[0].conclusion
        assert str(concl.object) == "http://e#b"

    def test_cycle_does_not_hang(self):
        from pyeye.eye_proof import ProofKB, build_proof
        from pyeye.parser import parse_n3
        # mutually recursive rules with no base fact: must terminate (no proof)
        data = parse_n3(
            "@prefix : <http://e#>.\n{?x :p ?y} => {?x :q ?y}.\n"
            "{?x :q ?y} => {?x :p ?y}.",
            source="d.n3")
        q = parse_n3("@prefix : <http://e#>.\n{?x :q ?y} => {?x :q ?y}.",
                     source="q.n3")
        kb = ProofKB(
            facts=[],
            rules=[(r, "d.n3") for r in data.rules],
        )
        proof = build_proof(kb, [(q.rules[0], "q.n3")])
        assert proof.components == []
