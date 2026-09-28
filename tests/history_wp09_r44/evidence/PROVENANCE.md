# Synthetic trace provenance (not Product evidence)

Regenerated for R45 by `python3 -B tests/history_wp09_r44/selftest.py --emit-synthetic tests/history_wp09_r44/evidence/synthetic.jsonl`, then `gzip -n -9` on the 5,097,385-byte raw JSONL. Fixed seed `0x9E3779B9`; plan SHA-256 `c41c8159862c40b759e059c3ed57b43ee94fd40ef7cb89f060fa5044d67be19c`. The changed raw bytes contain both B-slot observations, public info and remount reads at checkpoints.

- Raw uncompressed JSONL SHA-256: `7680b9470faca74bff1b2e062345c7c03b3956d7b2c2158ced6673e37fb3a68e`.
- Retained `synthetic.jsonl.gz` SHA-256: `b60e4fc7588d3fd6ea7a7175a2691d5a670246867d6d98f86683ee7a8b35c8b2`.
- Synthetic result: 10,000 continuous edits, 25 checkpoints, nine killed mutation controls and private-label spoof invariance. The compressed file contains the full unabridged raw callback/call/checkpoint trace, not a digest-only substitute.

Replay with `python3 replay.py evidence/synthetic.jsonl.gz --manifest new-manifest.json --adapter-kind synthetic --adapter-source-sha <selftest.py SHA> --product-commit <issued SHA> --product-tree <issued tree>`. The manifest must be created at a new path and labeled synthetic. Never cite this trace as Product acceptance.
