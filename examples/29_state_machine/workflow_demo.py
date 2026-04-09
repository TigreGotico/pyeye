"""
29 — State Machine / Workflow
===============================
Model an order-processing workflow as states and transitions.
Use forward-chaining to derive allowed next states and flag invalid
transition attempts.

States: pending → confirmed → shipped → delivered → archived
Invalid: e.g., jumping from pending directly to shipped.

Concepts:
  - State/transition facts as data
  - Forward rules deriving :nextAllowed states
  - Transitive reachability for multi-hop paths
  - Negation to flag invalid transitions
"""

from pyeye import execute

# ---------------------------------------------------------------------------
# Workflow definition + order states + attempted transitions
# ---------------------------------------------------------------------------
data = """
@prefix wf:  <http://example.org/workflow#> .
@prefix ord: <http://example.org/order#> .

# --- Allowed transitions (the state machine topology) ---
wf:pending    wf:canTransitionTo wf:confirmed .
wf:confirmed  wf:canTransitionTo wf:shipped .
wf:shipped    wf:canTransitionTo wf:delivered .
wf:delivered  wf:canTransitionTo wf:archived .

# --- Orders and their current states ---
ord:order1 wf:currentState wf:pending .
ord:order2 wf:currentState wf:confirmed .
ord:order3 wf:currentState wf:shipped .
ord:order4 wf:currentState wf:delivered .

# --- Attempted transitions (may or may not be valid) ---
ord:order1 wf:attemptTransition wf:confirmed .    # valid: pending→confirmed
ord:order2 wf:attemptTransition wf:shipped .      # valid: confirmed→shipped
ord:order3 wf:attemptTransition wf:delivered .    # valid: shipped→delivered
ord:order4 wf:attemptTransition wf:pending .      # INVALID: can't go back
ord:order1 wf:attemptTransition wf:shipped .      # INVALID: skip confirmed
"""

rules = """
@prefix wf:  <http://example.org/workflow#> .
@prefix log: <http://www.w3.org/2000/10/swap/log#> .

# Derive which states are immediately reachable from current state
{
    ?Order wf:currentState ?State .
    ?State wf:canTransitionTo ?Next
}
    => { ?Order wf:allowedNext ?Next } .

# Validate an attempted transition: allowed if it is in allowedNext
{
    ?Order wf:attemptTransition ?Target .
    ?Order wf:allowedNext ?Target
}
    => { ?Order wf:transitionValid ?Target } .

# Flag invalid transitions: attempted but not in allowedNext
{
    ?Order wf:attemptTransition ?Target .
    _:neg log:onNegativeSurface { ?Order wf:allowedNext ?Target }
}
    => { ?Order wf:transitionInvalid ?Target } .

# Multi-hop reachability (what states can an order eventually reach?)
{ ?S wf:canTransitionTo ?T } => { ?S wf:reaches ?T } .
{ ?S wf:reaches ?M . ?M wf:canTransitionTo ?T } => { ?S wf:reaches ?T } .

# Terminal state: no outgoing transitions defined
{
    ?State wf:canTransitionTo ?Any .
    _:neg2 log:onNegativeSurface { ?Any wf:canTransitionTo ?Further }
}
    => { ?Any a wf:TerminalState } .
"""

result = execute(data_strings=[data], rule_strings=[rules])

valid_transitions = {}
invalid_transitions = {}
allowed_next = {}
terminal = []

def local(iri_token):
    """Extract local name from either 'prefix:local' or '<...#local>' or '<...#local>'."""
    s = iri_token.strip("<>")
    return s.split("#")[-1].split(":")[-1]

for line in result.triples.splitlines():
    line = line.strip().rstrip(" .")
    if "wf:transitionValid" in line:
        parts = line.split()
        o = local(parts[0])
        t = local(parts[2])
        valid_transitions.setdefault(o, []).append(t)
    elif "wf:transitionInvalid" in line:
        parts = line.split()
        o = local(parts[0])
        t = local(parts[2])
        invalid_transitions.setdefault(o, []).append(t)
    elif "wf:allowedNext" in line:
        parts = line.split()
        o = local(parts[0])
        n = local(parts[2])
        allowed_next.setdefault(o, []).append(n)
    elif "wf:TerminalState" in line and " a " in line:
        terminal.append(local(line.split()[0]))

print("=== Order Workflow State Machine ===\n")

orders = ["order1", "order2", "order3", "order4"]
for o in orders:
    nxt = sorted(allowed_next.get(o, []))
    good = sorted(valid_transitions.get(o, []))
    bad  = sorted(invalid_transitions.get(o, []))
    print(f"{o}:")
    print(f"  allowed next states : {nxt}")
    if good:
        print(f"  valid transitions   : {good}")
    if bad:
        print(f"  INVALID transitions : {bad}")

print(f"\nTerminal states: {sorted(set(terminal))}")
print("(Expected: archived — no outgoing transitions)")
