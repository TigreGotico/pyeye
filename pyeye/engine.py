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

import time as _time

from pyeye.term import (
    NamedNode, Literal, Variable, Existential, Formula, Triple, Term, Binding,
    NegativeSurface,
)
from pyeye.unify import unify, apply_binding_to_triple, apply_binding, term_contains_var
from pyeye.store import TripleStore
from pyeye.parser import Rule
from pyeye.builtins import Builtin, BUILTIN_REGISTRY, MultiResult
from pyeye.proof import ProofStep, ProofTree


class ReasoningTimeoutError(RuntimeError):
    """Raised when the engine exceeds its wall-clock timeout.

    This prevents infinite loops caused by rules that generate an
    unbounded number of new triples (e.g. recursive rules without a
    base case, or rules that produce fresh blank nodes every step).

    Pass ``timeout_seconds=None`` to ``Engine`` or ``execute()`` to disable
    the guard (only do this if you are certain the rules terminate).
    """


class Engine:
    """Forward-chaining N3 reasoner (Euler Abstract Machine)."""

    def __init__(
        self,
        builtins: dict[str, Builtin] | None = None,
        max_steps: int = -1,
        limit_answers: int = -1,
        djiti_debug: bool = False,
        explain: bool = False,
        timeout_seconds: float | None = 30.0,
    ) -> None:
        self.store = TripleStore()
        self._rules: list[Rule] = []
        self._builtins: dict[str, Builtin] = {**BUILTIN_REGISTRY}
        if builtins:
            self._builtins.update(builtins)
        self._max_steps = max_steps
        self._limit_answers = limit_answers
        self._timeout_seconds = timeout_seconds
        self._deadline: float | None = None  # set at start of run()
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
        # Index of derived triple → proof tree for multi-level proofs
        self._proof_index: dict[Triple, ProofTree] = {}
        # Standardize-apart counter: monotonically increasing across all BC calls
        self._rename_counter = 0
        # Ephemeral list store for BC-instantiated list templates (avoids
        # polluting the main RDF store with Variable-valued triples).
        self._bc_list_store: dict[str, list[Term]] = {}
        # Tabling cache for backward chaining (None = not yet initialised)
        self._tabling_cache: dict[str, list[Binding]] | None = None
        self._bc_depth: int = 0
        # Predicates declared with log:table — use on-stack cycle detection
        self._tabled_predicates: set[str] = set()
        # On-stack set for tabled predicate cycle detection (normalized goal keys)
        self._bc_tabled_stack: set[str] = set()

    # -- population ----------------------------------------------------------

    def add_rule(self, rule: Rule) -> None:
        self._rules.append(rule)

    def add_triple(self, triple: Triple) -> bool:
        """Add a fact triple. Returns True if genuinely new."""
        new = self.store.add(triple)
        # Detect log:table directives stored as facts
        _LOG_TABLE = "http://www.w3.org/2000/10/swap/log#table"
        if isinstance(triple.predicate, NamedNode) and triple.predicate.value == _LOG_TABLE:
            if isinstance(triple.object, NamedNode):
                self._tabled_predicates.add(triple.object.value)
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

        M3 fix: @forSome bindings are tracked across all passes to prevent
        infinite derivation (each pass would generate a new skolem).
        """
        # Track processed bindings across all passes for @forSome rules
        global_processed: set[tuple[int, int]] = set()
        # Initialize tabling cache once per run() so BC results are stable
        # across fixpoint passes (prevents new ephemeral lists each pass).
        self._tabling_cache: dict[str, list[Binding]] = {}

        # Set wall-clock deadline for this run
        if self._timeout_seconds is not None:
            self._deadline = _time.monotonic() + self._timeout_seconds
        else:
            self._deadline = None

        while True:
            # Wall-clock timeout check (outer loop)
            if self._deadline is not None and _time.monotonic() > self._deadline:
                raise ReasoningTimeoutError(
                    f"Forward chaining exceeded {self._timeout_seconds}s timeout. "
                    "Use max_steps= to cap derivations or timeout_seconds=None to disable."
                )
            self._derived_count = 0
            # M6: Track processed rule+binding combinations this pass
            processed: set[tuple[int, str]] = set()
            for rule_idx, rule in enumerate(self._rules):
                if rule.is_backward:
                    continue  # backward rules are only used by BC, not forward engine
                self._apply_rule(rule, rule_idx, processed, global_processed, rule.for_some)
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
        global_processed: set[tuple[int, int]],
        for_some_vars: tuple[str, ...] = (),
    ) -> None:
        """Match body patterns against store, derive head if new.

        M6 fix: Skip (rule_idx, binding_hash) combinations already processed
        this pass.

        M3 fix: For @forSome rules, track base bindings across all passes
        to prevent infinite derivation.
        """
        bindings = self._match_formula(rule.body, {})
        for binding in bindings:
            if self._limit_answers > 0 and self._derived_count >= self._limit_answers:
                return
            if self._max_steps > 0 and self._step_count >= self._max_steps:
                return

            # M3 fix: Handle @forSome variables — replace unbound vars with fresh skolems
            for_some_binding = dict(binding)
            for var_name in for_some_vars:
                if var_name not in for_some_binding:
                    self._bn_counter += 1
                    for_some_binding[var_name] = Existential(f"forsome-{self._bn_counter}")

            # M3/M6 fix: Brake — skip if this base binding was already processed
            # For @forSome rules, check global_processed across all passes
            brake_binding = {k: v for k, v in for_some_binding.items() if k not in for_some_vars}
            binding_key = frozenset(brake_binding.items())
            brake_hash = hash(binding_key)
            brake_key_global = (rule_idx, brake_hash)

            if for_some_vars:
                # @forSome: check global brake across all passes
                if brake_key_global in global_processed:
                    continue
                global_processed.add(brake_key_global)
            else:
                # Normal rule: check per-pass brake
                brake_key_pass = (rule_idx, hash(frozenset(binding.items())))
                if brake_key_pass in processed:  # pragma: no cover — duplicate binding hash
                    continue
                processed.add(brake_key_pass)

            # Instantiate head
            head_triples = self._instantiate_formula(rule.head, for_some_binding)
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
                        tree = self._build_proof_tree(rule, for_some_binding, head_triple)
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

    def _is_builtin_pattern(self, pattern: Triple) -> bool:
        """Return True if the pattern's predicate is a registered builtin."""
        resolved_pred = pattern.predicate
        return (
            isinstance(resolved_pred, NamedNode)
            and resolved_pred.value in self._builtins
        )

    def _pattern_vars(self, pattern: Triple) -> set[str]:
        """Return the set of variable names referenced in the pattern."""
        vars_found: set[str] = set()
        for t in (pattern.subject, pattern.predicate, pattern.object):
            if isinstance(t, Variable):
                vars_found.add(t.name)
        return vars_found

    def _djiti_order(
        self,
        patterns: list[Triple],
        binding: Binding,
    ) -> list[Triple]:
        """Reorder patterns: store patterns first (fewest matches first),
        then builtin patterns in dependency order.

        Builtins must NEVER be sorted before the store patterns that bind
        their input variables, otherwise they execute with unbound variables
        and silently return None.
        """
        store_patterns: list[tuple[int, Triple]] = []
        builtin_patterns: list[tuple[int, Triple]] = []
        # Patterns that need backward chaining (0 store matches, not builtins)
        # should be deferred like builtins to ensure variables are bound first
        deferred_patterns: list[tuple[int, Triple]] = []

        for i, pattern in enumerate(patterns):
            if self._is_builtin_pattern(pattern):
                builtin_patterns.append((i, pattern))
            else:
                resolved = self._resolve_triple(pattern, binding)
                count = len(self._store_matches(resolved))
                if count == 0:
                    # No store matches — will need backward chaining, defer
                    deferred_patterns.append((i, pattern))
                else:
                    store_patterns.append((i, pattern))

        # Sort store patterns by match count (fewest first)
        store_counts: list[int] = []
        for _, pattern in store_patterns:
            resolved = self._resolve_triple(pattern, binding)
            store_counts.append(len(self._store_matches(resolved)))

        store_indexed = list(enumerate(store_patterns))
        store_indexed.sort(key=lambda pair: store_counts[pair[0]])
        ordered_store = [p for _, (_, p) in store_indexed]
        ordered_store_counts = [store_counts[i] for i, _ in store_indexed]

        # Sort builtins by dependency: those with most vars already bound go first
        bound_vars: set[str] = set(binding.keys())
        # Iteratively add vars as store patterns bind them
        for pattern in ordered_store:
            for t in (pattern.subject, pattern.predicate, pattern.object):
                if isinstance(t, Variable):
                    bound_vars.add(t.name)

        def builtin_output_var(pattern: Triple, store) -> set[str]:
            """Return variables that this builtin binds.

            Includes:
            - The object (usually the result variable)
            - For log:collectAllIn with Existential subject: extract variables from the RDF list
            """
            output = set()
            if isinstance(pattern.object, Variable):
                output.add(pattern.object.name)

            # Special case: log:collectAllIn with Existential subject binds variables in the list
            if (isinstance(pattern.predicate, NamedNode) and
                pattern.predicate.value == "http://www.w3.org/2000/10/swap/log#collectAllIn" and
                isinstance(pattern.subject, Existential)):
                # Extract variables from the RDF list at pattern.subject
                rdf_first = NamedNode("http://www.w3.org/1999/02/22-rdf-syntax-ns#first")
                rdf_rest = NamedNode("http://www.w3.org/1999/02/22-rdf-syntax-ns#rest")
                nil = Existential("nil")
                cur = pattern.subject
                visited: set[str] = set()
                while cur.name not in visited and cur.name != "nil":
                    visited.add(cur.name)
                    first_matches = list(store.match(subject=cur, predicate=rdf_first))
                    if first_matches:
                        elem = first_matches[0].object
                        if isinstance(elem, Variable):
                            output.add(elem.name)
                    rest_matches = list(store.match(subject=cur, predicate=rdf_rest))
                    if rest_matches:
                        cur = rest_matches[0].object
                    else:
                        break
            return output

        # Greedy topological sort: interleave builtins and deferred patterns by readiness
        ordered_late: list[Triple] = []
        remaining: list[tuple[int, Triple, str]] = []  # (orig_idx, pattern, kind)
        for idx, pat in builtin_patterns:
            remaining.append((idx, pat, "builtin"))
        for idx, pat in deferred_patterns:
            remaining.append((idx, pat, "deferred"))

        while remaining:
            best_idx = -1
            best_key = (float('inf'), float('inf'))
            for i, (orig_idx, pattern, kind) in enumerate(remaining):
                pvars = self._pattern_vars(pattern)
                unbound = len(pvars - bound_vars)
                key = (unbound, orig_idx)
                if key < best_key:
                    best_key = key
                    best_idx = i

            orig_idx, pattern, kind = remaining.pop(best_idx)
            ordered_late.append(pattern)
            # Track output variables
            if kind == "builtin":
                bound_vars.update(builtin_output_var(pattern, self.store))
            else:
                # Deferred patterns may bind their object variable
                if isinstance(pattern.object, Variable):
                    bound_vars.add(pattern.object.name)

        ordered = ordered_store + ordered_late
        ordered_counts = ordered_store_counts + [0] * len(ordered_late)

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
            _NEG_PREDS = {
                "http://eulersharp.sourceforge.net/2003/03swap/log-rules#onNegativeSurface",
                "http://www.w3.org/2000/10/swap/log#onNegativeSurface",
            }
            if isinstance(resolved.predicate, NamedNode) and resolved.predicate.value in _NEG_PREDS:
                # Negation: filter each accumulated binding individually.
                # The negated formula must fail for the binding to survive.
                if isinstance(resolved.object, Formula):
                    new_results = []
                    for b in results:
                        # Re-resolve the negative surface against the current binding
                        r = self._resolve_triple(pattern, b)
                        neg_form = list(r.object.triples) if isinstance(r.object, Formula) else list(resolved.object.triples)
                        neg_check = self._match_triples_iter(neg_form, b)
                        if not neg_check:
                            # Negated formula did NOT match for this binding → keep it
                            new_results.append(b)
                    results = new_results
                    if not results:
                        break
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

            # Normal triple: match against store, with backward chaining fallback
            new_results: list[Binding] = []
            for b in results:
                r = self._resolve_triple(pattern, b)
                # Pattern match: find all store triples that unify
                found = False
                for store_triple in self._store_matches(r):
                    ub = unify(r, store_triple, b)
                    if ub is not None:
                        new_results.append(ub)
                        found = True
                # Backward chaining fallback: if no store match, try proving via backward rules
                if not found:
                    bc_depth = getattr(self, '_bc_depth', 0)
                    if bc_depth < getattr(self, '_bc_depth_limit', 10):
                        self._bc_depth = bc_depth + 1
                        if self._tabling_cache is None:
                            self._tabling_cache = {}
                        try:
                            bc_results = self._backward_chain_triple(r, b)
                            for bc_b in bc_results:
                                new_results.append(bc_b)
                        finally:
                            self._bc_depth = bc_depth
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
            if not args:  # pragma: no cover — _collect_builtin_args always returns ≥1 element
                continue
            self._current_binding = b  # allow builtins to access current binding
            result = builtin(args, self)
            # Use the (possibly updated) binding from the builtin
            b = self._current_binding
            if result is None:
                continue  # unground args — skip
            if isinstance(result, MultiResult):
                # Generative builtin: extend binding once per result term
                for r_term in result.results:
                    if isinstance(builtin_obj, Variable):
                        new_b = dict(b)
                        new_b[builtin_obj.name] = r_term
                        results.append(new_b)
                    elif r_term == builtin_obj:
                        results.append(b)
                continue
            if isinstance(result, list):
                # Predicate-style: assert triples
                for t in result:
                    self.store.add(t)
                results.append(b)
            elif isinstance(result, Term):
                # Check for boolean result (success/fail predicate)
                # Only Literals have .value for "true"/"false" check
                if isinstance(result, Literal) and result.value in ("true", "false"):
                    if result.value == "true" and isinstance(builtin_obj, (Literal, NamedNode, Existential)):
                        # Boolean predicate succeeded (ground object)
                        results.append(b)
                        continue
                    elif result.value == "true" and isinstance(builtin_obj, Variable):
                        # Boolean predicate succeeded with unbound scope variable —
                        # bind scope to True and use the (possibly updated) binding
                        new_b = dict(b)
                        new_b[builtin_obj.name] = result
                        results.append(new_b)
                        continue
                    elif result.value == "false":
                        # Boolean predicate failed
                        continue
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

        When the subject is an RDF list, Variables inside that list are resolved
        using a rename-aware lookup that strips ``__rN`` suffixes from binding keys.
        This handles standardize-apart renamed rules where the list's Variables have
        original names but the binding uses renamed keys.
        """
        import re as _re_builtin
        args: list[Term] = []
        s = self._resolve_term(resolved.subject, binding)
        o = self._resolve_term(resolved.object, binding)
        # If subject is a list (Existential pointing to RDF list), expand it
        if isinstance(s, Existential):
            raw_items = self._expand_list(s)  # raw, no binding — get original Variable names
            for item in raw_items:
                if isinstance(item, Variable):
                    # Try exact name first, then strip rename suffix from binding keys
                    resolved_item = binding.get(item.name)
                    if resolved_item is None:
                        for key, val in binding.items():
                            base = _re_builtin.sub(r'__r\d+$', '', key)
                            if base == item.name:
                                resolved_item = val
                                break
                    args.append(resolved_item if resolved_item is not None else item)
                else:
                    args.append(item)
        else:
            args.append(s)
        args.append(o)
        return args

    def _make_list(self, items: list[Term]) -> Existential:
        """Create an ephemeral list for backward-chaining intermediate results.

        Stores the items directly in ``_bc_list_store`` (keyed by node name)
        instead of adding them to the main RDF store.  This prevents
        Variable-valued triples from polluting the store and triggering
        spurious forward-rule applications.
        """
        nil = Existential("nil")
        if not items:
            return nil
        self._bn_counter += 1
        name = f"_ml{self._bn_counter}"
        node = Existential(name)
        self._bc_list_store[name] = list(items)
        return node

    def _expand_list(self, head: Existential, binding: Binding | None = None) -> list[Term]:
        """Expand an RDF list starting at *head* into a Python list of Terms.

        *binding* is used to resolve Variable terms stored in the list
        (e.g. inline list subjects in rule bodies like ``(?A ?B) math:sum ?C``).

        Checks ``_bc_list_store`` first for ephemeral lists created by
        ``_make_list`` during backward chaining.
        """
        # Check ephemeral BC list store first
        if head.name in self._bc_list_store:
            raw = self._bc_list_store[head.name]
            if not binding:
                return list(raw)
            resolved = []
            for item in raw:
                if isinstance(item, Variable):
                    val = binding.get(item.name)
                    if val is None:
                        # Try chasing Variable→Variable chains
                        val = apply_binding(item, binding)
                    resolved.append(val if val is not None else item)
                else:
                    resolved.append(item)
            return resolved

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
                elem = first_matches[0].object
                # Resolve variable if binding provided (inline list in rule body).
                # Also try rename-aware lookup: strip ``__rN`` suffixes from binding
                # keys to handle standardize-apart renamed rule Variables.
                if binding and isinstance(elem, Variable):
                    val = binding.get(elem.name)
                    # If the exact match is absent or a Variable (ungrounded),
                    # search for the most-recently-suffixed concrete binding.
                    # E.g. B__r8=Literal(0) wins over B=Existential(_b22).
                    if val is None or isinstance(val, Variable) or isinstance(val, Existential):
                        import re as _re_exp
                        _r_pat = r'__r(\d+)$'
                        best_n = -1
                        best_v = None
                        for key, v in binding.items():
                            base = _re_exp.sub(_r_pat, '', key)
                            if base == elem.name:
                                m = _re_exp.search(_r_pat, key)
                                n = int(m.group(1)) if m else 0
                                if n > best_n:
                                    best_n = n
                                    best_v = v
                        if best_v is not None:
                            val = best_v
                    if val is not None:
                        elem = val
                result.append(elem)
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
        """Resolve a term through the binding, following Variable chains.

        Follows chains like ``R → route__r5 → _ml29`` that arise when BC
        binds a query variable to a rule variable that is later grounded.
        """
        if not isinstance(term, Variable):
            return term
        seen: set[str] = set()
        while isinstance(term, Variable) and term.name in binding:
            if term.name in seen:
                break  # cycle guard
            seen.add(term.name)
            term = binding[term.name]
        return term

    def _instantiate_formula(
        self,
        formula: Formula,
        binding: Binding,
    ) -> list[Triple]:
        """Create ground triples from the head formula with bindings applied.

        Only skolemize blank nodes that appear literally in the head formula
        template (not ones that arrived via variable binding from the body).
        """
        # Collect blank-node names that appear *directly* in the head template
        head_blanks: set[str] = set()
        for pattern in formula.triples:
            for term in (pattern.subject, pattern.predicate, pattern.object):
                if isinstance(term, Existential) and term.name.startswith("_b"):
                    head_blanks.add(term.name)

        # Build a per-instantiation mapping from template bnode → fresh skolem
        # so that shared bnodes in the head map to the SAME fresh node.
        bnode_map: dict[str, Existential] = {}

        result: list[Triple] = []
        for pattern in formula.triples:
            # Use _resolve_triple (chain-aware) instead of apply_binding_to_triple
            # to handle Variable→Variable bindings produced by backward chaining.
            t = self._resolve_triple(pattern, binding)
            t = self._skolemize(t, head_blanks, bnode_map)
            result.append(t)
        return result

    def _skolemize(
        self,
        triple: Triple,
        head_blanks: set[str] | None = None,
        bnode_map: dict[str, Existential] | None = None,
    ) -> Triple:
        """Replace anonymous blank nodes in the head with fresh skolem constants.

        Only blank nodes that appear literally in the head formula template
        (whose names are in *head_blanks*) are skolemized. Blank nodes that
        arrived via variable binding from the body are left untouched.
        """
        def sk(t: Term) -> Term:
            if not isinstance(t, Existential):
                return t
            if not t.name.startswith("_b"):
                return t
            # Only skolemize if it's a template bnode (not a body binding)
            if head_blanks is not None and t.name not in head_blanks:
                return t
            # Use consistent mapping within this instantiation
            if bnode_map is not None:
                if t.name not in bnode_map:
                    self._bn_counter += 1
                    bnode_map[t.name] = Existential(f"bn-{self._bn_counter}")
                return bnode_map[t.name]
            # Legacy path (called without head_blanks)
            self._bn_counter += 1
            return Existential(f"bn-{self._bn_counter}")

        return Triple(
            sk(triple.subject),
            sk(triple.predicate),
            sk(triple.object),
        )

    # -- backward chaining with tabling --------------------------------------

    def _rename_rule(self, rule: Rule) -> tuple[Rule, str]:
        """Return a renamed copy of *rule* and the suffix used.

        Appends ``__r{counter}`` to each Variable name so that recursive rule
        applications use distinct variable names (standardize-apart), preventing
        binding collisions.  Existentials (list structure nodes) are NOT renamed
        since they are keyed by rdf:first/rdf:rest triples in the store.

        Returns ``(renamed_rule, suffix)`` so callers can apply the suffix when
        expanding list-node Variables that were not yet renamed in the store.
        """
        self._rename_counter += 1
        suffix = f"__r{self._rename_counter}"

        def rename_term(t: Term) -> Term:
            if isinstance(t, Variable):
                return Variable(t.name + suffix)
            # Do NOT rename Existentials — they are list structure nodes
            # referenced by rdf:first/rdf:rest triples in the store.
            # Renaming them would break _expand_list lookups.
            return t

        def rename_triple(tr: Triple) -> Triple:
            return Triple(
                rename_term(tr.subject),
                rename_term(tr.predicate),
                rename_term(tr.object),
            )

        new_body = Formula(triples=[rename_triple(t) for t in rule.body.triples])
        new_head = Formula(triples=[rename_triple(t) for t in rule.head.triples])
        return Rule(body=new_body, head=new_head, source=rule.source), suffix

    def backward_chain(
        self,
        query: Triple,
    ) -> list[Binding]:
        """Goal-directed reasoning: find all bindings that satisfy *query*.

        Uses tabling (memoization) to prevent infinite recursion.
        """
        # Tabling cache: query_signature -> list[Binding]
        self._tabling_cache: dict[str, list[Binding]] = {}
        raw = self._backward_chain_triple(query, {})
        # Resolve Variable chains in results (from standardize-apart renaming)
        resolved = [self._resolve_binding_chains(b) for b in raw]
        # Deduplicate: keep only the query variables, discard renamed internals
        query_vars = {t.name for t in (query.subject, query.predicate, query.object)
                      if isinstance(t, Variable)}
        seen: set[tuple] = set()
        unique: list[Binding] = []
        for b in resolved:
            key = tuple(sorted((k, str(v)) for k, v in b.items() if k in query_vars))
            if key not in seen:
                seen.add(key)
                unique.append({k: v for k, v in b.items() if k in query_vars})
        return unique

    def _resolve_binding_chains(self, binding: Binding) -> Binding:
        """Follow Variable→Variable chains in a binding to ground values."""
        resolved = {}
        for key, val in binding.items():
            resolved[key] = self._resolve_term(val, binding)
        return resolved

    def _backward_chain_triple(
        self,
        query: Triple,
        binding: Binding,
    ) -> list[Binding]:
        """Find all bindings that make *query* true."""
        resolved = self._resolve_triple(query, binding)

        # On-stack cycle detection for tabled predicates.
        # Normalize Variables to "?" so renamed variants map to the same key.
        pred_val = resolved.predicate.value if isinstance(resolved.predicate, NamedNode) else None
        is_tabled = bool(pred_val and pred_val in self._tabled_predicates)
        if is_tabled:
            def _norm(t: Term) -> str:
                return "?" if isinstance(t, Variable) else str(t)
            goal_key = f"{_norm(resolved.subject)}|{_norm(resolved.predicate)}|{_norm(resolved.object)}"
            if goal_key in self._bc_tabled_stack:
                return []  # Cycle detected — cut recursion
            self._bc_tabled_stack.add(goal_key)

        # Tabling: key is based on the FULLY RESOLVED goal — expand Existential
        # list nodes with the current binding so that goals with the same
        # effective input (but different binding contexts) share a cache entry.
        cache_key = self._tabling_key(resolved, binding)
        if cache_key in self._tabling_cache:
            if is_tabled:
                self._bc_tabled_stack.discard(goal_key)
            return self._tabling_cache[cache_key]

        results: list[Binding] = []

        # 1. Try direct store match (query as pattern, store as ground)
        for store_triple in self._store_matches(resolved):
            ub = unify(resolved, store_triple, binding)
            if ub is not None:
                results.append(ub)

        # 2. Try matching against rule heads (bidirectional unification)
        for rule in self._rules:
            renamed, rename_suffix = self._rename_rule(rule)
            for head_triple in renamed.head.triples:
                ub = self._unify_backward(resolved, head_triple, binding, rename_suffix)
                if ub is not None:
                    # _expand_list now resolves rule-body list Variables using
                    # the most-recently-suffixed binding key, so no bridge needed.
                    body_bindings = self._match_formula(renamed.body, ub)
                    results.extend(body_bindings)

        # Resolve Variable→Variable chains before caching so callers get
        # fully grounded (or maximally resolved) bindings.
        results = [self._resolve_binding_chains(b) for b in results]
        # Cache the results
        self._tabling_cache[cache_key] = results
        if is_tabled:
            self._bc_tabled_stack.discard(goal_key)
        return results

    def _unify_backward(
        self,
        query: Triple,
        head: Triple,
        binding: Binding,
        rename_suffix: str = "",
    ) -> Binding | None:
        """Bidirectional unification for backward chaining.

        Unlike forward unification (pattern vs ground), this allows
        variable-to-variable binding and handles both sides having variables.

        *rename_suffix* is the standardize-apart suffix applied to the rule's
        Variables (e.g. ``__r3``).  When expanding RDF list nodes from the rule
        head, Variables found inside those lists are renamed with this suffix so
        they match the renamed body Variables.
        """
        # Unify predicate
        r = self._unify_terms_backward(query.predicate, head.predicate, binding, rename_suffix)
        if r is None:
            return None
        # Unify subject
        r = self._unify_terms_backward(query.subject, head.subject, r, rename_suffix)
        if r is None:
            return None
        # Unify object
        r = self._unify_terms_backward(query.object, head.object, r, rename_suffix)
        if r is None:
            return None
        return r

    def _unify_terms_backward(
        self,
        t1: Term,
        t2: Term,
        binding: Binding,
        rename_suffix: str = "",
    ) -> Binding | None:
        """Unify two terms where both may be variables or existentials.

        Existentials (blank nodes) in rule heads act as bindable variables
        during backward chaining — they represent quantified positions.

        *rename_suffix* is applied to Variables found inside list nodes that
        belong to the rule head (t2 side).  This aligns them with the renamed
        body Variables produced by ``_rename_rule``.
        """
        # Treat Existentials as bindable (like variables) for backward chaining
        # Exception: nil is the empty list terminator, not a variable
        def _is_bindable(t: Term) -> bool:
            if isinstance(t, Existential) and t.name == "nil":
                return False
            return isinstance(t, (Variable, Existential))

        def _name(t: Term) -> str:
            return t.name if isinstance(t, (Variable, Existential)) else ""

        def _apply_suffix(t: Term) -> Term:
            """Rename a Variable found inside a rule-head list node."""
            if rename_suffix and isinstance(t, Variable):
                return Variable(t.name + rename_suffix)
            return t

        # Resolve already-bound bindables
        if _is_bindable(t1) and _name(t1) in binding:
            t1 = binding[_name(t1)]
        if _is_bindable(t2) and _name(t2) in binding:
            t2 = binding[_name(t2)]

        # Both ground → must be equal
        if not _is_bindable(t1) and not _is_bindable(t2):
            return binding if t1 == t2 else None

        # Both Existentials → try structural list unification
        if isinstance(t1, Existential) and isinstance(t2, Existential):
            # Expand t1 (query) with binding, t2 (rule head) without binding.
            # Apply rename_suffix to Variables in the rule-head list so they
            # match the standardize-apart renamed body Variables.
            items1 = self._expand_list(t1, binding)
            items2 = [_apply_suffix(e) for e in self._expand_list(t2)]
            if items1 and items2 and len(items1) == len(items2):
                b = {**binding, _name(t1): t2}
                for e1, e2 in zip(items1, items2):
                    b = self._unify_terms_backward(e1, e2, b, rename_suffix)
                    if b is None:
                        return None
                return b
            if _name(t1) == _name(t2):
                return binding
            return {**binding, _name(t1): t2}

        # Both bindable → they unify.
        # Prefer binding a rule-head Variable (t2) to a query Existential (t1)
        # rather than the reverse, so that body Variables resolve correctly.
        if _is_bindable(t1) and _is_bindable(t2):
            if _name(t1) == _name(t2):
                return binding
            if isinstance(t2, Variable) and isinstance(t1, Existential):
                return {**binding, _name(t2): t1}
            return {**binding, _name(t1): t2}

        # One is bindable → bind it
        if _is_bindable(t1):
            # Occurs check: prevent circular binding
            if isinstance(t1, Variable) and term_contains_var(t2, _name(t1)):
                return None
            # If t1 is a list Existential, it can only unify with another
            # Existential (structural list unification), not a plain ground term.
            if isinstance(t1, Existential) and t1.name != "nil":
                if self._expand_list(t1):  # t1 IS a list
                    if not isinstance(t2, Existential):
                        return None  # list ≠ plain ground term
            # If t2 is a list Existential from the rule head, instantiate it
            # with renamed Variables so downstream expansions get concrete names.
            if isinstance(t2, Existential) and rename_suffix:
                items = self._expand_list(t2)
                if items:
                    renamed_items = [_apply_suffix(i) for i in items]
                    new_list = self._make_list(renamed_items)
                    return {**binding, _name(t1): new_list}
            return {**binding, _name(t1): t2}
        if _is_bindable(t2):
            if term_contains_var(t1, _name(t2)):
                return None  # occurs check failure
            # If t2 is a list Existential, it can only match another Existential
            # (structural list unification), not a plain NamedNode/Literal.
            if isinstance(t2, Existential) and t2.name != "nil":
                if self._expand_list(t2):  # t2 IS a list
                    if not isinstance(t1, Existential):
                        return None  # plain term ≠ list term
            return {**binding, _name(t2): t1}

        return None  # pragma: no cover

    def _tabling_key(self, triple: Triple, binding: "Binding | None" = None) -> str:
        """Create a cache key for tabling from a triple.

        When *binding* is provided, Existential list nodes and Variables are
        resolved through it so that goals with the same effective input share
        a cache entry even when their binding contexts differ.
        """
        import re as _re_tk
        _seen: set[str] = set()

        def key_term(t: Term) -> str:
            # Resolve Variables through binding
            if binding and isinstance(t, Variable):
                resolved = self._resolve_term(t, binding)
                if resolved is not t:
                    return key_term(resolved)
                # Un-resolved variable: normalize away suffix
                base = _re_tk.sub(r'__r\d+$', '', t.name)
                return f"V:{base}"
            if isinstance(t, Variable):
                base = _re_tk.sub(r'__r\d+$', '', t.name)
                return f"V:{base}"
            if isinstance(t, NamedNode):
                return f"N:{t.value}"
            if isinstance(t, Literal):
                dt = t.datatype.value if t.datatype else ""
                lang = t.language or ""
                return f"L:{t.value}|{dt}|{lang}"
            if isinstance(t, Existential):
                if t.name in _seen:
                    return f"E:{t.name}"  # cycle guard — do NOT discard, stay in seen
                _seen.add(t.name)
                # Check if the Existential itself is bound
                if binding and t.name in binding:
                    return key_term(binding[t.name])
                # Expand as list with binding for inner Variables
                items = self._expand_list(t, binding or {})
                if items:
                    return f"[{','.join(key_term(i) for i in items)}]"
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
