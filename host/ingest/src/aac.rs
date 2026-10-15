//! AAC-LC in ADTS and in ISO BMFF (M4A/MP4), decoded by the vendored Symphonia AAC-LC
//! decoder (contract §2, §4).
//!
//! Raw semantics of the pinned decoder: every access unit yields exactly 1024 frames, the
//! first of them included (no internal priming removal). An admitted ISO BMFF edit list
//! therefore maps directly: head = media_time, effective = segment_duration, both
//! converted to source frames by exact rational arithmetic.

use crate::common::*;
use crate::mpeg::{skip_id3v2, trailing_tags};
use symphonia_core::codecs::audio::well_known::CODEC_ID_AAC;
use symphonia_core::codecs::audio::{AudioCodecParameters, AudioDecoder, AudioDecoderOptions};
use symphonia_core::packet::PacketRef;
use symphonia_core::units::{Duration, Timestamp};

const SF: [u32; 13] = [96000, 88200, 64000, 48000, 44100, 32000, 24000, 22050, 16000, 12000, 11025, 8000, 7350];

/// The validated subset of an AudioSpecificConfig INGEST-1 admits.
struct Asc {
    rate: u32,
    channels: u32,
}

struct BitR<'a> {
    b: &'a [u8],
    pos: usize,
}
impl BitR<'_> {
    fn left(&self) -> usize {
        self.b.len() * 8 - self.pos
    }
    fn get(&mut self, n: u32) -> Res<u32> {
        if self.left() < n as usize {
            return refuse("AAC AudioSpecificConfig is truncated");
        }
        let mut v = 0u32;
        for _ in 0..n {
            v = (v << 1) | ((self.b[self.pos >> 3] >> (7 - (self.pos & 7))) & 1) as u32;
            self.pos += 1;
        }
        Ok(v)
    }
}

fn object_type_name(aot: u32) -> String {
    match aot {
        1 => "AAC Main".into(),
        3 => "AAC SSR".into(),
        4 => "AAC LTP".into(),
        5 => "HE-AAC (SBR)".into(),
        29 => "HE-AACv2 (PS)".into(),
        23 => "AAC-LD".into(),
        39 => "AAC-ELD".into(),
        42 => "xHE-AAC (USAC)".into(),
        n => format!("audio object type {n}"),
    }
}

fn parse_asc(d: &[u8]) -> Res<Asc> {
    let mut r = BitR { b: d, pos: 0 };
    let mut aot = r.get(5)?;
    if aot == 31 {
        aot = 32 + r.get(6)?;
    }
    if aot != 2 {
        return refuse(format!("{} is outside INGEST-1 (AAC-LC only)", object_type_name(aot)));
    }
    let sfi = r.get(4)?;
    let rate = if sfi == 15 {
        r.get(24)?
    } else {
        *SF.get(sfi as usize).ok_or_else(|| Fail::Refuse("AAC sampling-frequency index is reserved".into()))?
    };
    let cc = r.get(4)?;
    match cc {
        0 => return refuse("AAC with a program config element (channel config 0) is unsupported"),
        1 | 2 => {}
        n => return refuse(format!("AAC channel configuration {n} is not mono or stereo")),
    }
    // GASpecificConfig
    if r.get(1)? == 1 {
        return refuse("AAC 960-sample frames are unsupported");
    }
    if r.get(1)? == 1 {
        return refuse("AAC dependsOnCoreCoder is unsupported");
    }
    if r.get(1)? == 1 {
        return refuse("AAC GASpecificConfig extension flag is unsupported for AAC-LC");
    }
    // Backward-compatible explicit SBR/PS signalling.
    if r.left() >= 16 {
        let sync = r.get(11)?;
        if sync == 0x2B7 {
            let ext = r.get(5)?;
            if ext == 5 && r.get(1)? == 1 {
                return refuse("HE-AAC (explicit SBR signalling) is outside INGEST-1");
            }
        }
    }
    Ok(Asc { rate, channels: cc })
}

fn make_asc(sfi: u32, cc: u32) -> [u8; 2] {
    let v: u16 = (2 << 11) | ((sfi as u16) << 7) | ((cc as u16) << 3);
    v.to_be_bytes()
}

fn decode_units(units: &[&[u8]], asc_bytes: &[u8], asc: &Asc) -> Res<Vec<Vec<f64>>> {
    let mut params = AudioCodecParameters::new();
    params.for_codec(CODEC_ID_AAC).with_extra_data(asc_bytes.to_vec().into_boxed_slice());
    let mut dec = symphonia_codec_aac::AacDecoder::try_new(&params, &AudioDecoderOptions::default())
        .map_err(|e| Fail::Refuse(format!("AAC decoder refused the stream configuration ({e})")))?;
    let ch = asc.channels as usize;
    let mut planes: Vec<Vec<f64>> = vec![Vec::with_capacity(units.len() * 1024); ch];
    let mut tmp: Vec<Vec<f32>> = Vec::new();
    for (i, u) in units.iter().enumerate() {
        let pkt = PacketRef::new(0, Timestamp::new(i as i64 * 1024), Duration::new(1024), u);
        let buf = dec.decode_ref(&pkt).map_err(|e| {
            let s = e.to_string();
            if s.contains("sbr extension present") {
                Fail::Refuse("HE-AAC (SBR data in the stream) is outside INGEST-1".into())
            } else {
                Fail::Refuse(format!("AAC access unit {i} does not decode ({s}) (corrupt)"))
            }
        })?;
        if buf.frames() != 1024 || buf.spec().channels().count() != ch {
            return refuse(format!("AAC access unit {i} decoded to an unexpected length or layout"));
        }
        buf.copy_to_vecs_planar::<f32>(&mut tmp);
        for (p, t) in planes.iter_mut().zip(&tmp) {
            p.extend(t.iter().map(|&v| v as f64));
        }
    }
    Ok(planes)
}

pub fn decode_adts(b: &[u8]) -> Res<Decoded> {
    let start = skip_id3v2(b)?;
    let end = trailing_tags(b, start)?;
    let mut o = start;
    let mut units: Vec<&[u8]> = Vec::new();
    let mut first: Option<(u32, u32, u32)> = None;
    while o < end {
        if end - o < 7 {
            return refuse("ADTS header is truncated");
        }
        let h = &b[o..o + 7];
        if h[0] != 0xFF || h[1] & 0xF0 != 0xF0 {
            return refuse("ADTS sync lost (corrupt data or junk between frames)");
        }
        if (h[1] >> 1) & 3 != 0 {
            return refuse("ADTS layer field is not zero (corrupt)");
        }
        let crc_present = h[1] & 1 == 0;
        let profile = (h[2] >> 6) as u32;
        let sfi = ((h[2] >> 2) & 0xF) as u32;
        let cc = (((h[2] & 1) << 2) | (h[3] >> 6)) as u32;
        let len = (((h[3] & 3) as usize) << 11) | ((h[4] as usize) << 3) | (h[5] as usize >> 5);
        let blocks = (h[6] & 3) as u32;
        if profile != 1 {
            return refuse(format!("{} is outside INGEST-1 (AAC-LC only)", object_type_name(profile + 1)));
        }
        let hl = if crc_present { 9 } else { 7 };
        if len < hl || o + len > end {
            return refuse("ADTS frame length is invalid or the last frame is truncated");
        }
        if blocks != 0 {
            return refuse("ADTS frames with more than one raw data block are unsupported");
        }
        let cfg = (profile, sfi, cc);
        match first {
            None => first = Some(cfg),
            Some(f) if f != cfg => return refuse("ADTS sample rate or channel configuration changes mid-stream"),
            _ => {}
        }
        units.push(&b[o + hl..o + len]);
        o += len;
    }
    let Some((_, sfi, cc)) = first else { return refuse("the ADTS stream holds no frames") };
    if sfi as usize >= SF.len() {
        return refuse("ADTS sampling-frequency index is reserved");
    }
    let asc_bytes = make_asc(sfi, cc);
    let asc = parse_asc(&asc_bytes)?;
    let planes = decode_units(&units, &asc_bytes, &asc)?;
    Decoded {
        container: "adts",
        codec: "aac",
        codec_profile: "aac-lc".into(),
        rate: asc.rate,
        channels: asc.channels,
        raw_frames: units.len() as u64 * 1024,
        trim: Trim::unknown(),
        planes,
    }
    .finish()
}

// ---- ISO BMFF -------------------------------------------------------------------------

struct Boxx<'a> {
    typ: [u8; 4],
    body: &'a [u8],
}

fn boxes(b: &[u8], top: bool) -> Res<Vec<Boxx<'_>>> {
    let mut out = Vec::new();
    let mut o = 0usize;
    while o < b.len() {
        if b.len() - o < 8 {
            return refuse("MP4 box header is truncated");
        }
        let size32 = u32be(b, o) as u64;
        let mut typ = [0u8; 4];
        typ.copy_from_slice(&b[o + 4..o + 8]);
        let (hl, size) = match size32 {
            1 => {
                if b.len() - o < 16 {
                    return refuse("MP4 box header is truncated");
                }
                (16usize, u64be(b, o + 8))
            }
            0 if top => (8, (b.len() - o) as u64),
            0 => return refuse("MP4 nested box with size 0 is invalid"),
            s => (8, s),
        };
        if size < hl as u64 || size > (b.len() - o) as u64 {
            return refuse(format!("MP4 box '{}' runs past its parent (truncated)", String::from_utf8_lossy(&typ)));
        }
        out.push(Boxx { typ, body: &b[o + hl..o + size as usize] });
        o += size as usize;
    }
    Ok(out)
}

fn child<'a>(list: &'a [Boxx<'a>], t: &[u8; 4]) -> Res<Option<&'a Boxx<'a>>> {
    let mut it = list.iter().filter(|x| &x.typ == t);
    let f = it.next();
    if it.next().is_some() {
        return refuse(format!("MP4 has more than one '{}' box where one is allowed", String::from_utf8_lossy(t)));
    }
    Ok(f)
}

fn need<'a>(list: &'a [Boxx<'a>], t: &[u8; 4]) -> Res<&'a Boxx<'a>> {
    child(list, t)?.ok_or_else(|| Fail::Refuse(format!("MP4 is missing its '{}' box", String::from_utf8_lossy(t))))
}

fn chk(b: &[u8], n: usize) -> Res<()> {
    if b.len() < n {
        refuse("MP4 box is too short (truncated)")
    } else {
        Ok(())
    }
}

/// Read an MPEG-4 descriptor header: (tag, body).
fn descriptor(b: &[u8], o: usize) -> Res<(u8, usize, usize)> {
    chk(b, o + 2)?;
    let tag = b[o];
    let mut len = 0usize;
    let mut p = o + 1;
    for _ in 0..4 {
        chk(b, p + 1)?;
        let x = b[p];
        p += 1;
        len = (len << 7) | (x & 0x7F) as usize;
        if x & 0x80 == 0 {
            break;
        }
    }
    if p + len > b.len() {
        return refuse("MP4 esds descriptor runs past its box");
    }
    Ok((tag, p, p + len))
}

fn esds_asc(e: &[u8]) -> Res<Vec<u8>> {
    chk(e, 4)?;
    let (tag, s, end) = descriptor(e, 4)?;
    if tag != 3 {
        return refuse("MP4 esds lacks an ES_Descriptor");
    }
    let es = &e[..end];
    chk(es, s + 3)?;
    let flags = es[s + 2];
    let mut p = s + 3;
    if flags & 0x80 != 0 {
        p += 2;
    }
    if flags & 0x40 != 0 {
        chk(es, p + 1)?;
        p += 1 + es[p] as usize;
    }
    if flags & 0x20 != 0 {
        p += 2;
    }
    let (tag, s, end) = descriptor(es, p)?;
    if tag != 4 {
        return refuse("MP4 esds lacks a DecoderConfigDescriptor");
    }
    let dc = &es[..end];
    chk(dc, s + 13)?;
    let oti = dc[s];
    match oti {
        0x40 | 0x67 => {}
        0x66 => return refuse("MPEG-2 AAC Main is outside INGEST-1 (AAC-LC only)"),
        0x68 => return refuse("MPEG-2 AAC SSR is outside INGEST-1 (AAC-LC only)"),
        0x69 | 0x6B => return refuse("MP3 inside MP4 is outside INGEST-1"),
        n => return refuse(format!("MP4 audio object type indication 0x{n:02X} is unsupported")),
    }
    let (tag, s, end) = descriptor(dc, s + 13)?;
    if tag != 5 {
        return refuse("MP4 esds lacks a DecoderSpecificInfo (AudioSpecificConfig)");
    }
    Ok(dc[s..end].to_vec())
}

fn find_itunsmpb(moov: &[Boxx]) -> Res<Option<(u64, u64, u64)>> {
    let Some(udta) = child(moov, b"udta")? else { return Ok(None) };
    let ud = boxes(udta.body, false)?;
    let Some(meta) = child(&ud, b"meta")? else { return Ok(None) };
    // ISO meta is a full box; QuickTime-style meta is not.
    let body = if meta.body.len() >= 8 && &meta.body[4..8] == b"hdlr" { meta.body } else {
        chk(meta.body, 4)?;
        &meta.body[4..]
    };
    let mb = boxes(body, false)?;
    let Some(ilst) = child(&mb, b"ilst")? else { return Ok(None) };
    for item in boxes(ilst.body, false)? {
        if &item.typ != b"----" {
            continue;
        }
        let parts = boxes(item.body, false)?;
        let name = parts.iter().find(|x| &x.typ == b"name");
        let is_smpb = name.is_some_and(|n| n.body.len() >= 4 && &n.body[4..] == b"iTunSMPB");
        if !is_smpb {
            continue;
        }
        let Some(data) = parts.iter().find(|x| &x.typ == b"data") else {
            return refuse("iTunSMPB has no data (invalid metadata)");
        };
        chk(data.body, 8)?;
        let text = std::str::from_utf8(&data.body[8..]).or_else(|_| refuse("iTunSMPB is not text (invalid metadata)"))?;
        let f: Vec<&str> = text.split_ascii_whitespace().collect();
        let hex = |i: usize| -> Res<u64> {
            f.get(i)
                .and_then(|s| u64::from_str_radix(s, 16).ok())
                .ok_or_else(|| Fail::Refuse("iTunSMPB is malformed (invalid metadata)".into()))
        };
        return Ok(Some((hex(1)?, hex(2)?, hex(3)?)));
    }
    Ok(None)
}

/// Exact `v * num / den`, refusing a fractional result.
fn exact(v: u64, num: u64, den: u64, what: &str) -> Res<u64> {
    let p = v as u128 * num as u128;
    if den == 0 || p % den as u128 != 0 {
        return refuse(format!("{what} is not a whole number of source frames (fractional trim interval)"));
    }
    u64::try_from(p / den as u128).or_else(|_| refuse(format!("{what} is out of range")))
}

pub fn decode_mp4(b: &[u8]) -> Res<Decoded> {
    let top = boxes(b, true)?;
    if top.first().map(|x| &x.typ) != Some(b"ftyp") {
        return refuse("MP4 does not begin with an 'ftyp' box");
    }
    if top.iter().any(|x| &x.typ == b"moof" || &x.typ == b"mvex") {
        return refuse("fragmented MP4 is unsupported");
    }
    let moov_b = need(&top, b"moov")?;
    let moov = boxes(moov_b.body, false)?;
    if moov.iter().any(|x| &x.typ == b"pssh") {
        return refuse("protected (encrypted) MP4 is refused");
    }
    if moov.iter().any(|x| &x.typ == b"mvex") {
        return refuse("fragmented MP4 is unsupported");
    }
    let mvhd = need(&moov, b"mvhd")?.body;
    chk(mvhd, 24)?;
    let movie_ts = if mvhd[0] == 1 {
        chk(mvhd, 32)?;
        u32be(mvhd, 20)
    } else {
        u32be(mvhd, 12)
    } as u64;

    let mut audio: Option<Vec<Boxx>> = None;
    for t in moov.iter().filter(|x| &x.typ == b"trak") {
        let tk = boxes(t.body, false)?;
        let mdia = boxes(need(&tk, b"mdia")?.body, false)?;
        let hdlr = need(&mdia, b"hdlr")?.body;
        chk(hdlr, 12)?;
        match &hdlr[8..12] {
            b"soun" => {
                if audio.replace(tk).is_some() {
                    return refuse("MP4 holds more than one audio stream");
                }
            }
            b"vide" => return refuse("MP4 holds a video stream; INGEST-1 accepts audio-only M4A"),
            _ => {}
        }
    }
    let Some(tk) = audio else { return refuse("MP4 holds no audio stream") };
    let mdia = boxes(need(&tk, b"mdia")?.body, false)?;
    let mdhd = need(&mdia, b"mdhd")?.body;
    chk(mdhd, 24)?;
    let media_ts = if mdhd[0] == 1 {
        chk(mdhd, 32)?;
        u32be(mdhd, 20)
    } else {
        u32be(mdhd, 12)
    } as u64;
    let minf = boxes(need(&mdia, b"minf")?.body, false)?;
    let stbl = boxes(need(&minf, b"stbl")?.body, false)?;

    // Sample description: exactly one unencrypted mp4a/AAC-LC entry.
    let stsd = need(&stbl, b"stsd")?.body;
    chk(stsd, 8)?;
    if u32be(stsd, 4) != 1 {
        return refuse("MP4 audio track has more than one sample description");
    }
    let entries = boxes(&stsd[8..], false)?;
    let entry = entries.first().ok_or_else(|| Fail::Refuse("MP4 sample description is empty".into()))?;
    match &entry.typ {
        b"mp4a" => {}
        b"enca" | b"drms" | b"drmi" => return refuse("protected (encrypted) AAC is refused"),
        b"alac" => return refuse("ALAC is outside INGEST-1"),
        t => return refuse(format!("MP4 audio codec '{}' is outside INGEST-1", String::from_utf8_lossy(t))),
    }
    let se = entry.body;
    chk(se, 28)?;
    let sd_version = u16be(se, 8);
    let ext = match sd_version {
        0 => 28,
        1 => 44,
        2 => 64,
        _ => return refuse("MP4 sound description version is unsupported"),
    };
    chk(se, ext)?;
    let mut kids = boxes(&se[ext..], false)?;
    if let Some(w) = kids.iter().position(|x| &x.typ == b"wave") {
        let wb = kids[w].body;
        kids = boxes(wb, false)?;
    }
    if kids.iter().any(|x| &x.typ == b"sinf") {
        return refuse("protected (encrypted) AAC is refused");
    }
    let esds = need(&kids, b"esds")?.body;
    let asc_bytes = esds_asc(esds)?;
    let asc = parse_asc(&asc_bytes)?;

    // Sample table.
    let stts = need(&stbl, b"stts")?.body;
    chk(stts, 8)?;
    let n = u32be(stts, 4) as usize;
    chk(stts, 8 + n * 8)?;
    // Every access unit lasts 1024 frames in media time, except that the final sample may
    // be shortened: a redundant end declaration admitted only in exact agreement with the
    // edit list below.
    let unit = exact(1024, media_ts, asc.rate as u64, "an AAC access unit in MP4 media time")?;
    let mut units_count: u64 = 0;
    let mut media_total: u128 = 0;
    let mut short_end = false;
    for i in 0..n {
        let c = u32be(stts, 8 + i * 8) as u64;
        let d = u32be(stts, 12 + i * 8) as u64;
        let last_single = i + 1 == n && c == 1;
        if d != unit && !(last_single && d > 0 && d < unit) {
            return refuse("MP4 sample durations do not describe whole 1024-frame AAC access units (unsupported trim signalling)");
        }
        short_end |= d != unit;
        units_count += c;
        media_total += c as u128 * d as u128;
    }
    let sizes: Vec<u64> = if let Some(stsz) = child(&stbl, b"stsz")? {
        let s = stsz.body;
        chk(s, 12)?;
        let fixed = u32be(s, 4) as u64;
        let cnt = u32be(s, 8) as usize;
        if fixed != 0 {
            vec![fixed; cnt]
        } else {
            chk(s, 12 + cnt * 4)?;
            (0..cnt).map(|i| u32be(s, 12 + i * 4) as u64).collect()
        }
    } else {
        return refuse("MP4 audio track has no 'stsz' sample-size table");
    };
    if sizes.len() as u64 != units_count {
        return refuse("MP4 sample-size and time-to-sample tables disagree");
    }
    let offsets: Vec<u64> = if let Some(stco) = child(&stbl, b"stco")? {
        let s = stco.body;
        chk(s, 8)?;
        let c = u32be(s, 4) as usize;
        chk(s, 8 + c * 4)?;
        (0..c).map(|i| u32be(s, 8 + i * 4) as u64).collect()
    } else if let Some(co64) = child(&stbl, b"co64")? {
        let s = co64.body;
        chk(s, 8)?;
        let c = u32be(s, 4) as usize;
        chk(s, 8 + c * 8)?;
        (0..c).map(|i| u64be(s, 8 + i * 8)).collect()
    } else {
        return refuse("MP4 audio track has no chunk-offset table");
    };
    let stsc = need(&stbl, b"stsc")?.body;
    chk(stsc, 8)?;
    let sc = u32be(stsc, 4) as usize;
    chk(stsc, 8 + sc * 12)?;
    let runs: Vec<(u64, u64)> = (0..sc).map(|i| (u32be(stsc, 8 + i * 12) as u64, u32be(stsc, 12 + i * 12) as u64)).collect();
    let mut units: Vec<&[u8]> = Vec::with_capacity(sizes.len());
    let mut si = 0usize;
    for (ci, &off) in offsets.iter().enumerate() {
        let chunk_no = ci as u64 + 1;
        let per = runs.iter().rev().find(|r| r.0 <= chunk_no).map(|r| r.1).unwrap_or(0);
        let mut p = off;
        for _ in 0..per {
            let Some(&sz) = sizes.get(si) else { return refuse("MP4 sample-to-chunk table names more samples than exist") };
            let e = p.checked_add(sz).filter(|&e| e <= b.len() as u64);
            let Some(e) = e else { return refuse("MP4 sample data runs past the end of the file (truncated)") };
            units.push(&b[p as usize..e as usize]);
            p = e;
            si += 1;
        }
    }
    if units.len() != sizes.len() {
        return refuse("MP4 sample-to-chunk table does not cover every sample");
    }
    if units.is_empty() {
        return refuse("MP4 audio track holds zero samples");
    }
    let raw = units.len() as u64 * 1024;

    // Presentation interval.
    let mut trim = Trim::unknown();
    if let Some(edts) = child(&tk, b"edts")? {
        let eb = boxes(edts.body, false)?;
        if let Some(elst) = child(&eb, b"elst")? {
            let e = elst.body;
            chk(e, 8)?;
            let v1 = e[0] == 1;
            let cnt = u32be(e, 4) as usize;
            let w = if v1 { 20 } else { 12 };
            chk(e, 8 + cnt * w)?;
            if cnt != 1 {
                return refuse(format!("MP4 edit list has {cnt} entries; only one contiguous presentation interval is admitted"));
            }
            let (dur, mt, rate) = if v1 {
                (u64be(e, 8), u64be(e, 16) as i64, u32be(e, 24))
            } else {
                (u32be(e, 8) as u64, u32be(e, 12) as i32 as i64, u32be(e, 16))
            };
            if rate != 0x0001_0000 {
                return refuse("MP4 edit with a media rate other than 1 is unsupported");
            }
            if mt < 0 {
                return refuse("MP4 empty edit (inserted delay) is not an admitted presentation interval");
            }
            if dur == 0 {
                return refuse("MP4 edit with zero duration is ambiguous");
            }
            let head = exact(mt as u64, asc.rate as u64, media_ts, "MP4 edit media time")?;
            let eff = exact(dur, asc.rate as u64, movie_ts, "MP4 edit segment duration")?;
            let Some(tail) = raw.checked_sub(head).and_then(|r| r.checked_sub(eff)) else {
                return refuse("MP4 edit list extends past the decoded stream (out of range)");
            };
            if short_end && (mt as u128 * movie_ts as u128 + dur as u128 * media_ts as u128) != media_total * movie_ts as u128 {
                return refuse("the MP4 shortened final sample contradicts the edit list end");
            }
            trim = Trim { head, tail, evidence: "bmff_edit", known: true };
        }
    }
    if short_end && !trim.known {
        return refuse("an MP4 shortened final sample without an edit list is unsupported trim signalling");
    }
    match (find_itunsmpb(&moov)?, trim.known) {
        (Some(_), false) => return refuse("iTunSMPB alone is not an admitted trim interval in INGEST-1"),
        (Some((pri, pad, len)), true) => {
            if pri != trim.head || len != raw - trim.head - trim.tail || pad != trim.tail {
                return refuse("iTunSMPB contradicts the MP4 edit list");
            }
        }
        _ => {}
    }
    let planes = decode_units(&units, &asc_bytes, &asc)?;
    Decoded {
        container: "mp4",
        codec: "aac",
        codec_profile: "aac-lc".into(),
        rate: asc.rate,
        channels: asc.channels,
        raw_frames: raw,
        trim,
        planes,
    }
    .finish()
}

/// True when bytes at `o` begin an ADTS header.
pub fn looks_like_adts(b: &[u8], o: usize) -> bool {
    b.len() >= o + 7 && b[o] == 0xFF && b[o + 1] & 0xF6 == 0xF0
}
