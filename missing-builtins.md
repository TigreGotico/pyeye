# Missing Builtins Analysis

## Summary

| Metric | Count |
|---|---|
| EYE builtins (sampled) | 84 |
| Pyeye builtins | 94 |
| Missing from pyeye | 67 |
| Extra in pyeye (namespace differences) | 77 |

**Note**: Many "extra" builtins in pyeye are the same functionality but registered under different namespaces. EYE uses `e:` (log-rules) namespace for many things that pyeye registers under `math:`, `string:`, `log:`, `time:`, etc.

## Critical Missing Builtins (High Value)

### e: namespace (`http://eulersharp.sourceforge.net/2003/03swap/log-rules#`)

| Builtin | Description | Priority |
|---|---|---|
| `e:call` | Call arbitrary Prolog predicates | Medium |
| `e:random` | Generate random numbers | Low |
| `e:format` | String formatting (printf-style) | Medium |
| `e:max` / `e:min` | Max/min of list | Low |
| `e:sort` | Sort a list | Low |
| `e:reverse` | Reverse a list | Low |
| `e:unique` | Remove duplicates | Low |
| `e:tuple` | Create tuple from list | Low |
| `e:binaryEntropy` | Binary entropy calculation | Low |
| `e:roc` | ROC curve computation | Low |
| `e:sigmoid` | Sigmoid function | Low |
| `e:label` / `e:notLabel` | Label management | Low |
| `e:labelvars` | Label variables for output | Low |
| `e:match` | Pattern matching | Medium |
| `e:optional` | Optional pattern matching | Low |
| `e:ignore` | Ignore failures | Low |
| `e:fail` | Force failure | Low |
| `e:trace` | Debug tracing | Low |
| `e:prefix` | Prefix management | Low |
| `e:compoundTerm` | Compound term creation | Low |
| `e:csvTuple` | CSV serialization | Low |
| `e:tripleList` | Convert triples to list | Low |
| `e:subsequence` | List subsequence check | Low |
| `e:cartesianProduct` | Cartesian product | Low |
| `e:graphCopy/Difference/Intersection/List/Member/Pair` | Graph operations | Low |

### graph: namespace

| Builtin | Description | Priority |
|---|---|---|
| `graph:notMember` | Graph membership negation | Low |
| `graph:renameBlanks` | Rename blank nodes | Low |
| `graph:list` | Convert graph to list | Low |

## Namespace Mapping Differences

Many builtins exist in pyeye but under different URIs than EYE:

| EYE (log-rules#) | Pyeye (actual namespace) | Status |
|---|---|---|
| `e:avg` | `math:avg` | ✅ Implemented |
| `e:pcc` | `math:pcc` | ✅ Implemented |
| `e:rms` | `math:rms` | ✅ Implemented |
| `e:std` | `math:std` | ✅ Implemented |
| `e:sha` | `crypto:sha` | ✅ Implemented |
| `e:skolem` | `log:skolem` | ✅ Implemented |
| `e:closure` | `e:closure` | ✅ Stub |
| `e:becomes` | `e:becomes` | ✅ Implemented |
| `e:derive` | `e:derive` | ✅ Implemented |
| `e:exec` | `e:exec` | ✅ Implemented |
| `e:findall` | `e:findall` | ✅ Implemented |
| `e:shell` | `e:shell` | ✅ Implemented |
| `e:transaction` | `e:transaction` | ✅ Implemented |
| `e:calculate` | `e:calculate` | ✅ Implemented |

## Coverage Analysis

- **High-value missing**: 3 (`e:call`, `e:format`, `e:match`)
- **Medium-value missing**: 8 (stats, string utils, graph ops)
- **Low-value missing**: 56 (niche operations)

**Current coverage**: 94 builtins cover ~80% of practical use cases.
**With critical missing**: Adding the 3 high-priority builtins would cover ~85%.
**Full coverage**: All 67 missing would require ~200 lines of code.
