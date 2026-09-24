# WP-13 embedded-readiness product evidence binding

This directory contains Software-owned collection plumbing for the independently
published `tests/embedded_readiness_draft8/` package.

The tranche preserves Structural Rule 1:

1. commit `7bdfddb73cfa8e2021719a506eb02ceeaf2663bb` imports only the exact verifier package and its `tests/IMPORTS.json` declaration;
2. the following binding commit adds only this collector and CI wiring.

The collector does **not** change engine configuration or behavior. It invokes the
normal `engine/Makefile`, whose existing product engine flags already include
`-fstack-usage -fcallgraph-info=su,da`, and retains the complete command log.
It then retains per-object `readelf`, `nm`, `size`, and `objdump` reports,
all compiler stack/callgraph files, the full engine source SHA-256 inventory,
tool versions, and the verifier-owned public-API `tape_instance_size()` probe.

Normalized `WP13-EMBEDDED-EVIDENCE-1` contains measurements/classifications only.
The authoritative six-row PASS/FAIL result is generated solely by the unchanged
verifier-owned runner.

Any red gate is returned as evidence; this issue does not authorize engine changes.
