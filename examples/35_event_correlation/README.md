# 35 — Event Correlation / Complex Event Processing (CEP)

**Topic:** Complex event processing
**Key concepts:** Burst detection, time-window correlation, multi-stage alert derivation

Detect patterns across multiple events: - 3+ login failures within a short time window → :bruteForce alert - A login success shortly after multiple failures → :bruteForceSuccess alert - High-value transaction after account unlock → :suspiciousTransaction alert

Run:

```bash
python cep_demo.py
```

Back to the [examples index](../README.md).
