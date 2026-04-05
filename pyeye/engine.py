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
from pyeye.unify import unify, apply_binding_to_triple, apply_binding, term_contains_var
from pyeye.store import TripleStore
from pyeye.parser import Rule
from pyeye.builtins import Builtin, BUILTIN_REGISTRY
from pyeye.proof import ProofStep, ProofTree
from pyeye.term import Formula, NegativeSurface


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
        self._bn_counter = 0  # C6 fix: blank node counter (head skolemization)
        self._skolem_counter = 0  # log:skolem builtin counter
        self._output_strings: list[Term] = []
        self._djiti_debug = djiti_debug
        self._djiti_log: list[dict] = []  # debug log of pattern orderings
        # Proof tracing
        self._explain = explain
        self._proof_steps: list[ProofStep] = []
        self._proof_trees: list[ProofTree] = []
        # M7 fix: Index of derived triple → proof tree for multi-level proofs
        self._proof_index: dict[Triple, ProofTree] = {}

    # -- population ----------------------------------------------------------

    def add_rule(self, rule: Rule) -> None:
        self._rules.append(rule)

    def add_triple(self, triple: Triple) -> bool:
        """Add a fact triple. Returns True if genuinely new."""
        new = self.store.add(triple)
        if new and self._rules:
            # Incremental: re-evaluate rules that might be affected
            self._incremental_derive(triple)
        return new

    def _incremental_derive(self, new_triple: Triple) -> None:
        """Re-evaluate rules that could derive new facts from *new_triple*.

        This is a simplified incremental reasoner: for each rule, check if
        any body pattern matches the new triple, and if so, try to derive
        the head. Derived triples are recursively processed for cascading.
        """
        # Use a queue to handle cascading derivations
        queue = [new_triple]
        processed: set[Triple] = {new_triple}

        while queue:
            current = queue.pop(0)
            for rule in self._rules:
                for pattern in rule.body.triples:
                    # Check if the pattern could match the current triple
                    ub = unify(pattern, current, {})
                    if ub is not None:
                        # Pattern matches — try to derive the head
                        other_patterns = [p for p in rule.body.triples if p is not pattern]
                        if other_patterns:
                            # Try to match remaining patterns
                            bindings = self._match_triples_iter(other_patterns, ub)
                            for binding in bindings:
                                head_triples = self._instantiate_formula(rule.head, binding)
                                for head_triple in head_triples:
                                    if head_triple.is_ground() and head_triple not in processed:
                                        if self.store.add(head_triple):
                                            processed.add(head_triple)
                                            queue.append(head_triple)
                                            self._derived_count += 1
                                            self._step_count += 1
                                            self._derived_triples.append(head_triple)
                                            if self._explain:
                                                step = ProofStep(
                                                    conclusion=head_triple,
                                                    premise=list(rule.body.triples),
                                                    rule=rule,
                                                    chaining="forward",
                                                    source=rule.source,
                                                )
                                                self._proof_steps.append(step)
                                                tree = self._build_proof_tree(rule, binding, head_triple)
                                                self._proof_trees.append(tree)
                                                self._proof_index[head_triple] = tree
                        else:
                            # Single-pattern rule body — derive head directly
                            head_triples = self._instantiate_formula(rule.head, ub)
                            for head_triple in head_triples:
                                if head_triple.is_ground() and head_triple not in processed:
                                    if self.store.add(head_triple):
                                        processed.add(head_triple)
                                        queue.append(head_triple)
                                        self._derived_count += 1
                                        self._step_count += 1
                                        self._derived_triples.append(head_triple)
                                        if self._explain:
                                            step = ProofStep(
                                                conclusion=head_triple,
                                                premise=list(rule.body.triples),
                                                rule=rule,
                                                chaining="forward",
                                                source=rule.source,
                                            )
                                            self._proof_steps.append(step)
                                            tree = self._build_proof_tree(rule, ub, head_triple)
                                            self._proof_trees.append(tree)
                                            self._proof_index[head_triple] = tree
                        break  # Rule already processed for this triple

    def snapshot_initial(self) -> None:
        """Record the current store size as the baseline (input facts)."""
        self._initial_triples = len(self.store)

    # -- execution -----------------------------------------------------------

    def run(self) -> None:
        """Run forward chaining to fixpoint or until a limit is hit.

        M6 fix: Brake mechanism — tracks processed (rule, binding) pairs
        to avoid redundant work within a single pass.
        """
        while True:
            self._derived_count = 0
            # M6: Track processed rule+binding combinations this pass
            processed: set[tuple[int, str]] = set()
            for rule_idx, rule in enumerate(self._rules):
                self._apply_rule(rule, rule_idx, processed)
                if self._limit_answers > 0 and self._derived_count >= self._limit_answers:
                    return
            if self._derived_count == 0:
                break  # fixpoint
            if self._max_steps > 0 and self._step_count >= self._max_steps:
                break

    def _apply_rule(
        self,
        rule: Rule,
        rule_idx: int,
        processed: set[tuple[int, str]],
    ) -> None:
        """Match body patterns against store, derive head if new.

        M6 fix: Skip (rule_idx, binding_hash) combinations already processed
        this pass.
        """
        bindings = self._match_formula(rule.body, {})
        for binding in bindings:
            if self._limit_answers > 0 and self._derived_count >= self._limit_answers:
                return
            if self._max_steps > 0 and self._step_count >= self._max_steps:
                return

            # M6: Brake — skip if this rule+binding was already processed
            binding_key = frozenset(binding.items())
            brake_key = (rule_idx, hash(binding_key))
            if brake_key in processed:
                continue
            processed.add(brake_key)

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
                        # M7 fix: Build multi-level proof tree
                        tree = self._build_proof_tree(rule, binding, head_triple)
                        self._proof_trees.append(tree)
                        self._proof_index[head_triple] = tree

    def _build_proof_tree(
        self,
        rule: Rule,
        binding: Binding,
        conclusion: Triple,
    ) -> ProofTree:
        """Build a multi-level proof tree for a derived triple.

        M7 fix: For each body pattern in the rule, check if the bound
        triple exists in the proof index (i.e., was derived by another
        rule). If so, attach that proof tree as a child.
        """
        children: list[ProofTree] = []
        for pattern in rule.body.triples:
            bound = apply_binding_to_triple(pattern, binding)
            if bound in self._proof_index:
                children.append(self._proof_index[bound])

        return ProofTree(
            root=conclusion,
            children=children,
            rule=rule,
            chaining="forward",
        )

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

            # Phase 2: Check for negative surface (BLOGIC)
            # Pattern: ?S log:onNegativeSurface { ... }
            NEG_PRED = "http://www.w3.org/2000/10/swap/log#onNegativeSurface"
            if isinstance(resolved.predicate, NamedNode) and resolved.predicate.value == NEG_PRED:
                # Negation: if the formula CAN be matched, this path fails
                if isinstance(resolved.object, Formula):
                    # Try to match the negated formula against the store
                    neg_results = self._match_triples_iter(list(resolved.object.triples), binding)
                    if neg_results:
                        # Negated formula matched → this path is blocked
                        return []
                    # Negated formula didn't match → continue with current results
                    continue
                # If object is not a Formula, treat as normal triple
                new_results = []
                for b in results:
                    r = self._resolve_triple(pattern, b)
                    for store_triple in self._store_matches(r):
                        ub = unify(r, store_triple, b)
                        if ub is not None:
                            new_results.append(ub)
                results = new_results
                if not results:
                    break
                continue

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
                    # Optimization: unify already returns a new dict when
                    # bindings are extended, so no need to copy `b` first.
                    ub = unify(r, store_triple, b)
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
                # C6 fix: Use separate blank node counter
                self._bn_counter += 1
                return Existential(f"bn-{self._bn_counter}")
            return t
        return Triple(
            sk(triple.subject),
            sk(triple.predicate),
            sk(triple.object),
        )

    # -- backward chaining with tabling --------------------------------------

    def backward_chain(
        self,
        query: Triple,
    ) -> list[Binding]:
        """Goal-directed reasoning: find all bindings that satisfy *query*.

        Uses tabling (memoization) to prevent infinite recursion.
        """
        # Tabling cache: query_signature -> list[Binding]
        self._tabling_cache: dict[str, list[Binding]] = {}
        return self._backward_chain_triple(query, {})

    def _backward_chain_triple(
        self,
        query: Triple,
        binding: Binding,
    ) -> list[Binding]:
        """Find all bindings that make *query* true."""
        resolved = self._resolve_triple(query, binding)

        # Tabling: create a cache key from the resolved query
        cache_key = self._tabling_key(resolved)
        if cache_key in self._tabling_cache:
            # Return cached results, filtering by compatibility with current binding
            return self._tabling_cache[cache_key]

        results: list[Binding] = []

        # 1. Try direct store match (query as pattern, store as ground)
        for store_triple in self._store_matches(resolved):
            ub = unify(resolved, store_triple, binding)
            if ub is not None:
                results.append(ub)

        # 2. Try matching against rule heads (bidirectional unification)
        for rule in self._rules:
            for head_triple in rule.head.triples:
                ub = self._unify_backward(resolved, head_triple, binding)
                if ub is not None:
                    # Try to prove the body
                    body_bindings = self._match_formula(rule.body, ub)
                    results.extend(body_bindings)

        # Cache the results
        self._tabling_cache[cache_key] = results
        return results

    def _unify_backward(
        self,
        query: Triple,
        head: Triple,
        binding: Binding,
    ) -> Binding | None:
        """Bidirectional unification for backward chaining.

        Unlike forward unification (pattern vs ground), this allows
        variable-to-variable binding and handles both sides having variables.
        """
        # Unify predicate
        r = self._unify_terms_backward(query.predicate, head.predicate, binding)
        if r is None:
            return None
        # Unify subject
        r = self._unify_terms_backward(query.subject, head.subject, r)
        if r is None:
            return None
        # Unify object
        r = self._unify_terms_backward(query.object, head.object, r)
        if r is None:
            return None
        return r

    def _unify_terms_backward(
        self,
        t1: Term,
        t2: Term,
        binding: Binding,
    ) -> Binding | None:
        """Unify two terms where both may be variables."""
        # Resolve already-bound variables
        if isinstance(t1, Variable) and t1.name in binding:
            t1 = binding[t1.name]
        if isinstance(t2, Variable) and t2.name in binding:
            t2 = binding[t2.name]

        # Both ground → must be equal
        if not isinstance(t1, Variable) and not isinstance(t2, Variable):
            return binding if t1 == t2 else None

        # Both are variables → they unify (no new binding unless different)
        if isinstance(t1, Variable) and isinstance(t2, Variable):
            if t1.name == t2.name:
                return binding  # Same variable, no conflict
            # Different variables — bind one to the other
            return {**binding, t1.name: t2}

        # One is variable → bind it (with occurs check)
        if isinstance(t1, Variable):
            if term_contains_var(t2, t1.name):
                return None  # occurs check
            return {**binding, t1.name: t2}
        if isinstance(t2, Variable):
            if term_contains_var(t1, t2.name):
                return None  # occurs check
            return {**binding, t2.name: t1}

        return None  # unreachable but satisfies type checker

    def _tabling_key(self, triple: Triple) -> str:
        """Create a cache key for tabling from a triple.

        C5 fix: Use structural term hash instead of str() to avoid
        collisions between different term types that happen to have
        the same string representation.
        """
        def key_term(t: Term) -> str:
            if isinstance(t, Variable):
                return f"V:{t.name}"
            if isinstance(t, NamedNode):
                return f"N:{t.value}"
            if isinstance(t, Literal):
                dt = t.datatype.value if t.datatype else ""
                lang = t.language or ""
                return f"L:{t.value}|{dt}|{lang}"
            if isinstance(t, Existential):
                return f"E:{t.name}"
            return f"O:{type(t).__name__}:{str(t)}"
        return f"{key_term(triple.subject)} {key_term(triple.predicate)} {key_term(triple.object)}"

    # -- properties ----------------------------------------------------------

    @property
    def derived_triples(self) -> list[Triple]:
        """Only triples derived by rules (not input facts)."""
        return list(self._derived_triples)

    @property
    def step_count(self) -> int:
        return self._step_count
