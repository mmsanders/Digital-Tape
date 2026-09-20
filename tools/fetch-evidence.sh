#!/usr/bin/env bash
# Fetch a retained observation bundle's raw bytes from its release asset.
#
# Raw evidence over 1 MiB lives in a release asset, not the working tree
# (CLAUDE.md §4). The committed .sha256 beside each run is the citation; this
# brings the bytes back and REFUSES to install them unless they hash to it.
#
# replay.py reads output/observation.json directly, so a relocation that did not
# ship this script would have broken the documented reproduce command in each
# run's README. That is why fetch-and-verify is a requirement, not a convenience.
#
# Usage:
#   tools/fetch-evidence.sh            # every run that needs its bytes
#   tools/fetch-evidence.sh 2026-09-14-r14
set -euo pipefail
cd "$(dirname "$0")/.."

TAG=evidence-2026-09
BASE="https://github.com/mmsanders/Digital-Tape/releases/download/$TAG"

declare -A ASSET=(
  [2026-09-14-r14]=r14-observation.json
  [2026-09-13-r11]=r11-observation.json
)

runs=("${@:-}")
if [ -z "${runs[0]:-}" ]; then runs=("${!ASSET[@]}"); fi

for run in "${runs[@]}"; do
  asset="${ASSET[$run]:-}"
  if [ -z "$asset" ]; then
    echo "unknown run '$run'; known: ${!ASSET[*]}" >&2
    exit 2
  fi
  dir="docs/verification/runs/$run"
  dest="$dir/product-evidence/output/observation.json"
  sums="$dir/observation.json.sha256"
  [ -f "$sums" ] || { echo "missing $sums" >&2; exit 2; }

  if [ -f "$dest" ] && (cd "$dir" && sha256sum -c --status observation.json.sha256); then
    echo "ok    $run already present and verified"
    continue
  fi

  echo "fetch $run <- $BASE/$asset"
  tmp=$(mktemp)
  trap 'rm -f "$tmp"' EXIT
  curl -fsSL "$BASE/$asset" -o "$tmp"

  want=$(cut -d' ' -f1 < "$sums")
  got=$(sha256sum "$tmp" | cut -d' ' -f1)
  if [ "$want" != "$got" ]; then
    echo "REFUSED $run: sha256 $got does not match the committed $want" >&2
    echo "        Nothing was installed. The asset is not the cited evidence." >&2
    exit 1
  fi

  mkdir -p "$(dirname "$dest")"
  mv "$tmp" "$dest"
  trap - EXIT
  echo "ok    $run verified against $sums and installed"
done

echo
echo "Fetched bytes are the cited evidence, not an acceptance of anything."
