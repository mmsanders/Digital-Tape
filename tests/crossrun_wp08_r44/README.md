# WP-08 R44 cross-run playback property package

Run `python3 -B selftest.py` for the 33-case synthetic oracle, nine red controls and spoofed-label invariance. Run `python3 replay.py product-observations.jsonl --manifest new-manifest.json --adapter-kind product --adapter-source-sha SHA256 --product-commit SHA --product-tree SHA` for a separately built Product adapter. `ADAPTER.md` defines public call and raw fixture observations; `COVERAGE.md` states the property surface and exclusions. No Product acceptance is implied by the synthetic run.
