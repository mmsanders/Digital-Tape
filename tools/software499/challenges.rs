//! Mechanical calls to the exact b9f430c library; no Product source is edited.
use ingest::{common::*, dsp};
fn main() {
    let a: Vec<String> = std::env::args().skip(1).collect();
    let n = |i: usize| a[i].parse::<u64>().unwrap();
    match a[0].as_str() {
        "frames" => match dsp::output_frames(n(1), n(2) as u32) {
            Some(v) => println!("{{\"value\":{v}}}"), None => println!("{{\"value\":null}}"),
        },
        "trim" => {
            // Constructed guard discriminator. Empty planes deliberately avoid
            // allocating u64::MAX samples and are NOT an admitted decoder state.
            let d = Decoded { container:"guard",codec:"guard",codec_profile:String::new(),rate:44100,channels:1,raw_frames:n(1),trim:Trim {head:n(2),tail:n(3),known:true,evidence:"model"},planes:Vec::new() };
            match d.finish() {
                Ok(d) => println!("{{\"value\":{},\"constructed_empty_planes\":true}}",d.effective_frames()),
                Err(e) => println!("{{\"value\":null,\"error_id\":\"{}\",\"constructed_empty_planes\":true}}",e.id),
            }
        }
        "pcm_count" => {
            let (len,c,w)=(n(1) as usize,n(2) as usize,n(3) as usize);
            // The WAV caller's divisibility premise, NOT an added inner guard.
            if len % (c*w) != 0 { println!("{{\"value\":null,\"caller_divisibility_refusal\":true}}");return; }
            let fmt=match w {1=>Pcm::U8,2=>Pcm::S16Le,3=>Pcm::S24Le,4=>Pcm::F32Le,8=>Pcm::F64Le,_=>panic!()};
            let p=deinterleave(&vec![0u8;len],fmt,c).unwrap();
            assert_eq!(p.len(),c);assert!(p.iter().all(|x|x.len()==len/(c*w)));
            println!("{{\"value\":{},\"actual_planes\":{},\"actual_plane_lengths\":{:?}}}",p[0].len(),p.len(),p.iter().map(Vec::len).collect::<Vec<_>>());
        }
        "channels" => {
            let left=n(1) as usize;let right=a[2].parse::<usize>().ok();let requested=n(3) as usize;
            let l=vec![0.0;left];let r=right.map(|v|vec![0.0;v]);
            let p=dsp::quantize(&l,r.as_deref(),1.0).unwrap().unwrap();
            let valid=right.map_or(true,|v|v==left)&&p.len()==left*2&&requested==p.len();
            println!("{{\"value\":{valid},\"actual_samples\":{},\"right_equals_left\":{}}}",p.len(),right.map_or(true,|v|v==left));
        }
        _ => panic!("unissued native operation"),
    }
}
