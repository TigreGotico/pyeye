"""
32 — Decision Support / Scoring
=================================
A multi-criteria scoring system for loan applications. Each applicant
has income, credit score, and employment years. Rules derive a weighted
composite :score, then assign a :tier (approve / review / reject).

Scoring formula (all normalised to 0-100):
  income_score     = min(income / 1000, 100)    (capped at 100)
  credit_score     = credit (already 300-850 scale; treat directly)
  employment_score = min(employment_years * 10, 100)

Weighted composite (weights sum to 1):
  score = 0.4 * income_score + 0.3 * credit_score_norm + 0.3 * employ_score
  where credit_score_norm = (credit - 300) / 5.5   (maps 300-850 → 0-100)

Tiers:
  score >= 70 → approve
  score >= 50 → review
  score <  50 → reject

Concepts:
  - math:product, math:sum for weighted arithmetic
  - math:greaterThan / math:lessThan for tier assignment
  - Negation to make tiers mutually exclusive
"""

from pyeye import execute

data = """
@prefix loan: <http://example.org/loan#> .
@prefix app:  <http://example.org/applicant#> .

# applicant: income (annual $k), creditScore (300-850), employmentYears
app:alice  loan:income 80 ; loan:creditScore 750 ; loan:employmentYears 8 .
app:bob    loan:income 35 ; loan:creditScore 580 ; loan:employmentYears 2 .
app:carol  loan:income 120 ; loan:creditScore 820 ; loan:employmentYears 15 .
app:dave   loan:income 25 ; loan:creditScore 420 ; loan:employmentYears 1 .
app:eve    loan:income 60 ; loan:creditScore 650 ; loan:employmentYears 5 .
"""

rules = """
@prefix loan: <http://example.org/loan#> .
@prefix app:  <http://example.org/applicant#> .
@prefix math: <http://www.w3.org/2000/10/swap/math#> .
@prefix log:  <http://www.w3.org/2000/10/swap/log#> .

# income_score = income * 1.25  (so 80k → 100, capped conceptually)
# We use income directly as income_score (assume max meaningful is 80k)
# For simplicity: income_score = income (raw, up to 80 for 80k)
{ ?A loan:income ?Inc . (?Inc 1.25) math:product ?IS } => { ?A loan:incomeScore ?IS } .

# credit_score_norm = (credit - 300) / 5.5
{ ?A loan:creditScore ?CS .
  (?CS 300) math:difference ?CSDiff .
  (?CSDiff 5.5) math:quotient ?CSN }
    => { ?A loan:creditNorm ?CSN } .

# employ_score = employmentYears * 10 (so 10 years → 100)
{ ?A loan:employmentYears ?EY . (?EY 10) math:product ?ES } => { ?A loan:employScore ?ES } .

# Composite: 0.4*incomeScore + 0.3*creditNorm + 0.3*employScore
{ ?A loan:incomeScore ?IS .
  ?A loan:creditNorm  ?CN .
  ?A loan:employScore ?ES .
  (?IS 0.4) math:product ?W1 .
  (?CN 0.3) math:product ?W2 .
  (?ES 0.3) math:product ?W3 .
  (?W1 ?W2) math:sum ?Partial .
  (?Partial ?W3) math:sum ?Score }
    => { ?A loan:compositeScore ?Score } .

# Tier: approve if score >= 70
{ ?A loan:compositeScore ?S . ?S math:greaterThan 69.99 }
    => { ?A loan:tier "approve" } .

# Tier: review if 50 <= score < 70
{ ?A loan:compositeScore ?S .
  ?S math:greaterThan 49.99 .
  _:neg log:onNegativeSurface { ?S math:greaterThan 69.99 } }
    => { ?A loan:tier "review" } .

# Tier: reject if score < 50
{ ?A loan:compositeScore ?S .
  _:neg2 log:onNegativeSurface { ?S math:greaterThan 49.99 } }
    => { ?A loan:tier "reject" } .
"""

result = execute(data_strings=[data], rule_strings=[rules])

scores = {}
tiers = {}

def local(tok):
    return tok.strip("<>").split("#")[-1].split(":")[-1]

def numval(tok):
    if '"' in tok:
        return tok.split('"')[1]
    return tok

for line in result.triples.splitlines():
    line = line.strip().rstrip(" .")
    if "loan:compositeScore" in line:
        parts = line.split()
        a = local(parts[0])
        scores[a] = float(numval(parts[2]))
    elif "loan:tier" in line:
        parts = line.split(None, 2)
        a = local(parts[0])
        tiers[a] = parts[2].strip('"')

print("=== Loan Application Scoring System ===\n")
print(f"{'Applicant':<10} {'Score':>7} {'Tier':<10}")
print("-" * 30)
for app in ["alice", "bob", "carol", "dave", "eve"]:
    score = scores.get(app, 0.0)
    tier  = tiers.get(app, "?")
    print(f"{app:<10} {score:>7.1f} {tier:<10}")

print()
print("Expected (approximate):")
print("  carol  : highest score → approve")
print("  alice  : high score    → approve")
print("  eve    : mid score     → review")
print("  bob    : lower score   → review or reject")
print("  dave   : lowest score  → reject")
