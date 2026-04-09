"""
24 — Configuration Management
==============================
A practical use case: managing layered configuration with defaults,
overrides, and validation using N3 reasoning.

The pattern:
  1. Global defaults (base layer)
  2. Environment overrides (staging / production)
  3. Service-specific overrides (highest priority)
  4. Rules derive the effective config (last writer wins via negation)
  5. Rules validate the config (flag invalid combinations)

This demonstrates:
  - log:onNegativeSurface for "use default only if no override exists"
  - math: builtins for range validation
  - string: builtins for value checks
  - Hierarchical config merging without imperative code
"""

from pyeye import execute

# ---------------------------------------------------------------------------
# Layered configuration data
# ---------------------------------------------------------------------------
data = """
@prefix cfg:  <http://example.org/config#> .
@prefix svc:  <http://example.org/service#> .

# --- Global defaults ---
cfg:defaults cfg:maxConnections 100 .
cfg:defaults cfg:timeout        30 .
cfg:defaults cfg:logLevel       "INFO" .
cfg:defaults cfg:retryCount     3 .
cfg:defaults cfg:enableMetrics  false .

# --- Production environment overrides ---
cfg:production cfg:maxConnections 500 .
cfg:production cfg:logLevel       "WARN" .
cfg:production cfg:enableMetrics  true .

# --- Staging environment overrides ---
cfg:staging cfg:logLevel "DEBUG" .
cfg:staging cfg:timeout  60 .

# --- Service-specific overrides ---
svc:apiGateway    cfg:env cfg:production .
svc:apiGateway    cfg:maxConnections 1000 .     # Service overrides env

svc:authService   cfg:env cfg:production .

svc:debugWorker   cfg:env cfg:staging .
svc:debugWorker   cfg:logLevel "TRACE" .        # Service overrides env

svc:batchJob      cfg:env cfg:production .
svc:batchJob      cfg:retryCount 10 .
"""

# ---------------------------------------------------------------------------
# Config resolution rules
# ---------------------------------------------------------------------------
rules = """
@prefix cfg:  <http://example.org/config#> .
@prefix log:  <http://www.w3.org/2000/10/swap/log#> .
@prefix math: <http://www.w3.org/2000/10/swap/math#> .

# --- Config resolution: service > env > global default ---
# Each property: pick the most specific value available.

# maxConnections: service > env > default
{   ?Svc cfg:env ?Env .
    ?Svc cfg:maxConnections ?V }
    => { ?Svc cfg:effective_maxConnections ?V } .

{   ?Svc cfg:env ?Env .
    _:neg log:onNegativeSurface { ?Svc cfg:maxConnections ?Any } .
    ?Env cfg:maxConnections ?V }
    => { ?Svc cfg:effective_maxConnections ?V } .

{   ?Svc cfg:env ?Env .
    _:neg log:onNegativeSurface { ?Svc cfg:maxConnections ?Any } .
    _:neg2 log:onNegativeSurface { ?Env cfg:maxConnections ?Any } .
    cfg:defaults cfg:maxConnections ?V }
    => { ?Svc cfg:effective_maxConnections ?V } .

# timeout: service > env > default
{   ?Svc cfg:env ?Env .
    ?Svc cfg:timeout ?V }
    => { ?Svc cfg:effective_timeout ?V } .

{   ?Svc cfg:env ?Env .
    _:neg log:onNegativeSurface { ?Svc cfg:timeout ?Any } .
    ?Env cfg:timeout ?V }
    => { ?Svc cfg:effective_timeout ?V } .

{   ?Svc cfg:env ?Env .
    _:neg log:onNegativeSurface { ?Svc cfg:timeout ?Any } .
    _:neg2 log:onNegativeSurface { ?Env cfg:timeout ?Any } .
    cfg:defaults cfg:timeout ?V }
    => { ?Svc cfg:effective_timeout ?V } .

# logLevel: service > env > default
{   ?Svc cfg:env ?Env .
    ?Svc cfg:logLevel ?V }
    => { ?Svc cfg:effective_logLevel ?V } .

{   ?Svc cfg:env ?Env .
    _:neg log:onNegativeSurface { ?Svc cfg:logLevel ?Any } .
    ?Env cfg:logLevel ?V }
    => { ?Svc cfg:effective_logLevel ?V } .

{   ?Svc cfg:env ?Env .
    _:neg log:onNegativeSurface { ?Svc cfg:logLevel ?Any } .
    _:neg2 log:onNegativeSurface { ?Env cfg:logLevel ?Any } .
    cfg:defaults cfg:logLevel ?V }
    => { ?Svc cfg:effective_logLevel ?V } .

# retryCount: service > env > default
{   ?Svc cfg:env ?Env .
    ?Svc cfg:retryCount ?V }
    => { ?Svc cfg:effective_retryCount ?V } .

{   ?Svc cfg:env ?Env .
    _:neg log:onNegativeSurface { ?Svc cfg:retryCount ?Any } .
    _:neg2 log:onNegativeSurface { ?Env cfg:retryCount ?Any } .
    cfg:defaults cfg:retryCount ?V }
    => { ?Svc cfg:effective_retryCount ?V } .

# --- Validation rules ---

# Connections must not exceed 2000
{
    ?Svc cfg:effective_maxConnections ?V .
    ?V math:greaterThan 2000
}
    => { ?Svc cfg:configError "maxConnections exceeds 2000" } .

# Timeout must be positive
{
    ?Svc cfg:effective_timeout ?V .
    ?V math:lessThan 1
}
    => { ?Svc cfg:configError "timeout must be >= 1" } .

# TRACE log level only allowed in staging
{
    ?Svc cfg:effective_logLevel "TRACE" .
    ?Svc cfg:env cfg:production
}
    => { ?Svc cfg:configError "TRACE log level not allowed in production" } .
"""

print("=== Effective Configuration ===")
result = execute(data_strings=[data], rule_strings=[rules])

# Group by service
services = ["apiGateway", "authService", "debugWorker", "batchJob"]
SVC = "http://example.org/service#"
CFG = "http://example.org/config#"

for svc in services:
    print(f"\n--- svc:{svc} ---")
    svc_uri = SVC + svc
    for line in result.triples.splitlines():
        if svc_uri in line and "effective" in line:
            # Extract property and value
            parts = line.strip().rstrip(" .").split()
            if len(parts) >= 3:
                prop = parts[1].split("effective_")[-1].rstrip(">").lstrip("<")
                val = " ".join(parts[2:])
                print(f"  {prop:20s} = {val}")

print("\n=== Config Errors ===")
for line in result.triples.splitlines():
    if "configError" in line:
        print(" ", line.strip())
