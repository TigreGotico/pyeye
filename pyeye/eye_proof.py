"""EYE-compatible proof-trace generation (the ``reason:`` / ``r:`` vocabulary).

EYE emits a proof of a query as an RDF graph using the SWAP ``reason#``
vocabulary.  A proof is an ``r:Proof, r:Conjunction`` whose ``r:component``
links to one ``r:Inference`` lemma per answer (the query rule firing).  Each
``r:Inference`` records:

* ``r:gives`` — the conclusion it derives (an N3 formula),
* ``r:evidence`` — an RDF list of sub-lemmas proving the rule body atoms,
* ``r:binding`` — one entry per rule variable (``var:x_N`` → bound value),
* ``r:rule`` — the ``r:Extraction`` lemma for the rule that fired.

Leaf facts are ``r:Extraction`` lemmas justified by ``r:because [ a r:Parsing;
r:source <file> ]``.  Body atoms resolved by a builtin or through a backward
(``<=``) rule are inline ``[ a r:Fact; r:gives {...} ]`` — EYE collapses
Prolog-level resolution into a fact, with no sub-derivation.

Rule variables are numbered ``var#x_N`` in predicate-subject-object
first-appearance order (EYE stores triples predicate-first), walking into
nested formulas and lists.  Head variables left unbound by the body are
skolemised: the conclusion shows a fresh ``?U_N`` universal and the binding
shows ``[ a r:Existential; n3:nodeId "_:sk_N"]``, exactly as EYE does.

Goal solving is delegated to the forward-chaining engine (which evaluates
builtins and backward rules); this module only reconstructs and serializes
the derivation structure of each solution.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from pyeye.term import (
    NamedNode, Literal, Variable, Existential, Formula, Triple, Term,
    ListTerm, TripleTerm, FormulaTerm, Binding,
)
from pyeye.unify import unify_terms, apply_binding
from pyeye.parser import Rule


# Well-known IRIs
SKOLEM_GENID = "8b98b360-9a70-4845-b52c-c675af60ad01"
_VAR_NS = "http://www.w3.org/2000/10/swap/var#"
PASS_SOURCE = "http://eulersharp.sourceforge.net/2003/03swap/pass"
_E_FINDALL = "http://eulersharp.sourceforge.net/2003/03swap/log-rules#findall"
_XSD_INTEGER = "http://www.w3.org/2001/XMLSchema#integer"

# Existentials introduced for unbound head variables (rendered ?U_N in
# conclusions and [ a r:Existential; n3:nodeId "_:sk_N"] in bindings).
_SKOLEM_NAME_RE = re.compile(r"^sk_(\d+)$")


# ---------------------------------------------------------------------------
# Proof DAG nodes
# ---------------------------------------------------------------------------

@dataclass
class Inference:
    """A rule firing: head conclusions derived from evidence under bindings."""
    gives: list[Triple]                # instantiated head triples
    evidence: list["Node"]
    bindings: list[tuple[str, Term]]   # (x_N, boundValue) in var order
    rule: "Extraction"

    @property
    def conclusion(self) -> Triple:
        """The first (often only) conclusion triple."""
        return self.gives[0]


@dataclass
class Extraction:
    """A source fact or rule, justified by parsing its source file."""
    gives: object          # Triple (fact) or Rule (rule)
    source: str            # source file URL


@dataclass
class Fact:
    """A builtin- or backward-rule-produced fact (inline ``[ a r:Fact ]``)."""
    conclusion: Triple


Node = Inference | Extraction | Fact


# ---------------------------------------------------------------------------
# Source-tagged knowledge base
# ---------------------------------------------------------------------------

@dataclass
class ProofKB:
    """Facts and rules tagged with the source file each came from."""
    facts: list[tuple[Triple, str]] = field(default_factory=list)
    rules: list[tuple[Rule, str]] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Rule variable ordering (predicate-subject-object, deep)
# ---------------------------------------------------------------------------

def _walk_vars(t: Term, order: list[Variable], seen: set[int]) -> None:
    if isinstance(t, Variable):
        if t.id not in seen:
            seen.add(t.id)
            order.append(t)
        return
    if isinstance(t, ListTerm):
        for i in t.items:
            _walk_vars(i, order, seen)
        return
    if isinstance(t, Formula):
        for tr in t.triples:
            _walk_triple_vars(tr, order, seen)
        return
    if isinstance(t, TripleTerm):
        _walk_vars(t.predicate, order, seen)
        _walk_vars(t.subject, order, seen)
        _walk_vars(t.object, order, seen)
        return
    if isinstance(t, FormulaTerm):
        _walk_vars(t.functor, order, seen)
        for a in t.args:
            _walk_vars(a, order, seen)


def _walk_triple_vars(tr: Triple, order: list[Variable], seen: set[int]) -> None:
    # EYE stores triples predicate-first: P(S, O).
    _walk_vars(tr.predicate, order, seen)
    _walk_vars(tr.subject, order, seen)
    _walk_vars(tr.object, order, seen)


def _rule_var_order(rule: Rule) -> list[Variable]:
    """Distinct rule variables in EYE's first-appearance order (body, head)."""
    order: list[Variable] = []
    seen: set[int] = set()
    for part in (rule.body, rule.head):
        if isinstance(part, Formula):
            for tr in part.triples:
                _walk_triple_vars(tr, order, seen)
    if rule.head_var is not None:
        _walk_vars(rule.head_var, order, seen)
    return order


def _formula_var_ids(f: Formula) -> set[int]:
    order: list[Variable] = []
    seen: set[int] = set()
    for tr in f.triples:
        _walk_triple_vars(tr, order, seen)
    return seen


def _rename_rule_terms(rule: Rule) -> tuple[Formula, Formula, list[Variable]]:
    """Return (body, head, vars) with fresh variable ids (standardize apart).

    ``vars`` lists the distinct variables in EYE's first-appearance order
    (predicate-subject-object, body then head), so they can be numbered
    ``var#x_0, x_1, …`` deterministically.
    """
    from pyeye.term import _next_var_id
    var_map: dict[int, Variable] = {}

    def cp(t: Term) -> Term:
        if isinstance(t, Variable):
            nv = var_map.get(t.id)
            if nv is None:
                nv = Variable(name=t.name, id=_next_var_id())
                var_map[t.id] = nv
            return nv
        if isinstance(t, ListTerm):
            return ListTerm(items=tuple(cp(i) for i in t.items))
        if isinstance(t, Formula):
            return Formula(triples=tuple(cpt(x) for x in t.triples))
        if isinstance(t, TripleTerm):
            return TripleTerm(cp(t.subject), cp(t.predicate), cp(t.object))
        if isinstance(t, FormulaTerm):
            return FormulaTerm(cp(t.functor), tuple(cp(a) for a in t.args))
        return t

    def cpt(tr: Triple) -> Triple:
        return Triple(cp(tr.subject), cp(tr.predicate), cp(tr.object))

    body = Formula(triples=tuple(cpt(t) for t in rule.body.triples))
    head = Formula(triples=tuple(cpt(t) for t in rule.head.triples))
    order: list[Variable] = []
    seen: set[int] = set()
    for part in (body, head):
        for tr in part.triples:
            _walk_triple_vars(tr, order, seen)
    return body, head, order


def _goal_key(tr: Triple) -> str:
    """A structural key for cycle detection (variables collapsed to '?')."""
    def k(t: Term) -> str:
        if isinstance(t, Variable):
            return "?"
        if isinstance(t, ListTerm):
            return "(" + " ".join(k(i) for i in t.items) + ")"
        if isinstance(t, Formula):
            return "{" + ";".join(
                f"{k(x.subject)} {k(x.predicate)} {k(x.object)}"
                for x in t.triples) + "}"
        return str(t)
    return f"{k(tr.subject)} {k(tr.predicate)} {k(tr.object)}"


def _ground(t: Term, b: Binding) -> Term:
    return apply_binding(t, b)


def _ground_triple(tr: Triple, b: Binding) -> Triple:
    return Triple(_ground(tr.subject, b), _ground(tr.predicate, b),
                  _ground(tr.object, b))


# ---------------------------------------------------------------------------
# Proof construction (engine-backed)
# ---------------------------------------------------------------------------

class ProofBuilder:
    """Reconstructs EYE-shaped derivations of query solutions.

    The engine solves goals (with full builtin/backward-chaining support);
    this class classifies each body atom's justification:

    * matches a source fact            → shared ``Extraction`` lemma
    * predicate is a builtin           → inline ``Fact``
    * derived by a forward (=>) rule   → recursive ``Inference`` lemma
    * anything else (backward rules)   → inline ``Fact``
    """

    MAX_DEPTH = 80

    def __init__(self, kb: ProofKB, engine,
                 sources: list[str] | None = None) -> None:
        self.kb = kb
        self.engine = engine
        self._fact_extractions: dict[tuple, Extraction] = {}
        self._rule_extractions: dict[int, Extraction] = {}
        self._node_cache: dict[str, Node] = {}
        self._fact_sources: dict[str, tuple[Triple, str]] = {}
        for t, src in kb.facts:
            self._fact_sources.setdefault(str(t), (t, src))
        self._sk_counter = 0
        self._steps = 2_000_000
        # Replayed forward-chaining provenance (str(triple) -> firing); lazy.
        self._prov: dict[str, tuple] | None = None
        self._replay_derived: list[Triple] = []
        self._replaying = False
        if sources is None:
            sources = []
            for _t, src in kb.facts:
                if src not in sources:
                    sources.append(src)
            for _r, src in kb.rules:
                if src not in sources:
                    sources.append(src)
        # EYE's e:findall scope term: ((<data docs…>) recursion-level).
        self._scope_term = ListTerm(items=(
            ListTerm(items=tuple(NamedNode(s) for s in sources)),
            Literal("1", datatype=NamedNode(_XSD_INTEGER)),
        ))
        # Data blank nodes are skolemised by EYE into genid#e_<label>_<doc#>.
        self._bnode_docs: dict[str, int] = {}
        doc_no = {s: i + 1 for i, s in enumerate(sources)}
        for t, src in kb.facts:
            n = doc_no.get(src)
            if n is not None:
                for term in (t.subject, t.predicate, t.object):
                    self._collect_bnodes(term, n)

    def _collect_bnodes(self, t: Term, doc: int) -> None:
        if isinstance(t, Existential):
            self._bnode_docs.setdefault(t.name, doc)
        elif isinstance(t, ListTerm):
            for i in t.items:
                self._collect_bnodes(i, doc)
        elif isinstance(t, Formula):
            for tr in t.triples:
                for x in (tr.subject, tr.predicate, tr.object):
                    self._collect_bnodes(x, doc)

    # -- extraction lemma sharing -------------------------------------------

    def _fact_extraction(self, tr: Triple, source: str) -> Extraction:
        key = (str(tr), source)
        ex = self._fact_extractions.get(key)
        if ex is None:
            ex = Extraction(gives=tr, source=source)
            self._fact_extractions[key] = ex
        return ex

    def _rule_extraction(self, rule: Rule, source: str) -> Extraction:
        rid = id(rule)
        ex = self._rule_extractions.get(rid)
        if ex is None:
            ex = Extraction(gives=rule, source=source)
            self._rule_extractions[rid] = ex
        return ex

    # -- query components -----------------------------------------------------

    def build(self, query_rules: list[tuple[Rule, str]]) -> "Proof":
        # The engine's run() deadline may already be near; proof reconstruction
        # is bounded by its own step budget (and the caller's wall clock).
        self.engine._deadline = None
        self._ensure_replay()
        components: list[Inference] = []
        for rule, source in query_rules:
            seen: set[str] = set()
            if not isinstance(rule.head, Formula) or rule.head_var is not None:
                continue
            body, head, order = _rename_rule_terms(rule)
            for descs, b in self._solve_atoms(tuple(body.triples), {}, 0,
                                              frozenset()):
                # Dedup answers by head instantiation before materializing,
                # so alternate derivations of the same answer are dropped
                # (EYE emits one component per distinct answer).
                key = "|".join(str(_ground_triple(t, b)) for t in head.triples)
                if key in seen:
                    continue
                seen.add(key)
                desc = ("infer", rule, source, order, body, head, descs)
                components.append(self._materialize(desc, dict(b)))
        return Proof(components=components, bnode_docs=dict(self._bnode_docs))

    # -- SLD search (EYE clause order: facts, then rules, in load order) ------

    def _budget_ok(self) -> bool:
        self._steps -= 1
        return self._steps > 0

    def _solve_atoms(self, atoms: tuple, b: Binding, depth: int,
                     path: frozenset):
        """Yield (descriptors, binding) proving the conjunction left-to-right."""
        if not atoms:
            yield [], b
            return
        first, rest = atoms[0], atoms[1:]
        for desc, nb in self._solve_atom(first, b, depth, path):
            for descs, fb in self._solve_atoms(rest, nb, depth, path):
                yield [desc] + descs, fb

    def _solve_atom(self, atom: Triple, b: Binding, depth: int,
                    path: frozenset):
        """Yield (descriptor, binding) justifications for one body atom.

        Order mirrors EYE's clause order: builtins evaluate in place, then
        source facts in load order, then forward-derived facts in (replayed)
        assertion order, then backward rules via the engine.
        """
        if depth > self.MAX_DEPTH or not self._budget_ok():
            return
        resolved = _ground_triple(atom, b)
        pred = (resolved.predicate.value
                if isinstance(resolved.predicate, NamedNode) else None)

        # Builtin predicate → engine evaluation, inline r:Fact.
        if (pred is not None and pred in self.engine._builtins
                and self.engine._builtin_applies(resolved)):
            try:
                solutions = self.engine._match_patterns_sequential(
                    [atom], dict(b))
            except Exception:
                return
            for nb in solutions:
                yield ("builtin", atom), nb
            return

        # Source facts, in load order.
        for fact, source in self.kb.facts:
            nb = self._unify3(fact, resolved, dict(b))
            if nb is not None:
                yield ("fact", fact, source), nb

        # Forward-rule conclusions, in replayed assertion order.  After the
        # replay, engine-derived stragglers it missed also qualify (their
        # justification falls back to the engine's recorded firing); during
        # the replay only the partial state so far is visible.
        prov = self._prov or {}
        derivations = {} if self._replaying else getattr(
            self.engine, "_derivations", {})
        if resolved.is_ground():
            if str(resolved) in prov or resolved in derivations:
                yield ("derived", resolved), b
        else:
            seen_keys: set[str] = set()
            for dt in self._replay_derived:
                seen_keys.add(str(dt))
                nb = self._unify3(dt, resolved, dict(b))
                if nb is not None:
                    yield ("derived", dt), nb
            for dt in self.engine._derived_triples:
                if dt not in derivations or str(dt) in seen_keys:
                    continue
                nb = self._unify3(dt, resolved, dict(b))
                if nb is not None:
                    yield ("derived", dt), nb

        # Backward (<=) rules resolve through the engine, shown as r:Fact.
        for rule, _src in self.kb.rules:
            if not rule.is_backward or not isinstance(rule.head, Formula):
                continue
            if any(self._unify3(h, resolved, dict(b)) is not None
                   for h in rule.head.triples):
                try:
                    solutions = self.engine._match_patterns_sequential(
                        [atom], dict(b))
                except Exception:
                    return
                for nb in solutions:
                    yield ("engine", atom), nb
                return

    # -- forward-chaining replay (EYE's triple-driven semi-naive order) -------

    def _ensure_replay(self) -> None:
        """Replay forward chaining the way EYE asserts conclusions.

        Triple-driven semi-naive: a FIFO queue seeded with the source facts in
        load order; each dequeued trigger joins into every body position of
        every forward rule, the remaining atoms resolving facts-first then
        derived-in-assertion-order against the state so far.  New conclusions
        assert immediately and queue.  Each conclusion records the firing
        (rule, evidence descriptors, binding) that first produced it — the
        same firing EYE's proof cites.
        """
        if self._prov is not None:
            return
        self._prov = {}
        self._replaying = True
        known: set[str] = {str(f) for f, _ in self.kb.facts}
        rules = []
        for rule, source in self.kb.rules:
            if (rule.is_backward or rule.is_query
                    or rule.head_var is not None
                    or not isinstance(rule.head, Formula)):
                continue
            rules.append((rule, source))
        queue: list[tuple[tuple, Triple]] = [
            (("fact", f, src), f) for f, src in self.kb.facts
        ]
        qi = 0
        while qi < len(queue):
            if not self._budget_ok():
                break
            tdesc, t = queue[qi]
            qi += 1
            for rule, source in rules:
                body, head, order = _rename_rule_terms(rule)
                for i, atom in enumerate(body.triples):
                    ub = self._unify3(atom, t, {})
                    if ub is None:
                        continue
                    for descs, fb in self._replay_conj(body.triples, 0, i,
                                                       tdesc, ub):
                        new_heads = []
                        for ht in head.triples:
                            g = _ground_triple(ht, fb)
                            if g.is_ground() and str(g) not in known:
                                new_heads.append(g)
                        if not new_heads:
                            continue
                        firing = ("infer", rule, source, order, body, head,
                                  descs, dict(fb))
                        for g in new_heads:
                            known.add(str(g))
                            self._replay_derived.append(g)
                            self._prov[str(g)] = firing
                            queue.append((("derived", g), g))
        self._replaying = False

    def _replay_conj(self, atoms: tuple, j: int, skip: int, tdesc: tuple,
                     b: Binding):
        """Solve remaining body atoms around the trigger at *skip*."""
        if j == len(atoms):
            yield [], b
            return
        if j == skip:
            for descs, fb in self._replay_conj(atoms, j + 1, skip, tdesc, b):
                yield [tdesc] + descs, fb
            return
        for desc, nb in self._solve_atom(atoms[j], b, 0, frozenset()):
            for descs, fb in self._replay_conj(atoms, j + 1, skip, tdesc, nb):
                yield [desc] + descs, fb

    # -- materialization (descriptor tree → proof nodes) ----------------------

    def _materialize(self, desc: tuple, nb: Binding) -> Node:
        """Instantiate a justification descriptor under the final binding.

        Mutates *nb* in place: e:findall scopes and unbound rule variables
        are bound here (pre-order), so skolem numbering follows EYE's
        derivation order.
        """
        kind = desc[0]
        if kind == "node":
            return desc[1]
        if kind == "fact":
            return self._fact_extraction(desc[1], desc[2])
        if kind in ("builtin", "engine"):
            return Fact(conclusion=_ground_triple(desc[1], nb))
        if kind == "derived":
            return self._materialize_derived(desc[1])
        _, rule, source, order, body, head, subdescs = desc
        # EYE presents an unbound e:findall scope as ((<data docs…>) 1).
        for t in body.triples:
            if (isinstance(t.predicate, NamedNode)
                    and t.predicate.value == _E_FINDALL):
                subj = _ground(t.subject, nb)
                if isinstance(subj, Variable):
                    nb[subj.id] = self._scope_term
        # Skolemise variables the firing left unbound (in var order), as EYE
        # does for findall-local and head-only variables.
        for v in order:
            if isinstance(_ground(v, nb), Variable):
                nb[v.id] = Existential(f"sk_{self._sk_counter}")
                self._sk_counter += 1
        gives = [_ground_triple(t, nb) for t in head.triples]
        evidence = [self._materialize(d, nb) for d in subdescs]
        bindings = [(f"x_{i}", _ground(v, nb)) for i, v in enumerate(order)]
        node = Inference(gives=gives, evidence=evidence, bindings=bindings,
                         rule=self._rule_extraction(rule, source))
        # Every conclusion of the firing shares this lemma (a multi-head rule
        # firing is cited once per body atom it justifies, as in EYE).
        for g in gives:
            if g.is_ground():
                self._node_cache.setdefault(str(g), node)
        return node

    def _materialize_derived(self, triple: Triple) -> Node:
        """Inference lemma for a forward-derived triple.

        The justifying firing comes from the triple-driven replay (the firing
        that first produced the conclusion, in EYE's assertion order); when
        the replay missed it (timing-sensitive builtins), the engine's
        recorded firing is used instead.
        """
        key = str(triple)
        cached = self._node_cache.get(key)
        if cached is not None:
            return cached
        firing = (self._prov or {}).get(key)
        if firing is not None:
            _, rule, source, order, body, head, descs, fb = firing
            desc = ("infer", rule, source, order, body, head, descs)
            node = self._materialize(desc, dict(fb))
            self._node_cache[key] = node
            return node
        # Fallback: the engine's recorded firing.
        rec = self.engine._derivations.get(triple)
        if rec is None:
            return Fact(conclusion=triple)
        rule, rb = rec
        nb = dict(rb)
        order = _rule_var_order(rule)
        node = Inference(gives=[], evidence=[], bindings=[],
                         rule=self._rule_extraction(rule, rule.source))
        # Pre-cache so a (pathological) self-referential premise terminates.
        self._node_cache[key] = node
        for t in rule.body.triples:
            if (isinstance(t.predicate, NamedNode)
                    and t.predicate.value == _E_FINDALL):
                subj = _ground(t.subject, nb)
                if isinstance(subj, Variable):
                    nb[subj.id] = self._scope_term
        for v in order:
            if isinstance(_ground(v, nb), Variable):
                nb[v.id] = Existential(f"sk_{self._sk_counter}")
                self._sk_counter += 1
        node.gives = [_ground_triple(t, nb) for t in rule.head.triples]
        node.bindings = [(f"x_{i}", _ground(v, nb))
                         for i, v in enumerate(order)]
        node.evidence = [self._evidence_for(_ground_triple(t, nb))
                         for t in rule.body.triples]
        return node

    def _evidence_for(self, grounded: Triple) -> Node:
        """Classify one grounded body atom of a recorded rule firing."""
        pred = (grounded.predicate.value
                if isinstance(grounded.predicate, NamedNode) else None)
        if pred is not None and pred in self.engine._builtins:
            return Fact(conclusion=grounded)
        hit = self._fact_sources.get(str(grounded))
        if hit is not None:
            return self._fact_extraction(hit[0], hit[1])
        if grounded in getattr(self.engine, "_derivations", {}):
            return self._materialize_derived(grounded)
        return Fact(conclusion=grounded)

    @staticmethod
    def _unify3(pat: Triple, goal: Triple, b: Binding) -> Binding | None:
        b = unify_terms(pat.predicate, goal.predicate, b)
        if b is None:
            return None
        b = unify_terms(pat.subject, goal.subject, b)
        if b is None:
            return None
        return unify_terms(pat.object, goal.object, b)


# ---------------------------------------------------------------------------
# Top-level proof construction (query rules → proof DAG)
# ---------------------------------------------------------------------------

def build_proof(kb: ProofKB,
                query_rules: list[tuple[Rule, str]],
                engine=None,
                sources: list[str] | None = None) -> "Proof":
    """Build the proof DAG for *query_rules* against *kb*.

    Each query rule ``{P} => {C}`` fires once per binding of P; the firing is
    an Inference whose evidence justifies the body atoms and whose rule is the
    query extraction.  *engine* is a populated, already-run Engine; when None
    a fresh engine is built from *kb* (facts + rules) and run to closure.
    """
    if engine is None:
        from pyeye.engine import Engine
        engine = Engine(timeout_seconds=30.0)
        engine._record_derivations = True
        for rule, _src in kb.rules:
            engine.add_rule(rule)
        for t, _src in kb.facts:
            engine.add_triple(t)
        engine.snapshot_initial()
        engine.run()
    return ProofBuilder(kb, engine, sources=sources).build(query_rules)


def make_pass_query_rule() -> Rule:
    """The synthetic ``{?S ?P ?O} => {?S ?P ?O}`` rule EYE uses for --pass."""
    from pyeye.term import _next_var_id
    s = Variable(name="S", id=_next_var_id())
    p = Variable(name="P", id=_next_var_id())
    o = Variable(name="O", id=_next_var_id())
    f = Formula(triples=(Triple(s, p, o),))
    return Rule(body=f, head=f, is_query=True, source=PASS_SOURCE)


@dataclass
class Proof:
    components: list[Inference]
    # data blank-node label -> 1-based source-document number (EYE renders
    # such nodes as skolem genid IRIs ``e_<label>_<doc#>``)
    bnode_docs: dict[str, int] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Serialization to the reason: vocabulary
# ---------------------------------------------------------------------------

def serialize_proof(proof: Proof, doc_prefixes: dict[str, str],
                    genid: str = SKOLEM_GENID) -> str:
    return _Serializer(proof, doc_prefixes, genid).run()


class _Serializer:
    def __init__(self, proof: Proof, doc_prefixes: dict[str, str],
                 genid: str) -> None:
        self.proof = proof
        self.doc_prefixes = doc_prefixes
        self.genid = genid
        self.skolem_ns = (
            f"https://eyereasoner.github.io/.well-known/genid/{genid}#"
        )
        self._bnode_docs = proof.bnode_docs
        # node -> lemma name (assigned in BFS order)
        self._names: dict[int, str] = {}
        self._counter = 0
        self._order: list[Node] = []

    def _name(self, node: Node) -> str:
        nid = id(node)
        if nid not in self._names:
            self._counter += 1
            self._names[nid] = f"lemma{self._counter}"
            self._order.append(node)
        return self._names[nid]

    def run(self) -> str:
        # BFS numbering: queue components, then for each inference assign
        # evidence-children names, then rule-child name.
        queue: list[Node] = []
        for comp in self.proof.components:
            self._name(comp)
            queue.append(comp)
        i = 0
        while i < len(queue):
            node = queue[i]
            i += 1
            if isinstance(node, Inference):
                for ev in node.evidence:
                    if isinstance(ev, (Inference, Extraction)):
                        if id(ev) not in self._names:
                            self._name(ev)
                            queue.append(ev)
                if id(node.rule) not in self._names:
                    self._name(node.rule)
                    queue.append(node.rule)

        lines: list[str] = []
        lines.extend(self._prefix_block())
        lines.append("")
        lines.extend(self._proof_header())
        for node in self._order:
            lines.append("")
            if isinstance(node, Inference):
                lines.extend(self._inference_block(node))
            elif isinstance(node, Extraction):
                lines.extend(self._extraction_block(node))
        lines.append("")
        return "\n".join(lines) + "\n"

    # -- prefixes -----------------------------------------------------------

    def _prefix_block(self) -> list[str]:
        out = [
            f"@prefix skolem: <{self.skolem_ns}>.",
            "@prefix r: <http://www.w3.org/2000/10/swap/reason#>.",
        ]
        for pfx, uri in self.doc_prefixes.items():
            if pfx in ("skolem", "r", "n3", "var"):
                continue
            out.append(f"@prefix {pfx}: <{uri}>.")
        out.append("@prefix n3: <http://www.w3.org/2004/06/rei#>.")
        out.append(f"@prefix var: <{_VAR_NS}>.")
        return out

    def _proof_header(self) -> list[str]:
        out = ["skolem:proof a r:Proof, r:Conjunction;"]
        for comp in self.proof.components:
            out.append(f"    r:component skolem:{self._names[id(comp)]};")
        out.append("    r:gives {")
        for comp in self.proof.components:
            for tr in comp.gives:
                out.extend(self._triple_lines(tr, 8))
        out.append("    }.")
        return out

    # -- lemma blocks -------------------------------------------------------

    def _inference_block(self, node: Inference) -> list[str]:
        name = self._names[id(node)]
        out = [f"skolem:{name} a r:Inference;"]
        out.append("    r:gives {")
        for tr in node.gives:
            out.extend(self._triple_lines(tr, 8))
        out.append("    };")
        out.append("    r:evidence (")
        for ev in node.evidence:
            out.extend(self._evidence_ref(ev))
        out.append("    );")
        for var, val in node.bindings:
            out.append(self._binding_line(var, val))
        out.append(f"    r:rule skolem:{self._names[id(node.rule)]}.")
        return out

    def _evidence_ref(self, ev: Node) -> list[str]:
        if isinstance(ev, Fact):
            inner = self._inline_formula(ev.conclusion)
            return [f"        [ a r:Fact; r:gives {{{inner}}}]"]
        return [f"        skolem:{self._names[id(ev)]}"]

    def _extraction_block(self, node: Extraction) -> list[str]:
        name = self._names[id(node)]
        out = [f"skolem:{name} a r:Extraction;"]
        out.append("    r:gives {")
        if isinstance(node.gives, Rule):
            out.extend(self._rule_lines(node.gives, 8))
        else:
            out.extend(self._triple_lines(node.gives, 8))
        out.append("    };")
        out.append(
            f"    r:because [ a r:Parsing; r:source <{node.source}>]."
        )
        return out

    def _binding_line(self, var: str, val: Term) -> str:
        v = f'r:variable [ n3:uri "{_VAR_NS}{var}"]'
        return f"    r:binding [ {v}; r:boundTo {self._bound_to(val)}];"

    def _bound_to(self, val: Term) -> str:
        if isinstance(val, NamedNode):
            return f'[ n3:uri "{val.value}"]'
        if isinstance(val, Existential):
            m = _SKOLEM_NAME_RE.match(val.name)
            if m:
                return f'[ a r:Existential; n3:nodeId "_:sk_{m.group(1)}"]'
            doc = self._bnode_docs.get(val.name)
            if doc is not None:
                return (f'[ a r:Existential; n3:nodeId '
                        f'"{self.skolem_ns}e_{val.name}_{doc}"]')
            return f'[ a r:Existential; n3:nodeId "_:{val.name}"]'
        return self._term(val)

    # -- formula / term serialization ---------------------------------------

    def _triple_lines(self, tr: Triple, indent: int) -> list[str]:
        pad = " " * indent
        s = self._term(tr.subject)
        p = self._term(tr.predicate)
        o = self._term(tr.object)
        # A trailing digit would lex into the final dot (e.g. "0.5.").
        sep = " ." if o and (o[-1].isdigit() or o[-1] == ".") else "."
        return [f"{pad}{s} {p} {o}{sep}"]

    def _rule_lines(self, rule: Rule, indent: int) -> list[str]:
        """Render a rule with @forAll/@forSome quantifier prefix."""
        pad = " " * indent
        order = _rule_var_order(rule)
        var_names: dict[int, str] = {v.id: f"x_{i}"
                                     for i, v in enumerate(order)}
        body_ids = _formula_var_ids(rule.body)
        forall = ", ".join(f"var:{var_names[v.id]}" for v in order
                           if v.id in body_ids)
        forsome = ", ".join(f"var:{var_names[v.id]}" for v in order
                            if v.id not in body_ids)
        quant = ""
        if forall:
            quant += f"@forAll {forall}. "
        if forsome:
            quant += f"@forSome {forsome}. "
        out: list[str] = [f"{pad}{quant}{{"]
        for tr in rule.body.triples:
            out.append(self._var_triple_line(tr, indent + 4, var_names))
        out.append(f"{pad}}} => {{")
        for tr in rule.head.triples:
            out.append(self._var_triple_line(tr, indent + 4, var_names))
        out.append(f"{pad}}}.")
        return out

    def _var_triple_line(self, tr: Triple, indent: int,
                         var_names: dict[int, str]) -> str:
        pad = " " * indent
        s = self._var_term(tr.subject, var_names)
        p = self._var_term(tr.predicate, var_names)
        o = self._var_term(tr.object, var_names)
        sep = " ." if o and (o[-1].isdigit() or o[-1] == ".") else "."
        return f"{pad}{s} {p} {o}{sep}"

    def _var_term(self, t: Term, var_names: dict[int, str]) -> str:
        if isinstance(t, Variable):
            name = var_names.get(t.id)
            return f"var:{name}" if name else f"?{t.name}"
        if isinstance(t, ListTerm):
            return "(" + " ".join(
                self._var_term(i, var_names) for i in t.items) + ")"
        if isinstance(t, Formula):
            inner = ". ".join(
                f"{self._var_term(x.subject, var_names)} "
                f"{self._var_term(x.predicate, var_names)} "
                f"{self._var_term(x.object, var_names)}"
                for x in t.triples)
            return "{" + inner + "}"
        return self._term(t)

    def _inline_formula(self, tr: Triple) -> str:
        return (f"{self._term(tr.subject)} {self._term(tr.predicate)} "
                f"{self._term(tr.object)}")

    def _term(self, t: Term) -> str:
        if isinstance(t, NamedNode):
            return self._abbrev(t.value)
        if isinstance(t, Literal):
            return self._literal(t)
        if isinstance(t, Variable):
            return f"?{t.name}"
        if isinstance(t, Existential):
            # Skolemised head variables print as fresh universals (?U_N),
            # mirroring EYE; the r:binding shows the _:sk_N existential.
            m = _SKOLEM_NAME_RE.match(t.name)
            if m:
                return f"?U_{m.group(1)}"
            doc = self._bnode_docs.get(t.name)
            if doc is not None:
                return f"skolem:e_{t.name}_{doc}"
            return f"_:{t.name}"
        if isinstance(t, ListTerm):
            if not t.items:
                return "()"
            return "(" + " ".join(self._term(i) for i in t.items) + ")"
        if isinstance(t, Formula):
            inner = ". ".join(self._inline_formula(x) for x in t.triples)
            return "{" + inner + "}"
        if isinstance(t, TripleTerm):
            return (f"<<{self._term(t.subject)} {self._term(t.predicate)} "
                    f"{self._term(t.object)}>>")
        return str(t)

    _RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"

    def _abbrev(self, uri: str) -> str:
        if uri == self._RDF_TYPE:
            return "a"
        best = None
        for pfx, ns in self.doc_prefixes.items():
            if uri.startswith(ns) and (best is None or len(ns) > len(best[1])):
                best = (pfx, ns)
        if best is not None:
            local = uri[len(best[1]):]
            if local and not any(c in local for c in "/#?@(){}[]"):
                return f"{best[0]}:{local}"
        return f"<{uri}>"

    def _literal(self, lit: Literal) -> str:
        XSD = "http://www.w3.org/2001/XMLSchema#"
        if lit.datatype:
            dt = lit.datatype.value
            if dt == XSD + "boolean":
                return lit.value
            if dt == XSD + "integer":
                return lit.value
            if dt in (XSD + "decimal", XSD + "double", XSD + "float"):
                v = lit.value
                if v.endswith("."):
                    v += "0"
                return v
        value = (lit.value.replace("\\", "\\\\").replace('"', '\\"')
                 .replace("\n", "\\n").replace("\r", "\\r"))
        if lit.language:
            return f'"{value}"@{lit.language.lower()}'
        if lit.datatype:
            return f'"{value}"^^{self._abbrev(lit.datatype.value)}'
        return f'"{value}"'
