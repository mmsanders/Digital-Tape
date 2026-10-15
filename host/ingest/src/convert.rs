//! One source converted alone (contract §3): trim → mono/stereo → resample → measure →
//! one constant gain → TPDF quantize → remeasure.

use crate::common::*;
use crate::dsp::{self, Loud, TruePeak};

pub struct Converted {
    pub pcm: Vec<i16>, // interleaved stereo, exactly output_frames frames
    pub input_lufs: Option<f64>,
    pub input_dbtp: Option<f64>,
    pub output_lufs: Option<f64>,
    pub output_dbtp: Option<f64>,
    pub target_gain_db: f64,
    pub applied_gain_db: f64,
    pub peak_limited: bool,
    pub status: &'static str,
    pub reason: Option<&'static str>,
}

pub const TARGET_LUFS: f64 = -16.0;
pub const CEILING_DBTP: f64 = -1.0;
pub const GUARD_DB: f64 = 0.1;
pub const MAX_ATTEMPTS: usize = 32;

fn reason(l: Loud) -> Option<&'static str> {
    match l {
        Loud::Measured(_) => None,
        Loud::TooShort => Some("too_short"),
        Loud::GatedOut => Some("gated_out"),
    }
}

/// True peak of an interleaved 16-bit stereo buffer, in dBTP (None for all-zero).
pub fn pcm_peak(tp: &TruePeak, pcm: &[i16], mono: bool) -> f64 {
    let pl = tp.peak(&dsp::channel_f32(pcm, 0));
    let p = if mono { pl } else { pl.max(tp.peak(&dsp::channel_f32(pcm, 1))) };
    dsp::dbfs(p as f64)
}

pub fn is_silent(d: &Decoded) -> bool {
    let h = d.trim.head as usize;
    let e = h + d.effective_frames() as usize;
    d.planes.iter().all(|p| p[h..e].iter().all(|&v| v == 0.0))
}

pub fn convert(d: &Decoded, out_frames: u64, tp: &TruePeak) -> Res<Converted> {
    let h = d.trim.head as usize;
    let e = h + d.effective_frames() as usize;
    if is_silent(d) {
        return Ok(Converted {
            pcm: vec![0i16; out_frames as usize * 2],
            input_lufs: None,
            input_dbtp: None,
            output_lufs: None,
            output_dbtp: None,
            target_gain_db: 0.0,
            applied_gain_db: 0.0,
            peak_limited: false,
            status: "digital_silence",
            reason: None,
        });
    }
    let mono = d.channels == 1;
    let l = dsp::resample(&d.planes[0][h..e], d.rate, out_frames);
    let r = if mono { None } else { Some(dsp::resample(&d.planes[1][h..e], d.rate, out_frames)) };
    let rr: &[f64] = r.as_deref().unwrap_or(&l);
    let lin = dsp::loudness(&[&l, rr]);
    let pk = {
        let pl = tp.peak(&dsp::to_f32(&l));
        if mono { pl } else { pl.max(tp.peak(&dsp::to_f32(rr))) }
    };
    if !(pk > 0.0) {
        return refuse("no valid true-peak measurement for a source that is not digital silence");
    }
    let p_in = dsp::dbfs(pk as f64);
    let peak_bound = CEILING_DBTP - p_in - GUARD_DB;
    let (target, mut g, mut limited) = match lin {
        Loud::Measured(li) => {
            let t = TARGET_LUFS - li;
            (t, t.min(peak_bound), peak_bound < t)
        }
        _ => (0.0, peak_bound.min(0.0), peak_bound < 0.0),
    };
    for _ in 0..MAX_ATTEMPTS {
        let lin_gain = libm::pow(10.0, g / 20.0);
        let Some(pcm) = dsp::quantize(&l, r.as_deref(), lin_gain) else {
            return refuse("16-bit quantization would overflow");
        };
        let p_out = pcm_peak(tp, &pcm, mono);
        if p_out + GUARD_DB > CEILING_DBTP {
            g -= p_out + GUARD_DB - CEILING_DBTP + 0.001;
            limited = true;
            continue;
        }
        let (ql, qr) = dsp::planes_from_pcm(&pcm);
        let lout = dsp::loudness(&[&ql, &qr]);
        if let (Loud::Measured(_), Loud::Measured(lo)) = (lin, lout) {
            if !limited && (lo - TARGET_LUFS).abs() > 0.5 {
                let ng = g + (TARGET_LUFS - lo);
                if ng > peak_bound {
                    g = peak_bound;
                    limited = true;
                } else {
                    g = ng;
                }
                continue;
            }
        }
        let (status, why) = match (lin, lout) {
            (Loud::Measured(_), Loud::Measured(_)) => ("measured", None),
            (Loud::Measured(_), other) => ("unmeasurable", reason(other)),
            (other, _) => ("unmeasurable", reason(other)),
        };
        return Ok(Converted {
            pcm,
            input_lufs: if let Loud::Measured(v) = lin { Some(v) } else { None },
            input_dbtp: Some(p_in),
            output_lufs: if let (Loud::Measured(v), "measured") = (lout, status) { Some(v) } else { None },
            output_dbtp: Some(p_out),
            target_gain_db: target,
            applied_gain_db: g,
            peak_limited: limited,
            status,
            reason: why,
        });
    }
    Err(Fail::Io(format!("gain refinement did not converge in {MAX_ATTEMPTS} attempts")))
}
