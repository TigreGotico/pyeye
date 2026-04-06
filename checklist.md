# Builtin Registry — EYE Namespace Only

**All 240 builtins** registered under single namespace:
`http://eulersharp.sourceforge.net/2003/03swap/log-rules#`

No cross-namespace aliases. Every builtin uses the EYE namespace.

---

## Complete Registry (240 builtins)

### Math (46)
equalTo, lessThan, greaterThan, notEqualTo, plus, minus, times, divide, floor, ceiling, exponentiation, logarithm, sin, cos, tan, avg, std, pcc, rms, sum, product, difference, quotient, integerQuotient, remainder, absoluteValue, rounded, roundedTo, negation, max, min, notLessThan, notGreaterThan, acos, asin, atan, atan2, sinh, cosh, tanh, acosh, asinh, atanh, degrees, radians, memberCount

### String (30)
concatenation, contains, length, startsWith, endsWith, equal, matches, replace, substring, equalIgnoringCase, containsIgnoringCase, containsRoughly, notContainsRoughly, notEqualIgnoringCase, notMatches, replaceAll, join, capitalize, upperCase, lowerCase, format, scrape, scrapeAll, search, stringReverse, stringEscape, lessThan, greaterThan, notLessThan, notGreaterThan

### List (28)
in, length, car, cdr, select, remove, append, member, notMember, memberAt, removeAt, reverse, sort, unique, permutation, setEqualTo, setNotEqualTo, multisetEqualTo, multisetNotEqualTo, removeDuplicates, iterate, map, first, rest, last, isList, firstRest, intersection

### Log (48)
outputString, skolem, content, equalTo, notEqualTo, uuid, n3String, implies, forAllIn, ask, shell, collectAllIn, bound, call, callNotBind, callWithCleanup, callWithCut, callWithDisjunction, callWithOptional, copy, dtlit, langlit, localName, namespace, rawType, repeat, satisfiable, triple, version, conclusion, conjunction, graph, hasPrefix, includes, notIncludes, isBuiltin, isomorphic, notIsomorphic, parsedAsN3, phrase, prefix, pro, racine, semantics, semanticsOrError, trace, uri, becomes

### Type (4)
isLiteral, isNumeric, str, iri

### Crypto (4)
md5, sha, sha256, sha512

### Graph (9)
member, length, difference, intersection, union, statement, renameBlanks, notMember, list

### Time (9)
now, year, month, day, in-seconds, hours, minutes, seconds, localTime

### E: Extended (64)
calculate, findall, closure, exec, derive, before, biconditional, binaryEntropy, boolean, cartesianProduct, compoundTerm, conditional, cov, csvTuple, epsilon, F, fail, fileString, finalize, graphCopy, graphDifference, graphIntersection, graphList, graphMember, graphPair, hmac-sha, ignore, label, labelvars, match, multisetEqualTo, multisetNotEqualTo, notLabel, numeral, optional, propertyChainExtension, random, relabel, roc, sigmoid, stringSplit, subsequence, T, tactic, transpose, tripleList, true, tuple, whenGround, wwwFormEncode

### Reason (9)
because, binding, boundTo, component, evidence, gives, rule, source, variable

### Var (4)
all_, qe_, v_, x_

### RIF/XPath Functions (13)
concat, substring, string-length, upper-case, lower-case, contains, starts-with, ends-with, substring-before, substring-after, translate, normalize-space, tokenize

### XPath Predicates (4)
equalTo, less-than, greater-than, matches

---

## Usage

All builtins invoked with same namespace prefix:

```n3
@prefix e: <http://eulersharp.sourceforge.net/2003/03swap/log-rules#> .

# Math
{ (5 3 2) e:sum ?Total } => { :result :value ?Total } .

# String
{ "hello" e:contains "ell" } => { :yes :match :true } .

# List
{ ?List e:car ?First } => { :result :first ?First } .

# Log
{ :data e:skolem ?S } => { :result :skolem ?S } .
```
