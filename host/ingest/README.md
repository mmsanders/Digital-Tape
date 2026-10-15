# host/ingest — INGEST-1 (WP-16)

`ingest` turns explicitly ordered folders of audio into one new directory holding a canonical
`audio.wav` (44.1 kHz, 16-bit, stereo, 44-byte header) and `manifest.json`, exactly per
[the INGEST-1 contract](../../docs/WP16-INGEST-CONTRACT.md) (ADR-177, amended ADR-178).
It is a standalone host tool: no device access, no engine code, no format logic (guardrails 03,
09, 12). `tapectl load` consumes the WAV; the manifest stays on the computer.

**Status:** Software implementation for #429/#435 (ADR-180 applied). Not independently accepted. Verification #169
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

## Arithmetic profile `INGEST1-AP2`

`INGEST1-AP2` (#435) is `INGEST1-AP1` plus the ADR-180 validation: a verified ADTS CRC and the
`sowt` 16-bit rule. No arithmetic changed. For every input both admit, `audio.wav` is byte-identical
(identity corpus AP1 `e79bbf26…` reproduced by AP2). The manifest differs because its `libraries`
entry for the patched `symphonia-codec-aac` tree changed, so the ID is bumped per §5.


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

These are the implementation's choices where the contract leaves room. ADR-180 adopted (a), (c),
(d) and (e) as contract text and ruled (b) the other way: a present ADTS CRC is verified. Items
not raised as questions stay implementation choices, not contract text.

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
6. **ADTS** (ADR-180): one raw data block per frame; more refuses by name. When
   `protection_absent=0` the CRC is verified: CRC-16 0x8005, initial 0xFFFF, over the 56 header
   bits and then each SCE/LFE's first 192 bits, each CPE's first 192 bits and its second channel's
   first 128 bits (zero-padded when shorter), and each DSE whole; FIL/END and the element IDs
   are not covered. These are the FDK reference decoder's regions; the CRC fixtures come from the
   FDK reference encoder (`tests/fixtures/fdkgen.rs`). A mismatch refuses by name.
   **AIFC `sowt`** is little-endian PCM16 only; any other sampleSize refuses by name.
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
11. **True-peak bandwidth** (measured, `examples/tp_sweep.rs` and the interpolator response):
   the half-sample phase is within ±0.0011 dB from DC to 21.0 kHz, −1.13 dB at 21.5 kHz and
   −5.96 dB at 21.8 kHz. The §3 ≤0.1 dB under-read bound therefore holds for content up to
   about 21.2 kHz; steady tones read within 0.001 dB to 22.04 kHz because their samples
   eventually land on the peak. Resampled sources are band-limited below 22.05 kHz by the
   resampler; native 44.1 kHz transients above ~21.2 kHz can under-read.

Tests, fixtures and their regeneration: `tests/cli.rs`, `tests/fixtures/make.sh` (generated tones only).
