"""Public API — ``execute()`` function.

Ties together parsing, loading, and reasoning into a single call.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import time
from pathlib import Path
from typing import Literal

from pyeye.term import Triple, Quad, NamedNode
from pyeye.parser import (
    parse_n3, load_data_string, load_data_file, ParsedDocument, Rule
)
from pyeye.builtins import Builtin
from pyeye.engine import Engine, ReasoningTimeoutError
from pyeye.output import N3Writer

import ipaddress as _ipaddress
import urllib.parse as _urllib_parse


@dataclass
class Result:
    """Output of a reasoning run."""
    triples: str = ""
    stats: dict = field(default_factory=dict)
    explains: list = field(default_factory=list)
    query_answers: list = field(default_factory=list)  # populated when query is set


def execute(*args, **kwargs) -> Result:
    """Run reasoning in a worker thread with an enlarged C stack.

    Deeply recursive rule sets (ackermann, takeuchi, deep subclass chains) drive
    the backward-chaining call stack far past CPython's default limit even though
    they terminate.  Raising ``sys.setrecursionlimit`` alone risks a hard C-stack
    overflow (segfault) on the main thread, so the work runs on a thread whose
    stack is sized to match the high recursion limit set inside it.  The thread's
    result (or exception) is propagated back to the caller unchanged.
    """
    import threading as _threading
    import sys as _sys

    box: dict[str, object] = {}

    def _worker() -> None:
        _sys.setrecursionlimit(400_000)
        try:
            box["result"] = _execute_impl(*args, **kwargs)
        except BaseException as exc:  # noqa: BLE001 — re-raised in caller thread
            box["error"] = exc

    try:
        _threading.stack_size(512 * 1024 * 1024)  # 512 MiB
    except (ValueError, RuntimeError):  # pragma: no cover — platform-dependent
        pass
    t = _threading.Thread(target=_worker)
    t.start()
    t.join()
    if "error" in box:
        raise box["error"]  # type: ignore[misc]
    return box["result"]  # type: ignore[return-value]


def _execute_impl(
    data_paths: list[str] | None = None,
    data_strings: list[str] | None = None,
    rule_paths: list[str] | None = None,
    rule_strings: list[str] | None = None,
    query_paths: list[str] | None = None,
    builtins: dict[str, Builtin] | None = None,
    explain: bool = False,
    max_steps: int = -1,
    limit_answers: int = -1,
    timeout_seconds: float | None = 30.0,
    prefixes: dict[str, str] | None = None,
    nope: bool = False,
    pass_mode: bool = False,
    pass_all: bool = False,
    pass_only_new: bool = False,
    djiti_debug: bool = False,
    query: Triple | None = None,
    forward: bool = True,
    entail: bool = False,
    entail_owl: bool = False,
    not_entail: Triple | None = None,
    cache_dir: str | None = None,
    explain_format: Literal["n3", "dot", "html"] = "n3",
    proof: bool = False,
    source_urls: dict[str, str] | None = None,
) -> Result:
    """Run N3 reasoning and return derived triples as N3 text.

    Parameters
    ----------
    data_paths :
        Paths to N3/Turtle data files (parsed via rdflib).
    data_strings :
        Inline N3/Turtle data strings.
    rule_paths :
        Paths to N3 rule files (may contain {P} => {C} rules).
    rule_strings :
        Inline N3 rule strings.
    builtins :
        Custom builtin registry (merged with the default set).
    explain :
        If True, collect proof explanations (Phase 2).
    max_steps :
        Hard cap on inference steps (-1 = unlimited).
    limit_answers :
        Stop after this many new derivations (-1 = unlimited).
    prefixes :
        Additional prefix mappings for output serialization.
    nope :
        If True, skip derivation — pass through data only.
    pass_mode :
        If True, output includes input facts + derived triples.
    pass_all :
        If True, output includes input facts, rules, and derived triples.
    djiti_debug :
        If True, log DJITI pattern ordering for each rule application.
    query :
        A Triple to backward-chain from. If set, the engine finds all
        bindings that satisfy the query. Results go in Result.query_answers.
    forward :
        If True (default), run forward chaining before backward chaining.
        Set to False for pure backward chaining.
    entail :
        If True, apply RDFS entailment rules before running user rules.
        Derives implicit triples from subClassOf, subPropertyOf,
        domain, and range declarations.
    entail_owl :
        If True, apply OWL 2 RL entailment rules (implies entail=True).
        Derives implicit triples from OWL axioms: sameAs, differentFrom,
        transitive/symmetric/functional properties, intersectionOf,
        unionOf, someValuesFrom, allValuesFrom, hasValue, oneOf,
        property chains, and keys.
    not_entail :
        If set, check that this triple is NOT entailed by the data + rules.
        Returns empty triples if not entailed, or the triple if it IS entailed
        (i.e., the check fails).
    cache_dir :
        Directory for caching remote N3 files. When set, HTTP/HTTPS URIs
        in data_paths and rule_paths are fetched and cached locally.
    explain_format :
        Format for proof trace output: "n3" (default), "dot" (Graphviz),
        or "html" (collapsible browser view). Only used when explain=True.
    timeout_seconds :
        Wall-clock deadline for forward chaining, in seconds.  Defaults to
        30 s.  Raise ``ReasoningTimeoutError`` if the engine is still running
        when the deadline is hit — this prevents infinite loops caused by
        rules that generate an unbounded number of new triples.  Pass
        ``None`` to disable the guard entirely (use only when you are certain
        the rules terminate).
    """
    start = time.monotonic()

    # Deep subclass chains and recursive rules (deep-taxonomy, ackermann,
    # takeuchi) drive the matching/backward-chaining stack well past CPython's
    # default 1000-frame limit even though they terminate.  Raise it for the
    # duration of the run and restore afterwards.
    import sys as _sys
    _prev_reclimit = _sys.getrecursionlimit()
    _sys.setrecursionlimit(max(_prev_reclimit, 50000))

    all_triples: list[Triple] = []
    all_quads: list[Quad] = []
    all_rules: list[Rule] = []
    all_prefixes: dict[str, str] = dict(prefixes or {})

    # Proof-mode bookkeeping: facts/rules tagged with their source URL, plus
    # the query rules whose firings the proof explains.
    src_facts: list = []      # list[tuple[Triple, str]]
    src_rules: list = []      # list[tuple[Rule, str]]
    src_query_rules: list = []  # list[tuple[Rule, str]]

    def _src_url(path: str) -> str:
        if source_urls and path in source_urls:
            return source_urls[path]
        return path

    # -- helper: resolve path (HTTP with optional caching) -------------------
    def _validate_url(path: str) -> bool:
        """Reject URLs targeting private IPs or non-HTTP schemes."""
        parsed = _urllib_parse.urlparse(path)
        if parsed.scheme not in ("http", "https"):
            return False  # pragma: no cover — _resolve_path only passes http/https
        if parsed.hostname:
            try:
                ip = _ipaddress.ip_address(parsed.hostname)
                if ip.is_private or ip.is_loopback or ip.is_link_local:
                    return False
            except ValueError:  # pragma: no cover — needs non-IP hostname + network
                pass
        return True  # pragma: no cover — needs public URL + network to reach here

    def _resolve_path(path: str) -> str:
        """Resolve a path, fetching HTTP URIs with optional caching.

        SSRF protection: rejects URLs targeting private IP ranges.
        """
        if path.startswith(("http://", "https://")):
            if not _validate_url(path):
                raise ValueError(f"Blocked URL (private IP or invalid scheme): {path}")
            import urllib.request as _urllib_req  # pragma: no cover
            import hashlib as _hash  # pragma: no cover
            import os as _os  # pragma: no cover
            if cache_dir:  # pragma: no cover
                # Cache key: hash of URL
                cache_key = _hash.sha256(path.encode()).hexdigest()[:16]
                cached = _os.path.join(cache_dir, cache_key)
                if _os.path.exists(cached):
                    return cached
                # Fetch and cache
                _os.makedirs(cache_dir, exist_ok=True)
                with _urllib_req.urlopen(path, timeout=60) as resp:
                    content = resp.read()
                with open(cached, "wb") as f:
                    f.write(content)
                return cached
            else:  # pragma: no cover
                # Fetch to temp file
                import tempfile as _tempfile
                with _urllib_req.urlopen(path, timeout=60) as resp:
                    content = resp.read()
                tmp = _tempfile.NamedTemporaryFile(
                    suffix=".n3", delete=False, mode="wb"
                )
                tmp.write(content)
                tmp.close()
                return tmp.name
        return path

    # -- load data -----------------------------------------------------------
    if data_paths:
        for p in data_paths:
            resolved = _resolve_path(p)
            doc = load_data_file(resolved)
            all_triples.extend(doc.triples)
            all_quads.extend(doc.quads)
            all_prefixes.update(doc.prefixes)
            if proof:
                url = _src_url(p)
                for t in doc.triples:
                    src_facts.append((t, url))

    if data_strings:
        for s in data_strings:
            doc = load_data_string(s)
            all_triples.extend(doc.triples)
            all_quads.extend(doc.quads)
            all_prefixes.update(doc.prefixes)
            # If load_data_string fell back to parse_n3 (e.g. input has rules),
            # also collect the rules from the parsed document.
            if doc.rules:
                all_rules.extend(doc.rules)

    # -- load rules (may also contain TriG data) -----------------------------
    if rule_paths:
        for p in rule_paths:
            resolved = _resolve_path(p)
            text = Path(resolved).read_text(encoding="utf-8")
            url = _src_url(p)
            doc = parse_n3(text, source=url)
            all_rules.extend(doc.rules)
            all_triples.extend(doc.triples)
            all_quads.extend(doc.quads)
            all_prefixes.update(doc.prefixes)
            if proof:
                for t in doc.triples:
                    src_facts.append((t, url))
                for r in doc.rules:
                    src_rules.append((r, url))

    if rule_strings:
        for s in rule_strings:
            doc = parse_n3(s, source="<string>")
            all_rules.extend(doc.rules)
            all_triples.extend(doc.triples)
            all_quads.extend(doc.quads)
            all_prefixes.update(doc.prefixes)

    # -- load query files (their rule heads become the answer) ---------------
    has_query_rules = False
    if query_paths:
        from dataclasses import replace as _replace
        for p in query_paths:
            resolved = _resolve_path(p)
            text = Path(resolved).read_text(encoding="utf-8")
            url = _src_url(p)
            doc = parse_n3(text, source=url)
            for r in doc.rules:
                all_rules.append(_replace(r, is_query=True))
                has_query_rules = True
                if proof:
                    src_query_rules.append((r, url))
            # A query file's bare triples (no rule) are also data.
            all_triples.extend(doc.triples)
            all_quads.extend(doc.quads)
            all_prefixes.update(doc.prefixes)
            if proof:
                for t in doc.triples:
                    src_facts.append((t, url))

    # -- log:impliesAnswer rules are query/answer rules ----------------------
    # A ``{P} log:impliesAnswer {C}`` triple (whether inline in the data or
    # produced by --query) is an answer rule: its conclusions are the output.
    # ``{P} =^ {C}`` rules inline in a rule file are query rules too.
    if any(r.is_query for r in all_rules):
        has_query_rules = True
    _log_implies_answer_iri = "http://www.w3.org/2000/10/swap/log#impliesAnswer"
    from pyeye.term import Formula as _Formula
    if any(
        isinstance(t.predicate, NamedNode)
        and t.predicate.value == _log_implies_answer_iri
        and isinstance(t.subject, _Formula)
        and isinstance(t.object, _Formula)
        for t in all_triples
    ):
        has_query_rules = True

    # -- proof mode ----------------------------------------------------------
    # Emit an EYE-compatible proof trace (reason: vocabulary) of the query.
    if proof:
        from pyeye.eye_proof import ProofKB, build_proof, serialize_proof
        kb = ProofKB(facts=list(src_facts), rules=list(src_rules))
        proof_dag = build_proof(kb, src_query_rules)
        _sys.setrecursionlimit(_prev_reclimit)
        text = serialize_proof(proof_dag, all_prefixes)
        return Result(
            triples=text,
            stats={"steps": 0, "derived": len(proof_dag.components),
                   "time_ms": (time.monotonic() - start) * 1000},
        )

    # -- nope mode -----------------------------------------------------------
    # ``--nope`` only suppresses proof output; with a query it still runs and
    # returns the query answers.  Only short-circuit when there is nothing to
    # query and we are in pure pass-through.
    if (nope and not has_query_rules and not pass_mode and not pass_all
            and not pass_only_new):
        elapsed = time.monotonic() - start
        writer = N3Writer(all_prefixes)
        _sys.setrecursionlimit(_prev_reclimit)
        return Result(
            triples=writer.write_triples(all_triples),
            stats={"steps": 0, "derived": 0, "time_ms": elapsed * 1000},
        )

    # -- reason --------------------------------------------------------------
    engine = Engine(
        builtins=builtins,
        max_steps=max_steps,
        limit_answers=limit_answers,
        djiti_debug=djiti_debug,
        explain=explain,
        timeout_seconds=timeout_seconds,
    )

    # Convert log:implies triples to rules AND keep them in the store
    # (keeping them queryable lets meta-builtins like log:forAllIn inspect rules)
    _log_implies_iri = "http://www.w3.org/2000/10/swap/log#implies"
    for t in all_triples:
        if (
            isinstance(t.predicate, NamedNode)
            and t.predicate.value in (_log_implies_iri, _log_implies_answer_iri)
            and isinstance(t.subject, _Formula)
            and isinstance(t.object, _Formula)
        ):
            is_ans = t.predicate.value == _log_implies_answer_iri
            all_rules.append(Rule(body=t.subject, head=t.object, is_query=is_ans))

    # Add data triples
    for t in all_triples:
        engine.add_triple(t)

    # Add named graph quads
    for q in all_quads:
        engine.store.add_quad(q)

    # Apply RDFS entailment (if enabled)
    if entail and not nope:
        from pyeye.rdfs import apply_rdfs_entailment
        rdfs_count = apply_rdfs_entailment(engine.store)
    else:
        rdfs_count = 0

    # Apply OWL 2 RL entailment (implies entail=True)
    if entail_owl and not nope:
        from pyeye.owl import apply_owl_rl_entailment
        owl_count = apply_owl_rl_entailment(engine.store)
    else:
        owl_count = 0

    # Snapshot baseline (input facts should not count as derived)
    engine.snapshot_initial()

    # Add rules
    for r in all_rules:
        engine.add_rule(r)

    # Run forward chaining. With a --query we always need to forward-chain so
    # the query rules can match the deductive closure, even under --nope (which
    # in EYE only suppresses proof output, not derivation).
    # ``--nope`` only suppresses proof output; it must not suppress derivation
    # when the run still needs the closure (a query, --pass, --pass-all, or
    # --pass-only-new).
    run_forward = forward and (
        not nope or has_query_rules or pass_only_new or pass_mode or pass_all
    )
    if run_forward:
        engine.run()

    # Run backward chaining (if query Triple is set)
    query_answers: list = []
    if query is not None and not nope:
        query_answers = engine.backward_chain(query)

    # Collect query answers (head instantiations of --query rules)
    if has_query_rules:
        engine.collect_answers()

    # Collect output
    elapsed = time.monotonic() - start
    writer = N3Writer(all_prefixes)

    if pass_mode or pass_all:
        # All triples in the store (input + derived)
        output_triples = list(engine.store)
        if pass_all:
            # --pass-all also echoes the rules, rendered with =>/<= sugar.
            _SUGAR_IMPLIES = NamedNode(
                "http://eulersharp.sourceforge.net/2003/03swap/log-rules#implies")
            _SUGAR_IMPLIED_BY = NamedNode(
                "http://eulersharp.sourceforge.net/2003/03swap/log-rules#impliedBy")
            derived_rules = [r for r in engine._rules if r.source == "derived"]
            for r in list(all_rules) + derived_rules:
                if r.is_query:
                    continue
                if r.is_backward:
                    output_triples.append(Triple(r.head, _SUGAR_IMPLIED_BY, r.body))
                else:
                    output_triples.append(Triple(r.body, _SUGAR_IMPLIES, r.head))
    elif has_query_rules:
        # Query run: output is exactly the answer set (query rule heads)
        output_triples = engine.answer_triples
    else:
        # Only derived triples
        output_triples = engine.derived_triples

    triples_text = writer.write_triples(output_triples)

    # Check not_entail: verify the triple is NOT in the store
    not_entail_failed = False
    if not_entail is not None:
        from pyeye.unify import unify
        for store_triple in engine.store:
            if unify(not_entail, store_triple) is not None:
                not_entail_failed = True
                break

    _sys.setrecursionlimit(_prev_reclimit)
    return Result(
        triples=triples_text,
        stats={
            "steps": engine.step_count,
            "derived": len(output_triples),
            "time_ms": elapsed * 1000,
            "not_entail_failed": not_entail_failed,
        },
        explains=_format_proofs(engine._proof_trees if explain else [], explain_format),
        query_answers=query_answers,
    )


def _format_proofs(
    trees: list,
    fmt: Literal["n3", "dot", "html"],
) -> list | str:
    """Format proof trees in the requested format.

    "n3" returns the raw list (default, for API compatibility).
    "dot" and "html" return serialized strings.
    """
    if not trees:
        return []
    if fmt == "n3":
        return trees  # Return raw list for API compatibility
    if fmt == "dot":
        from pyeye.proof import serialize_dot
        return serialize_dot(trees)
    if fmt == "html":
        from pyeye.proof import serialize_html
        return serialize_html(trees)
    return trees  # pragma: no cover — exhaustive match on Literal["n3", "dot", "html"]
