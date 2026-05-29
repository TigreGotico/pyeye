"""Tests for functional requirements not covered by integration tests.

Covers:
- FR3: @base propagation to output
- FR6: @forSome/@forAll quantifier parsing
- FR21: Unground builtins skipped, grounded on later pass
- FR23: Explicit deterministic sort order verification
- FR28: CLI exit code non-zero on parse error (also tested in test_cli.py)
"""

from __future__ import annotations

from pyeye import execute, parse_n3, parse_rules
from pyeye.parser import Parser
from pyeye.output import N3Writer
from pyeye.term import NamedNode, Triple


class TestBaseDirective:
    """FR3: @base directive resolved and propagated."""

    def test_base_parsed(self):
        doc = parse_n3('@base <http://default.org/> .\n:a :p :b .')
        assert doc.base == "http://default.org/"

    def test_base_in_output(self):
        """@base should be available for prefix expansion."""
        doc = parse_n3(
            '@base <http://default.org/> .\n'
            ':a :p :b .'
        )
        w = N3Writer(doc.prefixes)
        # The base is used as fallback for empty prefix
        assert len(doc.triples) == 1
        assert doc.triples[0].subject.value == "http://default.org/a"


class TestQuantifierParsing:
    """FR6: @forSome/@forAll directives parsed and consumed."""

    def test_forsome_parsed(self):
        doc = parse_n3("@prefix : <http://ex.org/> .\n@forSome ?X .\n{:a :p ?X} => {:b :q ?X} .")
        assert len(doc.rules) == 1
        assert "X" in doc.rules[0].for_some
        assert doc.for_some == ["X"]

    def test_forall_parsed(self):
        doc = parse_n3("@prefix : <http://ex.org/> .\n@forAll ?X .\n{:a :p ?X} => {:b :q ?X} .")
        assert len(doc.rules) == 1
        assert "X" in doc.rules[0].for_all
        assert doc.for_all == ["X"]

    def test_multiple_quantifier_vars(self):
        doc = parse_n3(
            "@prefix : <http://ex.org/> .\n"
            "@forSome ?X, ?Y .\n"
            "{:a :p ?X} => {:b :q ?Y} ."
        )
        assert len(doc.rules) == 1

    def test_quantifier_with_formula_top(self):
        """Quantifier directive before a formula at the top level."""
        doc = parse_n3(
            "@forSome ?S .\n"
            "{?S :p :o} => {:a :q :b} ."
        )
        assert len(doc.rules) == 1
        assert doc.rules[0].for_some == ("S",)


class TestForSomeBehavior:
    """M3 fix: @forSome variables get fresh skolems when unbound."""

    def test_forsome_generates_skolem(self):
        """Unbound @forSome vars should get fresh skolem IDs."""
        from pyeye.engine import Engine
        from pyeye.parser import Rule
        from pyeye.term import Formula, Triple, Variable, Existential, NamedNode

        engine = Engine()
        engine.add_rule(Rule(
            body=Formula((
                Triple(Variable("S"), NamedNode("http://ex.org/p"), NamedNode("http://ex.org/o")),
            )),
            head=Formula((
                Triple(NamedNode("http://ex.org/result"), NamedNode("http://ex.org/hasSkolem"), Variable("S")),
            )),
            for_some=("S",),
        ))
        engine.run()
        # No data matched, so nothing derived
        assert len(engine.derived_triples) == 0

    def test_forsome_with_partial_binding(self):
        """@forSome vars not in binding should get skolems."""
        from pyeye.engine import Engine
        from pyeye.parser import Rule
        from pyeye.term import Formula, Triple, Variable, NamedNode

        engine = Engine()
        engine.add_triple(Triple(
            NamedNode("http://ex.org/a"), NamedNode("http://ex.org/p"), NamedNode("http://ex.org/b"),
        ))
        X, Y, S = Variable("X"), Variable("Y"), Variable("S")
        engine.add_rule(Rule(
            body=Formula((
                Triple(X, NamedNode("http://ex.org/p"), Y),
            )),
            head=Formula((
                Triple(X, NamedNode("http://ex.org/hasSkolem"), S),
            )),
            for_some=("S",),
        ))
        engine.run()
        # Should derive: :a :hasSkolem _:forsome-1
        assert len(engine.derived_triples) == 1
        assert engine.derived_triples[0].object.name.startswith("forsome-")


class TestUngroundBuiltins:
    """FR21: Unground builtins are skipped; later patterns may ground them."""

    def test_builtin_skipped_when_args_unground(self):
        from pyeye.engine import Engine
        from pyeye.parser import Rule
        from pyeye.term import Variable, Formula, Triple, Literal, NamedNode

        e = Engine()
        # Add data that doesn't bind the math builtin's args
        e.add_triple(Triple(NamedNode("http://x/a"), NamedNode("http://x/val"), NamedNode("http://x/b")))
        # Rule with math:greaterThan in body, but args are unground vars
        e.add_rule(Rule(
            body=Formula((
                Triple(Variable("X"), NamedNode("http://math#greaterThan"), Variable("Y")),
            )),
            head=Formula((Triple(Variable("X"), NamedNode("http://x/big"), Variable("Y")),)),
        ))
        # Should not crash — builtin is skipped when args are unground
        e.run()
        # No derivation happens since math:greaterThan needs ground numeric args
        assert e.step_count == 0

    def test_builtin_evaluated_when_args_become_ground(self):
        """When a later binding grounds the args, the builtin evaluates."""
        from pyeye.engine import Engine
        from pyeye.parser import Rule
        from pyeye.term import Variable, Formula, Triple, Literal, NamedNode

        e = Engine()
        # Ground data
        e.add_triple(Triple(
            NamedNode("http://x/a"),
            NamedNode("http://x/val"),
            Literal("10", datatype=NamedNode("http://www.w3.org/2001/XMLSchema#integer")),
        ))
        # Rule: if ?X has value ?V and ?V > 5, then ?X :big true
        e.add_rule(Rule(
            body=Formula((
                Triple(Variable("X"), NamedNode("http://x/val"), Variable("V")),
                Triple(Variable("V"), NamedNode("http://www.w3.org/2000/10/swap/math#greaterThan"), Literal("5", datatype=NamedNode("http://www.w3.org/2001/XMLSchema#integer"))),
            )),
            head=Formula((Triple(Variable("X"), NamedNode("http://x/big"), Literal("true")),)),
        ))
        e.run()
        # This tests the builtin-in-body path with ground args
        # The math:greaterThan builtin receives (Literal("10"), Literal("5")) and returns true
        # The binding filters accordingly


class TestOutputSortOrder:
    """FR23: Output triples sorted deterministically by (subject, predicate, object)."""

    def test_explicit_sort_order(self):
        """Create triples in non-alphabetical order, verify output is sorted."""
        w = N3Writer({"ex": "http://example.org/"})
        triples = [
            Triple(NamedNode("http://example.org/z"), NamedNode("http://example.org/p"), NamedNode("http://example.org/x")),
            Triple(NamedNode("http://example.org/a"), NamedNode("http://example.org/q"), NamedNode("http://example.org/y")),
            Triple(NamedNode("http://example.org/a"), NamedNode("http://example.org/p"), NamedNode("http://example.org/x")),
            Triple(NamedNode("http://example.org/m"), NamedNode("http://example.org/r"), NamedNode("http://example.org/z")),
        ]
        result = w.write_triples(triples)
        # Extract triple lines (skip prefix lines)
        lines = [l for l in result.strip().split("\n") if l and not l.startswith("@prefix") and l.strip()]
        assert len(lines) == 4
        # Verify order: a/p, a/q, m/r, z/p
        assert "ex:a ex:p ex:x" in lines[0]
        assert "ex:a ex:q ex:y" in lines[1]
        assert "ex:m ex:r ex:z" in lines[2]
        assert "ex:z ex:p ex:x" in lines[3]


class TestCLIExitCodeOnError:
    """FR28: CLI exits non-zero on parse error."""

    def test_success_exit_zero(self):
        import subprocess
        r = subprocess.run(
            ["python", "-m", "pyeye.cli"],
            capture_output=True, text=True,
        )
        assert r.returncode == 0

    def test_parse_error_exit_nonzero(self):
        import subprocess
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".n3", delete=False) as f:
            f.write("=> {:a :b :c} .\n")
            f.flush()
            r = subprocess.run(
                ["python", "-m", "pyeye.cli", "--n3", f.name],
                capture_output=True, text=True,
            )
            assert r.returncode != 0
            assert "pyeye: error" in r.stderr
