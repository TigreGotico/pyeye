"""
25 — Role-Based Access Control (RBAC)
======================================
A full RBAC policy engine implemented in N3: roles, permissions,
inheritance, and dynamic access decisions — all as pure inference rules.

Structure:
  - Users have roles  (:alice :hasRole :admin)
  - Roles have permissions (:admin :canDo :readAny, :writeAny, :deleteAny)
  - Roles can inherit from other roles (:manager :inheritsFrom :viewer)
  - Access decisions are derived triples: ?User :canAccess ?Resource

Demonstrates:
  - RBAC hierarchy via rule chaining
  - Permission inheritance (transitive role expansion)
  - Context-sensitive access (owner can always access their own resources)
  - Negation: explicit DENY overrides any ALLOW
  - Backward chaining for specific access queries
"""

from pyeye import execute, NamedNode, Variable, Triple

BASE    = "http://example.org/rbac#"
RESOURCE = "http://example.org/resource#"

# ---------------------------------------------------------------------------
# Policy data
# ---------------------------------------------------------------------------
policy = """
@prefix rbac: <http://example.org/rbac#> .
@prefix res:  <http://example.org/resource#> .

# --- Role hierarchy ---
rbac:admin    rbac:inheritsFrom rbac:manager .
rbac:manager  rbac:inheritsFrom rbac:editor .
rbac:editor   rbac:inheritsFrom rbac:viewer .

# --- Base permissions per role ---
rbac:viewer  rbac:permits rbac:read .
rbac:editor  rbac:permits rbac:write .
rbac:manager rbac:permits rbac:delete .
rbac:admin   rbac:permits rbac:admin_panel .

# --- User assignments ---
rbac:alice rbac:hasRole rbac:admin .
rbac:bob   rbac:hasRole rbac:editor .
rbac:carol rbac:hasRole rbac:viewer .
rbac:dave  rbac:hasRole rbac:manager .

# --- Resources ---
res:publicDocs  rbac:requiredPerm rbac:read .
res:editDocs    rbac:requiredPerm rbac:write .
res:archive     rbac:requiredPerm rbac:delete .
res:adminPanel  rbac:requiredPerm rbac:admin_panel .

# --- Resource ownership ---
res:myReport    rbac:owner rbac:bob .

# --- Explicit denials (overrides all allows) ---
rbac:carol rbac:denied rbac:bob .    # carol cannot access bob's reports
"""

# ---------------------------------------------------------------------------
# RBAC rules
# ---------------------------------------------------------------------------
rules = """
@prefix rbac: <http://example.org/rbac#> .
@prefix res:  <http://example.org/resource#> .
@prefix log:  <http://www.w3.org/2000/10/swap/log#> .

# 1. Inherit permissions transitively up the role hierarchy
{ ?Role rbac:inheritsFrom ?Parent . ?Parent rbac:permits ?Perm }
    => { ?Role rbac:permits ?Perm } .

# 2. Inherit role hierarchy itself (transitive)
{ ?Role rbac:inheritsFrom ?Mid . ?Mid rbac:inheritsFrom ?Top }
    => { ?Role rbac:inheritsFrom ?Top } .

# 3. Effective permissions for a user = permissions of their role
{ ?User rbac:hasRole ?Role . ?Role rbac:permits ?Perm }
    => { ?User rbac:effectivePerm ?Perm } .

# 4. Access granted if user has required permission
{ ?User rbac:effectivePerm ?Perm .
  ?Res  rbac:requiredPerm  ?Perm }
    => { ?User rbac:canAccess ?Res } .

# 5. Owner always can access their own resource
{ ?Res rbac:owner ?User }
    => { ?User rbac:canAccess ?Res } .

# 6. Explicit DENY overrides all grants (negation-as-failure not needed here —
#    deny is a positive assertion that the rule engine checks)
{ ?User rbac:canAccess ?Res .
  ?Res  rbac:owner ?Owner .
  ?User rbac:denied ?Owner }
    => { ?User rbac:accessDenied ?Res } .

# 7. Final: can access = granted AND NOT denied
{ ?User rbac:canAccess ?Res .
  _:neg log:onNegativeSurface { ?User rbac:accessDenied ?Res } }
    => { ?User rbac:allow ?Res } .
"""

print("=== RBAC Access Decisions ===\n")
result = execute(data_strings=[policy], rule_strings=[rules])

# Group output by user
users = ["alice", "bob", "carol", "dave"]
RBAC = "http://example.org/rbac#"
RES  = "http://example.org/resource#"

for user in users:
    allowed = []
    denied  = []
    perms   = []

    for line in result.triples.splitlines():
        # Match abbreviated form (rbac:alice) or full IRI form
        if f"rbac:{user} " not in line and f"rbac#{user}>" not in line:
            continue
        # Extract last token (object), strip punctuation and prefix
        obj = line.strip().rstrip(" .").split()[-1]
        obj = obj.split("#")[-1].rstrip(">").split(":")[-1]
        if ":allow " in line or " rbac:allow " in line:
            allowed.append(obj)
        elif ":accessDenied " in line or " rbac:accessDenied " in line:
            denied.append(obj)
        elif ":effectivePerm " in line or " rbac:effectivePerm " in line:
            perms.append(obj)

    print(f"rbac:{user}")
    print(f"  permissions : {sorted(perms)}")
    print(f"  allow       : {sorted(allowed)}")
    if denied:
        print(f"  DENIED      : {sorted(denied)}")
    print()


# ---------------------------------------------------------------------------
# Backward chain: who can access the admin panel?
# ---------------------------------------------------------------------------
print("=== BC Query: who can access adminPanel? ===")

result2 = execute(
    data_strings=[policy],
    rule_strings=[rules],
    query=Triple(
        Variable("User"),
        NamedNode(RBAC + "allow"),
        NamedNode(RES  + "adminPanel"),
    ),
)
seen = set()
for b in result2.query_answers:
    user = list(b.values())[0]
    name = user.value.split("#")[-1]
    if name not in seen:
        seen.add(name)
        print(" ", name)
