// Compiled only as a Rust unit test, inside the production bridge module. The TEST-ONLY
// adapter for tests/c1_closeout_r1/g3.py (#624, F364-2), driven case by case by
// tools/app/g3_624.py. With DT_G3_CASE naming a case file, one child-origin case runs
// through the production bridge and completion path with a REAL child: the original
// INGEST on real folders, `tapectl-test make` on a CI VHD with the exact argv the bridge
// built, or the shipping `tapectl cards`. The child's original stdout/stderr/report are
// kept before the bridge removes the job holding them. With DT_G3_APP_OUT, the twelve
// app-origin cases run through the same bridge actions. Without either, every test here
// returns at once.
use super::*;
use crate::{ingest_job::CAPACITY_FRAMES, report::{self, Reading, Tool}};
use serde_json::{json, Value};
use std::{fs, path::Path, process::{Command, Stdio}};

const NONCE: &str = "cccccccccccccccccccccccccccccccc";
const CARDS_VERSION: &str = "g3-typed-recheck";

fn case(tool: &str) -> Option<(Value, PathBuf)> {
    let p = std::env::var_os("DT_G3_CASE")?;
    let v: Value = serde_json::from_slice(&fs::read(&p).unwrap()).unwrap();
    if v["tool"] != tool { return None; }
    let out = PathBuf::from(v["out"].as_str().unwrap());
    fs::create_dir_all(&out).unwrap();
    Some((v, out))
}

fn text<'a>(v: &'a Value, k: &str) -> &'a str { v[k].as_str().unwrap_or_else(|| panic!("case field {k}")) }

fn scratch(tag: &str) -> PathBuf {
    let r = std::env::temp_dir().join(format!("DigitalTapeG3-{tag}-{}", children::nonce()));
    jobdir::prepare(&r).unwrap();
    r
}

fn keep(out: &Path, name: &str, bytes: &[u8]) -> String {
    let p = out.join(name);
    fs::write(&p, bytes).unwrap();
    p.to_string_lossy().into_owned()
}

fn write_row(out: &Path, row: Value) {
    fs::write(out.join("row.json"), serde_json::to_vec_pretty(&row).unwrap()).unwrap();
}

/// The bridge's own event notes for this run, as its bridge reference.
fn notes(b: &Bridge) -> Vec<String> { b.trace.lock().unwrap().clone() }

/// A typed recheck (the card-check child's terminal) printing `list`.
fn cards(list: &[(String, u64)]) -> impl FnOnce(&jobdir::Job, &AtomicBool, &mut dyn FnMut(), &mut dyn FnMut(), Launched) -> (Ran, Request) {
    let mut stdout = String::new();
    for (p, b) in list { stdout += &format!("{}\n", json!({"t": "card", "path": p, "bytes": b})); }
    stdout += &format!("{{\"t\":\"summary\",\"offered\":{},\"unprobed\":0}}\n", list.len());
    move |job, _, _, _, _| {
        let report = format!("{{\"t\":\"start\",\"tool\":\"tapectl cards\",\"version\":\"{CARDS_VERSION}\",\"nonce\":\"{NONCE}\"}}\n{{\"t\":\"end\",\"exit\":0}}\n");
        (Ran { pid: Some(1), exit: Some(0), stdout: stdout.into_bytes(), report: Some(report.into_bytes()), ..Default::default() },
         Request { exe: "tapectl.exe".into(), argv: vec![], cwd: job.dir.clone(), report: job.control.join("r"), nonce: NONCE.into(), version: CARDS_VERSION.into() })
    }
}

/// Ready with one card: `wav` retained as the checked audio (moved into an owned job, as
/// production retains ingest's DEST), `label`, and a current one-card check of `dev`.
fn ready(b: &Arc<Bridge>, root: &Path, dev: &str, bytes: u64, wav: &Path, label: &str) {
    let generation = {
        let mut core = b.core.lock().unwrap();
        core.app.folders = vec![root.join("Music")];
        core.app.set_label("C1 Music");
        let g = core.app.begin_job("ingest-g3");
        core.app.finish_job(g, "ingest-g3", &Outcome { exit: Some(0), stderr: String::new(), reading: Reading::Unusable("not needed"),
            total_frames: Some(CAPACITY_FRAMES / 2), cancelled: false });
        g
    };
    let ingest = jobdir::create(root, "ingest-g3").unwrap();
    fs::create_dir_all(ingest.out.join("DEST")).unwrap();
    fs::copy(wav, ingest.out.join("DEST").join("audio.wav")).unwrap();
    fs::write(ingest.out.join("DEST").join("manifest.json"), b"{}").unwrap();
    b.retain(&ingest, generation);
    jobdir::remove(&ingest);
    b.discover(cards(&[(dev.to_owned(), bytes)])).unwrap();
    // The label box refuses more than 32 bytes (label.rs); a longer label can only be
    // placed here, to reach tapectl's own LABEL_INVALID (generic-make).
    if label.len() > crate::label::MAX_BYTES { b.core.lock().unwrap().app.label = label.to_owned(); }
    else { b.core.lock().unwrap().app.set_label(label); }
    assert!(b.snapshot().make_enabled, "{:?}", b.snapshot());
}

/// The same report with every `stderr` record's text replaced; all other lines unchanged.
fn reworded(report: &[u8]) -> Vec<u8> {
    let mut out = Vec::new();
    for line in report.split_inclusive(|&c| c == b'\n') {
        match serde_json::from_slice::<Value>(line) {
            Ok(mut v) if v["t"] == "stderr" => {
                v["text"] = json!("tapectl: a differently worded diagnostic");
                out.extend(serde_json::to_vec(&v).unwrap());
                if line.ends_with(b"\n") { out.push(b'\n'); }
            }
            _ => out.extend_from_slice(line),
        }
    }
    out
}

fn wait_published(b: &Bridge, what: &str, secs: u64) {
    let deadline = Instant::now() + Duration::from_secs(secs);
    while Instant::now() < deadline {
        if b.trace.lock().unwrap().iter().any(|e| e == what) { return; }
        thread::sleep(Duration::from_millis(50));
    }
    panic!("{what} never happened: {:?}", b.trace.lock().unwrap());
}

#[test]
fn g3_child_make() {
    let Some((c, out)) = case("make") else { return };
    let root = scratch("make");
    let (b, _rx) = Bridge::channel(root.clone(), Arc::new(|_| {}));
    let (dev, bytes) = (text(&c, "dev").to_owned(), c["bytes"].as_u64().unwrap());
    ready(&b, &root, &dev, bytes, Path::new(text(&c, "wav")), text(&c, "label"));
    *b.make_child.lock().unwrap() = Some((PathBuf::from(text(&c, "tapectl")), text(&c, "version").into()));
    let env: Vec<(String, String)> = c["env"].as_object().map(|m| m.iter().map(|(k, v)| (k.clone(), v.as_str().unwrap().to_owned())).collect()).unwrap_or_default();
    let seen: Arc<Mutex<Option<(make::Request, i32, u32)>>> = Arc::new(Mutex::new(None));
    let (dir, got, child_env) = (out.clone(), seen.clone(), env.clone());
    // TEST-ONLY launcher: the request the bridge built, run unelevated on the CI runner
    // (an administrator without UAC) instead of through ShellExecuteExW "runas".
    *b.launch.lock().unwrap() = Arc::new(move |req: &make::Request, tick: &mut dyn FnMut()| {
        let mut cmd = Command::new(&req.exe);
        cmd.args(&req.args).current_dir(&req.dir).stdin(Stdio::null())
            .stdout(fs::File::create(dir.join("child.stdout")).unwrap()).stderr(fs::File::create(dir.join("child.stderr")).unwrap());
        for (k, _) in std::env::vars().filter(|(k, _)| k.starts_with("TAPECTL_TEST")) { cmd.env_remove(k); }
        for (k, v) in &child_env { cmd.env(k, v); }
        let mut child = match cmd.spawn() { Ok(c) => c, Err(e) => return make::Launched::NotStarted(e.to_string()) };
        let code = loop {
            if let Some(s) = child.try_wait().unwrap() { break s.code().unwrap_or(-1); }
            tick();
            thread::sleep(Duration::from_millis(100));
        };
        // The original report, kept before run_make removes the job that holds it.
        if let Ok(r) = fs::read(&req.report) { fs::write(dir.join("child.report.jsonl"), r).unwrap(); }
        *got.lock().unwrap() = Some((req.clone(), code, child.id()));
        make::Launched::Exited(code)
    });
    let one = vec![(dev.clone(), bytes)];
    assert!(b.make_request(cards(&one)).confirm, "no erase confirmation");
    b.make_start(cards(&one));
    wait_published(&b, "make:published", 1500);
    let (view, details) = (b.snapshot(), b.raw_details());
    let (req, code, pid) = seen.lock().unwrap().clone().expect("the make child ran");
    let process = keep(&out, "child.process.json", &serde_json::to_vec_pretty(&json!({"exe": req.exe, "args": req.args, "cwd": req.dir,
        "pid": pid, "exit": code, "env": env.iter().cloned().collect::<std::collections::BTreeMap<_, _>>(), "report": req.report,
        "nonce": req.nonce, "version": req.version})).unwrap());
    let original = fs::read(out.join("child.report.jsonl")).ok();
    // Make's stderr reaches the app only as the report's stderr records: reword them and
    // judge the otherwise identical report again with the production selector.
    let changed = original.as_deref().map(reworded);
    let again = make::judge(&make::Launched::Exited(code), changed.as_deref(), &req.nonce, &req.version).message;
    if let Some(ch) = &changed { keep(&out, "reworded.report.jsonl", ch); }
    let launches = notes(&b).iter().filter(|e| e.as_str() == "make:launch").count();
    write_row(&out, json!({"id": c["id"], "message": view.message, "view": view.view, "details": details,
        "details_copyable": !details.is_empty(), "auto_relaunches": launches.saturating_sub(1), "make_children": launches,
        "real_tool_outcome": true, "exit": code, "report_ref": out.join("child.report.jsonl"), "process_ref": process,
        "raw_refs": [out.join("child.stdout"), out.join("child.stderr"), out.join("child.report.jsonl"), out.join("child.trace.json")],
        "bridge_refs": ["bridge::Bridge::make_request", "bridge::Bridge::make_start", "bridge::Bridge::run_make", "make::judge",
                        "state::App::made", format!("notes: {}", notes(&b).join(" "))],
        "message_changed_stderr": again, "stderr_variant": "report stderr records reworded; same exit, nonce and all other lines"}));
}

#[test]
fn g3_child_ingest() {
    let Some((c, out)) = case("ingest") else { return };
    let version = children::INGEST.version.expect("DT_INGEST_VERSION pin");
    let bin = PathBuf::from(text(&c, "ingest"));
    let folders: Vec<PathBuf> = c["folders"].as_array().unwrap().iter().map(|f| PathBuf::from(f.as_str().unwrap())).collect();
    let root = scratch("ingest");
    let (b, rx) = Bridge::channel(root.clone(), Arc::new(|_| {}));
    b.drop_from(Route::ControlledTest, json!(folders));
    let Ok(Message::Check(work)) = rx.recv_timeout(Duration::from_secs(5)) else { panic!("no ingest scheduled") };
    let kept: Arc<Mutex<Option<(i32, String, Vec<u8>, String)>>> = Arc::new(Mutex::new(None));
    let (dir, got) = (out.clone(), kept.clone());
    // The production worker closure, with the original child named instead of resolved
    // beside this test executable.
    b.execute_with(work, |job, work, receipt, spawned| {
        let o = ingest_job::run_hooked(&bin, version, job, &work.folders, work.cancel.clone(), receipt, spawned);
        keep(&dir, "child.stdout", &receipt.stdout);
        keep(&dir, "child.stderr", &receipt.stderr);
        keep(&dir, "child.report.jsonl", receipt.report_bytes.as_deref().unwrap_or_default());
        keep(&dir, "child.process.json", &serde_json::to_vec_pretty(&*receipt).unwrap());
        *got.lock().unwrap() = Some((o.exit.unwrap_or(-1), receipt.nonce.clone(), receipt.report_bytes.clone().unwrap_or_default(), o.stderr.clone()));
        Ok(o)
    });
    let (view, details) = (b.snapshot(), b.raw_details());
    let (exit, nonce, original, _) = kept.lock().unwrap().clone().expect("ingest ran");
    // Same exit and original report, different stderr, through a second production bridge.
    let root2 = scratch("ingest-reworded");
    let (b2, rx2) = Bridge::channel(root2, Arc::new(|_| {}));
    b2.drop_from(Route::ControlledTest, json!(folders));
    let Ok(Message::Check(work2)) = rx2.recv_timeout(Duration::from_secs(5)) else { panic!("no second ingest scheduled") };
    b2.execute_with(work2, |_, w, _, _| Ok(Outcome { exit: Some(exit), stderr: "ingest: a differently worded diagnostic\n".into(),
        reading: report::read(&original, Tool::Ingest, &nonce, version, exit, w.folders.len()), total_frames: None, cancelled: false }));
    let again = b2.snapshot().message;
    write_row(&out, json!({"id": c["id"], "message": view.message, "view": view.view, "details": details,
        "details_copyable": !details.is_empty(), "auto_relaunches": 0, "real_tool_outcome": true, "exit": exit,
        "report_ref": out.join("child.report.jsonl"), "process_ref": out.join("child.process.json"),
        "raw_refs": [out.join("child.stdout"), out.join("child.stderr"), out.join("child.report.jsonl"), out.join("child.process.json")],
        "bridge_refs": ["bridge::Bridge::drop_from", "bridge::Bridge::execute_with", "ingest_job::run_hooked", "bridge::Bridge::deliver",
                        "state::App::finished", format!("notes: {}", notes(&b).join(" "))],
        "message_changed_stderr": again, "stderr_variant": "captured stderr replaced; same exit and original report bytes re-read"}));
}

#[test]
fn g3_child_cards() {
    let Some((c, out)) = case("cards") else { return };
    let bin = PathBuf::from(text(&c, "tapectl"));
    let version = text(&c, "version").to_owned();
    let root = scratch("cards");
    let (b, _rx) = Bridge::channel(root.clone(), Arc::new(|_| {}));
    let kept: Arc<Mutex<Option<(Ran, Request)>>> = Arc::new(Mutex::new(None));
    let (dir, got, v2) = (out.clone(), kept.clone(), version.clone());
    // The production discovery child, with the shipping tapectl named instead of resolved.
    b.discover(move |job, cancel, on_timeout, on_cancel, _| {
        let (cmd, request) = discovery::command(&bin, &v2, job);
        let ran = discovery::run(cmd, &request, cancel, on_timeout, on_cancel, None);
        keep(&dir, "child.stdout", &ran.stdout);
        keep(&dir, "child.stderr", &ran.stderr);
        keep(&dir, "child.report.jsonl", ran.report.as_deref().unwrap_or_default());
        keep(&dir, "child.process.json", &serde_json::to_vec_pretty(&json!({"ran": ran, "request": request})).unwrap());
        *got.lock().unwrap() = Some((ran.clone(), request.clone()));
        (ran, request)
    });
    let (view, details) = (b.snapshot(), b.raw_details());
    let (ran, request) = kept.lock().unwrap().clone().expect("cards ran");
    let root2 = scratch("cards-reworded");
    let (b2, _rx2) = Bridge::channel(root2, Arc::new(|_| {}));
    b2.discover(move |_, _, _, _, _| (Ran { stderr: b"tapectl: a differently worded diagnostic\n".to_vec(), ..ran.clone() }, request.clone()));
    let again = b2.snapshot().card_line;
    let exit = kept.lock().unwrap().as_ref().and_then(|(r, _)| r.exit).unwrap_or(-1);
    write_row(&out, json!({"id": c["id"], "message": view.card_line, "message_from": "card_line", "view": view.view, "details": details,
        "details_copyable": !details.is_empty(), "auto_relaunches": 0, "real_tool_outcome": true, "exit": exit,
        "report_ref": out.join("child.report.jsonl"), "process_ref": out.join("child.process.json"),
        "raw_refs": [out.join("child.stdout"), out.join("child.stderr"), out.join("child.report.jsonl"), out.join("child.process.json")],
        "bridge_refs": ["bridge::Bridge::discover", "discovery::command", "discovery::run", "discovery::judge", "bridge::Bridge::publish_cards",
                        "state::App::finish_cards", format!("notes: {}", notes(&b).join(" "))],
        "message_changed_stderr": again, "stderr_variant": "captured stderr replaced; same exit, stdout and original report"}));
}

/// The twelve app-origin cases (APP-1 §6 †), through the production bridge actions. Only
/// the launcher and recheck dependencies are typed; no child report is forged.
#[test]
fn g3_app_origin() {
    let Some(out) = std::env::var_os("DT_G3_APP_OUT").map(PathBuf::from) else { return };
    fs::create_dir_all(&out).unwrap();
    let mut rows = Vec::new();
    let refs = |b: &Bridge, what: &[&str]| { let mut v: Vec<String> = what.iter().map(|s| s.to_string()).collect(); v.push(format!("notes: {}", notes(b).join(" "))); v };
    for (id, mixed) in [("drop-file", false), ("drop-mixed", true)] {
        let root = scratch(id);
        let (b, rx) = Bridge::channel(root.clone(), Arc::new(|_| {}));
        let file = root.join("song.wav");
        fs::write(&file, b"ordinary").unwrap();
        let folder = root.join("Music");
        fs::create_dir(&folder).unwrap();
        let payload = if mixed { json!([folder, file]) } else { json!([file]) };
        let v = b.drop_from(Route::ControlledTest, payload.clone());
        let details = b.raw_details();
        rows.push(json!({"id": id, "message": v.message, "new_children": rx.try_iter().count(), "additions": b.core.lock().unwrap().app.folders.len(),
            "details": details, "details_copyable": !details.is_empty(), "auto_relaunches": 0, "production_action": "Bridge::drop_from(Route::ControlledTest)",
            "forged_child_report": false, "bridge_refs": refs(&b, &["bridge::Bridge::drop_from", "drops::classify", "state::App::admit_drop"]),
            "raw_refs": [format!("payload {payload}")]}));
    }
    {
        // A real OS spawn failure: the production worker closure on a missing executable.
        let root = scratch("spawn-failed");
        let (b, rx) = Bridge::channel(root.clone(), Arc::new(|_| {}));
        let folder = root.join("Music");
        fs::create_dir(&folder).unwrap();
        b.drop_from(Route::ControlledTest, json!([folder]));
        let Ok(Message::Check(work)) = rx.recv_timeout(Duration::from_secs(5)) else { panic!("no ingest scheduled") };
        let missing = root.join("missing").join(children::INGEST.file);
        b.execute_with(work, |job, work, receipt, spawned| Ok(ingest_job::run_hooked(&missing, "unused", job, &work.folders, work.cancel.clone(), receipt, spawned)));
        let (v, details) = (b.snapshot(), b.raw_details());
        rows.push(json!({"id": "spawn-failed", "message": v.message, "details": details, "details_copyable": !details.is_empty(), "auto_relaunches": 0,
            "production_action": "Bridge::execute_with + ingest_job::run_hooked on a missing executable (real OS spawn failure)",
            "forged_child_report": false, "bridge_refs": refs(&b, &["bridge::Bridge::execute_with", "ingest_job::run_command", "state::App::finished"]),
            "raw_refs": [format!("spawned {}", missing.display())]}));
    }
    let dev = "\\\\.\\PhysicalDriveG3".to_owned();
    let bytes = 64_000_000_000u64;
    let wav = std::env::temp_dir().join(format!("g3-app-{}.wav", children::nonce()));
    fs::write(&wav, b"RIFF app-origin audio, never read").unwrap();
    {
        let root = scratch("elevation-declined");
        let (b, _rx) = Bridge::channel(root.clone(), Arc::new(|_| {}));
        ready(&b, &root, &dev, bytes, &wav, "C1 Music");
        *b.make_child.lock().unwrap() = Some((root.join("not-executed.exe"), "g3".into()));
        let children_started = Arc::new(Mutex::new(0usize));
        *b.launch.lock().unwrap() = Arc::new(|_, _| make::Launched::Declined);
        let one = vec![(dev.clone(), bytes)];
        assert!(b.make_request(cards(&one)).confirm);
        b.make_start(cards(&one));
        wait_published(&b, "make:published", 30);
        let (v, details) = (b.snapshot(), b.raw_details());
        rows.push(json!({"id": "elevation-declined", "message": v.message, "make_children": *children_started.lock().unwrap(), "details": details,
            "details_copyable": !details.is_empty(), "auto_relaunches": notes(&b).iter().filter(|e| e.as_str() == "make:launch").count().saturating_sub(1),
            "production_action": "Bridge::make_request + make_start; make launcher dependency returns UAC cancellation (ERROR_CANCELLED)",
            "forged_child_report": false, "bridge_refs": refs(&b, &["bridge::Bridge::make_start", "bridge::Bridge::run_make", "make::judge"]),
            "raw_refs": ["typed launcher: make::Launched::Declined"]}));
    }
    for after in [false, true] {
        for (change, list) in [
            ("zero", vec![]),
            ("two", vec![("one".to_owned(), bytes), ("two".to_owned(), bytes)]),
            ("different-path", vec![("different-card".to_owned(), bytes)]),
            ("different-capacity", vec![(dev.clone(), 32_000_000_000)]),
        ] {
            let id = format!("recheck-{}-confirm-{change}", if after { "after" } else { "before" });
            let root = scratch(&id);
            let (b, _rx) = Bridge::channel(root.clone(), Arc::new(|_| {}));
            ready(&b, &root, &dev, bytes, &wav, "C1 Music");
            *b.launch.lock().unwrap() = Arc::new(|_, _| panic!("no make may start after a recheck mismatch"));
            if after { assert!(b.make_request(cards(&[(dev.clone(), bytes)])).confirm); }
            let v = if after { b.make_start(cards(&list)) } else { b.make_request(cards(&list)) };
            let sizes: Vec<u64> = list.iter().map(|x| x.1).collect();
            let expected = discovery::line(Some(&discovery::Hint { sizes, paths: list.iter().map(|x| x.0.clone()).collect(), unprobed: 0 }));
            let details = b.raw_details();
            rows.push(json!({"id": id, "message": v.message, "state": if v.view == "ready" { "Ready" } else { v.view },
                "make_children": notes(&b).iter().filter(|e| e.as_str() == "make:launch").count(), "card_line": v.card_line,
                "card_line_current": v.card_line == expected && !v.confirm, "details": details, "details_copyable": !details.is_empty(),
                "auto_relaunches": 0, "production_action": if after { "Bridge::make_start (step 3 recheck)" } else { "Bridge::make_request (step 1 recheck)" },
                "forged_child_report": false, "bridge_refs": refs(&b, &["bridge::Bridge::recheck", "bridge::Bridge::discover", "state::App::confirm/start_making"]),
                "raw_refs": [format!("typed recheck {list:?}")]}));
        }
    }
    let _ = fs::remove_file(&wav);
    fs::write(out.join("app-rows.json"), serde_json::to_vec_pretty(&rows).unwrap()).unwrap();
}
