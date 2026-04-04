# Security Considerations

pyeye is a reasoning engine that executes N3 rules. Some builtins can execute
external commands or make network requests. This document describes the
security model and how to run pyeye safely.

## Dangerous Builtins

The following builtins can execute arbitrary code or access external resources:

| Builtin | Risk | Mitigation |
| :--- | :--- | :--- |
| `e:calculate` | Was `eval()` — now uses `ast.literal_eval` (safe) | ✅ Fixed |
| `e:exec` / `e:shell` | Command execution | Allowlist of ~30 safe commands only |
| `log:ask` | HTTP requests | SSRF protection: rejects private IPs, non-HTTP schemes |
| HTTP data loading | Fetches remote files | SSRF protection: same as `log:ask` |

## Command Allowlist

`e:exec` and `e:shell` only permit these commands:

```
echo, date, uname, whoami, hostname, id, uptime,
cat, head, tail, wc, ls, find, stat, file, md5sum, sha256sum,
curl, wget, ping, dig, nslookup,
grep, awk, sed, sort, uniq, tr, cut,
bc, expr, df, free, ps
```

Commands not in this list are silently rejected. Shell met injection (`;`, `|`, `$()`, etc.) is prevented by using `subprocess.run(..., shell=False)`.

## SSRF Protection

HTTP loading (`data_paths=["http://..."]`) and `log:ask` reject:
- `file://`, `ftp://`, and other non-HTTP schemes
- Private IP ranges (10.x, 172.16-31.x, 192.168.x, 127.x)
- Link-local addresses

## Running in Untrusted Environments

If you need to process untrusted N3 files:

1. **Disable dangerous builtins**: Pass a custom `builtins={}` dict to `execute()` that excludes `e:exec`, `e:shell`, `log:ask`.
2. **Don't use HTTP loading**: Only pass local file paths or strings.
3. **Use a container**: Run pyeye in a Docker container with no network access and minimal filesystem access.
4. **Set resource limits**: Use `max_steps` and `limit_answers` to prevent runaway reasoning.

```python
from pyeye import execute, BUILTIN_REGISTRY

# Safe mode: exclude command execution and HTTP
UNSAFE_PREFIXES = (
    "http://eulersharp.sourceforge.net/2003/03swap/log-rules#exec",
    "http://eulersharp.sourceforge.net/2003/03swap/log-rules#shell",
    "http://www.w3.org/2000/10/swap/log#ask",
)
SAFE_BUILTINS = {k: v for k, v in BUILTIN_REGISTRY.items()
                 if not any(k.startswith(p) for p in UNSAFE_PREFIXES)}

result = execute(
    data_strings=[...],
    rule_strings=[...],
    builtins=SAFE_BUILTINS,
    max_steps=10000,
)
```

## Reporting Vulnerabilities

If you find a security issue, please report it privately. Do not open a public issue.
