//! `ingest` — Digital Tape INGEST-1 (docs/WP16-INGEST-CONTRACT.md).
//!
//! ingest --out DEST --length SECONDS FOLDER [FOLDER ...]
//! ingest --version

use ingest::{common, convert, dsp, libs, manifest, observe, order, publish, report, sniff};

use common::*;
use ingest::{DITHER_PROFILE, GAP_FRAMES, METER_PROFILE, PROFILE_ID, RESAMPLER_PROFILE, TOOL_VERSION};
use manifest::J;
use sha2::{Digest, Sha256};
use std::ffi::OsString;
use std::fs;
use std::path::PathBuf;


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

/// Contract §4 overage display: mm:ss with two-digit minutes (more digits past 99).
fn mmss(secs: u64) -> String {
    format!("{:02}:{:02}", secs / 60, secs % 60)
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
    silent: bool,
}

fn read(p: &std::path::Path, logical: &str) -> Res<Vec<u8>> {
    let open = observe::io_fault("read-open").and_then(|_| fs::File::open(p));
    let mut f = open.map_err(|e| Fail::io(IO_SOURCE, format!("{logical}: cannot open: {e}")).about(Subject::Source(logical.into())))?;
    let len = f.metadata().map(|m| m.len() as usize).unwrap_or(0);
    let mut b = alloc(len)?;
    let r = match observe::io_fault("decode-read") {
        Ok(()) => read_into(&mut f, &mut b)?,
        Err(e) => Err(e),
    };
    r.map_err(|e| Fail::io(IO_SOURCE, format!("{logical}: cannot read: {e}")).about(Subject::Source(logical.into())))?;
    Ok(b)
}

fn named(logical: &str, r: Res<Decoded>) -> Res<Decoded> {
    r.map_err(|f| f.prefixed(logical).about(Subject::Source(logical.into())))
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
        .ok_or_else(|| Fail::refuse(INGEST_LENGTH_INVALID, "--length is too large"))?;

    // Folders: distinct, listed, validated and ordered before anything is decoded.
    let mut ids: Vec<(String, usize)> = Vec::new();
    let mut sources: Vec<Source> = Vec::new();
    let mut counts = Vec::new();
    for (i, f) in a.folders.iter().enumerate() {
        let id = order::identity(f).map_err(|e| e.about(Subject::Folder(i)))?;
        if let Some((_, j)) = ids.iter().find(|x| x.0 == id) {
            return Err(Fail::refuse(FOLDER_DUPLICATE, format!(
                "{}: folder {i} is the same folder as folder {j}; folders must be distinct",
                f.display()
            ))
            .about(Subject::Folder(i))
            .with(Payload { same_as: Some(*j), ..Payload::default() }));
        }
        push(&mut ids, (id, i))?;
        let list = order::list_folder(f, i)?;
        push(&mut counts, list.len() as u64)?;
        report::progress("list", i as u64 + 1, a.folders.len() as u64);
        for e in list {
            push(&mut sources, Source {
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
                silent: false,
            })?;
        }
        checkpoint()?;
    }

    // Pass 1: decode, validate and count every source exactly.
    let n_sources = sources.len() as u64;
    for (pos, s) in sources.iter_mut().enumerate() {
        report::progress("decode", pos as u64, n_sources);
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
            .ok_or_else(|| Fail::refuse(SOURCE_CORRUPT, format!("{}: frame count overflows", s.logical)).about(Subject::Source(s.logical.clone())))?;
        if s.out_frames == 0 {
            return Err(Fail::refuse(SOURCE_TOO_SHORT, format!(
                "{}: too short to produce one 44.1 kHz frame ({} frames at {} Hz); the whole request is refused",
                s.logical, s.effective, s.rate
            ))
            .about(Subject::Source(s.logical.clone())));
        }
        checkpoint()?;
    }

    report::progress("decode", n_sources, n_sources);

    // Exact capacity, gaps included.
    let mut total: u64 = 0;
    let mut prev_folder = None;
    for s in sources.iter_mut() {
        if prev_folder.is_some() && prev_folder != Some(s.folder) {
            total = total.checked_add(GAP_FRAMES).ok_or_else(|| Fail::refuse(INGEST_LENGTH_INVALID, "total length overflows"))?;
        }
        prev_folder = Some(s.folder);
        s.start = total;
        total = total.checked_add(s.out_frames).ok_or_else(|| Fail::refuse(INGEST_LENGTH_INVALID, "total length overflows"))?;
    }
    if total > capacity {
        let e = total - capacity;
        return Err(Fail::refuse(INGEST_TOO_LONG, format!(
            "the sources and folder gaps total {} ({} frames), over the {} label by {} frames (rounded up {}); nothing was written",
            mmss(total.div_ceil(44100)),
            total,
            mmss(a.seconds),
            e,
            mmss(e.div_ceil(44100))
        ))
        .with(Payload { frames: Some((total, capacity, e)), ..Payload::default() }));
    }
    let data_len = total.checked_mul(4).filter(|&d| d + 36 <= u32::MAX as u64);
    let Some(data_len) = data_len else {
        return Err(Fail::refuse(INGEST_RIFF_LIMIT, "the output would exceed the canonical RIFF size limit (4 GiB)"));
    };

    // Pass 2: re-decode bound to the same bytes, convert each source alone.
    let tp = dsp::TruePeak::new()?;
    for (pos, s) in sources.iter_mut().enumerate() {
        report::progress("convert", pos as u64, n_sources);
        let bytes = read(&s.path, &s.logical)?;
        if sha256_hex(&[&bytes]) != s.sha {
            observe::mark("source_mutation_detected");
            return Err(Fail::refuse(SOURCE_CHANGED, format!("{}: the file changed while ingest was running", s.logical))
                .about(Subject::Source(s.logical.clone())));
        }
        let d = named(&s.logical, sniff::decode(&bytes))?;
        drop(bytes);
        let c = convert::convert(&d, s.out_frames, &tp, pos)
            .map_err(|f| f.prefixed(&s.logical).about(Subject::Source(s.logical.clone())))?;
        s.silent = c.status == "digital_silence";
        if !s.silent && c.pcm.len() as u64 != s.out_frames * 2 {
            return Err(Fail::io(INTERNAL, format!("{}: internal: output length disagrees", s.logical)));
        }
        let mut b = alloc(c.pcm.len() * 2)?;
        for v in &c.pcm {
            b.extend_from_slice(&v.to_le_bytes());
        }
        s.pcm = b;
        s.conv = Some(convert::Converted { pcm: Vec::new(), ..c });
        checkpoint()?;
    }

    report::progress("convert", n_sources, n_sources);

    // Joined true peak: every boundary in the assembled stream (§3).
    let mut segs: Vec<(u64, u64, Seg)> = Vec::new();
    let mut pf = None;
    for s in &sources {
        if pf.is_some() && pf != Some(s.folder) {
            push(&mut segs, (s.start - GAP_FRAMES, GAP_FRAMES, Seg::Gap))?;
        }
        pf = Some(s.folder);
        push(&mut segs, (s.start, s.out_frames, Seg::Src(s)))?;
    }
    let sample = |i: i64, c: usize| -> f32 {
        if i < 0 || i as u64 >= total {
            return 0.0;
        }
        let i = i as u64;
        let k = segs.partition_point(|x| x.0 <= i) - 1;
        match segs[k].2 {
            Seg::Gap => 0.0,
            Seg::Src(s) if s.silent => 0.0,
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
    // APP-1A §2: a boundary is named by its two neighbouring sources; a join with the
    // folder gap is named by the sources either side of that gap.
    let boundary = |k: usize| {
        let src = |j: usize| match segs[j].2 {
            Seg::Src(s) => Some(s.logical.clone()),
            Seg::Gap => None,
        };
        let before = (0..k).rev().find_map(src);
        let after = (k..segs.len()).find_map(src);
        match (before, after) {
            (Some(a), Some(b)) => Subject::Boundary(a, b),
            _ => Subject::None,
        }
    };
    // The whole joined output, measured as one signal (streamed in blocks): this is
    // the reported joined true peak and the refusal decision (§3).
    let fill_channel = |c: usize, start: i64, buf: &mut [f32]| {
        buf.fill(0.0);
        let end = start + buf.len() as i64;
        let k0 = segs.partition_point(|x| (x.0 + x.1) as i64 <= start.max(0));
        for (s0, len, seg) in &segs[k0..] {
            let (s0, len) = (*s0 as i64, *len as i64);
            if s0 >= end {
                break;
            }
            let Seg::Src(s) = seg else { continue };
            if s.silent {
                continue;
            }
            let a = s0.max(start);
            let b = (s0 + len).min(end);
            for i in a..b {
                let o = ((i - s0) * 4) as usize + c * 2;
                buf[(i - start) as usize] = i16::from_le_bytes([s.pcm[o], s.pcm[o + 1]]) as f32 / 32768.0;
            }
        }
    };
    let mut joined = 0.0f32;
    for c in 0..2 {
        joined = joined.max(tp.peak_streamed(total as i64, |start, buf| fill_channel(c, start, buf))?);
    }
    checkpoint()?;
    let joined_dbtp = (joined > 0.0).then(|| dsp::dbfs(joined as f64));
    observe::joined(joined_dbtp);
    let half = dsp::TP_HALF as i64;
    let h = 3 * half;
    for k in 1..segs.len() {
        let b = segs[k].0 as i64;
        let mut worst = 0.0f32;
        for c in 0..2 {
            let local: Vec<f32> = (b - h..b + h).map(|i| sample(i, c)).collect();
            worst = worst.max(tp.peak_range(&local, h - half, h + half));
        }
        let db = dsp::dbfs(worst as f64);
        if db + convert::GUARD_DB > convert::CEILING_DBTP {
            return Err(Fail::refuse(JOIN_PEAK, format!(
                "the join between {} and {} reaches {} dBTP, over the {} dBTP ceiling with its {} dB guard; refusing without changing gains",
                name(k - 1),
                name(k),
                manifest::dec6(db),
                convert::CEILING_DBTP,
                convert::GUARD_DB
            ))
            .about(boundary(k))
            .with(Payload { dbtp: Some(manifest::dec6(db)), ..Payload::default() }));
        }
    }

    if let Some(db) = joined_dbtp {
        if db + convert::GUARD_DB > convert::CEILING_DBTP {
            return Err(Fail::refuse(JOINED_PEAK, format!(
                "the joined output reaches {} dBTP, over the {} dBTP ceiling with its {} dB guard; refusing without changing gains",
                manifest::dec6(db),
                convert::CEILING_DBTP,
                convert::GUARD_DB
            ))
            .with(Payload { dbtp: Some(manifest::dec6(db)), ..Payload::default() }));
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
    let gap = filled(GAP_FRAMES as usize * 4, 0u8)?;
    let zeros = filled(1 << 20, 0u8)?;
    let mut parts: Vec<&[u8]> = alloc(1 + segs.len())?;
    push(&mut parts, &hdr)?;
    let mut gaps = Vec::new();
    for (start, frames, seg) in &segs {
        match seg {
            Seg::Gap => {
                push(&mut parts, &gap)?;
                push(&mut gaps, J::obj([("frames", J::Int(*frames)), ("start_frame", J::Int(*start))]))?;
            }
            Seg::Src(s) if s.silent => {
                let mut left = (s.out_frames * 4) as usize;
                while left > 0 {
                    let n = left.min(zeros.len());
                    push(&mut parts, &zeros[..n])?;
                    left -= n;
                }
            }
            Seg::Src(s) => push(&mut parts, &s.pcm)?,
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
                    ("target_gain_db", J::opt_dec(c.target_gain_db)),
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
    let manifest = m.canonical()?;
    drop(m);
    checkpoint()?;

    // Every decode, count, order, trim, numeric and capacity decision is made.
    observe::mark("preflight_complete");
    observe::cut("preflight_complete");
    // Final identity check: the published result derives only from the bytes hashed.
    for s in &sources {
        let bytes = read(&s.path, &s.logical)?;
        if sha256_hex(&[&bytes]) != s.sha {
            observe::mark("source_mutation_detected");
            return Err(Fail::refuse(SOURCE_CHANGED, format!("{}: the file changed while ingest was running", s.logical))
                .about(Subject::Source(s.logical.clone())));
        }
    }
    observe::mark("sources_revalidated");
    publish::publish(&a.out, &parts, manifest.as_bytes())?;
    report::progress("publish", 1, 1);
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
    if let Some(code) = observe::probe() {
        std::process::exit(code);
    }
    observe::init_heap_limit();
    let argv: Vec<OsString> = std::env::args_os().skip(1).collect();
    // APP-1A §1: report flags are split off first; without them argv is untouched.
    let (argv, flags) = match report::take_flags(argv) {
        Ok(x) => x,
        Err(m) => {
            eprintln!("ingest: {m}\n{USAGE}");
            std::process::exit(2);
        }
    };
    if let Some(f) = &flags {
        if let Err(m) = report::start(f, &format!("{TOOL_VERSION} INGEST-1 arithmetic-profile {PROFILE_ID}")) {
            eprintln!("ingest: report: {m}");
            std::process::exit(1);
        }
    }
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
            report::refusal(&Fail::refuse(INGEST_USAGE, m));
            2
        }
        Ok(Cmd::Run(a)) => match run(a) {
            Ok(summary) => {
                println!("{summary}");
                let _ = std::io::Write::flush(&mut std::io::stdout());
                observe::cut("after-publish");
                0
            }
            Err(f) => {
                let code = match f.class {
                    Class::Refuse => {
                        eprintln!("ingest: refused: {f}");
                        2
                    }
                    Class::Io => {
                        eprintln!("ingest: error: {f}");
                        1
                    }
                };
                report::refusal(&f);
                code
            }
        },
    };
    report::end(code);
    std::process::exit(code);
}
