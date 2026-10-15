# Vendored Symphonia 0.6.1 — INGEST-1 arithmetic profile patches

These four crates are copied unchanged from crates.io `0.6.1` (MPL-2.0; see each crate's
`LICENSE`) except for the edits below. They are wired in through `[patch.crates-io]` in
`host/ingest/Cargo.toml`.

1. **Deterministic transcendental math.** Every `sin`/`cos`/`tan`/`powf`/`pow` call in
   `symphonia-core` (`dsp/mdct.rs`, `dsp/fft/{mod,no_simd}.rs`), `symphonia-bundle-mp3`
   (`synthesis.rs`, `layer3/{hybrid_synthesis,requantize,stereo}.rs`) and
   `symphonia-codec-aac` (`aac/{window,codebooks}.rs`, `aac/ics/{mod,pulse,tns}.rs`) calls the
   pure-Rust `libm` crate (`=0.2.16`, default features off) instead of the platform C
   library. The platform libm differs between glibc, macOS and the Windows CRT; `libm` is
   the same IEEE-754 basic-operation sequence on every target, and Rust never contracts
   to FMA. `sqrt` stays on `std` because IEEE-754 requires it correctly rounded. The one `powi` (demuxer
   ReplayGain peak scale, unused by ingest) became the exact constant `8388608.0`.
2. **HE-AAC refusal.** `symphonia-codec-aac/src/aac/mod.rs`: an `ID_FIL` element carrying
   `EXT_SBR_DATA`/`EXT_SBR_DATA_CRC` returns `unsupported_error("aac: sbr extension present")`
   instead of silently decoding only the AAC-LC core (implicit HE-AAC/HE-AACv2 signalling).
3. Packaging: `Cargo.toml.orig`, `.cargo_vcs_info.json` and the crates' own `Cargo.lock`
   removed; `libm` added to the three crates' `[dependencies]`.

`tools/check_vendor.py` (run by CI) recomputes `PATCHES.sha256` and fails on any drift,
and fails if a vendored source calls a transcendental `std` float method.
4. **No MP3 concealment.** `symphonia-bundle-mp3/src/layer3/mod.rs`: a bit-reservoir underflow
   (`main_data_begin` naming bytes that were never decoded) returns
   `decode_error("mpa: main_data_begin underflow")` instead of concealing missing main data.
   `layer3/requantize.rs`: a `big_values` Huffman overrun returns
   `decode_error("mpa: big_values overrun")`. The benign, widely-tolerated `count1` overrun
   undo is unchanged.
