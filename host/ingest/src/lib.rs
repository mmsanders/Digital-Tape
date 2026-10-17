//! Digital Tape INGEST-1 host ingest (docs/WP16-INGEST-CONTRACT.md). The binary in
//! `main.rs` is the only consumer; the library split exists for tests.

pub mod aac;
pub mod common;
pub mod convert;
pub mod dsp;
pub mod flac;
pub mod manifest;
pub mod mpeg;
pub mod observe;
pub mod order;
pub mod publish;
pub mod sniff;
pub mod wav;

pub mod libs {
    include!(concat!(env!("OUT_DIR"), "/libraries.rs"));
}

pub const TOOL_VERSION: &str = env!("CARGO_PKG_VERSION");
pub const PROFILE_ID: &str = "INGEST1-AP4";
pub const GAP_FRAMES: u64 = 88200;

pub const RESAMPLER_PROFILE: &str = "kaiser-windowed-sinc polyphase, exact L/M ratio to 44100 Hz; \
Kaiser 100 dB (beta 0.1102*(100-8.7)); downsampling pass 18000 Hz / stop 22050 Hz; upsampling \
pass 0.4*fin / stop 0.5*fin; cutoff at the band centre; length (100-7.95)/(2.285*dw) taps; \
one prototype h at L*fin (no per-phase renormalisation), declared as an FIR with first_highrate_index; output k centred on input time k*fin/44100; zero \
extension outside the source; 44100 Hz input is the identity; binary64 scalar, fixed order";
pub const METER_PROFILE: &str = "ITU-R BS.1770-5 K-weighting re-derived for 44100 Hz (libebur128 \
analogue prototype); EBU Tech 3341 V4 gating: 400 ms blocks (17640), 75% overlap (4410), \
absolute -70 LKFS, relative -10 LU, incomplete final block discarded; true peak: Kaiser \
beta 14 windowed sinc cut at 22050 Hz, 512 taps (256 each side), 256 phases, 4x grid with every grid local \
maximum >= 0.90 of the running grid maximum refined at 256x; binary32 inner products";
pub const DITHER_PROFILE: &str = "TPDF; xorshift32 (13,17,5) reset to 0x6D2B79F5 per source and per \
gain attempt; u=(s+0.5)/2^32; round_ties_even(32768*x*g+u1-u2); stereo draw order L(u1,u2) \
R(u1,u2); mono one pair per frame, duplicated; no noise shaping or saturation; digital \
silence and gaps bypass";

