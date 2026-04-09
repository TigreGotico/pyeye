"""
02 — Family Tree
================
Multi-hop reasoning: derive grandparent, sibling, ancestor (transitive).

Concepts:
  - Rules with multi-triple bodies (conjunction)
  - Chain rules (rule output feeds next rule)
  - pass_mode: include original facts in the output
"""

from pyeye import execute

facts = """
@prefix fam: <http://example.org/family#> .

fam:alice  fam:parent fam:bob .
fam:alice  fam:parent fam:carol .
fam:bob    fam:parent fam:dave .
fam:carol  fam:parent fam:eve .
"""

rules = """
@prefix fam: <http://example.org/family#> .

# Inverse: parent → child
{ ?X fam:parent ?Y }
    => { ?Y fam:child ?X } .

# Grandparent: two hops of parent
{ ?X fam:parent ?Y .
  ?Y fam:parent ?Z }
    => { ?X fam:grandparent ?Z } .

# Siblings share a parent
{ ?X fam:parent ?P .
  ?Y fam:parent ?P }
    => { ?X fam:sibling ?Y } .

# Ancestor: base case — parent is an ancestor
{ ?X fam:parent ?Y }
    => { ?X fam:ancestor ?Y } .

# Ancestor: inductive case — ancestor is transitive
{ ?X fam:ancestor ?Y .
  ?Y fam:ancestor ?Z }
    => { ?X fam:ancestor ?Z } .
"""

result = execute(
    data_strings=[facts],
    rule_strings=[rules],
    pass_mode=True,   # include original facts in output
)

print(result.triples)

# Useful: filter just the derived relationship
print("\n--- grandparent triples only ---")
for line in result.triples.splitlines():
    if "grandparent" in line:
        print(line)

print("\n--- ancestor triples only ---")
for line in result.triples.splitlines():
    if "ancestor" in line:
        print(line)
