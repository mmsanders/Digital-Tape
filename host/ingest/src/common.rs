//! Shared types: the failure classes of the contract and a decoded source.

use std::fmt;

/// Contract §1 exit classes: `Refuse` is an input/contract refusal (exit 2), `Io` an I/O
/// or tool failure (exit 1).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Class {
    Refuse,
    Io,
}

/// APP-1A §2 subject of a refusal: what the app may name. Request, destination and
/// internal failures name nothing.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub enum Subject {
    #[default]
    None,
    /// An INGEST-1 logical path `ordinal/NFC_name`.
    Source(String),
    /// A folder argument, by ordinal.
    Folder(usize),
    /// Two neighbouring source logical paths.
    Boundary(String, String),
}

/// APP-1A §2 payloads; only the ID that owns a field sets it.
#[derive(Debug, Clone, Default, PartialEq, Eq)]
pub struct Payload {
    /// INGEST_TOO_LONG: total, capacity and excess frames, gaps included.
    pub frames: Option<(u64, u64, u64)>,
    /// FOLDER_DUPLICATE: the earlier ordinal.
    pub same_as: Option<usize>,
    /// JOIN_PEAK / JOINED_PEAK: the six-decimal dBTP string.
    pub dbtp: Option<String>,
}

/// A refusal or failure: its exit class, the plain sentence stderr prints (unchanged
/// from INGEST-1), and the closed APP-1A ID, subject and payload a report carries. The
/// ID is fixed where the failure is created, never derived from the sentence.
#[derive(Debug)]
pub struct Fail {
    pub class: Class,
    pub msg: String,
    pub id: &'static str,
    pub subject: Subject,
    pub payload: Payload,
}

impl Fail {
    pub fn refuse(id: &'static str, msg: impl Into<String>) -> Fail {
        Fail { class: Class::Refuse, msg: msg.into(), id, subject: Subject::None, payload: Payload::default() }
    }
    pub fn io(id: &'static str, msg: impl Into<String>) -> Fail {
        Fail { class: Class::Io, msg: msg.into(), id, subject: Subject::None, payload: Payload::default() }
    }
    /// Prefix the sentence (`"{p}: {msg}"`), keeping class, ID, subject and payload.
    pub fn prefixed(mut self, p: &str) -> Fail {
        self.msg = format!("{p}: {}", self.msg);
        self
    }
    /// Name the subject unless the site already named a more specific one.
    pub fn about(mut self, s: Subject) -> Fail {
        if self.subject == Subject::None && !names_nothing(self.id) {
            self.subject = s;
        }
        self
    }
    pub fn with(mut self, p: Payload) -> Fail {
        self.payload = p;
        self
    }
}

/// APP-1A §2: request, destination and internal failures carry a null subject.
pub fn names_nothing(id: &str) -> bool {
    id.starts_with("INGEST_") || id.starts_with("DEST_") || matches!(id, IO_DEST | IO_MEMORY | INTERNAL | JOINED_PEAK)
}

impl fmt::Display for Fail {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        f.write_str(&self.msg)
    }
}

pub type Res<T> = Result<T, Fail>;

/// A refusal of the source being decoded; the caller prefixes the logical path.
pub fn refuse<T>(id: &'static str, msg: impl Into<String>) -> Res<T> {
    Err(Fail::refuse(id, msg))
}

// APP-1A §2 closed IDs. Exit 2:
pub const INGEST_USAGE: &str = "INGEST_USAGE";
pub const INGEST_LENGTH_INVALID: &str = "INGEST_LENGTH_INVALID";
pub const INGEST_TOO_LONG: &str = "INGEST_TOO_LONG";
pub const INGEST_RIFF_LIMIT: &str = "INGEST_RIFF_LIMIT";
pub const FOLDER_SYMLINK: &str = "FOLDER_SYMLINK";
pub const FOLDER_UNREADABLE: &str = "FOLDER_UNREADABLE";
pub const FOLDER_NOT_FOLDER: &str = "FOLDER_NOT_FOLDER";
pub const FOLDER_DUPLICATE: &str = "FOLDER_DUPLICATE";
pub const FOLDER_EMPTY: &str = "FOLDER_EMPTY";
pub const FOLDER_NAME_COLLISION: &str = "FOLDER_NAME_COLLISION";
pub const FOLDER_NAME_NOT_UNICODE: &str = "FOLDER_NAME_NOT_UNICODE";
pub const ENTRY_SYMLINK: &str = "ENTRY_SYMLINK";
pub const ENTRY_NESTED_FOLDER: &str = "ENTRY_NESTED_FOLDER";
pub const ENTRY_NOT_REGULAR: &str = "ENTRY_NOT_REGULAR";
pub const ENTRY_NAME_INVALID: &str = "ENTRY_NAME_INVALID";
pub const SOURCE_PROTECTED: &str = "SOURCE_PROTECTED";
pub const SOURCE_NOT_AUDIO: &str = "SOURCE_NOT_AUDIO";
pub const SOURCE_TOO_SHORT: &str = "SOURCE_TOO_SHORT";
pub const SOURCE_CHANGED: &str = "SOURCE_CHANGED";
pub const SOURCE_NON_FINITE: &str = "SOURCE_NON_FINITE";
pub const SOURCE_LEVEL: &str = "SOURCE_LEVEL";
pub const SOURCE_TRIM_UNSUPPORTED: &str = "SOURCE_TRIM_UNSUPPORTED";
pub const SOURCE_OUTSIDE_INGEST1: &str = "SOURCE_OUTSIDE_INGEST1";
pub const SOURCE_CORRUPT: &str = "SOURCE_CORRUPT";
pub const JOIN_PEAK: &str = "JOIN_PEAK";
pub const JOINED_PEAK: &str = "JOINED_PEAK";
pub const DEST_EXISTS: &str = "DEST_EXISTS";
pub const DEST_APPEARED: &str = "DEST_APPEARED";
pub const DEST_NAME_INVALID: &str = "DEST_NAME_INVALID";
// Exit 1:
pub const IO_SOURCE: &str = "IO_SOURCE";
pub const IO_FOLDER: &str = "IO_FOLDER";
pub const IO_DEST: &str = "IO_DEST";
pub const IO_MEMORY: &str = "IO_MEMORY";
pub const INTERNAL: &str = "INTERNAL";

/// Contract §2: the decoded rates INGEST-1 admits.
pub const RATES: [u32; 15] = [
    7350, 8000, 11025, 12000, 16000, 22050, 24000, 32000, 44100, 48000, 64000, 88200, 96000,
    176400, 192000,
];

pub fn check_rate(rate: u32) -> Res<()> {
    if RATES.contains(&rate) {
        Ok(())
    } else {
        refuse(SOURCE_OUTSIDE_INGEST1, format!("sample rate {rate} Hz is not supported by INGEST-1"))
    }
}

pub fn check_channels(ch: u32) -> Res<()> {
    match ch {
        1 | 2 => Ok(()),
        0 => refuse(SOURCE_OUTSIDE_INGEST1, "the stream declares zero channels"),
        n => refuse(SOURCE_OUTSIDE_INGEST1, format!("{n} channels; INGEST-1 accepts only mono or stereo")),
    }
}

/// Contract §4 trim declaration. `known` false is `gapless_unknown`.
#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Trim {
    pub head: u64,
    pub tail: u64,
    pub evidence: &'static str,
    pub known: bool,
}

impl Trim {
    /// A lossless container: the decoded sequence is the source, exactly.
    pub fn lossless() -> Trim {
        Trim { head: 0, tail: 0, evidence: "none", known: true }
    }
    /// A lossy stream without admitted trim metadata: untrimmed, `gapless_unknown`.
    pub fn unknown() -> Trim {
        Trim { head: 0, tail: 0, evidence: "none", known: false }
    }
}

/// One fully decoded, validated source. `planes` holds the raw decoded sequence per
/// channel (untrimmed) as floating-point full scale ±1.0.
pub struct Decoded {
    pub container: &'static str,
    pub codec: &'static str,
    pub codec_profile: String,
    pub rate: u32,
    pub channels: u32,
    pub raw_frames: u64,
    pub trim: Trim,
    pub planes: Vec<Vec<f64>>,
}

impl Decoded {
    pub fn effective_frames(&self) -> u64 {
        self.raw_frames - self.trim.head - self.trim.tail
    }

    /// Validate the trim interval against the decoded length (§4) and finite samples.
    pub fn finish(self) -> Res<Decoded> {
        check_rate(self.rate)?;
        check_channels(self.channels)?;
        if self.raw_frames == 0 {
            return refuse(SOURCE_TOO_SHORT, "the stream decodes to zero frames");
        }
        for p in &self.planes {
            if p.len() as u64 != self.raw_frames {
                return Err(Fail::io(INTERNAL, "internal: decoded plane length disagrees"));
            }
            if p.iter().any(|v| !v.is_finite()) {
                return refuse(SOURCE_NON_FINITE, "the stream contains non-finite (NaN or infinite) samples");
            }
        }
        let trimmed = self.trim.head.checked_add(self.trim.tail);
        match trimmed {
            Some(t) if t < self.raw_frames => Ok(self),
            _ => refuse(SOURCE_TRIM_UNSUPPORTED, format!(
                "declared trim (head {}, tail {}) leaves no frames of the {} decoded",
                self.trim.head, self.trim.tail, self.raw_frames
            )),
        }
    }
}

/// Little/big-endian readers over a byte slice with explicit truncation refusal.
pub fn u16le(b: &[u8], o: usize) -> u16 {
    u16::from_le_bytes([b[o], b[o + 1]])
}
pub fn u32le(b: &[u8], o: usize) -> u32 {
    u32::from_le_bytes([b[o], b[o + 1], b[o + 2], b[o + 3]])
}
pub fn u16be(b: &[u8], o: usize) -> u16 {
    u16::from_be_bytes([b[o], b[o + 1]])
}
pub fn u32be(b: &[u8], o: usize) -> u32 {
    u32::from_be_bytes([b[o], b[o + 1], b[o + 2], b[o + 3]])
}
pub fn u64be(b: &[u8], o: usize) -> u64 {
    let mut a = [0u8; 8];
    a.copy_from_slice(&b[o..o + 8]);
    u64::from_be_bytes(a)
}

/// Decode interleaved integer/float PCM bytes into planes.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Pcm {
    U8,
    S8,
    S16Le,
    S24Le,
    S32Le,
    S16Be,
    S24Be,
    S32Be,
    F32Le,
    F64Le,
}

impl Pcm {
    pub fn bytes(self) -> usize {
        match self {
            Pcm::U8 | Pcm::S8 => 1,
            Pcm::S16Le | Pcm::S16Be => 2,
            Pcm::S24Le | Pcm::S24Be => 3,
            Pcm::S32Le | Pcm::S32Be | Pcm::F32Le => 4,
            Pcm::F64Le => 8,
        }
    }

    pub fn name(self) -> &'static str {
        match self {
            Pcm::U8 => "u8",
            Pcm::S8 => "s8",
            Pcm::S16Le => "s16le",
            Pcm::S24Le => "s24le",
            Pcm::S32Le => "s32le",
            Pcm::S16Be => "s16be",
            Pcm::S24Be => "s24be",
            Pcm::S32Be => "s32be",
            Pcm::F32Le => "f32le",
            Pcm::F64Le => "f64le",
        }
    }

    fn sample(self, s: &[u8]) -> f64 {
        match self {
            Pcm::U8 => (s[0] as f64 - 128.0) / 128.0,
            Pcm::S8 => (s[0] as i8) as f64 / 128.0,
            Pcm::S16Le => i16::from_le_bytes([s[0], s[1]]) as f64 / 32768.0,
            Pcm::S16Be => i16::from_be_bytes([s[0], s[1]]) as f64 / 32768.0,
            Pcm::S24Le => (i32::from_le_bytes([0, s[0], s[1], s[2]]) >> 8) as f64 / 8388608.0,
            Pcm::S24Be => (i32::from_be_bytes([s[0], s[1], s[2], 0]) >> 8) as f64 / 8388608.0,
            Pcm::S32Le => i32::from_le_bytes([s[0], s[1], s[2], s[3]]) as f64 / 2147483648.0,
            Pcm::S32Be => i32::from_be_bytes([s[0], s[1], s[2], s[3]]) as f64 / 2147483648.0,
            Pcm::F32Le => f32::from_le_bytes([s[0], s[1], s[2], s[3]]) as f64,
            Pcm::F64Le => {
                let mut a = [0u8; 8];
                a.copy_from_slice(&s[..8]);
                f64::from_le_bytes(a)
            }
        }
    }
}

/// An empty vector with room for `n` elements, or an I/O failure (exit 1) when memory
/// is exhausted: resource exhaustion must not abort the process (contract §6).
pub fn alloc<T>(n: usize) -> Res<Vec<T>> {
    let mut v = Vec::new();
    v.try_reserve_exact(n).map_err(|_| oom(n))?;
    Ok(v)
}

fn oom(n: usize) -> Fail {
    Fail::io(IO_MEMORY, format!("out of memory (needed {n} elements); nothing was written"))
}

// Fallible forms of the std allocations an input can size (crate::mem): every one
// fails as an IO_MEMORY `Fail` (exit 1), never through std's abort.

/// `vec![v; n]`.
pub fn filled<T: Clone>(n: usize, v: T) -> Res<Vec<T>> {
    let mut x = alloc(n)?;
    x.resize(n, v);
    Ok(x)
}

/// `collect()` of an iterator that yields about `n` items (more still grow fallibly).
pub fn collect<T>(n: usize, it: impl IntoIterator<Item = T>) -> Res<Vec<T>> {
    let mut x = alloc(n)?;
    for v in it {
        push(&mut x, v)?;
    }
    Ok(x)
}

/// `v.push(x)`.
pub fn push<T>(v: &mut Vec<T>, x: T) -> Res<()> {
    if v.len() == v.capacity() {
        v.try_reserve(1).map_err(|_| oom(v.len() + 1))?;
    }
    v.push(x);
    Ok(())
}

/// `v.extend_from_slice(s)`.
pub fn extend<T: Copy>(v: &mut Vec<T>, s: &[T]) -> Res<()> {
    v.try_reserve(s.len()).map_err(|_| oom(v.len() + s.len()))?;
    v.extend_from_slice(s);
    Ok(())
}

/// `s.push_str(t)`.
pub fn put(s: &mut String, t: &str) -> Res<()> {
    s.try_reserve(t.len()).map_err(|_| oom(s.len() + t.len()))?;
    s.push_str(t);
    Ok(())
}

/// `read_to_end` that grows `b` only fallibly: reads into spare capacity, then probes.
pub fn read_into(f: &mut impl std::io::Read, b: &mut Vec<u8>) -> Res<std::io::Result<()>> {
    use std::io::Read;
    loop {
        let room = (b.capacity() - b.len()) as u64;
        if room > 0 {
            if let Err(e) = f.by_ref().take(room).read_to_end(b) {
                return Ok(Err(e));
            }
            if b.len() < b.capacity() {
                return Ok(Ok(())); // end of file inside the spare capacity
            }
        }
        let mut one = [0u8; 1];
        let n = loop {
            match f.read(&mut one) {
                Err(e) if e.kind() == std::io::ErrorKind::Interrupted => continue,
                r => break r,
            }
        };
        match n {
            Ok(0) => return Ok(Ok(())),
            Ok(_) => {
                b.try_reserve(b.len().max(1 << 16)).map_err(|_| oom(b.len() + 1))?;
                b.push(one[0]);
            }
            Err(e) => return Ok(Err(e)),
        }
    }
}

/// The run's memory checkpoint: once the system has refused an allocation (crate::mem),
/// the run fails here as IO_MEMORY (exit 1) instead of going on to publish.
pub fn checkpoint() -> Res<()> {
    if crate::mem::exhausted() {
        return Err(Fail::io(IO_MEMORY, "out of memory (the system refused an allocation); nothing was written"));
    }
    Ok(())
}

pub fn deinterleave(data: &[u8], fmt: Pcm, channels: usize) -> Res<Vec<Vec<f64>>> {
    let w = fmt.bytes();
    let frames = data.len() / (w * channels);
    let mut planes = Vec::with_capacity(channels);
    for _ in 0..channels {
        planes.push(alloc(frames)?);
    }
    for f in 0..frames {
        for (c, plane) in planes.iter_mut().enumerate() {
            let o = (f * channels + c) * w;
            plane.push(fmt.sample(&data[o..o + w]));
        }
    }
    Ok(planes)
}
