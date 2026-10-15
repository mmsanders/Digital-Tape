//! Development aid: worst true-peak under-read of the INGEST1-AP2 meter for steady 44.1 kHz
//! sinusoids over a grid of frequencies and phases.
fn main() {
    let tp = ingest::dsp::TruePeak::new();
    for f in [20000.0, 21800.0, 21900.0, 21950.0, 22000.0, 22020.0, 22040.0] {
        let mut worst: f64 = 0.0;
        for k in 0..32 {
            let ph = k as f64 * std::f64::consts::PI / 32.0;
            let x: Vec<f32> = (0..8192).map(|i| (0.5 * libm::sin(2.0 * std::f64::consts::PI * f * i as f64 / 44100.0 + ph)) as f32).collect();
            let p = tp.peak_range(&x, 1000, 7000) as f64;
            worst = worst.min(20.0 * libm::log10(p / 0.5));
        }
        println!("{f:>8} Hz worst {worst:+.4} dB");
    }
}
