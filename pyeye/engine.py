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
    ListTerm, NegativeSurface, TripleTerm, _next_var_id,
)
from pyeye.unify import unify, unify_terms, apply_binding_to_triple, apply_binding, term_contains_var
from pyeye.store import TripleStore
from pyeye.parser import Rule
from pyeye.builtins import (
    Builtin, BUILTIN_REGISTRY, MultiResult, BindingsList, numeric_equal,
)
from pyeye.proof import ProofStep, ProofTree


# ---------------------------------------------------------------------------
# Well-known IRIs
# ---------------------------------------------------------------------------

_LOG_IMPLIES = "http://www.w3.org/2000/10/swap/log#implies"
_LOG_TABLE = "http://www.w3.org/2000/10/swap/log#table"
_LOG_CALL_WITH_CUT = "http://www.w3.org/2000/10/swap/log#callWithCut"
_NEG_SURFACE_IRIS = frozenset({
    "http://eulersharp.sourceforge.net/2003/03swap/log-rules#onNegativeSurface",
    "http://www.w3.org/2000/10/swap/log#onNegativeSurface",
})


def _is_nonground_tripleterm(term: Term) -> bool:
    """Return True if *term* is a TripleTerm that contains a Variable.

    A ground TripleTerm can be looked up by exact equality in the store
    index, but one with variables inside must be matched element-wise by
    the unifier, so the store must not pre-filter on it.
    """
    return isinstance(term, TripleTerm) and not term.is_ground()


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


def _premise_existentials_to_vars(rule: Rule) -> Rule:
    """Rewrite blank nodes occurring in *rule*'s premise as fresh Variables.

    A blank node in a rule premise is existentially quantified over the rule,
    so for matching purposes it behaves as a universal variable (``[ :p ?V ]``
    patterns must match any node).  Occurrences of the same blank node in the
    conclusion share the variable; blank nodes appearing only in the
    conclusion keep their existential reading (fresh node per instantiation).
    """
    ex_map: dict[str, Variable] = {}

    def conv(t: Term, create: bool) -> Term:
        if isinstance(t, Existential):
            if t.name in ex_map:
                return ex_map[t.name]
            if create:
                ex_map[t.name] = Variable(name=t.name, id=_next_var_id())
                return ex_map[t.name]
            return t
        if isinstance(t, ListTerm):
            return ListTerm(items=tuple(conv(i, create) for i in t.items))
        if isinstance(t, Formula):
            return Formula(triples=tuple(conv_triple(tr, create) for tr in t.triples))
        if isinstance(t, NegativeSurface):
            return NegativeSurface(formula=Formula(triples=tuple(
                conv_triple(tr, create) for tr in t.formula.triples)))
        return t

    def conv_triple(tr: Triple, create: bool) -> Triple:
        return Triple(conv(tr.subject, create), conv(tr.predicate, create),
                      conv(tr.object, create))

    body = Formula(triples=tuple(conv_triple(t, True) for t in rule.body.triples))
    if not ex_map:
        return rule
    head = Formula(triples=tuple(conv_triple(t, False) for t in rule.head.triples))
    return Rule(
        body=body,
        head=head,
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
        # Answer table for SLG-style tabling, scoped to one top-level _solve.
        # gk -> {"answers": list[Triple], "seen": set, "complete": bool}.
        self._answer_table: dict[str, dict] | None = None
        self._table_stack: list[str] = []
        # Completed answer-table entries from the last top-level solve, valid
        # while the store mutation counter matches _table_cache_version.
        self._table_cache: dict[str, dict] | None = None
        self._table_cache_version: int = -1
        # On-stack set for BC cycle detection (goal keys)
        self._bc_stack: set[str] = set()
        # Predicates declared with log:table
        self._tabled_predicates: set[str] = set()
        # Builtins still read this until step 5 rewrites them
        self._current_binding: Binding = {}
        # The resolved goal triple of the builtin call in flight; lets variadic
        # builtins distinguish the engine-appended object slot from inputs.
        self._current_pattern: Triple | None = None

    # -- population ----------------------------------------------------------

    def add_rule(self, rule: Rule) -> None:
        """Add a rule to the engine."""
        self._rules.append(_premise_existentials_to_vars(rule))

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
                if rule.is_query:
                    # Query-rule conclusions are answers, not derived facts:
                    # they never feed forward inference.  collect_answers()
                    # evaluates them once against the final closure.
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

            # Handle @forSome variables — bind each unbound head variable whose
            # name is existentially quantified to a fresh skolem.  Bindings are
            # keyed by Variable.id, so the head's own variable ids are used.
            for_some_binding = dict(binding)
            skolem_ids: set[int] = set()
            if for_some_vars:
                for head_triple in rule.head.triples:
                    for term in (head_triple.subject,
                                 head_triple.predicate,
                                 head_triple.object):
                        if (isinstance(term, Variable)
                                and term.name in for_some_vars
                                and term.id not in for_some_binding):
                            self._bn_counter += 1
                            for_some_binding[term.id] = Existential(
                                f"forsome-{self._bn_counter}")
                            skolem_ids.add(term.id)

            # Brake — skip duplicate bindings (exclude the fresh skolems, which
            # differ on every pass and would otherwise defeat the brake).
            brake_binding = {k: v for k, v in for_some_binding.items()
                            if k not in skolem_ids}
            binding_key = frozenset((k, str(v)) for k, v in brake_binding.items())
            brake_hash = hash(binding_key)
            brake_key = (rule_idx, brake_hash)

            if for_some_vars or rule.is_query:
                # Query-rule heads are answers, not new facts: reprocessing a
                # binding on a later pass can never derive anything new, so
                # brake across passes.
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
        """Iteratively match patterns, accumulating bindings.

        A builtin goal that fails while it still carries unbound variables may
        merely be unevaluable in this direction (its inputs are bound by a
        later goal that the DJITI ordering misjudged) — such a goal is pushed
        back and retried after the remaining goals; a failure with bound
        inputs falsifies the conjunction.
        """
        results: list[Binding] = [binding]

        queue: list[Triple] = list(patterns)
        deferrals = 0
        while queue:
            pattern = queue.pop(0)
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
                    if builtin is not None and self._builtin_applies(resolved):
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
                    new_results.extend(self._solve([pattern], b))

            if not new_results:
                if (queue and deferrals < len(queue)
                        and any(self._goal_maybe_unready(pattern, b)
                                for b in results)):
                    queue.append(pattern)
                    deferrals += 1
                    continue
                return []
            results = new_results
            deferrals = 0

        return results

    def _store_matches(self, pattern: Triple) -> list[Triple]:
        """Find store triples matching the (partially resolved) pattern.

        Passes subject=None if subject is a ListTerm (store can't index by it).
        """
        s = pattern.subject
        if (isinstance(s, (Variable, ListTerm, Formula))
                or _is_nonground_tripleterm(s)):
            # Formula slots match by set semantics (triple order/duplicates
            # do not matter), so the exact-key index cannot pre-filter them.
            s = None
        p = pattern.predicate if not isinstance(pattern.predicate, Variable) else None
        o = pattern.object
        if (isinstance(o, (Variable, ListTerm, Formula))
                or _is_nonground_tripleterm(o)):
            o = None
        return list(self.store.match(subject=s, predicate=p, object=o))

    # -- DJITI ordering ------------------------------------------------------

    def _is_builtin_pattern(self, pattern: Triple) -> bool:
        """Return True if the pattern's predicate is a registered builtin."""
        return (isinstance(pattern.predicate, NamedNode)
                and pattern.predicate.value in self._builtins)

    def _pattern_var_ids(self, pattern: Triple) -> set[int]:
        """Return Variable IDs referenced in the pattern.

        Static per pattern, so the result is cached on the triple itself —
        goal ordering consults it many times per conjunction level.
        """
        cached = getattr(pattern, "_pvar_ids", None)
        if cached is not None:
            return cached
        ids: set[int] = set()
        for t in (pattern.subject, pattern.predicate, pattern.object):
            if isinstance(t, Variable):
                ids.add(t.id)
            elif isinstance(t, ListTerm):
                for item in t.items:
                    if isinstance(item, Variable):
                        ids.add(item.id)
        object.__setattr__(pattern, "_pvar_ids", ids)
        return ids

    # Builtins that can run with an unbound subject when the object side is
    # bound (split / construct modes).  None of their variables are *required*
    # inputs; subject variables they may bind count as produced outputs so
    # consumer goals wait for them.
    # Builtins whose object slot is a required input (filter semantics), not
    # an output to bind.
    _OBJECT_INPUT_IRIS = frozenset({
        "http://www.w3.org/2000/10/swap/math#greaterThan",
        "http://www.w3.org/2000/10/swap/math#lessThan",
        "http://www.w3.org/2000/10/swap/math#notLessThan",
        "http://www.w3.org/2000/10/swap/math#notGreaterThan",
        "http://www.w3.org/2000/10/swap/math#equalTo",
        "http://www.w3.org/2000/10/swap/math#notEqualTo",
        "http://www.w3.org/2000/10/swap/list#notMember",
        "http://www.w3.org/2000/10/swap/log#notEqualTo",
    })

    _BIDIRECTIONAL_IRIS = frozenset({
        "http://www.w3.org/2000/10/swap/list#append",
        "http://www.w3.org/2000/10/swap/list#firstRest",
        "http://www.w3.org/2000/10/swap/list#select",
        "http://eulersharp.sourceforge.net/2003/03swap/log-rules#firstRest",
    })

    def _is_bidirectional_pattern(self, pattern: Triple) -> bool:
        return (isinstance(pattern.predicate, NamedNode)
                and pattern.predicate.value in self._BIDIRECTIONAL_IRIS)

    def _pattern_input_var_ids(self, pattern: Triple) -> set[int]:
        """Variable IDs that must be *bound before* a builtin pattern fires.

        Treats the object slot as the builtin's output and, for a ListTerm
        subject (e.g. ``(Tmpl {Pattern} ?Out) log:collectAllIn ?Scope``), the
        trailing list item as an output too.  Formula items declare their own
        scope and are not counted as required inputs.
        """
        cached = getattr(pattern, "_pinput_ids", None)
        if cached is not None:
            return cached
        ids: set[int] = set()
        s = pattern.subject
        pred = (pattern.predicate.value
                if isinstance(pattern.predicate, NamedNode) else "")
        if pred in self._BIDIRECTIONAL_IRIS:
            object.__setattr__(pattern, "_pinput_ids", ids)
            return ids
        is_forallin = pred.endswith("/log#forAllIn")
        if pred.endswith("/log#ifThenElseIn") and isinstance(s, ListTerm):
            # The condition formula runs under the bindings available at call
            # time; its variables (shared with sibling goals, e.g. the queen
            # picked by list:select) are required inputs — running the
            # conditional first would commit to an arbitrary instantiation.
            items = list(s.items)
            if items and isinstance(items[0], Formula):
                self._collect_var_ids(items[0], ids)
            object.__setattr__(pattern, "_pinput_ids", ids)
            return ids
        if isinstance(s, Variable):
            ids.add(s.id)
        elif isinstance(s, ListTerm):
            items = list(s.items)
            # The trailing list item is an OUTPUT slot only for collect-style
            # builtins whose subject embeds a quoted Formula pattern, e.g.
            # ``(Tmpl {Pattern} ?Out) log:collectAllIn ?Scope``.  For ordinary
            # list-subject builtins (``(?A ?B ?C) math:sum ?S``) every list
            # item is a required input.
            has_formula = any(isinstance(it, Formula) for it in items)
            scan = (items[:-1] if (has_formula and len(items) > 1) else items)
            for item in scan:
                if isinstance(item, Variable):
                    ids.add(item.id)
                elif is_forallin and isinstance(item, Formula):
                    # log:forAllIn's condition formula may reference outer
                    # variables produced by an earlier builtin (e.g. ?B from
                    # log:allPossibleCases); those must be bound before it runs.
                    self._collect_var_ids(item, ids)
        if isinstance(pattern.predicate, Variable):
            ids.add(pattern.predicate.id)
        # object is the output slot — not a required input
        object.__setattr__(pattern, "_pinput_ids", ids)
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

        # Variables produced as the OUTPUT of a builtin pattern.  A store
        # pattern that references such a variable as an *input* must wait for
        # the producing builtin, otherwise it would match unrelated store
        # triples (e.g. the recursive ``?N1 :sum ?Sum1`` greedily matching the
        # base fact ``0 :sum 0`` before ``math:difference`` binds ?N1).
        produced_ids: set[int] = set()
        for i, pattern in enumerate(patterns):
            if self._is_builtin_pattern(pattern):
                pvars = self._pattern_var_ids(pattern)
                inputs = self._pattern_input_var_ids(pattern)
                produced_ids.update(pvars - inputs)

        bound_keys = set(binding.keys())
        for i, pattern in enumerate(patterns):
            if self._is_builtin_pattern(pattern):
                builtin_patterns.append((i, pattern))
                continue
            input_vars = self._pattern_input_var_ids(pattern)
            unbound_inputs = input_vars - bound_keys
            if unbound_inputs & produced_ids:
                # An input is produced by a builtin → defer to the topo phase.
                deferred_patterns.append((i, pattern))
                continue
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
            # Variables produced as the output of a *still-remaining* builtin.
            # A consumer whose unbound input is produced by another remaining
            # builtin must wait for that producer, even if it superficially has
            # fewer unbound inputs (e.g. ``?C math:notLessThan 3`` must not run
            # before ``(?C1 ?C2 ?C3) math:sum ?C`` produces ?C).
            pending_outputs: set[int] = set()
            for _oi, pat, _k in remaining:
                pvars = self._pattern_var_ids(pat)
                inputs = self._pattern_input_var_ids(pat)
                pending_outputs.update(pvars - inputs)

            best_idx = -1
            best_key = (1, float('inf'), float('inf'), float('inf'))
            for i, (orig_idx, pattern, kind) in enumerate(remaining):
                pvars = self._pattern_var_ids(pattern)
                unbound = len(pvars - bound_ids)
                # A builtin is "ready" only when its INPUT vars are bound; the
                # object slot is the output and may stay unbound.  Counting
                # unbound *inputs* lets a producer (e.g. log:collectAllIn that
                # binds ?List) schedule before its consumer (math:sum on ?List),
                # which the plain fewest-unbound heuristic gets backwards.
                input_vars = self._pattern_input_var_ids(pattern)
                if kind == "deferred":
                    # A rule/store goal has no output slot: every unbound
                    # variable — including the object — is a join key that a
                    # pending builtin may produce.  Posing it first would run
                    # recursion with an unbound argument (divergence risk).
                    input_vars = pvars
                elif self._is_bidirectional_pattern(pattern):
                    # A split/construct builtin is evaluable once either side
                    # is ground; while both sides are unbound it consumes all
                    # its variables (must wait for some producer).
                    s_ids: set[int] = set()
                    o_ids: set[int] = set()
                    self._collect_var_ids(pattern.subject, s_ids)
                    self._collect_var_ids(pattern.object, o_ids)
                    if (s_ids - bound_ids) and (o_ids - bound_ids):
                        input_vars = pvars
                unbound_inputs = input_vars - bound_ids
                # Blocked iff an unbound input is produced by another remaining
                # pattern.  Own outputs come from the input/output slot split
                # (not the widened input_vars above): a deferred rule goal is
                # the producer of its non-subject variables and must not block
                # on them, or its consumers win the tie-break and run first.
                own_outputs = pvars - self._pattern_input_var_ids(pattern)
                blocked = 1 if (unbound_inputs & (pending_outputs - own_outputs)) else 0
                key = (blocked, len(unbound_inputs), unbound, orig_idx)
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

    # rdf:first / rdf:rest double as list accessors over a native ListTerm
    # subject AND as ordinary RDF-list store data (``_:b rdf:first :a``).  They
    # act as builtins only when the subject is a native list; otherwise they
    # must be matched against the store like any data triple.
    _LIST_ACCESSOR_IRIS = frozenset({
        "http://www.w3.org/1999/02/22-rdf-syntax-ns#first",
        "http://www.w3.org/1999/02/22-rdf-syntax-ns#rest",
    })

    def _builtin_applies(self, resolved: Triple) -> bool:
        """Whether the builtin for *resolved*'s predicate should fire here."""
        pred = resolved.predicate
        if (isinstance(pred, NamedNode)
                and pred.value in self._LIST_ACCESSOR_IRIS):
            return isinstance(resolved.subject, ListTerm)
        return True

    def _collect_builtin_args(self, resolved: Triple, binding: Binding) -> list[Term]:
        """Extract arguments for a builtin from the resolved triple.

        If subject is a ListTerm, iterate .items resolving each via
        apply_binding().  Always append object.
        """
        args: list[Term] = []
        s = self._resolve_term(resolved.subject, binding)
        o = self._resolve_term(resolved.object, binding)

        if isinstance(s, ListTerm) and s.items:
            for item in s.items:
                resolved_item = apply_binding(item, binding)
                args.append(resolved_item)
        else:
            # Keep an empty ListTerm as a single argument so builtins such as
            # ``() list:length ?L`` see the (empty) list rather than nothing —
            # expanding it away is indistinguishable from an unbound subject.
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
            self._current_pattern = resolved
            try:
                result = builtin(args, self)
            except (TypeError, ValueError, ZeroDivisionError):
                continue
            finally:
                self._current_pattern = None
            # Pick up any binding updates from the builtin
            b = self._current_binding

            if result is None:
                continue

            if isinstance(result, BindingsList):
                # Meta-builtin produced several full binding extensions
                # (e.g. generative list:member that unifies a pattern object
                # carrying variables against each list element).
                results.extend(result.bindings)
                continue

            if isinstance(result, MultiResult):
                for r_term in result.results:
                    if isinstance(builtin_obj, Variable):
                        new_b = dict(b)
                        new_b[builtin_obj.id] = r_term
                        results.append(new_b)
                    elif r_term == builtin_obj or numeric_equal(r_term, builtin_obj):
                        results.append(b)
                continue

            if isinstance(result, list):
                # Predicate-style: assert triples
                for t in result:
                    self.store.add(t)
                results.append(b)
            else:
                # Only Term results remain (list/MultiResult/BindingsList/None
                # handled above); avoid the runtime-checkable Protocol
                # isinstance, which is costly on hot paths.
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
                elif result == builtin_obj or numeric_equal(result, builtin_obj):
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
        """Goal-directed reasoning: find all bindings that satisfy *query*."""
        raw = self._solve([query], {})

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

    # -- answer-table tabling (SLG-style) ------------------------------------

    def _solve(self, goals: list[Triple], binding: Binding) -> list[Binding]:
        """Solve a conjunction of *goals*, returning every binding extension.

        This is the tabled (memoising) front door for backward chaining.  A
        per-session *answer table* maps each resolved goal — keyed by its ground
        skeleton — to the set of answer substitutions proved for it.  A subgoal
        solved once at one depth is reused (its answers shared) instead of being
        recomputed, so overlapping recursion (ackermann, takeuchi, fibonacci) is
        polynomial rather than exponential, and a deep linear recursion (sum of
        the first n, deep taxonomies) stays linear because each level's answer is
        materialised as a ground fact rather than threaded through an O(depth)
        binding chain.

        The table lives for one top-level ``_solve`` call; nested ``_solve``
        invocations (NAF graphs, builtins that re-enter the engine) reuse the
        live table, so a subgoal proved once is shared across the whole proof.
        Negative surfaces and builtins are evaluated per goal in
        :meth:`_solve_goal`; only rule expansion is tabled.

        Proof depth lives on the Python call stack (one frame band per recursive
        level).  Deeply recursive rule sets terminate but descend far past
        CPython's default limit, so the limit is raised for the duration of a
        top-level solve.  ``execute`` additionally runs on a large-stack worker
        thread; callers that drive very deep recursion through the bare ``Engine``
        API should do likewise to avoid a hard C-stack overflow.
        """
        if not goals:
            return [dict(binding)]

        owns_table = self._answer_table is None
        prev_limit: int | None = None
        if owns_table:
            # Reuse the previous top-level call's completed table while the
            # store is unchanged (its mutation counter is the cache key), so
            # repeated goal-directed queries over one closure — e.g. a query
            # rule iterating ``log:repeat`` over a recursive predicate —
            # share subgoal answers instead of recomputing each chain.
            if (self._table_cache is not None
                    and self._table_cache_version == self.store.version):
                self._answer_table = self._table_cache
            else:
                self._answer_table = {}
            self._table_stack = []
            import sys as _sys
            prev_limit = _sys.getrecursionlimit()
            if prev_limit < 200_000:
                _sys.setrecursionlimit(200_000)
        try:
            return self._solve_conj(goals, dict(binding))
        finally:
            if owns_table:
                # Only completed entries are reusable across calls.
                self._table_cache = {
                    k: v for k, v in self._answer_table.items() if v["complete"]
                }
                self._table_cache_version = self.store.version
                self._answer_table = None
                self._table_stack = []
                if prev_limit is not None:
                    import sys as _sys
                    _sys.setrecursionlimit(prev_limit)

    def _solve_conj(self, goals: list[Triple], binding: Binding) -> list[Binding]:
        """Recursively solve a conjunction over the answer table.

        Goals are taken in the order chosen by :meth:`_djiti_order` (which keeps
        builtins after the goals that bind their inputs and orders store goals by
        selectivity), with one backward-chaining refinement: among the goals
        whose variables are already ready, a plain store/rule goal that currently
        has *zero* candidate matches is taken first so an unsatisfiable body fails
        fast on its empty goal rather than expanding a recursive sibling with an
        unbound join key (which would table the recursion at its most general
        form and turn a linear search quadratic).

        Each selected goal's solutions extend the binding; the continuation is
        solved under every extension.  Proof depth lives on the Python stack of
        nested ``_table_goal`` calls (run on the engine's large-stack worker).
        """
        if not goals:
            # Empty body (a fact-rule) is vacuously true under the binding.
            return [binding]
        if len(goals) == 1:
            return self._solve_goal(goals[0], binding)

        idx = self._select_goal(goals, binding)
        order = [idx] + [i for i in range(len(goals)) if i != idx]
        for i in order:
            first = goals[i]
            sols = self._solve_goal(first, binding)
            if sols:
                rest = goals[:i] + goals[i + 1:]
                results: list[Binding] = []
                for b in sols:
                    results.extend(self._solve_conj(rest, b))
                return results
            # No solutions: a builtin whose resolved form still carries unbound
            # variables may merely be unevaluable in this direction (e.g. the
            # construct mode of a bidirectional builtin scheduled before its
            # inputs are bound) — try another goal first and revisit it later.
            # An evaluable goal with no solutions falsifies the conjunction.
            if not self._goal_maybe_unready(first, binding):
                return []
        return []

    def _goal_maybe_unready(self, goal: Triple, binding: Binding) -> bool:
        """Whether *goal* failing under *binding* may mean "not yet evaluable".

        True only for builtin goals that carry unbound variables on *both*
        sides: a bidirectional builtin can run as soon as either side is
        ground (decompose with a ground subject, construct/split with a
        ground object), so a failure with one ground side is a genuine
        refutation — deferring it would let sibling recursion run with an
        unbound argument and diverge (e.g. ``() list:firstRest (?Y ?Ys)``
        must fail its clause, not be retried later).
        """
        resolved = apply_binding_to_triple(goal, binding)
        pred = resolved.predicate
        if not isinstance(pred, NamedNode):
            return False
        if pred.value in _NEG_SURFACE_IRIS:
            return False
        if pred.value not in self._builtins or not self._builtin_applies(resolved):
            return False
        s_ids: set[int] = set()
        o_ids: set[int] = set()
        self._collect_var_ids(resolved.subject, s_ids)
        self._collect_var_ids(resolved.object, o_ids)
        if self._is_bidirectional_pattern(resolved):
            # Evaluable as soon as either side is ground — a failure with one
            # ground side is a genuine refutation.
            return bool(s_ids) and bool(o_ids)
        # Function-style builtins take inputs in the subject; filter-style
        # ones (comparisons, notMember) also read the object.  A failure with
        # an unbound required input means "not yet evaluable".
        if pred.value in self._OBJECT_INPUT_IRIS:
            return bool(s_ids) or bool(o_ids)
        return bool(s_ids)

    def _select_goal(self, goals: list[Triple], binding: Binding) -> int:
        """Pick the index of the next goal to solve.

        A plain store/rule goal whose key components are bound enough to have
        *zero* candidate matches is chosen first (fail fast).  Otherwise the
        first goal in :meth:`_djiti_order` is used, preserving the builtin
        input/output scheduling that ``_djiti_order`` already gets right.
        """
        # Fail-fast: an unsatisfiable plain store goal short-circuits the body.
        for i, goal in enumerate(goals):
            resolved = apply_binding_to_triple(goal, binding)
            pred = resolved.predicate
            if not isinstance(pred, NamedNode):
                continue
            if pred.value in self._builtins and self._builtin_applies(resolved):
                continue
            if pred.value in _NEG_SURFACE_IRIS:
                continue
            # Plain goal: if it has no store match and no rule can derive it, the
            # whole conjunction is doomed — solve it now so the branch dies here.
            if not self._store_matches(resolved) and not self._goal_has_rule(resolved):
                return i
        # Otherwise follow DJITI's schedule.
        ordered = self._djiti_order(goals, binding)
        first = ordered[0]
        for i, g in enumerate(goals):
            if g is first:
                return i
        return 0

    def _solve_goal(self, goal: Triple, binding: Binding) -> list[Binding]:
        """Solve a single *goal*, returning binding extensions of *binding*.

        Negative surfaces and builtins are evaluated here directly (extending
        the caller's binding) so the surrounding conjunction's other bindings
        survive — routing them through the resolvent solver would garbage-collect
        sibling-goal variables it cannot see.  A goal whose predicate matches no
        rule head is a pure store lookup; a rule-defined predicate is tabled.
        """
        resolved = apply_binding_to_triple(goal, binding)

        if isinstance(resolved.predicate, NamedNode):
            # Negative surface (NAF): succeed iff the negated graph is unprovable.
            if resolved.predicate.value in _NEG_SURFACE_IRIS:
                neg: list[Triple] | None = None
                if isinstance(resolved.object, Formula):
                    neg = list(resolved.object.triples)
                elif isinstance(resolved.object, NegativeSurface):
                    neg = list(resolved.object.formula.triples)
                if neg is not None:
                    return [binding] if not self._solve(neg, binding) else []
                # object is not a formula: fall through to a normal match.
            else:
                builtin = self._builtins.get(resolved.predicate.value)
                if builtin is not None and self._builtin_applies(resolved):
                    return self._handle_builtin(builtin, goal, [binding])

        # Only rule-defined predicates benefit from (and need) tabling.  A goal
        # that no rule head can unify with is a pure store lookup — solve it
        # directly without a table entry.
        if not self._goal_has_rule(resolved):
            out: list[Binding] = []
            for st in self._store_matches(resolved):
                nb = unify(resolved, st, binding)
                if nb is not None:
                    out.append(nb)
            return out

        # Tabled goal: get answer skeletons, then unify each against the live
        # goal under the caller's binding so the caller's variables are bound.
        answers = self._table_goal(resolved)
        out = []
        for ans in answers:
            nb = unify(resolved, ans, binding)
            if nb is not None:
                out.append(nb)
        return out

    def _goal_has_rule(self, resolved: Triple) -> bool:
        """Return True if some rule head could unify with *resolved*.

        A cheap predicate-level pre-filter (exact predicate match or a variable
        predicate on either side) avoids creating table entries for pure facts.
        """
        gp = resolved.predicate
        for rule in self._rules:
            for ht in rule.head.triples:
                hp = ht.predicate
                if isinstance(gp, Variable) or isinstance(hp, Variable):
                    return True
                if isinstance(gp, NamedNode) and isinstance(hp, NamedNode):
                    if gp.value == hp.value:
                        return True
                elif gp == hp:
                    return True
        return False

    @staticmethod
    def _rule_has_cut(rule: Rule) -> bool:
        """Return True if *rule*'s body contains a ``log:callWithCut`` goal.

        Such a clause is deterministic: once it fires for a goal, the remaining
        clauses for that goal are pruned (a Prolog-style cut).
        """
        for t in rule.body.triples:
            if (isinstance(t.predicate, NamedNode)
                    and t.predicate.value == _LOG_CALL_WITH_CUT):
                return True
        return False

    def _table_goal(self, resolved: Triple) -> list[Triple]:
        """Return the set of answer triples for *resolved* via the answer table.

        Each answer is the goal's pattern instantiated by one proof, with any
        residual variables renamed to a private namespace so answers from
        different proofs (and different callers) never alias.  Completed entries
        are reused verbatim; an entry currently being generated (a recursive
        re-entry on the same key) returns the answers known *so far* — the
        generator's fixpoint loop reruns until that set stops growing, which is
        what makes genuinely cyclic recursion terminate at the least fixpoint.
        """
        self._check_timeout()
        gk = self._goal_key(resolved, {})
        table = self._answer_table
        entry = table.get(gk)

        if entry is not None:
            # Completed → reuse.  In-progress (a re-entry while this goal is
            # still being generated) → return the answers known so far and flag
            # the entry cyclic, so its generator knows to iterate to a fixpoint.
            if not entry["complete"]:
                entry["cyclic"] = True
            return list(entry["answers"])

        entry = {"answers": [], "seen": set(), "complete": False, "cyclic": False}
        table[gk] = entry
        self._table_stack.append(gk)
        try:
            while True:
                self._check_timeout()
                grew = False

                # Way 1: facts already in the store.
                for st in self._store_matches(resolved):
                    if unify(resolved, st, {}) is not None:
                        if self._table_add_answer(entry, st):
                            grew = True

                # Way 2: each rule whose head unifies with the goal, in source
                # order.  A clause guarded by ``log:callWithCut`` that produces a
                # solution *cuts* — it commits the goal to that clause and skips
                # the remaining clauses, exactly as a Prolog cut prunes choice
                # points.  This is what makes guarded base cases (takeuchi,
                # ackermann) tractable: once the base case fires, the open-ended
                # recursive clause is never explored for that goal.
                cut = False
                for rule in self._rules:
                    if cut:
                        break
                    has_cut = self._rule_has_cut(rule)
                    renamed = copy_rule(rule)
                    for rhead in renamed.head.triples:
                        hb = unify(resolved, rhead, {})
                        if hb is None:
                            continue
                        body = list(renamed.body.triples)
                        fired = False
                        for sol in self._solve_conj(body, hb):
                            fired = True
                            ans = apply_binding_to_triple(rhead, sol)
                            ans = self._canonicalize_answer(ans)
                            if self._table_add_answer(entry, ans):
                                grew = True
                        if has_cut and fired:
                            cut = True
                            break
                # A non-cyclic goal is fully solved in a single pass: re-running
                # would only re-derive the same answers.  Only a goal that was
                # consumed recursively while still in progress needs the
                # fixpoint loop (its first pass saw an incomplete answer set).
                if not grew or not entry["cyclic"]:
                    break
            entry["complete"] = True
            return list(entry["answers"])
        finally:
            self._table_stack.pop()

    @staticmethod
    def _table_add_answer(entry: dict, ans: Triple) -> bool:
        """Add *ans* to a table entry if new (by canonical string). Returns True
        if it was genuinely new."""
        key = (str(ans.subject), str(ans.predicate), str(ans.object))
        if key in entry["seen"]:
            return False
        entry["seen"].add(key)
        entry["answers"].append(ans)
        return True

    def _canonicalize_answer(self, triple: Triple) -> Triple:
        """Rename residual variables in an answer to a private namespace.

        Answer triples are unified against fresh caller goals later; renaming to
        fresh ids keeps two proofs' leftover variables from colliding and keeps
        the answer independent of the ids used while proving it.
        """
        var_map: dict[int, Variable] = {}

        def cv(t: Term) -> Term:
            if isinstance(t, Variable):
                if t.id not in var_map:
                    var_map[t.id] = Variable(name=t.name, id=_next_var_id())
                return var_map[t.id]
            if isinstance(t, ListTerm):
                return ListTerm(items=tuple(cv(i) for i in t.items))
            if isinstance(t, Formula):
                return Formula(triples=tuple(
                    Triple(cv(tr.subject), cv(tr.predicate), cv(tr.object))
                    for tr in t.triples))
            return t

        return Triple(cv(triple.subject), cv(triple.predicate), cv(triple.object))

    def _solve_resolvent(self, goals: list[Triple], binding: Binding) -> list[Binding]:
        """Iterative SLD resolution of a conjunction of *goals*.

        Returns every binding (an extension of *binding*) under which all goals
        hold.  Proving a goal via a backward/forward rule rewrites the resolvent
        — the goal is replaced by the rule's body — so proof *depth* lives on an
        explicit heap stack, never the Python call stack.  This is the structural
        reason deep recursion (fibonacci, deep taxonomies) needs no raised
        recursion limit and no oversized thread stack.

        Resolvent entries are either ``Triple`` goals or ``("POP", gk, mark)``
        markers that close a goal's scope.

        * **Cycle termination.** Each branch carries an ``ancestors`` frozenset of
          goal keys currently being expanded.  A goal already among its own
          ancestors is matched against facts but not re-expanded through rules,
          which bounds left/self-recursive rules.
        * **Compact bindings.** ``mark`` records the variable-id watermark taken
          before a rule's fresh variables are allocated.  When the goal's scope
          closes, every variable introduced inside that subtree is dropped (after
          the goal's own variables are resolved to ground), so a linear recursion
          keeps an O(1) binding per level instead of accumulating O(depth).
        """
        solutions: list[Binding] = []
        # The resolvent is an immutable cons list of cells ``(item, tail, live)``
        # / ``None``.  Popping the next goal and prepending a rule body are both
        # O(1), and forked branches share tails without copying.  ``live`` caches
        # the set of variable ids referenced by every goal from this cell onward,
        # computed incrementally on prepend; it lets scope-exit GC keep only the
        # variables the *continuation* still needs (O(width)) instead of scanning
        # the whole binding (O(depth)) — the difference between linear and
        # quadratic on deep recursion.
        def _cell(item, tail):
            tail_live = tail[2] if tail is not None else frozenset()
            if isinstance(item, tuple):  # POP marker — references no variables
                return (item, tail, tail_live)
            ids: set[int] = set()
            self._collect_var_ids(item.subject, ids)
            self._collect_var_ids(item.predicate, ids)
            self._collect_var_ids(item.object, ids)
            return (item, tail, frozenset(ids) | tail_live)

        def _prepend(items: list, tail):
            for it in reversed(items):
                tail = _cell(it, tail)
            return tail

        # The caller reads back the bindings of the top-level goals' variables,
        # so those must survive every scope-exit GC even after their goal has
        # been consumed and is no longer in the continuation's live set.
        root_live: set[int] = set()
        for g in goals:
            self._collect_var_ids(g.subject, root_live)
            self._collect_var_ids(g.predicate, root_live)
            self._collect_var_ids(g.object, root_live)
        root_live_fs = frozenset(root_live)

        # Each work item: (resolvent_conslist, binding, ancestors)
        stack: list[tuple] = [(_prepend(list(goals), None), dict(binding), frozenset())]

        while stack:
            self._check_timeout()
            resolvent, b, anc = stack.pop()
            if resolvent is None:
                solutions.append(b)
                continue

            item, rest, live = resolvent

            # Keep the binding from accumulating on a deep descent: once it
            # grows well past what the resolvent still references, compact it to
            # the live variables (plus the top-level query's), each resolved to
            # ground.  Guarding on size means shallow proofs — the vast majority
            # — never pay for GC, while deep linear recursion stays O(width) per
            # level instead of O(depth), keeping the whole proof linear.
            b = self._gc_binding(b, live | root_live_fs)

            # Scope-close marker: just leave the goal's ancestor scope.
            if isinstance(item, tuple):
                _tag, gk = item
                stack.append((rest, b, anc - {gk}))
                continue

            goal: Triple = item
            resolved = apply_binding_to_triple(goal, b)

            # 1. Negative surface (NAF) — succeeds iff the negated graph has no proof.
            if (isinstance(resolved.predicate, NamedNode)
                    and resolved.predicate.value in _NEG_SURFACE_IRIS):
                neg: list[Triple] | None = None
                if isinstance(resolved.object, Formula):
                    neg = list(resolved.object.triples)
                elif isinstance(resolved.object, NegativeSurface):
                    neg = list(resolved.object.formula.triples)
                if neg is not None:
                    if not self._solve(neg, b):
                        stack.append((rest, b, anc))
                    continue
                # object is not a formula: fall through to a normal match

            # 2. Builtin predicate.
            if isinstance(resolved.predicate, NamedNode):
                builtin = self._builtins.get(resolved.predicate.value)
                if builtin is not None and self._builtin_applies(resolved):
                    for nb in self._handle_builtin(builtin, goal, [b]):
                        stack.append((rest, nb, anc))
                    continue

            # 3. Normal goal: match facts, then expand rules.
            gk = self._goal_key(resolved, {})

            for st in self._store_matches(resolved):
                nb = unify(resolved, st, b)
                if nb is not None:
                    stack.append((rest, nb, anc))

            if gk in anc:
                # Already on this branch's proof path — do not re-expand (cycle).
                continue

            child_anc = anc | {gk}
            for rule in self._rules:
                renamed = copy_rule(rule)
                for head_triple in renamed.head.triples:
                    ub = unify_terms(resolved.predicate, head_triple.predicate, b)
                    if ub is None:
                        continue
                    ub = unify_terms(resolved.subject, head_triple.subject, ub)
                    if ub is None:
                        continue
                    ub = unify_terms(resolved.object, head_triple.object, ub)
                    if ub is None:
                        continue
                    body = self._djiti_order(list(renamed.body.triples), ub)
                    new_resolvent = _prepend(body + [("POP", gk)], rest)
                    stack.append((new_resolvent, ub, child_anc))

        return solutions

    def _gc_binding(self, b: Binding, live: frozenset) -> Binding:
        """Garbage-collect the binding when a goal's scope closes.

        Only the variables the continuation still references (*live*) are kept,
        each resolved to ground through the chains that pass through the dropped
        subtree variables.  Any variable still referenced by a kept value is
        retained transitively so no binding dangles.  Because *live* is the
        continuation's variable set (O(width)) rather than the whole binding
        (O(depth)), a linear recursion stays linear.
        """
        kept: Binding = {}
        pending = [vid for vid in live if vid in b]
        while pending:
            vid = pending.pop()
            if vid in kept:
                continue
            rv = self._resolve_term(b[vid], b)
            kept[vid] = rv
            ref: set[int] = set()
            self._collect_var_ids(rv, ref)
            for r in ref:
                if r in b and r not in kept:
                    pending.append(r)
        return kept

    @staticmethod
    def _collect_var_ids(term: Term, out: set[int]) -> None:
        """Collect every Variable id occurring anywhere in *term*."""
        if isinstance(term, Variable):
            out.add(term.id)
        elif isinstance(term, ListTerm):
            for it in term.items:
                Engine._collect_var_ids(it, out)
        elif isinstance(term, Formula):
            for tr in term.triples:
                Engine._collect_var_ids(tr.subject, out)
                Engine._collect_var_ids(tr.predicate, out)
                Engine._collect_var_ids(tr.object, out)
        elif isinstance(term, NegativeSurface):
            for tr in term.formula.triples:
                Engine._collect_var_ids(tr.subject, out)
                Engine._collect_var_ids(tr.predicate, out)
                Engine._collect_var_ids(tr.object, out)
        elif isinstance(term, TripleTerm):
            Engine._collect_var_ids(term.subject, out)
            Engine._collect_var_ids(term.predicate, out)
            Engine._collect_var_ids(term.object, out)

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
