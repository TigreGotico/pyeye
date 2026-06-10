"""
30 — Belief Revision / Multi-Source Facts
===========================================
Integrate facts from multiple sources with confidence scores. When sources
report conflicting values, select the highest-confidence reading as the
:effectiveReading.

Scenario: three temperature sensors report different readings. We derive
which sensor's reading wins (highest :confidence), and flag disagreement.

Concepts:
  - log:collectAllIn to gather all confidence scores
  - math:max to find the highest confidence
  - Negation to exclude lower-confidence readings from :effectiveReading
  - math:notEqualTo / math:lessThan to compare values

Note: math:max expects a list — we collect confidences, find the max,
then match back to the sensor with that confidence.
"""

from pyeye import execute

# ---------------------------------------------------------------------------
# Sensor readings with confidence scores (0–100)
# ---------------------------------------------------------------------------
data = """
@prefix sensor: <http://example.org/sensor#> .
@prefix room:   <http://example.org/room#> .

# Room A: three sensors disagree
sensor:s1 sensor:room room:A ; sensor:temperature 22 ; sensor:confidence 80.0 .
sensor:s2 sensor:room room:A ; sensor:temperature 24 ; sensor:confidence 95.0 .
sensor:s3 sensor:room room:A ; sensor:temperature 21 ; sensor:confidence 60.0 .

# Room B: two sensors, one clearly dominant
sensor:s4 sensor:room room:B ; sensor:temperature 18 ; sensor:confidence 70.0 .
sensor:s5 sensor:room room:B ; sensor:temperature 19 ; sensor:confidence 40.0 .

# Room C: single sensor (no conflict)
sensor:s6 sensor:room room:C ; sensor:temperature 25 ; sensor:confidence 90.0 .
"""

rules = """
@prefix sensor: <http://example.org/sensor#> .
@prefix room:   <http://example.org/room#> .
@prefix log:    <http://www.w3.org/2000/10/swap/log#> .
@prefix math:   <http://www.w3.org/2000/10/swap/math#> .
@prefix list:   <http://www.w3.org/2000/10/swap/list#> .

# Collect all confidence scores for each room, find the maximum
{
    ?S sensor:room ?Room ; sensor:confidence ?AnyConf .
    (?C { ?Sx sensor:room ?Room . ?Sx sensor:confidence ?C } ?Confs) log:collectAllIn ?Scope .
    ?Confs math:max ?MaxConf
}
    => { ?Room sensor:maxConfidence ?MaxConf } .

# The winning sensor: no other sensor in the same room has higher confidence
{
    ?S sensor:room ?Room .
    ?S sensor:confidence ?C .
    ?S sensor:temperature ?Temp .
    _:neg log:onNegativeSurface {
        ?S2 sensor:room ?Room .
        ?S2 sensor:confidence ?C2 .
        ?C2 math:greaterThan ?C
    }
}
    => { ?Room sensor:effectiveTemperature ?Temp } .

# Flag rooms where sensors disagree (more than one distinct temperature)
{
    ?S1 sensor:room ?Room ; sensor:temperature ?T1 .
    ?S2 sensor:room ?Room ; sensor:temperature ?T2 .
    ?T1 math:notEqualTo ?T2
}
    => { ?Room sensor:hasConflict true } .
"""

result = execute(data_strings=[data], rule_strings=[rules])

rooms_temp = {}
rooms_conflict = set()
rooms_maxconf = {}

def local(tok):
    return tok.strip("<>").split("#")[-1].split(":")[-1]

for line in result.triples.splitlines():
    line = line.strip().rstrip(" .")
    if "sensor:effectiveTemperature" in line:
        parts = line.split()
        room = local(parts[0])
        temp = parts[2]
        rooms_temp[room] = temp
    elif "sensor:hasConflict" in line:
        parts = line.split()
        rooms_conflict.add(local(parts[0]))
    elif "sensor:maxConfidence" in line:
        parts = line.split()
        room = local(parts[0])
        # extract numeric value from typed literal like "95.0"^^xsd:double
        raw = parts[2]
        num = raw.split('"')[1] if '"' in raw else raw
        rooms_maxconf[room] = num

def extract_num(raw):
    """Extract numeric string from typed literal or plain literal."""
    if '"' in raw:
        return raw.split('"')[1]
    return raw

print("=== Belief Revision: Multi-Source Temperature Readings ===\n")
print("Room | Effective Temp | Max Confidence | Conflict")
print("-----|----------------|----------------|----------")
for room in ["A", "B", "C"]:
    temp  = extract_num(rooms_temp.get(room, "?"))
    conf  = rooms_maxconf.get(room, "?")
    conflict = "YES" if room in rooms_conflict else "no"
    print(f"  {room}  |      {temp:>4}°C      |      {conf:>4}       | {conflict}")

print()
print("Expected:")
print("  Room A: temp=24 (sensor s2, confidence 95), conflict=YES")
print("  Room B: temp=18 (sensor s4, confidence 70), conflict=YES")
print("  Room C: temp=25 (sensor s6, confidence 90), conflict=no")
