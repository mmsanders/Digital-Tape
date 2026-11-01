//! Writes the INGEST-1 Stage1 `profile_file` for this exact library: every resampler as
//! a generic FIR descriptor (coefficients as little-endian f64 with SHA-256 and
//! `first_highrate_index`), plus the meter, dither and gain-refinement declarations.
//! The coefficients are the runtime prototype itself (`dsp::Fir::design`), not a copy.
//!
//! cargo run --release --example profile_file -- OUTDIR
use sha2::{Digest, Sha256};
use std::fs;
use std::path::Path;

fn hex(b: &[u8]) -> String {
    Sha256::digest(b).iter().map(|x| format!("{x:02x}")).collect()
}

fn main() {
    let out = std::env::args().nth(1).expect("OUTDIR");
    let out = Path::new(&out);
    fs::create_dir_all(out.join("coefficients")).unwrap();
    let mut rates = String::new();
    for (i, &rate) in ingest::common::RATES.iter().filter(|&&r| r != 44100).enumerate() {
        let f = ingest::dsp::Fir::design(rate).expect("memory");
        let mut b = Vec::with_capacity(f.h.len() * 8);
        for v in &f.h {
            b.extend_from_slice(&v.to_le_bytes());
        }
        let name = format!("coefficients/h{rate}.f64");
        fs::write(out.join(&name), &b).unwrap();
        if i > 0 {
            rates.push(',');
        }
        rates.push_str(&format!(
            "\"{rate}\":{{\"coefficients_file\":\"profile/{name}\",\"coefficients_sha256\":\"{}\",\"down\":{},\"first_highrate_index\":{},\"kind\":\"fir\",\"taps\":{},\"up\":{}}}",
            hex(&b), f.m, f.first, f.h.len(), f.l
        ));
    }
    let esc = |s: &str| s.replace('\\', "\\\\").replace('"', "\\\"");
    let json = format!(
        "{{\"dither\":\"{}\",\"gain_refinement\":\"start min(-16-L,-1-P-0.1) dB (unmeasurable: min(0,-1-P-0.1)); quantize; if final true peak +0.1 > -1 dBTP reduce by the excess +0.001 dB and mark peak_limited; else if unlimited and |final L +16| > 0.5 LU move by -16-L capped at the peak bound; at most 32 attempts, dither reset each attempt; gain applied as 10^(g/20) (libm pow), binary64\",\"identity_44100\":\"44100 Hz input is copied unchanged (no filter)\",\"meter\":\"{}\",\"profile\":\"{}\",\"resampler\":\"{}\",\"resamplers\":{{{rates}}},\"tool_version\":\"{}\"}}\n",
        esc(ingest::DITHER_PROFILE),
        esc(ingest::METER_PROFILE),
        ingest::PROFILE_ID,
        esc(ingest::RESAMPLER_PROFILE),
        ingest::TOOL_VERSION
    );
    fs::write(out.join("profile.json"), json).unwrap();
    println!("{}", out.join("profile.json").display());
}
