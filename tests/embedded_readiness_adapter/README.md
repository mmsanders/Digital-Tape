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

## DRAFT-9 binding (#250)

`collect_product_evidence_draft9.py` binds the independently published
`tests/embedded_readiness_draft9/` package (tree `8e5d0853`, Verification PR #82)
and is what CI now runs. `collect_product_evidence.py` above is left
byte-identical: it is the binding behind the accepted DRAFT-8 evidence.

The DRAFT-9 collector reuses the DRAFT-8 build, object, stack and manifest code
unchanged. It rebuilds only two things:

- **Provenance.** It adds `spec_bundle`/`spec_hashes`, and checks the declared
  base and import against git history before measuring anything.
- **WP13-G5.** Every call expression in every engine `.c`/`.h` comes from
  clang's own AST (`-Xclang -ast-dump=json`). Each call is classified by what
  its callee resolves to:
  - `direct`;
  - `permitted_indirect`: exactly `dev_read`/`dev_write`/`dev_flush` →
    `tape_dev.read/write/flush` and `dev_progress` → caller-supplied
    `tape_progress_fn`, all in `engine/src/dev.h`;
  - `forbidden_indirect`;
  - `ambiguous`.

A permitted-looking wrapper outside `dev.h` is forbidden. A header that is not
self-contained counts as covered only when a translation unit that parsed
reaches it; each standalone clang log is retained. The DRAFT-8
function-address-in-data backstop still reports violations.
