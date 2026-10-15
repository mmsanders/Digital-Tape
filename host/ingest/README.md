# host/ingest — INGEST-1 (WP-16)

`ingest` turns explicitly ordered folders of audio into one new directory holding a canonical
`audio.wav` (44.1 kHz, 16-bit, stereo, 44-byte header) and `manifest.json`, exactly per
[the INGEST-1 contract](../../docs/WP16-INGEST-CONTRACT.md) (ADR-177, amended ADR-178).
It is a standalone host tool: no device access, no engine code, no format logic (guardrails 03,
09, 12). `tapectl load` consumes the WAV; the manifest stays on the computer.

**Status:** Software implementation for #429. Not independently accepted. Verification #169
authors the oracle separately; no real-card WP16 or WP15 claim.

```sh
cargo build --release --locked          # → target/release/ingest
ingest --out DEST --length SECONDS FOLDER [FOLDER ...]
ingest --version                        # tool version and arithmetic-profile ID
cargo test --release --locked           # Software's own unit and contract checks
python3 tools/check_vendor.py --selftest
tools/identity_run.sh OUT.txt           # cross-platform identity corpus → two SHA-256 lines
```

Exit 0 only after both files are published; 2 for an input/contract refusal; 1 for an I/O or tool
failure. Every refusal names the logical source path (`folder_ordinal/NFC_name`) or the join.

## Arithmetic profile `INGEST1-AP1`

| Stage | Choice |
|---|---|
| Language/toolchain | Rust 1.97.0 (`rust-toolchain.toml`), `--locked`, release profile in `Cargo.toml` |
| WAV, AIFF/AIFC, FLAC | Own strict parsers/decoder (`src/wav.rs`, `src/flac.rs`); FLAC frame CRC-8/CRC-16 and STREAMINFO MD5 verified |
| MP3, AAC-LC | Symphonia 0.6.1 decoders, vendored and patched (`vendor/PATCHES.md`): platform libm → pure-Rust `libm` 0.2.16, HE-AAC refusal, no MP3 concealment; own frame/box parsing and trim validation |
| Resampler | Kaiser windowed sinc, 100 dB, exact L/M polyphase, binary64 scalar (`src/dsp.rs`) |
| Meter | BS.1770-5 K-weighting at 44.1 kHz, Tech 3341 V4 gating; true peak 256-phase 80 dB interpolator, 4x grid plus local-maximum refinement |
| Dither | The issued xorshift32 TPDF, reset per source and per gain attempt |
| Hashes | `sha2` 0.10.9 (SHA-256), `md-5` 0.10.6 (FLAC MD5 check) |

The manifest's `libraries` array carries each library's version and SHA-256 (the Cargo.lock
checksum, or a hash of the vendored, patched tree computed by `build.rs`).

**Determinism.** No platform C maths, no SIMD-dependent dispatch, no FMA contraction (Rust never
contracts), no hash-map iteration, fixed reduction order. The 4-lane true-peak grid kernel sums
each lane in the same order as the scalar path. CI (`.github/workflows/ingest.yml`) builds on
Linux x64, macOS arm64 and Windows x64 and requires byte-identical outputs on a corpus covering
all fifteen rates and every decoder. Hosted Windows is Windows Server, not the Windows 11
desktop the contract qualifies; that native run is separate.

## Interface facts and interpretations for Verification/PM

These are the implementation's choices where the contract leaves room. None changes an issued
rule; each is returned to PM384 as a fact, not a self-acceptance.

1. **Lossless sources** (WAV/AIFF/FLAC) report `gapless_known`, `trim_evidence` `none`, trims 0.
   Only lossy streams without admitted metadata are `gapless_unknown`.
2. **WAVE_FORMAT_EXTENSIBLE**: channel mask must be exactly `0x4` (mono) or `0x3` (stereo); `0`
   or anything else is refused as ambiguous. Valid bits ≤ container bits are decoded at the
   container width.
3. **Container sizes are strict**: RIFF/FORM size must equal the file length; AIFF `SSND` must hold
   exactly the `COMM` frame count. Unknown RIFF/AIFF chunks are skipped (standard extensibility).
4. **MP3 trim**: needs a Xing/Info frame with a frame count equal to the real audio frames and a
   LAME-compatible tag whose CRC matches either LAME's span or FFmpeg's fixed 190-byte span.
   Head = delay + 529, tail = padding − 529; padding < 529 refuses as out of range. The Info
   frame is metadata and is not decoded. VBRI refuses by name.
5. **M4A trim**: one edit, media rate 1, `media_time ≥ 0`, nonzero duration, both converting to
   whole source frames exactly. A shortened final `stts` sample (FFmpeg's end signalling) is
   admitted only when it agrees exactly with the edit end; alone it refuses. `iTunSMPB` must
   agree with the edit list; alone it refuses. Tracks other than `soun`/`vide` (text, chapters)
   are ignored; `vide` refuses.
6. **Known limitations inside the positive matrix**: ADTS frames carrying more than one raw data
   block refuse by name; the ADTS CRC is not verified (the decoder then refuses corrupt data
   only when it fails to decode). Both are returned to PM384.
7. **Names**: NFC; logical-path and case-folded (full Unicode lowercase) collisions refuse;
   characters Windows cannot store, trailing dot/space and reserved device names refuse. A
   FOLDER argument is resolved; entries inside it are never followed.
8. **Gain**: start `min(-16-L, -1-P-0.1)`; on a final peak violation reduce by the excess +
   0.001 dB and set `peak_limited`; an unlimited source outside ±0.5 LU is moved by the error
   (capped at the peak bound). `target_gain_db` is `-16-L`, or `0` for unmeasurable sources
   and digital silence.
9. **Joined true peak**: computed on the assembled stream at every boundary (source/source,
   source/gap); interior points are identical to the isolated measurement by construction.
10. **Stage**: `.<DEST name>.ingest-stage-<pid>-<n>` beside DEST, published by
   `renameat2(RENAME_NOREPLACE)` / `renamex_np(RENAME_EXCL)` / `MoveFileExW(0)`.
11. **True-peak bandwidth**: the interpolator is flat to about 21 kHz. Native 44.1 kHz content
   above that may under-read; resampled sources are already band-limited below 22.05 kHz.

Tests, fixtures and their regeneration: `tests/cli.rs`, `tests/fixtures/make.sh` (generated tones only).
