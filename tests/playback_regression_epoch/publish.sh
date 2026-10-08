#!/usr/bin/env bash
set -euo pipefail
repo=mmsanders/Digital-Tape-Verification
tag=evidence-readopt-d10-1
pkg=tests/playback_regression_epoch
work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT
# Never overwrite an issued asset. Existing assets must authenticate.
if gh release view "$tag" --repo "$repo" >/dev/null 2>&1; then
  gh release download "$tag" --repo "$repo" --pattern READOPT-D10-1.tar --dir "$work"
else
  git init -q "$work/product"
  git -C "$work/product" fetch -q --depth=1 https://github.com/mmsanders/Digital-Tape.git a1b362268a53320e676359976593b2f01202ef13
  git -C "$work/product" checkout -q --detach FETCH_HEAD
  python3 -B "$pkg/bootstrap.py" --product "$work/product" --downloads "$work/downloads" --output "$work/READOPT-D10-1.tar"
  python3 -B "$pkg/asset.py" --archive "$work/READOPT-D10-1.tar" --destination "$work/prepublish"
  gh release create "$tag" "$work/READOPT-D10-1.tar" --repo "$repo" --target a273355e8aa87b967ce66cf9f40e6a71e3ee9513 --title 'READOPT-D10-1 immutable transcript evidence' --notes 'ADR-172 expected transcript binding; not Product acceptance. SHA-256: 81fadd9a69adde06cf83c0774facdb987d1413c23231b6ba5b1dbe01ed275610. Declaration and replay checker published separately on Verification main. Old evidence remains unchanged.'
fi
# Fetch from the public durable release endpoint, not the local bootstrap or CI store.
python3 -B "$pkg/asset.py" --destination "$work/fetched"
python3 -B "$pkg/check.py" transition --root "$work/fetched"
