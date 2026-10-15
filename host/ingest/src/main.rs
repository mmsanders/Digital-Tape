//! `ingest` — Digital Tape INGEST-1 (docs/WP16-INGEST-CONTRACT.md).
//!
//! ingest --out DEST --length SECONDS FOLDER [FOLDER ...]
//! ingest --version

use ingest::{common, convert, dsp, libs, manifest, order, publish, sniff};

use common::*;
use ingest::{GAP_FRAMES, PROFILE_ID, TOOL_VERSION};
use manifest::J;
use sha2::{Digest, Sha256};
use std::ffi::OsString;
use std::fs;
use std::path::PathBuf;


const RESAMPLER_PROFILE: &str = "kaiser-windowed-sinc polyphase, exact L/M ratio to 44100 Hz; \
Kaiser 100 dB (beta 0.1102*(100-8.7)); downsampling pass 18000 Hz / stop 22050 Hz; upsampling \
pass 0.4*fin / stop 0.5*fin; cutoff at the band centre; length (100-7.95)/(2.285*dw) taps; \
each phase normalised to unit DC gain; output k centred on input time k*fin/44100; zero \
extension outside the source; 44100 Hz input is the identity; binary64 scalar, fixed order";
const METER_PROFILE: &str = "ITU-R BS.1770-5 K-weighting re-derived for 44100 Hz (libebur128 \
analogue prototype); EBU Tech 3341 V4 gating: 400 ms blocks (17640), 75% overlap (4410), \
absolute -70 LKFS, relative -10 LU, incomplete final block discarded; true peak: Kaiser \
80 dB windowed sinc cut at 22050 Hz, 108 taps, 256 phases, 4x grid with every grid local \
maximum >= 0.92 of the grid maximum refined at 256x; binary32 inner products";
const DITHER_PROFILE: &str = "TPDF; xorshift32 (13,17,5) reset to 0x6D2B79F5 per source and per \
gain attempt; u=(s+0.5)/2^32; round_ties_even(32768*x*g+u1-u2); stereo draw order L(u1,u2) \
R(u1,u2); mono one pair per frame, duplicated; no noise shaping or saturation; digital \
silence and gaps bypass";

const USAGE: &str = "usage: ingest --out DEST --length SECONDS FOLDER [FOLDER ...]\n       ingest --version\n\n\
Turns explicitly ordered folders of audio into DEST/audio.wav (44.1 kHz, 16-bit, stereo) and\n\
DEST/manifest.json. SECONDS is the cartridge label length. DEST must not exist.\n";

struct Args {
    out: PathBuf,
    seconds: u64,
    folders: Vec<PathBuf>,
}

enum Cmd {
    Run(Args),
    Version,
    Help,
}

fn parse(argv: Vec<OsString>) -> Result<Cmd, String> {
    let mut out: Option<PathBuf> = None;
    let mut len: Option<u64> = None;
    let mut folders = Vec::new();
    let mut it = argv.into_iter();
    let mut only_paths = false;
    while let Some(a) = it.next() {
        if only_paths {
            folders.push(PathBuf::from(a));
            continue;
        }
        match a.to_str() {
            Some("--help") | Some("-h") => return Ok(Cmd::Help),
            Some("--version") => return Ok(Cmd::Version),
            Some("--") => only_paths = true,
            Some("--out") => {
                let v = it.next().ok_or("--out needs a destination")?;
                if out.replace(PathBuf::from(v)).is_some() {
                    return Err("--out given twice".into());
                }
            }
            Some("--length") => {
                let v = it.next().ok_or("--length needs SECONDS")?;
                let s = v.to_str().ok_or("--length must be a positive whole number of seconds")?;
                if s.is_empty() || !s.bytes().all(|c| c.is_ascii_digit()) {
                    return Err("--length must be a positive whole number of seconds".into());
                }
                let n: u64 = s.parse().map_err(|_| "--length is too large")?;
                if n == 0 {
                    return Err("--length must be a positive whole number of seconds".into());
                }
                if len.replace(n).is_some() {
                    return Err("--length given twice".into());
                }
            }
            Some(s) if s.starts_with('-') && s.len() > 1 => return Err(format!("unknown option {s}")),
            _ => folders.push(PathBuf::from(a)),
        }
    }
    let out = out.ok_or("--out DEST is required")?;
    let seconds = len.ok_or("--length SECONDS is required")?;
    if folders.is_empty() {
        return Err("at least one FOLDER is required".into());
    }
    Ok(Cmd::Run(Args { out, seconds, folders }))
}

fn mmss(secs: u64) -> String {
    format!("{}:{:02}", secs / 60, secs % 60)
}

fn sha256_hex(parts: &[&[u8]]) -> String {
    let mut h = Sha256::new();
    for p in parts {
        h.update(p);
    }
    h.finalize().iter().map(|b| format!("{b:02x}")).collect()
}

struct Source {
    logical: String,
    path: PathBuf,
    folder: usize,
    sha: String,
    container: &'static str,
    codec: &'static str,
    codec_profile: String,
    rate: u32,
    channels: u32,
    raw: u64,
    trim: Trim,
    effective: u64,
    out_frames: u64,
    start: u64,
    conv: Option<convert::Converted>,
    pcm: Vec<u8>,
}

fn read(p: &std::path::Path, logical: &str) -> Res<Vec<u8>> {
    fs::read(p).map_err(|e| Fail::Io(format!("{logical}: cannot read: {e}")))
}

fn named(logical: &str, r: Res<Decoded>) -> Res<Decoded> {
    r.map_err(|f| match f {
        Fail::Refuse(m) => Fail::Refuse(format!("{logical}: {m}")),
        Fail::Io(m) => Fail::Io(format!("{logical}: {m}")),
    })
}

/// Segments of the joined output, for boundary true-peak checks.
enum Seg<'a> {
    Src(&'a Source),
    Gap,
}

fn run(a: Args) -> Res<String> {
    publish::check_dest(&a.out)?;
    let capacity = a
        .seconds
        .checked_mul(dsp::OUT_RATE as u64)
        .ok_or_else(|| Fail::Refuse("--length is too large".into()))?;

    // Folders: distinct, listed, validated and ordered before anything is decoded.
    let mut ids: Vec<(String, usize)> = Vec::new();
    let mut sources: Vec<Source> = Vec::new();
    let mut counts = Vec::new();
    for (i, f) in a.folders.iter().enumerate() {
        let id = order::identity(f)?;
        if let Some((_, j)) = ids.iter().find(|x| x.0 == id) {
            return Err(Fail::Refuse(format!(
                "{}: folder {i} is the same folder as folder {j}; folders must be distinct",
                f.display()
            )));
        }
        ids.push((id, i));
        let list = order::list_folder(f, i)?;
        counts.push(list.len() as u64);
        for e in list {
            sources.push(Source {
                logical: e.logical,
                path: e.path,
                folder: i,
                sha: String::new(),
                container: "",
                codec: "",
                codec_profile: String::new(),
                rate: 0,
                channels: 0,
                raw: 0,
                trim: Trim::unknown(),
                effective: 0,
                out_frames: 0,
                start: 0,
                conv: None,
                pcm: Vec::new(),
            });
        }
    }

    // Pass 1: decode, validate and count every source exactly.
    for s in sources.iter_mut() {
        let bytes = read(&s.path, &s.logical)?;
        s.sha = sha256_hex(&[&bytes]);
        let d = named(&s.logical, sniff::decode(&bytes))?;
        s.container = d.container;
        s.codec = d.codec;
        s.codec_profile = d.codec_profile.clone();
        s.rate = d.rate;
        s.channels = d.channels;
        s.raw = d.raw_frames;
        s.trim = d.trim.clone();
        s.effective = d.effective_frames();
        s.out_frames = dsp::output_frames(s.effective, d.rate)
            .ok_or_else(|| Fail::Refuse(format!("{}: frame count overflows", s.logical)))?;
        if s.out_frames == 0 {
            return Err(Fail::Refuse(format!(
                "{}: too short to produce one 44.1 kHz frame ({} frames at {} Hz); the whole request is refused",
                s.logical, s.effective, s.rate
            )));
        }
    }

    // Exact capacity, gaps included.
    let mut total: u64 = 0;
    let mut prev_folder = None;
    for s in sources.iter_mut() {
        if prev_folder.is_some() && prev_folder != Some(s.folder) {
            total = total.checked_add(GAP_FRAMES).ok_or_else(|| Fail::Refuse("total length overflows".into()))?;
        }
        prev_folder = Some(s.folder);
        s.start = total;
        total = total.checked_add(s.out_frames).ok_or_else(|| Fail::Refuse("total length overflows".into()))?;
    }
    if total > capacity {
        let e = total - capacity;
        return Err(Fail::Refuse(format!(
            "the sources and folder gaps total {} ({} frames), over the {} label by {} frames (rounded up {}); nothing was written",
            mmss(total.div_ceil(44100)),
            total,
            mmss(a.seconds),
            e,
            mmss(e.div_ceil(44100))
        )));
    }
    let data_len = total.checked_mul(4).filter(|&d| d + 36 <= u32::MAX as u64);
    let Some(data_len) = data_len else {
        return Err(Fail::Refuse("the output would exceed the canonical RIFF size limit (4 GiB)".into()));
    };

    // Pass 2: re-decode bound to the same bytes, convert each source alone.
    let tp = dsp::TruePeak::new();
    for s in sources.iter_mut() {
        let bytes = read(&s.path, &s.logical)?;
        if sha256_hex(&[&bytes]) != s.sha {
            return Err(Fail::Refuse(format!("{}: the file changed while ingest was running", s.logical)));
        }
        let d = named(&s.logical, sniff::decode(&bytes))?;
        drop(bytes);
        let c = convert::convert(&d, s.out_frames, &tp).map_err(|f| match f {
            Fail::Refuse(m) => Fail::Refuse(format!("{}: {m}", s.logical)),
            Fail::Io(m) => Fail::Io(format!("{}: {m}", s.logical)),
        })?;
        if c.pcm.len() as u64 != s.out_frames * 2 {
            return Err(Fail::Io(format!("{}: internal: output length disagrees", s.logical)));
        }
        let mut b = Vec::with_capacity(c.pcm.len() * 2);
        for v in &c.pcm {
            b.extend_from_slice(&v.to_le_bytes());
        }
        s.pcm = b;
        s.conv = Some(convert::Converted { pcm: Vec::new(), ..c });
    }

    // Joined true peak: every boundary in the assembled stream (§3).
    let mut segs: Vec<(u64, u64, Seg)> = Vec::new();
    let mut pf = None;
    for s in &sources {
        if pf.is_some() && pf != Some(s.folder) {
            segs.push((s.start - GAP_FRAMES, GAP_FRAMES, Seg::Gap));
        }
        pf = Some(s.folder);
        segs.push((s.start, s.out_frames, Seg::Src(s)));
    }
    let sample = |i: i64, c: usize| -> f32 {
        if i < 0 || i as u64 >= total {
            return 0.0;
        }
        let i = i as u64;
        let k = segs.partition_point(|x| x.0 <= i) - 1;
        match segs[k].2 {
            Seg::Gap => 0.0,
            Seg::Src(s) => {
                let o = ((i - s.start) * 4) as usize + c * 2;
                i16::from_le_bytes([s.pcm[o], s.pcm[o + 1]]) as f32 / 32768.0
            }
        }
    };
    let name = |k: usize| match segs[k].2 {
        Seg::Gap => "the folder gap".to_string(),
        Seg::Src(s) => s.logical.clone(),
    };
    let h = 3 * 54i64;
    for k in 1..segs.len() {
        let b = segs[k].0 as i64;
        let mut worst = 0.0f32;
        for c in 0..2 {
            let local: Vec<f32> = (b - h..b + h).map(|i| sample(i, c)).collect();
            worst = worst.max(tp.peak_range(&local, h - 54, h + 54));
        }
        let db = dsp::dbfs(worst as f64);
        if db + convert::GUARD_DB > convert::CEILING_DBTP {
            return Err(Fail::Refuse(format!(
                "the join between {} and {} reaches {} dBTP, over the {} dBTP ceiling with its {} dB guard; refusing without changing gains",
                name(k - 1),
                name(k),
                manifest::dec6(db),
                convert::CEILING_DBTP,
                convert::GUARD_DB
            )));
        }
    }

    // WAV bytes and manifest.
    let mut hdr = Vec::with_capacity(44);
    hdr.extend_from_slice(b"RIFF");
    hdr.extend_from_slice(&((data_len + 36) as u32).to_le_bytes());
    hdr.extend_from_slice(b"WAVEfmt ");
    hdr.extend_from_slice(&16u32.to_le_bytes());
    hdr.extend_from_slice(&1u16.to_le_bytes());
    hdr.extend_from_slice(&2u16.to_le_bytes());
    hdr.extend_from_slice(&44100u32.to_le_bytes());
    hdr.extend_from_slice(&176400u32.to_le_bytes());
    hdr.extend_from_slice(&4u16.to_le_bytes());
    hdr.extend_from_slice(&16u16.to_le_bytes());
    hdr.extend_from_slice(b"data");
    hdr.extend_from_slice(&(data_len as u32).to_le_bytes());
    let gap = vec![0u8; GAP_FRAMES as usize * 4];
    let mut parts: Vec<&[u8]> = vec![&hdr];
    let mut gaps = Vec::new();
    for (start, frames, seg) in &segs {
        match seg {
            Seg::Gap => {
                parts.push(&gap);
                gaps.push(J::obj([("frames", J::Int(*frames)), ("start_frame", J::Int(*start))]));
            }
            Seg::Src(s) => parts.push(&s.pcm),
        }
    }
    let wav_sha = sha256_hex(&parts);

    let libraries = J::Arr(
        libs::LIBRARIES
            .iter()
            .map(|(n, v, k, s)| J::obj([("name", J::s(*n)), ("version", J::s(*v)), ("source", J::s(*k)), ("sha256", J::s(*s))]))
            .collect(),
    );
    let (mut n_limited, mut n_unmeas, mut n_unknown) = (0, 0, 0);
    let srcs = J::Arr(
        sources
            .iter()
            .map(|s| {
                let c = s.conv.as_ref().unwrap();
                n_limited += c.peak_limited as u32;
                n_unmeas += (c.status == "unmeasurable") as u32;
                n_unknown += (!s.trim.known) as u32;
                J::obj([
                    ("logical_path", J::s(&s.logical)),
                    ("source_sha256", J::s(&s.sha)),
                    ("container", J::s(s.container)),
                    ("codec", J::s(s.codec)),
                    ("codec_profile", J::s(&s.codec_profile)),
                    ("input_rate", J::Int(s.rate as u64)),
                    ("input_channels", J::Int(s.channels as u64)),
                    ("raw_frames", J::Int(s.raw)),
                    ("trim_head", J::Int(s.trim.head)),
                    ("trim_tail", J::Int(s.trim.tail)),
                    ("trim_evidence", J::s(s.trim.evidence)),
                    ("effective_frames", J::Int(s.effective)),
                    ("output_frames", J::Int(s.out_frames)),
                    ("start_frame", J::Int(s.start)),
                    ("input_lufs", J::opt_dec(c.input_lufs)),
                    ("input_dbtp", J::opt_dec(c.input_dbtp)),
                    ("output_lufs", J::opt_dec(c.output_lufs)),
                    ("output_dbtp", J::opt_dec(c.output_dbtp)),
                    ("target_gain_db", J::dec(c.target_gain_db)),
                    ("applied_gain_db", J::dec(c.applied_gain_db)),
                    ("peak_limited", J::Bool(c.peak_limited)),
                    ("loudness_status", J::s(c.status)),
                    ("loudness_reason", J::opt_s(c.reason)),
                    ("gapless_status", J::s(if s.trim.known { "gapless_known" } else { "gapless_unknown" })),
                ])
            })
            .collect(),
    );
    let folders = J::Arr(
        counts
            .iter()
            .enumerate()
            .map(|(i, &n)| J::obj([("ordinal", J::Int(i as u64)), ("source_count", J::Int(n))]))
            .collect(),
    );
    let m = J::obj([
        ("schema", J::Int(1)),
        ("contract", J::s("INGEST-1")),
        ("tool_version", J::s(TOOL_VERSION)),
        ("build_profile", J::s(PROFILE_ID)),
        ("libraries", libraries),
        ("resampler_profile", J::s(RESAMPLER_PROFILE)),
        ("meter_profile", J::s(METER_PROFILE)),
        ("dither_profile", J::s(DITHER_PROFILE)),
        ("target_seconds", J::Int(a.seconds)),
        ("capacity_frames", J::Int(capacity)),
        ("total_frames", J::Int(total)),
        ("wav_sha256", J::s(&wav_sha)),
        ("folders", folders),
        ("sources", srcs),
        ("gaps", J::Arr(gaps)),
    ]);
    let manifest = m.canonical();

    // Final identity check: the published result derives only from the bytes hashed.
    for s in &sources {
        let bytes = read(&s.path, &s.logical)?;
        if sha256_hex(&[&bytes]) != s.sha {
            return Err(Fail::Refuse(format!("{}: the file changed while ingest was running", s.logical)));
        }
    }
    publish::publish(&a.out, &parts, manifest.as_bytes())?;
    Ok(format!(
        "ingest: wrote {} ({} sources in {} folders, {} of {}); peak-limited {}, unmeasurable {}, gapless-unknown {}",
        a.out.display(),
        sources.len(),
        counts.len(),
        mmss(total.div_ceil(44100)),
        mmss(a.seconds),
        n_limited,
        n_unmeas,
        n_unknown
    ))
}

fn main() {
    let argv: Vec<OsString> = std::env::args_os().skip(1).collect();
    let code = match parse(argv) {
        Ok(Cmd::Help) => {
            print!("{USAGE}");
            0
        }
        Ok(Cmd::Version) => {
            println!("ingest {TOOL_VERSION} INGEST-1 arithmetic-profile {PROFILE_ID}");
            0
        }
        Err(m) => {
            eprintln!("ingest: {m}\n{USAGE}");
            2
        }
        Ok(Cmd::Run(a)) => match run(a) {
            Ok(summary) => {
                println!("{summary}");
                0
            }
            Err(Fail::Refuse(m)) => {
                eprintln!("ingest: refused: {m}");
                2
            }
            Err(Fail::Io(m)) => {
                eprintln!("ingest: error: {m}");
                1
            }
        },
    };
    std::process::exit(code);
}
