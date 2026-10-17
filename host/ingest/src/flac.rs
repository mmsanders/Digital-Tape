//! Native FLAC decoder (RFC 9639). Integer-exact; every frame's CRC-8/CRC-16 and the
//! STREAMINFO MD5 (when present) are verified, so corruption refuses rather than conceals.

use crate::common::*;
use md5::{Digest, Md5};

struct Bits<'a> {
    b: &'a [u8],
    pos: usize, // bit position
}

impl<'a> Bits<'a> {
    fn new(b: &'a [u8], byte: usize) -> Self {
        Bits { b, pos: byte * 8 }
    }
    fn bit(&mut self) -> Res<u32> {
        let byte = self.pos >> 3;
        if byte >= self.b.len() {
            return refuse(SOURCE_CORRUPT, "FLAC frame is truncated");
        }
        let v = (self.b[byte] >> (7 - (self.pos & 7))) & 1;
        self.pos += 1;
        Ok(v as u32)
    }
    fn bits(&mut self, n: u32) -> Res<u64> {
        debug_assert!(n <= 64);
        if self.pos + n as usize > self.b.len() * 8 {
            return refuse(SOURCE_CORRUPT, "FLAC frame is truncated");
        }
        let mut v: u64 = 0;
        let mut left = n;
        while left > 0 {
            let byte = self.pos >> 3;
            let off = (self.pos & 7) as u32;
            let avail = 8 - off;
            let take = avail.min(left);
            let chunk = ((self.b[byte] as u32) >> (avail - take)) & ((1u32 << take) - 1);
            v = (v << take) | chunk as u64;
            self.pos += take as usize;
            left -= take;
        }
        Ok(v)
    }
    fn signed(&mut self, n: u32) -> Res<i64> {
        if n == 0 {
            return Ok(0);
        }
        let v = self.bits(n)?;
        let sh = 64 - n;
        Ok(((v << sh) as i64) >> sh)
    }
    fn unary(&mut self) -> Res<u64> {
        let mut q = 0u64;
        loop {
            let byte = self.pos >> 3;
            if byte >= self.b.len() {
                return refuse(SOURCE_CORRUPT, "FLAC frame is truncated");
            }
            let off = self.pos & 7;
            let rest = (self.b[byte] << off) as u32;
            if rest == 0 {
                q += (8 - off) as u64;
                self.pos += 8 - off;
                continue;
            }
            let lz = (rest as u8).leading_zeros() as usize;
            q += lz as u64;
            self.pos += lz + 1;
            return Ok(q);
        }
    }
    fn align(&mut self) -> Res<()> {
        while self.pos & 7 != 0 {
            if self.bit()? != 0 {
                return refuse(SOURCE_CORRUPT, "FLAC frame padding bits are not zero");
            }
        }
        Ok(())
    }
}

fn crc8(d: &[u8]) -> u8 {
    let mut c: u8 = 0;
    for &x in d {
        c ^= x;
        for _ in 0..8 {
            c = if c & 0x80 != 0 { (c << 1) ^ 0x07 } else { c << 1 };
        }
    }
    c
}

fn crc16(d: &[u8]) -> u16 {
    let mut c: u16 = 0;
    for &x in d {
        c ^= (x as u16) << 8;
        for _ in 0..8 {
            c = if c & 0x8000 != 0 { (c << 1) ^ 0x8005 } else { c << 1 };
        }
    }
    c
}

struct Info {
    rate: u32,
    channels: u32,
    bps: u32,
    total: u64,
    md5: [u8; 16],
    max_block: u32,
}

fn residual(r: &mut Bits, block: usize, order: usize, out: &mut Vec<i64>) -> Res<()> {
    let method = r.bits(2)?;
    let pbits = match method {
        0 => 4,
        1 => 5,
        _ => return refuse(SOURCE_CORRUPT, "FLAC reserved residual coding method"),
    };
    let porder = r.bits(4)? as u32;
    let parts = 1usize << porder;
    if block % parts != 0 || (block >> porder) < order {
        return refuse(SOURCE_CORRUPT, "FLAC residual partition order is invalid for the block");
    }
    let escape = (1u64 << pbits) - 1;
    for p in 0..parts {
        let n = (block >> porder) - if p == 0 { order } else { 0 };
        let k = r.bits(pbits)?;
        if k == escape {
            let w = r.bits(5)? as u32;
            for _ in 0..n {
                out.push(r.signed(w)?);
            }
        } else {
            let k = k as u32;
            for _ in 0..n {
                let q = r.unary()?;
                if q > (1u64 << 40) {
                    return refuse(SOURCE_CORRUPT, "FLAC residual is out of range");
                }
                let u = (q << k) | r.bits(k)?;
                out.push(((u >> 1) as i64) ^ -((u & 1) as i64));
            }
        }
    }
    Ok(())
}

fn subframe(r: &mut Bits, block: usize, bps: u32) -> Res<Vec<i64>> {
    if r.bit()? != 0 {
        return refuse(SOURCE_CORRUPT, "FLAC subframe padding bit is not zero");
    }
    let t = r.bits(6)? as u32;
    let mut wasted = 0u32;
    if r.bit()? == 1 {
        wasted = 1 + r.unary()? as u32;
        if wasted >= bps {
            return refuse(SOURCE_CORRUPT, "FLAC wasted-bits count is invalid");
        }
    }
    let bps = bps - wasted;
    let mut s: Vec<i64> = Vec::with_capacity(block);
    match t {
        0 => {
            let v = r.signed(bps)?;
            s.resize(block, v);
        }
        1 => {
            for _ in 0..block {
                s.push(r.signed(bps)?);
            }
        }
        8..=12 => {
            let order = (t - 8) as usize;
            if order > block {
                return refuse(SOURCE_CORRUPT, "FLAC predictor order exceeds the block size");
            }
            for _ in 0..order {
                s.push(r.signed(bps)?);
            }
            let mut res = Vec::with_capacity(block - order);
            residual(r, block, order, &mut res)?;
            for (i, e) in res.into_iter().enumerate() {
                let n = i + order;
                let p = match order {
                    0 => 0,
                    1 => s[n - 1],
                    2 => 2 * s[n - 1] - s[n - 2],
                    3 => 3 * s[n - 1] - 3 * s[n - 2] + s[n - 3],
                    _ => 4 * s[n - 1] - 6 * s[n - 2] + 4 * s[n - 3] - s[n - 4],
                };
                s.push(p.checked_add(e).ok_or_else(|| Fail::refuse(SOURCE_CORRUPT, "FLAC sample overflow"))?);
            }
        }
        32..=63 => {
            let order = (t - 31) as usize;
            if order > block {
                return refuse(SOURCE_CORRUPT, "FLAC predictor order exceeds the block size");
            }
            for _ in 0..order {
                s.push(r.signed(bps)?);
            }
            let prec = r.bits(4)? as u32;
            if prec == 15 {
                return refuse(SOURCE_CORRUPT, "FLAC invalid LPC precision");
            }
            let prec = prec + 1;
            let shift = r.signed(5)?;
            if shift < 0 {
                return refuse(SOURCE_CORRUPT, "FLAC negative LPC shift");
            }
            let mut coef = Vec::with_capacity(order);
            for _ in 0..order {
                coef.push(r.signed(prec)?);
            }
            let mut res = Vec::with_capacity(block - order);
            residual(r, block, order, &mut res)?;
            for (i, e) in res.into_iter().enumerate() {
                let n = i + order;
                let mut acc: i128 = 0;
                for (j, c) in coef.iter().enumerate() {
                    acc += *c as i128 * s[n - 1 - j] as i128;
                }
                let v = (acc >> shift) + e as i128;
                let v = i64::try_from(v).or_else(|_| refuse(SOURCE_CORRUPT, "FLAC sample overflow"))?;
                s.push(v);
            }
        }
        _ => return refuse(SOURCE_CORRUPT, "FLAC reserved subframe type"),
    }
    let lim = 1i64 << (bps - 1);
    if s.iter().any(|&v| v < -lim || v >= lim) {
        return refuse(SOURCE_CORRUPT, "FLAC decoded sample exceeds its bit depth");
    }
    if wasted > 0 {
        for v in s.iter_mut() {
            *v <<= wasted;
        }
    }
    Ok(s)
}

/// Read the UTF-8-style coded frame/sample number.
fn coded_number(r: &mut Bits) -> Res<u64> {
    let first = r.bits(8)? as u8;
    let (mut v, extra) = match first.leading_ones() {
        0 => (first as u64, 0),
        n @ 2..=7 => (((first as u32) & (0x7F >> n)) as u64, n - 1),
        _ => return refuse(SOURCE_CORRUPT, "FLAC invalid coded frame number"),
    };
    for _ in 0..extra {
        let b = r.bits(8)?;
        if b & 0xC0 != 0x80 {
            return refuse(SOURCE_CORRUPT, "FLAC invalid coded frame number");
        }
        v = (v << 6) | (b & 0x3F);
    }
    Ok(v)
}

pub fn decode(b: &[u8]) -> Res<Decoded> {
    // Metadata blocks. STREAMINFO first.
    let mut o = 4usize;
    let mut info: Option<Info> = None;
    loop {
        if b.len() < o + 4 {
            return refuse(SOURCE_CORRUPT, "FLAC metadata is truncated");
        }
        let last = b[o] & 0x80 != 0;
        let typ = b[o] & 0x7F;
        let len = ((b[o + 1] as usize) << 16) | ((b[o + 2] as usize) << 8) | b[o + 3] as usize;
        o += 4;
        if b.len() < o + len {
            return refuse(SOURCE_CORRUPT, "FLAC metadata block runs past the end of the file");
        }
        let body = &b[o..o + len];
        if info.is_none() && typ != 0 {
            return refuse(SOURCE_CORRUPT, "FLAC STREAMINFO is not the first metadata block");
        }
        match typ {
            0 => {
                if info.is_some() {
                    return refuse(SOURCE_CORRUPT, "FLAC has more than one STREAMINFO");
                }
                if len != 34 {
                    return refuse(SOURCE_CORRUPT, "FLAC STREAMINFO has the wrong length");
                }
                let mut r = Bits::new(body, 0);
                let _min_block = r.bits(16)?;
                let max_block = r.bits(16)? as u32;
                let _ = r.bits(48)?;
                let rate = r.bits(20)? as u32;
                let channels = r.bits(3)? as u32 + 1;
                let bps = r.bits(5)? as u32 + 1;
                let total = r.bits(36)?;
                let mut md5 = [0u8; 16];
                md5.copy_from_slice(&body[18..34]);
                if rate == 0 {
                    return refuse(SOURCE_OUTSIDE_INGEST1, "FLAC STREAMINFO sample rate is zero");
                }
                info = Some(Info { rate, channels, bps, total, md5, max_block });
            }
            127 => return refuse(SOURCE_CORRUPT, "FLAC metadata block type 127 is invalid"),
            _ => {}
        }
        o += len;
        if last {
            break;
        }
    }
    let info = info.unwrap();
    check_channels(info.channels)?;
    if info.bps < 8 {
        return refuse(SOURCE_OUTSIDE_INGEST1, format!("{}-bit FLAC is outside INGEST-1 (8–32 bits)", info.bps));
    }
    check_rate(info.rate)?;
    let ch = info.channels as usize;
    let mut planes: Vec<Vec<i64>> = Vec::with_capacity(ch);
    for _ in 0..ch {
        planes.push(alloc(info.total as usize)?);
    }
    let mut next_number: u64 = 0;
    let mut samples: u64 = 0;
    let mut strategy: Option<u32> = None;
    let mut end = b.len();
    if end >= o + 128 && &b[end - 128..end - 125] == b"TAG" {
        end -= 128; // ID3v1 trailer
    }
    while o < end {
        let start = o;
        let mut r = Bits::new(&b[..end], o);
        if r.bits(14)? != 0x3FFE {
            return refuse(SOURCE_CORRUPT, "FLAC frame sync not found (corrupt or trailing data)");
        }
        if r.bit()? != 0 {
            return refuse(SOURCE_CORRUPT, "FLAC frame reserved bit is set");
        }
        let strat = r.bit()?;
        if *strategy.get_or_insert(strat) != strat {
            return refuse(SOURCE_OUTSIDE_INGEST1, "FLAC blocking strategy changes mid-stream");
        }
        let bs_code = r.bits(4)? as u32;
        let sr_code = r.bits(4)? as u32;
        let ch_code = r.bits(4)? as u32;
        let ss_code = r.bits(3)? as u32;
        if r.bit()? != 0 {
            return refuse(SOURCE_CORRUPT, "FLAC frame reserved bit is set");
        }
        let number = coded_number(&mut r)?;
        let block = match bs_code {
            0 => return refuse(SOURCE_CORRUPT, "FLAC reserved block size"),
            1 => 192,
            2..=5 => 576 << (bs_code - 2),
            6 => r.bits(8)? as usize + 1,
            7 => r.bits(16)? as usize + 1,
            _ => 256 << (bs_code - 8),
        };
        let rate = match sr_code {
            0 => info.rate,
            1 => 88200,
            2 => 176400,
            3 => 192000,
            4 => 8000,
            5 => 16000,
            6 => 22050,
            7 => 24000,
            8 => 32000,
            9 => 44100,
            10 => 48000,
            11 => 96000,
            12 => r.bits(8)? as u32 * 1000,
            13 => r.bits(16)? as u32,
            14 => r.bits(16)? as u32 * 10,
            _ => return refuse(SOURCE_CORRUPT, "FLAC invalid frame sample rate"),
        };
        let bps = match ss_code {
            0 => info.bps,
            1 => 8,
            2 => 12,
            4 => 16,
            5 => 20,
            6 => 24,
            7 => 32,
            _ => return refuse(SOURCE_CORRUPT, "FLAC reserved sample size"),
        };
        let hdr_end = r.pos / 8;
        let crc = r.bits(8)? as u8;
        if crc8(&b[start..hdr_end]) != crc {
            return refuse(SOURCE_CORRUPT, "FLAC frame header CRC-8 mismatch (corrupt)");
        }
        if rate != info.rate || bps != info.bps {
            return refuse(SOURCE_OUTSIDE_INGEST1, "FLAC sample rate or bit depth changes mid-stream");
        }
        if info.max_block != 0 && block as u32 > info.max_block {
            return refuse(SOURCE_CORRUPT, "FLAC frame block exceeds the STREAMINFO maximum");
        }
        let (fch, decor) = match ch_code {
            0..=7 => (ch_code as usize + 1, 0),
            8..=10 => (2, ch_code),
            _ => return refuse(SOURCE_CORRUPT, "FLAC reserved channel assignment"),
        };
        if fch != ch {
            return refuse(SOURCE_OUTSIDE_INGEST1, "FLAC channel count changes mid-stream");
        }
        let expect = if strat == 0 { next_number } else { samples };
        if number != expect {
            return refuse(SOURCE_CORRUPT, "FLAC frame numbering is discontinuous (missing or duplicated frame)");
        }
        let mut subs = Vec::with_capacity(ch);
        for c in 0..ch {
            let side = matches!((decor, c), (8, 1) | (9, 0) | (10, 1));
            subs.push(subframe(&mut r, block, bps + side as u32)?);
        }
        r.align()?;
        let body_end = r.pos / 8;
        let crc = r.bits(16)? as u16;
        if crc16(&b[start..body_end]) != crc {
            return refuse(SOURCE_CORRUPT, "FLAC frame CRC-16 mismatch (corrupt)");
        }
        match decor {
            8 => {
                for i in 0..block {
                    subs[1][i] = subs[0][i] - subs[1][i];
                }
            }
            9 => {
                for i in 0..block {
                    subs[0][i] += subs[1][i];
                }
            }
            10 => {
                for i in 0..block {
                    let mid = subs[0][i] << 1 | (subs[1][i] & 1);
                    let side = subs[1][i];
                    subs[0][i] = (mid + side) >> 1;
                    subs[1][i] = (mid - side) >> 1;
                }
            }
            _ => {}
        }
        for (p, s) in planes.iter_mut().zip(subs) {
            p.extend_from_slice(&s);
        }
        samples += block as u64;
        next_number += 1;
        o = r.pos / 8;
    }
    if info.total != 0 && info.total != samples {
        return refuse(SOURCE_CORRUPT, format!(
            "FLAC STREAMINFO declares {} samples but the stream holds {} (truncated or corrupt)",
            info.total, samples
        ));
    }
    if info.md5 != [0u8; 16] {
        let w = info.bps.div_ceil(8) as usize;
        let mut h = Md5::new();
        let mut buf = Vec::with_capacity(4096 * ch * w);
        for i in 0..samples as usize {
            for p in &planes {
                buf.extend_from_slice(&p[i].to_le_bytes()[..w]);
            }
            if buf.len() >= 4096 * ch * w {
                h.update(&buf);
                buf.clear();
            }
        }
        h.update(&buf);
        if h.finalize()[..] != info.md5 {
            return refuse(SOURCE_CORRUPT, "FLAC audio MD5 does not match STREAMINFO (corrupt)");
        }
    }
    let scale = 1.0 / (1u64 << (info.bps - 1)) as f64;
    let planes = planes
        .into_iter()
        .map(|p| p.into_iter().map(|v| v as f64 * scale).collect())
        .collect();
    Decoded {
        container: "flac",
        codec: "flac",
        codec_profile: format!("flac-{}bit", info.bps),
        rate: info.rate,
        channels: info.channels,
        raw_frames: samples,
        trim: Trim::lossless(),
        planes,
    }
    .finish()
}
