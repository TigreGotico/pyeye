# FAQ

## Getting Started

### I have no idea what N3, RDF, or triples are. Where do I start?

Start with the [Getting Started guide](getting-started.md). The first section explains everything in plain English with no jargon.

In the simplest terms: pyeye lets you write **facts** (like "Alice is Bob's parent") and **rules** (like "if X is Y's parent, then Y is X's child"), and it automatically **figures out new facts** you didn't explicitly state (like "Bob is Alice's child").

### Do I need to know programming to use pyeye?

No. You can use it entirely from the command line:

```bash
pyeye --n3 facts.ttl --query rules.n3
```

If you want to use it from Python, you only need to call one function: `execute()`.

### What's the difference between N3 and Turtle?

- **Turtle** is a format for writing facts only. Like a list of statements.
- **N3** extends Turtle with **rules** — "if you see this, then conclude that."

If your file has `=>` in it, it's N3. If it only has facts, it can be either.

### What can I build with this?

Anything where you have data and want to automatically derive new information from it:

- **Family trees**: parents → children → grandparents → siblings
- **Business rules**: "orders over $1000 need review"
- **Smart home**: "if temperature > 30°C, turn on AC"
- **Access control**: "if user is admin, allow access to /settings"
- **Data cleaning**: "if email doesn't contain @, mark as invalid"
- **Knowledge graphs**: connecting facts through shared variables to discover relationships
- **Fact checking**: "if a claim contradicts known facts, flag it"

---

## Understanding Behavior

### What does "forward chaining" mean?

It means the engine works **forward** from your facts, applying rules to derive new facts, and repeating until nothing new can be found.

Think of it like a detective who starts with clues and follows every lead until there are no new leads to follow.

The alternative (**backward chaining**) starts with a question and works backward to find supporting facts. pyeye supports both — forward chaining is the default, backward chaining is triggered with `query=...`.

### What's a "fixpoint"?

The fixpoint is the moment when a full pass over all rules produces **zero new facts**. The engine stops because there's nothing left to derive.

With small rule sets, this happens in milliseconds. With large ones, you can use `--max-inferences` to stop early.

### What does "backward chaining" mean?

Backward chaining starts with a **goal** (a triple you want to prove) and works backward through rules to find evidence.

```python
from pyeye import execute
from pyeye.term import NamedNode, Variable, Triple

r = execute(
    data_strings=["@prefix : <http://ex.org/> .\n:alice :parent :bob ."],
    rule_strings=["@prefix : <http://ex.org/> .\n{?X :parent ?Y} => {?Y :child ?X} ."],
    query=Triple(NamedNode("http://ex.org/bob"), NamedNode("http://ex.org/child"), Variable("X")),
)
# r.query_answers = [{"X": NamedNode("http://ex.org/alice")}]
```

### Why don't I get infinite loops?

The engine keeps a record of every fact it has derived. If a rule tries to derive a fact that already exists, the engine skips it. This prevents rules like:

```n3
{ ?X :p ?Y } => { ?X :p ?Y } .
```

from running forever — the fact is already in the store, so nothing new is derived, and the engine reaches a fixpoint.

### How does DJITI improve performance?

DJITI (Deep Just-In-Time Indexing) reorders the patterns in a rule body so that the **most selective** pattern (fewest matching triples) is checked first.

If a rule body has three patterns that match 100, 50, and 1 triple respectively, DJITI checks them in order: 1, 50, 100. This dramatically reduces the number of combinations the engine needs to try.

### Why is it slow with lots of data?

Phase 1 uses a straightforward matching strategy: for each rule, try each pattern against every fact in the store. With many rules and many facts, this is O(n × k) where n is the number of facts and k is the number of rule patterns.

**Quick fixes:**
- Use `--max-inferences N` to cap execution
- Use `--tactic limited-answer N` to stop after N derivations
- Enable DJITI debug to see pattern ordering: it's on by default

**Long-term:** The predicate index in the store gives O(1) lookups when the predicate is a concrete `NamedNode`. For very large datasets, consider the TriG named graphs feature to partition data.

---

## Phase 2 Features

### How do I use OWL 2 RL entailment?

```bash
pyeye --n3 ontology.ttl --query rules.n3 --entail-owl
```

Or from Python:

```python
r = execute(data_strings=[...], rule_strings=[...], entail_owl=True)
```

OWL 2 RL entailment is a superset of RDFS entailment. It derives implicit triples from:

- **Property characteristics**: `owl:TransitiveProperty`, `owl:SymmetricProperty`, `owl:FunctionalProperty`, `owl:InverseFunctionalProperty`, `owl:inverseOf`
- **Individual equality**: `owl:sameAs`, `owl:differentFrom`
- **Class constructors**: `owl:intersectionOf`, `owl:unionOf`, `owl:someValuesFrom`, `owl:allValuesFrom`, `owl:hasValue`, `owl:oneOf`
- **Property chains**: `owl:propertyChainAxiom`
- **Equivalent classes and properties**: `owl:equivalentClass`, `owl:equivalentProperty`

`apply_owl_rl_entailment` — `pyeye/owl.py:81`

### How do I use RDFS entailment?

```bash
pyeye --n3 data.ttl --query rules.n3 --entail
```

Or from Python:

```python
r = execute(data_strings=[...], rule_strings=[...], entail=True)
```

This derives implicit triples from `rdfs:subClassOf`, `rdfs:subPropertyOf`, `rdfs:domain`, and `rdfs:range` declarations **before** running your user rules.

### How do I get proof traces?

```bash
pyeye --n3 data.ttl --query rules.n3 --explain --explain-format html > proof.html
```

Or from Python:

```python
r = execute(data_strings=[...], rule_strings=[...], explain=True)
print(r.explains)  # List of ProofTree objects
```

### How do I load data from a website?

```bash
pyeye --n3 http://example.org/data.ttl --query rules.n3 --cache-dir /tmp/cache
```

Or from Python:

```python
r = execute(data_paths=["http://example.org/data.ttl"], cache_dir="/tmp/cache")
```

HTTP loading includes SSRF protection: it rejects URLs targeting private IP ranges and non-HTTP schemes (file://, ftp://).

### How do I check that a triple is NOT derivable?

```bash
pyeye --n3 data.ttl --query rules.n3 --not-entail-triple http://ex.org/a,http://ex.org/p,http://ex.org/b
```

Or from Python:

```python
from pyeye.term import NamedNode, Triple
r = execute(
    data_strings=[...],
    rule_strings=[...],
    not_entail=Triple(NamedNode("http://ex.org/a"), NamedNode("http://ex.org/p"), NamedNode("http://ex.org/b")),
)
# r.stats["not_entail_failed"] is True if the triple WAS found (check failed)
# r.stats["not_entail_failed"] is False if the triple was NOT found (check passed)
```

### How do I use named graphs (TriG)?

```bash
pyeye --n3 data.trig --query rules.n3 --pass
```

TriG files use `GRAPH <id> { ... }` syntax. The engine stores triples in their named graphs, and you can query specific graphs using `match(graph=...)` in the Python API.

---

## Security

### Are any builtins dangerous?

Yes. Three builtins can execute external code or access external resources:

| Builtin | Risk | Mitigation |
| :--- | :--- | :--- |
| `e:calculate` | Was `eval()` — now uses `ast.literal_eval` (safe) | ✅ Only allows literals |
| `e:exec` / `e:shell` | Command execution | Allowlist of ~30 safe commands only |
| `log:ask` | HTTP requests | SSRF protection: rejects private IPs |

See [SECURITY.md](../SECURITY.md) for the full security model.

### How do I run pyeye safely with untrusted N3?

1. **Disable dangerous builtins**: Pass a custom `builtins={}` dict to `execute()`.
2. **Don't use HTTP loading**: Only pass local file paths or strings.
3. **Use a container**: Run pyeye in a Docker container with no network access.
4. **Set resource limits**: Use `max_steps` and `limit_answers` to prevent runaway reasoning.

```python
from pyeye import execute, BUILTIN_REGISTRY

# Safe mode: exclude command execution and HTTP
UNSAFE_PREFIXES = (
    "http://eulersharp.sourceforge.net/2003/03swap/log-rules#exec",
    "http://eulersharp.sourceforge.net/2003/03swap/log-rules#shell",
    "http://www.w3.org/2000/10/swap/log#ask",
)
SAFE_BUILTINS = {k: v for k, v in BUILTIN_REGISTRY.items()
                 if not any(k.startswith(p) for p in UNSAFE_PREFIXES)}

result = execute(
    data_strings=[...],
    rule_strings=[...],
    builtins=SAFE_BUILTINS,
    max_steps=10000,
)
```

---

## Installation

### How do I install pyeye?

```bash
cd /path/to/pyeye
pip install -e .
```

That's it. The only dependency is `rdflib`, which is installed automatically.

### What Python version do I need?

Python 3.11 or newer. Check with `python --version`.

### I got an error during installation

Make sure you have a Python virtual environment set up:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

---

## Troubleshooting

### My rule isn't firing. What's wrong?

The three most common causes:

1. **Prefix mismatch**: Your data uses `:alice` with one prefix, and your rule uses `:alice` with a different prefix. They look the same but have different full URLs. Use `--pass` to see what the engine actually sees.

2. **Variable names**: `?X` and `?x` are different variables (case-sensitive). Make sure the same variable name appears in both the body and head if you want them connected.

3. **Typo in predicate**: `:parent` vs `:parents` — one letter off, zero matches.

### Why is my output empty?

By default, pyeye only shows **new** facts derived by rules. If no rules fired, the output is empty.

To see everything (including your original facts), add `--pass`:

```bash
pyeye --n3 data.ttl --query rules.n3 --pass
```

Or from Python:

```python
r = execute(..., pass_mode=True)
```

### How do I see what's in the store?

Use `--pass` mode (CLI) or `pass_mode=True` (Python). This shows all facts — both the ones you provided and the ones the engine derived.

### How do I debug rule execution?

Use `--explain` to get proof traces. Each derived fact comes with a proof tree showing which rule fired and which facts triggered it.

```bash
pyeye --n3 data.ttl --query rules.n3 --explain --explain-format html > debug.html
```

Open `debug.html` in a browser for collapsible proof branches.

---

## Feature Summary

All features listed below are currently implemented:

| Feature | Available |
| :--- | :--- |
| Forward chaining | ✅ |
| Backward chaining | ✅ |
| Triple terms `<< >>` | ✅ |
| Formula terms `(| |)` | ✅ |
| Path expressions `!` / `^` | ✅ |
| `has`/`is`/`of` sugar | ✅ |
| BLOGIC negation | ✅ |
| Set syntax `($ $)` | ✅ |
| TriG named graphs | ✅ |
| RDFS entailment (`--entail`) | ✅ |
| OWL 2 RL entailment (`--entail-owl`) | ✅ |
| Proof traces | ✅ |
| DJITI indexing | ✅ |
| Incremental reasoning | ✅ |
| HTTP data loading | ✅ |
| Not-entail checking | ✅ |
| 240 builtins | ✅ |

---

## EYE vs HermiT: How They Complement Each Other

### What's the difference?

**EYE** (and pyeye) is an **N3 rule-based reasoner**. It uses forward and backward chaining over custom rules written in Notation3 logic. Think of it as a *programmable inference engine* — you write the rules, it applies them.

**HermiT** is an **OWL DL reasoner**. It uses hypertableau calculus to classify ontologies, check consistency, and compute subsumption hierarchies. Think of it as a *schema validator* — you define the ontology, it checks whether everything makes sense.

| Feature | EYE / pyeye | HermiT |
| :--- | :--- | :--- |
| **Logic** | First-order logic via N3 rules | Description Logic (OWL 2 DL) |
| **Reasoning style** | Forward + backward chaining | Hypertableau calculus |
| **Input** | N3 rules + data triples | OWL ontologies (RDF/XML, Turtle, Manchester) |
| **Strengths** | Custom business rules, data integration, agent communication | Ontology classification, consistency checking, subsumption |
| **Open world** | Yes (with explicit negation via BLOGIC) | Yes (full OWL open-world semantics) |
| **Expressivity** | Arbitrary Horn + non-Horn rules, meta-reasoning | OWL 2 DL (SROIQ(D)) — decidable but restricted |
| **Proof traces** | Yes — step-by-step derivation trees | Yes — explanation of entailments |
| **Typical use** | "If order > $1000, flag for review" | "Is Manager a subclass of Employee?" |

### When to use EYE / pyeye

- **Business rules**: "If temperature > 30°C AND room is occupied, turn on AC"
- **Data integration**: Merging facts from multiple sources with custom mapping rules
- **Agent communication**: Agents exchange N3 rules and derive shared conclusions
- **Dynamic reasoning**: Rules that modify other rules (`e:becomes`, `e:transaction`)
- **Explainable decisions**: Every derived fact comes with a proof tree
- **Anything that needs custom logic** beyond what OWL profiles can express

### When to use HermiT

- **Ontology development**: Checking that your class hierarchy is consistent
- **Classification**: Computing all implicit subsumption relationships
- **Consistency checking**: Finding contradictions in your ontology
- **Realization**: Determining the most specific classes for each individual
- **OWL 2 DL compliance**: Verifying that your ontology conforms to the spec
- **Anything that needs deep schema-level reasoning**

### How they complement each other

In a complete Semantic Web system, you'd typically use **both**:

```
┌─────────────────────────────────────────────────────┐
│                    Application Layer                  │
├─────────────────────────────────────────────────────┤
│  HermiT (OWL DL)         │  EYE / pyeye (N3 rules)  │
│  ─────────────────       │  ──────────────────      │
│  • Classify ontology       │  • Apply business rules  │
│  • Check consistency       │  • Integrate data        │
│  • Compute subsumption     │  • Agent reasoning       │
│  • Validate schema         │  • Derive new facts      │
├─────────────────────────────────────────────────────┤
│              Shared RDF Knowledge Graph               │
│  (Triples + Named Graphs + OWL Axioms + N3 Rules)    │
└─────────────────────────────────────────────────────┘
```

**Workflow:**

1. **Design phase**: Use HermiT to develop and validate your ontology. Ensure class hierarchies are consistent, properties have correct domains/ranges, and there are no contradictions.

2. **Runtime phase**: Use EYE / pyeye to apply custom rules over the data that conforms to your ontology. Derive new facts, make decisions, trigger actions.

3. **Feedback loop**: If EYE derives facts that violate your ontology constraints, HermiT will catch the inconsistency. Fix the rules or the data, then repeat.

### Example: Combined workflow

```python
# Step 1: Validate ontology with HermiT (external tool)
# hermit --check-consistency ontology.owl  ← passes

# Step 2: Apply business rules with pyeye
from pyeye import execute

result = execute(
    data_paths=["ontology-data.ttl", "sensor-readings.ttl"],
    rule_strings=[
        # Custom rules that go beyond OWL expressivity
        """
        @prefix : <http://smart-building.org/> .
        @prefix e: <http://eulersharp.sourceforge.net/2003/03swap/log-rules#> .
        
        # Rule: if room temperature > 30 AND room is occupied, turn on AC
        { ?Room :temperature ?T . ?T e:greaterThan "30" .
          ?Room :occupied true }
            => { ?Room :acOn true } .
        """,
    ],
    entail=True,  # RDFS entailment bridges ontology and data
)
```

### Can pyeye replace HermiT?

**No.** pyeye (and EYE) cannot perform OWL DL classification, compute subsumption hierarchies, or check ontology consistency in the DL sense. These require description logic algorithms that are fundamentally different from rule chaining.

### Can HermiT replace pyeye?

**No.** HermiT cannot execute custom business rules, integrate data from heterogeneous sources using mapping rules, or support agent-to-agent rule exchange. These require the flexibility of N3 logic that goes far beyond OWL's decidable fragment.

### Bottom line

| You need... | Use... |
| :--- | :--- |
| Custom if-then rules | **EYE / pyeye** |
| Ontology classification | **HermiT** |
| Data integration with rules | **EYE / pyeye** |
| Consistency checking | **HermiT** |
| Agent communication | **EYE / pyeye** |
| Schema validation | **HermiT** |
| Both | **Both** — they complement each other |

---

## Development

### How do I run the tests?

```bash
cd /path/to/pyeye
source .venv/bin/activate
python -m pytest tests/ -v
```

312 tests, all passing.

### How do I add a new builtin?

1. Add the function to `pyeye/builtins.py`:
   ```python
   def my_builtin(args, engine):
       if _unground(args):
           return None  # skip if arguments aren't ready
       # ... compute result ...
       return Literal("result")
   ```

2. Register it in `BUILTIN_REGISTRY` at the bottom of the file:
   ```python
   NS_MY + "myFunc": my_builtin,
   ```

3. Add unit tests to `tests/test_builtins_extended.py`.

4. Document it in `docs/builtins.md`.
