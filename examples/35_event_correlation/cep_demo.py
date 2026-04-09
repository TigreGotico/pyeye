"""
35 — Event Correlation / Complex Event Processing (CEP)
=========================================================
Detect patterns across multiple events:
  - 3+ login failures within a short time window → :bruteForce alert
  - A login success shortly after multiple failures → :bruteForceSuccess alert
  - High-value transaction after account unlock → :suspiciousTransaction alert

Events have: :user, :type, :timestamp (integer seconds since epoch offset).
Time windows are checked using math comparisons on timestamp differences.

Concepts:
  - Forward chaining over event triples
  - math:greaterThan / math:lessThan for time-window checks
  - math:difference for computing elapsed time
  - log:collectAllIn to count failures in a window
  - list:length for counting correlated events
  - Negation for "no intervening success" check
"""

from pyeye import execute

# ---------------------------------------------------------------------------
# Event log — integer timestamps (seconds, arbitrary epoch)
# ---------------------------------------------------------------------------
data = """
@prefix ev:   <http://example.org/event#> .
@prefix user: <http://example.org/user#> .

# User alice: 3 login failures followed by a success (brute-force pattern)
ev:e01 ev:user user:alice ; ev:type ev:loginFail    ; ev:timestamp 100 .
ev:e02 ev:user user:alice ; ev:type ev:loginFail    ; ev:timestamp 115 .
ev:e03 ev:user user:alice ; ev:type ev:loginFail    ; ev:timestamp 130 .
ev:e04 ev:user user:alice ; ev:type ev:loginSuccess ; ev:timestamp 145 .

# User bob: 2 failures then nothing (not enough for brute-force threshold)
ev:e05 ev:user user:bob   ; ev:type ev:loginFail    ; ev:timestamp 200 .
ev:e06 ev:user user:bob   ; ev:type ev:loginFail    ; ev:timestamp 210 .

# User carol: failures spread over a long time window (not correlated)
ev:e07 ev:user user:carol ; ev:type ev:loginFail    ; ev:timestamp 300 .
ev:e08 ev:user user:carol ; ev:type ev:loginFail    ; ev:timestamp 900 .  # 10 min gap
ev:e09 ev:user user:carol ; ev:type ev:loginFail    ; ev:timestamp 920 .

# User dave: success after 2 failures (short window → suspicious)
ev:e10 ev:user user:dave  ; ev:type ev:loginFail    ; ev:timestamp 400 .
ev:e11 ev:user user:dave  ; ev:type ev:loginFail    ; ev:timestamp 410 .
ev:e12 ev:user user:dave  ; ev:type ev:loginFail    ; ev:timestamp 420 .
ev:e13 ev:user user:dave  ; ev:type ev:loginSuccess ; ev:timestamp 430 .
ev:e14 ev:user user:dave  ; ev:type ev:highValueTx  ; ev:timestamp 440 .
"""

rules = """
@prefix ev:   <http://example.org/event#> .
@prefix user: <http://example.org/user#> .
@prefix math: <http://www.w3.org/2000/10/swap/math#> .
@prefix log:  <http://www.w3.org/2000/10/swap/log#> .
@prefix list: <http://www.w3.org/2000/10/swap/list#> .

# Mark a failure event as part of a burst if another failure occurs
# within 120 seconds BEFORE it (i.e., an anchor earlier event exists)
{
    ?E1 ev:user ?U ; ev:type ev:loginFail ; ev:timestamp ?T1 .
    ?E2 ev:user ?U ; ev:type ev:loginFail ; ev:timestamp ?T2 .
    ?E1 log:notEqualTo ?E2 .
    ?T2 math:greaterThan ?T1 .
    (?T2 ?T1) math:difference ?Gap .
    ?Gap math:lessThan 121
}
    => { ?E2 ev:inBurstWith ?E1 } .

# A failure is in a burst if it has a partner (or is a partner itself)
{ ?E ev:inBurstWith ?F } => { ?E ev:inBurst true } .
{ ?E ev:inBurstWith ?F } => { ?F ev:inBurst true } .

# Brute-force: user has 3+ failures all in burst (count distinct burst failures per user)
{
    ?AnyE ev:user ?U ; ev:type ev:loginFail ; ev:inBurst true .
    (1 { ?E ev:user ?U ; ev:type ev:loginFail ; ev:inBurst true } ?BurstEvents) log:collectAllIn ?U .
    ?BurstEvents list:length ?N .
    ?N math:greaterThan 2
}
    => { ?U ev:alert "brute_force_detected" } .

# Brute-force success: login success after a failure within 120s
{
    ?U ev:alert "brute_force_detected" .
    ?EF ev:user ?U ; ev:type ev:loginFail    ; ev:timestamp ?TF .
    ?ES ev:user ?U ; ev:type ev:loginSuccess ; ev:timestamp ?TS .
    ?TS math:greaterThan ?TF .
    (?TS ?TF) math:difference ?Gap .
    ?Gap math:lessThan 121
}
    => { ?U ev:alert "brute_force_with_success" } .

# Suspicious transaction: high-value tx within 60s of a brute-force success
{
    ?U ev:alert "brute_force_with_success" .
    ?ES ev:user ?U ; ev:type ev:loginSuccess ; ev:timestamp ?TS .
    ?ET ev:user ?U ; ev:type ev:highValueTx  ; ev:timestamp ?TX .
    ?TX math:greaterThan ?TS .
    (?TX ?TS) math:difference ?Gap .
    ?Gap math:lessThan 61
}
    => { ?U ev:alert "suspicious_transaction_after_compromise" } .
"""

result = execute(data_strings=[data], rule_strings=[rules])

alerts = {}
def local(tok):
    return tok.strip("<>").split("#")[-1].split(":")[-1]
def strval(tok):
    return tok.split('"')[1] if '"' in tok else tok

for line in result.triples.splitlines():
    line = line.strip().rstrip(" .")
    if "ev:alert" in line:
        parts = line.split(None, 2)
        u = local(parts[0])
        a = strval(parts[2])
        alerts.setdefault(u, []).append(a)

print("=== Complex Event Processing: Login Security Alerts ===\n")
users = ["alice", "bob", "carol", "dave"]
for u in users:
    a = sorted(set(alerts.get(u, [])))
    status = ", ".join(a) if a else "no alerts"
    print(f"{u:<8}: {status}")

print()
print("Expected:")
print("  alice: brute_force_detected, brute_force_with_success")
print("         (3 failures in 30s window, then success at t=145)")
print("  bob  : no alerts (only 2 failures, below threshold of 3)")
print("  carol: no alerts (failures spread >10 min apart, outside 120s window)")
print("  dave : brute_force_detected, brute_force_with_success,")
print("         suspicious_transaction_after_compromise")
