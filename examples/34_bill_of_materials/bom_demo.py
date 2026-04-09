"""
34 — Recursive Data Structures: Bill of Materials
===================================================
A Bill of Materials (BOM) tree: products are assembled from components,
which may themselves be assemblies. Compute total weight and total cost
by recursively summing component values.

Structure:
  product:laptop = {body, screen_assembly, keyboard}
  screen_assembly = {screen_panel, backlight}

Concepts:
  - Transitive part-of relationships via forward-chaining rules
  - log:collectAllIn to sum direct component weights/costs
  - Recursive derivation: total cost of assembly = sum of component totals
  - Leaf detection: a component with no sub-parts uses its own unit values

Note: This example computes direct-assembly totals (one level up).
Full recursive explosion uses the transitive :hasPart rule.
"""

from pyeye import execute

data = """
@prefix bom:  <http://example.org/bom#> .
@prefix part: <http://example.org/part#> .

# Leaf components (no sub-parts)
part:screen_panel  bom:unitWeight 400 ; bom:unitCost 180 .
part:backlight     bom:unitWeight  50 ; bom:unitCost  30 .
part:body          bom:unitWeight 600 ; bom:unitCost 120 .
part:keyboard      bom:unitWeight 200 ; bom:unitCost  45 .
part:battery       bom:unitWeight 300 ; bom:unitCost  80 .
part:cpu           bom:unitWeight  30 ; bom:unitCost 350 .
part:ram           bom:unitWeight  20 ; bom:unitCost  60 .

# Sub-assembly: screen_assembly is made of screen_panel + backlight
part:screen_assembly
    bom:directPart part:screen_panel ;
    bom:directPart part:backlight .

# Sub-assembly: mainboard is made of cpu + ram
part:mainboard
    bom:directPart part:cpu ;
    bom:directPart part:ram .

# Top-level product: laptop
part:laptop
    bom:directPart part:body ;
    bom:directPart part:screen_assembly ;
    bom:directPart part:keyboard ;
    bom:directPart part:battery ;
    bom:directPart part:mainboard .
"""

rules = """
@prefix bom:  <http://example.org/bom#> .
@prefix part: <http://example.org/part#> .
@prefix math: <http://www.w3.org/2000/10/swap/math#> .
@prefix log:  <http://www.w3.org/2000/10/swap/log#> .
@prefix list: <http://www.w3.org/2000/10/swap/list#> .

# Leaf: unit weight and cost become the assembly weight/cost
{ ?P bom:unitWeight ?W } => { ?P bom:totalWeight ?W } .
{ ?P bom:unitCost   ?C } => { ?P bom:totalCost   ?C } .

# Sub-assembly total weight = sum of direct parts' total weights
{
    ?Asm bom:directPart ?AnyPart .
    (?W { ?Asm bom:directPart ?P . ?P bom:totalWeight ?W } ?Ws) log:collectAllIn ?Asm .
    ?Ws math:sum ?TW
}
    => { ?Asm bom:totalWeight ?TW } .

# Sub-assembly total cost = sum of direct parts' total costs
{
    ?Asm bom:directPart ?AnyPart .
    (?C { ?Asm bom:directPart ?P . ?P bom:totalCost ?C } ?Cs) log:collectAllIn ?Asm .
    ?Cs math:sum ?TC
}
    => { ?Asm bom:totalCost ?TC } .

# Transitive part-of: direct or indirect
{ ?A bom:directPart ?B } => { ?A bom:hasPart ?B } .
{ ?A bom:hasPart ?B . ?B bom:hasPart ?C } => { ?A bom:hasPart ?C } .
"""

result = execute(data_strings=[data], rule_strings=[rules])

weights = {}
costs = {}

def local(tok):
    return tok.strip("<>").split("#")[-1].split(":")[-1]

def numval(tok):
    if '"' in tok:
        return tok.split('"')[1]
    return tok

for line in result.triples.splitlines():
    line = line.strip().rstrip(" .")
    if "bom:totalWeight" in line:
        parts = line.split()
        p = local(parts[0])
        w = float(numval(parts[2]))
        # Keep the largest value (the assembly total overrides the unit value)
        if p not in weights or w > weights[p]:
            weights[p] = w
    elif "bom:totalCost" in line:
        parts = line.split()
        p = local(parts[0])
        c = float(numval(parts[2]))
        if p not in costs or c > costs[p]:
            costs[p] = c

print("=== Bill of Materials: Recursive Cost/Weight Roll-up ===\n")
print(f"{'Component':<20} {'Weight(g)':>10} {'Cost($)':>10}")
print("-" * 42)

order = [
    "screen_panel", "backlight", "screen_assembly",
    "cpu", "ram", "mainboard",
    "body", "keyboard", "battery",
    "laptop",
]
for p in order:
    w = weights.get(p, 0)
    c = costs.get(p, 0)
    prefix = "  " if p not in ("screen_assembly", "mainboard", "laptop") else ""
    bold = " ← assembly" if p in ("screen_assembly", "mainboard", "laptop") else ""
    print(f"{prefix}{p:<20} {w:>10.0f} {c:>10.0f}{bold}")

print()
# Manual verification
screen_w = 400 + 50   # 450
screen_c = 180 + 30   # 210
main_w   = 30 + 20    # 50
main_c   = 350 + 60   # 410
laptop_w = 600 + screen_w + 200 + 300 + main_w  # 1600
laptop_c = 120 + screen_c + 45 + 80 + main_c    # 865
print(f"Manual check — laptop: weight={laptop_w}g, cost=${laptop_c}")
print(f"Engine result: weight={weights.get('laptop',0):.0f}g, cost=${costs.get('laptop',0):.0f}")
