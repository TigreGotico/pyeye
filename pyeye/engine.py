"""N3 reasoning engine — forward and backward chaining with tabling.

The engine iterates over rules, matches body patterns against the triple
store, derives head instances, and repeats until fixpoint (no new
derivations in a full pass).  Backward chaining is available for
goal-directed queries and as a fallback during forward evaluation.

Variable scoping uses fresh ``Variable.id`` values (via ``copy_rule``)
instead of string-suffix renaming.  Bindings are keyed by ``Variable.id``
(int), never by name.

Public API
----------
``Engine``
    .. automethod:: add_rule
    .. automethod:: add_triple
    .. automethod:: run
    .. automethod:: backward_chain
    .. automethod:: derived_triples
"""

from __future__ import annotations

import time as _time
from typing import Any

from pyeye.term import (
    NamedNode, Literal, Variable, Existential, Formula, Triple, Term, Binding,
    ListTerm, NegativeSurface, _next_var_id,
)
from pyeye.unify import unify, unify_terms, apply_binding_to_triple, apply_binding, term_contains_var
from pyeye.store import TripleStore
from pyeye.parser import Rule
from pyeye.builtins import Builtin, BUILTIN_REGISTRY, MultiResult
from pyeye.proof import ProofStep, ProofTree


# ---------------------------------------------------------------------------
# Well-known IRIs
# ---------------------------------------------------------------------------

_LOG_IMPLIES = "http://www.w3.org/2000/10/swap/log#implies"
_LOG_TABLE = "http://www.w3.org/2000/10/swap/log#table"
_NEG_SURFACE_IRIS = frozenset({
    "http://eulersharp.sourceforge.net/2003/03swap/log-rules#onNegativeSurface",
    "http://www.w3.org/2000/10/swap/log#onNegativeSurface",
})


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class ContradictionError(RuntimeError):
    """Raised when a ``=> false`` constraint rule fires.

    In N3 logic, ``{ body } => false`` means the body must not hold.
    When the body is satisfied, the engine raises this exception.
    """


class ReasoningTimeoutError(RuntimeError):
    """Raised when the engine exceeds its wall-clock timeout.

    This prevents infinite loops caused by rules that generate an
    unbounded number of new triples.
    """


# ---------------------------------------------------------------------------
# Deep-copy with fresh variable IDs
# ---------------------------------------------------------------------------

def copy_rule(rule: Rule) -> Rule:
    """Deep-copy *rule*, replacing every Variable with a fresh one.

    Uses a ``{old_id: new_var}`` map built lazily on first encounter so
    that all occurrences of the same original Variable map to the same
    fresh Variable.  No string-suffix renaming — scoping is purely by ID.
    """
    var_map: dict[int, Variable] = {}

    def copy_term(t: Term) -> Term:
        if isinstance(t, Variable):
            if t.id not in var_map:
                var_map[t.id] = Variable(name=t.name, id=_next_var_id())
            return var_map[t.id]
        if isinstance(t, ListTerm):
            new_items = tuple(copy_term(item) for item in t.items)
            return ListTerm(items=new_items)
        if isinstance(t, Formula):
            new_triples = tuple(copy_triple(tr) for tr in t.triples)
            return Formula(triples=new_triples)
        if isinstance(t, NegativeSurface):
            new_formula = Formula(triples=tuple(
                copy_triple(tr) for tr in t.formula.triples
            ))
            return NegativeSurface(formula=new_formula)
        return t

    def copy_triple(tr: Triple) -> Triple:
        return Triple(
            copy_term(tr.subject),
            copy_term(tr.predicate),
            copy_term(tr.object),
        )

    new_body = Formula(triples=tuple(copy_triple(t) for t in rule.body.triples))
    new_head = Formula(triples=tuple(copy_triple(t) for t in rule.head.triples))
    return Rule(
        body=new_body,
        head=new_head,
        source=rule.source,
        for_some=rule.for_some,
        for_all=rule.for_all,
        is_backward=rule.is_backward,
        is_contradiction=rule.is_contradiction,
    )


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class Engine:
    """Forward-chaining N3 reasoner with backward-chaining fallback."""

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
        self._derived_rule_hashes: set[int] = set()
        self._builtins: dict[str, Builtin] = {**BUILTIN_REGISTRY}
        if builtins:
            self._builtins.update(builtins)
        self._max_steps = max_steps
        self._limit_answers = limit_answers
        self._timeout_seconds = timeout_seconds
        self._deadline: float | None = None
        self._step_count = 0
        self._derived_count = 0
        self._derived_triples: list[Triple] = []
        # Answer triples: head instantiations of --query rules (the output of a
        # query run, per EYE log:impliesAnswer semantics). Insertion-ordered,
        # deduplicated.
        self._answer_triples: list[Triple] = []
        self._answer_seen: set = set()
        self._initial_triples: int = 0
        self._bn_counter = 0
        self._skolem_counter = 0
        self._output_strings: list[Term] = []
        self._djiti_debug = djiti_debug
        self._djiti_log: list[dict] = []
        # Proof tracing
        self._explain = explain
        self._proof_steps: list[ProofStep] = []
        self._proof_trees: list[ProofTree] = []
        self._proof_index: dict[Triple, ProofTree] = {}
        # Tabling cache for backward chaining
        self._tabling_cache: dict[str, list[Binding]] | None = None
        # On-stack set for BC cycle detection (goal keys)
        self._bc_stack: set[str] = set()
        # Predicates declared with log:table
        self._tabled_predicates: set[str] = set()
        # Builtins still read this until step 5 rewrites them
        self._current_binding: Binding = {}

    # -- population ----------------------------------------------------------

    def add_rule(self, rule: Rule) -> None:
        """Add a rule to the engine."""
        self._rules.append(rule)

    def add_triple(self, triple: Triple) -> bool:
        """Add a fact triple. Returns True if genuinely new."""
        new = self.store.add(triple)
        # Detect log:table directives
        if (isinstance(triple.predicate, NamedNode)
                and triple.predicate.value == _LOG_TABLE
                and isinstance(triple.object, NamedNode)):
            self._tabled_predicates.add(triple.object.value)
        if new and self._rules:
            self._incremental_derive(triple)
        return new

    def _incremental_derive(self, new_triple: Triple) -> None:
        """Re-evaluate rules that could derive new facts from *new_triple*."""
        queue = [new_triple]
        processed: set[Triple] = {new_triple}

        while queue:
            current = queue.pop(0)
            for rule in self._rules:
                if rule.is_backward:
                    continue
                for pattern in rule.body.triples:
                    ub = unify(pattern, current, {})
                    if ub is not None:
                        other_patterns = [p for p in rule.body.triples if p is not pattern]
                        if other_patterns:
                            bindings = self._match_patterns_sequential(other_patterns, ub)
                        else:
                            bindings = [ub]
                        for binding in bindings:
                            head_triples = self._instantiate_formula(rule.head, binding)
                            for ht in head_triples:
                                if ht.is_ground() and ht not in processed:
                                    if self.store.add(ht):
                                        processed.add(ht)
                                        queue.append(ht)
                                        self._derived_count += 1
                                        self._step_count += 1
                                        self._derived_triples.append(ht)
                                        if self._explain:
                                            step = ProofStep(
                                                conclusion=ht,
                                                premise=list(rule.body.triples),
                                                rule=rule,
                                                chaining="forward",
                                                source=rule.source,
                                            )
                                            self._proof_steps.append(step)
                                            tree = self._build_proof_tree(rule, binding, ht)
                                            self._proof_trees.append(tree)
                                            self._proof_index[ht] = tree
                        break

    def snapshot_initial(self) -> None:
        """Record the current store size as the baseline (input facts)."""
        self._initial_triples = len(self.store)

    # -- execution -----------------------------------------------------------

    def run(self) -> None:
        """Run forward chaining to fixpoint or until a limit is hit.

        Tracks processed (rule, binding) pairs to avoid redundant work
        within a single pass.  For @forSome rules, tracks across all passes
        to prevent infinite derivation.
        """
        global_processed: set[tuple[int, int]] = set()
        self._tabling_cache = {}

        if self._timeout_seconds is not None:
            self._deadline = _time.monotonic() + self._timeout_seconds
        else:
            self._deadline = None

        while True:
            self._check_timeout()
            self._derived_count = 0
            processed: set[tuple[int, int]] = set()
            for rule_idx, rule in enumerate(self._rules):
                if rule.is_backward:
                    continue
                self._apply_rule(rule, rule_idx, processed, global_processed, rule.for_some)
                if self._limit_answers > 0 and self._derived_count >= self._limit_answers:
                    return
            if self._derived_count == 0:
                break
            if self._max_steps > 0 and self._step_count >= self._max_steps:
                break

    def _check_timeout(self) -> None:
        """Raise ReasoningTimeoutError if deadline exceeded."""
        if self._deadline is not None and _time.monotonic() > self._deadline:
            raise ReasoningTimeoutError(
                f"Forward chaining exceeded {self._timeout_seconds}s timeout. "
                "Use max_steps= to cap derivations or timeout_seconds=None to disable."
            )

    def _apply_rule(
        self,
        rule: Rule,
        rule_idx: int,
        processed: set[tuple[int, int]],
        global_processed: set[tuple[int, int]],
        for_some_vars: tuple[str, ...] = (),
    ) -> None:
        """Match body patterns against store, derive head if new.

        Brake mechanism: skip (rule_idx, binding_hash) combinations already
        processed this pass.  For @forSome rules, track across all passes.
        """
        self._check_timeout()
        bindings = self._match_formula(rule.body, {})
        for binding in bindings:
            self._check_timeout()
            if self._limit_answers > 0 and self._derived_count >= self._limit_answers:
                return
            if self._max_steps > 0 and self._step_count >= self._max_steps:
                return

            # Handle @forSome variables — replace unbound vars with fresh skolems
            for_some_binding = dict(binding)
            for var_name in for_some_vars:
                # Find variable IDs with this name that are unbound
                found = False
                for vid, val in binding.items():
                    if isinstance(val, Variable) and val.name == var_name:
                        found = True
                        break
                if not found:
                    self._bn_counter += 1
                    for_some_binding[var_name] = Existential(f"forsome-{self._bn_counter}")

            # Brake — skip duplicate bindings
            brake_binding = {k: v for k, v in for_some_binding.items()
                            if not isinstance(k, str) or k not in for_some_vars}
            binding_key = frozenset((k, str(v)) for k, v in brake_binding.items())
            brake_hash = hash(binding_key)
            brake_key = (rule_idx, brake_hash)

            if for_some_vars:
                if brake_key in global_processed:
                    continue
                global_processed.add(brake_key)
            else:
                if brake_key in processed:
                    continue
                processed.add(brake_key)

            # Contradiction check
            if rule.is_contradiction:
                raise ContradictionError(
                    f"Constraint violation: rule body is satisfiable — {rule}"
                )

            # Instantiate head
            head_triples = self._instantiate_formula(
                rule.head, for_some_binding,
                rule_id=rule.source or str(rule_idx),
            )
            for head_triple in head_triples:
                if self._limit_answers > 0 and self._derived_count >= self._limit_answers:
                    return
                if self._max_steps > 0 and self._step_count >= self._max_steps:
                    return

                # Derived rule promotion: {body} log:implies {head} → new Rule
                if (isinstance(head_triple.predicate, NamedNode)
                        and head_triple.predicate.value == _LOG_IMPLIES
                        and isinstance(head_triple.subject, Formula)
                        and isinstance(head_triple.object, Formula)):
                    rule_hash = hash((str(head_triple.subject), str(head_triple.object)))
                    if rule_hash not in self._derived_rule_hashes:
                        self._derived_rule_hashes.add(rule_hash)
                        derived_rule = Rule(
                            body=head_triple.subject,
                            head=head_triple.object,
                            source="derived",
                        )
                        self._rules.append(derived_rule)
                        self._derived_count += 1
                    continue

                if head_triple.is_ground() and self.store.add(head_triple):
                    self._derived_count += 1
                    self._step_count += 1
                    self._derived_triples.append(head_triple)

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

        For each body pattern, check if the bound triple was itself derived
        and attach its proof tree as a child.
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

    # -- pattern matching (core) ---------------------------------------------

    def _match_formula(
        self,
        formula: Formula,
        binding: Binding,
    ) -> list[Binding]:
        """Match all patterns in *formula* against the store.

        Returns a list of binding extensions.  Uses DJITI (most-constrained-
        first) ordering.  For each pattern:
        - Negative surface → NAF check
        - Builtin predicate → _handle_builtin()
        - Store match via unify()
        - BC fallback via _resolve_bc()
        """
        if not formula.triples:
            return [binding]

        patterns = list(formula.triples)
        patterns = self._djiti_order(patterns, binding)
        return self._match_patterns_sequential(patterns, binding)

    def _match_patterns_sequential(
        self,
        patterns: list[Triple],
        binding: Binding,
    ) -> list[Binding]:
        """Iteratively match patterns, accumulating bindings."""
        results: list[Binding] = [binding]

        for pattern in patterns:
            self._check_timeout()

            new_results: list[Binding] = []

            for b in results:
                resolved = apply_binding_to_triple(pattern, b)

                # Negative surface (NAF)
                if (isinstance(resolved.predicate, NamedNode)
                        and resolved.predicate.value in _NEG_SURFACE_IRIS):
                    if isinstance(resolved.object, Formula):
                        neg_patterns = list(resolved.object.triples)
                        neg_check = self._match_patterns_sequential(neg_patterns, b)
                        if not neg_check:
                            new_results.append(b)
                    elif isinstance(resolved.object, NegativeSurface):
                        neg_patterns = list(resolved.object.formula.triples)
                        neg_check = self._match_patterns_sequential(neg_patterns, b)
                        if not neg_check:
                            new_results.append(b)
                    else:
                        # Not a formula — treat as normal triple
                        for st in self._store_matches(resolved):
                            ub = unify(resolved, st, b)
                            if ub is not None:
                                new_results.append(ub)
                    continue

                # Builtin predicate
                if isinstance(resolved.predicate, NamedNode):
                    builtin = self._builtins.get(resolved.predicate.value)
                    if builtin is not None:
                        builtin_results = self._handle_builtin(builtin, pattern, [b])
                        new_results.extend(builtin_results)
                        continue

                # Normal triple: store match + BC fallback
                found = False
                for st in self._store_matches(resolved):
                    ub = unify(resolved, st, b)
                    if ub is not None:
                        new_results.append(ub)
                        found = True

                if not found:
                    bc_results = self._resolve_bc(resolved, b)
                    new_results.extend(bc_results)

            results = new_results
            if not results:
                break

        return results

    def _store_matches(self, pattern: Triple) -> list[Triple]:
        """Find store triples matching the (partially resolved) pattern.

        Passes subject=None if subject is a ListTerm (store can't index by it).
        """
        s = pattern.subject
        if isinstance(s, (Variable, ListTerm)):
            s = None
        p = pattern.predicate if not isinstance(pattern.predicate, Variable) else None
        o = pattern.object
        if isinstance(o, (Variable, ListTerm)):
            o = None
        return list(self.store.match(subject=s, predicate=p, object=o))

    # -- DJITI ordering ------------------------------------------------------

    def _is_builtin_pattern(self, pattern: Triple) -> bool:
        """Return True if the pattern's predicate is a registered builtin."""
        return (isinstance(pattern.predicate, NamedNode)
                and pattern.predicate.value in self._builtins)

    def _pattern_var_ids(self, pattern: Triple) -> set[int]:
        """Return Variable IDs referenced in the pattern."""
        ids: set[int] = set()
        for t in (pattern.subject, pattern.predicate, pattern.object):
            if isinstance(t, Variable):
                ids.add(t.id)
            elif isinstance(t, ListTerm):
                for item in t.items:
                    if isinstance(item, Variable):
                        ids.add(item.id)
        return ids

    def _pattern_input_var_ids(self, pattern: Triple) -> set[int]:
        """Variable IDs that must be *bound before* a builtin pattern fires.

        Treats the object slot as the builtin's output and, for a ListTerm
        subject (e.g. ``(Tmpl {Pattern} ?Out) log:collectAllIn ?Scope``), the
        trailing list item as an output too.  Formula items declare their own
        scope and are not counted as required inputs.
        """
        ids: set[int] = set()
        s = pattern.subject
        if isinstance(s, Variable):
            ids.add(s.id)
        elif isinstance(s, ListTerm):
            items = list(s.items)
            # last item is the conventional output slot for collect-style builtins
            for item in items[:-1] if len(items) > 1 else items:
                if isinstance(item, Variable):
                    ids.add(item.id)
        if isinstance(pattern.predicate, Variable):
            ids.add(pattern.predicate.id)
        # object is the output slot — not a required input
        return ids

    def _djiti_order(
        self,
        patterns: list[Triple],
        binding: Binding,
    ) -> list[Triple]:
        """Reorder patterns: store patterns first (fewest matches first),
        then builtins/deferred in dependency order.

        Builtins must never be sorted before the store patterns that bind
        their input variables.
        """
        store_patterns: list[tuple[int, Triple, int]] = []  # (orig_idx, pattern, count)
        builtin_patterns: list[tuple[int, Triple]] = []
        deferred_patterns: list[tuple[int, Triple]] = []

        for i, pattern in enumerate(patterns):
            if self._is_builtin_pattern(pattern):
                builtin_patterns.append((i, pattern))
            else:
                resolved = apply_binding_to_triple(pattern, binding)
                count = len(self._store_matches(resolved))
                if count == 0:
                    deferred_patterns.append((i, pattern))
                else:
                    store_patterns.append((i, pattern, count))

        # Sort store patterns by match count ascending
        store_patterns.sort(key=lambda x: x[2])
        ordered_store = [p for _, p, _ in store_patterns]
        ordered_store_counts = [c for _, _, c in store_patterns]

        # Track bound variable IDs
        bound_ids: set[int] = set(binding.keys())
        for pattern in ordered_store:
            bound_ids.update(self._pattern_var_ids(pattern))

        # Greedy topological sort for builtins and deferred patterns
        remaining: list[tuple[int, Triple, str]] = []
        for idx, pat in builtin_patterns:
            remaining.append((idx, pat, "builtin"))
        for idx, pat in deferred_patterns:
            remaining.append((idx, pat, "deferred"))

        ordered_late: list[Triple] = []
        while remaining:
            best_idx = -1
            best_key = (float('inf'), float('inf'), float('inf'))
            for i, (orig_idx, pattern, kind) in enumerate(remaining):
                pvars = self._pattern_var_ids(pattern)
                unbound = len(pvars - bound_ids)
                # A builtin is "ready" only when its INPUT vars are bound; the
                # object slot is the output and may stay unbound.  Counting
                # unbound *inputs* lets a producer (e.g. log:collectAllIn that
                # binds ?List) schedule before its consumer (math:sum on ?List),
                # which the plain fewest-unbound heuristic gets backwards.
                input_vars = self._pattern_input_var_ids(pattern)
                unbound_inputs = len(input_vars - bound_ids)
                key = (unbound_inputs, unbound, orig_idx)
                if key < best_key:
                    best_key = key
                    best_idx = i

            orig_idx, pattern, kind = remaining.pop(best_idx)
            ordered_late.append(pattern)
            # Track output variables
            if isinstance(pattern.object, Variable):
                bound_ids.add(pattern.object.id)
            if isinstance(pattern.subject, Variable):
                bound_ids.add(pattern.subject.id)
            if isinstance(pattern.subject, ListTerm):
                for item in pattern.subject.items:
                    if isinstance(item, Variable):
                        bound_ids.add(item.id)

        ordered = ordered_store + ordered_late
        ordered_counts = ordered_store_counts + [0] * len(ordered_late)

        if self._djiti_debug:
            self._djiti_log.append({
                "original": [str(p) for p in patterns],
                "ordered": [str(p) for p in ordered],
                "counts": ordered_counts,
            })

        return ordered

    # -- builtin handling ----------------------------------------------------

    def _collect_builtin_args(self, resolved: Triple, binding: Binding) -> list[Term]:
        """Extract arguments for a builtin from the resolved triple.

        If subject is a ListTerm, iterate .items resolving each via
        apply_binding().  Always append object.
        """
        args: list[Term] = []
        s = self._resolve_term(resolved.subject, binding)
        o = self._resolve_term(resolved.object, binding)

        if isinstance(s, ListTerm):
            for item in s.items:
                resolved_item = apply_binding(item, binding)
                args.append(resolved_item)
        else:
            args.append(s)
        args.append(o)
        return args

    def _handle_builtin(
        self,
        builtin: Builtin,
        pattern: Triple,
        input_bindings: list[Binding],
    ) -> list[Binding]:
        """Evaluate a builtin predicate and filter/extend bindings."""
        results: list[Binding] = []
        for b in input_bindings:
            resolved = apply_binding_to_triple(pattern, b)
            builtin_obj = resolved.object
            args = self._collect_builtin_args(resolved, b)
            if not args:
                continue
            self._current_binding = b
            try:
                result = builtin(args, self)
            except (TypeError, ValueError, ZeroDivisionError):
                continue
            # Pick up any binding updates from the builtin
            b = self._current_binding

            if result is None:
                continue

            if isinstance(result, MultiResult):
                for r_term in result.results:
                    if isinstance(builtin_obj, Variable):
                        new_b = dict(b)
                        new_b[builtin_obj.id] = r_term
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
                if isinstance(result, Literal) and result.value in ("true", "false"):
                    if result.value == "true":
                        if isinstance(builtin_obj, Variable):
                            new_b = dict(b)
                            new_b[builtin_obj.id] = result
                            results.append(new_b)
                        else:
                            results.append(b)
                        continue
                    else:
                        continue  # false → filter out

                # Function-style result
                if isinstance(builtin_obj, Variable):
                    new_b = dict(b)
                    new_b[builtin_obj.id] = result
                    results.append(new_b)
                elif result == builtin_obj:
                    results.append(b)
        return results

    # -- term resolution -----------------------------------------------------

    def _resolve_term(self, term: Term, binding: Binding) -> Term:
        """Resolve a term through the binding, following Variable→Variable chains.

        Also resolves ListTerm items recursively.
        """
        if isinstance(term, Variable):
            seen: set[int] = set()
            while isinstance(term, Variable) and term.id in binding:
                if term.id in seen:
                    break
                seen.add(term.id)
                term = binding[term.id]
            return term
        if isinstance(term, ListTerm):
            new_items = tuple(self._resolve_term(item, binding) for item in term.items)
            return ListTerm(items=new_items) if new_items != term.items else term
        return term

    # -- instantiation -------------------------------------------------------

    def _instantiate_formula(
        self,
        formula: Formula,
        binding: Binding,
        rule_id: str = "",
    ) -> list[Triple]:
        """Create ground triples from the head formula with bindings applied.

        Skolemizes Existentials that appear literally in the head template.
        Skolem names are stable: same rule + same binding → same blank node.
        """
        # Collect blank-node names that appear directly in the head template
        head_blanks: set[str] = set()
        for pattern in formula.triples:
            for term in (pattern.subject, pattern.predicate, pattern.object):
                if isinstance(term, Existential) and term.name.startswith("_b"):
                    head_blanks.add(term.name)

        # Build stable skolem mapping
        binding_key = "_".join(f"{k}={v}" for k, v in sorted(
            (str(k), str(v)) for k, v in binding.items()
        ))
        bnode_map: dict[str, Existential] = {}
        for bn in sorted(head_blanks):
            key = f"{rule_id}|{bn}|{binding_key}"
            skolem_name = f"sk-{abs(hash(key)) % (10**9)}"
            bnode_map[bn] = Existential(skolem_name)

        result: list[Triple] = []
        for pattern in formula.triples:
            t = apply_binding_to_triple(pattern, binding)
            t = self._skolemize(t, head_blanks, bnode_map)
            result.append(t)
        return result

    def _skolemize(
        self,
        triple: Triple,
        head_blanks: set[str] | None = None,
        bnode_map: dict[str, Existential] | None = None,
    ) -> Triple:
        """Replace template blank nodes with stable skolem constants."""
        def sk(t: Term) -> Term:
            if not isinstance(t, Existential):
                return t
            if not t.name.startswith("_b"):
                return t
            if head_blanks is not None and t.name not in head_blanks:
                return t
            if bnode_map is not None:
                if t.name in bnode_map:
                    return bnode_map[t.name]
                self._bn_counter += 1
                mapped = Existential(f"bn-{self._bn_counter}")
                bnode_map[t.name] = mapped
                return mapped
            self._bn_counter += 1
            return Existential(f"bn-{self._bn_counter}")

        return Triple(sk(triple.subject), sk(triple.predicate), sk(triple.object))

    # -- backward chaining ---------------------------------------------------

    def backward_chain(self, query: Triple) -> list[Binding]:
        """Goal-directed reasoning: find all bindings that satisfy *query*.

        Uses tabling (memoization) and on-stack cycle detection.
        """
        self._tabling_cache = {}
        self._bc_stack = set()
        raw = self._resolve_bc(query, {})

        # Resolve Variable chains in results
        resolved = [self._resolve_binding_chains(b) for b in raw]

        # Deduplicate: keep only the query variables
        query_var_ids = {t.id for t in (query.subject, query.predicate, query.object)
                        if isinstance(t, Variable)}
        seen: set[tuple] = set()
        unique: list[Binding] = []
        for b in resolved:
            key = tuple(sorted((k, str(v)) for k, v in b.items() if k in query_var_ids))
            if key not in seen:
                seen.add(key)
                unique.append({k: v for k, v in b.items() if k in query_var_ids})
        return unique

    def _resolve_bc(
        self,
        pattern: Triple,
        binding: Binding,
    ) -> list[Binding]:
        """Backward-chain resolution for a single pattern.

        For each backward (and forward) rule: copy_rule(), unify_terms()
        against each head triple, then _match_formula(body, head_binding).

        On-stack tabling: check if the fully-resolved goal key is on
        _bc_stack.  If yes, return [].  Cache results.
        """
        resolved = apply_binding_to_triple(pattern, binding)

        # Goal key for cycle detection and caching
        goal_key = self._goal_key(resolved, binding)

        # On-stack cycle detection
        if goal_key in self._bc_stack:
            return []

        # Tabling cache lookup
        if self._tabling_cache is None:
            self._tabling_cache = {}
        if goal_key in self._tabling_cache:
            return self._tabling_cache[goal_key]

        self._bc_stack.add(goal_key)

        results: list[Binding] = []

        # 1. Try direct store match
        for store_triple in self._store_matches(resolved):
            ub = unify(resolved, store_triple, binding)
            if ub is not None:
                results.append(ub)

        # 2. Try matching against rule heads
        for rule in self._rules:
            renamed = copy_rule(rule)
            for head_triple in renamed.head.triples:
                ub = unify_terms(resolved.predicate, head_triple.predicate, binding)
                if ub is None:
                    continue
                ub = unify_terms(resolved.subject, head_triple.subject, ub)
                if ub is None:
                    continue
                ub = unify_terms(resolved.object, head_triple.object, ub)
                if ub is None:
                    continue
                # Head unified — now match the body
                body_bindings = self._match_formula(renamed.body, ub)
                results.extend(body_bindings)

        # Resolve chains before caching
        results = [self._resolve_binding_chains(b) for b in results]

        self._tabling_cache[goal_key] = results
        self._bc_stack.discard(goal_key)
        return results

    def _resolve_binding_chains(self, binding: Binding) -> Binding:
        """Follow Variable→Variable chains in a binding to ground values."""
        resolved: Binding = {}
        for key, val in binding.items():
            resolved[key] = self._resolve_term(val, binding)
        return resolved

    def _goal_key(self, triple: Triple, binding: Binding) -> str:
        """Create a cache key for tabling from a resolved triple.

        Resolves all Variables and ListTerm items through the binding.
        """
        def key_term(t: Term) -> str:
            t = self._resolve_term(t, binding)
            if isinstance(t, Variable):
                return "?"
            if isinstance(t, NamedNode):
                return f"N:{t.value}"
            if isinstance(t, Literal):
                dt = t.datatype.value if t.datatype else ""
                lang = t.language or ""
                return f"L:{t.value}|{dt}|{lang}"
            if isinstance(t, Existential):
                return f"E:{t.name}"
            if isinstance(t, ListTerm):
                inner = ",".join(key_term(item) for item in t.items)
                return f"[{inner}]"
            if isinstance(t, Formula):
                inner = ";".join(
                    f"{key_term(tr.subject)} {key_term(tr.predicate)} {key_term(tr.object)}"
                    for tr in t.triples
                )
                return f"{{{inner}}}"
            return f"O:{type(t).__name__}:{str(t)}"

        return f"{key_term(triple.subject)} {key_term(triple.predicate)} {key_term(triple.object)}"

    # -- properties ----------------------------------------------------------

    @property
    def derived_triples(self) -> list[Triple]:
        """Only triples derived by rules (not input facts)."""
        return list(self._derived_triples)

    @property
    def answer_triples(self) -> list[Triple]:
        """Head instantiations of --query rules (EYE query-answer semantics)."""
        return list(self._answer_triples)

    def has_query_rules(self) -> bool:
        return any(getattr(r, "is_query", False) for r in self._rules)

    def collect_answers(self) -> list[Triple]:
        """Re-evaluate every --query rule against the final store and collect
        all ground head instantiations as the answer set.

        A query rule ``{P} => {C}`` contributes, for each binding that satisfies
        ``P``, the instantiation of ``C``.  Answers are collected regardless of
        whether the triple already exists in the store (EYE outputs the matched
        conclusions, not only newly-derived facts).
        """
        for rule in self._rules:
            if not getattr(rule, "is_query", False):
                continue
            for binding in self._match_formula(rule.body, {}):
                for ht in self._instantiate_formula(rule.head, binding):
                    if not ht.is_ground():
                        continue
                    if ht not in self._answer_seen:
                        self._answer_seen.add(ht)
                        self._answer_triples.append(ht)
        return list(self._answer_triples)

    @property
    def step_count(self) -> int:
        return self._step_count
