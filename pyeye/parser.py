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
    # Phase 2 extended types
    TripleTerm,
    FormulaTerm,
    PathTerm,
    NegativeSurface,
    Quad,
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


@dataclass
class ParsedDocument:
    """Result of parsing an N3/TriG file."""
    triples: list[Triple] = field(default_factory=list)
    quads: list[Quad] = field(default_factory=list)
    rules: list[Rule] = field(default_factory=list)
    prefixes: dict[str, str] = field(default_factory=dict)
    base: str | None = None


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
        return NamedNode(ns + local)


# ---------------------------------------------------------------------------
# Tokenizer
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Tok:
    t: str  # type
    v: str  # value


def tokenize(text: str) -> list[Tok]:
    """Lex N3 text into tokens.  Skips comments and whitespace."""
    specs: list[tuple[str, str]] = [
        ("LONGSTR", r"'''[\s\S]*?'''|\"\"\"[\s\S]*?\"\"\""),
        ("STR",     r'"(?:[^"\\]|\\.)*"'),
        ("TTOPEN",  r"<<"),         # Phase 2: triple term open — before IRI!
        ("TTCLOSE", r">>"),         # Phase 2: triple term close — before IRI!
        ("IRI",     r"<[^>]+>"),
        ("PFX",     r"@prefix\b"),
        ("BASE",    r"@base\b"),
        ("FSOME",   r"@forSome\b"),
        ("FALL",    r"@forAll\b"),
        ("IMPF",    r"=>"),
        ("IMPB",    r"<="),
        ("HATHAT",  r"\^\^"),
        ("PREDINV", r"<-"),
        ("FTOPEN",  r"\(\|"),       # Phase 2: formula term open
        ("FTCLOSE", r"\|\)"),       # Phase 2: formula term close
        ("SETOPEN", r"\(\$"),       # Phase 2: set open
        ("SETCLOSE", r"\$\)"),      # Phase 2: set close
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
        ("OF_KW",   r"\bof\b"),     # Phase 2: "of" keyword
        ("HAS_KW",  r"\bhas\b"),    # Phase 2: "has" keyword
        ("IS_KW",   r"\bis\b"),     # Phase 2: "is" keyword
        ("GRAPH_KW", r"\bGRAPH\b"), # Phase 2: TriG graph keyword
        ("TRUE",    r"\btrue\b"),   # Boolean literal
        ("FALSE",   r"\bfalse\b"),  # Boolean literal
        ("VAR",     r"\?[^\W\d]\w*"),  # C9 fix: Unicode variable names
        ("BLANK",   r"_:[^\W\d]\w*"),  # C9 fix: Unicode blank node names
        ("LANG",    r"@[A-Za-z]+(-[A-Za-z0-9]+)*"),
        ("COLON",   r":"),
        ("NUM",     r"[+-]?(\d+\.?\d*|\.\d+)([eE][+-]?\d+)?"),
        ("KW",      r"[^\W\d]\w*"),   # C9 fix: Unicode keywords (local names)
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
        out.append(Tok(kind, val))
    out.append(Tok("EOF", ""))
    return out


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

    def parse(self) -> ParsedDocument:
        while not self._eof():
            self._stmt()
        return ParsedDocument(
            triples=self._triples,
            quads=list(self._quads),
            rules=self._rules,
            prefixes=self._pm.prefixes,
            base=self._pm._base,
        )

    # -- statement dispatch --------------------------------------------------

    def _stmt(self) -> None:
        t = self._peek()
        if t.t == "PFX":
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
        self._eat("PFX")
        t = self._peek()
        if t.t == "COLON":
            # @prefix : <...>
            self._eat("COLON")
            prefix = ""
        elif t.t == "KW" and self._i + 1 < len(self._toks) and self._toks[self._i + 1].t == "COLON":
            # @prefix ex: <...>
            prefix = self._eat("KW").v
            self._eat("COLON")
        else:
            # @prefix ex <...> (no colon — non-standard but accept it)
            prefix = self._eat_any().v.rstrip(":")
        uri = self._eat("IRI").v[1:-1]
        self._pm.register(prefix, uri)
        self._eat("DOT")

    def _do_base(self) -> None:
        self._eat("BASE")
        self._pm._base = self._eat("IRI").v[1:-1]
        self._eat("DOT")

    def _do_quantifier(self) -> None:
        """Consume @forSome/@forAll <var>, <var> ."""
        self._eat_any()
        while self._peek().t not in ("DOT", "EOF"):
            if self._peek().t == "CM":
                self._eat("CM")
            else:
                self._eat_any()
        if self._peek().t == "DOT":
            self._eat("DOT")

    # -- TriG: GRAPH <g> { ... } --------------------------------------------

    def _do_graph(self) -> None:
        """Parse ``GRAPH <graph_id> { ... triples ... }`` into quads."""
        self._eat("GRAPH_KW")
        # Parse graph identifier
        graph_id = self._item()
        # Parse the graph body (formula)
        body = self._formula()
        # Convert triples to quads
        for t in body.triples:
            self._quads.append(Quad(t.subject, t.predicate, t.object, graph_id))

    @property
    def _quads(self) -> list[Quad]:
        """Access the parser's quad list (stored on the instance)."""
        if not hasattr(self, "_quads_list"):
            self._quads_list: list[Quad] = []
        return self._quads_list

    # -- rules / formulas ----------------------------------------------------

    def _do_formula_top(self) -> None:
        body = self._formula()
        t = self._peek()
        if t.t == "IMPF":
            self._eat("IMPF")
            head = self._formula()
            self._eat("DOT")
            self._rules.append(Rule(body, head, self._src))
        elif t.t == "IMPB":
            self._eat("IMPB")
            head = self._formula()
            self._eat("DOT")
            self._rules.append(Rule(head, body, self._src))  # reverse
        elif t.t == "DOT":
            self._eat("DOT")
            self._triples.extend(body.triples)
        else:
            raise ParseError(f"Expected => or <= or . got {t.t}")

    def _formula(self) -> Formula:
        self._eat("LBR")
        tris: list[Triple] = []
        while self._peek().t != "RBR":
            tris.extend(self._triple_pattern())
        self._eat("RBR")
        return Formula(tris)

    # -- triple patterns -----------------------------------------------------

    def _triple_pattern(self) -> list[Triple]:
        subj = self._item()
        return self._verb_obj_list(subj)

    def _verb_obj_list(self, subj: Term) -> list[Triple]:
        out: list[Triple] = []
        while True:
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

            if self._peek().t == "SC":
                self._eat("SC")
                # After semicolon, also check for `has`/`is`
                if self._peek().t in ("HAS_KW", "IS_KW"):
                    self._eat_any()
                if self._peek().t in ("RBR", "DOT"):
                    break
            else:
                break
        if self._peek().t == "DOT":
            self._eat("DOT")
        return out

    def _verb(self) -> Term:
        t = self._peek()
        if t.t == "KW" and t.v == "a":
            self._eat("KW")
            return RDF_TYPE
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
            return self._triple_term()

        # Phase 2: formula term (| Functor Args |)
        if t.t == "FTOPEN":
            return self._formula_term()

        # Phase 2: set ($ a b $)
        if t.t == "SETOPEN":
            return self._set_term()

        # Phase 2: path expression starting with !
        if t.t == "OP_FWD":
            return self._path_expression()

        # Phase 2: path expression starting with ^
        if t.t == "OP_REV":
            return self._path_expression()

        # Prefixed name: :foo → COLON + KW
        if t.t == "COLON":
            self._eat("COLON")
            lt = self._peek()
            local = self._eat("KW").v if lt.t == "KW" else ""
            return self._pm.expand(":" + local)

        # Prefixed name: ex:foo → KW + COLON + KW
        if t.t == "KW" and self._i + 1 < len(self._toks) and self._toks[self._i + 1].t == "COLON":
            prefix = self._eat("KW").v
            self._eat("COLON")
            lt = self._peek()
            local = self._eat("KW").v if lt.t == "KW" else ""
            return self._pm.expand(prefix + ":" + local)

        if t.t == "IRI":
            self._eat("IRI")
            return NamedNode(t.v[1:-1])
        if t.t == "VAR":
            self._eat("VAR")
            return Variable(t.v[1:])       # strip ?
        if t.t == "BLANK":
            self._eat("BLANK")
            return Existential(t.v[2:])     # strip _:
        # C1 fix: Boolean literals
        if t.t == "TRUE":
            self._eat("TRUE")
            return Literal("true", datatype=NamedNode("http://www.w3.org/2001/XMLSchema#boolean"))
        if t.t == "FALSE":
            self._eat("FALSE")
            return Literal("false", datatype=NamedNode("http://www.w3.org/2001/XMLSchema#boolean"))
        if t.t == "LBK":
            return self._bnode()
        if t.t == "LP":
            return self._rdf_list()
        if t.t == "LBR":
            return self._formula()
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
                self._triples.append(Triple(node, pred, o))
            if self._peek().t == "SC":
                self._eat("SC")
        self._eat("RBK")
        return node

    # -- RDF lists -----------------------------------------------------------

    def _rdf_list(self) -> Term:
        self._eat("LP")
        items: list[Term] = []
        while self._peek().t != "RP":
            items.append(self._item())
        self._eat("RP")
        if not items:
            return Existential("nil")
        rdf = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
        first_p = NamedNode(rdf + "first")
        rest_p = NamedNode(rdf + "rest")
        nil = Existential("nil")
        head = Existential(f"_b{self._bn}")
        self._bn += 1
        cur = head
        for i, item in enumerate(items):
            self._triples.append(Triple(cur, first_p, item))
            if i < len(items) - 1:
                nxt = Existential(f"_b{self._bn}")
                self._bn += 1
                self._triples.append(Triple(cur, rest_p, nxt))
                cur = nxt
            else:
                self._triples.append(Triple(cur, rest_p, nil))
        return head

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
            dt = NamedNode(self._eat("IRI").v[1:-1])
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
        """Parse ``<< S P O >>`` into a TripleTerm."""
        self._eat("TTOPEN")
        s = self._item()
        p = self._item()
        o = self._item()
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

    def _set_term(self) -> Existential:
        """Parse ``($ a b $)`` — Phase 1: treated as an anonymous blank node.

        Full set semantics (unordered, membership testing) is Phase 2b.
        For now, we just parse and generate a blank node with rdf:first/rdf:rest
        like an RDF list, but without ordering guarantees.
        """
        self._eat("SETOPEN")
        items: list[Term] = []
        while self._peek().t != "SETCLOSE":
            items.append(self._item())
        self._eat("SETCLOSE")
        # For now, treat sets like lists (Phase 2b: proper set semantics)
        rdf = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"
        first_p = NamedNode(rdf + "first")
        rest_p = NamedNode(rdf + "rest")
        nil = Existential("nil")
        if not items:
            return nil
        head = Existential(f"_b{self._bn}")
        self._bn += 1
        cur = head
        for i, item in enumerate(items):
            self._triples.append(Triple(cur, first_p, item))
            if i < len(items) - 1:
                nxt = Existential(f"_b{self._bn}")
                self._bn += 1
                self._triples.append(Triple(cur, rest_p, nxt))
                cur = nxt
            else:
                self._triples.append(Triple(cur, rest_p, nil))
        return head

    # -- Phase 2: path expressions :a ! :p ! :q / :a ^ :p --------------------

    def _path_expression(self) -> Term:
        """Parse ``! :p ! :q`` or ``^ :p`` into a PathTerm.

        The caller has already consumed the initial ``!`` or ``^`` token.
        C3 fix: Store a dummy subject; the real subject comes from the triple context.
        """
        terms: list[Term] = []
        directions: list[str] = []

        while self._peek().t in ("OP_FWD", "OP_REV"):
            op = self._eat_any().t
            directions.append("forward" if op == "OP_FWD" else "reverse")
            terms.append(self._item())

        if not terms:
            raise ParseError(f"Expected term after path operator at {self._src}:{self._i}")

        # C3 fix: Use None-like placeholder; actual subject comes from triple context
        return PathTerm(Existential("_path_placeholder"), tuple(terms), tuple(directions))

    # -- data triples (no rules) ---------------------------------------------

    def _do_data(self) -> None:
        subj = self._item()
        new = self._verb_obj_list(subj)
        self._triples.extend(new)

    # -- tokenizer helpers ---------------------------------------------------

    def _peek(self) -> Tok:
        if self._i >= len(self._toks):
            return Tok("EOF", "")
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
    raise ValueError(f"Unknown rdflib term: {type(obj)}")


def load_data_file(path: str | Path) -> ParsedDocument:
    """Load pure data N3/Turtle via rdflib."""
    g = Graph()
    g.parse(str(path), format="turtle")
    pm = PrefixManager()
    return ParsedDocument(
        triples=[Triple(_to_term(s), _to_term(p), _to_term(o)) for s, p, o in g],
        prefixes=pm.prefixes,
    )


def load_data_string(text: str) -> ParsedDocument:
    """Load N3/Turtle data from a string via rdflib."""
    g = Graph()
    g.parse(data=text, format="n3")
    pm = PrefixManager()
    return ParsedDocument(
        triples=[Triple(_to_term(s), _to_term(p), _to_term(o)) for s, p, o in g],
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
