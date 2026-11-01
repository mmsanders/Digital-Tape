//! Encode a generated tone with the FDK reference encoder as ADTS AAC-LC with
//! protection (CRC) on. usage: fdkgen RATE CHANNELS SECONDS OUT
use fdk_aac_sys::*;
use std::ptr;
fn main() {
    let a: Vec<String> = std::env::args().collect();
    let rate: u32 = a[1].parse().unwrap();
    let ch: u32 = a[2].parse().unwrap();
    let secs: f64 = a[3].parse().unwrap();
    unsafe {
        let mut h: HANDLE_AACENCODER = ptr::null_mut();
        assert_eq!(aacEncOpen(&mut h, 0, ch), 0);
        for (p, v) in [
            (AACENC_PARAM_AACENC_AOT, 2u32),
            (AACENC_PARAM_AACENC_SAMPLERATE, rate),
            (AACENC_PARAM_AACENC_CHANNELMODE, ch),
            (AACENC_PARAM_AACENC_BITRATE, 64000 * ch),
            (AACENC_PARAM_AACENC_TRANSMUX, 2),
            (AACENC_PARAM_AACENC_PROTECTION, 1),
        ] {
            assert_eq!(aacEncoder_SetParam(h, p, v), 0, "param {p}");
        }
        assert_eq!(aacEncEncode(h, ptr::null(), ptr::null(), ptr::null(), ptr::null_mut()), 0);
        let n = (rate as f64 * secs) as usize;
        let mut pcm: Vec<i16> = Vec::with_capacity(n * ch as usize);
        for i in 0..n {
            for c in 0..ch {
                let f = 440.0 * (1.0 + c as f64);
                pcm.push((8000.0 * (2.0 * std::f64::consts::PI * f * i as f64 / rate as f64).sin()) as i16);
            }
        }
        let mut out = Vec::new();
        let mut obuf = vec![0u8; 20000];
        let mut pos = 0usize;
        loop {
            let left = pcm.len() - pos;
            let mut inp = pcm[pos..].as_mut_ptr() as *mut std::ffi::c_void;
            let mut in_id = AACENC_BufferIdentifier_IN_AUDIO_DATA as i32;
            let mut in_size = (left * 2) as i32;
            let mut in_el = 2i32;
            let ib = AACENC_BufDesc { numBufs: 1, bufs: &mut inp, bufferIdentifiers: &mut in_id, bufSizes: &mut in_size, bufElSizes: &mut in_el };
            let mut outp = obuf.as_mut_ptr() as *mut std::ffi::c_void;
            let mut out_id = AACENC_BufferIdentifier_OUT_BITSTREAM_DATA as i32;
            let mut out_size = obuf.len() as i32;
            let mut out_el = 1i32;
            let ob = AACENC_BufDesc { numBufs: 1, bufs: &mut outp, bufferIdentifiers: &mut out_id, bufSizes: &mut out_size, bufElSizes: &mut out_el };
            let ia = AACENC_InArgs { numInSamples: if left == 0 { -1 } else { left as i32 }, numAncBytes: 0 };
            let mut oa: AACENC_OutArgs = std::mem::zeroed();
            let e = aacEncEncode(h, &ib, &ob, &ia, &mut oa);
            if e == AACENC_ERROR_AACENC_ENCODE_EOF { break; }
            assert_eq!(e, 0);
            out.extend_from_slice(&obuf[..oa.numOutBytes as usize]);
            pos += oa.numInSamples as usize;
            if left == 0 && oa.numOutBytes == 0 { break; }
        }
        aacEncClose(&mut h);
        std::fs::write(&a[4], out).unwrap();
    }
}
