//! Shared types: the failure classes of the contract and a decoded source.

use std::fmt;

/// Contract §1 exit classes. `Refuse` is an input/contract refusal (exit 2); `Io` is an
/// I/O or tool failure (exit 1). The message is a plain sentence naming the source or
/// boundary and the reason.
#[derive(Debug)]
pub enum Fail {
    Refuse(String),
    Io(String),
}

impl fmt::Display for Fail {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        match self {
            Fail::Refuse(m) | Fail::Io(m) => f.write_str(m),
        }
    }
}

pub type Res<T> = Result<T, Fail>;

/// A refusal of the source being decoded; the caller prefixes the logical path.
pub fn refuse<T>(msg: impl Into<String>) -> Res<T> {
    Err(Fail::Refuse(msg.into()))
}

/// Contract §2: the decoded rates INGEST-1 admits.
pub const RATES: [u32; 15] = [
    7350, 8000, 11025, 12000, 16000, 22050, 24000, 32000, 44100, 48000, 64000, 88200, 96000,
    176400, 192000,
];

pub fn check_rate(rate: u32) -> Res<()> {
    if RATES.contains(&rate) {
        Ok(())
    } else {
        refuse(format!("sample rate {rate} Hz is not supported by INGEST-1"))
    }
}

pub fn check_channels(ch: u32) -> Res<()> {
    match ch {
        1 | 2 => Ok(()),
        0 => refuse("the stream declares zero channels"),
        n => refuse(format!("{n} channels; INGEST-1 accepts only mono or stereo")),
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
            return refuse("the stream decodes to zero frames");
        }
        for p in &self.planes {
            if p.len() as u64 != self.raw_frames {
                return Err(Fail::Io("internal: decoded plane length disagrees".into()));
            }
            if p.iter().any(|v| !v.is_finite()) {
                return refuse("the stream contains non-finite (NaN or infinite) samples");
            }
        }
        let trimmed = self.trim.head.checked_add(self.trim.tail);
        match trimmed {
            Some(t) if t < self.raw_frames => Ok(self),
            _ => refuse(format!(
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

pub fn deinterleave(data: &[u8], fmt: Pcm, channels: usize) -> Vec<Vec<f64>> {
    let w = fmt.bytes();
    let frames = data.len() / (w * channels);
    let mut planes = vec![Vec::with_capacity(frames); channels];
    for f in 0..frames {
        for (c, plane) in planes.iter_mut().enumerate() {
            let o = (f * channels + c) * w;
            plane.push(fmt.sample(&data[o..o + w]));
        }
    }
    planes
}
