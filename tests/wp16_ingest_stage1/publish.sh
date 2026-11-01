#!/usr/bin/env bash
set -euo pipefail
pkg=tests/wp16_ingest_stage1
repo=mmsanders/Digital-Tape-Verification
tag=evidence-ingest1-stage1-adr180
asset=INGEST1-STAGE1-SOURCES.tar.gz
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
if gh release view "$tag" --repo "$repo" >/dev/null 2>&1; then
  gh release download "$tag" --repo "$repo" --pattern "$asset" --dir "$work"
else
  python3 -B "$pkg/fixtures.py" "$work/generated" --seed "$pkg/encoded-seed.tar.gz"
  python3 -B "$pkg/asset.py" --build "$work/generated" --archive "$work/$asset"
  python3 -B "$pkg/asset.py" --archive "$work/$asset" --destination "$work/check"
  gh release create "$tag" "$work/$asset" --repo "$repo" --target "$GITHUB_SHA" --title 'INGEST-1 complete Stage1 ADR180 CC0 sources' --notes-file "$pkg/ASSET-NOTES.md"
fi
# Durable download replay; local bootstrap alone does not establish availability.
python3 -B "$pkg/asset.py" --destination "$work/fetched"
python3 -B "$pkg/format_selftest.py" --sources "$work/fetched"
python3 -B "$pkg/integration_selftest.py" --sources "$work/fetched"
