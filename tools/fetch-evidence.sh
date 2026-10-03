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
#   tools/fetch-evidence.sh wp11      # only the WP-11 assets (below)
#
# WP-11 (#366): release assets the golden suite needs are declared one per line
# in tests/golden_adapter/RELEASE-ASSETS:
#
#   <sha256>  <destination path from the repo root>  <release tag>  <asset name>
#
# Each is fetched from that tag, refused unless it hashes to the declared value,
# and only then installed. A file already present and matching is left alone.
# FETCH_EVIDENCE_RELEASES overrides the releases base URL (used by
# tools/ci/verify-fetch-evidence-wp11.sh to prove the refusal path).
set -euo pipefail
cd "$(dirname "$0")/.."

RELEASES=${FETCH_EVIDENCE_RELEASES:-https://github.com/mmsanders/Digital-Tape/releases/download}
WP11_ASSETS=${WP11_ASSETS:-tests/golden_adapter/RELEASE-ASSETS}

fetch_wp11() {
  [ -f "$WP11_ASSETS" ] || { echo "ok    no WP-11 release assets declared ($WP11_ASSETS absent)"; return 0; }
  local want dest tag asset got tmp
  while read -r want dest tag asset; do
    case "$want" in ''|\#*) continue ;; esac
    if [ -z "${asset:-}" ] || ! [[ $want =~ ^[0-9a-f]{64}$ ]]; then
      echo "REFUSED malformed line in $WP11_ASSETS: $want $dest $tag $asset" >&2
      return 1
    fi
    if [ -f "$dest" ] && [ "$(sha256sum "$dest" | cut -d' ' -f1)" = "$want" ]; then
      echo "ok    $dest already present and verified"
      continue
    fi
    echo "fetch $dest <- $tag/$asset"
    tmp=$(mktemp)
    if ! curl -fsSL "$RELEASES/$tag/$asset" -o "$tmp"; then
      rm -f "$tmp"; echo "REFUSED $dest: download failed" >&2; return 1
    fi
    got=$(sha256sum "$tmp" | cut -d' ' -f1)
    if [ "$got" != "$want" ]; then
      rm -f "$tmp"
      echo "REFUSED $dest: sha256 $got does not match the declared $want" >&2
      echo "        Nothing was installed. The asset is not the cited evidence." >&2
      return 1
    fi
    mkdir -p "$(dirname "$dest")"
    mv "$tmp" "$dest"
    echo "ok    $dest verified against the declared sha256 and installed"
  done < "$WP11_ASSETS"
}

if [ "${1:-}" = wp11 ]; then
  fetch_wp11
  exit $?
fi

TAG=evidence-2026-09
BASE="$RELEASES/$TAG"

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

# With no arguments, everything: the retained runs above and the WP-11 assets.
if [ $# -eq 0 ]; then fetch_wp11; fi

echo
echo "Fetched bytes are the cited evidence, not an acceptance of anything."
