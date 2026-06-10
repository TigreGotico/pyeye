# 13 — Custom Builtins

**Topic:** Extend the engine
**Key concepts:** `builtins={}`, custom `fn(args, engine)` protocol

pyeye's builtin registry is extensible. You can register Python functions as custom predicates and use them in N3 rules just like math: or string:.

Run:

```bash
python custom_builtins_demo.py
```

Back to the [examples index](../README.md).
