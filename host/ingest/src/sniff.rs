//! Identify a source by its bytes (contract §2: suffixes never admit or refuse).

use crate::common::*;
use crate::{aac, flac, mpeg, wav};

pub fn decode(b: &[u8]) -> Res<Decoded> {
    let at = |o: usize, s: &[u8]| b.len() >= o + s.len() && &b[o..o + s.len()] == s;
    if at(0, b"RIFF") && at(8, b"WAVE") {
        return wav::decode_wav(b);
    }
    if at(0, b"RF64") || at(0, b"BW64") {
        return refuse(SOURCE_OUTSIDE_INGEST1, "RF64/BW64 WAV is outside INGEST-1");
    }
    if at(0, b"riff") && at(4, &[0x2E, 0x91, 0xCF, 0x11]) {
        return refuse(SOURCE_OUTSIDE_INGEST1, "Wave64 is outside INGEST-1");
    }
    if at(0, b"FORM") && (at(8, b"AIFF") || at(8, b"AIFC")) {
        return wav::decode_aiff(b);
    }
    if at(0, b"fLaC") {
        return flac::decode(b);
    }
    if at(0, b"OggS") {
        return refuse(SOURCE_OUTSIDE_INGEST1, "Ogg streams (including Ogg-FLAC, Vorbis and Opus) are outside INGEST-1");
    }
    if at(0, b"caff") {
        return refuse(SOURCE_OUTSIDE_INGEST1, "Core Audio Format (CAF) is outside INGEST-1");
    }
    if at(4, b"ftyp") {
        return aac::decode_mp4(b);
    }
    if at(0, b"ADIF") {
        return refuse(SOURCE_OUTSIDE_INGEST1, "ADIF AAC is outside INGEST-1");
    }
    if b.len() >= 2 && b[0] == 0x56 && b[1] & 0xE0 == 0xE0 {
        return refuse(SOURCE_OUTSIDE_INGEST1, "LATM/LOAS AAC is outside INGEST-1");
    }
    // MPEG audio and ADTS may follow ID3v2 tags.
    let o = mpeg::skip_id3v2(b)?;
    if at(o, b"fLaC") {
        return refuse(SOURCE_OUTSIDE_INGEST1, "FLAC preceded by an ID3v2 tag is not native FLAC");
    }
    if aac::looks_like_adts(b, o) {
        return aac::decode_adts(b);
    }
    if mpeg::looks_like_mpeg(b, o) {
        return mpeg::decode(b);
    }
    if b.is_empty() {
        return refuse(SOURCE_NOT_AUDIO, "the file is empty");
    }
    refuse(SOURCE_NOT_AUDIO, "not a supported audio format (unrecognised bytes)")
}
