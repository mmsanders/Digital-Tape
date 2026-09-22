# P1-R25 WP-09 retained product evidence

This directory is a byte-for-byte Verification-side retention of the product
evidence named by Digital-Tape-Verification issue #38.

- Product repository: `mmsanders/Digital-Tape`
- Product commit: `9d3649d87f2adb093d18b34825e38ca9573ba0a5`
- Source path: `tests/record_adapter/evidence/p1-r25-product/observations.jsonl`
- Exact evidence SHA-256: `a88850df6554df973fdda6071f65184fcd9012b8886c253dafbff4fc9e0966fc`
- Original verifier publication: `af15a8f4e7069aff9e9d5a98728530702a4f1f56`
- Product-imported verifier subtree: `b7eb335d08f35b70f55fb54b5a0966c52a25688b`

The product commit's Git tree independently resolves
`tests/record_draft8` to that exact subtree SHA. Verification independently
recomputed the retained JSONL SHA-256 before publication here.

`replay_product_evidence.py` ignores the Software-authored stored verdict
strings. It regenerates verifier fixtures and expected post-media hashes, checks
the retained product identity/call/event trace, and applies the verifier oracle.
