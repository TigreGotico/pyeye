"""Tests for Phase 2: store retraction and e:becomes full retraction."""

from __future__ import annotations

import pytest

from pyeye.store import TripleStore
from pyeye.builtins import e_becomes, e_transaction
from pyeye.term import NamedNode, Literal, Triple


NN = NamedNode
L = Literal
T = Triple


class TestStoreRetraction:
    """TripleStore retract methods."""

    def test_retract_existing(self):
        store = TripleStore()
        t = T(NN("a"), NN("p"), NN("b"))
        store.add(t)
        assert store.retract(t) is True
        assert not store.contains(t)
        assert len(store) == 0

    def test_retract_nonexistent(self):
        store = TripleStore()
        t = T(NN("a"), NN("p"), NN("b"))
        assert store.retract(t) is False

    def test_retract_updates_index(self):
        store = TripleStore()
        t1 = T(NN("a"), NN("p"), NN("b"))
        t2 = T(NN("c"), NN("p"), NN("d"))
        store.add(t1)
        store.add(t2)
        store.retract(t1)
        # Only t2 should remain, indexed by predicate
        matches = list(store.match(predicate=NN("p")))
        assert len(matches) == 1
        assert matches[0] == t2

    def test_retract_all(self):
        store = TripleStore()
        store.add(T(NN("a"), NN("p"), NN("b")))
        store.add(T(NN("c"), NN("p"), NN("d")))
        store.add(T(NN("e"), NN("q"), NN("f")))
        count = store.retract_all(predicate=NN("p"))
        assert count == 2
        assert len(store) == 1


class TestEBecomesRetraction:
    """e:becomes with full retraction support."""

    def test_becomes_retracts_old(self):
        engine_class = __import__("pyeye.engine", fromlist=["Engine"]).Engine
        engine = engine_class()
        # Add old fact
        engine.add_triple(T(NN("http://x/alice"), NN("http://x/status"), L("active")))
        # Use e:becomes to replace it
        old = T(NN("http://x/alice"), NN("http://x/status"), L("active"))
        new = T(NN("http://x/alice"), NN("http://x/status"), L("inactive"))
        result = e_becomes([old, new], engine)
        assert result is not None
        assert len(result) == 1
        # Old fact should be gone
        assert not engine.store.contains(old)
        # New fact should be present
        assert engine.store.contains(new)

    def test_becomes_with_six_args(self):
        engine_class = __import__("pyeye.engine", fromlist=["Engine"]).Engine
        engine = engine_class()
        # Add old fact
        engine.add_triple(T(NN("http://x/a"), NN("http://x/p"), NN("http://x/b")))
        # Use e:becomes with 6 args (old S,P,O + new S,P,O)
        result = e_becomes([
            NN("http://x/a"), NN("http://x/p"), NN("http://x/b"),
            NN("http://x/a"), NN("http://x/p"), NN("http://x/c"),
        ], engine)
        assert result is not None
        # Old fact should be gone
        assert not engine.store.contains(T(NN("http://x/a"), NN("http://x/p"), NN("http://x/b")))
        # New fact should be present
        assert engine.store.contains(T(NN("http://x/a"), NN("http://x/p"), NN("http://x/c")))


class TestETransaction:
    """e:transaction atomic assertion."""

    def test_transaction_adds_triples(self):
        engine_class = __import__("pyeye.engine", fromlist=["Engine"]).Engine
        engine = engine_class()
        t1 = T(NN("http://x/a"), NN("http://x/p"), NN("http://x/b"))
        t2 = T(NN("http://x/c"), NN("http://x/q"), NN("http://x/d"))
        result = e_transaction([t1, t2], engine)
        assert result is not None
        assert len(result) == 2
        assert engine.store.contains(t1)
        assert engine.store.contains(t2)

    def test_transaction_unground(self):
        from pyeye.term import Variable
        result = e_transaction([Variable("X")], None)
        assert result is None
