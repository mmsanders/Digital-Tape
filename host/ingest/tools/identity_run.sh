#!/usr/bin/env bash
# Cross-platform byte-identity run (contract §5, I6). Builds the corpus, ingests it with
# the release binary and prints the SHA-256 of both published files. Every qualified
# platform must print identical lines; tools/compare_identity.py checks that.
set -euo pipefail
cd "$(dirname "$0")/.."
out="${1:?usage: identity_run.sh OUTFILE}"
work="$(mktemp -d)"
cargo build --release --locked --quiet --bin ingest
cargo run --release --locked --quiet --example make_corpus -- "$work/corpus"
mkdir -p "$work/corpus/encoded"
for f in tone_cbr.mp3 tone_vbr_mono.mp3 tone_mpeg2.mp3 tone_noxing.mp3 tone.m4a tone_ts.m4a tone.aac tone16.flac tone24.flac; do
  cp "tests/fixtures/$f" "$work/corpus/encoded/$f"
done
bin=target/release/ingest
[ -x "$bin.exe" ] && bin="$bin.exe"
"$bin" --version
"$bin" --out "$work/out" --length 300 "$work/corpus/rates" "$work/corpus/depths" "$work/corpus/encoded"
{
  echo "audio.wav $(sha256sum "$work/out/audio.wav" | cut -d' ' -f1)"
  echo "manifest.json $(sha256sum "$work/out/manifest.json" | cut -d' ' -f1)"
} > "$out"
cat "$out"
cp "$work/out/manifest.json" "${out%.txt}.manifest.json"
