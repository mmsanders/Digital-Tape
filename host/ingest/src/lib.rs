//! Digital Tape INGEST-1 host ingest (docs/WP16-INGEST-CONTRACT.md). The binary in
//! `main.rs` is the only consumer; the library split exists for tests.

pub mod aac;
pub mod common;
pub mod convert;
pub mod dsp;
pub mod flac;
pub mod manifest;
pub mod mpeg;
pub mod order;
pub mod publish;
pub mod sniff;
pub mod wav;

pub mod libs {
    include!(concat!(env!("OUT_DIR"), "/libraries.rs"));
}

pub const TOOL_VERSION: &str = env!("CARGO_PKG_VERSION");
pub const PROFILE_ID: &str = "INGEST1-AP2";
pub const GAP_FRAMES: u64 = 88200;
