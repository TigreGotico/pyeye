"""Minimal N3 rule parser.

Parses N3 rule files containing ``{P} => {C}`` (forward) and
``{C} <= {P}`` (backward) syntax, along with the term vocabulary needed
inside rules: variables (``?name``), blank nodes (``[]``, ``_:name``),
RDF lists (``(a b c)``), prefixed names (``:foo``, ``ex:bar``), literals,
and quantifier directives (``@forSome``, ``@forAll``).

Data triples (no rules) are delegated to **rdflib** for parsing; this
module only handles rule-bearing N3 files and the shared vocabulary
(prefixes, base) that both data and rules need.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from rdflib import Graph, URIRef, Literal as RDFLiteral, BNode
from rdflib.namespace import RDF

from pyeye.term import (
    NamedNode,
    Literal,
    Variable,
    Existential,
    Formula,
    Triple,
    Term,
    ListTerm,
    # Phase 2 extended types
    TripleTerm,
    FormulaTerm,
    NegativeSurface,
    Quad,
    SetTerm,
)


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

RDF_TYPE = NamedNode(str(RDF.type))

@dataclass
class Rule:
    """A single N3 rule: body ``=>`` head (or body ``<=`` head reversed)."""
    body: Formula
    head: Formula
    source: str = ""
    for_some: tuple[str, ...] = ()  # M3 fix: existentially quantified variables
    for_all: tuple[str, ...] = ()   # M3 fix: universally quantified variables
    is_backward: bool = False       # True for ``<=`` rules (backward chaining only)
    is_contradiction: bool = False  # True for ``=> false`` rules (N3 constraint violation)
    is_query: bool = False          # True for --query rules (heads are the answer)
    head_var: Variable | None = None  # ``{...} => ?phi`` — assert the formula bound to ?phi


@dataclass
class ParsedDocument:
    """Result of parsing an N3/TriG file."""
    triples: list[Triple] = field(default_factory=list)
    quads: list[Quad] = field(default_factory=list)
    rules: list[Rule] = field(default_factory=list)
    prefixes: dict[str, str] = field(default_factory=dict)
    base: str | None = None
    for_some: list[str] = field(default_factory=list)
    for_all: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Prefix manager
# ---------------------------------------------------------------------------

class PrefixManager:
    def __init__(self, base: str | None = None) -> None:
        self._prefixes: dict[str, str] = {}
        self._base = base

    def register(self, prefix: str, uri: str) -> None:
        self._prefixes[prefix] = uri

    @property
    def prefixes(self) -> dict[str, str]:
        return dict(self._prefixes)

    def expand(self, qname: str) -> NamedNode:
        """Expand ``ex:foo`` or ``:foo`` to a NamedNode."""
        if ":" in qname:
            prefix, local = qname.split(":", 1)
        else:
            prefix, local = "", qname
        ns = self._prefixes.get(prefix, "")
        if not ns and self._base:
            ns = self._base
        # Percent-escapes (e.g. %20) and other PN_LOCAL escapes stay verbatim:
        # they are part of the resulting IRI, matching EYE's behaviour.
        return NamedNode(ns + local)


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Tok:
    t: str  # type
    v: str  # value


# Turtle prefixed-name (PNAME) regex.  A prefixed name is an optional prefix,
# a ':', and a rich local part.  The local part allows letters, digits, '_',
# '-', ':', percent-escapes (%XX), and internal '.' (not as the last char so a
# trailing statement-terminating dot is not swallowed).
_PN_BASE = r"A-Za-zÀ-￿"
_PN_PREFIX = rf"(?:[{_PN_BASE}][\w{_PN_BASE}.\-]*[\w{_PN_BASE}\-]|[{_PN_BASE}])?"
_PN_LOCAL_START = rf"(?:[{_PN_BASE}_0-9:]|%[0-9A-Fa-f]{{2}})"
_PN_LOCAL_MID = rf"(?:[\w{_PN_BASE}.\-:]|%[0-9A-Fa-f]{{2}})"
_PN_LOCAL_END = rf"(?:[\w{_PN_BASE}\-:]|%[0-9A-Fa-f]{{2}})"
_PN_LOCAL = rf"(?:{_PN_LOCAL_START}(?:{_PN_LOCAL_MID}*{_PN_LOCAL_END})?)?"
_PNAME_RE = rf"{_PN_PREFIX}:{_PN_LOCAL}"


def tokenize(text: str) -> list[Tok]:
    """Lex N3 text into tokens.  Skips comments and whitespace.

    M2 fix: IRI validation — rejects forbidden characters in IRIREFs.
    """
    specs: list[tuple[str, str]] = [
        ("LONGSTR", r"'''[\s\S]*?'''|\"\"\"[\s\S]*?\"\"\""),
        ("STR",     r'"(?:[^"\\]|\\.)*"'),
        ("TTOPEN",  r"<<"),         # Phase 2: triple term open — before IRI!
        ("TTCLOSE", r">>"),         # Phase 2: triple term close — before IRI!
        ("IMPQ",    r"=\^"),        # EYE query operator =^ (filter rule, answer-only)
        ("IMPF",    r"=>"),
        ("IMPB",    r"<="),         # must be before IRI so <= is not swallowed as <...>
        ("PREDINV", r"<-"),         # must be before IRI so <-<IRI> is not swallowed as <...>
        ("IRI",     r"<[^>]*>"),
        ("PFX",     r"@prefix\b"),
        ("SPARQL_PFX", r"\bPREFIX\b"),  # L1 fix: SPARQL-style prefix
        ("BASE",    r"@base\b"),
        ("FSOME",   r"@forSome\b"),
        ("FALL",    r"@forAll\b"),
        ("HATHAT",  r"\^\^"),
        ("FTOPEN",  r"\(\|"),       # Phase 2: formula term open
        ("FTCLOSE", r"\|\)"),       # Phase 2: formula term close
        ("SETOPEN", r"\(\$"),       # Phase 2: set open
        ("SETCLOSE", r"\$\)"),      # Phase 2: set close
        ("ANNOT_OPEN",  r"\{\|"),    # RDF 1.2 annotation {| ... |}
        ("ANNOT_CLOSE", r"\|\}"),    # RDF 1.2 annotation close
        ("LBR",     r"\{"),
        ("RBR",     r"\}"),
        ("LBK",     r"\["),
        ("RBK",     r"\]"),
        ("LP",      r"\("),
        ("RP",      r"\)"),
        ("SC",      r";"),
        ("CM",      r","),
        ("DOT",     r"\."),
        ("OP_FWD",  r"!"),          # Phase 2: forward path
        ("OP_REV",  r"\^(?!\^)"),   # Phase 2: reverse path (not ^^)
        ("TILDE",   r"~"),          # RDF 1.2 reifier: ``s p o ~ :id`` / ``<< s p o ~ :id >>``
        ("EQ",      r"="),          # C8 fix: owl:sameAs sugar
        ("OF_KW",   r"\bof\b"),     # Phase 2: "of" keyword
        ("HAS_KW",  r"\bhas\b"),    # Phase 2: "has" keyword
        ("IS_KW",   r"\bis\b"),     # Phase 2: "is" keyword
        ("GRAPH_KW", r"\bGRAPH\b"), # Phase 2: TriG graph keyword
        ("TRUE",    r"\btrue\b"),   # Boolean literal
        ("FALSE",   r"\bfalse\b"),  # Boolean literal
        ("VAR",     r"\?[^\W\d]\w*"),  # C9 fix: Unicode variable names
        # Blank node label per Turtle BLANK_NODE_LABEL: leading word char
        # (Unicode, incl. digit), interior chars may include '-' and '.',
        # but no trailing '.' (so ``_:b1.`` still ends the statement).
        ("BLANK",   r"_:\w(?:[\w.\-]*[\w\-])?"),
        ("LANG",    r"@[A-Za-z]+(-[A-Za-z0-9]+)*"),
        # Prefixed name (Turtle PNAME): optional prefix, ':', rich local part
        # (digits anywhere, percent-escapes %XX, internal dots, ':').  Matched
        # as a single token so names like ``res:COUNTRY_United%20States`` and
        # ``ex:AIRLINE_100`` are not fragmented into KW/NUM/COLON pieces.
        ("PNAME",   _PNAME_RE),
        ("COLON",   r":"),
        ("NUM",     r"[+-]?(\d+\.\d+|\.\d+|\d+)([eE][+-]?\d+)?"),
        ("KW",      r"[^\W\d][\w\-]*"),  # C9 fix: Unicode keywords and local names (hyphens allowed per N3 spec)
        ("HASH",    r"#[^\n]*"),
        ("WS",      r"\s+"),
    ]
    combined = "|".join(f"(?P<{n}>{p})" for n, p in specs)
    pat = re.compile(combined)

    out: list[Tok] = []
    for m in pat.finditer(text):
        kind = m.lastgroup
        val = m.group()
        if kind in ("WS", "HASH", None):
            continue
        # M2 fix: Validate IRI characters
        if kind == "IRI":
            _validate_iri(val)
        out.append(Tok(kind, val))
    out.append(Tok("EOF", ""))
    return out


# Forbidden characters in IRIREF per N3 spec
_IRI_FORBIDDEN = set('{}|^\\`"')

# Token kinds that can begin a graph-label term in an N3 quad ``s p o g .``.
_GRAPH_TERM_START = frozenset(("PNAME", "IRI", "BLANK", "COLON"))


def _validate_iri(iri: str) -> None:
    """M2 fix: Reject forbidden characters in IRI references.

    Per the N3 spec, IRIREFs must not contain: { } | ^ \\ ` "
    """
    # Strip < > delimiters
    content = iri[1:-1]
    for char in content:
        if char in _IRI_FORBIDDEN:
            raise ParseError(f"Forbidden character {char!r} in IRI: {iri}")


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

class ParseError(Exception):
    pass


class Parser:
    def __init__(self, text: str, source: str = "") -> None:
        self._toks = tokenize(text)
        self._i = 0
        self._src = source
        self._pm = PrefixManager()
        self._triples: list[Triple] = []
        self._rules: list[Rule] = []
        self._bn = 0
        self._for_some: list[str] = []
        self._for_all: list[str] = []
        # IRIs declared ``@forAll <iri>`` — universally quantified, rewritten
        # to Variables inside rule formulas (document scope).
        self._forall_iris: set[str] = set()
        # Variable scope: maps name → Variable within the current rule.
        # Ensures ?X in body and ?X in head share the same Variable.id.
        # Reset for each top-level statement, inherited into nested formulas.
        self._var_scope: dict[str, Variable] = {}
        # Formula-local triple routing: when inside { ... }, blank node
        # property triples and path-expansion triples go into the formula's
        # triple list, not the document-level self._triples.
        self._formula_triples_stack: list[list[Triple]] = []

    _SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.\-]*:")

    def _resolve_iri(self, ref: str) -> str:
        """Resolve a relative IRI reference against the document base.

        The base is an explicit ``@base`` directive, falling back to the
        document source URL when it is absolute.  Absolute references and
        documents without a usable base pass through unchanged.
        """
        if self._SCHEME_RE.match(ref):
            return ref
        base = self._pm._base
        if not base and self._src and self._SCHEME_RE.match(self._src):
            base = self._src
        if not base:
            return ref
        from urllib.parse import urljoin
        resolved = urljoin(base, ref)
        # urljoin drops an empty fragment: ``dpe#`` resolves to ``.../dpe``.
        # Namespace IRIs commonly end in '#', so restore it.
        if ref.endswith("#") and not resolved.endswith("#"):
            resolved += "#"
        return resolved

    @property
    def _current_triples(self) -> list[Triple]:
        """The triple list that side-effect triples (blank nodes, paths) go into.

        When inside a formula (``{ ... }``), returns the formula-local list.
        Otherwise returns the document-level list.
        """
        if self._formula_triples_stack:
            return self._formula_triples_stack[-1]
        return self._triples

    def parse(self) -> ParsedDocument:
        while not self._eof():
            self._stmt()
        # A top-level triple containing a quickvar (``?x :loves _:y.``) is an
        # implicitly universally quantified fact; EYE represents it as a
        # backward rule with an empty body in addition to the triple itself.
        def _has_var(t: Term) -> bool:
            if isinstance(t, Variable):
                return True
            if isinstance(t, ListTerm):
                return any(_has_var(i) for i in t.items)
            return False
        for t in self._triples:
            if _has_var(t.subject) or _has_var(t.predicate) or _has_var(t.object):
                self._rules.append(Rule(
                    body=Formula(()),
                    head=Formula((t,)),
                    source=self._src,
                    is_backward=True,
                ))
        return ParsedDocument(
            triples=self._triples,
            quads=list(self._quads),
            rules=self._rules,
            prefixes=self._pm.prefixes,
            base=self._pm._base,
            for_some=list(self._for_some),
            for_all=list(self._for_all),
        )

    # -- statement dispatch --------------------------------------------------

    def _stmt(self) -> None:
        # Reset variable scope for each top-level statement so that ?X in
        # one rule is independent from ?X in a different rule.
        self._var_scope = {}
        t = self._peek()
        if t.t in ("PFX", "SPARQL_PFX"):
            self._do_prefix()
        elif t.t == "BASE":
            self._do_base()
        elif t.t in ("FSOME", "FALL"):
            self._do_quantifier()
        elif t.t == "GRAPH_KW":
            self._do_graph()
        elif t.t == "LBR":
            self._do_formula_top()
        else:
            self._do_data()

    # -- directives ----------------------------------------------------------

    def _do_prefix(self) -> None:
        # L1 fix: Handle both @prefix (N3) and PREFIX (SPARQL) tokens
        if self._peek().t == "SPARQL_PFX":
            self._eat("SPARQL_PFX")
        else:
            self._eat("PFX")
        t = self._peek()
        if t.t == "PNAME":
            # prefix ex: <...> or prefix : <...> (single PNAME token ``ex:``/``:``)
            prefix = self._eat("PNAME").v.rstrip(":")
        elif t.t == "COLON":
            # prefix : <...>
            self._eat("COLON")
            prefix = ""
        elif t.t == "KW" and self._i + 1 < len(self._toks) and self._toks[self._i + 1].t == "COLON":
            # prefix ex: <...>
            prefix = self._eat("KW").v
            self._eat("COLON")
        else:
            # prefix ex <...> (no colon — non-standard but accept it)
            prefix = self._eat_any().v.rstrip(":")
        uri = self._resolve_iri(self._eat("IRI").v[1:-1])
        self._pm.register(prefix, uri)
        # DOT is optional (SPARQL-style)
        if self._peek().t == "DOT":
            self._eat("DOT")

    def _do_base(self) -> None:
        self._eat("BASE")
        self._pm._base = self._resolve_iri(self._eat("IRI").v[1:-1])
        self._eat("DOT")

    def _do_quantifier(self) -> None:
        """Consume @forSome/@forAll <var>, <var> . and store variable names.

        ``@forAll`` accepts IRIs as well as ``?var`` quickvars; a declared IRI
        is universally quantified, so its occurrences inside rule formulas are
        rewritten to Variables (see :meth:`_universalize`).
        """
        is_forsome = self._peek().t == "FSOME"
        self._eat_any()
        vars_list = []
        while self._peek().t not in ("DOT", "EOF"):
            t = self._peek()
            if t.t == "VAR":
                var_name = self._eat("VAR").v[1:]  # strip ?
                vars_list.append(var_name)
            elif t.t == "CM":
                self._eat("CM")
            elif not is_forsome and t.t == "IRI":
                self._eat("IRI")
                self._forall_iris.add(self._resolve_iri(t.v[1:-1]))
            elif not is_forsome and t.t == "PNAME":
                self._eat("PNAME")
                node = self._pm.expand(t.v)
                if isinstance(node, NamedNode):
                    self._forall_iris.add(node.value)
            else:
                self._eat_any()
        if self._peek().t == "DOT":
            self._eat("DOT")
        # M3 fix: Store quantified variables
        if is_forsome:
            self._for_some.extend(vars_list)
        else:
            self._for_all.extend(vars_list)

    # -- TriG: GRAPH <g> { ... } --------------------------------------------

    def _do_graph(self) -> None:
        """Parse ``GRAPH <graph_id> { ... triples ... }`` into quads.

        DOT after the GRAPH block is optional.
        """
        self._eat("GRAPH_KW")
        # Parse graph identifier
        graph_id = self._item()
        # Parse the graph body (formula)
        body = self._formula()
        # Convert triples to quads
        for t in body.triples:
            self._quads.append(Quad(t.subject, t.predicate, t.object, graph_id))
        # DOT after GRAPH block is optional
        if self._peek().t == "DOT":
            self._eat("DOT")

    @property
    def _quads(self) -> list[Quad]:
        """Access the parser's quad list (stored on the instance)."""
        if not hasattr(self, "_quads_list"):
            self._quads_list: list[Quad] = []
        return self._quads_list

    # -- rules / formulas ----------------------------------------------------

    _VAR_NS = "http://www.w3.org/2000/10/swap/var#"

    def _universalize(self, body: Formula, head: Formula) -> tuple[Formula, Formula]:
        """Rewrite universally quantified IRIs in a rule to Variables.

        Covers EYE quickvars (the ``var:`` namespace) and IRIs declared with
        ``@forAll <iri>``.  Only rule bodies/heads are rewritten — the same
        IRIs in plain data triples stay constants (e.g. ``log:allPossibleCases``
        declarations).  Occurrences across body and head share one Variable.
        """
        var_map: dict[str, Variable] = {}

        def conv(t: Term) -> Term:
            if isinstance(t, NamedNode):
                uri = t.value
                if uri.startswith(self._VAR_NS) or uri in self._forall_iris:
                    if uri not in var_map:
                        local = uri.rsplit("#", 1)[-1].rsplit("/", 1)[-1]
                        var_map[uri] = Variable(local)
                    return var_map[uri]
                return t
            if isinstance(t, ListTerm):
                return ListTerm(items=tuple(conv(i) for i in t.items))
            if isinstance(t, Formula):
                return Formula(triples=tuple(conv_triple(tr) for tr in t.triples))
            if isinstance(t, NegativeSurface):
                return NegativeSurface(formula=Formula(triples=tuple(
                    conv_triple(tr) for tr in t.formula.triples)))
            return t

        def conv_triple(tr: Triple) -> Triple:
            # Predicates are left alone: var:* predicates are builtins.
            return Triple(conv(tr.subject), tr.predicate, conv(tr.object))

        def has_candidate(f: Formula) -> bool:
            def scan(t: Term) -> bool:
                if isinstance(t, NamedNode):
                    return (t.value.startswith(self._VAR_NS)
                            or t.value in self._forall_iris)
                if isinstance(t, ListTerm):
                    return any(scan(i) for i in t.items)
                if isinstance(t, Formula):
                    return any(scan(tr.subject) or scan(tr.object)
                               for tr in t.triples)
                if isinstance(t, NegativeSurface):
                    return any(scan(tr.subject) or scan(tr.object)
                               for tr in t.formula.triples)
                return False
            return any(scan(tr.subject) or scan(tr.object) for tr in f.triples)

        if not (has_candidate(body) or has_candidate(head)):
            return body, head
        return (Formula(triples=tuple(conv_triple(tr) for tr in body.triples)),
                Formula(triples=tuple(conv_triple(tr) for tr in head.triples)))

    def _do_formula_top(self) -> None:
        body = self._formula()
        t = self._peek()
        if t.t == "IMPQ":
            # EYE query operator ``{P} =^ {C}`` — like ``=>`` but the conclusion
            # is the query answer (a filter rule that only emits its head).
            self._eat("IMPQ")
            if self._peek().t in ("TRUE", "FALSE"):
                self._eat_any()
                head = Formula(())
            elif self._peek().t == "LBR":
                head = self._formula()
            else:
                self._eat_any()
                head = Formula(())
            if self._peek().t == "ANNOT_OPEN":
                self._skip_annotation()
            self._eat("DOT")
            body, head = self._universalize(body, head)
            self._rules.append(Rule(
                body, head, self._src,
                for_some=tuple(self._for_some),
                for_all=tuple(self._for_all),
                is_query=True,
            ))
            return
        if t.t == "IMPF":
            self._eat("IMPF")
            # `=> false` is N3 contradiction syntax — marks a constraint rule
            is_contradiction = False
            head_var: Variable | None = None
            if self._peek().t == "FALSE":
                self._eat("FALSE")
                head = Formula(())
                is_contradiction = True
            elif self._peek().t == "TRUE":
                self._eat("TRUE")
                head = Formula(())
            elif self._peek().t == "LBR":
                head = self._formula()
            elif self._peek().t == "VAR":
                # ``{...} => ?phi`` — assert the formula bound to ?phi
                vt = self._eat("VAR")
                vname = vt.v[1:]
                if vname not in self._var_scope:
                    self._var_scope[vname] = Variable(vname)
                head_var = self._var_scope[vname]
                head = Formula(())
            else:
                # Bare term (literal, IRI) as rule head — skip
                self._eat_any()
                head = Formula(())
            if self._peek().t == "ANNOT_OPEN":
                self._skip_annotation()
            self._eat("DOT")
            body, head = self._universalize(body, head)
            self._rules.append(Rule(
                body, head, self._src,
                for_some=tuple(self._for_some),
                for_all=tuple(self._for_all),
                is_contradiction=is_contradiction,
                head_var=head_var,
            ))
        elif t.t == "IMPB":
            self._eat("IMPB")
            # Allow `true` as the unit formula (empty body) in backward rules
            if self._peek().t == "TRUE":
                self._eat("TRUE")
                head = Formula(())
            elif self._peek().t == "LBR":
                head = self._formula()
            else:
                # Variable or other term as body — skip it (treat as empty body)
                self._eat_any()
                head = Formula(())
            if self._peek().t == "ANNOT_OPEN":
                self._skip_annotation()
            self._eat("DOT")
            head, body = self._universalize(head, body)
            self._rules.append(Rule(
                head, body, self._src,
                for_some=tuple(self._for_some),
                for_all=tuple(self._for_all),
                is_backward=True,
            ))  # reverse
        elif t.t == "DOT":
            self._eat("DOT")
            self._triples.extend(body.triples)
        else:
            # M4 fix: Formula used as subject of a data triple
            # e.g., { {A} => {B} } :in :rules .
            self._triples.extend(self._verb_obj_list(body))

    def _formula(self) -> Formula:
        """Parse ``{ ... }`` into a Formula.

        Blank-node property triples and path-expansion triples created inside
        this formula are captured in the formula-local triple list (via
        ``_formula_triples_stack``), not added to the document-level triples.
        """
        self._eat("LBR")
        tris: list[Triple] = []
        self._formula_triples_stack.append(tris)
        while self._peek().t != "RBR":
            # Bug 1 fix: If we see `()` and nothing follows (or only DOT/RBR
            # follows), it is the "unit formula" — a no-op.  But if a predicate
            # follows, `()` is the empty-list *subject* of a triple pattern.
            if self._peek().t == "LP":
                # Peek ahead to see if it's empty ()
                if self._i + 1 < len(self._toks) and self._toks[self._i + 1].t == "RP":
                    # Look at the token after the closing ) to decide
                    after_rp = self._toks[self._i + 2].t if self._i + 2 < len(self._toks) else "EOF"
                    if after_rp in ("RBR", "DOT"):
                        # It's the unit formula — consume and skip
                        self._eat("LP")
                        self._eat("RP")
                        continue
                    # else: fall through to _triple_pattern which will parse () as subject
            # Handle @forAll/@forSome quantifier inside a formula
            if self._peek().t in ("FSOME", "FALL"):
                self._do_quantifier()
                continue

            # Handle ?Var => {head} or ?Var <= {body} inside a formula
            if self._peek().t == "VAR" and self._i + 1 < len(self._toks) and self._toks[self._i + 1].t in ("IMPF", "IMPB"):
                vname = self._eat("VAR").v[1:]
                if vname not in self._var_scope:
                    self._var_scope[vname] = Variable(vname)
                var_term = self._var_scope[vname]
                imp_dir = self._eat_any().t  # IMPF or IMPB
                head_formula: Term
                if self._peek().t == "LBR":
                    head_formula = self._formula()
                elif self._peek().t in ("FALSE", "TRUE"):
                    self._eat_any()
                    head_formula = Formula(())
                elif self._peek().t == "VAR":
                    # ``?P => ?C`` — keep the conclusion variable
                    hname = self._eat("VAR").v[1:]
                    if hname not in self._var_scope:
                        self._var_scope[hname] = Variable(hname)
                    head_formula = self._var_scope[hname]
                else:
                    # Bare term (literal) — eat and treat as empty
                    if self._peek().t not in ("DOT", "RBR"):
                        self._eat_any()
                    head_formula = Formula(())
                if self._peek().t == "DOT":
                    self._eat("DOT")
                if imp_dir == "IMPF":
                    log_implies = NamedNode("http://www.w3.org/2000/10/swap/log#implies")
                    tris.append(Triple(var_term, log_implies, head_formula))
                else:
                    log_implied_by = NamedNode("http://www.w3.org/2000/10/swap/log#impliedBy")
                    tris.append(Triple(head_formula, log_implied_by, var_term))
                continue

            # Handle true/false => {head} or true/false <= {body} inside a formula
            if self._peek().t in ("TRUE", "FALSE") and self._i + 1 < len(self._toks) and self._toks[self._i + 1].t in ("IMPF", "IMPB"):
                self._eat_any()  # eat true/false
                imp_dir = self._eat_any().t  # IMPF or IMPB
                if self._peek().t == "LBR":
                    head_formula = self._formula()
                elif self._peek().t in ("FALSE", "TRUE"):
                    self._eat_any()
                    head_formula = Formula(())
                else:
                    if self._peek().t not in ("DOT", "RBR"):
                        self._eat_any()
                    head_formula = Formula(())
                if self._peek().t == "DOT":
                    self._eat("DOT")
                continue

            # M4 fix: Check for implication inside formulas: {A} => {B}
            if self._peek().t == "LBR":
                body_formula = self._formula()
                if self._peek().t == "IMPF":
                    self._eat("IMPF")
                    if self._peek().t in ("FALSE", "TRUE"):
                        self._eat_any()
                        head_formula = Formula(())
                    elif self._peek().t == "LBR":
                        head_formula = self._formula()
                    else:
                        # Bare term as implication head — skip
                        self._eat_any()
                        head_formula = Formula(())
                    # Optional trailing DOT inside formula
                    if self._peek().t == "DOT":
                        self._eat("DOT")
                    # Create triple with log:implies predicate
                    log_implies = NamedNode("http://www.w3.org/2000/10/swap/log#implies")
                    tris.append(Triple(body_formula, log_implies, head_formula))
                elif self._peek().t == "IMPB":
                    self._eat("IMPB")
                    if self._peek().t == "LBR":
                        head_formula = self._formula()
                    elif self._peek().t == "TRUE":
                        self._eat("TRUE")
                        head_formula = Formula(())
                    else:
                        # Variable or other bare term as body — skip
                        self._eat_any()
                        head_formula = Formula(())
                    # Optional trailing DOT inside formula
                    if self._peek().t == "DOT":
                        self._eat("DOT")
                    # Create triple with log:impliedBy predicate
                    log_implied_by = NamedNode("http://www.w3.org/2000/10/swap/log#impliedBy")
                    tris.append(Triple(head_formula, log_implied_by, body_formula))
                else:
                    # Not an implication — put the formula back as subject
                    # and parse as normal triple pattern
                    tris.extend(self._verb_obj_list(body_formula))
                continue
            tris.extend(self._triple_pattern())
        self._eat("RBR")
        self._formula_triples_stack.pop()
        return Formula(tuple(tris))

    # -- triple patterns -----------------------------------------------------

    def _triple_pattern(self) -> list[Triple]:
        subj = self._item()
        return self._verb_obj_list(subj)

    def _verb_obj_list(self, subj: Term) -> list[Triple]:
        out: list[Triple] = []
        # If the subject is followed immediately by a path operator, expand it.
        # E.g. ``(?L ?L) ! math:product math:lessThan ?N`` — the ``!math:product``
        # modifies the list subject, producing a new existential as the effective subj.
        subj = self._maybe_path(subj)
        # Bare blank node: [ p o ] . — blank node properties already emitted; no verb follows
        if self._peek().t in ("DOT", "RBR", "ANNOT_OPEN", "EOF"):
            if self._peek().t == "DOT":
                self._eat("DOT")
            return out
        while True:
            # Handle inverse predicate: `<-pred obj` → Triple(obj, pred, subj)
            if self._peek().t == "PREDINV":
                self._eat("PREDINV")
                pred = self._item()
                objs = self._obj_list()
                for o in objs:
                    out.append(Triple(o, pred, subj))
                if self._peek().t == "SC":
                    self._eat("SC")
                    if self._peek().t in ("RBR", "DOT"):
                        break
                else:
                    break
                continue
            pred = self._verb()

            # C8 fix: `=` sugar — owl:sameAs
            if self._peek().t == "EQ":
                self._eat("EQ")
                obj = self._item()
                out.append(Triple(subj, pred, obj))
                # Emit owl:sameAs triple
                same_as = NamedNode("http://www.w3.org/2002/07/owl#sameAs")
                out.append(Triple(subj, same_as, obj))
                if self._peek().t == "SC":
                    self._eat("SC")
                    if self._peek().t in ("RBR", "DOT"):
                        break
                continue

            # Phase 2: `of` sugar — swaps subject and object
            # `:Bob :child of :Alice` → `:Alice :child :Bob`
            of_target = None
            if self._peek().t == "OF_KW":
                self._eat("OF_KW")
                of_target = self._item()
                # `of` provides the "object" already, no need for _obj_list
                if of_target is not None:
                    out.append(Triple(of_target, pred, subj))
            else:
                # Phase 2: skip `has` / `is` keyword between predicate and object
                if self._peek().t in ("HAS_KW", "IS_KW"):
                    self._eat_any()
                objs = self._obj_list()
                for o in objs:
                    out.append(Triple(subj, pred, o))

            # If `of` was used, the effective subject for next semicolon clause is the of_target
            if of_target is not None:
                subj = of_target

            # RDF 1.2 reifier on the object: ``s p o ~ :id`` — consume the
            # reifier identifier (reification handled at use site for now).
            if self._peek().t == "TILDE":
                self._eat("TILDE")
                self._item()
            if self._peek().t == "SC":
                self._eat("SC")
                # After semicolon, also check for `has`/`is`
                if self._peek().t in ("HAS_KW", "IS_KW"):
                    self._eat_any()
                if self._peek().t in ("RBR", "DOT"):
                    break
            else:
                break
        # N3 quad: a 4th term after the object names the graph (top-level data
        # only).  ``:s :p :o _:g .`` → quad with ``_:g`` as graph.
        if (not self._formula_triples_stack
                and self._peek().t in _GRAPH_TERM_START):
            graph = self._item()
            for tr in out:
                self._quads.append(Quad(tr.subject, tr.predicate, tr.object, graph))
            out = []
        # RDF 1.2 annotation syntax: ``triple {| prop val |}`` — expand each
        # block to triples about the annotated triple's triple term.  Repeated
        # blocks (``s p o {| ... |} {| ... |}``) all annotate the base triple.
        base = list(out[-1:])
        while self._peek().t == "ANNOT_OPEN":
            out.extend(self._parse_annotation(base))
        if self._peek().t == "DOT":
            self._eat("DOT")
        return out

    def _parse_annotation(self, base_triples: list[Triple]) -> list[Triple]:
        """Parse ``{| prop val ; ... |}``, returning the expanded triples.

        Each annotation pair becomes ``<< s p o >> prop val`` for every base
        triple (the triple term stands for the annotated statement).
        """
        self._eat("ANNOT_OPEN")
        pairs: list[tuple[Term, Term]] = []
        while self._peek().t not in ("ANNOT_CLOSE", "EOF"):
            if self._peek().t == "SC":
                self._eat("SC")
                continue
            pred = self._verb()
            for o in self._obj_list():
                pairs.append((pred, o))
        if self._peek().t == "ANNOT_CLOSE":
            self._eat("ANNOT_CLOSE")
        expanded: list[Triple] = []
        for bt in base_triples:
            tt = TripleTerm(bt.subject, bt.predicate, bt.object)
            for pred, o in pairs:
                expanded.append(Triple(tt, pred, o))
        return expanded

    def _skip_annotation(self) -> None:
        """Skip an RDF 1.2 annotation block ``{| prop val ; ... |}``."""
        self._eat("ANNOT_OPEN")
        depth = 1
        while depth > 0:
            t = self._peek()
            if t.t == "ANNOT_OPEN":
                depth += 1
                self._eat_any()
            elif t.t == "ANNOT_CLOSE":
                depth -= 1
                self._eat_any()
            elif t.t == "EOF":
                break
            else:
                self._eat_any()

    def _verb(self) -> Term:
        t = self._peek()
        if t.t == "KW" and t.v == "a":
            self._eat("KW")
            return RDF_TYPE
        # N3/EYE `=` shorthand for owl:sameAs when used as predicate
        if t.t == "EQ":
            self._eat("EQ")
            return NamedNode("http://www.w3.org/2002/07/owl#sameAs")
        return self._item()

    def _obj_list(self) -> list[Term]:
        objs = [self._item()]
        while self._peek().t == "CM":
            self._eat("CM")
            objs.append(self._item())
        return objs

    # -- items (IRI, var, blank, literal, list, formula) ---------------------

    def _item(self) -> Term:
        t = self._peek()

        # Phase 2: triple term << S P O >>
        if t.t == "TTOPEN":
            return self._maybe_path(self._triple_term())

        # Phase 2: formula term (| Functor Args |)
        if t.t == "FTOPEN":
            return self._maybe_path(self._formula_term())

        # Phase 2: set ($ a b $)
        if t.t == "SETOPEN":
            return self._maybe_path(self._set_term())

        # A path operator must follow a subject term; a bare leading !/^ is
        # invalid.  Path expressions after a term are compiled by _maybe_path.
        if t.t in ("OP_FWD", "OP_REV"):
            raise ParseError(
                f"Unexpected path operator {t.v!r} at {self._src}:{self._i} "
                "— a path step must follow a subject term"
            )

        # Single-token prefixed name (Turtle PNAME): ``ex:foo``, ``:foo``,
        # ``res:COUNTRY_United%20States`` — expanded directly.
        if t.t == "PNAME":
            self._eat("PNAME")
            return self._maybe_path(self._pm.expand(t.v))

        # Keyword tokens that can appear as local names in prefixed names
        _LOCAL_NAME_TOKENS = frozenset(("KW", "IS_KW", "HAS_KW", "OF_KW", "GRAPH_KW", "TRUE", "FALSE"))

        # Prefixed name: :foo → COLON + KW
        # Also handles digit-starting local names: :3outof5 → COLON + NUM + KW
        if t.t == "COLON":
            self._eat("COLON")
            lt = self._peek()
            if lt.t in _LOCAL_NAME_TOKENS:
                local = self._eat_any().v
            elif lt.t == "NUM":
                # Digit-starting local name: :3outof5 → combine NUM + optional KW
                local = self._eat_any().v
                if self._peek().t in _LOCAL_NAME_TOKENS:
                    local += self._eat_any().v
            else:
                local = ""
            return self._maybe_path(self._pm.expand(":" + local))

        # Prefixed name: ex:foo → KW + COLON + KW
        # Also handles ex:3outof5 → KW + COLON + NUM + KW
        if t.t == "KW" and self._i + 1 < len(self._toks) and self._toks[self._i + 1].t == "COLON":
            prefix = self._eat("KW").v
            self._eat("COLON")
            lt = self._peek()
            if lt.t in _LOCAL_NAME_TOKENS:
                local = self._eat_any().v
            elif lt.t == "NUM":
                local = self._eat_any().v
                if self._peek().t in _LOCAL_NAME_TOKENS:
                    local += self._eat_any().v
            else:
                local = ""
            return self._maybe_path(self._pm.expand(prefix + ":" + local))

        if t.t == "IRI":
            self._eat("IRI")
            return self._maybe_path(NamedNode(self._resolve_iri(t.v[1:-1])))
        if t.t == "VAR":
            self._eat("VAR")
            name = t.v[1:]  # strip leading ?
            # Reuse the same Variable for the same name within the current scope
            if name not in self._var_scope:
                self._var_scope[name] = Variable(name)
            return self._maybe_path(self._var_scope[name])
        if t.t == "BLANK":
            self._eat("BLANK")
            return self._maybe_path(Existential(t.v[2:]))     # strip _:
        # C1 fix: Boolean literals
        if t.t == "TRUE":
            self._eat("TRUE")
            return Literal("true", datatype=NamedNode("http://www.w3.org/2001/XMLSchema#boolean"))
        if t.t == "FALSE":
            self._eat("FALSE")
            return Literal("false", datatype=NamedNode("http://www.w3.org/2001/XMLSchema#boolean"))
        if t.t == "LBK":
            return self._maybe_path(self._bnode())
        if t.t == "LP":
            return self._maybe_path(self._rdf_list())
        if t.t == "LBR":
            return self._maybe_path(self._formula())
        if t.t in ("STR", "LONGSTR", "NUM"):
            return self._literal()
        if t.t == "KW" and t.v == "a":
            self._eat("KW")
            return RDF_TYPE
        # Bare keyword → expand as local name
        if t.t == "KW":
            self._eat("KW")
            return self._pm.expand(t.v)
        raise ParseError(f"Unexpected {t.t} '{t.v}' at {self._src}:{self._i}")

    def _maybe_path(self, term: Term) -> Term:
        """After parsing a term, expand any following ! (forward) or ^ (reverse) path ops.

        ``a ! p ! q`` expands as:
            _:b1 . a p _:b1 .    (forward: a -> p -> _:b1)
            _:b2 . _:b1 q _:b2 . (forward: _:b1 -> q -> _:b2)
        returns _:b2.

        ``a ^ p`` expands as:
            _:b1 . _:b1 p a .    (reverse: _:b1 -> p -> a)
        returns _:b1.
        """
        cur = term
        while self._peek().t in ("OP_FWD", "OP_REV"):
            op = self._eat_any().t
            pred = self._item_no_path()
            # Inside a formula (rule body/head) the fresh path node is a logic
            # Variable: it is the output slot the path step binds (e.g. a builtin
            # result) and must propagate to wherever the path term is used.  In
            # top-level data a path introduces an existential blank node, which
            # is asserted as a ground fact rather than bound.
            if self._formula_triples_stack:
                nxt: Term = Variable(f"_p{self._bn}")
            else:
                nxt = Existential(f"_b{self._bn}")
            self._bn += 1
            if op == "OP_FWD":
                self._current_triples.append(Triple(cur, pred, nxt))
            else:
                self._current_triples.append(Triple(nxt, pred, cur))
            cur = nxt
        return cur

    def _item_no_path(self) -> Term:
        """Parse a single term WITHOUT expanding path operators afterward.

        Used internally by _maybe_path to read the predicate of a path step,
        preventing infinite recursion.
        """
        t = self._peek()

        _LOCAL_NAME_TOKENS = frozenset(("KW", "IS_KW", "HAS_KW", "OF_KW", "GRAPH_KW", "TRUE", "FALSE"))

        if t.t == "PNAME":
            self._eat("PNAME")
            return self._pm.expand(t.v)

        if t.t == "COLON":
            self._eat("COLON")
            lt = self._peek()
            local = self._eat_any().v if lt.t in _LOCAL_NAME_TOKENS else ""
            return self._pm.expand(":" + local)

        if t.t == "KW" and self._i + 1 < len(self._toks) and self._toks[self._i + 1].t == "COLON":
            prefix = self._eat("KW").v
            self._eat("COLON")
            lt = self._peek()
            local = self._eat_any().v if lt.t in _LOCAL_NAME_TOKENS else ""
            return self._pm.expand(prefix + ":" + local)

        if t.t == "IRI":
            self._eat("IRI")
            return NamedNode(self._resolve_iri(t.v[1:-1]))

        if t.t == "VAR":
            self._eat("VAR")
            name = t.v[1:]
            if name not in self._var_scope:
                self._var_scope[name] = Variable(name)
            return self._var_scope[name]

        raise ParseError(f"Expected IRI or prefixed name in path at {self._src}:{self._i}")

    # -- blank nodes ---------------------------------------------------------

    def _bnode(self) -> Term:
        self._eat("LBK")
        name = f"_b{self._bn}"
        self._bn += 1
        node = Existential(name)
        if self._peek().t == "RBK":
            self._eat("RBK")
            return node
        while self._peek().t != "RBK":
            pred = self._verb()
            objs = self._obj_list()
            for o in objs:
                # Route blank-node property triples into the formula when
                # inside { ... }, so they become part of the rule body/head.
                self._current_triples.append(Triple(node, pred, o))
            if self._peek().t == "SC":
                self._eat("SC")
        self._eat("RBK")
        return node

    # -- RDF lists -----------------------------------------------------------

    def _rdf_list(self) -> Term:
        """Parse ``(a b c)`` into a ListTerm (native list, no rdf:first/rest)."""
        self._eat("LP")
        items: list[Term] = []
        while self._peek().t != "RP":
            items.append(self._item())
        self._eat("RP")
        return ListTerm(items=tuple(items))

    # -- literals ------------------------------------------------------------

    def _literal(self) -> Term:
        t = self._eat_any()
        # Strip quotes
        v = t.v
        if v.startswith('"""') and v.endswith('"""'):
            v = v[3:-3]
        elif v.startswith("'''") and v.endswith("'''"):
            v = v[3:-3]
        elif v.startswith('"') and v.endswith('"'):
            v = v[1:-1]

        # M1 fix: Decode escape sequences
        v = self._decode_escapes(v)

        # Datatype
        if self._peek().t == "HATHAT":
            self._eat("HATHAT")
            nt = self._peek()
            if nt.t == "IRI":
                dt = NamedNode(self._eat("IRI").v[1:-1])
            else:
                # Prefixed name: xsd:date, xsd:integer, etc.
                dt_term = self._item()
                if isinstance(dt_term, NamedNode):
                    dt = dt_term
                else:
                    raise ParseError(f"Expected IRI or prefixed name after ^^, got {nt.t} '{nt.v}'")
            return Literal(v, datatype=dt)

        # Language tag
        if self._peek().t == "LANG":
            lang = self._eat("LANG").v[1:]
            return Literal(v, language=lang)

        # Numeric
        if t.t == "NUM":
            if "." in v or "e" in v.lower():
                dt = NamedNode("http://www.w3.org/2001/XMLSchema#double")
            else:
                dt = NamedNode("http://www.w3.org/2001/XMLSchema#integer")
            return Literal(v, datatype=dt)

        return Literal(v)

    @staticmethod
    def _decode_escapes(s: str) -> str:
        """M1 fix: Decode common escape sequences in string literals."""
        escape_map = {
            'n': '\n', 't': '\t', 'r': '\r', '\\': '\\',
            '"': '"', "'": "'", '/': '/',
        }
        result = []
        i = 0
        while i < len(s):
            if s[i] == '\\' and i + 1 < len(s):
                next_char = s[i + 1]
                if next_char in escape_map:
                    result.append(escape_map[next_char])
                    i += 2
                    continue
                # Unicode escape: \uXXXX
                if next_char == 'u' and i + 5 < len(s):
                    try:
                        result.append(chr(int(s[i+2:i+6], 16)))
                        i += 6
                        continue
                    except ValueError:
                        pass
            result.append(s[i])
            i += 1
        return ''.join(result)

    # -- Phase 2: triple terms << S P O >> -----------------------------------

    def _triple_term(self) -> TripleTerm:
        """Parse ``<< S P O >>`` or ``<<( S P O )>>`` into a TripleTerm."""
        self._eat("TTOPEN")
        # EYE uses <<( S P O )>> syntax (parenthesised form)
        paren = self._peek().t == "LP"
        if paren:
            self._eat("LP")
        s = self._item()
        p = self._item()
        o = self._item()
        # Optional reifier marker: ``<< s p o ~ :id >>`` names the reified
        # statement; the identifier is consumed (reification handled at use site).
        if self._peek().t == "TILDE":
            self._eat("TILDE")
            self._item()  # consume reifier id, ignore for now
        if paren:
            self._eat("RP")
        self._eat("TTCLOSE")
        return TripleTerm(s, p, o)

    # -- Phase 2: formula terms (| Functor Args |) --------------------------

    def _formula_term(self) -> FormulaTerm:
        """Parse ``(| Functor Args |)`` into a FormulaTerm."""
        self._eat("FTOPEN")
        functor = self._item()
        args: list[Term] = []
        while self._peek().t != "FTCLOSE":
            args.append(self._item())
        self._eat("FTCLOSE")
        return FormulaTerm(functor, tuple(args))

    # -- Phase 2: set terms ($ a b $) ----------------------------------------

    def _set_term(self) -> SetTerm:
        """Parse ``($ a b $)`` into a SetTerm.

        M5 fix: Sets are now proper unordered collections (SetTerm),
        not RDF lists.
        """
        self._eat("SETOPEN")
        items: list[Term] = []
        while self._peek().t != "SETCLOSE":
            items.append(self._item())
        self._eat("SETCLOSE")
        return SetTerm(tuple(items))

    # -- data triples (no rules) ---------------------------------------------

    def _do_data(self) -> None:
        subj = self._item()
        # Bnode/IRI-labelled graph: ``_:g { ... }`` or ``<g> { ... }`` at top
        # level — the leading term names the graph, the block holds its triples.
        # (N3-plus / TriG-in-N3, used by the ldes and n3plus1 scenarios.)
        if self._peek().t == "LBR":
            body = self._formula()
            for tr in body.triples:
                self._quads.append(Quad(tr.subject, tr.predicate, tr.object, subj))
            if self._peek().t == "DOT":
                self._eat("DOT")
            return
        # A bare blank node `[ ... ] .` is a valid top-level statement in N3.
        # The blank node's properties are already added inside _bnode(), so if
        # the next token is just a DOT, eat it and return.
        if self._peek().t == "DOT":
            self._eat("DOT")
            return
        # Handle bare-term backward rule: `true <= { ... } .`
        # These arise in EYE N3 files like: `true <= { <body> }.`
        if self._peek().t == "IMPB":
            self._eat("IMPB")
            if self._peek().t == "TRUE":
                self._eat("TRUE")
                body_formula = Formula(())
            else:
                body_formula = self._formula()
            self._eat("DOT")
            # Wrap head in a 1-triple formula: {subj :is :true} or treat as unit
            # For now: create an empty head formula (facts derived trivially)
            # The backward rule says: whenever body holds, derive subj.
            # If subj is a literal like `true`, this means "the body is always satisfiable".
            # We skip execution but record it as a backward rule.
            head_formula = Formula(())
            self._rules.append(Rule(
                body_formula, head_formula, self._src,
                for_some=tuple(self._for_some),
                for_all=tuple(self._for_all),
                is_backward=True,
            ))
            return
        new = self._verb_obj_list(subj)
        # Check if this turned out to be a rule (=> in predicate position)
        if self._triples and self._triples[-1].predicate.value.endswith("implies"):  # pragma: no cover — dead code: data mode never produces implies triples
            pass
        self._triples.extend(new)

    # -- tokenizer helpers ---------------------------------------------------

    def _peek(self) -> Tok:
        if self._i >= len(self._toks):
            return Tok("EOF", "")  # pragma: no cover — tokenizer always appends EOF token
        return self._toks[self._i]

    def _eat_any(self) -> Tok:
        t = self._toks[self._i]
        self._i += 1
        return t

    def _eat(self, kind: str) -> Tok:
        t = self._peek()
        if t.t != kind:
            raise ParseError(f"Expected {kind}, got {t.t} '{t.v}' at {self._src}:{self._i}")
        self._i += 1
        return t

    def _eof(self) -> bool:
        return self._peek().t == "EOF"


# ---------------------------------------------------------------------------
# Data loading helpers (rdflib)
# ---------------------------------------------------------------------------

def _to_term(obj) -> Term:
    if isinstance(obj, URIRef):
        return NamedNode(str(obj))
    if isinstance(obj, RDFLiteral):
        return Literal(
            str(obj),
            datatype=NamedNode(str(obj.datatype)) if obj.datatype else None,
            language=str(obj.language) if obj.language else None,
        )
    if isinstance(obj, BNode):
        return Existential(str(obj))
    raise ValueError(f"Unknown rdflib term: {type(obj)}")  # pragma: no cover — rdflib only returns URIRef, Literal, BNode


def _graph_to_triples(g) -> list[Triple]:
    """Convert an rdflib graph to pyeye triples.

    RDF collections — which rdflib parses into ``rdf:first``/``rdf:rest``
    blank-node chains — are rebuilt as native ``ListTerm`` values, matching
    pyeye's own N3 parser (``(a b c)`` → ``ListTerm``), so the ``list:``
    builtins see the same representation regardless of which parser loaded
    the data.
    """
    rdf_first = RDF.first
    rdf_rest = RDF.rest
    rdf_nil = RDF.nil

    firsts: dict = {}
    rests: dict = {}
    malformed: set = set()
    for s, p, o in g:
        if isinstance(s, BNode):
            if p == rdf_first:
                if s in firsts:
                    malformed.add(s)
                firsts[s] = o
            elif p == rdf_rest:
                if s in rests:
                    malformed.add(s)
                rests[s] = o
    chain_nodes = {n for n in firsts if n in rests and n not in malformed}

    list_heads: dict = {}   # chain head -> ListTerm (memoised)
    consumed: set = set()   # chain nodes folded into a ListTerm

    def convert(obj):
        if obj == rdf_nil:
            return ListTerm(items=())
        if isinstance(obj, BNode) and obj in chain_nodes:
            lt = make_list(obj)
            if lt is not None:
                return lt
        return _to_term(obj)

    def make_list(head):
        if head in list_heads:
            return list_heads[head]
        chain = []
        seen: set = set()
        cur = head
        while cur != rdf_nil:
            if not isinstance(cur, BNode) or cur not in chain_nodes or cur in seen:
                return None  # broken or cyclic chain — leave as raw triples
            seen.add(cur)
            chain.append(cur)
            cur = rests[cur]
        lt = ListTerm(items=tuple(convert(firsts[n]) for n in chain))
        list_heads[head] = lt
        consumed.update(chain)
        return lt

    for n in list(chain_nodes):
        make_list(n)

    triples: list[Triple] = []
    for s, p, o in g:
        if isinstance(s, BNode) and s in consumed and p in (rdf_first, rdf_rest):
            continue
        triples.append(Triple(convert(s), convert(p), convert(o)))
    return triples


def load_data_file(path: str | Path) -> ParsedDocument:
    """Load pure data N3/Turtle via rdflib."""
    g = Graph()
    g.parse(str(path), format="turtle")
    pm = PrefixManager()
    return ParsedDocument(
        triples=_graph_to_triples(g),
        prefixes=pm.prefixes,
    )


def load_data_string(text: str) -> ParsedDocument:
    """Load N3/Turtle data from a string.

    Delegates to rdflib for pure data (no rules). Falls back to pyeye's own
    N3 parser when the input contains N3 constructs rdflib doesn't handle:
    formulas/rules (``{...} => {...}``), backward rules (``<=``), or inverse
    predicates (``<-``).
    """
    import re as _re
    # Fast pre-check: if input contains N3-only constructs, use pyeye parser
    if _re.search(r'=>|<=|<-[<:]', text):
        return parse_n3(text)
    from rdflib.graph import QuotedGraph as _QuotedGraph
    try:
        g = Graph()
        g.parse(data=text, format="n3")
    except Exception:
        return parse_n3(text)
    # Check if any term is a QuotedGraph (formula)
    for s, p, o in g:
        if isinstance(s, _QuotedGraph) or isinstance(p, _QuotedGraph) or isinstance(o, _QuotedGraph):
            return parse_n3(text)
    pm = PrefixManager()
    return ParsedDocument(
        triples=_graph_to_triples(g),
        prefixes=pm.prefixes,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_n3(text: str, source: str = "") -> ParsedDocument:
    """Parse an N3 file that may contain both data triples and rules."""
    return Parser(text, source=source).parse()


def parse_rules(text: str, source: str = "") -> list[Rule]:
    """Parse only the rules from an N3 text."""
    return Parser(text, source=source).parse().rules
