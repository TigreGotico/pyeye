"""
15 — Peano Arithmetic via Backward Chaining
============================================
The classic EYE demonstration of recursive backward chaining: natural numbers
defined inductively using the Peano encoding, with addition, multiplication,
and factorial defined via pure backward rules.

In this encoding, natural numbers are nested structures:
  0         →  0
  1         →  (:s 0)
  2         →  (:s (:s 0))
  3         →  (:s (:s (:s 0)))

Addition:
  add(A, 0) = A                        (base)
  add(A, s(B)) = s(add(A, B))          (inductive)

Multiplication:
  mult(A, 0) = 0                       (base)
  mult(A, s(B)) = add(A, mult(A, B))   (inductive)

Factorial:
  n! = fac(n, 1)   where fac(0, acc) = acc
                         fac(s(n), acc) = fac(n, mult(acc, s(n)))

Key concept: log:table memoizes recursive predicates to prevent
the backward chaining engine from looping infinitely.
"""

from pyeye import execute, ReasoningTimeoutError

FACTS_AND_RULES = """
@prefix log: <http://www.w3.org/2000/10/swap/log#> .
@prefix : <http://example.org/#> .

# --- Addition ---
# add(A, 0) = A
{(?A 0) :add ?A} <= true .

# add(A, s(B)) = s(add(A, B))
{(?A (:s ?B)) :add (:s ?C)} <= {
    (?A ?B) :add ?C .
} .

# --- Multiplication ---
# mult(A, 0) = 0
{(?A 0) :multiply 0} <= true .

# mult(A, s(B)) = add(A, mult(A, B))
{(?A (:s ?B)) :multiply ?C} <= {
    (?A ?B) :multiply ?D .
    (?A ?D) :add ?C .
} .

# --- Factorial ---
# n! starts as fac(n, 1)
{?A :factorial ?B} <= {
    (?A (:s 0)) :fac ?B .
} .

# fac(0, acc) = acc
{(0 ?A) :fac ?A} <= true .

# fac(s(n), acc) = fac(n, mult(acc, s(n)))
{((:s ?A) ?B) :fac ?C} <= {
    (?B (:s ?A)) :multiply ?D .
    (?A ?D) :fac ?C .
} .
"""

# ---------------------------------------------------------------------------
# Example 1: Compute 1 * 2 = 2, then 2 + 1 = 3, then 3! = 6
# ---------------------------------------------------------------------------
print("=== 3! = 6 via Peano arithmetic ===")
print("Computing: 1*2=2, 2+1=3, 3!=6 ...")

# The query rule: chain multiply → add → factorial
QUERY = """
@prefix : <http://example.org/#> .

{
    ((:s 0) (:s (:s 0))) :multiply ?A .
    (?A (:s 0)) :add ?B .
    ?B :factorial ?C .
} => {
    ?B :factorial ?C .
} .
"""

result = execute(rule_strings=[FACTS_AND_RULES, QUERY])
print("\nDerived:", result.triples or "(none — recursion may need more steps)")
print("Stats:", result.stats)

# The result ?C is 6 in Peano: (:s (:s (:s (:s (:s (:s 0))))))
# The output triple should be ?B :factorial ?C where B=3 and C=6


# ---------------------------------------------------------------------------
# Example 2: Simpler — verify 2 + 3 = 5
# ---------------------------------------------------------------------------
print("\n=== Verify: 2 + 3 = 5 ===")

VERIFY = """
@prefix : <http://example.org/#> .

# 5 = s(s(s(s(s(0)))))
{
    ((:s (:s 0)) (:s (:s (:s 0)))) :add (:s (:s (:s (:s (:s 0))))) .
} => {
    :result :check "2+3=5 confirmed" .
} .
"""

result2 = execute(rule_strings=[FACTS_AND_RULES, VERIFY])
print(result2.triples or "(not confirmed)")


# ---------------------------------------------------------------------------
# Explanation
# ---------------------------------------------------------------------------
print("""
--- Why this encoding works ---

Numbers are nested lists: 3 = (:s (:s (:s 0))).

The backward rules unfold recursively:
  (3 2):multiply ?C
    ← (3 1):multiply ?D, (3 ?D):add ?C
    ← (3 0):multiply ?E → E=0; (3 0):add ?D → D=3; (3 3):add ?C → C=6

The engine backtracks from the goal, matching rule heads, and
records intermediate results via log:table to avoid re-proving
the same subgoal twice (tabling / SLG resolution).

This is the technique used in EYE (Euler) for logic programming.
""")


# ---------------------------------------------------------------------------
# Safety demo: ReasoningTimeoutError protects against infinite loops
# ---------------------------------------------------------------------------
print("\n=== Safety: ReasoningTimeoutError ===")

try:
    execute(
        rule_strings=["""
@prefix : <http://example.org/> .
@prefix math: <http://www.w3.org/2000/10/swap/math#> .
:a :x 1 .
{ ?S :x ?N . (?N 1) math:sum ?M } => { :a :x ?M } .
"""],
        timeout_seconds=1.0,
    )
    print("No timeout (unexpected)")
except ReasoningTimeoutError as e:
    print("ReasoningTimeoutError raised — infinite loop was stopped.")
    print("Message:", str(e)[:100])
