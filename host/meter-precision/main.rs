//! Test-only binary. All DSP/convert/common/memory operations come from pinned source.
mod common;
mod dsp;
mod convert;
mod observe;
mod mem;
use std::io::Write;
use std::sync::Mutex;
static TRACE: Mutex<Option<std::io::BufWriter<std::fs::File>>> = Mutex::new(None);
pub fn trace(s: String) {
    if let Some(f) = TRACE.lock().unwrap().as_mut() { writeln!(f,"{s}").unwrap(); }
}
fn main() {
    let a: Vec<String> = std::env::args().collect();
    *TRACE.lock().unwrap() = Some(std::io::BufWriter::new(std::fs::OpenOptions::new().write(true).create_new(true).open(&a[3]).unwrap()));
    trace(format!("{{\"kind\":\"process\",\"pid\":{}}}",std::process::id()));
    let tp = dsp::TruePeak::new().unwrap();
    let raw = std::fs::read(&a[2]).unwrap();
    if a[1] == "convert" {
        // Input is the original selected WAVE's PCM16 payload. Admission/trim
        // receipt is separately retained; this is not a fresh shipping decode.
        let channels: usize = a[5].parse().unwrap();
        let frames = raw.len() / (2*channels);
        let planes = common::deinterleave(&raw, common::Pcm::S16Le, channels).unwrap();
        let d = common::Decoded {container:"WAVE",codec:"PCM",codec_profile:"selected PCM16".into(),rate:44100,channels:channels as u32,raw_frames:frames as u64,trim:common::Trim::lossless(),planes};
        let cv = convert::convert(&d,frames as u64,&tp,0).unwrap();
        let mut f = std::fs::OpenOptions::new().write(true).create_new(true).open(&a[4]).unwrap();
        for x in cv.pcm { f.write_all(&x.to_le_bytes()).unwrap(); }
        trace(format!("{{\"kind\":\"converted\",\"frames\":{frames},\"channels\":{channels},\"gain_db_le\":\"{}\",\"limited\":{},\"status\":\"{}\"}}",dsp::s513hex(&cv.applied_gain_db.to_le_bytes()),cv.peak_limited,cv.status));
    } else {
        let x: Vec<f32> = raw.chunks_exact(4).map(|b| f32::from_le_bytes(b.try_into().unwrap())).collect();
        let coords = std::fs::read_to_string(&a[4]).unwrap();
        for line in coords.lines() {
            let mut it=line.split_whitespace();
            let n:i64=it.next().unwrap().parse().unwrap();
            let q:usize=it.next().unwrap().parse().unwrap();
            tp.s513eval(&x,n,q);
        }
        if a[1] == "stream" {
            let p=tp.peak_streamed(x.len() as i64,|start,buf| {
                trace(format!("{{\"kind\":\"fill\",\"start\":{start},\"length\":{}}}",buf.len()));
                for (i,v) in buf.iter_mut().enumerate() {let k=start+i as i64;*v=if k>=0 && k<(x.len() as i64) {x[k as usize]}else{0.0};}
            }).unwrap();
            trace(format!("{{\"kind\":\"stream-result\",\"peak_le\":\"{}\"}}",dsp::s513hex(&p.to_le_bytes())));
        }
        if a[1] == "coeff" { tp.s513coeff(&a[5]); }
    }
    TRACE.lock().unwrap().as_mut().unwrap().flush().unwrap();
}
