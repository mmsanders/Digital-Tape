//! Arithmetic profile INGEST1-AP2 (arithmetic unchanged from AP1): resampler, BS.1770-5 / Tech 3341 meter, true peak and
//! the issued TPDF quantizer (contract §3, §5).
//!
//! Every operation is scalar IEEE-754 binary64 (true-peak inner products binary32) in a
//! fixed order; transcendental functions come from the pure-Rust `libm` crate, never the
//! platform C library. Rust never contracts a*b+c into FMA, so the same source bytes give
//! the same bits on every target.

pub const OUT_RATE: u32 = 44100;

fn gcd(a: u64, b: u64) -> u64 {
    if b == 0 { a } else { gcd(b, a % b) }
}

/// Zeroth-order modified Bessel function, fixed 64-term series.
fn bessel_i0(x: f64) -> f64 {
    let q = x * x / 4.0;
    let mut term = 1.0;
    let mut sum = 1.0;
    for k in 1..64 {
        term *= q / ((k * k) as f64);
        sum += term;
    }
    sum
}

/// Kaiser-windowed sinc, `cut` = cutoff/sample-rate, `half` = half-width in samples.
fn kaiser_sinc(t: f64, cut: f64, half: f64, beta: f64, i0b: f64) -> f64 {
    if t.abs() >= half {
        return 0.0;
    }
    let r = t / half;
    let w = bessel_i0(beta * (1.0 - r * r).sqrt()) / i0b;
    let x = 2.0 * cut * t;
    let s = if x == 0.0 { 1.0 } else { libm::sin(core::f64::consts::PI * x) / (core::f64::consts::PI * x) };
    2.0 * cut * s * w
}

pub struct ResamplerProfile {
    pub l: u64,
    pub m: u64,
    pub cut: f64,  // cutoff / input rate
    pub half: f64, // half-width in input samples
    pub beta: f64,
}

pub const RS_ATTEN_DB: f64 = 100.0;
pub const RS_BETA: f64 = 0.1102 * (RS_ATTEN_DB - 8.7);

/// Design for one input rate. Downsampling: passband 18 kHz, stopband from 22.05 kHz.
/// Upsampling: passband 0.4·fin, stopband from fin/2 (image rejection).
pub fn profile(rate: u32) -> ResamplerProfile {
    let g = gcd(OUT_RATE as u64, rate as u64);
    let l = OUT_RATE as u64 / g;
    let m = rate as u64 / g;
    let fin = rate as f64;
    let (pass, stop) = if rate > OUT_RATE { (18000.0, 22050.0) } else { (0.4 * fin, 0.5 * fin) };
    let cut = (pass + stop) / 2.0 / fin;
    let dw = 2.0 * core::f64::consts::PI * (stop - pass) / fin;
    let taps = (RS_ATTEN_DB - 7.95) / (2.285 * dw);
    let half = libm::ceil(taps / 2.0) + 1.0;
    ResamplerProfile { l, m, cut, half, beta: RS_BETA }
}

/// Resample one channel to exactly `out_frames` frames at 44.1 kHz. Output frame k is
/// centred on input time k·fin/44100 (latency compensated); input is zero-extended
/// outside [0, N). 44.1 kHz input is the identity.
pub fn resample(x: &[f64], rate: u32, out_frames: u64) -> Vec<f64> {
    if rate == OUT_RATE {
        debug_assert_eq!(x.len() as u64, out_frames);
        return x.to_vec();
    }
    let p = profile(rate);
    let i0b = bessel_i0(p.beta);
    let j = p.half as i64; // taps j in [-J, J]
    let width = (2 * j + 1) as usize;
    // Phase table: phase q = (k*M) mod L, offset frac = q/L. Weight for input n0 + i - J
    // is h(frac - (i - J)). Each phase is normalised to unit DC gain.
    let mut table = vec![0.0f64; p.l as usize * width];
    for q in 0..p.l as usize {
        let frac = q as f64 / p.l as f64;
        let row = &mut table[q * width..(q + 1) * width];
        let mut sum = 0.0;
        for (i, w) in row.iter_mut().enumerate() {
            let t = frac - (i as i64 - j) as f64;
            *w = kaiser_sinc(t, p.cut, p.half, p.beta, i0b);
            sum += *w;
        }
        for w in row.iter_mut() {
            *w /= sum;
        }
    }
    let n = x.len() as i64;
    let mut y = Vec::with_capacity(out_frames as usize);
    for k in 0..out_frames {
        let pos = k as u128 * p.m as u128;
        let n0 = (pos / p.l as u128) as i64;
        let q = (pos % p.l as u128) as usize;
        let row = &table[q * width..(q + 1) * width];
        let base = n0 - j;
        let mut acc = 0.0;
        if base >= 0 && base + width as i64 <= n {
            let s = &x[base as usize..base as usize + width];
            for i in 0..width {
                acc += s[i] * row[i];
            }
        } else {
            for (i, w) in row.iter().enumerate() {
                let idx = base + i as i64;
                if idx >= 0 && idx < n {
                    acc += x[idx as usize] * w;
                }
            }
        }
        y.push(acc);
    }
    y
}

/// Contract §4 exact output count.
pub fn output_frames(n: u64, rate: u32) -> Option<u64> {
    let v = (n as u128).checked_mul(OUT_RATE as u128)?.checked_add((rate / 2) as u128)? / rate as u128;
    u64::try_from(v).ok()
}

// ---- BS.1770-5 loudness ---------------------------------------------------------------

struct Biquad {
    b: [f64; 3],
    a: [f64; 3],
}

fn k_weighting() -> (Biquad, Biquad) {
    let fs = OUT_RATE as f64;
    let pi = core::f64::consts::PI;
    // Stage 1: high-shelf (BS.1770 pre-filter) re-derived for 44.1 kHz.
    let f0 = 1681.974450955533;
    let g = 3.999843853973347;
    let q = 0.7071752369554196;
    let k = libm::tan(pi * f0 / fs);
    let vh = libm::pow(10.0, g / 20.0);
    let vb = libm::pow(vh, 0.4996667741545416);
    let a0 = 1.0 + k / q + k * k;
    let s1 = Biquad {
        b: [(vh + vb * k / q + k * k) / a0, 2.0 * (k * k - vh) / a0, (vh - vb * k / q + k * k) / a0],
        a: [1.0, 2.0 * (k * k - 1.0) / a0, (1.0 - k / q + k * k) / a0],
    };
    // Stage 2: RLB high-pass.
    let f0 = 38.13547087602444;
    let q = 0.5003270373238773;
    let k = libm::tan(pi * f0 / fs);
    let a0 = 1.0 + k / q + k * k;
    let s2 = Biquad { b: [1.0, -2.0, 1.0], a: [1.0, 2.0 * (k * k - 1.0) / a0, (1.0 - k / q + k * k) / a0] };
    (s1, s2)
}

struct State {
    x1: f64,
    x2: f64,
    y1: f64,
    y2: f64,
}

impl State {
    #[inline]
    fn step(&mut self, f: &Biquad, v: f64) -> f64 {
        let o = f.b[0] * v + f.b[1] * self.x1 + f.b[2] * self.x2 - f.a[1] * self.y1 - f.a[2] * self.y2;
        self.x2 = self.x1;
        self.x1 = v;
        self.y2 = self.y1;
        self.y1 = o;
        o
    }
}

pub const BLOCK: usize = 17640; // 400 ms
pub const HOP: usize = 4410; // 75 % overlap

#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Loud {
    Measured(f64),
    TooShort,
    GatedOut,
}

/// Integrated loudness of a 44.1 kHz stereo signal (EBU Tech 3341 gating). Incomplete
/// final blocks are discarded; nothing is padded.
pub fn loudness(ch: &[&[f64]]) -> Loud {
    let n = ch[0].len();
    if n < BLOCK {
        return Loud::TooShort;
    }
    let (s1, s2) = k_weighting();
    // Per-hop sums of squares, summed over channels (G = 1.0 for L and R).
    let hops = n / HOP;
    let mut e = vec![0.0f64; hops];
    for c in ch {
        let mut a = State { x1: 0.0, x2: 0.0, y1: 0.0, y2: 0.0 };
        let mut b = State { x1: 0.0, x2: 0.0, y1: 0.0, y2: 0.0 };
        for (h, slot) in e.iter_mut().enumerate() {
            let mut s = 0.0;
            for &v in &c[h * HOP..(h + 1) * HOP] {
                let y = b.step(&s2, a.step(&s1, v));
                s += y * y;
            }
            *slot += s;
        }
    }
    let blocks = (n - BLOCK) / HOP + 1;
    let z: Vec<f64> = (0..blocks).map(|j| (e[j] + e[j + 1] + e[j + 2] + e[j + 3]) / BLOCK as f64).collect();
    let lk = |z: f64| -0.691 + 10.0 * libm::log10(z);
    let abs: Vec<f64> = z.iter().copied().filter(|&z| z > 0.0 && lk(z) > -70.0).collect();
    if abs.is_empty() {
        return Loud::GatedOut;
    }
    let mean = abs.iter().sum::<f64>() / abs.len() as f64;
    let rel = lk(mean) - 10.0;
    let gated: Vec<f64> = abs.into_iter().filter(|&z| lk(z) > rel).collect();
    if gated.is_empty() {
        return Loud::GatedOut;
    }
    Loud::Measured(lk(gated.iter().sum::<f64>() / gated.len() as f64))
}

// ---- True peak --------------------------------------------------------------------------

/// Polyphase interpolator: `TP_PHASES` sub-sample positions per input sample, Kaiser sinc
/// cut at 22.05 kHz with transition 21.0–23.1 kHz, 80 dB. The 4x grid (every 64th phase)
/// is evaluated everywhere; each grid local maximum of |x| at or above 0.92 of the grid
/// maximum is refined over the neighbouring grid intervals at the full phase resolution.
pub const TP_PHASES: usize = 256;
pub const TP_GRID: usize = 64; // 4x grid
const TP_HALF: usize = 54; // taps each side

pub struct TruePeak {
    taps: Vec<f32>, // [phase][2*TP_HALF]
    grid: Vec<f32>, // [tap][4 grid phases]
}

impl TruePeak {
    pub fn new() -> TruePeak {
        let w = 2 * TP_HALF;
        let beta = 0.1102 * (80.0 - 8.7);
        let i0b = bessel_i0(beta);
        let cut = 0.5;
        let half = TP_HALF as f64;
        let mut taps = vec![0.0f32; TP_PHASES * w];
        for q in 0..TP_PHASES {
            let frac = q as f64 / TP_PHASES as f64;
            for i in 0..w {
                // input n0 + i - (TP_HALF - 1), time frac relative to n0
                let t = frac - (i as f64 - (TP_HALF as f64 - 1.0));
                taps[q * w + i] = kaiser_sinc(t, cut, half, beta, i0b) as f32;
            }
        }
        let per = TP_PHASES / TP_GRID;
        let mut grid = vec![0.0f32; w * per];
        for i in 0..w {
            for p in 0..per {
                grid[i * per + p] = taps[p * TP_GRID * w + i];
            }
        }
        TruePeak { taps, grid }
    }

    #[inline]
    fn at(&self, x: &[f32], n0: i64, q: usize) -> f32 {
        let w = 2 * TP_HALF;
        let row = &self.taps[q * w..(q + 1) * w];
        let base = n0 - (TP_HALF as i64 - 1);
        let n = x.len() as i64;
        let mut acc = 0.0f32;
        if base >= 0 && base + w as i64 <= n {
            let s = &x[base as usize..base as usize + w];
            for i in 0..w {
                acc += s[i] * row[i];
            }
        } else {
            for (i, c) in row.iter().enumerate() {
                let idx = base + i as i64;
                if idx >= 0 && idx < n {
                    acc += x[idx as usize] * c;
                }
            }
        }
        acc
    }

    /// The four 4x-grid values after input sample n0. Each lane sums in the same tap
    /// order as `at`, so the result equals four `at` calls bit for bit.
    #[inline]
    fn grid4(&self, x: &[f32], n0: i64) -> [f32; 4] {
        let w = 2 * TP_HALF;
        let base = n0 - (TP_HALF as i64 - 1);
        let n = x.len() as i64;
        let mut acc = [0.0f32; 4];
        if base >= 0 && base + w as i64 <= n {
            let s = &x[base as usize..base as usize + w];
            for (i, &v) in s.iter().enumerate() {
                let c = &self.grid[i * 4..i * 4 + 4];
                acc[0] += v * c[0];
                acc[1] += v * c[1];
                acc[2] += v * c[2];
                acc[3] += v * c[3];
            }
        } else {
            for i in 0..w {
                let idx = base + i as i64;
                if idx >= 0 && idx < n {
                    let v = x[idx as usize];
                    let c = &self.grid[i * 4..i * 4 + 4];
                    acc[0] += v * c[0];
                    acc[1] += v * c[1];
                    acc[2] += v * c[2];
                    acc[3] += v * c[3];
                }
            }
        }
        [acc[0].abs(), acc[1].abs(), acc[2].abs(), acc[3].abs()]
    }

    /// Maximum absolute reconstructed value over input positions [lo, hi) (positions may
    /// run past the signal; outside samples are zero). One streaming pass over the 4x
    /// grid; a grid local maximum at or above 0.92 of the running grid maximum is refined
    /// across its two neighbouring grid intervals at full phase resolution. The running
    /// maximum never exceeds the final one, so this refines a superset of the points a
    /// final-maximum threshold would.
    pub fn peak_range(&self, x: &[f32], lo: i64, hi: i64) -> f32 {
        if hi <= lo {
            return 0.0;
        }
        let per = (TP_PHASES / TP_GRID) as i64;
        let mut cur = self.grid4(x, lo - 1);
        let mut prev = cur[3];
        cur = self.grid4(x, lo);
        let mut gmax = 0.0f32;
        let mut best = 0.0f32;
        for n0 in lo..hi {
            let nxt = self.grid4(x, n0 + 1);
            for p in 0..4 {
                let v = cur[p];
                let next = if p < 3 { cur[p + 1] } else { nxt[0] };
                gmax = gmax.max(v);
                best = best.max(v);
                if v > 0.0 && v >= gmax * 0.92 && v >= prev && v >= next {
                    let centre = (n0 * per + p as i64) * TP_GRID as i64;
                    for s in -(TP_GRID as i64) + 1..TP_GRID as i64 {
                        let pos = centre + s;
                        let m0 = pos.div_euclid(TP_PHASES as i64);
                        let q = pos.rem_euclid(TP_PHASES as i64) as usize;
                        best = best.max(self.at(x, m0, q).abs());
                    }
                }
                prev = v;
            }
            cur = nxt;
        }
        best
    }

    /// Whole-signal true peak (with half a filter of zero extension each side).
    pub fn peak(&self, x: &[f32]) -> f32 {
        self.peak_range(x, -(TP_HALF as i64), x.len() as i64 + TP_HALF as i64)
    }
}

pub fn dbfs(v: f64) -> f64 {
    20.0 * libm::log10(v)
}

// ---- Quantizer ----------------------------------------------------------------------------

pub const DITHER_SEED: u32 = 0x6D2B79F5;

pub struct Xorshift(u32);
impl Xorshift {
    pub fn new() -> Self {
        Xorshift(DITHER_SEED)
    }
    #[inline]
    pub fn draw(&mut self) -> f64 {
        let mut s = self.0;
        s ^= s << 13;
        s ^= s >> 17;
        s ^= s << 5;
        self.0 = s;
        (s as f64 + 0.5) / 4294967296.0
    }
}

/// Quantize one source with constant linear gain `g`. Mono (`r` None) uses one dither pair
/// per frame and duplicates the sample. Returns interleaved stereo, or None on overflow.
pub fn quantize(l: &[f64], r: Option<&[f64]>, g: f64) -> Option<Vec<i16>> {
    let mut rng = Xorshift::new();
    let mut out = Vec::with_capacity(l.len() * 2);
    let q = |x: f64, rng: &mut Xorshift| -> Option<i16> {
        let u1 = rng.draw();
        let u2 = rng.draw();
        let v = (32768.0 * (x * g) + u1 - u2).round_ties_even();
        if (-32768.0..=32767.0).contains(&v) { Some(v as i16) } else { None }
    };
    match r {
        None => {
            for &x in l {
                let s = q(x, &mut rng)?;
                out.push(s);
                out.push(s);
            }
        }
        Some(r) => {
            for (&a, &b) in l.iter().zip(r) {
                out.push(q(a, &mut rng)?);
                out.push(q(b, &mut rng)?);
            }
        }
    }
    Some(out)
}

/// One channel of interleaved 16-bit PCM as binary32 at full scale 32768.
pub fn channel_f32(pcm: &[i16], c: usize) -> Vec<f32> {
    pcm.iter().skip(c).step_by(2).map(|&v| v as f32 / 32768.0).collect()
}

/// Split interleaved 16-bit PCM into float planes at full scale 32768.
pub fn planes_from_pcm(pcm: &[i16]) -> (Vec<f64>, Vec<f64>) {
    let l = pcm.iter().step_by(2).map(|&v| v as f64 / 32768.0).collect();
    let r = pcm.iter().skip(1).step_by(2).map(|&v| v as f64 / 32768.0).collect();
    (l, r)
}

pub fn to_f32(x: &[f64]) -> Vec<f32> {
    x.iter().map(|&v| v as f32).collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn counts() {
        assert_eq!(output_frames(48000, 48000), Some(44100));
        assert_eq!(output_frames(1, 192000), Some(0));
        assert_eq!(output_frames(3, 192000), Some(1)); // 132300+96000 / 192000 = 1.19
        assert_eq!(output_frames(2, 192000), Some(0)); // (88200+96000)/192000 = 0.959
    }

    #[test]
    fn xorshift_first_draws() {
        // Hand-computed from the issued recurrence and seed 0x6D2B79F5.
        let mut x = Xorshift::new();
        for s in [0x40aec71fu32, 0x91e00c19, 0x9c0fe128] {
            assert_eq!(x.draw(), (s as f64 + 0.5) / 4294967296.0);
        }
    }

    #[test]
    fn eb_tech3341_1khz_stereo() {
        // 1 kHz sine at -23 dBFS in both channels for 20 s reads -23.0 LUFS (±0.1).
        let n = 44100 * 20;
        let a = libm::pow(10.0, -23.0 / 20.0);
        let x: Vec<f64> = (0..n)
            .map(|i| a * libm::sin(2.0 * core::f64::consts::PI * 1000.0 * i as f64 / 44100.0))
            .collect();
        match loudness(&[&x, &x]) {
            Loud::Measured(l) => assert!((l + 23.0).abs() < 0.1, "{l}"),
            o => panic!("{o:?}"),
        }
    }

    #[test]
    fn true_peak_tones() {
        let tp = TruePeak::new();
        for &f in &[997.0, 5512.5, 11025.0, 15000.0, 19000.0, 20000.0] {
            for &ph in &[0.0, 0.3, 0.785, 1.2] {
                let x: Vec<f32> = (0..44100)
                    .map(|i| (0.5 * libm::sin(2.0 * core::f64::consts::PI * f * i as f64 / 44100.0 + ph)) as f32)
                    .collect();
                let p = tp.peak_range(&x, 1000, 43000) as f64;
                let db = dbfs(p / 0.5);
                assert!(db > -0.1 && db < 0.1, "f={f} ph={ph} {db}");
            }
        }
    }

    #[test]
    fn resampler_tone_passband() {
        for &rate in &[8000u32, 22050, 32000, 48000, 96000, 192000] {
            let f = if rate < 44100 { 0.3 * rate as f64 } else { 15000.0 };
            let n = rate as usize * 2;
            let x: Vec<f64> = (0..n).map(|i| libm::sin(2.0 * core::f64::consts::PI * f * i as f64 / rate as f64)).collect();
            let m = output_frames(n as u64, rate).unwrap();
            let y = resample(&x, rate, m);
            let mid = &y[y.len() / 4..3 * y.len() / 4];
            let pk = mid.iter().fold(0.0f64, |a, &b| a.max(b.abs()));
            assert!(dbfs(pk).abs() < 0.1, "rate {rate}: {}", dbfs(pk));
        }
    }
}
