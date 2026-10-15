//! MPEG-1/2/2.5 Layer III: strict frame walk, Xing/Info + LAME delay/padding, and decoding
//! through the vendored Symphonia decoder (contract §2, §4).
//!
//! Raw semantics of the pinned decoder: every audio frame yields exactly its samples-per-
//! frame (1152 or 576) with no internal trimming. The Xing/Info frame is metadata and is
//! not decoded. A validated LAME declaration trims `delay + 529` head frames and
//! `padding - 529` tail frames (the 529-sample synthesis delay of the standard decoder).

use crate::common::*;
use symphonia_core::audio::Channels;
use symphonia_core::codecs::audio::well_known::CODEC_ID_MP3;
use symphonia_core::codecs::audio::{AudioCodecParameters, AudioDecoder, AudioDecoderOptions};
use symphonia_core::packet::PacketRef;
use symphonia_core::units::{Duration, Timestamp};

pub const DECODER_DELAY: u64 = 529;

#[derive(Clone, Copy, PartialEq, Eq)]
struct Hdr {
    version: u8, // 1, 2, 25
    crc: bool,
    bitrate: u32, // kbit/s
    rate: u32,
    pad: bool,
    mono: bool,
    size: usize,
    spf: u64,
}

const BR1: [u32; 15] = [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320];
const BR2: [u32; 15] = [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160];

fn header(b: &[u8], o: usize) -> Res<Hdr> {
    if b.len() < o + 4 {
        return refuse("MPEG audio frame header is truncated");
    }
    let h = u32be(b, o);
    if h >> 21 != 0x7FF {
        return refuse("MPEG audio frame sync lost (corrupt data or junk between frames)");
    }
    let version = match (h >> 19) & 3 {
        0 => 25,
        2 => 2,
        3 => 1,
        _ => return refuse("MPEG audio version is reserved (corrupt)"),
    };
    match (h >> 17) & 3 {
        1 => {}
        2 => return refuse("MPEG Layer II audio is outside INGEST-1"),
        3 => return refuse("MPEG Layer I audio is outside INGEST-1"),
        _ => return refuse("MPEG audio layer is reserved (corrupt)"),
    }
    let crc = (h >> 16) & 1 == 0;
    let bri = ((h >> 12) & 0xF) as usize;
    if bri == 0 {
        return refuse("free-format MP3 is outside INGEST-1");
    }
    if bri == 15 {
        return refuse("MP3 bitrate index is invalid (corrupt)");
    }
    let bitrate = if version == 1 { BR1[bri] } else { BR2[bri] };
    let sri = (h >> 10) & 3;
    if sri == 3 {
        return refuse("MP3 sample-rate index is reserved (corrupt)");
    }
    let base = [44100u32, 48000, 32000][sri as usize];
    let rate = match version {
        1 => base,
        2 => base / 2,
        _ => base / 4,
    };
    let pad = (h >> 9) & 1 == 1;
    let mono = (h >> 6) & 3 == 3;
    if h & 3 == 2 {
        return refuse("MP3 emphasis value is reserved (corrupt)");
    }
    let coef = if version == 1 { 144 } else { 72 };
    let size = (coef * bitrate * 1000 / rate) as usize + pad as usize;
    Ok(Hdr { version, crc, bitrate, rate, pad, mono, size, spf: if version == 1 { 1152 } else { 576 } })
}

fn side_info_len(h: &Hdr) -> usize {
    match (h.version == 1, h.mono) {
        (true, true) => 17,
        (true, false) => 32,
        (false, true) => 9,
        (false, false) => 17,
    }
}

/// CRC-16/ARC (reflected 0x8005, init 0): the LAME tag CRC.
fn crc16_arc(d: &[u8]) -> u16 {
    let mut c: u16 = 0;
    for &x in d {
        c ^= x as u16;
        for _ in 0..8 {
            c = if c & 1 != 0 { (c >> 1) ^ 0xA001 } else { c >> 1 };
        }
    }
    c
}

/// CRC-16 (0x8005, init 0xFFFF) over header bytes 2..4 and the side information.
fn crc16_frame(b: &[u8]) -> u16 {
    let mut c: u16 = 0xFFFF;
    for &x in b {
        c ^= (x as u16) << 8;
        for _ in 0..8 {
            c = if c & 0x8000 != 0 { (c << 1) ^ 0x8005 } else { c << 1 };
        }
    }
    c
}

/// Skip every leading ID3v2 tag; returns the first byte after them.
pub fn skip_id3v2(b: &[u8]) -> Res<usize> {
    let mut o = 0usize;
    while b.len() >= o + 10 && &b[o..o + 3] == b"ID3" {
        let s = &b[o + 6..o + 10];
        if s.iter().any(|&x| x & 0x80 != 0) {
            return refuse("ID3v2 tag size is invalid");
        }
        let size = ((s[0] as usize) << 21) | ((s[1] as usize) << 14) | ((s[2] as usize) << 7) | s[3] as usize;
        let footer = if b[o + 5] & 0x10 != 0 { 10 } else { 0 };
        o += 10 + size + footer;
        if o > b.len() {
            return refuse("ID3v2 tag runs past the end of the file");
        }
    }
    Ok(o)
}

/// Bytes at the end that are tags rather than audio: ID3v1 and APEv2.
pub fn trailing_tags(b: &[u8], start: usize) -> Res<usize> {
    let mut end = b.len();
    if end >= start + 128 && &b[end - 128..end - 125] == b"TAG" {
        end -= 128;
    }
    if end >= start + 32 && &b[end - 32..end - 24] == b"APETAGEX" {
        let size = u32le(b, end - 20) as usize;
        let flags = u32le(b, end - 12);
        let total = size + if flags & 0x8000_0000 != 0 { 32 } else { 0 };
        if total > end - start {
            return refuse("APEv2 tag size is invalid");
        }
        end -= total;
    }
    Ok(end)
}

pub fn decode(b: &[u8]) -> Res<Decoded> {
    let start = skip_id3v2(b)?;
    let end = trailing_tags(b, start)?;
    let mut frames: Vec<(usize, Hdr)> = Vec::new();
    let mut o = start;
    while o < end {
        let h = header(&b[..end], o)?;
        if o + h.size > end {
            return refuse("the last MP3 frame is truncated");
        }
        if let Some((_, f)) = frames.first() {
            if f.version != h.version || f.rate != h.rate {
                return refuse("MP3 sample rate changes mid-stream");
            }
            if f.mono != h.mono {
                return refuse("MP3 channel count changes mid-stream");
            }
        }
        if h.crc {
            let si = side_info_len(&h);
            if o + 6 + si > o + h.size {
                return refuse("MP3 frame is too short for its side information");
            }
            let mut d = Vec::with_capacity(2 + si);
            d.extend_from_slice(&b[o + 2..o + 4]);
            d.extend_from_slice(&b[o + 6..o + 6 + si]);
            if crc16_frame(&d) != u16be(b, o + 4) {
                return refuse("MP3 frame CRC mismatch (corrupt)");
            }
        }
        frames.push((o, h));
        o += h.size;
    }
    if frames.is_empty() {
        return refuse("the MPEG stream holds no audio frames");
    }

    // Xing/Info (first frame only), VBRI and LAME.
    let (f0, h0) = frames[0];
    let xo = f0 + 4 + if h0.crc { 2 } else { 0 } + side_info_len(&h0);
    let fr0 = &b[f0..f0 + h0.size];
    let mut trim = Trim::unknown();
    let mut audio = &frames[..];
    if fr0.len() >= 36 + 4 && &fr0[36..40] == b"VBRI" {
        return refuse("VBRI (Fraunhofer) gapless/duration metadata is unsupported in INGEST-1");
    }
    if fr0.len() >= xo - f0 + 8 && (&b[xo..xo + 4] == b"Xing" || &b[xo..xo + 4] == b"Info") {
        audio = &frames[1..];
        let flags = u32be(b, xo + 4);
        let mut p = xo + 8;
        let mut xframes: Option<u64> = None;
        let need = |p: usize, n: usize| -> Res<()> {
            if p + n > f0 + h0.size {
                refuse("Xing/Info header is truncated")
            } else {
                Ok(())
            }
        };
        if flags & 1 != 0 {
            need(p, 4)?;
            xframes = Some(u32be(b, p) as u64);
            p += 4;
        }
        if flags & 2 != 0 {
            need(p, 4)?;
            p += 4;
        }
        if flags & 4 != 0 {
            need(p, 100)?;
            p += 100;
        }
        if flags & 8 != 0 {
            need(p, 4)?;
            p += 4;
        }
        // A LAME-compatible extension: a printable encoder string and a valid tag CRC.
        let has_lame = p + 36 <= f0 + h0.size
            && b[p..p + 4].iter().all(|c| c.is_ascii_alphanumeric() || *c == b'.');
        if has_lame {
            // LAME computes the tag CRC over the frame up to the CRC field; FFmpeg's LAME-
            // compatible writer over a fixed 190 bytes with the field zeroed. They agree for
            // MPEG-1 stereo; either is admitted, anything else is invalid metadata.
            let crc = u16be(b, p + 34);
            let lame_span = crc16_arc(&b[f0..p + 34]);
            let fixed190 = (f0 + 190 <= f0 + h0.size).then(|| {
                let mut z = b[f0..f0 + 190].to_vec();
                for k in [p + 34 - f0, p + 35 - f0] {
                    if k < z.len() {
                        z[k] = 0;
                    }
                }
                crc16_arc(&z)
            });
            if lame_span != crc && fixed190 != Some(crc) {
                return refuse("LAME tag CRC mismatch (invalid gapless metadata)");
            }
            let dp = &b[p + 21..p + 24];
            let delay = ((dp[0] as u64) << 4) | (dp[1] as u64 >> 4);
            let padding = (((dp[1] & 0xF) as u64) << 8) | dp[2] as u64;
            let Some(xf) = xframes else {
                return refuse("LAME delay/padding without a Xing frame count cannot be validated");
            };
            if xf != audio.len() as u64 {
                return refuse(format!(
                    "Xing frame count {} disagrees with the {} audio frames in the stream",
                    xf,
                    audio.len()
                ));
            }
            if padding < DECODER_DELAY {
                return refuse(format!(
                    "LAME padding {padding} is smaller than the {DECODER_DELAY}-frame decoder delay (out of range)"
                ));
            }
            trim = Trim { head: delay + DECODER_DELAY, tail: padding - DECODER_DELAY, evidence: "xing_lame", known: true };
        }
    }
    if audio.is_empty() {
        return refuse("the MPEG stream holds no audio frames after its Xing/Info frame");
    }

    let channels = if h0.mono { 1 } else { 2 };
    let mut params = AudioCodecParameters::new();
    params.for_codec(CODEC_ID_MP3).with_sample_rate(h0.rate).with_channels(if h0.mono {
        Channels::Positioned(symphonia_core::audio::Position::FRONT_CENTER)
    } else {
        Channels::Positioned(
            symphonia_core::audio::Position::FRONT_LEFT | symphonia_core::audio::Position::FRONT_RIGHT,
        )
    });
    let mut dec = symphonia_bundle_mp3::MpaDecoder::try_new(&params, &AudioDecoderOptions::default())
        .map_err(|e| Fail::Io(format!("MP3 decoder init failed: {e}")))?;
    let mut planes: Vec<Vec<f64>> = vec![Vec::new(); channels];
    let mut tmp: Vec<Vec<f32>> = Vec::new();
    let mut vbr = false;
    for (i, (fo, h)) in audio.iter().enumerate() {
        vbr |= h.bitrate != audio[0].1.bitrate;
        let _ = h.pad;
        let pkt = PacketRef::new(0, Timestamp::new(i as i64 * h.spf as i64), Duration::new(h.spf), &b[*fo..*fo + h.size]);
        let buf = dec.decode_ref(&pkt).map_err(|e| Fail::Refuse(format!("MP3 frame {i} does not decode ({e}) (corrupt)")))?;
        if buf.frames() as u64 != h.spf || buf.spec().channels().count() != channels {
            return refuse(format!("MP3 frame {i} decoded to an unexpected length"));
        }
        buf.copy_to_vecs_planar::<f32>(&mut tmp);
        for (p, t) in planes.iter_mut().zip(&tmp) {
            p.extend(t.iter().map(|&v| v as f64));
        }
    }
    let raw = audio.len() as u64 * h0.spf;
    let ver = match h0.version {
        1 => "mpeg1",
        2 => "mpeg2",
        _ => "mpeg2.5",
    };
    Decoded {
        container: "mp3",
        codec: "mp3",
        codec_profile: format!("{ver}-layer3-{}", if vbr { "vbr" } else { "cbr" }),
        rate: h0.rate,
        channels: channels as u32,
        raw_frames: raw,
        trim,
        planes,
    }
    .finish()
}

/// True when bytes at `o` begin an MPEG audio Layer I/II/III frame header.
pub fn looks_like_mpeg(b: &[u8], o: usize) -> bool {
    b.len() >= o + 4 && b[o] == 0xFF && b[o + 1] & 0xE0 == 0xE0 && (b[o + 1] >> 1) & 3 != 0
}
