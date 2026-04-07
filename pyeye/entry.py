"""Public API — ``execute()`` function.

Ties together parsing, loading, and reasoning into a single call.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import time
from pathlib import Path
from typing import Literal

from pyeye.term import Triple, Quad
from pyeye.parser import (
    parse_n3, load_data_string, load_data_file, ParsedDocument, Rule
)
from pyeye.builtins import Builtin
from pyeye.engine import Engine
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


def execute(
    data_paths: list[str] | None = None,
    data_strings: list[str] | None = None,
    rule_paths: list[str] | None = None,
    rule_strings: list[str] | None = None,
    builtins: dict[str, Builtin] | None = None,
    explain: bool = False,
    max_steps: int = -1,
    limit_answers: int = -1,
    prefixes: dict[str, str] | None = None,
    nope: bool = False,
    pass_mode: bool = False,
    pass_all: bool = False,
    djiti_debug: bool = False,
    query: Triple | None = None,
    forward: bool = True,
    entail: bool = False,
    entail_owl: bool = False,
    not_entail: Triple | None = None,
    cache_dir: str | None = None,
    explain_format: Literal["n3", "dot", "html"] = "n3",
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
    """
    start = time.monotonic()

    all_triples: list[Triple] = []
    all_quads: list[Quad] = []
    all_rules: list[Rule] = []
    all_prefixes: dict[str, str] = dict(prefixes or {})

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
            doc = parse_n3(text, source=p)
            all_rules.extend(doc.rules)
            all_triples.extend(doc.triples)
            all_quads.extend(doc.quads)
            all_prefixes.update(doc.prefixes)

    if rule_strings:
        for s in rule_strings:
            doc = parse_n3(s, source="<string>")
            all_rules.extend(doc.rules)
            all_triples.extend(doc.triples)
            all_quads.extend(doc.quads)
            all_prefixes.update(doc.prefixes)

    # -- nope mode -----------------------------------------------------------
    if nope:
        elapsed = time.monotonic() - start
        writer = N3Writer(all_prefixes)
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
    )

    # Convert log:implies triples (formula log:implies formula) to rules
    _log_implies_iri = "http://www.w3.org/2000/10/swap/log#implies"
    from pyeye.term import Formula as _Formula
    remaining_triples: list[Triple] = []
    for t in all_triples:
        if (
            isinstance(t.predicate, type(t.predicate))
            and hasattr(t.predicate, "value")
            and t.predicate.value == _log_implies_iri
            and isinstance(t.subject, _Formula)
            and isinstance(t.object, _Formula)
        ):
            all_rules.append(Rule(body=t.subject, head=t.object))
        else:
            remaining_triples.append(t)
    all_triples = remaining_triples

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

    # Run forward chaining (if enabled)
    if forward and not nope:
        engine.run()

    # Run backward chaining (if query is set)
    query_answers: list = []
    if query is not None and not nope:
        query_answers = engine.backward_chain(query)

    # Collect output
    elapsed = time.monotonic() - start
    writer = N3Writer(all_prefixes)

    if pass_mode or pass_all:
        # All triples in the store (input + derived)
        output_triples = list(engine.store)
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
