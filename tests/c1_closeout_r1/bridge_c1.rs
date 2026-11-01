// Independent APP-1 §2/§4/§6 tests. Included INSIDE the production bridge module
// only in the disposable CI checkout. No shipping source or private tests changed.
use super::*;
use crate::report::Reading;
use serde_json::json;

fn setup() -> (Arc<Bridge>,mpsc::Receiver<Message>,PathBuf) {
    let root=std::env::temp_dir().join(format!("verifier364-{}-{}",std::process::id(),children::nonce()));
    std::fs::create_dir_all(&root).unwrap();
    let (b,rx)=Bridge::channel(root.clone(),Arc::new(|_|{}));
    (b,rx,root)
}
fn ready(b:&Bridge) {
    let mut c=b.core.lock().unwrap();
    c.app.folders=vec![PathBuf::from("Music")];
    let g=c.app.begin_job("independent-checked");
    let o=Outcome{exit:Some(0),stderr:String::new(),reading:Reading::Unusable("optional success report"),total_frames:Some(44100),cancelled:false};
    assert!(c.app.finish_job(g,"independent-checked",&o));
    c.app.audio=Some(b.data.join("ordinary-audio.wav"));
    c.app.set_label("C1 Music");
    let t=c.app.begin_cards();
    assert!(c.app.finish_cards(t,&Judged{hint:Some(discovery::Hint{sizes:vec![64_000_000_000],paths:vec!["controlled-card".into()],unprobed:0}),id_specific:None},String::new()));
    assert!(c.app.view().make_enabled);
}
fn cards(paths:Vec<String>,sizes:Vec<u64>)->impl FnOnce(&jobdir::Job,&AtomicBool,&mut dyn FnMut(),&mut dyn FnMut(),Launched)->(Ran,Request) {
    move |_,_,_,_,_| {
        let nonce="0123456789abcdef0123456789abcdef";
        let mut stdout=Vec::new();
        for (path,bytes) in paths.iter().zip(&sizes) {stdout.extend(format!("{}\n",json!({"t":"card","path":path,"bytes":bytes})).as_bytes());}
        stdout.extend(format!("{}\n",json!({"t":"summary","offered":paths.len(),"unprobed":0})).as_bytes());
        let raw=format!("{{\"t\":\"start\",\"tool\":\"tapectl cards\",\"version\":\"c1-unit\",\"nonce\":\"{nonce}\"}}\n{{\"t\":\"end\",\"exit\":0}}\n");
        (Ran{exit:Some(0),stdout,report:Some(raw.into_bytes()),..Default::default()},Request{version:"c1-unit".into(),nonce:nonce.into(),..Default::default()})
    }
}
fn same()->impl FnOnce(&jobdir::Job,&AtomicBool,&mut dyn FnMut(),&mut dyn FnMut(),Launched)->(Ran,Request) {
    cards(vec!["controlled-card".into()],vec![64_000_000_000])
}

#[test]
fn app_origin_drop_file_and_mixed_zero_children() {
    for mixed in [false,true] {
        let(b,rx,root)=setup(); let file=root.join("song.wav");std::fs::write(&file,b"ordinary").unwrap();
        let folder=root.join("Music");std::fs::create_dir(&folder).unwrap();
        let payload=if mixed{json!([folder,file])}else{json!([file])};
        let v=b.drop_from(Route::ControlledTest,payload);
        assert_eq!(v.message.as_deref(),Some("Drop a folder of music, not single songs."));
        assert!(b.core.lock().unwrap().app.folders.is_empty());assert!(rx.try_recv().is_err());
        std::fs::remove_dir_all(root).unwrap();
    }
}
#[test]
fn app_origin_ingest_spawn_failure_through_worker_completion() {
    let(b,rx,root)=setup(); let folder=root.join("Music");std::fs::create_dir(&folder).unwrap();
    b.drop_from(Route::ControlledTest,json!([folder]));
    let Message::Check(work)=rx.recv().unwrap() else{panic!("no check")};
    b.execute_with(work,|_,_,_,_|Err("independent OS launch failure".into()));
    assert_eq!(b.snapshot().message.as_deref(),Some("Something went wrong. Nothing else on your computer was changed."));
    assert!(b.raw_details().contains("independent OS launch failure"));assert!(rx.try_recv().is_err());
    std::fs::remove_dir_all(root).unwrap();
}
#[test]
fn app_origin_decline_and_make_spawn_failure() {
    for declined in [true,false] {
        let(b,_rx,root)=setup();ready(&b);
        assert!(b.make_request(same()).confirm);
        *b.make_child.lock().unwrap()=Some((root.join("not-executed.exe"),"c1-unit".into()));
        *b.launch.lock().unwrap()=Arc::new(move|_,_|if declined{make::Launched::Declined}else{make::Launched::NotStarted("independent launch failure".into())});
        b.make_start(same());
        let deadline=Instant::now()+Duration::from_secs(5);
        while b.snapshot().view=="making" && Instant::now()<deadline{thread::sleep(Duration::from_millis(5));}
        let v=b.snapshot();assert_ne!(v.view,"making");
        assert_eq!(v.message.as_deref(),Some(if declined{"The computer said no, so the card wasn't changed. Press Make cartridge to try again."}else{"Something went wrong. Nothing else on your computer was changed."}));
        assert!(!b.raw_details().is_empty());
        let trace=b.trace.lock().unwrap();assert_eq!(trace.iter().filter(|x|x.as_str()=="make:launch").count(),1);drop(trace);
        std::fs::remove_dir_all(root).unwrap();
    }
}
#[test]
fn app_origin_each_recheck_mismatch_starts_no_make() {
    for after_confirm in [false,true] {
        for (paths,sizes,line) in [
            (vec![],vec![],"Put a card in."),
            (vec!["one".into(),"two".into()],vec![64_000_000_000,64_000_000_000],"Leave just one card in the computer."),
            (vec!["different-card".into()],vec![64_000_000_000],"Card ready (64 GB)."),
            (vec!["controlled-card".into()],vec![32_000_000_000],"Card ready (32 GB)."),
        ] {
            let(b,_rx,root)=setup();ready(&b);
            if after_confirm {assert!(b.make_request(same()).confirm);}
            let v=if after_confirm{b.make_start(cards(paths,sizes))}else{b.make_request(cards(paths,sizes))};
            assert_eq!(v.view,"ready");assert!(!v.confirm);assert_eq!(v.card_line,line);
            assert!(!b.trace.lock().unwrap().iter().any(|x|x=="make:launch"));
            std::fs::remove_dir_all(root).unwrap();
        }
    }
}
