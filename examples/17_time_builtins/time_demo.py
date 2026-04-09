"""
17 — Time Builtins
==================
The time: namespace provides temporal reasoning: current timestamp,
and extraction of individual date/time components from ISO 8601 strings.

Builtins:
  - _:x time:now ?T           — current timestamp (ISO 8601)
  - ?DT time:year   ?N        — extract year integer
  - ?DT time:month  ?N        — extract month integer (1-12)
  - ?DT time:day    ?N        — extract day integer (1-31)
  - ?DT time:hour   ?N        — extract hour (0-23)
  - ?DT time:minute ?N        — extract minute (0-59)
  - ?DT time:second ?N        — extract second (0-59)
  - ?DT time:timeZone ?TZ     — extract timezone string

Use cases:
  - Timestamp events at rule firing time
  - Filter data by year/month
  - Classify records by time period
"""

from pyeye import execute

# Example 1: Timestamp events when they are processed
print("=== Event Timestamping ===")

data = """
@prefix ev: <http://example.org/event#> .

ev:login1  ev:user ev:alice ; ev:action "login" .
ev:login2  ev:user ev:bob   ; ev:action "login" .
ev:logout1 ev:user ev:alice ; ev:action "logout" .
"""

rules = """
@prefix ev:   <http://example.org/event#> .
@prefix time: <http://www.w3.org/2000/10/swap/time#> .

# Record processing timestamp for every event
{
    ?E ev:action ?A .
    _:t time:now ?Now
}
    => { ?E ev:processedAt ?Now } .
"""

result = execute(data_strings=[data], rule_strings=[rules])
print(result.triples)


# Example 2: Extract year/month from stored timestamps
print("\n=== Date Component Extraction ===")

data2 = """
@prefix rec: <http://example.org/record#> .

rec:sale1 rec:timestamp "2024-03-15T14:30:00" ; rec:amount 250 .
rec:sale2 rec:timestamp "2024-07-22T09:15:00" ; rec:amount 180 .
rec:sale3 rec:timestamp "2025-01-08T16:45:00" ; rec:amount 320 .
"""

rules2 = """
@prefix rec:  <http://example.org/record#> .
@prefix time: <http://www.w3.org/2000/10/swap/time#> .

# Extract year and month from each record's timestamp
{
    ?R rec:timestamp ?TS .
    ?TS time:year  ?Y .
    ?TS time:month ?M
}
    => { ?R rec:year ?Y ; rec:month ?M } .
"""

result2 = execute(data_strings=[data2], rule_strings=[rules2])
print(result2.triples)


# Example 3: Classify records by year
print("\n=== Year-Based Classification ===")

rules3 = """
@prefix rec:  <http://example.org/record#> .
@prefix time: <http://www.w3.org/2000/10/swap/time#> .
@prefix math: <http://www.w3.org/2000/10/swap/math#> .

# Extract year
{
    ?R rec:timestamp ?TS .
    ?TS time:year ?Y
}
    => { ?R rec:year ?Y } .

# Mark 2024 records as historical
{
    ?R rec:year ?Y .
    ?Y math:equalTo 2024
}
    => { ?R rec:period "2024-archive" } .

# Mark 2025+ records as current
{
    ?R rec:year ?Y .
    ?Y math:greaterThan 2024
}
    => { ?R rec:period "current" } .
"""

result3 = execute(data_strings=[data2], rule_strings=[rules3])
print(result3.triples)
