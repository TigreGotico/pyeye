"""
16 — Crypto Builtins
====================
The crypto: namespace provides one-way hash functions for content
fingerprinting, deduplication, and integrity verification.

Builtins:
  - ?S crypto:md5    ?Hash  — MD5 hex digest (128-bit)
  - ?S crypto:sha    ?Hash  — SHA-1 hex digest (deprecated, kept for compat)
  - ?S crypto:sha256 ?Hash  — SHA-256 hex digest (recommended)
  - ?S crypto:sha512 ?Hash  — SHA-512 hex digest

Subject is the input string; object receives the hex digest.

Use cases:
  - Content-addressed deduplication
  - Integrity fingerprinting
  - Deriving stable identifiers from content
"""

from pyeye import execute

# Example 1: Content fingerprinting
print("=== Content Fingerprinting ===")

data = """
@prefix doc: <http://example.org/doc#> .

doc:report1 doc:title "Q1 Results" ; doc:body "Revenue increased 12% YoY" .
doc:report2 doc:title "Q2 Results" ; doc:body "Revenue increased 8% YoY" .
doc:report3 doc:title "Q1 Results" ; doc:body "Revenue increased 12% YoY" .
"""

rules = """
@prefix doc:    <http://example.org/doc#> .
@prefix crypto: <http://www.w3.org/2000/10/swap/crypto#> .
@prefix string: <http://www.w3.org/2000/10/swap/string#> .

# Fingerprint each document from title + body concatenated
{
    ?D doc:title ?T .
    ?D doc:body  ?B .
    (?T " | " ?B) string:concatenation ?Content .
    ?Content crypto:sha256 ?Hash
}
    => { ?D doc:fingerprint ?Hash } .
"""

result = execute(data_strings=[data], rule_strings=[rules])
print(result.triples)
# Note: report1 and report3 have identical content → identical fingerprints


# Example 2: Detect duplicate content by matching fingerprints
print("\n=== Duplicate Detection ===")

rules2 = """
@prefix doc:    <http://example.org/doc#> .
@prefix crypto: <http://www.w3.org/2000/10/swap/crypto#> .
@prefix string: <http://www.w3.org/2000/10/swap/string#> .
@prefix log:    <http://www.w3.org/2000/10/swap/log#> .

# Compute fingerprints
{
    ?D doc:title ?T .
    ?D doc:body ?B .
    (?T " | " ?B) string:concatenation ?Content .
    ?Content crypto:sha256 ?Hash
}
    => { ?D doc:fingerprint ?Hash } .

# Two different documents with the same fingerprint = duplicate
{
    ?A doc:fingerprint ?H .
    ?B doc:fingerprint ?H .
    ?A log:notEqualTo ?B
}
    => { ?A doc:duplicateOf ?B } .
"""

result2 = execute(data_strings=[data], rule_strings=[rules2])
for line in result2.triples.splitlines():
    if "duplicate" in line or "fingerprint" in line:
        print(line)


# Example 3: Password-style hashing
print("\n=== API Key Hashing ===")

data3 = """
@prefix api: <http://example.org/api#> .

api:user1 api:rawKey "secret-key-abc123" .
api:user2 api:rawKey "another-secret-xyz" .
"""

rules3 = """
@prefix api:    <http://example.org/api#> .
@prefix crypto: <http://www.w3.org/2000/10/swap/crypto#> .

# Store only the hash, never the raw key in derived facts
{
    ?U api:rawKey ?K .
    ?K crypto:sha256 ?H
}
    => { ?U api:keyHash ?H } .
"""

result3 = execute(data_strings=[data3], rule_strings=[rules3])
print(result3.triples)
