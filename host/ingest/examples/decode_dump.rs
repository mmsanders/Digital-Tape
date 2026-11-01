//! Development aid: decode one file and write its trimmed effective frames as raw f32le
//! interleaved (mono duplicated), for comparison against a reference decoder.
fn main() {
    let a: Vec<String> = std::env::args().collect();
    let b = std::fs::read(&a[1]).unwrap();
    let d = ingest::sniff::decode(&b).unwrap_or_else(|e| panic!("{e}"));
    let h = d.trim.head as usize;
    let e = h + d.effective_frames() as usize;
    let mut out = Vec::new();
    for i in h..e {
        for c in 0..2 {
            let p = &d.planes[if d.channels == 1 { 0 } else { c }];
            out.extend_from_slice(&(p[i] as f32).to_le_bytes());
        }
    }
    std::fs::write(&a[2], out).unwrap();
    eprintln!("{} {} Hz raw {} head {} tail {}", d.codec_profile, d.rate, d.raw_frames, d.trim.head, d.trim.tail);
}
