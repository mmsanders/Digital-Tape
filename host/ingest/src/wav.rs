//! RIFF WAVE and AIFF/AIFC: strict container parsing, PCM only (contract §2).

use crate::common::*;

const KSDATA_TAIL: [u8; 14] =
    [0x00, 0x00, 0x00, 0x00, 0x10, 0x00, 0x80, 0x00, 0x00, 0xAA, 0x00, 0x38, 0x9B, 0x71];

struct Chunk<'a> {
    id: [u8; 4],
    body: &'a [u8],
}

/// Walk the chunks of a RIFF/FORM body. Every chunk must fit, with its pad byte.
fn chunks(body: &[u8], le: bool) -> Res<Vec<Chunk<'_>>> {
    let mut out = Vec::new();
    let mut o = 0usize;
    while o < body.len() {
        if body.len() - o < 8 {
            return refuse("truncated chunk header");
        }
        let mut id = [0u8; 4];
        id.copy_from_slice(&body[o..o + 4]);
        let size = if le { u32le(body, o + 4) } else { u32be(body, o + 4) } as usize;
        let start = o + 8;
        let end = start.checked_add(size).filter(|&e| e <= body.len());
        let Some(end) = end else {
            return refuse(format!(
                "chunk '{}' runs past the end of the file (truncated)",
                String::from_utf8_lossy(&id)
            ));
        };
        out.push(Chunk { id, body: &body[start..end] });
        o = end;
        if size % 2 == 1 {
            if o >= body.len() {
                return refuse("missing chunk pad byte (truncated)");
            }
            o += 1;
        }
    }
    Ok(out)
}

pub fn decode_wav(b: &[u8]) -> Res<Decoded> {
    if b.len() < 12 {
        return refuse("truncated RIFF header");
    }
    let riff = u32le(b, 4) as u64;
    if riff + 8 != b.len() as u64 {
        return refuse(if riff + 8 > b.len() as u64 {
            "RIFF size runs past the end of the file (truncated)"
        } else {
            "bytes follow the end of the RIFF chunk"
        });
    }
    let list = chunks(&b[12..], true)?;
    let mut fmt: Option<&[u8]> = None;
    let mut data: Option<&[u8]> = None;
    for c in &list {
        match &c.id {
            b"fmt " => {
                if fmt.is_some() {
                    return refuse("more than one 'fmt ' chunk");
                }
                if data.is_some() {
                    return refuse("'data' precedes 'fmt '");
                }
                fmt = Some(c.body);
            }
            b"data" => {
                if data.is_some() {
                    return refuse("more than one 'data' chunk");
                }
                data = Some(c.body);
            }
            _ => {}
        }
    }
    let Some(f) = fmt else { return refuse("no 'fmt ' chunk") };
    let Some(data) = data else { return refuse("no 'data' chunk") };
    if f.len() < 16 {
        return refuse("'fmt ' chunk is too short");
    }
    let mut tag = u16le(f, 0);
    let ch = u16le(f, 2) as u32;
    let rate = u32le(f, 4);
    let byte_rate = u32le(f, 8);
    let align = u16le(f, 12) as u32;
    let bits = u16le(f, 14) as u32;
    let mut container = "wav";
    if tag == 0xFFFE {
        container = "wav";
        if f.len() < 40 || u16le(f, 16) < 22 {
            return refuse("WAVE_FORMAT_EXTENSIBLE 'fmt ' chunk is too short");
        }
        let valid = u16le(f, 18) as u32;
        let mask = u32le(f, 20);
        if f[26..40] != KSDATA_TAIL {
            return refuse("WAVE_FORMAT_EXTENSIBLE sub-format GUID is not a WAVE format code");
        }
        let sub = u16le(f, 24);
        if valid == 0 || valid > bits {
            return refuse(format!("{valid} valid bits in a {bits}-bit container"));
        }
        let ok_mask = match ch {
            1 => mask == 0x4,
            2 => mask == 0x3,
            _ => true,
        };
        if !ok_mask {
            return refuse(format!(
                "ambiguous channel mask 0x{mask:X} for {ch} channel(s); INGEST-1 accepts mono 0x4 or stereo 0x3"
            ));
        }
        tag = sub;
    }
    check_channels(ch)?;
    let pcm = match (tag, bits) {
        (1, 8) => Pcm::U8,
        (1, 16) => Pcm::S16Le,
        (1, 24) => Pcm::S24Le,
        (1, 32) => Pcm::S32Le,
        (3, 32) => Pcm::F32Le,
        (3, 64) => Pcm::F64Le,
        (1, b) => return refuse(format!("{b}-bit integer PCM WAV is not supported")),
        (3, b) => return refuse(format!("{b}-bit float WAV is not supported")),
        (0x0055, _) => return refuse("MP3 inside WAV (format tag 0x0055) is not supported"),
        (t, _) => return refuse(format!("compressed or unknown WAV format tag 0x{t:04X}")),
    };
    if align != ch * pcm.bytes() as u32 || byte_rate as u64 != rate as u64 * align as u64 {
        return refuse("'fmt ' block align or byte rate disagrees with channels and bits");
    }
    check_rate(rate)?;
    if data.len() % align as usize != 0 {
        return refuse("'data' ends inside a sample frame (truncated)");
    }
    let frames = (data.len() / align as usize) as u64;
    let profile = if u16le(f, 0) == 0xFFFE { format!("extensible-{}", pcm.name()) } else { pcm.name().into() };
    Decoded {
        container,
        codec: if tag == 3 { "float" } else { "pcm" },
        codec_profile: profile,
        rate,
        channels: ch,
        raw_frames: frames,
        trim: Trim::lossless(),
        planes: deinterleave(data, pcm, ch as usize)?,
    }
    .finish()
}

/// IEEE-754 80-bit extended to an exact integer rate; refuses a fractional rate.
fn ext80_rate(e: &[u8]) -> Res<u32> {
    let sign_exp = u16be(e, 0);
    let mant = u64be(e, 2);
    if sign_exp & 0x8000 != 0 || mant == 0 {
        return refuse("AIFF sample rate is zero or negative");
    }
    let exp = (sign_exp & 0x7FFF) as i32 - 16383 - 63;
    let v = if exp >= 0 {
        if exp > 0 { return refuse("AIFF sample rate is out of range") }
        mant
    } else {
        let sh = (-exp) as u32;
        if sh >= 64 {
            return refuse("AIFF sample rate is not an integer");
        }
        if mant & ((1u64 << sh) - 1) != 0 {
            return refuse("AIFF sample rate is not an integer");
        }
        mant >> sh
    };
    u32::try_from(v).or_else(|_| refuse("AIFF sample rate is out of range"))
}

pub fn decode_aiff(b: &[u8]) -> Res<Decoded> {
    if b.len() < 12 {
        return refuse("truncated FORM header");
    }
    let size = u32be(b, 4) as u64;
    if size + 8 != b.len() as u64 {
        return refuse(if size + 8 > b.len() as u64 {
            "FORM size runs past the end of the file (truncated)"
        } else {
            "bytes follow the end of the FORM chunk"
        });
    }
    let aifc = &b[8..12] == b"AIFC";
    let list = chunks(&b[12..], false)?;
    let mut comm: Option<&[u8]> = None;
    let mut ssnd: Option<&[u8]> = None;
    for c in &list {
        match &c.id {
            b"COMM" => {
                if comm.replace(c.body).is_some() {
                    return refuse("more than one COMM chunk");
                }
            }
            b"SSND" => {
                if ssnd.replace(c.body).is_some() {
                    return refuse("more than one SSND chunk");
                }
            }
            _ => {}
        }
    }
    let Some(c) = comm else { return refuse("no COMM chunk") };
    if c.len() < if aifc { 22 } else { 18 } {
        return refuse("COMM chunk is too short");
    }
    let ch = u16be(c, 0) as u32;
    let frames = u32be(c, 2) as u64;
    let bits = u16be(c, 6) as u32;
    let rate = ext80_rate(&c[8..18])?;
    let mut little = false;
    let mut profile = String::new();
    if aifc {
        let ct = &c[18..22];
        match ct {
            b"NONE" => profile.push_str("none-"),
            b"sowt" => {
                little = true;
                profile.push_str("sowt-")
            }
            other => {
                return refuse(format!(
                    "compressed AIFC (compression type '{}') is not supported",
                    String::from_utf8_lossy(other)
                ))
            }
        }
    }
    check_channels(ch)?;
    // ADR-180 (P2V16-002): `sowt` is little-endian PCM16 only. Any other COMM sampleSize
    // refuses by name; it is never reinterpreted at the COMM width or frame count.
    let pcm = match (bits, little) {
        (16, true) => Pcm::S16Le,
        (b, true) => {
            return refuse(format!(
                "AIFC 'sowt' with {b}-bit samples is outside INGEST-1 ('sowt' is 16-bit only)"
            ))
        }
        (8, false) => Pcm::S8,
        (16, false) => Pcm::S16Be,
        (24, false) => Pcm::S24Be,
        (32, false) => Pcm::S32Be,
        (b, false) => return refuse(format!("{b}-bit AIFF samples are not supported")),
    };
    check_rate(rate)?;
    if frames == 0 {
        return refuse("COMM declares zero sample frames");
    }
    let Some(s) = ssnd else { return refuse("no SSND chunk") };
    if s.len() < 8 {
        return refuse("SSND chunk is too short");
    }
    let offset = u32be(s, 0) as usize;
    let need = frames as u128 * ch as u128 * pcm.bytes() as u128;
    let have = (s.len() - 8) as u128;
    if (offset as u128) + need != have {
        return refuse(if (offset as u128) + need > have {
            "SSND holds fewer sample frames than COMM declares (truncated)"
        } else {
            "SSND holds more bytes than COMM declares"
        });
    }
    let data = &s[8 + offset..];
    profile.push_str(&format!("s{bits}{}", if bits == 8 { "" } else if little { "le" } else { "be" }));
    Decoded {
        container: if aifc { "aifc" } else { "aiff" },
        codec: "pcm",
        codec_profile: profile,
        rate,
        channels: ch,
        raw_frames: frames,
        trim: Trim::lossless(),
        planes: deinterleave(data, pcm, ch as usize)?,
    }
    .finish()
}
