//! Development aid: write the resampler FIR for RATE (coefficients f64le) and the
//! resampled output of a deterministic test signal, for external reconstruction.
//! usage: fir_dump RATE OUTDIR
fn main() {
    let a: Vec<String> = std::env::args().collect();
    let rate: u32 = a[1].parse().unwrap();
    let out = std::path::Path::new(&a[2]);
    let f = ingest::dsp::Fir::design(rate).expect("memory");
    let mut b = Vec::new();
    for v in &f.h { b.extend_from_slice(&v.to_le_bytes()); }
    std::fs::write(out.join(format!("h{rate}.f64")), b).unwrap();
    let n = rate as usize / 2;
    let x: Vec<f64> = (0..n).map(|i| 0.4 * libm::sin(i as f64 * 0.0137) + 0.2 * libm::sin(i as f64 * 1.1)).collect();
    let m = ingest::dsp::output_frames(n as u64, rate).unwrap();
    let y = ingest::dsp::resample(&x, rate, m).unwrap();
    let mut b = Vec::new();
    for v in &x { b.extend_from_slice(&v.to_le_bytes()); }
    std::fs::write(out.join(format!("x{rate}.f64")), b).unwrap();
    let mut b = Vec::new();
    for v in &y { b.extend_from_slice(&v.to_le_bytes()); }
    std::fs::write(out.join(format!("y{rate}.f64")), b).unwrap();
    println!("{rate} L={} M={} first={} len={}", f.l, f.m, f.first, f.h.len());
}
