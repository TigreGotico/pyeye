# Security Considerations

pyeye is a reasoning engine that executes N3 rules. Some builtins run external
commands, read local files, or make network requests. This document describes
the security model and how to run pyeye safely on untrusted input.

Namespace prefixes used below:

- `e:` = `http://eulersharp.sourceforge.net/2003/03swap/log-rules#`
- `log:` = `http://www.w3.org/2000/10/swap/log#`

## Builtins with system access

| Builtin | Capability |
| :--- | :--- |
| `e:exec` | Runs an allowlisted external command, returns its exit code |
| `log:shell` | Runs an allowlisted external command, returns its stdout |
| `e:fileString` | Reads any local file the process can read |
| `log:ask` | HTTP/HTTPS GET request, returns the body (capped at 10KB) |
| HTTP data loading | `data_paths=["http://…"]` / `--n3 http://…` fetches remote documents |

`e:calculate` evaluates expressions with `ast.literal_eval` (literals only) and
cannot execute arbitrary code.

## Command execution (`e:exec`, `log:shell`)

Command strings are split with `shlex` and run via
`subprocess.run(..., shell=False, timeout=30)`. No shell is involved, so
`;`, `|`, `$()` and similar shell syntax are not interpreted. Only commands
whose basename is on this allowlist run; anything else fails silently:

```
echo, date, uname, whoami, hostname, id, uptime,
cat, head, tail, wc, ls, find, stat, file, md5sum, sha256sum,
curl, wget, ping, dig, nslookup,
grep, awk, sed, sort, uniq, tr, cut,
bc, expr, df, free, ps
```

The allowlist limits *which* programs run, not what they read: several of the
allowed commands (`cat`, `head`, `grep`, …) can disclose any file the pyeye
process can access. Treat `e:exec`/`log:shell` as file-read primitives too.

## SSRF Protection

HTTP loading (`data_paths=["http://…"]`) and `log:ask` reject:

- `file://`, `ftp://`, and other non-HTTP schemes
- Private IP ranges (10.x, 172.16-31.x, 192.168.x, 127.x)
- Link-local addresses

Response bodies are capped at 10 KB.

## Running on Untrusted Input

If you need to process untrusted N3 files:

1. **Disable system-access builtins**: pass a filtered `builtins` dict to
   `execute()` that excludes `e:exec`, `log:shell`, `e:fileString`, `log:ask`.
2. **Don't use HTTP loading**: only pass local file paths or strings.
3. **Use a container**: run pyeye with no network access and minimal
   filesystem access.
4. **Set resource limits**: use `timeout_seconds`, `max_steps` and
   `limit_answers` to bound runaway reasoning.

```python
from pyeye import execute, BUILTIN_REGISTRY

UNSAFE = (
    "http://eulersharp.sourceforge.net/2003/03swap/log-rules#exec",
    "http://eulersharp.sourceforge.net/2003/03swap/log-rules#fileString",
    "http://www.w3.org/2000/10/swap/log#shell",
    "http://www.w3.org/2000/10/swap/log#ask",
)
SAFE_BUILTINS = {k: v for k, v in BUILTIN_REGISTRY.items() if k not in UNSAFE}

result = execute(
    data_strings=[...],
    rule_strings=[...],
    builtins=SAFE_BUILTINS,
    max_steps=10000,
)
```

## Reporting Vulnerabilities

If you find a security issue, please report it privately. Do not open a
public issue.
