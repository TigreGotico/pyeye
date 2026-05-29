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
r:source <file> ]``.  Builtin-produced facts are inline ``[ a r:Fact; ... ]``.

The lemmas are numbered ``skolem:lemma1, lemma2, …`` in breadth-first order,
assigning ids to each inference's evidence children first and then its rule
child, matching EYE's traversal.  Identical extraction lemmas are shared.

This module runs an independent SLD backward proof over the source facts and
rules (each tagged with the file it was parsed from), so it does not depend on
the forward-chaining engine's optimised solver.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from pyeye.term import (
    NamedNode, Literal, Variable, Existential, Formula, Triple, Term,
    ListTerm, TripleTerm, FormulaTerm, Binding, _next_var_id,
)
from pyeye.unify import unify_terms, apply_binding
from pyeye.parser import Rule


# Well-known IRIs
SKOLEM_GENID = "8b98b360-9a70-4845-b52c-c675af60ad01"
_VAR_NS = "http://www.w3.org/2000/10/swap/var#"
_LIST_IN = "http://www.w3.org/2000/10/swap/list#in"


# ---------------------------------------------------------------------------
# Proof DAG nodes
# ---------------------------------------------------------------------------

@dataclass
class Inference:
    """A rule firing: conclusion derived from evidence under bindings."""
    conclusion: Triple
    evidence: list["Node"]
    bindings: list[tuple[str, Term]]   # (var#x_N, boundValue) in var order
    rule: "Extraction"


@dataclass
class Extraction:
    """A source fact or rule, justified by parsing its source file."""
    gives: object          # Triple (fact) or Rule (rule)
    source: str            # source file URL


@dataclass
class Fact:
    """A builtin-produced fact (inline ``[ a r:Fact; r:gives {...} ]``)."""
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
# Variable renaming for proof search (fresh ids per rule application)
# ---------------------------------------------------------------------------

def _rename_rule_terms(rule: Rule) -> tuple[Formula, Formula, list[Variable]]:
    """Return (body, head, vars) with fresh variable ids.

    ``vars`` lists the distinct variables in first-appearance order (body then
    head), so they can be numbered ``var#x_0, x_1, …`` deterministically.
    """
    var_map: dict[int, Variable] = {}
    order: list[Variable] = []

    def cp(t: Term) -> Term:
        if isinstance(t, Variable):
            if t.id not in var_map:
                nv = Variable(name=t.name, id=_next_var_id())
                var_map[t.id] = nv
                order.append(nv)
            return var_map[t.id]
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
# Proof search
# ---------------------------------------------------------------------------

class ProofSearch:
    """Backward SLD proof search that records the derivation DAG."""

    def __init__(self, kb: ProofKB, max_depth: int = 60) -> None:
        self.kb = kb
        self.max_depth = max_depth
        # Cache: identical Extraction(fact|rule, source) is shared
        self._fact_extractions: dict[tuple, Extraction] = {}
        self._rule_extractions: dict[int, Extraction] = {}
        # Global skolem counter for head-introduced existentials (_:sk_N).
        self._sk_counter = 0

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

    # -- proving (generator-based, with backtracking) -----------------------

    def prove_body(self, rule: Rule, source: str, body: Formula,
                   head: Formula, order: list[Variable], b: Binding,
                   head_idx: int, depth: int, anc: frozenset = frozenset()):
        """Yield Inference nodes proving the rule's *head_idx* conclusion.

        Proves every body atom in order with full backtracking, so a
        conjunction can choose a body solution that lets later atoms succeed.
        """
        if depth > self.max_depth:
            return
        rule_ex = self._rule_extraction(rule, source)
        for ev, cur in self._prove_atoms(list(body.triples), b, depth, anc):
            # Bind any head variable not constrained by the body to a fresh
            # existential (_:sk_N), as EYE skolemises free head variables.
            cur = self._skolemise_free_head_vars(head.triples[head_idx],
                                                 order, cur)
            conclusion = _ground_triple(head.triples[head_idx], cur)
            bindings = self._var_bindings(order, cur)
            yield Inference(conclusion=conclusion, evidence=ev,
                            bindings=bindings, rule=rule_ex)

    def _skolemise_free_head_vars(self, head_t: Triple,
                                  order: list[Variable],
                                  b: Binding) -> Binding:
        """Bind unresolved head variables to fresh _:sk_N existentials."""
        free: list[Variable] = []
        for t in (head_t.subject, head_t.predicate, head_t.object):
            for v in self._term_vars(t):
                if isinstance(apply_binding(v, b), Variable) and v not in free:
                    free.append(v)
        if not free:
            return b
        nb = dict(b)
        for v in free:
            nb[v.id] = Existential(f"sk_{self._sk_counter}")
            self._sk_counter += 1
        return nb

    @staticmethod
    def _term_vars(t: Term) -> list[Variable]:
        if isinstance(t, Variable):
            return [t]
        if isinstance(t, ListTerm):
            out: list[Variable] = []
            for i in t.items:
                out.extend(ProofSearch._term_vars(i))
            return out
        return []

    def _prove_atoms(self, atoms: list[Triple], b: Binding, depth: int,
                     anc: frozenset):
        """Yield (evidence_list, binding) for proving the conjunction *atoms*."""
        if not atoms:
            yield [], b
            return
        first, rest = atoms[0], atoms[1:]
        for node, nb in self._prove_atom(first, b, depth, anc):
            for ev_rest, fb in self._prove_atoms(rest, nb, depth, anc):
                ev = ([node] + ev_rest) if node is not None else ev_rest
                yield ev, fb

    def _prove_atom(self, atom: Triple, b: Binding, depth: int,
                    anc: frozenset):
        """Yield (evidence_node | None, binding) solutions for one atom."""
        resolved = _ground_triple(atom, b)

        # list:in builtin membership → inline r:Fact, no extraction lemma.
        if (isinstance(resolved.predicate, NamedNode)
                and resolved.predicate.value == _LIST_IN):
            if isinstance(resolved.object, ListTerm):
                if isinstance(resolved.subject, Variable):
                    for item in resolved.object.items:
                        nb = unify_terms(resolved.subject, item, b)
                        if nb is not None:
                            yield (Fact(conclusion=Triple(
                                item, resolved.predicate, resolved.object)), nb)
                elif resolved.subject in resolved.object.items:
                    yield Fact(conclusion=resolved), b
            return

        # Ordinary atom: prove via a source fact or a rule, with backtracking.
        for fact, source in self.kb.facts:
            nb = self._unify3(fact, resolved, dict(b))
            if nb is None:
                continue
            grounded = _ground_triple(fact, nb)
            merged = self._bind_goal_vars(resolved, grounded, b)
            yield self._fact_extraction(grounded, source), merged

        # Cycle guard: do not re-expand a goal already on this proof path.
        gk = _goal_key(resolved)
        if gk in anc:
            return
        child_anc = anc | {gk}
        for rule, source in self.kb.rules:
            for hi, _ in enumerate(rule.head.triples):
                body, head, order = _rename_rule_terms(rule)
                head_t = head.triples[hi]
                nb = self._unify3(head_t, resolved, dict(b))
                if nb is None:
                    continue
                for node in self.prove_body(rule, source, body, head, order,
                                            nb, hi, depth + 1, child_anc):
                    merged = self._bind_goal_vars(resolved, node.conclusion, b)
                    yield node, merged

    @staticmethod
    def _unify3(pat: Triple, goal: Triple, b: Binding) -> Binding | None:
        b = unify_terms(pat.predicate, goal.predicate, b)
        if b is None:
            return None
        b = unify_terms(pat.subject, goal.subject, b)
        if b is None:
            return None
        return unify_terms(pat.object, goal.object, b)

    def _bind_goal_vars(self, goal: Triple, concl: Triple,
                        b: Binding) -> Binding:
        """Extend *b* with bindings recovered by matching goal against concl."""
        nb = self._unify3(goal, concl, dict(b))
        return nb if nb is not None else b

    @staticmethod
    def _goal_vars(goal: Triple) -> list[Variable]:
        out: list[Variable] = []
        for t in (goal.subject, goal.predicate, goal.object):
            if isinstance(t, Variable):
                out.append(t)
        return out

    @staticmethod
    def _var_bindings(order: list[Variable],
                      b: Binding) -> list[tuple[str, Term]]:
        """Produce (var#x_N, value) pairs for the rule's variables in order."""
        out: list[tuple[str, Term]] = []
        for i, v in enumerate(order):
            val = apply_binding(v, b)
            out.append((f"x_{i}", val))
        return out


# ---------------------------------------------------------------------------
# Top-level proof construction (query rules → proof DAG)
# ---------------------------------------------------------------------------

def build_proof(kb: ProofKB,
                query_rules: list[tuple[Rule, str]]) -> "Proof":
    """Build the proof DAG for *query_rules* against *kb*.

    Each query rule ``{P} => {C}`` fires once per binding of P; the firing is
    an Inference whose evidence is the proof of P and whose rule is the query
    extraction.  Returns a Proof holding the component inferences (one per
    answer).
    """
    search = ProofSearch(kb)
    components: list[Inference] = []
    for rule, source in query_rules:
        # rename, then prove the body, collecting every solution
        for sol in _solve_query(search, rule, source):
            components.append(sol)
    return Proof(components=components)


def _solve_query(search: ProofSearch, rule: Rule,
                 source: str):
    """Yield one Inference per distinct answer of the query rule."""
    seen: set[str] = set()
    body, head, order = _rename_rule_terms(rule)
    for hi in range(len(head.triples)):
        for node in search.prove_body(rule, source, body, head, order, {},
                                      hi, 0):
            key = str(node.conclusion)
            if key not in seen:
                seen.add(key)
                yield node


@dataclass
class Proof:
    components: list[Inference]


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
                        self._name(ev)
                        queue.append(ev)
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
            out.extend(self._formula_lines(comp.conclusion, 8))
        out.append("    }.")
        return out

    # -- lemma blocks -------------------------------------------------------

    def _inference_block(self, node: Inference) -> list[str]:
        name = self._names[id(node)]
        out = [f"skolem:{name} a r:Inference;"]
        out.append("    r:gives {")
        out.extend(self._formula_lines(node.conclusion, 8))
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
            out.extend(self._formula_lines(node.gives, 8))
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
        if isinstance(val, ListTerm):
            return self._term(val)
        if isinstance(val, Existential):
            return f'[ a r:Existential; n3:nodeId "_:{val.name}"]'
        return self._term(val)

    # -- formula / term serialization ---------------------------------------

    def _formula_lines(self, conclusion, indent: int) -> list[str]:
        """Render a conclusion (Triple) as indented N3 triple lines."""
        return self._triple_lines(conclusion, indent)

    def _triple_lines(self, tr: Triple, indent: int) -> list[str]:
        pad = " " * indent
        s = self._term_multiline(tr.subject, indent)
        p = self._term(tr.predicate)
        o = self._term_multiline(tr.object, indent)
        # When subject/object are multi-line formulas, splice them.
        return [f"{pad}{s} {p} {o}."]

    def _rule_lines(self, rule: Rule, indent: int) -> list[str]:
        """Render a rule with @forAll/@forSome quantifier prefix."""
        pad = " " * indent
        # Collect variables of the rule (for @forAll) in first-appearance order
        body, head, order = _rename_rule_terms(rule)
        # Map fresh var ids -> var:x_N names
        var_names: dict[int, str] = {v.id: f"x_{i}"
                                     for i, v in enumerate(order)}
        forall = ", ".join(f"var:{var_names[v.id]}" for v in order)
        out: list[str] = []
        prefix = f"@forAll {forall}. {{" if forall else "{"
        out.append(f"{pad}{prefix}")
        for tr in body.triples:
            out.append(self._var_triple_line(tr, indent + 4, var_names))
        out.append(f"{pad}}} => {{")
        for tr in head.triples:
            out.append(self._var_triple_line(tr, indent + 4, var_names))
        out.append(f"{pad}}}.")
        return out

    def _var_triple_line(self, tr: Triple, indent: int,
                         var_names: dict[int, str]) -> str:
        pad = " " * indent
        s = self._var_term(tr.subject, var_names)
        p = self._var_term(tr.predicate, var_names)
        o = self._var_term(tr.object, var_names)
        return f"{pad}{s} {p} {o}."

    def _var_term(self, t: Term, var_names: dict[int, str]) -> str:
        if isinstance(t, Variable):
            return f"var:{var_names.get(t.id, t.name)}"
        if isinstance(t, ListTerm):
            return "(" + " ".join(
                self._var_term(i, var_names) for i in t.items) + ")"
        return self._term(t)

    def _term_multiline(self, t: Term, indent: int) -> str:
        # For the targeted scenarios subjects/objects are atomic or lists.
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
            return f"{best[0]}:{uri[len(best[1]):]}"
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
        if lit.language:
            return f'"{lit.value}"@{lit.language}'
        if lit.datatype:
            return f'"{lit.value}"^^{self._abbrev(lit.datatype.value)}'
        return f'"{lit.value}"'
