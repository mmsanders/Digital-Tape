# WP-09 R44 seeded edit history

`python3 selftest.py` runs 10,000 independent model edits, 25 checkpoints, nine red controls and private-label spoof invariance. `python3 selftest.py --emit-synthetic new.jsonl` generates raw reproducibility evidence (refuses overwrite). `python3 replay.py product.jsonl --manifest new-manifest.json --adapter-kind product --adapter-source-sha SHA256 --product-commit SHA --product-tree SHA` replays a separate Product adapter's unabridged observations. See `ADAPTER.md` and `COVERAGE.md`. This authoring package is not Product implementation acceptance.
