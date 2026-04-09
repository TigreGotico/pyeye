"""
03 — Math Builtins
==================
Use the math: namespace to do arithmetic inside rules.

Concepts:
  - Builtin predicates: subject is input, object is output/comparison
  - math:greaterThan, math:lessThan, math:equalTo  — comparisons (filter)
  - (?A ?B) math:sum ?C                            — C = A + B
  - (?A ?B) math:product ?C                        — C = A * B
  - (?A ?B) math:quotient ?C                       — C = A / B
  - (?A ?B) math:difference ?C                     — C = A - B
  - math:sqrt, math:exponentiation                 — advanced

Binary math builtins take a 2-element list as subject:
    { (?Price 0.8) math:product ?Final }   means Final = Price * 0.8

Comparison builtins take the value directly:
    { ?Price math:greaterThan 100 }        means Price > 100  (filter, no output)
"""

from pyeye import execute

# Example 1: Price discount calculation
print("=== Price Discount ===")

data = """
@prefix shop: <http://example.org/shop#> .

shop:widgetA shop:price 120 .
shop:widgetB shop:price 45 .
shop:widgetC shop:price 80 .
"""

rules = """
@prefix shop: <http://example.org/shop#> .
@prefix math: <http://www.w3.org/2000/10/swap/math#> .

# Items over 100 get 20% off: finalPrice = price * 0.8
{
    ?Item shop:price ?P .
    ?P math:greaterThan 100 .
    (?P 0.8) math:product ?Final
}
    => { ?Item shop:salePrice ?Final } .

# Items under or equal to 100 are full price
{
    ?Item shop:price ?P .
    ?P math:lessThan 101
}
    => { ?Item shop:salePrice ?P } .
"""

result = execute(data_strings=[data], rule_strings=[rules])
print(result.triples)


# Example 2: BMI calculation
print("\n=== BMI Calculation ===")

data2 = """
@prefix health: <http://example.org/health#> .

health:alice health:weightKg 68 ; health:heightM 1.7 .
health:bob   health:weightKg 95 ; health:heightM 1.8 .
"""

rules2 = """
@prefix health: <http://example.org/health#> .
@prefix math:   <http://www.w3.org/2000/10/swap/math#> .

# BMI = weight / (height^2)
{
    ?P health:weightKg ?W .
    ?P health:heightM ?H .
    (?H ?H) math:product ?H2 .
    (?W ?H2) math:quotient ?BMI
}
    => { ?P health:bmi ?BMI } .

# BMI >= 25 → overweight
{
    ?P health:bmi ?BMI .
    ?BMI math:greaterThan 24.9
}
    => { ?P health:category "overweight" } .

# BMI < 25 → normal (simplified)
{
    ?P health:bmi ?BMI .
    ?BMI math:lessThan 25
}
    => { ?P health:category "normal" } .
"""

result2 = execute(data_strings=[data2], rule_strings=[rules2])
print(result2.triples)


# Example 3: Temperature conversion (Celsius → Fahrenheit)
print("\n=== Temperature Conversion ===")

data3 = """
@prefix temp: <http://example.org/temp#> .

temp:london  temp:celsius 15 .
temp:phoenix temp:celsius 40 .
temp:oslo    temp:celsius -5 .
"""

rules3 = """
@prefix temp: <http://example.org/temp#> .
@prefix math: <http://www.w3.org/2000/10/swap/math#> .

# F = C * 9/5 + 32  →  F = (C * 1.8) + 32
{
    ?City temp:celsius ?C .
    (?C 1.8) math:product ?Scaled .
    (?Scaled 32) math:sum ?F
}
    => { ?City temp:fahrenheit ?F } .
"""

result3 = execute(data_strings=[data3], rule_strings=[rules3])
print(result3.triples)
