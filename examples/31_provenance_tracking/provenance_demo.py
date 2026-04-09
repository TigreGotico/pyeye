"""
31 — Provenance Tracking
=========================
Track the origin of facts across multiple data sources. Rules propagate
source metadata so that derived facts know which input source they came from.

Scenario: patient medical records from two hospitals and a lab system.
Rules derive diagnoses; each derived fact is tagged with the originating
source via a :derivedFrom predicate.

Concepts:
  - Multiple data_strings, each tagged with its source
  - Forward rules that join data with source metadata
  - Derived provenance triples: ?Derived :derivedFrom ?Source
  - Source conflict detection: same entity, different values from different sources
"""

from pyeye import execute

# Source 1: Hospital A records
hospital_a = """
@prefix rec:  <http://example.org/record#> .
@prefix src:  <http://example.org/source#> .
@prefix pat:  <http://example.org/patient#> .

# All triples from Hospital A are tagged with source:hospitalA
src:hospitalA a src:DataSource ; src:name "Hospital A" .

pat:p001 rec:bloodPressure 145 ; rec:source src:hospitalA .
pat:p002 rec:bloodPressure 120 ; rec:source src:hospitalA .
pat:p003 rec:bloodPressure 135 ; rec:source src:hospitalA .
"""

# Source 2: Hospital B records (p001 also appears here — potential conflict)
hospital_b = """
@prefix rec:  <http://example.org/record#> .
@prefix src:  <http://example.org/source#> .
@prefix pat:  <http://example.org/patient#> .

src:hospitalB a src:DataSource ; src:name "Hospital B" .

pat:p001 rec:bloodPressure 150 ; rec:source src:hospitalB .   # different reading!
pat:p004 rec:bloodPressure 118 ; rec:source src:hospitalB .
"""

# Source 3: Lab system
lab = """
@prefix rec:  <http://example.org/record#> .
@prefix src:  <http://example.org/source#> .
@prefix pat:  <http://example.org/patient#> .

src:lab a src:DataSource ; src:name "Lab System" .

pat:p001 rec:cholesterol 240 ; rec:source src:lab .
pat:p002 rec:cholesterol 180 ; rec:source src:lab .
pat:p003 rec:cholesterol 220 ; rec:source src:lab .
"""

# Rules
rules = """
@prefix rec:  <http://example.org/record#> .
@prefix src:  <http://example.org/source#> .
@prefix pat:  <http://example.org/patient#> .
@prefix math: <http://www.w3.org/2000/10/swap/math#> .
@prefix log:  <http://www.w3.org/2000/10/swap/log#> .

# Hypertension: blood pressure > 140, tag with source
{
    ?P rec:bloodPressure ?BP ; rec:source ?Src .
    ?BP math:greaterThan 140
}
    => { ?P rec:diagnosis "hypertension" ; rec:derivedFrom ?Src } .

# High cholesterol: cholesterol > 200, tag with source
{
    ?P rec:cholesterol ?C ; rec:source ?Src .
    ?C math:greaterThan 200
}
    => { ?P rec:diagnosis "high_cholesterol" ; rec:derivedFrom ?Src } .

# Cardiovascular risk: both hypertension AND high cholesterol
{
    ?P rec:diagnosis "hypertension" .
    ?P rec:diagnosis "high_cholesterol"
}
    => { ?P rec:riskLevel "high_cardiovascular_risk" } .

# Source conflict: same patient, same measurement, different sources
{
    ?P rec:bloodPressure ?V1 ; rec:source ?S1 .
    ?P rec:bloodPressure ?V2 ; rec:source ?S2 .
    ?S1 log:notEqualTo ?S2 .
    ?V1 math:notEqualTo ?V2
}
    => { ?P rec:conflict "bloodPressure" } .
"""

result = execute(
    data_strings=[hospital_a, hospital_b, lab],
    rule_strings=[rules],
)

# Parse results
diagnoses = {}
derived_from = {}
conflicts = set()
risk = set()

def local(tok):
    return tok.strip("<>").split("#")[-1].split(":")[-1]

for line in result.triples.splitlines():
    line = line.strip().rstrip(" .")
    if "rec:diagnosis" in line:
        parts = line.split(None, 2)
        p = local(parts[0])
        d = parts[2].strip('"')
        diagnoses.setdefault(p, set()).add(d)
    elif "rec:derivedFrom" in line:
        parts = line.split()
        p = local(parts[0])
        s = local(parts[2])
        derived_from.setdefault(p, set()).add(s)
    elif "rec:conflict" in line:
        parts = line.split()
        conflicts.add(local(parts[0]))
    elif "rec:riskLevel" in line:
        parts = line.split()
        risk.add(local(parts[0]))

print("=== Provenance Tracking in Medical Records ===\n")

patients = ["p001", "p002", "p003", "p004"]
for p in patients:
    d = sorted(diagnoses.get(p, []))
    s = sorted(derived_from.get(p, []))
    r = "HIGH RISK" if p in risk else ""
    c = "CONFLICT" if p in conflicts else ""
    print(f"{p}: diagnoses={d}  sources={s}  {r} {c}".rstrip())

print()
print("Expected:")
print("  p001: hypertension (hospitalA BP=145, hospitalB BP=150, CONFLICT) + high_cholesterol (lab) → HIGH RISK")
print("  p002: BP=120, cholesterol=180 → no diagnoses (both within limits)")
print("  p003: BP=135 (below 140 threshold), high_cholesterol (lab chol=220) → not HIGH RISK (missing hypertension)")
print("  p004: BP=118 → no diagnosis")
