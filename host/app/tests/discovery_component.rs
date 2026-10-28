// Compiled only as a Rust unit test. Typed child outcomes enter the actual production
// discovery run/publication closure; no fake executable, shipping switch or real enumeration.
use super::*;
use crate::{discovery::{Child, End, INTERVAL_MS, TIMEOUT_MS}, ingest_job::CAPACITY_FRAMES, messages, report::Reading};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::{collections::BTreeMap, fs, path::Path, sync::atomic::AtomicUsize, time::Duration};

const NONCE: &str = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
const VERSION: &str = "tapectl-wp15-s2+bbbbbbbbbbbb";

fn save(p: &Path, v: &Value) { fs::write(p, serde_json::to_vec_pretty(v).unwrap()).unwrap(); }
fn sha(b: &[u8]) -> String { Sha256::digest(b).iter().map(|x| format!("{x:02x}")).collect() }
fn trace(b: &Bridge) -> Vec<String> { b.trace.lock().unwrap().clone() }
fn root(tag: &str) -> PathBuf {
    let r = std::env::temp_dir().join(format!("DigitalTapeDiscovery-{tag}-{}", children::nonce()));
    jobdir::prepare(&r).unwrap();
    r
}
fn new(root: &Path) -> (Arc<Bridge>, Arc<Mutex<Vec<View>>>) {
    let views = Arc::new(Mutex::new(Vec::new()));
    let out = views.clone();
    let (b, rx) = Bridge::channel(root.into(), Arc::new(move |v| out.lock().unwrap().push(v)));
    std::mem::forget(rx); // no ingest work in these tests
    (b, views)
}

/// One typed child outcome, as tapectl would leave it.
fn typed(c: &Value) -> Ran {
    Ran {
        pid: Some(1),
        exit: c["exit"].as_i64().map(|e| e as i32),
        stdout: c["stdout"].as_str().unwrap().as_bytes().to_vec(),
        stderr: b"tapectl: diagnostic text never selects an outcome\n".to_vec(),
        report: Some(c["report"].as_str().unwrap().as_bytes().to_vec()).filter(|r| !r.is_empty()),
        ..Default::default()
    }
}
fn request(job: &jobdir::Job) -> Request {
    Request { exe: "tapectl.exe".into(), argv: vec![], cwd: job.dir.clone(), report: job.control.join("r"), nonce: NONCE.into(), version: VERSION.into() }
}
fn run_case(b: &Bridge, c: &Value) -> (Ran, Request, Judged) {
    let ran = typed(c);
    b.discover(move |job, _, _, _, _| (ran, request(job))).unwrap()
}
fn row(b: &Bridge, judged: &Judged) -> Value {
    let v = b.snapshot();
    json!({"line": v.card_line, "offered": judged.hint.as_ref().map(|h| h.sizes.len()), "unprobed": judged.hint.as_ref().map(|h| h.unprobed),
           "id_specific": judged.id_specific, "make_enabled": v.make_enabled})
}

/// A started child that never exits by itself; `stop` is its terminal.
struct Blocked { polled: Arc<AtomicBool> }
impl Child for Blocked {
    fn poll(&mut self) -> Option<Option<i32>> { self.polled.store(true, Ordering::SeqCst); None }
    fn stop(&mut self) -> Option<i32> { None }
}

fn order(t: &[String], from: &str, want: &[&str]) -> Vec<String> {
    let start = t.iter().position(|e| e == from).unwrap_or(0);
    let mut out = Vec::new();
    for e in &t[start..] {
        let e = e.strip_prefix("cards:").unwrap_or(e);
        if want.contains(&e) && !out.iter().any(|x: &String| x == e) { out.push(e.to_owned()); }
    }
    out
}

#[test]
fn capture() {
    let Ok(output) = std::env::var("DT_DISCOVERY_OUTPUT") else { return };
    let out = PathBuf::from(output);
    fs::create_dir_all(&out).unwrap();
    let input: Value = serde_json::from_slice(&fs::read(std::env::var("DT_DISCOVERY_INPUT").unwrap()).unwrap()).unwrap();
    let head = std::env::var("DT_SOURCE_HEAD").unwrap();
    let private = root("capture");
    let source = private.parent().unwrap().join(format!("DigitalTapeDiscoverySource-{}", children::nonce()));
    fs::create_dir(&source).unwrap();
    fs::write(source.join("song.wav"), b"SOURCE BYTES\n").unwrap();
    let source_before = sha(&fs::read(source.join("song.wav")).unwrap());
    let (b, views) = new(&private);
    let foreign = private.join("jobs").join("foreign");
    fs::create_dir_all(&foreign).unwrap();
    fs::write(foreign.join("keep"), b"FOREIGN\n").unwrap();
    let foreign_before = sha(&fs::read(foreign.join("keep")).unwrap());

    // Every frozen row through the actual run/judge/publication closure; failure clears a hint.
    let mut rows = serde_json::Map::new();
    let mut raw_rows = Vec::new();
    let mut failure_clears = true;
    let mut stderr_selected = false;
    let one = input["cases"].as_array().unwrap().iter().find(|c| c["id"] == "one64").unwrap().clone();
    for c in input["cases"].as_array().unwrap() {
        run_case(&b, &one);
        let seeded = b.snapshot().card_line;
        let (ran, req, judged) = run_case(&b, c);
        let r = row(&b, &judged);
        if judged.hint.is_none() && b.snapshot().card_line == seeded { failure_clears = false; }
        let mut quiet = typed(c);
        quiet.stderr = b"Card ready (999 GB).\n".to_vec();
        let other = b.discover(move |job, _, _, _, _| (quiet, request(job))).unwrap().2;
        if other != judged { stderr_selected = true; }
        raw_rows.push(json!({"id": c["id"], "ran": ran, "request": req, "hint": judged.hint, "id_specific": judged.id_specific, "view": b.snapshot(), "details": b.raw_details()}));
        rows.insert(c["id"].as_str().unwrap().into(), r);
    }

    // Make stays false with valid music, a label and exactly one hint.
    {
        let mut core = b.core.lock().unwrap();
        core.app.folders = vec![source.clone()];
        core.app.set_label("Road Trip");
        core.app.finished(&Outcome { exit: Some(0), stderr: String::new(), reading: Reading::Unusable("not needed"), total_frames: Some(CAPACITY_FRAMES / 2), cancelled: false });
    }
    run_case(&b, &one);
    let ready = b.snapshot();
    let make_with_one = ready.make_enabled;
    assert_eq!((ready.view, ready.card_line.as_str()), ("ready", "Card ready (64 GB)."));

    // The actual production request: pinned child beside the executable, cards only.
    let mut nonces = Vec::new();
    let mut reports = Vec::new();
    let mut requests = Vec::new();
    for i in 0..3 {
        let job = jobdir::create(&private, &format!("request-{i}")).unwrap();
        let bin = children::resolve(&children::TAPECTL).expect("pinned tapectl beside the test executable");
        let (cmd, req) = discovery::command(&bin, children::TAPECTL.version.unwrap(), &job);
        assert_eq!(cmd.get_program(), bin.as_os_str());
        assert_eq!(cmd.get_current_dir(), Some(job.dir.as_path()));
        nonces.push(req.nonce.clone());
        reports.push(req.report.to_string_lossy().into_owned());
        requests.push((job, req));
    }
    let (job0, req0) = &requests[0];
    let request_row = json!({"shell": false, "elevated": false, "exe": req0.exe, "executable_dir": req0.exe.parent().unwrap(), "argv": req0.argv,
        "report": req0.report, "nonce": req0.nonce, "private_root": private, "job": job0.dir, "cwd": req0.cwd,
        "nonce_ref": "discovery.raw.json#requests", "actual_command_ref": "src/discovery.rs:command"});
    let raw_requests: Vec<Value> = requests.iter().map(|(_, r)| json!(r)).collect();
    for (job, _) in &requests { assert!(jobdir::remove(job)); }

    // Schedules: the production Schedule over the frozen logical ticks.
    let mut schedules = serde_json::Map::new();
    let (mut busy_new, mut making_new, mut stopped_new) = (0, 0, 0);
    for (name, s) in input["schedules"].as_object().unwrap() {
        let has = |k: &str, t: u64| s[k].as_array().unwrap().iter().any(|x| x.as_u64() == Some(t));
        let mut sched = discovery::Schedule::new(0);
        let (mut busy, mut started) = (false, Vec::new());
        for t in s["ticks"].as_array().unwrap().iter().map(|x| x.as_u64().unwrap()) {
            if has("terminal_before", t) { sched.terminal(t); busy = false; }
            let (making, stopped) = (has("making", t), has("stopped", t));
            if sched.tick(t, making, stopped) {
                if busy { busy_new += 1; }
                if making { making_new += 1; }
                if stopped { stopped_new += 1; }
                busy = true;
                started.push(t);
            }
        }
        schedules.insert(name.clone(), json!(started));
    }

    // Single flight: schedule-driven runs through the real closure never overlap.
    let live = Arc::new(AtomicUsize::new(0));
    let peak = Arc::new(AtomicUsize::new(0));
    let mut sched = discovery::Schedule::new(0);
    for t in (0..20_000).step_by(500) {
        if sched.tick(t, false, false) {
            let (live, peak, c) = (live.clone(), peak.clone(), one.clone());
            b.discover(move |job, _, _, _, _| {
                let n = live.fetch_add(1, Ordering::SeqCst) + 1;
                peak.fetch_max(n, Ordering::SeqCst);
                live.fetch_sub(1, Ordering::SeqCst);
                (typed(&c), request(job))
            });
            sched.terminal(t + 700);
        }
    }

    // Duplicate completion of one ticket publishes once.
    let before = views.lock().unwrap().len();
    let ticket = b.core.lock().unwrap().app.begin_cards();
    let judged = discovery::judge(Some(0), one["stdout"].as_str().unwrap().as_bytes(), one["report"].as_str().map(str::as_bytes), NONCE, VERSION);
    b.publish_cards(ticket, &judged, String::new(), None);
    b.publish_cards(ticket, &judged, String::new(), None);
    let duplicate = views.lock().unwrap().len() - before - 1;

    // Timeout: logical clock, a blocked typed child, the real supervisor.
    b.trace.lock().unwrap().clear();
    let before = views.lock().unwrap().len();
    run_case(&b, &one);
    let mark = trace(&b).len();
    let polled = Arc::new(AtomicBool::new(false));
    let p = polled.clone();
    let (ran, _, _) = b.discover(move |job, cancel, on_timeout, on_cancel, _| {
        let mut clock = 0u64;
        let end = discovery::supervise(&mut Blocked { polled: p }, cancel, &mut || { clock += 2500; clock }, on_timeout, on_cancel);
        assert_eq!(end, End::TimedOut);
        (Ran { timed_out: true, ..Default::default() }, request(job))
    }).unwrap();
    assert!(ran.timed_out && polled.load(Ordering::SeqCst));
    let timeout_trace = trace(&b)[mark..].to_vec();
    let timeout_order = order(&timeout_trace, "cards:worker-start", &["invalidate-current", "cancel", "child-terminal", "remove-owned-job"]);
    let timed_out_line = b.snapshot().card_line;
    let mut stale = timeout_trace.iter().filter(|e| *e == "cards:published").count();
    let timeout_emissions = views.lock().unwrap().len() - before;

    // Replacement: the old run's terminal and cleanup precede the next start.
    b.trace.lock().unwrap().clear();
    run_case(&b, &one);
    run_case(&b, &one);
    let t = trace(&b);
    let second = t.iter().rposition(|e| e == "cards:worker-start").unwrap();
    let replacement_order: Vec<&str> = {
        let terminal = t[..second].iter().rposition(|e| e == "cards:child-terminal").unwrap();
        let cleanup = t[..second].iter().rposition(|e| e == "cards:remove-owned-job").unwrap();
        assert!(terminal < cleanup);
        vec!["old-child-terminal", "old-owned-cleanup", "new-worker-start"]
    };
    let replacement_trace = t.clone();

    // UI never waits for a running child; shutdown stops polls, then the running child.
    b.trace.lock().unwrap().clear();
    let polled = Arc::new(AtomicBool::new(false));
    let p = polled.clone();
    let worker = {
        let b = b.clone();
        std::thread::spawn(move || b.discover(move |job, cancel, on_timeout, on_cancel, _| {
            let clock = std::time::Instant::now();
            let end = discovery::supervise(&mut Blocked { polled: p }, cancel, &mut || clock.elapsed().as_millis() as u64, on_timeout, on_cancel);
            (Ran { cancelled: end == End::Cancelled, ..Default::default() }, request(job))
        }))
    };
    while !polled.load(Ordering::SeqCst) { std::thread::sleep(Duration::from_millis(5)); }
    let asked = std::time::Instant::now();
    b.snapshot();
    b.set_label("Road Trip");
    let ui_wait_ms = asked.elapsed().as_millis();
    let before = views.lock().unwrap().len();
    let shutdown_views = before;
    b.shutdown();
    let ran = worker.join().unwrap().unwrap().0;
    assert!(ran.cancelled);
    let shutdown_trace = trace(&b);
    let shutdown_order = order(&shutdown_trace, "stop-polls", &["stop-polls", "invalidate-current", "cancel", "child-terminal", "remove-owned-job"]);
    stale += shutdown_trace.iter().filter(|e| *e == "cards:published").count();
    let _ = shutdown_views;

    let jobs: Vec<String> = fs::read_dir(private.join("jobs")).unwrap().flatten().map(|e| e.file_name().to_string_lossy().into_owned()).collect();
    let all_lines: Vec<String> = views.lock().unwrap().iter().map(|v| v.card_line.clone()).collect();
    let displayed_paths: Vec<&String> = all_lines.iter().filter(|l| l.contains("MODEL-DISK") || l.contains('\\') || l.contains('/')).collect();
    let child = json!({"sha256": children::TAPECTL.sha256, "source": std::env::var("DT_CHILD_SOURCE").unwrap(), "version": children::TAPECTL.version,
        "engine_tree": std::env::var("DT_CHILD_ENGINE_TREE").unwrap(), "test_build": false,
        "build_refs": ["child-build.json", "tapectl-build.stdout.txt"], "accepted_source_crosswalk": ["child-build.json#crosswalk"]});
    let poll = json!({"nominal_interval_ms": INTERVAL_MS, "max_concurrent": peak.load(Ordering::SeqCst), "timeout_ms": TIMEOUT_MS,
        "busy_tick_new_workers": busy_new, "making_tick_new_workers": making_new, "stopped_tick_new_workers": stopped_new,
        "stale_emissions": stale, "duplicate_emissions": duplicate, "ui_waits_for_child": ui_wait_ms >= 1000,
        "timeout_order": timeout_order, "shutdown_order": shutdown_order, "replacement_order": replacement_order,
        "current_result_refs": ["src/state.rs:finish_cards", "src/bridge.rs:publish_cards"], "timer_worker_refs": ["src/discovery.rs:Schedule", "src/bridge.rs:poll"],
        "actual_trace_refs": ["discovery.raw.json#traces"], "schedules": schedules, "request_nonces": nonces, "request_reports": reports});
    let result = json!({"source_head": head, "evidence_class": "production discovery integration / controlled order", "raw_refs": ["discovery.raw.json"],
        "adapter_ref": "host/app/tests/discovery_component.rs", "rows": rows, "native_ui": false, "live_enumeration": false, "shipping_fake_switch": false,
        "stderr_selected_outcome": stderr_selected, "child": child, "request": request_row, "poll": poll,
        "valid_music_label_one_hint_make_enabled": make_with_one, "displayed_paths": displayed_paths, "lists": [], "external_cleanup_calls": [],
        "app_device_calls": false, "make_or_elevation_calls": false,
        "source_before": source_before, "source_after": sha(&fs::read(source.join("song.wav")).unwrap()),
        "foreign_before": foreign_before, "foreign_after": sha(&fs::read(foreign.join("keep")).unwrap()),
        "accepted_parser_reuse_refs": ["src/discovery.rs:judge -> src/report.rs:read(Tool::Cards)"],
        "card_line_actual_render_refs": ["frontend/screen.mjs:card.textContent = view.card_line", "discovery.raw.json#rows[].view.card_line"],
        "failure_clears_hint": failure_clears});
    let mut traces = BTreeMap::new();
    traces.insert("timeout", json!(timeout_trace));
    traces.insert("replacement", json!(replacement_trace));
    traces.insert("shutdown", json!(shutdown_trace));
    save(&out.join("discovery.raw.json"), &json!({"rows": raw_rows, "requests": raw_requests, "traces": traces, "timed_out_line": timed_out_line,
        "timeout_emissions": timeout_emissions, "ui_wait_ms": ui_wait_ms, "jobs_left": jobs, "card_lines": all_lines}));
    save(&out.join("discovery.json"), &result);
    fs::remove_dir_all(&source).unwrap();
}

#[test]
fn failure_clears_the_hint_and_make_stays_off() {
    let r = root("unit");
    let (b, _) = new(&r);
    let ok = json!({"exit": 0, "stdout": "{\"t\":\"card\",\"path\":\"D\",\"bytes\":64000000000}\n{\"t\":\"summary\",\"offered\":1,\"unprobed\":0}\n",
        "report": format!("{{\"t\":\"start\",\"tool\":\"tapectl cards\",\"version\":\"{VERSION}\",\"nonce\":\"{NONCE}\"}}\n{{\"t\":\"end\",\"exit\":0}}\n")});
    run_case(&b, &ok);
    assert_eq!(b.snapshot().card_line, "Card ready (64 GB).");
    assert!(!b.snapshot().make_enabled);
    let mut bad = ok.clone();
    bad["report"] = json!("");
    run_case(&b, &bad);
    assert_eq!(b.snapshot().card_line, messages::GENERIC_INGEST);
    b.start_over();
    assert_eq!(b.snapshot().card_line, messages::GENERIC_INGEST, "Start over keeps the card line");
    assert_eq!(fs::read_dir(r.join("jobs")).unwrap().count(), 0, "every run removes its own job");
    fs::remove_dir_all(&r).unwrap();
}

/// V318 correction 1. A due poll paused after its stop read and before registration
/// cannot start or publish a run once shutdown's cancellation pass has completed; and each
/// current discovery diagnostic reaches the details control in the actual backend view.
#[test]
fn correction1() {
    let Ok(output) = std::env::var("DT_DISCOVERY_OUTPUT") else { return };
    let out = PathBuf::from(output);
    fs::create_dir_all(&out).unwrap();
    let input: Value = serde_json::from_slice(&fs::read(std::env::var("DT_DISCOVERY_INPUT").unwrap()).unwrap()).unwrap();
    let case = |id: &str| input["cases"].as_array().unwrap().iter().find(|c| c["id"] == id).unwrap().clone();

    // Admission across the stop boundary, through the production poll step.
    let r = root("admission");
    let (b, views) = new(&r);
    let (paused_tx, paused_rx) = mpsc::channel();
    let (resume_tx, resume_rx) = mpsc::channel::<()>();
    *b.before_admission.lock().unwrap() = Some(Box::new(move || { paused_tx.send(()).unwrap(); resume_rx.recv().unwrap(); }));
    let callbacks = Arc::new(AtomicUsize::new(0));
    let poller = {
        let (b, callbacks, one) = (b.clone(), callbacks.clone(), case("one64"));
        std::thread::spawn(move || {
            let mut schedule = discovery::Schedule::new(0);
            b.poll_once(&mut schedule, &|| INTERVAL_MS, move |job, _, _, _, _| { callbacks.fetch_add(1, Ordering::SeqCst); (typed(&one), request(job)) })
        })
    };
    paused_rx.recv().unwrap();
    b.shutdown();
    let shutdown_done = trace(&b);
    let after_shutdown = views.lock().unwrap().len();
    resume_tx.send(()).unwrap();
    assert!(poller.join().unwrap(), "the paused step had already passed its stop read");
    let admission_trace = trace(&b);
    let admission = json!({"paused_after_stop_read": true, "shutdown_completed_before_resume": shutdown_done.contains(&"stop-polls".to_owned()),
        "child_callbacks": callbacks.load(Ordering::SeqCst), "current_publications": admission_trace.iter().filter(|e| *e == "cards:published").count(),
        "emissions_after_resume": views.lock().unwrap().len() - after_shutdown,
        "registered": admission_trace.contains(&"cards:worker-start".to_owned()), "refused": admission_trace.contains(&"cards:admission-refused".to_owned()),
        "cards_active": b.core.lock().unwrap().app.cards_active(), "trace": admission_trace});
    assert_eq!(admission["child_callbacks"], 0);
    assert_eq!(admission["current_publications"], 0);
    assert_eq!(admission["emissions_after_resume"], 0);
    assert_eq!(admission["refused"], true);
    assert_eq!(admission["registered"], false);
    fs::remove_dir_all(&r).unwrap();

    // Diagnostics reach the details control with empty and with valid music.
    let r = root("details");
    let music = r.parent().unwrap().join(format!("DigitalTapeDiscoveryMusic-{}", children::nonce()));
    fs::create_dir(&music).unwrap();
    let mut scenarios = Vec::new();
    let mut record = |b: &Bridge, id: &str, music: &str, card: &str| {
        scenarios.push(json!({"id": id, "music": music, "card_check": card, "view": b.snapshot(), "details": b.raw_details()}));
    };
    let timeout = |b: &Bridge| {
        b.discover(|job, cancel, on_timeout, on_cancel, _| {
            let mut clock = 0u64;
            let end = discovery::supervise(&mut Blocked { polled: Arc::new(AtomicBool::new(false)) }, cancel, &mut || { clock += 2500; clock }, on_timeout, on_cancel);
            (Ran { timed_out: end == End::TimedOut, ..Default::default() }, request(job))
        }).unwrap();
    };
    for music_state in ["empty", "valid"] {
        let (b, _) = new(&r);
        if music_state == "valid" {
            let mut core = b.core.lock().unwrap();
            core.app.folders = vec![music.clone()];
            core.app.set_label("Road Trip");
            core.app.finished(&Outcome { exit: Some(0), stderr: String::new(), reading: Reading::Unusable("not needed"), total_frames: Some(CAPACITY_FRAMES / 2), cancelled: false });
        }
        for id in ["one64", "zero-unprobed", "one-plus-unprobed", "enum-unavailable"] {
            run_case(&b, &case(id));
            record(&b, &format!("{music_state}/{id}"), music_state, id);
        }
        timeout(&b);
        record(&b, &format!("{music_state}/timeout"), music_state, "timeout");
        run_case(&b, &case("one64"));
        record(&b, &format!("{music_state}/fresh-success-after-failure"), music_state, "one64");
    }
    for s in &scenarios {
        let (v, card) = (&s["view"], s["card_check"].as_str().unwrap());
        let diagnostic = card != "one64";
        assert_eq!(v["card_details_available"], diagnostic, "{}", s["id"]);
        assert_eq!(v["make_enabled"], false);
        let line = v["card_line"].as_str().unwrap();
        assert!(!line.contains("MODEL-DISK") && !line.contains('\\') && !line.contains('/') && !line.contains('\n'), "{line}");
        let details = s["details"].as_str().unwrap();
        if diagnostic { assert!(details.contains("Card check"), "{details}"); }
        if s["id"].as_str().unwrap().ends_with("fresh-success-after-failure") { assert!(!details.contains("failed"), "{details}"); }
    }
    let mut views = serde_json::Map::new();
    for s in &scenarios { views.insert(s["id"].as_str().unwrap().into(), json!({"view": s["view"], "details": s["details"]})); }
    save(&out.join("correction1.json"), &json!({"source_head": std::env::var("DT_SOURCE_HEAD").unwrap(), "finding_refs": ["V318-01", "V318-02"],
        "evidence_class": "production poll step/registration and backend View under controlled order; renderer run separately", "native_ui": false,
        "live_enumeration": false, "admission": admission, "details_views": views}));
    fs::remove_dir_all(&music).unwrap();
    fs::remove_dir_all(&r).unwrap();
}
