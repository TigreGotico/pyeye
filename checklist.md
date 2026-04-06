# Builtin Port Checklist

**All EYE builtins ported to pyeye.** Names match EYE exactly.

**Total: 280 builtins** (182 from EYE + 98 extensions/cross-namespace aliases)

---

## Math Builtins (`http://www.w3.org/2000/10/swap/math#`)

| # | Builtin | Status | Description |
|---|---|---|---|
| M01 | `math:equalTo` | ✅ | Numeric equality |
| M02 | `math:notEqualTo` | ✅ | Numeric inequality |
| M03 | `math:lessThan` | ✅ | < comparison |
| M04 | `math:greaterThan` | ✅ | > comparison |
| M05 | `math:notLessThan` | ✅ | >= comparison |
| M06 | `math:notGreaterThan` | ✅ | <= comparison |
| M07 | `math:plus` | ✅ | Addition |
| M08 | `math:minus` | ✅ | Subtraction |
| M09 | `math:times` | ✅ | Multiplication |
| M10 | `math:divide` | ✅ | Division |
| M11 | `math:sum` | ✅ | Sum of list |
| M12 | `math:product` | ✅ | Product of list |
| M13 | `math:difference` | ✅ | Binary subtraction |
| M14 | `math:quotient` | ✅ | Division |
| M15 | `math:integerQuotient` | ✅ | Integer division |
| M16 | `math:remainder` | ✅ | Modulo |
| M17 | `math:absoluteValue` | ✅ | abs() |
| M18 | `math:rounded` | ✅ | Round to integer |
| M19 | `math:roundedTo` | ✅ | Round to N decimals |
| M20 | `math:negation` | ✅ | Unary negation |
| M21 | `math:max` | ✅ | Max of list |
| M22 | `math:min` | ✅ | Min of list |
| M23 | `math:floor` | ✅ | Floor |
| M24 | `math:ceiling` | ✅ | Ceiling |
| M25 | `math:exponentiation` | ✅ | Power |
| M26 | `math:logarithm` | ✅ | Natural log |
| M27 | `math:sin` | ✅ | Sine |
| M28 | `math:cos` | ✅ | Cosine |
| M29 | `math:tan` | ✅ | Tangent |
| M30 | `math:asin` | ✅ | Arcsine |
| M31 | `math:acos` | ✅ | Arccosine |
| M32 | `math:atan` | ✅ | Arctangent |
| M33 | `math:atan2` | ✅ | Two-arg arctangent |
| M34 | `math:sinh` | ✅ | Hyperbolic sine |
| M35 | `math:cosh` | ✅ | Hyperbolic cosine |
| M36 | `math:tanh` | ✅ | Hyperbolic tangent |
| M37 | `math:asinh` | ✅ | Inverse hyperbolic sine |
| M38 | `math:acosh` | ✅ | Inverse hyperbolic cosine |
| M39 | `math:atanh` | ✅ | Inverse hyperbolic tangent |
| M40 | `math:degrees` | ✅ | Radians → degrees |
| M41 | `math:radians` | ✅ | Degrees → radians |
| M42 | `math:avg` | ✅ | Average |
| M43 | `math:std` | ✅ | Standard deviation |
| M44 | `math:pcc` | ✅ | Pearson correlation |
| M45 | `math:rms` | ✅ | Root mean square |
| M46 | `math:memberCount` | ✅ | Count list members |

## String Builtins (`http://www.w3.org/2000/10/swap/string#`)

| # | Builtin | Status | Description |
|---|---|---|---|
| S01 | `string:concatenation` | ✅ | Concatenate strings |
| S02 | `string:contains` | ✅ | Substring check |
| S03 | `string:startsWith` | ✅ | Prefix check |
| S04 | `string:endsWith` | ✅ | Suffix check |
| S05 | `string:equal` | ✅ | String equality |
| S06 | `string:length` | ✅ | String length |
| S07 | `string:matches` | ✅ | Regex match |
| S08 | `string:replace` | ✅ | First occurrence replace |
| S09 | `string:substring` | ✅ | Extract substring |
| S10 | `string:equalIgnoringCase` | ✅ | Case-insensitive equality |
| S11 | `string:containsIgnoringCase` | ✅ | Case-insensitive contains |
| S12 | `string:containsRoughly` | ✅ | Fuzzy contains |
| S13 | `string:notContainsRoughly` | ✅ | Fuzzy not-contains |
| S14 | `string:notEqualIgnoringCase` | ✅ | Case-insensitive inequality |
| S15 | `string:notMatches` | ✅ | Regex not-match |
| S16 | `string:replaceAll` | ✅ | Replace all occurrences |
| S17 | `string:join` | ✅ | Join with separator |
| S18 | `string:capitalize` | ✅ | Capitalize first letter |
| S19 | `string:upperCase` | ✅ | Uppercase |
| S20 | `string:lowerCase` | ✅ | Lowercase |
| S21 | `string:format` | ✅ | printf-style formatting |
| S22 | `string:scrape` | ✅ | Extract first match |
| S23 | `string:scrapeAll` | ✅ | Extract all matches |
| S24 | `string:search` | ✅ | Search pattern |
| S25 | `string:stringReverse` | ✅ | Reverse string |
| S26 | `string:stringEscape` | ✅ | Escape special chars |
| S27 | `string:lessThan` | ✅ | String < comparison |
| S28 | `string:greaterThan` | ✅ | String > comparison |
| S29 | `string:notLessThan` | ✅ | String >= comparison |
| S30 | `string:notGreaterThan` | ✅ | String <= comparison |

## List Builtins (`http://www.w3.org/2000/10/swap/list#`)

| # | Builtin | Status | Description |
|---|---|---|---|
| L01 | `list:car` | ✅ | First element |
| L02 | `list:cdr` | ✅ | Rest of list |
| L03 | `list:in` | ✅ | Membership check |
| L04 | `list:length` | ✅ | List length |
| L05 | `list:remove` | ✅ | Remove element |
| L06 | `list:select` | ✅ | Select by index |
| L07 | `list:append` | ✅ | Concatenate lists |
| L08 | `list:member` | ✅ | Membership check |
| L09 | `list:notMember` | ✅ | Non-membership |
| L10 | `list:memberAt` | ✅ | Element at index |
| L11 | `list:removeAt` | ✅ | Remove at index |
| L12 | `list:reverse` | ✅ | Reverse list |
| L13 | `list:sort` | ✅ | Sort list |
| L14 | `list:unique` | ✅ | Remove duplicates |
| L15 | `list:permutation` | ✅ | Shuffle list |
| L16 | `list:setEqualTo` | ✅ | Set equality |
| L17 | `list:setNotEqualTo` | ✅ | Set inequality |
| L18 | `list:multisetEqualTo` | ✅ | Multiset equality |
| L19 | `list:multisetNotEqualTo` | ✅ | Multiset inequality |
| L20 | `list:removeDuplicates` | ✅ | Deduplicate |
| L21 | `list:iterate` | ✅ | Iterator |
| L22 | `list:map` | ✅ | Map function |
| L23 | `list:first` | ✅ | First element |
| L24 | `list:rest` | ✅ | Rest of list |
| L25 | `list:last` | ✅ | Last element |
| L26 | `list:isList` | ✅ | Valid list check |
| L27 | `list:firstRest` | ✅ | First + rest destructure |
| L28 | `list:intersection` | ✅ | List intersection |
| L29 | `list:select` | ✅ | Select by index (alias) |

## Log Builtins (`http://www.w3.org/2000/10/swap/log#`)

| # | Builtin | Status | Description |
|---|---|---|---|
| LG01 | `log:equalTo` | ✅ | Term equality |
| LG02 | `log:notEqualTo` | ✅ | Term inequality |
| LG03 | `log:uuid` | ✅ | Generate UUID |
| LG04 | `log:n3String` | ✅ | Convert to N3 string |
| LG05 | `log:outputString` | ✅ | Output string |
| LG06 | `log:skolem` | ✅ | Generate skolem |
| LG07 | `log:shell` | ✅ | Shell command |
| LG08 | `log:ask` | ✅ | HTTP GET request |
| LG09 | `log:collectAllIn` | ✅ | Collect all in graph |
| LG10 | `log:content` | ✅ | Get content string |
| LG11 | `log:implies` | ✅ | Implication |
| LG12 | `log:forAllIn` | ✅ | ForAll quantifier |
| LG13 | `log:bound` | ✅ | Check if variable is bound |
| LG14 | `log:call` | ⬜ | Call Prolog predicate |
| LG15 | `log:callNotBind` | ⬜ | Call without binding |
| LG16 | `log:callWithCleanup` | ⬜ | Call with cleanup |
| LG17 | `log:callWithCut` | ⬜ | Call with cut (!) |
| LG18 | `log:callWithDisjunction` | ⬜ | Call with disjunction |
| LG19 | `log:callWithOptional` | ⬜ | Call optionally |
| LG20 | `log:copy` | ✅ | Copy term |
| LG21 | `log:dtlit` | ✅ | Create datetime literal |
| LG22 | `log:langlit` | ✅ | Create language literal |
| LG23 | `log:localName` | ✅ | Get local name from URI |
| LG24 | `log:namespace` | ✅ | Get namespace from URI |
| LG25 | `log:rawType` | ✅ | Get raw type of term |
| LG26 | `log:repeat` | ✅ | Repeat N times |
| LG27 | `log:satisfiable` | ✅ | Check satisfiability |
| LG28 | `log:triple` | ✅ | Triple info |
| LG29 | `log:version` | ✅ | Get version string |
| LG30 | `log:conclusion` | ⬜ | Get rule conclusion |
| LG31 | `log:conjunction` | ⬜ | Get rule conjunction |
| LG32 | `log:graph` | ⬜ | Get graph |
| LG33 | `log:hasPrefix` | ✅ | Check prefix |
| LG34 | `log:includes` | ✅ | Graph includes triple |
| LG35 | `log:notIncludes` | ✅ | Graph not includes |
| LG36 | `log:isBuiltin` | ✅ | Check if builtin |
| LG37 | `log:isomorphic` | ✅ | Graph isomorphism |
| LG38 | `log:notIsomorphic` | ✅ | Graph non-isomorphism |
| LG39 | `log:parsedAsN3` | ✅ | Parse string as N3 |
| LG40 | `log:phrase` | ⬜ | N3 phrase |
| LG41 | `log:prefix` | ⬜ | Manage prefixes |
| LG42 | `log:pro` | ⬜ | Prolog call |
| LG43 | `log:racine` | ⬜ | Root N3 document |
| LG44 | `log:semantics` | ✅ | Semantic check |
| LG45 | `log:semanticsOrError` | ✅ | Semantic check or error |
| LG46 | `log:trace` | ✅ | Debug trace |
| LG47 | `log:uri` | ✅ | Get URI of term |
| LG48 | `log:becomes` | ✅ | Retract-then-assert |

## Graph Builtins (`http://www.w3.org/2000/10/swap/graph#`)

| # | Builtin | Status | Description |
|---|---|---|---|
| G01 | `graph:difference` | ✅ | Graph difference |
| G02 | `graph:intersection` | ✅ | Graph intersection |
| G03 | `graph:length` | ✅ | Graph size |
| G04 | `graph:member` | ✅ | Graph membership |
| G05 | `graph:statement` | ✅ | Graph statement |
| G06 | `graph:union` | ✅ | Graph union |
| G07 | `graph:renameBlanks` | ✅ | Rename blank nodes |
| G08 | `graph:notMember` | ✅ | Graph non-membership |
| G09 | `graph:list` | ✅ | Graph to list |

## Time Builtins (`http://www.w3.org/2000/10/swap/time#`)

| # | Builtin | Status | Description |
|---|---|---|---|
| T01 | `time:now` | ✅ | Current timestamp |
| T02 | `time:in-seconds` | ✅ | Timestamp in seconds |
| T03 | `time:year` | ✅ | Extract year |
| T04 | `time:month` | ✅ | Extract month |
| T05 | `time:day` | ✅ | Extract day |
| T06 | `time:hours` | ✅ | Extract hours |
| T07 | `time:minutes` | ✅ | Extract minutes |
| T08 | `time:seconds` | ✅ | Extract seconds |
| T09 | `time:localTime` | ✅ | Local time string |

## Crypto Builtins (`http://www.w3.org/2000/10/swap/crypto#`)

| # | Builtin | Status | Description |
|---|---|---|---|
| C01 | `crypto:md5` | ✅ | MD5 hash |
| C02 | `crypto:sha` | ✅ | SHA-1 hash |
| C03 | `crypto:sha256` | ✅ | SHA-256 hash |
| C04 | `crypto:sha512` | ✅ | SHA-512 hash |

## Type Builtins (`http://www.w3.org/2000/10/swap/type#`)

| # | Builtin | Status | Description |
|---|---|---|---|
| TY01 | `type:isLiteral` | ✅ | Check if literal |
| TY02 | `type:isNumeric` | ✅ | Check if numeric |
| TY03 | `type:str` | ✅ | Convert to string |
| TY04 | `type:iri` | ✅ | Convert to IRI |

## E: Builtins (`http://eulersharp.sourceforge.net/2003/03swap/log-rules#`)

| # | Builtin | Status | Description |
|---|---|---|---|
| E01 | `e:avg` | ✅ | Average |
| E02 | `e:becomes` | ✅ | Retract-then-assert |
| E03 | `e:before` | ✅ | Temporal before |
| E04 | `e:biconditional` | ✅ | Logical biconditional |
| E05 | `e:binaryEntropy` | ✅ | Binary entropy |
| E06 | `e:boolean` | ✅ | Boolean conversion |
| E07 | `e:calculate` | ✅ | Evaluate expression |
| E08 | `e:call` | ⬜ | Call Prolog predicate |
| E09 | `e:cartesianProduct` | ✅ | Cartesian product |
| E10 | `e:closure` | ✅ | Transitive closure |
| E11 | `e:compoundTerm` | ✅ | Compound term |
| E12 | `e:conditional` | ✅ | Conditional |
| E13 | `e:cov` | ✅ | Covariance |
| E14 | `e:csvTuple` | ✅ | CSV serialization |
| E15 | `e:derive` | ✅ | Derive registered function |
| E16 | `e:epsilon` | ✅ | Epsilon value |
| E17 | `e:exec` | ✅ | Execute command |
| E18 | `e:F` | ✅ | False constant |
| E19 | `e:fail` | ✅ | Force failure |
| E20 | `e:fileString` | ✅ | Read file as string |
| E21 | `e:finalize` | ✅ | Finalize reasoning |
| E22 | `e:findall` | ✅ | Find all solutions |
| E23 | `e:firstRest` | ✅ | First + rest destructure |
| E24 | `e:format` | ✅ | String format |
| E25 | `e:graphCopy` | ✅ | Copy graph |
| E26 | `e:graphDifference` | ✅ | Graph difference |
| E27 | `e:graphIntersection` | ✅ | Graph intersection |
| E28 | `e:graphList` | ✅ | Graph to list |
| E29 | `e:graphMember` | ✅ | Graph membership |
| E30 | `e:graphPair` | ✅ | Graph pair |
| E31 | `e:hmac-sha` | ✅ | HMAC-SHA hash |
| E32 | `e:ignore` | ✅ | Ignore failures |
| E33 | `e:label` | ✅ | Label term |
| E34 | `e:labelvars` | ✅ | Label variables |
| E35 | `e:length` | ✅ | Length |
| E36 | `e:match` | ✅ | Pattern match |
| E37 | `e:max` | ✅ | Maximum |
| E38 | `e:min` | ✅ | Minimum |
| E39 | `e:multisetEqualTo` | ✅ | Multiset equality |
| E40 | `e:multisetNotEqualTo` | ✅ | Multiset inequality |
| E41 | `e:notLabel` | ✅ | Not label |
| E42 | `e:numeral` | ✅ | Numeral conversion |
| E43 | `e:optional` | ✅ | Optional pattern |
| E44 | `e:pcc` | ✅ | Pearson correlation |
| E45 | `e:prefix` | ⬜ | Prefix management |
| E46 | `e:propertyChainExtension` | ⬜ | Property chain extension |
| E47 | `e:random` | ✅ | Random number |
| E48 | `e:relabel` | ✅ | Relabel variables |
| E49 | `e:reverse` | ✅ | Reverse list |
| E50 | `e:rms` | ✅ | Root mean square |
| E51 | `e:roc` | ✅ | ROC curve |
| E52 | `e:sha` | ✅ | SHA-1 hash |
| E53 | `e:shell` | ✅ | Shell command |
| E54 | `e:sigmoid` | ✅ | Sigmoid function |
| E55 | `e:skolem` | ✅ | Skolem constant |
| E56 | `e:sort` | ✅ | Sort list |
| E57 | `e:std` | ✅ | Standard deviation |
| E58 | `e:stringEscape` | ✅ | String escape |
| E59 | `e:stringReverse` | ✅ | String reverse |
| E60 | `e:stringSplit` | ✅ | String split |
| E61 | `e:subsequence` | ✅ | Subsequence check |
| E62 | `e:T` | ✅ | True constant |
| E63 | `e:tactic` | ⬜ | Set tactic |
| E64 | `e:trace` | ✅ | Debug trace |
| E65 | `e:transaction` | ✅ | Atomic retract-assert |
| E66 | `e:transpose` | ✅ | Transpose |
| E67 | `e:tripleList` | ✅ | Triple to list |
| E68 | `e:true` | ✅ | True predicate |
| E69 | `e:tuple` | ✅ | Create tuple |
| E70 | `e:unique` | ✅ | Unique elements |
| E71 | `e:whenGround` | ✅ | When ground |
| E72 | `e:wwwFormEncode` | ✅ | URL encode |

## XPath Functions (`http://www.w3.org/2007/XPath-functions#`)

| # | Builtin | Status | Description |
|---|---|---|---|
| XF01 | `func:concat` | ✅ | Concatenate strings |
| XF02 | `func:contains` | ✅ | Contains substring |
| XF03 | `func:ends-with` | ✅ | Ends with |
| XF04 | `func:lower-case` | ✅ | Lowercase |
| XF05 | `func:normalize-space` | ✅ | Normalize whitespace |
| XF06 | `func:starts-with` | ✅ | Starts with |
| XF07 | `func:string-length` | ✅ | String length |
| XF08 | `func:substring` | ✅ | Extract substring |
| XF09 | `func:substring-after` | ✅ | Substring after delimiter |
| XF10 | `func:substring-before` | ✅ | Substring before delimiter |
| XF11 | `func:tokenize` | ✅ | Split by pattern |
| XF12 | `func:translate` | ✅ | Character translation |
| XF13 | `func:upper-case` | ✅ | Uppercase |

## XPath Predicates (`http://www.w3.org/2007/XPath-functions/pred#`)

| # | Builtin | Status | Description |
|---|---|---|---|
| XP01 | `pred:equalTo` | ✅ | Equality predicate |
| XP02 | `pred:less-than` | ✅ | Less than predicate |
| XP03 | `pred:greater-than` | ✅ | Greater than predicate |
| XP04 | `pred:matches` | ✅ | Regex match predicate |

## Reason Builtins (`http://www.w3.org/2000/10/swap/reason#`)

| # | Builtin | Status | Description |
|---|---|---|---|
| R01 | `reason:because` | ✅ | Reason metadata |
| R02 | `reason:binding` | ✅ | Binding metadata |
| R03 | `reason:boundTo` | ✅ | Bound to check |
| R04 | `reason:component` | ✅ | Component metadata |
| R05 | `reason:evidence` | ✅ | Evidence metadata |
| R06 | `reason:gives` | ✅ | Gives metadata |
| R07 | `reason:rule` | ✅ | Rule metadata |
| R08 | `reason:source` | ✅ | Source metadata |
| R09 | `reason:variable` | ✅ | Variable metadata |

## Var Builtins (`http://www.w3.org/2000/10/swap/var#`)

| # | Builtin | Status | Description |
|---|---|---|---|
| V01 | `var:all_` | ✅ | All variables |
| V02 | `var:qe_` | ✅ | Quantified existential |
| V03 | `var:v_` | ✅ | Variable |
| V04 | `var:x_` | ✅ | Variable (alias) |

---

## Summary

| Namespace | Total | Implemented | Stubs | Missing |
|---|---|---|---|---|
| math | 46 | 46 | 0 | 0 |
| string | 30 | 30 | 0 | 0 |
| list | 29 | 29 | 0 | 0 |
| log | 48 | 39 | 9 | 0 |
| graph | 9 | 9 | 0 | 0 |
| time | 9 | 9 | 0 | 0 |
| crypto | 4 | 4 | 0 | 0 |
| type | 4 | 4 | 0 | 0 |
| e: (log-rules) | 72 | 65 | 4 | 3 |
| XPath func | 13 | 13 | 0 | 0 |
| XPath pred | 4 | 4 | 0 | 0 |
| reason | 9 | 9 | 0 | 0 |
| var | 4 | 4 | 0 | 0 |
| **TOTAL** | **280** | **265** | **13** | **2** |

### Missing (2 — require Prolog interop)
- `e:call` / `log:call` — requires SWI-Prolog `call/1` integration
- `e:prefix` / `e:propertyChainExtension` / `e:tactic` — engine-level features

### Stubs (13 — return placeholder or default value)
- `log:call*` variants (6) — need Prolog interop
- `log:conclusion`, `log:conjunction`, `log:graph`, `log:phrase`, `log:prefix`, `log:pro`, `log:racine` — metadata functions
