"""
19 — Math Statistics
====================
Combine log:collectAllIn with math: aggregation builtins to compute
summary statistics over sets of values derived from the knowledge graph.

Builtins used:
  - math:sum     — total
  - math:max     — maximum
  - math:min     — minimum
  - math:quotient — division (for average)
  - list:length  — count

Pattern:
    1. Use log:collectAllIn to gather values matching a pattern into a list
    2. Apply math: builtins to that list
    3. Derive summary triples

This is the RDF/N3 equivalent of SQL GROUP BY + aggregate functions.
"""

from pyeye import execute

# Example 1: Per-department salary statistics
print("=== Salary Statistics per Department ===")

data = """
@prefix hr:  <http://example.org/hr#> .

hr:alice hr:dept hr:engineering ; hr:salary 95000 .
hr:bob   hr:dept hr:engineering ; hr:salary 88000 .
hr:carol hr:dept hr:engineering ; hr:salary 102000 .
hr:dave  hr:dept hr:marketing   ; hr:salary 72000 .
hr:eve   hr:dept hr:marketing   ; hr:salary 68000 .
"""

rules = """
@prefix hr:   <http://example.org/hr#> .
@prefix log:  <http://www.w3.org/2000/10/swap/log#> .
@prefix math: <http://www.w3.org/2000/10/swap/math#> .
@prefix list: <http://www.w3.org/2000/10/swap/list#> .

{
    ?Dept a hr:Dept .
} <= {
    ?P hr:dept ?Dept .
} .

{
    ?Dept a hr:Dept .
    (?V { ?P hr:dept ?Dept . ?P hr:salary ?V } ?Salaries) log:collectAllIn ?Dept .
    ?Salaries math:sum ?Total .
    ?Salaries math:max ?Hi .
    ?Salaries math:min ?Lo .
    ?Salaries list:length ?N .
    (?Total ?N) math:quotient ?Avg
}
    => {
        ?Dept hr:headcount ?N .
        ?Dept hr:totalSalary ?Total .
        ?Dept hr:maxSalary ?Hi .
        ?Dept hr:minSalary ?Lo .
        ?Dept hr:avgSalary ?Avg .
    } .
"""

result = execute(data_strings=[data], rule_strings=[rules])
print(result.triples)


# Example 2: Grade distribution
print("\n=== Grade Distribution ===")

data2 = """
@prefix edu: <http://example.org/edu#> .

edu:class1 a edu:Class .
edu:s1 edu:class edu:class1 ; edu:grade 85 .
edu:s2 edu:class edu:class1 ; edu:grade 92 .
edu:s3 edu:class edu:class1 ; edu:grade 78 .
edu:s4 edu:class edu:class1 ; edu:grade 95 .
edu:s5 edu:class edu:class1 ; edu:grade 61 .
"""

rules2 = """
@prefix edu:  <http://example.org/edu#> .
@prefix log:  <http://www.w3.org/2000/10/swap/log#> .
@prefix math: <http://www.w3.org/2000/10/swap/math#> .
@prefix list: <http://www.w3.org/2000/10/swap/list#> .

# Compute class stats
{
    ?C a edu:Class .
    (?G { ?S edu:class ?C . ?S edu:grade ?G } ?Grades) log:collectAllIn ?C .
    ?Grades math:max ?Hi .
    ?Grades math:min ?Lo .
    ?Grades math:sum ?Sum .
    ?Grades list:length ?N .
    (?Sum ?N) math:quotient ?Avg
}
    => {
        ?C edu:highestGrade ?Hi .
        ?C edu:lowestGrade  ?Lo .
        ?C edu:avgGrade     ?Avg .
        ?C edu:studentCount ?N .
    } .

# Pass rate: count students >= 70
{
    ?C a edu:Class .
    (1 { ?S edu:class ?C . ?S edu:grade ?G . ?G math:greaterThan 69 } ?Passes) log:collectAllIn ?C .
    ?Passes math:sum ?PassCount
}
    => { ?C edu:passCount ?PassCount } .
"""

result2 = execute(data_strings=[data2], rule_strings=[rules2])
print(result2.triples)


# Example 3: Threshold alerting
print("\n=== Threshold Alerts ===")

data3 = """
@prefix sensor: <http://example.org/sensor#> .

sensor:room1 a sensor:Room .
sensor:r1m1 sensor:room sensor:room1 ; sensor:temp 22 .
sensor:r1m2 sensor:room sensor:room1 ; sensor:temp 24 .
sensor:r1m3 sensor:room sensor:room1 ; sensor:temp 35 .
sensor:r1m4 sensor:room sensor:room1 ; sensor:temp 21 .
"""

rules3 = """
@prefix sensor: <http://example.org/sensor#> .
@prefix log:    <http://www.w3.org/2000/10/swap/log#> .
@prefix math:   <http://www.w3.org/2000/10/swap/math#> .

# Max temperature per room
{
    ?Room a sensor:Room .
    (?T { ?M sensor:room ?Room . ?M sensor:temp ?T } ?Temps) log:collectAllIn ?Room .
    ?Temps math:max ?MaxT
}
    => { ?Room sensor:peakTemp ?MaxT } .

# Alert if peak > 30
{
    ?Room sensor:peakTemp ?T .
    ?T math:greaterThan 30
}
    => { ?Room sensor:alert "OVERHEATING" } .
"""

result3 = execute(data_strings=[data3], rule_strings=[rules3])
print(result3.triples)
