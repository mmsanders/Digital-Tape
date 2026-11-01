//! Writes the deterministic cross-platform identity corpus: generated tones (contract I8)
//! at every admitted rate, mono and stereo, integer and float PCM, as WAV and AIFF.
//! Samples are computed with `libm`, so the corpus bytes are identical on every target.
//!
//! cargo run --release --example make_corpus -- DIR
use std::fs;
use std::path::Path;

const RATES: [u32; 15] = [7350, 8000, 11025, 12000, 16000, 22050, 24000, 32000, 44100, 48000, 64000, 88200, 96000, 176400, 192000];

fn sample(i: usize, rate: u32, c: usize) -> f64 {
    let t = i as f64 / rate as f64;
    let f = 220.0 * (1.0 + c as f64 * 0.5);
    0.25 * libm::sin(2.0 * core::f64::consts::PI * f * t) + 0.05 * libm::sin(2.0 * core::f64::consts::PI * 3150.0 * t)
}

fn wav(path: &Path, rate: u32, ch: u16, bits: u16, float: bool, frames: usize) {
    let mut d = Vec::new();
    for i in 0..frames {
        for c in 0..ch as usize {
            let v = sample(i, rate, c);
            match (bits, float) {
                (16, false) => d.extend_from_slice(&(libm::round(v * 32767.0) as i16).to_le_bytes()),
                (24, false) => d.extend_from_slice(&(libm::round(v * 8388607.0) as i32).to_le_bytes()[..3]),
                (32, true) => d.extend_from_slice(&(v as f32).to_le_bytes()),
                _ => unreachable!(),
            }
        }
    }
    let align = ch * bits / 8;
    let mut b = Vec::new();
    b.extend_from_slice(b"RIFF");
    b.extend_from_slice(&((36 + d.len()) as u32).to_le_bytes());
    b.extend_from_slice(b"WAVEfmt ");
    b.extend_from_slice(&16u32.to_le_bytes());
    b.extend_from_slice(&(if float { 3u16 } else { 1u16 }).to_le_bytes());
    b.extend_from_slice(&ch.to_le_bytes());
    b.extend_from_slice(&rate.to_le_bytes());
    b.extend_from_slice(&(rate * align as u32).to_le_bytes());
    b.extend_from_slice(&align.to_le_bytes());
    b.extend_from_slice(&bits.to_le_bytes());
    b.extend_from_slice(b"data");
    b.extend_from_slice(&(d.len() as u32).to_le_bytes());
    b.extend_from_slice(&d);
    fs::write(path, b).unwrap();
}

fn main() {
    let dir = std::env::args().nth(1).expect("DIR");
    let a = Path::new(&dir).join("rates");
    let b = Path::new(&dir).join("depths");
    fs::create_dir_all(&a).unwrap();
    fs::create_dir_all(&b).unwrap();
    for (k, &r) in RATES.iter().enumerate() {
        let ch = if k % 2 == 0 { 2 } else { 1 };
        wav(&a.join(format!("{k:02} {r}.wav")), r, ch, 16, false, (r as usize * 3) / 4);
    }
    wav(&b.join("a 24bit.wav"), 48000, 2, 24, false, 36000);
    wav(&b.join("b float.wav"), 96000, 2, 32, true, 72000);
}
