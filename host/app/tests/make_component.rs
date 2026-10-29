// Compiled only as a Rust unit test. The actual production bridge runs Make cartridge end to
// end: real job directories, the real recheck/publication closure, the real request builder,
// report reader and message selector. Only the two OS boundaries are typed: the card check
// child's terminal (as in discovery_component) and the elevated launcher's result.
use super::*;
use crate::{ingest_job::CAPACITY_FRAMES, messages, report::Reading, state::{Making, MADE, WAIT}};
use std::{fs, path::Path, sync::mpsc::Receiver, time::Duration};

const NONCE: &str = "cccccccccccccccccccccccccccccccc";
const VERSION: &str = "tapectl-wp15-s2+dddddddddddd";
const CARD: &str = "CARD-1";
const BYTES: u64 = 64_000_000_000;

fn root(tag: &str) -> PathBuf {
    let r = std::env::temp_dir().join(format!("DigitalTapeMake-{tag}-{}", children::nonce()));
    jobdir::prepare(&r).unwrap();
    r
}

fn cards(list: &[(&str, u64)]) -> impl FnOnce(&jobdir::Job, &AtomicBool, &mut dyn FnMut(), &mut dyn FnMut(), Launched) -> (Ran, Request) {
    let mut stdout = String::new();
    for (p, b) in list { stdout += &format!("{{\"t\":\"card\",\"path\":\"{p}\",\"bytes\":{b}}}\n"); }
    stdout += &format!("{{\"t\":\"summary\",\"offered\":{},\"unprobed\":0}}\n", list.len());
    move |job, _, _, _, _| {
        let report = format!("{{\"t\":\"start\",\"tool\":\"tapectl cards\",\"version\":\"{VERSION}\",\"nonce\":\"{NONCE}\"}}\n{{\"t\":\"end\",\"exit\":0}}\n");
        (Ran { pid: Some(1), exit: Some(0), stdout: stdout.into_bytes(), report: Some(report.into_bytes()), ..Default::default() },
         Request { exe: "tapectl.exe".into(), argv: vec![], cwd: job.dir.clone(), report: job.control.join("r"), nonce: NONCE.into(), version: VERSION.into() })
    }
}

struct Fixture { b: Arc<Bridge>, views: Arc<Mutex<Vec<View>>>, rx: Receiver<Message>, root: PathBuf, audio: PathBuf }

/// Ready with one card: a real retained DEST, a label, and a current one-card check.
fn ready(tag: &str) -> Fixture {
    let root = root(tag);
    let views = Arc::new(Mutex::new(Vec::new()));
    let out = views.clone();
    let (b, rx) = Bridge::channel(root.clone(), Arc::new(move |v| out.lock().unwrap().push(v)));
    *b.make_child.lock().unwrap() = Some(("tapectl.exe".into(), VERSION.into()));
    let generation = {
        let mut core = b.core.lock().unwrap();
        core.app.folders = vec![root.join("Road Trip")];
        core.app.set_label("Road Trip");
        let g = core.app.begin_job("ingest-test");
        core.app.finish_job(g, "ingest-test", &Outcome { exit: Some(0), stderr: String::new(), reading: Reading::Unusable("not needed"),
            total_frames: Some(CAPACITY_FRAMES / 2), cancelled: false });
        g
    };
    let ingest = jobdir::create(&root, "ingest-test").unwrap();
    fs::create_dir_all(ingest.out.join("DEST")).unwrap();
    fs::write(ingest.out.join("DEST").join("audio.wav"), b"RIFF test audio").unwrap();
    fs::write(ingest.out.join("DEST").join("manifest.json"), b"{}").unwrap();
    b.retain(&ingest, generation);
    jobdir::remove(&ingest);
    b.discover(cards(&[(CARD, BYTES)])).unwrap();
    let audio = b.core.lock().unwrap().app.audio.clone().expect("audio retained");
    assert!(audio.is_file() && audio.starts_with(root.join("jobs")), "{}", audio.display());
    assert!(b.snapshot().make_enabled);
    Fixture { b, views, rx, root, audio }
}

fn set_launch(b: &Bridge, f: impl Fn(&make::Request, &mut dyn FnMut()) -> make::Launched + Send + Sync + 'static) {
    *b.launch.lock().unwrap() = Arc::new(f);
}

fn settle(b: &Bridge) -> View {
    for _ in 0..400 {
        if b.trace.lock().unwrap().iter().any(|e| e == "make:published") { return b.snapshot(); }
        std::thread::sleep(Duration::from_millis(10));
    }
    panic!("make never published: {:?}", b.trace.lock().unwrap());
}

fn jobs(root: &Path, prefix: &str) -> usize {
    fs::read_dir(root.join("jobs")).map(|d| d.flatten().filter(|e| e.file_name().to_string_lossy().starts_with(prefix)).count()).unwrap_or(0)
}

fn report(req: &make::Request, body: &[&str], exit: i32) {
    let mut s = format!("{{\"t\":\"start\",\"tool\":\"tapectl make\",\"version\":\"{}\",\"nonce\":\"{}\"}}\n", req.version, req.nonce);
    for l in body { s += l; s.push('\n'); }
    s += &format!("{{\"t\":\"end\",\"exit\":{exit}}}\n");
    fs::write(&req.report, s).unwrap();
}

#[test]
fn recheck_mismatch_and_keep_card_start_nothing() {
    let f = ready("recheck");
    let launches = Arc::new(Mutex::new(0));
    let n = launches.clone();
    set_launch(&f.b, move |_, _| { *n.lock().unwrap() += 1; make::Launched::Exited(0) });
    // Step 1: two cards now, so back to Ready with that card line (CARD_RECHECK_MISMATCH).
    let v = f.b.make_request(cards(&[(CARD, BYTES), ("CARD-2", BYTES)]));
    assert_eq!((v.view, v.confirm, v.make_enabled, v.card_line.as_str()), ("ready", false, false, "Leave just one card in the computer."));
    // A different card at the same size is not the card the person saw.
    f.b.discover(cards(&[(CARD, BYTES)])).unwrap();
    let v = f.b.make_request(cards(&[("CARD-9", BYTES)]));
    assert!(!v.confirm);
    // Confirmation, then Keep card.
    f.b.discover(cards(&[(CARD, BYTES)])).unwrap();
    let v = f.b.make_request(cards(&[(CARD, BYTES)]));
    assert!(v.confirm && !v.make_enabled);
    let v = f.b.make_cancel();
    assert!(!v.confirm && v.make_enabled);
    // Replace, but the card is gone at the second recheck.
    assert!(f.b.make_request(cards(&[(CARD, BYTES)])).confirm);
    let v = f.b.make_start(cards(&[]));
    assert_eq!((v.view, v.confirm, v.make_enabled, v.card_line.as_str()), ("ready", false, false, "Put a card in."));
    assert_eq!(*launches.lock().unwrap(), 0, "no make child without two matching rechecks and a confirmation");
    assert!(f.audio.is_file(), "the music is kept");
    fs::remove_dir_all(&f.root).unwrap();
}

#[test]
fn success_runs_one_elevated_request_with_progress_then_cleans_up() {
    let f = ready("success");
    let seen = Arc::new(Mutex::new(None));
    let s = seen.clone();
    set_launch(&f.b, move |req, tick| {
        *s.lock().unwrap() = Some(req.clone());
        report(req, &["{\"t\":\"progress\",\"step\":\"safety\",\"done\":1,\"total\":1}", "{\"t\":\"progress\",\"step\":\"load\",\"done\":5,\"total\":10}"], 0);
        tick();
        report(req, &["{\"t\":\"progress\",\"step\":\"verify_b\",\"done\":10,\"total\":10}"], 0);
        tick();
        make::Launched::Exited(0)
    });
    assert!(f.b.make_request(cards(&[(CARD, BYTES)])).confirm);
    let started = f.b.make_start(cards(&[(CARD, BYTES)]));
    assert_eq!((started.view, started.bar), ("making", Some(0.0)));
    let done = settle(&f.b);
    assert_eq!((done.view, done.message.as_deref(), done.make_enabled), ("done", Some(MADE), false));
    let req = seen.lock().unwrap().clone().unwrap();
    let wav = f.audio.to_string_lossy().into_owned();
    let report_path = req.report.to_string_lossy().into_owned();
    assert_eq!(req.args, ["make", CARD, "--label", "Road Trip", "--length-s", "3600", "--wav", &wav, "--erase", CARD,
        "--report", &report_path, "--report-nonce", &req.nonce]);
    assert!(req.report.starts_with(f.root.join("jobs")) && req.report.parent().unwrap().ends_with("control"));
    // The bar only moved forward, with plain step lines.
    let bars: Vec<(f64, String)> = f.views.lock().unwrap().iter().filter(|v| v.view == "making").map(|v| (v.bar.unwrap(), v.message.clone().unwrap())).collect();
    assert!(bars.windows(2).all(|w| w[1].0 >= w[0].0), "{bars:?}");
    assert!(bars.iter().any(|(_, m)| m == "Copying the music…") && bars.last().unwrap().0 == 1.0, "{bars:?}");
    // Step 4: the make job and the retained audio are deleted; nothing else.
    assert!(!f.audio.exists());
    assert_eq!((jobs(&f.root, "make-"), jobs(&f.root, "ready-")), (0, 0));
    // Make another: the same folders checked again.
    let v = f.b.make_another();
    assert!(v.checking);
    assert!(matches!(f.rx.try_recv(), Ok(Message::Check(_))));
    fs::remove_dir_all(&f.root).unwrap();
}

#[test]
fn child_outcomes_select_their_rows_and_keep_the_music() {
    let rows: [(&str, &[&str], i32, &str); 4] = [
        ("card-changed", &["{\"t\":\"refusal\",\"id\":\"CARD_CHANGED\",\"subject\":null,\"phase\":\"load\",\"os_error\":\"ERROR_DEV_NOT_EXIST\"}",
            "{\"t\":\"stderr\",\"text\":\"tapectl: CARD_CHANGED: the card was removed or changed during load (ERROR_DEV_NOT_EXIST)\"}"], 1,
            "The card was taken out before it was finished. Put it back in and press Make cartridge again."),
        ("refused", &["{\"t\":\"refusal\",\"id\":\"REFUSE_FOREIGN_MOUNT\",\"subject\":null}"], 3,
            "This card can't be used right now. Check the card and try again."),
        ("findings", &["{\"t\":\"refusal\",\"id\":\"VERIFY_FINDINGS\",\"subject\":null,\"findings\":[{\"f\":\"READ_ERROR\",\"side\":\"A\",\"frame\":0}]}"], 1,
            "Something went wrong writing this card. Press Make cartridge to try again."),
        ("no-report-terminal", &[], 1, "The cartridge wasn't finished. Start over and try again."),
    ];
    for (tag, body, exit, sentence) in rows {
        let f = ready(tag);
        let body: Vec<String> = body.iter().map(|s| s.to_string()).collect();
        set_launch(&f.b, move |req, _| { let b: Vec<&str> = body.iter().map(String::as_str).collect(); report(req, &b, exit); make::Launched::Exited(exit) });
        f.b.make_request(cards(&[(CARD, BYTES)]));
        f.b.make_start(cards(&[(CARD, BYTES)]));
        let v = settle(&f.b);
        assert_eq!((v.view, v.message.as_deref(), v.make_enabled, v.details_available), ("ready", Some(sentence), true, true), "{tag}");
        if tag == "card-changed" { assert!(f.b.raw_details().contains("CARD_CHANGED: the card was removed"), "{}", f.b.raw_details()); }
        assert!(f.audio.is_file() && jobs(&f.root, "make-") == 0, "{tag}: the music is kept, the make job removed");
        fs::remove_dir_all(&f.root).unwrap();
    }
}

#[test]
fn app_origin_declined_and_spawn_failed() {
    for (tag, launched, sentence) in [
        ("declined", make::Launched::Declined, "The computer said no, so the card wasn't changed. Press Make cartridge to try again."),
        ("spawn", make::Launched::NotStarted("ShellExecuteExW runas: Windows error 2".into()), messages::GENERIC_INGEST),
    ] {
        let f = ready(tag);
        let l = launched.clone();
        set_launch(&f.b, move |_, _| l.clone());
        f.b.make_request(cards(&[(CARD, BYTES)]));
        f.b.make_start(cards(&[(CARD, BYTES)]));
        let v = settle(&f.b);
        assert_eq!((v.view, v.message.as_deref(), v.make_enabled), ("ready", Some(sentence), true), "{tag}");
        assert!(f.audio.is_file());
        fs::remove_dir_all(&f.root).unwrap();
    }
}

#[test]
fn while_making_close_start_over_and_drops_are_refused() {
    let f = ready("busy");
    let (go, wait) = std::sync::mpsc::channel::<()>();
    let wait = Mutex::new(wait);
    set_launch(&f.b, move |req, _| { wait.lock().unwrap().recv().unwrap(); report(req, &[], 0); make::Launched::Exited(0) });
    f.b.make_request(cards(&[(CARD, BYTES)]));
    f.b.make_start(cards(&[(CARD, BYTES)]));
    assert!(f.b.close_requested());
    assert_eq!(f.b.snapshot().message.as_deref(), Some(WAIT));
    assert_eq!(f.b.start_over().view, "making");
    assert_eq!(f.b.drop_from(Route::ControlledTest, serde_json::json!([f.root.to_string_lossy()])).view, "making");
    assert!(matches!(f.b.core.lock().unwrap().app.making, Making::Running { .. }));
    go.send(()).unwrap();
    assert_eq!(settle(&f.b).view, "done");
    assert!(!f.b.close_requested(), "closing is allowed again");
    fs::remove_dir_all(&f.root).unwrap();
}
