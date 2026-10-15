//! Software-side contract checks for INGEST-1. These are the implementer's own tests and
//! not the independent oracle (Verification #169 authors that separately). Each refusal
//! is paired with the nearest admitted neighbour, so a test cannot pass by refusing
//! everything.

use std::fs;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::sync::atomic::{AtomicUsize, Ordering};

static N: AtomicUsize = AtomicUsize::new(0);
const BIN: &str = env!("CARGO_BIN_EXE_ingest");
const FIX: &str = concat!(env!("CARGO_MANIFEST_DIR"), "/tests/fixtures");

fn tmp() -> PathBuf {
    let p = std::env::temp_dir().join(format!("ingest-t-{}-{}", std::process::id(), N.fetch_add(1, Ordering::SeqCst)));
    let _ = fs::remove_dir_all(&p);
    fs::create_dir_all(&p).unwrap();
    p
}

fn run(args: &[&std::ffi::OsStr]) -> (i32, String, String) {
    let o = Command::new(BIN).args(args).output().unwrap();
    (o.status.code().unwrap_or(-1), String::from_utf8_lossy(&o.stdout).into(), String::from_utf8_lossy(&o.stderr).into())
}

fn ingest(dest: &Path, secs: u64, folders: &[&Path]) -> (i32, String, String) {
    let s = secs.to_string();
    let mut a: Vec<&std::ffi::OsStr> = vec!["--out".as_ref(), dest.as_os_str(), "--length".as_ref(), s.as_ref()];
    for f in folders {
        a.push(f.as_os_str());
    }
    run(&a)
}

#[derive(Clone, Copy)]
enum Fmt {
    U8,
    S16,
    S24,
    S32,
    F32,
    F64,
}

fn wav_bytes(rate: u32, ch: u16, fmt: Fmt, x: &[f64], extensible: Option<u32>) -> Vec<u8> {
    let (tag, bits): (u16, u16) = match fmt {
        Fmt::U8 => (1, 8),
        Fmt::S16 => (1, 16),
        Fmt::S24 => (1, 24),
        Fmt::S32 => (1, 32),
        Fmt::F32 => (3, 32),
        Fmt::F64 => (3, 64),
    };
    let mut d = Vec::new();
    for &v in x {
        match fmt {
            Fmt::U8 => d.push(((v * 127.0).round() as i32 + 128) as u8),
            Fmt::S16 => d.extend_from_slice(&((v * 32767.0).round() as i16).to_le_bytes()),
            Fmt::S24 => d.extend_from_slice(&((v * 8388607.0).round() as i32).to_le_bytes()[..3]),
            Fmt::S32 => d.extend_from_slice(&((v * 2147483647.0).round() as i32).to_le_bytes()),
            Fmt::F32 => d.extend_from_slice(&(v as f32).to_le_bytes()),
            Fmt::F64 => d.extend_from_slice(&v.to_le_bytes()),
        }
    }
    let align = ch * bits / 8;
    let mut f = Vec::new();
    match extensible {
        None => {
            f.extend_from_slice(&tag.to_le_bytes());
        }
        Some(_) => f.extend_from_slice(&0xFFFEu16.to_le_bytes()),
    }
    f.extend_from_slice(&ch.to_le_bytes());
    f.extend_from_slice(&rate.to_le_bytes());
    f.extend_from_slice(&(rate * align as u32).to_le_bytes());
    f.extend_from_slice(&align.to_le_bytes());
    f.extend_from_slice(&bits.to_le_bytes());
    if let Some(mask) = extensible {
        f.extend_from_slice(&22u16.to_le_bytes());
        f.extend_from_slice(&bits.to_le_bytes());
        f.extend_from_slice(&mask.to_le_bytes());
        f.extend_from_slice(&tag.to_le_bytes());
        f.extend_from_slice(&[0x00, 0x00, 0x00, 0x00, 0x10, 0x00, 0x80, 0x00, 0x00, 0xAA, 0x00, 0x38, 0x9B, 0x71]);
    }
    let mut b = Vec::new();
    b.extend_from_slice(b"RIFF");
    let body = 4 + 8 + f.len() + 8 + d.len() + d.len() % 2;
    b.extend_from_slice(&(body as u32).to_le_bytes());
    b.extend_from_slice(b"WAVEfmt ");
    b.extend_from_slice(&(f.len() as u32).to_le_bytes());
    b.extend_from_slice(&f);
    b.extend_from_slice(b"data");
    b.extend_from_slice(&(d.len() as u32).to_le_bytes());
    b.extend_from_slice(&d);
    if d.len() % 2 == 1 {
        b.push(0);
    }
    b
}

fn tone(rate: u32, ch: usize, frames: usize, f: f64, amp: f64) -> Vec<f64> {
    let mut x = Vec::with_capacity(frames * ch);
    for i in 0..frames {
        let v = amp * (2.0 * std::f64::consts::PI * f * i as f64 / rate as f64).sin();
        for _ in 0..ch {
            x.push(v);
        }
    }
    x
}

fn put(dir: &Path, name: &str, b: &[u8]) {
    fs::write(dir.join(name), b).unwrap();
}

fn s16_wav(rate: u32, ch: u16, frames: usize) -> Vec<u8> {
    wav_bytes(rate, ch, Fmt::S16, &tone(rate, ch as usize, frames, 440.0, 0.3), None)
}

fn manifest(dest: &Path) -> String {
    fs::read_to_string(dest.join("manifest.json")).unwrap()
}

fn field<'a>(m: &'a str, key: &str) -> Vec<&'a str> {
    let pat = format!("\"{key}\":");
    m.match_indices(&pat)
        .map(|(i, _)| {
            let r = &m[i + pat.len()..];
            let end = if r.starts_with('"') { r[1..].find('"').unwrap() + 2 } else { r.find([',', '}', ']']).unwrap() };
            &r[..end]
        })
        .collect()
}

fn no_stage(dir: &Path) {
    for e in fs::read_dir(dir).unwrap() {
        let n = e.unwrap().file_name();
        assert!(!n.to_string_lossy().contains(".ingest-stage-"), "stage left behind: {n:?}");
    }
}

fn pcm(dest: &Path) -> Vec<i16> {
    let b = fs::read(dest.join("audio.wav")).unwrap();
    b[44..].chunks(2).map(|c| i16::from_le_bytes([c[0], c[1]])).collect()
}

#[test]
fn version_and_syntax() {
    let (c, o, _) = run(&["--version".as_ref()]);
    assert_eq!(c, 0);
    assert!(o.contains("INGEST1-AP2"));
    assert_eq!(run(&["--help".as_ref()]).0, 0);
    assert_eq!(run(&[]).0, 2);
    let t = tmp();
    let d = t.join("x");
    for bad in ["0", "-5", "abc", "99999999999999999999999"] {
        let (c, _, _) = run(&["--out".as_ref(), d.as_os_str(), "--length".as_ref(), bad.as_ref(), t.as_os_str()]);
        assert_eq!(c, 2, "length {bad}");
    }
    assert!(!d.exists());
}

#[test]
fn positive_matrix_and_canonical_wav() {
    let t = tmp();
    let a = t.join("a");
    fs::create_dir(&a).unwrap();
    put(&a, "01 u8.wav", &wav_bytes(8000, 1, Fmt::U8, &tone(8000, 1, 8000, 300.0, 0.4), None));
    put(&a, "02 s24.wav", &wav_bytes(48000, 2, Fmt::S24, &tone(48000, 2, 24000, 300.0, 0.4), None));
    put(&a, "03 s32.wav", &wav_bytes(88200, 2, Fmt::S32, &tone(88200, 2, 44100, 300.0, 0.4), None));
    put(&a, "04 f32.wav", &wav_bytes(192000, 2, Fmt::F32, &tone(192000, 2, 96000, 300.0, 0.4), None));
    put(&a, "05 f64.wav", &wav_bytes(16000, 1, Fmt::F64, &tone(16000, 1, 16000, 300.0, 0.4), None));
    put(&a, "06 ext.wav", &wav_bytes(44100, 2, Fmt::S16, &tone(44100, 2, 22050, 300.0, 0.4), Some(0x3)));
    for f in ["tone_cbr.mp3", "tone_vbr_mono.mp3", "tone_mpeg2.mp3", "tone_noxing.mp3", "tone.m4a", "tone_ts.m4a", "tone.aac", "tone16.flac", "tone24.flac"] {
        fs::copy(Path::new(FIX).join(f), a.join(format!("10 {f}"))).unwrap();
    }
    let d = t.join("out");
    let (c, o, e) = ingest(&d, 120, &[&a]);
    assert_eq!(c, 0, "{e}");
    assert!(o.contains("gapless-unknown 2"), "{o}"); // tone_noxing.mp3, tone.aac
    let w = fs::read(d.join("audio.wav")).unwrap();
    assert_eq!(&w[..4], b"RIFF");
    assert_eq!(&w[8..16], b"WAVEfmt ");
    assert_eq!(u32::from_le_bytes(w[16..20].try_into().unwrap()), 16);
    assert_eq!(&w[20..36], &[1, 0, 2, 0, 0x44, 0xAC, 0, 0, 0x10, 0xB1, 2, 0, 4, 0, 16, 0]);
    assert_eq!(&w[36..40], b"data");
    let data = u32::from_le_bytes(w[40..44].try_into().unwrap()) as usize;
    assert_eq!(data + 44, w.len());
    assert_eq!(u32::from_le_bytes(w[4..8].try_into().unwrap()) as usize, data + 36);
    let m = manifest(&d);
    assert!(m.starts_with("{\"build_profile\":") && m.ends_with("}\n") && m.matches('\n').count() == 1);
    assert_eq!(field(&m, "total_frames")[0].parse::<usize>().unwrap() * 4, data);
    // Every measured source within ±0.5 LU of target and under the ceiling with guard.
    for (s, p) in field(&m, "output_lufs").iter().zip(field(&m, "output_dbtp")) {
        if *s == "null" {
            continue; // tone24.flac is 0.25 s: unmeasurable, too_short
        }
        let l: f64 = s.trim_matches('"').parse().unwrap();
        let p: f64 = p.trim_matches('"').parse().unwrap();
        assert!((l + 16.0).abs() <= 0.5, "{l}");
        assert!(p + 0.1 <= -1.0, "{p}");
    }
    // Mono sources are duplicated: the u8 mono source opens the output.
    let x = pcm(&d);
    assert!(x[..2 * 44100].chunks(2).all(|f| f[0] == f[1]));
}

#[test]
fn deterministic_and_relocatable() {
    let t = tmp();
    let a = t.join("one");
    fs::create_dir(&a).unwrap();
    put(&a, "a.wav", &s16_wav(48000, 2, 30000));
    fs::copy(Path::new(FIX).join("tone.m4a"), a.join("b.m4a")).unwrap();
    let elsewhere = t.join("deeper/place/one");
    fs::create_dir_all(&elsewhere).unwrap();
    for f in ["a.wav", "b.m4a"] {
        fs::copy(a.join(f), elsewhere.join(f)).unwrap();
    }
    let (d1, d2) = (t.join("o1"), t.join("deeper/o2"));
    assert_eq!(ingest(&d1, 60, &[&a]).0, 0);
    assert_eq!(ingest(&d2, 60, &[&elsewhere]).0, 0);
    assert_eq!(fs::read(d1.join("audio.wav")).unwrap(), fs::read(d2.join("audio.wav")).unwrap());
    assert_eq!(manifest(&d1), manifest(&d2));
    assert!(!manifest(&d1).contains(t.to_str().unwrap()));
}

#[test]
fn existing_destination_is_never_touched() {
    let t = tmp();
    let a = t.join("a");
    fs::create_dir(&a).unwrap();
    put(&a, "a.wav", &s16_wav(44100, 2, 4410));
    let d = t.join("out");
    fs::create_dir(&d).unwrap();
    put(&d, "keep", b"x");
    let (c, _, e) = ingest(&d, 60, &[&a]);
    assert_eq!(c, 2, "{e}");
    assert_eq!(fs::read(d.join("keep")).unwrap(), b"x");
    assert_eq!(fs::read_dir(&d).unwrap().count(), 1);
    no_stage(&t);
}

#[test]
fn zero_output_refuses_and_one_frame_neighbour_admits() {
    // 192 kHz: 2 frames -> floor((88200+96000)/192000) = 0; 3 frames -> 1.
    let t = tmp();
    let a = t.join("a");
    fs::create_dir(&a).unwrap();
    put(&a, "long.wav", &s16_wav(44100, 2, 44100));
    put(&a, "tiny.wav", &wav_bytes(192000, 2, Fmt::S16, &[0.2, 0.2, -0.2, -0.2], None));
    let d = t.join("out");
    let (c, _, e) = ingest(&d, 60, &[&a]);
    assert_eq!(c, 2);
    assert!(e.contains("0/tiny.wav") && e.contains("too short"), "{e}");
    assert!(!d.exists());
    no_stage(&t);
    // Digital silence with zero output frames refuses too.
    put(&a, "tiny.wav", &wav_bytes(192000, 2, Fmt::S16, &[0.0; 4], None));
    assert_eq!(ingest(&d, 60, &[&a]).0, 2);
    // Neighbour: three frames give one output frame and are admitted.
    put(&a, "tiny.wav", &wav_bytes(192000, 2, Fmt::S16, &[0.2, 0.2, -0.2, -0.2, 0.1, 0.1], None));
    let (c, _, e) = ingest(&d, 60, &[&a]);
    assert_eq!(c, 0, "{e}");
    let m = manifest(&d);
    assert_eq!(field(&m, "output_frames"), ["44100", "1"]);
    assert_eq!(field(&m, "loudness_reason")[1], "\"too_short\"");
}

#[test]
fn capacity_exact_fit_and_one_frame_over() {
    // Two folders: 44100 + 88200 gap + 44099 = 176399; then +1 frame = 176400 = 4 s exactly.
    let t = tmp();
    let (a, b) = (t.join("a"), t.join("b"));
    fs::create_dir(&a).unwrap();
    fs::create_dir(&b).unwrap();
    put(&a, "x.wav", &s16_wav(44100, 2, 44100));
    put(&b, "y.wav", &s16_wav(44100, 2, 44100));
    let d = t.join("out");
    let (c, _, e) = ingest(&d, 3, &[&a, &b]);
    assert_eq!(c, 2);
    assert!(e.contains("by 44100 frames") && e.contains("0:01"), "{e}");
    assert!(!d.exists());
    let (c, _, e) = ingest(&d, 4, &[&a, &b]);
    assert_eq!(c, 0, "{e}");
    let m = manifest(&d);
    assert_eq!(field(&m, "total_frames"), ["176400"]);
    assert_eq!(field(&m, "capacity_frames"), ["176400"]);
    assert_eq!(field(&m, "start_frame"), ["44100", "0", "132300"]); // "gaps" sorts before "sources"
    let x = pcm(&d);
    assert!(x[44100 * 2..132300 * 2].iter().all(|&v| v == 0));
    // One frame over: 44101 frames in the second folder.
    let d2 = t.join("out2");
    put(&b, "y.wav", &s16_wav(44100, 2, 44101));
    let (c, _, e) = ingest(&d2, 4, &[&a, &b]);
    assert_eq!(c, 2);
    assert!(e.contains("by 1 frames") && e.contains("(rounded up 0:01)"), "{e}");
}

#[test]
fn natural_order_and_join_is_exact_concatenation() {
    let t = tmp();
    let a = t.join("a");
    fs::create_dir(&a).unwrap();
    for n in ["10.wav", "2.wav", "1.wav", "02.wav"] {
        put(&a, n, &s16_wav(44100, 2, 22050));
    }
    let d = t.join("out");
    assert_eq!(ingest(&d, 60, &[&a]).0, 0);
    let m = manifest(&d);
    assert_eq!(field(&m, "logical_path"), ["\"0/1.wav\"", "\"0/02.wav\"", "\"0/2.wav\"", "\"0/10.wav\""]);
    // Each identical source converts identically regardless of neighbours.
    let x = pcm(&d);
    let n = 22050 * 2;
    for k in 1..4 {
        assert_eq!(&x[..n], &x[k * n..(k + 1) * n]);
    }
    // ... and alone.
    let b = t.join("b");
    fs::create_dir(&b).unwrap();
    put(&b, "only.wav", &s16_wav(44100, 2, 22050));
    let d2 = t.join("out2");
    assert_eq!(ingest(&d2, 60, &[&b]).0, 0);
    assert_eq!(pcm(&d2), &x[..n]);
}

#[test]
fn folder_refusals_with_admitted_neighbour() {
    let t = tmp();
    let a = t.join("a");
    fs::create_dir(&a).unwrap();
    put(&a, "x.wav", &s16_wav(44100, 2, 4410));
    let d = t.join("out");
    assert_eq!(ingest(&d, 60, &[&a]).0, 0); // neighbour
    let cases: Vec<(&str, Box<dyn Fn(&Path)>)> = vec![
        ("nested folders", Box::new(|p: &Path| fs::create_dir(p.join("sub")).unwrap())),
        ("not a supported audio format", Box::new(|p: &Path| put(p, "notes.txt", b"hello"))),
        ("not a supported audio format", Box::new(|p: &Path| put(p, ".DS_Store", b"\0\0\0\x01Bud1"))),
        ("folder is empty", Box::new(|p: &Path| fs::remove_file(p.join("x.wav")).unwrap())),
        #[cfg(unix)]
        ("symbolic links", Box::new(|p: &Path| std::os::unix::fs::symlink(p.join("x.wav"), p.join("y.wav")).unwrap())),
    ];
    for (i, (why, make)) in cases.iter().enumerate() {
        let f = t.join(format!("f{i}"));
        fs::create_dir(&f).unwrap();
        put(&f, "x.wav", &s16_wav(44100, 2, 4410));
        make(&f);
        let d = t.join(format!("o{i}"));
        let (c, _, e) = ingest(&d, 60, &[&f]);
        assert_eq!(c, 2, "{why}: {e}");
        assert!(e.contains(why), "{why}: {e}");
        assert!(!d.exists());
    }
    let (c, _, e) = ingest(&t.join("dup"), 60, &[&a, &t.join("a/../a")]);
    assert_eq!(c, 2);
    assert!(e.contains("distinct"), "{e}");
    let (c, _, _) = ingest(&t.join("missing"), 60, &[&t.join("nope")]);
    assert_eq!(c, 2);
    no_stage(&t);
}

#[test]
fn format_refusals_by_name() {
    let t = tmp();
    let ok = s16_wav(44100, 2, 4410);
    let mut rf64 = ok.clone();
    rf64[..4].copy_from_slice(b"RF64");
    let mut adpcm = ok.clone();
    adpcm[20] = 2;
    let mut trunc = ok.clone();
    trunc.truncate(ok.len() - 3);
    let mut three_ch = wav_bytes(44100, 3, Fmt::S16, &tone(44100, 3, 4410, 300.0, 0.3), None);
    three_ch.truncate(three_ch.len());
    let mut nan = wav_bytes(44100, 1, Fmt::F32, &tone(44100, 1, 4410, 300.0, 0.3), None);
    nan[44 + 400..44 + 404].copy_from_slice(&f32::NAN.to_le_bytes());
    let ambiguous = wav_bytes(44100, 2, Fmt::S16, &tone(44100, 2, 4410, 300.0, 0.3), Some(0));
    let rate = wav_bytes(44000, 2, Fmt::S16, &tone(44000, 2, 4400, 300.0, 0.3), None);
    let mut flac = fs::read(Path::new(FIX).join("tone16.flac")).unwrap();
    let mid = flac.len() / 2;
    flac[mid] ^= 0x10;
    let mut mp3 = fs::read(Path::new(FIX).join("tone_cbr.mp3")).unwrap();
    mp3.truncate(mp3.len() - 50);
    let m4a = fs::read(Path::new(FIX).join("tone.m4a")).unwrap();
    let swap = |b: &[u8], from: &[u8; 4], to: &[u8; 4]| -> Vec<u8> {
        let mut v = b.to_vec();
        let i = v.windows(4).position(|w| w == from).unwrap();
        v[i..i + 4].copy_from_slice(to);
        v
    };
    let enca = swap(&m4a, b"mp4a", b"enca");
    // AudioSpecificConfig object type 2 (LC) -> 5 (SBR): first ASC byte 0x11.. -> 0x29..
    let mut he = m4a.clone();
    let esds = he.windows(4).position(|w| w == b"esds").unwrap();
    // tone.m4a is 48 kHz stereo AAC-LC: ASC 0x11 0x90.
    let asc = esds + he[esds..].windows(2).position(|w| w == [0x11, 0x90]).unwrap();
    he[asc] = (he[asc] & 0x07) | (5 << 3);
    let cases: Vec<(&str, Vec<u8>, &str)> = vec![
        ("rf64.wav", rf64, "RF64"),
        ("adpcm.wav", adpcm, "format tag 0x0002"),
        ("trunc.wav", trunc, "RIFF size"),
        ("3ch.wav", three_ch, "3 channels"),
        ("nan.wav", nan, "non-finite"),
        ("mask.wav", ambiguous, "ambiguous channel mask"),
        ("rate.wav", rate, "44000 Hz"),
        ("bad.flac", flac, "FLAC"),
        ("cut.mp3", mp3, "truncated"),
        ("enc.m4a", enca, "protected"),
        ("he.m4a", he, "HE-AAC"),
        ("x.mp2", fs::read(Path::new(FIX).join("tone.mp2")).unwrap(), "Layer II"),
        ("x.oga", fs::read(Path::new(FIX).join("tone.oga")).unwrap(), "Ogg"),
        ("x.m4a", fs::read(Path::new(FIX).join("tone_alac.m4a")).unwrap(), "ALAC"),
        ("v.mp4", fs::read(Path::new(FIX).join("tone_video.mp4")).unwrap(), "video"),
        ("empty.wav", Vec::new(), "empty"),
    ];
    for (i, (name, bytes, why)) in cases.into_iter().enumerate() {
        let f = t.join(format!("f{i}"));
        fs::create_dir(&f).unwrap();
        put(&f, "ok.wav", &ok);
        put(&f, name, &bytes);
        let d = t.join(format!("o{i}"));
        let (c, _, e) = ingest(&d, 60, &[&f]);
        assert_eq!(c, 2, "{name}: {e}");
        assert!(e.contains(name) && e.contains(why), "{name}: {e}");
        assert!(!d.exists());
        // Neighbour: the same folder without the refused file is admitted.
        fs::remove_file(f.join(name)).unwrap();
        assert_eq!(ingest(&d, 60, &[&f]).0, 0, "{name} neighbour");
    }
    no_stage(&t);
}

#[test]
fn silence_short_and_peak_limited_exceptions() {
    let t = tmp();
    let a = t.join("a");
    fs::create_dir(&a).unwrap();
    put(&a, "1 silence.wav", &wav_bytes(48000, 2, Fmt::S16, &vec![0.0; 2 * 4800], None));
    put(&a, "2 short.wav", &wav_bytes(44100, 2, Fmt::S16, &tone(44100, 2, 4410, 1000.0, 0.05), None));
    // Crest factor ~30 dB: a single loud click in quiet tone; normalising to -16 LUFS
    // would exceed the ceiling, so the gain is peak-limited.
    let mut x = tone(44100, 1, 44100, 1000.0, 0.001);
    for i in 0..20 {
        x[22050 + i] = 0.9;
    }
    put(&a, "3 click.wav", &wav_bytes(44100, 1, Fmt::F32, &x, None));
    let d = t.join("out");
    let (c, o, e) = ingest(&d, 60, &[&a]);
    assert_eq!(c, 0, "{e}");
    assert!(o.contains("peak-limited 1") && o.contains("unmeasurable 1"), "{o}");
    let m = manifest(&d);
    assert_eq!(field(&m, "loudness_status"), ["\"digital_silence\"", "\"unmeasurable\"", "\"measured\""]);
    assert_eq!(field(&m, "peak_limited"), ["false", "false", "true"]);
    assert_eq!(field(&m, "input_lufs")[0], "null");
    assert_eq!(field(&m, "applied_gain_db")[0], "\"0.000000\"");
    let g: f64 = field(&m, "applied_gain_db")[1].trim_matches('"').parse().unwrap();
    assert!(g <= 0.0, "unmeasurable sources are never boosted");
    let p: f64 = field(&m, "output_dbtp")[2].trim_matches('"').parse().unwrap();
    assert!(p + 0.1 <= -1.0);
    let x = pcm(&d);
    assert!(x[..2 * 4410].iter().all(|&v| v == 0), "digital silence is exact zero");
}

#[test]
fn joined_peak_over_ceiling_refuses_naming_the_join() {
    // Two DC sources of opposite sign: each is fine alone, the step between them
    // overshoots after reconstruction.
    let t = tmp();
    let a = t.join("a");
    fs::create_dir(&a).unwrap();
    put(&a, "1.wav", &wav_bytes(44100, 2, Fmt::F32, &vec![0.8; 2 * 44100], None));
    put(&a, "2.wav", &wav_bytes(44100, 2, Fmt::F32, &vec![-0.8; 2 * 44100], None));
    let d = t.join("out");
    let (c, _, e) = ingest(&d, 60, &[&a]);
    assert_eq!(c, 2, "{e}");
    assert!(e.contains("join between 0/1.wav and 0/2.wav"), "{e}");
    assert!(!d.exists());
    // Neighbour: same sign joins cleanly.
    put(&a, "2.wav", &wav_bytes(44100, 2, Fmt::F32, &vec![0.8; 2 * 44100], None));
    let (c, _, e) = ingest(&d, 60, &[&a]);
    assert_eq!(c, 0, "{e}");
    no_stage(&t);
}

/// AIFF (`aifc` None) or AIFC with compression type `ct`; samples big-endian unless `le`.
fn aiff_bytes(rate: u32, ch: u16, bits: u16, x: &[f64], aifc: Option<&[u8; 4]>, le: bool) -> Vec<u8> {
    let mut d = Vec::new();
    for &v in x {
        let s = (v * ((1i64 << (bits - 1)) - 1) as f64).round() as i64;
        let bytes = (s as i32).to_be_bytes();
        let mut w = bytes[4 - bits as usize / 8..].to_vec();
        if le {
            w.reverse();
        }
        d.extend_from_slice(&w);
    }
    // 80-bit extended rate: integer rate exactly.
    let e = 63 - (rate as u64).leading_zeros() as u16;
    let mut ext = Vec::new();
    ext.extend_from_slice(&(16383 + e).to_be_bytes());
    ext.extend_from_slice(&((rate as u64) << (63 - e)).to_be_bytes());
    let mut comm = Vec::new();
    comm.extend_from_slice(&ch.to_be_bytes());
    comm.extend_from_slice(&((x.len() / ch as usize) as u32).to_be_bytes());
    comm.extend_from_slice(&bits.to_be_bytes());
    comm.extend_from_slice(&ext);
    if let Some(ct) = aifc {
        comm.extend_from_slice(ct);
        comm.extend_from_slice(&[0, 0]); // empty pstring, padded
    }
    let mut body = Vec::new();
    body.extend_from_slice(if aifc.is_some() { b"AIFC" } else { b"AIFF" });
    body.extend_from_slice(b"COMM");
    body.extend_from_slice(&(comm.len() as u32).to_be_bytes());
    body.extend_from_slice(&comm);
    body.extend_from_slice(b"SSND");
    body.extend_from_slice(&((d.len() + 8) as u32).to_be_bytes());
    body.extend_from_slice(&[0; 8]);
    body.extend_from_slice(&d);
    if d.len() % 2 == 1 {
        body.push(0);
    }
    let mut b = b"FORM".to_vec();
    b.extend_from_slice(&(body.len() as u32).to_be_bytes());
    b.extend_from_slice(&body);
    b
}

#[test]
fn aiff_matrix_and_sowt_is_16_bit_only() {
    // ADR-180 / P2V16-002.
    let t = tmp();
    let a = t.join("a");
    fs::create_dir(&a).unwrap();
    let x = tone(44100, 2, 4410, 300.0, 0.4);
    for bits in [8u16, 16, 24, 32] {
        put(&a, &format!("aiff{bits}.aif"), &aiff_bytes(44100, 2, bits, &x, None, false));
        put(&a, &format!("none{bits}.aifc"), &aiff_bytes(44100, 2, bits, &x, Some(b"NONE"), false));
    }
    put(&a, "sowt16.aifc", &aiff_bytes(44100, 2, 16, &x, Some(b"sowt"), true));
    let d = t.join("out");
    let (c, _, e) = ingest(&d, 60, &[&a]);
    assert_eq!(c, 0, "{e}");
    let m = manifest(&d);
    assert!(m.contains("\"codec_profile\":\"sowt-s16le\""));
    // sowt and big-endian 16-bit of the same samples convert identically.
    let pcm = pcm(&d);
    let paths = field(&m, "logical_path");
    let starts = field(&m, "start_frame");
    let idx = |name: &str| paths.iter().position(|p| p.contains(name)).unwrap();
    let start = |name: &str| starts[starts.len() - paths.len() + idx(name)].parse::<usize>().unwrap() * 2;
    let n = 4410 * 2;
    assert_eq!(&pcm[start("sowt16")..start("sowt16") + n], &pcm[start("aiff16")..start("aiff16") + n]);
    for (bits, le) in [(8u16, false), (24, true), (32, true), (24, false)] {
        let f = t.join(format!("s{bits}{le}"));
        fs::create_dir(&f).unwrap();
        put(&f, "ok.aifc", &aiff_bytes(44100, 2, 16, &x, Some(b"sowt"), true));
        put(&f, "x.aifc", &aiff_bytes(44100, 2, bits, &x, Some(b"sowt"), le));
        let d = t.join(format!("o{bits}{le}"));
        let (c, _, e) = ingest(&d, 60, &[&f]);
        assert_eq!(c, 2, "sowt {bits}: {e}");
        assert!(e.contains("0/x.aifc") && e.contains("'sowt' is 16-bit only"), "{e}");
        assert!(!d.exists());
    }
    let f = t.join("fl32");
    fs::create_dir(&f).unwrap();
    put(&f, "x.aifc", &aiff_bytes(44100, 2, 32, &x, Some(b"fl32"), false));
    let (c, _, e) = ingest(&t.join("of"), 60, &[&f]);
    assert_eq!(c, 2);
    assert!(e.contains("compressed AIFC") && e.contains("fl32"), "{e}");
    no_stage(&t);
}

#[test]
fn adts_crc_is_verified_when_present() {
    // ADR-180 ruling (b). Fixtures from the FDK reference encoder with protection on.
    let t = tmp();
    let a = t.join("a");
    fs::create_dir(&a).unwrap();
    for f in ["tone_crc_stereo.aac", "tone_crc_mono.aac"] {
        fs::copy(Path::new(FIX).join(f), a.join(f)).unwrap();
    }
    let (c, o, e) = ingest(&t.join("out"), 60, &[&a]);
    assert_eq!(c, 0, "{e}");
    assert!(o.contains("gapless-unknown 2"), "{o}");
    let good = fs::read(Path::new(FIX).join("tone_crc_stereo.aac")).unwrap();
    assert_eq!(good[1] & 1, 0, "fixture carries a CRC");
    // Locate the second frame so the flips are mid-stream.
    let len0 = (((good[3] & 3) as usize) << 11) | ((good[4] as usize) << 3) | (good[5] as usize >> 5);
    let f1 = len0;
    let flips: [(&str, usize, u8); 3] = [
        ("crc field", f1 + 7, 0x01),
        ("private bit in the header", f1 + 2, 0x02),
        ("first payload bits", f1 + 9 + 2, 0x10),
    ];
    for (i, (what, byte, mask)) in flips.into_iter().enumerate() {
        let mut bad = good.clone();
        bad[byte] ^= mask;
        let f = t.join(format!("f{i}"));
        fs::create_dir(&f).unwrap();
        put(&f, "ok.aac", &good);
        put(&f, "x.aac", &bad);
        let d = t.join(format!("o{i}"));
        let (c, _, e) = ingest(&d, 60, &[&f]);
        assert_eq!(c, 2, "{what}: {e}");
        assert!(e.contains("0/x.aac") && (e.contains("CRC mismatch") || e.contains("does not decode")), "{what}: {e}");
        assert!(!d.exists());
    }
    // The header private bit decodes identically, so only the CRC can refuse it.
    let mut bad = good.clone();
    bad[f1 + 2] ^= 0x02;
    let f = t.join("priv");
    fs::create_dir(&f).unwrap();
    put(&f, "x.aac", &bad);
    let (_, _, e) = ingest(&t.join("op"), 60, &[&f]);
    assert!(e.contains("ADTS frame 1 CRC mismatch"), "{e}");
    no_stage(&t);
}
