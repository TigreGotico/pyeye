"""Euler Abstract Machine — forward-chaining reasoner.

The engine iterates over rules, matches body patterns against the triple
store, derives head instances, and repeats until fixpoint (no new
derivations in a full pass).

Public API
----------
``Engine``
    .. automethod:: add_rule
    .. automethod:: add_triple
    .. automethod:: run
    .. automethod:: derived_triples
"""

from __future__ import annotations

from pyeye.term import (
    NamedNode, Literal, Variable, Existential, Formula, Triple, Term, Binding
)
from pyeye.unify import unify, apply_binding_to_triple, apply_binding
from pyeye.store import TripleStore
from pyeye.parser import Rule
from pyeye.builtins import Builtin, BUILTIN_REGISTRY
from pyeye.proof import ProofStep, ProofTree


class Engine:
    """Forward-chaining N3 reasoner (Euler Abstract Machine)."""

    def __init__(
        self,
        builtins: dict[str, Builtin] | None = None,
        max_steps: int = -1,
        limit_answers: int = -1,
        djiti_debug: bool = False,
        explain: bool = False,
    ) -> None:
        self.store = TripleStore()
        self._rules: list[Rule] = []
        self._builtins: dict[str, Builtin] = {**BUILTIN_REGISTRY}
        if builtins:
            self._builtins.update(builtins)
        self._max_steps = max_steps
        self._limit_answers = limit_answers
        self._step_count = 0
        self._derived_count = 0
        self._derived_triples: list[Triple] = []  # only rule-derived triples
        self._initial_triples: int = 0  # snapshot after loading data
        self._skolem_counter = 0
        self._output_strings: list[Term] = []
        self._djiti_debug = djiti_debug
        self._djiti_log: list[dict] = []  # debug log of pattern orderings
        # Proof tracing
        self._explain = explain
        self._proof_steps: list[ProofStep] = []
        self._proof_trees: list[ProofTree] = []

    # -- population ----------------------------------------------------------

    def add_rule(self, rule: Rule) -> None:
        self._rules.append(rule)

    def add_triple(self, triple: Triple) -> bool:
        """Add a fact triple. Returns True if genuinely new."""
        return self.store.add(triple)

    def snapshot_initial(self) -> None:
        """Record the current store size as the baseline (input facts)."""
        self._initial_triples = len(self.store)

    # -- execution -----------------------------------------------------------

    def run(self) -> None:
        """Run forward chaining to fixpoint or until a limit is hit."""
        while True:
            self._derived_count = 0
            for rule in self._rules:
                self._apply_rule(rule)
                if self._limit_answers > 0 and self._derived_count >= self._limit_answers:
                    return
            if self._derived_count == 0:
                break  # fixpoint
            if self._max_steps > 0 and self._step_count >= self._max_steps:
                break

    def _apply_rule(self, rule: Rule) -> None:
        """Match body patterns against store, derive head if new."""
        bindings = self._match_formula(rule.body, {})
        for binding in bindings:
            if self._limit_answers > 0 and self._derived_count >= self._limit_answers:
                return
            if self._max_steps > 0 and self._step_count >= self._max_steps:
                return

            # Instantiate head
            head_triples = self._instantiate_formula(rule.head, binding)
            for head_triple in head_triples:
                if self._limit_answers > 0 and self._derived_count >= self._limit_answers:
                    return
                if self._max_steps > 0 and self._step_count >= self._max_steps:
                    return

                if head_triple.is_ground() and self.store.add(head_triple):
                    self._derived_count += 1
                    self._step_count += 1
                    self._derived_triples.append(head_triple)

                    # Record proof step
                    if self._explain:
                        premise = list(rule.body.triples) if rule.body.triples else None
                        step = ProofStep(
                            conclusion=head_triple,
                            premise=premise,
                            rule=rule,
                            chaining="forward",
                            source=rule.source,
                        )
                        self._proof_steps.append(step)
                        # Build a simple proof tree (flat, one level)
                        tree = ProofTree(
                            root=head_triple,
                            rule=rule,
                            chaining="forward",
                        )
                        self._proof_trees.append(tree)

    def _match_formula(
        self,
        formula: Formula,
        binding: Binding,
    ) -> list[Binding]:
        """Match all triple patterns in *formula* against the store.

        Returns a list of binding extensions — one per valid combination
        of store triples that satisfy all patterns simultaneously.

        Uses DJITI (most-constrained-first) ordering: patterns are sorted
        by how many store triples they match, ascending, to minimize the
        combinatorial explosion of the nested join.
        """
        if not formula.triples:
            return [binding]

        patterns = list(formula.triples)

        # DJITI: order patterns by constraint (fewest matches first)
        patterns = self._djiti_order(patterns, binding)

        return self._match_triples_iter(patterns, binding)

    def _djiti_order(
        self,
        patterns: list[Triple],
        binding: Binding,
    ) -> list[Triple]:
        """Reorder patterns by how many store triples they could match.

        Patterns with fewer possible matches are placed first, reducing
        the branching factor of the nested join. Deterministic: ties are
        broken by original position.
        """
        counts: list[int] = []
        for pattern in patterns:
            resolved = self._resolve_triple(pattern, binding)
            counts.append(len(self._store_matches(resolved)))

        indexed = list(enumerate(patterns))
        indexed.sort(key=lambda pair: counts[pair[0]])
        ordered = [p for _, p in indexed]
        ordered_counts = [counts[i] for i, _ in indexed]

        if self._djiti_debug:
            self._djiti_log.append({
                "original": [str(p) for p in patterns],
                "ordered": [str(p) for p in ordered],
                "counts": ordered_counts,
            })

        return ordered

    def _match_triples_iter(
        self,
        patterns: list[Triple],
        binding: Binding,
    ) -> list[Binding]:
        """Iteratively match triple patterns, accumulating bindings."""
        results: list[Binding] = [binding]

        for pattern in patterns:
            # Resolve any bound variables in the pattern
            resolved = self._resolve_triple(pattern, binding)

            # Check for builtins in the predicate position
            if isinstance(resolved.predicate, NamedNode):
                builtin = self._builtins.get(resolved.predicate.value)
                if builtin is not None:
                    results = self._handle_builtin(builtin, resolved, results)
                    continue

            # Normal triple: match against store
            new_results: list[Binding] = []
            for b in results:
                r = self._resolve_triple(pattern, b)
                # Pattern match: find all store triples that unify
                for store_triple in self._store_matches(r):
                    ub = unify(r, store_triple, dict(b))
                    if ub is not None:
                        new_results.append(ub)
            results = new_results
            if not results:
                break

        return results

    def _store_matches(self, pattern: Triple) -> list[Triple]:
        """Find store triples matching the (partially resolved) pattern."""
        s = pattern.subject if not isinstance(pattern.subject, Variable) else None
        p = pattern.predicate if not isinstance(pattern.predicate, Variable) else None
        o = pattern.object if not isinstance(pattern.object, Variable) else None
        return list(self.store.match(subject=s, predicate=p, object=o))

    def _handle_builtin(
        self,
        builtin: Builtin,
        pattern: Triple,
        input_bindings: list[Binding],
    ) -> list[Binding]:
        """Evaluate a builtin predicate and filter/extend bindings."""
        results: list[Binding] = []
        for b in input_bindings:
            resolved = self._resolve_triple(pattern, b)
            # Collect args: the object of the builtin triple
            builtin_obj = resolved.object
            # The subject and predicate provide the input args
            args = self._collect_builtin_args(resolved, b)
            if not args:
                continue
            result = builtin(args, self)
            if result is None:
                continue  # unground args — skip
            if isinstance(result, list):
                # Predicate-style: assert triples
                for t in result:
                    self.store.add(t)
                results.append(b)
            elif isinstance(result, Term):
                # Function-style: compare with pattern object
                if isinstance(builtin_obj, Variable):
                    new_b = dict(b)
                    new_b[builtin_obj.name] = result
                    results.append(new_b)
                elif result == builtin_obj:
                    results.append(b)
        return results

    def _collect_builtin_args(self, resolved: Triple, binding: Binding) -> list[Term]:
        """Extract arguments for a builtin from the resolved triple.

        For builtin patterns like ``{math:greaterThan(?X, 5) ?Result}`` or
        ``{(5) math:greaterThan (?X)}``, we treat the subject and object as args.
        """
        args: list[Term] = []
        s = self._resolve_term(resolved.subject, binding)
        o = self._resolve_term(resolved.object, binding)
        # If subject is a list (Existential pointing to RDF list), expand it
        if isinstance(s, Existential):
            args.extend(self._expand_list(s))
        else:
            args.append(s)
        args.append(o)
        return args

    def _expand_list(self, head: Existential) -> list[Term]:
        """Expand an RDF list starting at *head* into a Python list of Terms."""
        rdf_first = NamedNode("http://www.w3.org/1999/02/22-rdf-syntax-ns#first")
        rdf_rest = NamedNode("http://www.w3.org/1999/02/22-rdf-syntax-ns#rest")
        nil = Existential("nil")
        result: list[Term] = []
        cur = head
        visited: set[str] = set()
        while cur.name not in visited and cur.name != "nil":
            visited.add(cur.name)
            first_matches = list(self.store.match(subject=cur, predicate=rdf_first))
            if first_matches:
                result.append(first_matches[0].object)
            rest_matches = list(self.store.match(subject=cur, predicate=rdf_rest))
            if rest_matches:
                nxt = rest_matches[0].object
                if nxt == nil:
                    break
                if isinstance(nxt, Existential):
                    cur = nxt
                else:
                    break
            else:
                break
        return result

    def _resolve_triple(self, triple: Triple, binding: Binding) -> Triple:
        """Substitute bound variables in a triple pattern."""
        return Triple(
            self._resolve_term(triple.subject, binding),
            self._resolve_term(triple.predicate, binding),
            self._resolve_term(triple.object, binding),
        )

    def _resolve_term(self, term: Term, binding: Binding) -> Term:
        if isinstance(term, Variable) and term.name in binding:
            return binding[term.name]
        return term

    def _instantiate_formula(
        self,
        formula: Formula,
        binding: Binding,
    ) -> list[Triple]:
        """Create ground triples from the head formula with bindings applied."""
        result: list[Triple] = []
        for pattern in formula.triples:
            t = apply_binding_to_triple(pattern, binding)
            # Skolemize unbound existentials
            t = self._skolemize(t)
            result.append(t)
        return result

    def _skolemize(self, triple: Triple) -> Triple:
        """Replace any remaining Existential terms with fresh skolem constants."""
        def sk(t: Term) -> Term:
            if isinstance(t, Existential) and t.name.startswith("_b"):
                self._skolem_counter += 1
                return Existential(f"sk-{self._skolem_counter}")
            return t
        return Triple(
            sk(triple.subject),
            sk(triple.predicate),
            sk(triple.object),
        )

    # -- properties ----------------------------------------------------------

    @property
    def derived_triples(self) -> list[Triple]:
        """Only triples derived by rules (not input facts)."""
        return list(self._derived_triples)

    @property
    def step_count(self) -> int:
        return self._step_count
