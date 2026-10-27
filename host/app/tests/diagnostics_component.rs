// Software594 controlled method (Verification332, windows_diagnostics_r1 C01-C26, corrected r2). Compiled
// only as a Rust unit test inside `bridge`. Every case runs the production Command/
// run_hooked/Bridge/Session code with the test-only harmless `probe_child` (never the
// real INGEST, a window, a poller or a device). The harness keeps its own copies of the
// child's originals after the wait and before cleanup, so receipts are compared against
// bytes the logger did not produce. With DT_DIAG_EVIDENCE set, each case writes its
// session envelope, harness originals and observations there for receipts.py/cases.py.
#![cfg(windows)]
use super::*;
use crate::diagnostics::{self, Fault, Provenance, Route, Session, SINK_CALLS};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::{fs, path::{Path, PathBuf}, sync::mpsc, time::Duration};

const VERSION: &str = "0.1.1 INGEST-1 arithmetic-profile INGEST1-AP4";

#[link(name = "kernel32")]
extern "system" { fn GetConsoleWindow() -> *mut std::ffi::c_void; }

fn sha(b: &[u8]) -> String { Sha256::digest(b).iter().map(|x| format!("{x:02x}")).collect() }
fn b64(b: &[u8]) -> String {
    const A: &[u8; 64] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    let mut s = String::new();
    for c in b.chunks(3) {
        let n = (u32::from(c[0]) << 16) | (u32::from(*c.get(1).unwrap_or(&0)) << 8) | u32::from(*c.get(2).unwrap_or(&0));
        for i in 0..4 { s.push(if i <= c.len() { A[(n >> (18 - 6 * i) & 63) as usize] as char } else { '=' }); }
    }
    s
}
fn probe() -> PathBuf {
    std::env::var_os("DT_PROBE_CHILD").map(PathBuf::from).unwrap_or_else(|| {
        let exe = std::env::current_exe().unwrap();
        exe.parent().unwrap().parent().unwrap().join("examples").join("probe_child.exe")
    })
}

/// One case's owned root: the app data folder, fixtures and (optionally) its evidence.
struct Fx { case: &'static str, root: PathBuf, n: std::cell::Cell<u32> }
impl Fx {
    /// None (reported UNEXECUTED) when the helper was not built for this run; the 594
    /// workflow sets DT_DIAG_REQUIRE so a missing helper fails there instead.
    fn new(case: &'static str) -> Option<Fx> {
        if !probe().is_file() {
            assert!(std::env::var_os("DT_DIAG_REQUIRE").is_none(), "DT_DIAG_REQUIRE: helper missing at {}", probe().display());
            eprintln!("{case}: UNEXECUTED, test-only probe_child not built (cargo build --example probe_child)");
            return None;
        }
        let root = std::env::temp_dir().join(format!("dt594-{case}-{}", crate::children::nonce()));
        fs::create_dir_all(root.join("data")).unwrap();
        fs::create_dir_all(root.join("fixtures")).unwrap();
        Some(Fx { case, root, n: std::cell::Cell::new(0) })
    }
    fn data(&self) -> PathBuf { self.root.join("data") }
    /// A fresh owned fixture folder whose probe.json selects the helper's behavior.
    fn folder(&self, mode: &str, extra: Value) -> PathBuf {
        let i = self.n.get(); self.n.set(i + 1);
        let dir = self.root.join("fixtures").join(format!("{mode}-{i}"));
        fs::create_dir(&dir).unwrap();
        let mut cfg = json!({"mode": mode, "version": VERSION, "observe": self.root.join(format!("observe-{i}.json"))});
        for (k, v) in extra.as_object().cloned().unwrap_or_default() { cfg[k] = v; }
        fs::write(dir.join("probe.json"), serde_json::to_vec(&cfg).unwrap()).unwrap();
        dir
    }
    fn observed(&self, folder: &Path) -> Value {
        let cfg: Value = serde_json::from_slice(&fs::read(folder.join("probe.json")).unwrap()).unwrap();
        serde_json::from_slice(&fs::read(cfg["observe"].as_str().unwrap()).unwrap()).unwrap()
    }
    fn evidence(&self, name: &str, bytes: &[u8]) {
        if let Some(dir) = std::env::var_os("DT_DIAG_EVIDENCE") {
            let d = PathBuf::from(dir).join(self.case);
            fs::create_dir_all(&d).unwrap();
            fs::write(d.join(name), bytes).unwrap();
        }
    }
    fn json(&self, name: &str, v: &Value) { self.evidence(name, &serde_json::to_vec_pretty(v).unwrap()); }
    /// The session's own files, byte-exact, in receipts.py's envelope; `expect` is
    /// "complete", "incomplete" or "invalid" (a torn record).
    fn envelope(&self, s: &Session, tag: &str, expect: &str) -> (Vec<Value>, Value) {
        let dir = s.path_in(&self.data());
        let mut files = serde_json::Map::new();
        for (name, path) in [(diagnostics::MARKER.to_owned(), dir.join(diagnostics::MARKER)), ("records.jsonl".to_owned(), dir.join("records.jsonl"))] {
            files.insert(name, json!(b64(&fs::read(path).unwrap())));
        }
        for e in fs::read_dir(dir.join("blobs")).unwrap().flatten() {
            files.insert(format!("blobs/{}", e.file_name().to_string_lossy()), json!(b64(&fs::read(e.path()).unwrap())));
        }
        let rows = records(s, &self.data());
        let env = json!({"files": files});
        self.json(&format!("envelope-{tag}.json"), &env);
        self.evidence(&format!("expect-{tag}.txt"), expect.as_bytes());
        (rows, env)
    }
}
impl Drop for Fx {
    fn drop(&mut self) { if std::env::var_os("DT_DIAG_KEEP").is_none() { let _ = fs::remove_dir_all(&self.root); } }
}

fn records(s: &Session, data: &Path) -> Vec<Value> {
    let raw = fs::read(s.path_in(data).join("records.jsonl")).unwrap();
    raw.split(|&b| b == b'\n').filter(|l| !l.is_empty()).filter_map(|l| serde_json::from_slice(l).ok()).collect()
}
fn kinds(rows: &[Value]) -> Vec<String> { rows.iter().map(|r| r["kind"].as_str().unwrap().to_owned()).collect() }
fn of<'a>(rows: &'a [Value], kind: &str) -> Vec<&'a Value> { rows.iter().filter(|r| r["kind"] == kind).map(|r| &r["data"]).collect() }

/// Controlled provenance: this test executable and the checked-out source head.
fn provenance(source: bool) -> Provenance {
    let exe = std::env::current_exe().unwrap();
    Provenance { app_path: exe.to_string_lossy().into_owned(), app_sha256: sha(&fs::read(&exe).unwrap()),
        source_commit: if source { std::env::var("DT_SOURCE_HEAD").ok().filter(|s| s.len() == 40) } else { None },
        os_build: crate::win::os_build(), app_os_start_ns: crate::win::own_start_ns() }
}
fn bridge(fx: &Fx, s: Option<Session>) -> (Arc<Bridge>, mpsc::Receiver<Message>, Arc<Mutex<Vec<View>>>, Option<Arc<Session>>) {
    let views = Arc::new(Mutex::new(Vec::new()));
    let out = views.clone();
    let s = s.map(Arc::new);
    let (b, rx) = Bridge::channel_with(fx.data(), Arc::new(move |v| out.lock().unwrap().push(v)), s.clone());
    (b, rx, views, s)
}
fn next(rx: &mpsc::Receiver<Message>) -> Work {
    match rx.recv_timeout(Duration::from_secs(5)).unwrap() { Message::Check(w) => w, Message::Stop => panic!("check expected") }
}
fn drop_folder(b: &Bridge, p: &Path) -> View { b.drop_routed(Route::ControlledTest, json!([p]), drops::classify) }

/// Harness copies taken in the worker closure after the child's wait, before cleanup.
#[derive(Default, Clone)]
struct Originals { report: Option<Vec<u8>>, manifest: Option<Vec<u8>>, audio: Option<Vec<u8>>, stdout: Vec<u8>, stderr: Vec<u8>, receipt: Value }

/// The production worker with the probe in place of the pinned child; `flags` lets C02
/// clear CREATE_NO_WINDOW on the production Command, test-only.
fn run(b: &Bridge, work: Work, bin: &Path, flags: Option<u32>) -> Originals {
    let kept = Mutex::new(Originals::default());
    b.execute_with(work, |job, work, receipt, spawned| {
        let (mut cmd, prepared) = ingest_job::command(bin, VERSION, job, &work.folders);
        if let Some(f) = flags {
            use std::os::windows::process::CommandExt;
            cmd.creation_flags(f);
        }
        *receipt = prepared;
        if let Some(f) = flags { receipt.creation_flags = f; }
        let o = ingest_job::run_command(cmd, VERSION, &work.folders, work.cancel.clone(), receipt, spawned);
        let mut k = kept.lock().unwrap();
        k.report = fs::read(&receipt.report).ok();
        k.manifest = fs::read(receipt.dest.join("manifest.json")).ok();
        k.audio = fs::read(receipt.dest.join("audio.wav")).ok();
        k.stdout = receipt.stdout.clone();
        k.stderr = receipt.stderr.clone();
        k.receipt = json!({"pid": receipt.pid, "exit": receipt.exit, "argv": receipt.argv, "cwd": receipt.cwd, "nonce": receipt.nonce,
            "report": receipt.report, "dest": receipt.dest, "creation_flags": receipt.creation_flags, "env_sha256": receipt.env_sha256,
            "os_start_ns": receipt.os_start_ns.map(|n| n as u64), "spawn_call_ns": receipt.spawn_call_ns as u64, "cancelled": receipt.cancelled,
            "wait_kind": receipt.wait_kind, "spawn_error": receipt.spawn_error, "job_dir": job.dir});
        Ok(o)
    });
    kept.into_inner().unwrap()
}
fn keep(fx: &Fx, tag: &str, k: &Originals) {
    fx.json(&format!("receipt-{tag}.json"), &k.receipt);
    for (n, b) in [("report", &k.report), ("manifest", &k.manifest)] { if let Some(b) = b { fx.evidence(&format!("original-{tag}-{n}.bin"), b); } }
    fx.evidence(&format!("original-{tag}-stdout.bin"), &k.stdout);
    fx.evidence(&format!("original-{tag}-stderr.bin"), &k.stderr);
    if let Some(a) = &k.audio { fx.json(&format!("original-{tag}-audio.json"), &json!({"sha256": sha(a), "bytes": a.len()})); }
}
/// The independently comparable projection (cases.parity): only proven own job path,
/// report path and nonce tokens are normalized; exits/streams/outputs/state are not.
fn projection(k: &Originals, v: &View, cleaned: bool) -> Value {
    let r = &k.receipt;
    let (nonce, job) = (r["nonce"].as_str().unwrap(), r["job_dir"].as_str().unwrap());
    let norm = |s: &str| s.replace(job, "<JOB>").replace(nonce, "<NONCE>");
    let argv: Vec<String> = r["argv"].as_array().unwrap().iter().map(|a| norm(a.as_str().unwrap())).collect();
    let report = k.report.as_ref().map(|b| sha(norm(&String::from_utf8_lossy(b)).as_bytes()));
    json!({"exe_sha256": sha(&fs::read(&argv[0]).unwrap()), "argv": argv, "cwd": norm(r["cwd"].as_str().unwrap()), "env_sha256": r["env_sha256"],
        "exit": r["exit"], "stdout_sha256": sha(&k.stdout), "stderr_sha256": sha(&k.stderr), "report_sha256": report,
        "manifest_sha256": k.manifest.as_ref().map(|b| sha(b)), "audio_sha256": k.audio.as_ref().map(|b| sha(b)),
        "audio_bytes": k.audio.as_ref().map(Vec::len), "total_frames": v.total_frames,
        "state": json!({"view": v.view, "checking": v.checking, "message": v.message, "details_available": v.details_available, "make_enabled": v.make_enabled}),
        "cleanup": if cleaned { "removed" } else { "present" }, "reaped": r["exit"].is_number() || r["cancelled"] == true})
}
/// One full positive flow through drop → worker → probe → delivery → cleanup → close.
fn flow(fx: &Fx, s: Option<Session>, mode: &str, extra: Value, tag: &str) -> (Originals, View, Option<Arc<Session>>, bool) {
    let music = fx.folder(mode, extra);
    flow_in(fx, s, &music, tag)
}
/// The same flow over an existing fixture folder, so OFF/ON or healthy/faulty runs see
/// identical inputs.
fn flow_in(fx: &Fx, s: Option<Session>, music: &Path, tag: &str) -> (Originals, View, Option<Arc<Session>>, bool) {
    let (b, rx, _, s) = bridge(fx, s);
    drop_folder(&b, music);
    let k = run(&b, next(&rx), &probe(), None);
    let view = b.snapshot();
    let job = PathBuf::from(k.receipt["job_dir"].as_str().unwrap());
    let cleaned = !job.exists();
    b.shutdown();
    keep(fx, tag, &k);
    (k, view, s, cleaned)
}
fn assert_blobs_match(rows: &[Value], fx: &Fx, s: &Session, k: &Originals) {
    let dir = s.path_in(&fx.data());
    for b in of(rows, "blob") {
        let stored = fs::read(dir.join(b["leaf"].as_str().unwrap().replace('/', "\\"))).unwrap();
        let original = match b["role"].as_str().unwrap() { "report" => k.report.clone().unwrap(), "manifest" => k.manifest.clone().unwrap(), "stdout" => k.stdout.clone(), _ => k.stderr.clone() };
        assert_eq!(stored, original, "{} differs from the harness original", b["role"]);
        assert_eq!(b["sha256"], sha(&original));
    }
}

#[test]
fn c01_c02_console_association() {
    let Some(fx) = Fx::new("C01-C02") else { return };
    let (b, rx, _, _) = bridge(&fx, None);
    let a = fx.folder("success", json!({}));
    drop_folder(&b, &a);
    let k1 = run(&b, next(&rx), &probe(), None);
    let o1 = fx.observed(&a);
    b.start_over();
    let c = fx.folder("success", json!({}));
    drop_folder(&b, &c);
    let k2 = run(&b, next(&rx), &probe(), Some(0));
    let o2 = fx.observed(&c);
    // SAFETY: no arguments.
    let runner = !unsafe { GetConsoleWindow() }.is_null();
    let report = json!({"runner_pid": std::process::id(), "runner_console_window": runner, "runner_exe_sha256": sha(&fs::read(std::env::current_exe().unwrap()).unwrap()),
        "probe_sha256": sha(&fs::read(probe()).unwrap()),
        "C01": {"creation_flags": k1.receipt["creation_flags"], "child": o1, "receipt": k1.receipt},
        "C02": {"creation_flags": k2.receipt["creation_flags"], "child": o2, "receipt": k2.receipt,
                "status": if runner { "observed" } else { "UNEXECUTED: this runner has no console to inherit" }}});
    fx.json("console.json", &report);
    assert_eq!(k1.receipt["creation_flags"], json!(ingest_job::INGEST_CREATION_FLAGS));
    assert_eq!(o1["console_window"], json!(false), "CREATE_NO_WINDOW child must have no console");
    assert_eq!(o1["pid"], k1.receipt["pid"]);
    if runner { assert_eq!(o2["console_window"], json!(true), "flag removed: the child inherits the runner's console"); }
    // C01's actual command against caller-owned expectations (cases.command shape).
    let r = &k1.receipt;
    fx.json("command.json", &json!({"actual": {"exe": r["argv"][0], "argv": r["argv"], "cwd": r["cwd"], "env_sha256": r["env_sha256"],
        "stdin": "null", "stdout": "piped", "stderr": "piped", "creation_flags": r["creation_flags"]},
        "expected": {"exe": probe(), "report": r["report"], "nonce": r["nonce"], "dest": r["dest"], "folders": [a], "job_dir": r["job_dir"], "env_sha256": ingest_job::env_sha256()}}));
    assert_eq!(o1["argv"], r["argv"]);
    assert_eq!(o1["cwd"], r["cwd"]);
}

#[test]
fn c03_c17_c18_success_chain() {
    let Some(fx) = Fx::new("C03-C17-C18") else { return };
    let s = Session::open(&fx.data(), provenance(true)).unwrap();
    let (k, view, s, cleaned) = flow(&fx, Some(s), "success", json!({"frames": 4}), "success");
    let s = s.unwrap();
    let (rows, _) = fx.envelope(&s, "success", "complete");
    assert_eq!(view.view, "ready");
    assert_eq!(view.total_frames, Some(4));
    assert!(cleaned, "the job is removed after the terminal");
    let ks = kinds(&rows);
    let at = |k: &str| ks.iter().position(|x| x == k).unwrap_or_else(|| panic!("no {k}"));
    assert!(at("child-launch") < at("child-terminal") && at("child-terminal") < at("blob") && at("blob") < at("cleanup") && at("cleanup") < at("session-end"));
    let launch = of(&rows, "child-launch")[0];
    assert_eq!(launch["pid"], k.receipt["pid"]);
    assert_eq!(launch["argv"], k.receipt["argv"]);
    assert_eq!(launch["creation_flags"], json!(0x0800_0000));
    assert!(launch["os_start_ns"].as_u64().unwrap() > 0 && launch["os_start_ns"] != launch["spawn_call_ns"]);
    assert_blobs_match(&rows, &fx, &s, &k);
    let audio = of(&rows, "audio")[0];
    assert_eq!(audio["sha256"], sha(k.audio.as_ref().unwrap()));
    assert_eq!(audio["bytes"], json!(60));
    assert_eq!(audio["total_frames"], json!(4));
    let names: Vec<String> = walk(&s.path_in(&fx.data()));
    assert!(names.iter().all(|n| !n.ends_with(".wav")), "no audio is copied: {names:?}");
    let end = of(&rows, "session-end")[0];
    if std::env::var("DT_SOURCE_HEAD").is_ok() { assert_eq!(end["complete"], json!(true), "{end}"); }
}
fn walk(d: &Path) -> Vec<String> {
    let mut v = Vec::new();
    for e in fs::read_dir(d).unwrap().flatten() {
        if e.path().is_dir() { v.extend(walk(&e.path())); } else { v.push(e.path().to_string_lossy().into_owned()); }
    }
    v
}

#[test]
fn c04_refusal_chain() {
    let Some(fx) = Fx::new("C04") else { return };
    let s = Session::open(&fx.data(), provenance(true)).unwrap();
    let (k, view, s, cleaned) = flow(&fx, Some(s), "refusal", json!({}), "refusal");
    let s = s.unwrap();
    let (rows, _) = fx.envelope(&s, "refusal", "complete");
    assert_eq!(view.view, "problem");
    assert_eq!(k.receipt["exit"], json!(2));
    assert!(cleaned && k.manifest.is_none());
    assert_blobs_match(&rows, &fx, &s, &k);
    assert!(of(&rows, "audio").is_empty() && of(&rows, "blob").iter().all(|b| b["role"] != "manifest"));
}

#[test]
fn c05_missing_executable_and_unpinned_child() {
    let Some(fx) = Fx::new("C05") else { return };
    let s = Session::open(&fx.data(), provenance(true)).unwrap();
    let (b, rx, _, s) = bridge(&fx, Some(s));
    drop_folder(&b, &fx.folder("success", json!({})));
    let k = run(&b, next(&rx), &fx.root.join("missing-child.exe"), None);
    assert!(k.receipt["pid"].is_null() && k.receipt["spawn_error"].is_string());
    b.start_over();
    drop_folder(&b, &fx.folder("success", json!({})));
    b.execute_with(next(&rx), |_, _, _, _| Err("this build has no pinned ingest.exe".into()));
    b.shutdown();
    let s = s.unwrap();
    let (rows, _) = fx.envelope(&s, "missing", "complete");
    let nl = of(&rows, "child-not-launched");
    assert_eq!(nl.len(), 2);
    assert!(of(&rows, "child-launch").is_empty() && of(&rows, "child-terminal").is_empty(), "no invented PID or wait");
    let disp: Vec<_> = of(&rows, "outcome").iter().map(|o| o["disposition"].as_str().unwrap().to_owned()).collect();
    assert_eq!(disp, ["delivered", "failed"]);
    assert!(of(&rows, "cleanup").iter().all(|c| c["result"] == "removed"));
}

/// A sleeping child stopped by `stop` (Start over or shutdown) while the worker waits on
/// it: `mode` "sleep" after its report exists, "sleep-before-report" before it creates one.
fn cancel_case(case: &'static str, shutdown: bool, mode: &str) {
    let Some(fx) = Fx::new(case) else { return };
    let s = Session::open(&fx.data(), provenance(true)).unwrap();
    let (b, rx, _, s) = bridge(&fx, Some(s));
    let sleep = fx.folder(mode, json!({}));
    drop_folder(&b, &sleep);
    let w = next(&rx);
    let runner = b.clone();
    let worker = std::thread::spawn(move || run(&runner, w, &probe(), None));
    let cfg: Value = serde_json::from_slice(&fs::read(sleep.join("probe.json")).unwrap()).unwrap();
    let observe = PathBuf::from(cfg["observe"].as_str().unwrap());
    for _ in 0..200 { if observe.exists() { break; } std::thread::sleep(Duration::from_millis(50)); }
    assert!(observe.exists(), "the helper started");
    let k = if shutdown {
        // Teardown joins the worker before the footer, as production shutdown does.
        *b.worker.lock().unwrap() = Some(std::thread::spawn(move || { let k = worker.join().unwrap(); keep_slot(k); }));
        b.shutdown();
        take_slot()
    } else {
        b.start_over();
        let k = worker.join().unwrap();
        b.shutdown();
        k
    };
    keep(&fx, "cancel", &k);
    let s = s.unwrap();
    let (rows, _) = fx.envelope(&s, "cancel", "incomplete");
    let end = of(&rows, "session-end")[0];
    assert_eq!(end["complete"], json!(false));
    let reasons: Vec<&str> = end["reason"].as_str().unwrap().split(';').collect();
    let reports: Vec<_> = of(&rows, "blob").into_iter().filter(|b| b["role"] == "report").collect();
    if mode == "sleep" {
        assert!(reasons.contains(&"cancelled-child-report"), "{end}");
        assert_eq!(reports.len(), 1, "the partial report is kept as left");
    } else {
        assert!(k.report.is_none(), "the helper never created its report");
        assert!(reasons.contains(&"cancelled-before-report"), "{end}");
        assert!(reports.is_empty());
        let m = of(&rows, "missing");
        assert_eq!((m.len(), &m[0]["role"]), (1, &json!("report")), "the absence is recorded honestly");
        assert!(of(&rows, "blob").iter().any(|b| b["role"] == "stdout") && of(&rows, "blob").iter().any(|b| b["role"] == "stderr"));
    }
    let t = of(&rows, "child-terminal")[0];
    assert_eq!(t["cancelled"], json!(true));
    assert_eq!(t["wait_kind"], json!("wait"));
    assert_eq!(of(&rows, "outcome")[0]["disposition"], json!("stale-dropped"));
    assert_eq!(of(&rows, "cleanup")[0]["result"], json!("removed"));
    assert!(kinds(&rows).last().unwrap() == "session-end");
    assert!(!alive(k.receipt["pid"].as_u64().unwrap() as u32), "the killed helper was reaped");
}
static SLOT: Mutex<Option<Originals>> = Mutex::new(None);
fn keep_slot(k: Originals) { *SLOT.lock().unwrap() = Some(k); }
fn take_slot() -> Originals { SLOT.lock().unwrap().take().unwrap() }
fn alive(pid: u32) -> bool {
    let out = std::process::Command::new("tasklist").args(["/FI", &format!("PID eq {pid}"), "/NH", "/FO", "CSV"]).output().unwrap();
    String::from_utf8_lossy(&out.stdout).contains(&format!("\"{pid}\""))
}
#[test]
fn c06_cancellation() { cancel_case("C06", false, "sleep"); }
#[test]
fn c06_cancelled_before_report() { cancel_case("C06-before-report", false, "sleep-before-report"); }
#[test]
fn c07_teardown_during_child() { cancel_case("C07", true, "sleep"); }
#[test]
fn c07_teardown_before_report() { cancel_case("C07-before-report", true, "sleep-before-report"); }

#[test]
fn c08_off_on_parity() {
    let Some(fx) = Fx::new("C08") else { return };
    let mut out = serde_json::Map::new();
    for mode in ["success", "refusal"] {
        let folder = fx.folder(mode, json!({}));
        let (off, voff, _, coff) = flow_in(&fx, None, &folder, &format!("{mode}-off"));
        let s = Session::open(&fx.data(), provenance(true)).unwrap();
        let (on, von, _, con) = flow_in(&fx, Some(s), &folder, &format!("{mode}-on"));
        let (p, q) = (projection(&off, &voff, coff), projection(&on, &von, con));
        assert_eq!(p, q, "{mode}: diagnostics changed an observable");
        out.insert(mode.into(), json!({"off": p, "on": q, "normalization": "own job_dir -> <JOB>, own nonce -> <NONCE>, in argv/cwd/report only"}));
    }
    fx.json("parity.json", &Value::Object(out));
}

#[test]
fn c09_opt_in_and_off_zero_sink_calls() {
    use std::ffi::OsString;
    let a = |v: &[&str]| v.iter().map(OsString::from).collect::<Vec<_>>();
    assert!(diagnostics::opted_in(&a(&["app", "--diagnostic-receipts"])));
    for bad in [&["app"][..], &["app", "--diagnostic-receipts=x"], &["app", "--diagnostic-receipts", "--diagnostic-receipts"], &["app", "--diagnostic-receipts", "C:\\x"], &["app", "--DIAGNOSTIC-RECEIPTS"]] {
        assert!(!diagnostics::opted_in(&a(bad)), "{bad:?}");
    }
    let Some(fx) = Fx::new("C09") else { return };
    SINK_CALLS.with(|c| c.set(0));
    let (k, view, s, _) = flow(&fx, None, "success", json!({}), "off");
    assert!(s.is_none() && view.view == "ready" && k.receipt["exit"] == json!(0));
    assert_eq!(SINK_CALLS.with(|c| c.get()), 0, "OFF made diagnostic sink calls");
    assert!(!fx.data().join("control").exists(), "OFF created the control folder");
    fx.json("off.json", &json!({"sink_calls": 0, "control_exists": false}));
}

#[test]
fn c10_c26_exclusive_session_and_retention() {
    let Some(fx) = Fx::new("C10-C26") else { return };
    let control = fx.data().join("control");
    fs::create_dir_all(control.join("diag-old")).unwrap();
    let (foreign, old) = (b"foreign bytes, not the app's\n".to_vec(), b"an older session's records\n".to_vec());
    fs::write(control.join("foreign.txt"), &foreign).unwrap();
    fs::write(control.join("diag-old").join("records.jsonl"), &old).unwrap();
    let s1 = Session::open(&fx.data(), provenance(true)).unwrap();
    let (_, _, s1, _) = flow(&fx, Some(s1), "success", json!({}), "first");
    let s1 = s1.unwrap();
    let before = snapshot(&s1.path_in(&fx.data()));
    let s2 = Session::open(&fx.data(), provenance(true)).unwrap();
    assert_ne!(s1.dir_name, s2.dir_name);
    drop(s2);
    assert_eq!(fs::read(control.join("foreign.txt")).unwrap(), foreign);
    assert_eq!(fs::read(control.join("diag-old").join("records.jsonl")).unwrap(), old);
    assert_eq!(snapshot(&s1.path_in(&fx.data())), before, "a later session never touches an earlier one");
    fx.envelope(&s1, "first", "complete");
    fx.json("foreign.json", &json!({"foreign_sha256": sha(&foreign), "old_sha256": sha(&old), "after_first_session_unchanged": true}));
}
fn snapshot(d: &Path) -> Vec<(String, String)> {
    let mut v: Vec<_> = walk(d).into_iter().map(|p| { let s = sha(&fs::read(&p).unwrap()); (p, s) }).collect();
    v.sort();
    v
}

#[test]
fn c11_occupied_leaves_fail_closed() {
    let Some(fx) = Fx::new("C11") else { return };
    // An occupied session directory: the open fails, the occupant is untouched.
    let id = crate::children::nonce();
    let occupied = fx.data().join("control").join(format!("diag-{id}"));
    fs::create_dir_all(&occupied).unwrap();
    fs::write(occupied.join("records.jsonl"), b"someone else's\n").unwrap();
    let e = Session::open_faulty(&fx.data(), provenance(true), id, None).err().expect("occupied session must fail");
    assert_eq!(e.kind(), std::io::ErrorKind::AlreadyExists);
    assert_eq!(fs::read(occupied.join("records.jsonl")).unwrap(), b"someone else's\n");
    // An occupied blob leaf: the report blob of a one-drop success is record 7.
    let id = crate::children::nonce();
    let s = Session::open_faulty(&fx.data(), provenance(true), id, None).unwrap();
    let leaf = s.path_in(&fx.data()).join("blobs").join("00000007-report.bin");
    fs::write(&leaf, b"foreign leaf").unwrap();
    let (k, view, s, cleaned) = flow(&fx, Some(s), "success", json!({}), "occupied");
    assert_eq!(fs::read(&leaf).unwrap(), b"foreign leaf");
    assert!(view.view == "ready" && cleaned && k.receipt["exit"] == json!(0), "the child's outcome and cleanup are unchanged");
    let s = s.unwrap();
    let (rows, _) = fx.envelope(&s, "occupied", "incomplete");
    assert_eq!(kinds(&rows).last().unwrap(), "incomplete");
}

/// Ordinary unprivileged directory junction (mklink /J), owned fixture only.
fn junction(link: &Path, target: &Path) {
    let st = std::process::Command::new("cmd").args(["/C", "mklink", "/J"]).arg(link).arg(target).output().unwrap();
    assert!(st.status.success(), "{}", String::from_utf8_lossy(&st.stderr));
}
#[test]
fn c12_substitution_never_written_through() {
    let Some(fx) = Fx::new("C12") else { return };
    let elsewhere = fx.root.join("elsewhere");
    fs::create_dir_all(&elsewhere).unwrap();
    fs::write(elsewhere.join("sentinel"), b"keep").unwrap();
    // A control folder that is a junction: refused, nothing written through it.
    junction(&fx.data().join("control"), &elsewhere);
    assert!(Session::open(&fx.data(), provenance(true)).is_err());
    assert_eq!(walk(&elsewhere).len(), 1);
    fs::remove_dir(fx.data().join("control")).unwrap();
    // A data root that is a junction: refused.
    let linked = fx.root.join("linked-data");
    junction(&linked, &fx.data());
    assert!(Session::open(&linked, provenance(true)).is_err());
    // Held directories cannot be renamed or removed while the session is open.
    let s = Session::open(&fx.data(), provenance(true)).unwrap();
    let dir = s.path_in(&fx.data());
    let moved = [fs::rename(fx.data().join("control"), fx.root.join("moved")).is_err(),
        fs::rename(&dir, fx.data().join("control").join("moved")).is_err(),
        fs::remove_dir_all(dir.join("blobs")).is_err()];
    assert_eq!(moved, [true, true, true], "a held directory was replaced");
    let (_, _, s, _) = flow(&fx, Some(s), "success", json!({}), "held");
    let s = s.unwrap();
    fx.envelope(&s, "held", "complete");
    assert_eq!(walk(&elsewhere).len(), 1);
    fx.json("substitution.json", &json!({"control_junction_refused": true, "root_junction_refused": true, "held_rename_or_remove_refused": moved}));
}

#[test]
fn c13_stale_after_reset_and_new_drop() {
    let Some(fx) = Fx::new("C13") else { return };
    let s = Session::open(&fx.data(), provenance(true)).unwrap();
    let (b, rx, _, s) = bridge(&fx, Some(s));
    let sleep = fx.folder("sleep", json!({}));
    drop_folder(&b, &sleep);
    let w1 = next(&rx);
    let runner = b.clone();
    let worker = std::thread::spawn(move || run(&runner, w1, &probe(), None));
    let observe = fx.root.join("observe-0.json");
    for _ in 0..200 { if observe.exists() { break; } std::thread::sleep(Duration::from_millis(50)); }
    b.start_over();
    drop_folder(&b, &fx.folder("success", json!({})));
    let w2 = next(&rx);
    let k1 = worker.join().unwrap();
    let k2 = run(&b, w2, &probe(), None);
    b.shutdown();
    keep(&fx, "old", &k1);
    keep(&fx, "new", &k2);
    let s = s.unwrap();
    let (rows, _) = fx.envelope(&s, "stale", "incomplete");
    let disp: Vec<_> = of(&rows, "outcome").iter().map(|o| o["disposition"].as_str().unwrap().to_owned()).collect();
    assert_eq!(disp, ["stale-dropped", "delivered"]);
    assert_eq!(of(&rows, "cleanup").len(), 2);
}

#[test]
fn c13_cumulative_folders() {
    // Production runs INGEST over every folder so far (APP-1 §2); r2 freezes each work's
    // cumulative ordered snapshot, so this original chain is complete as recorded.
    let Some(fx) = Fx::new("C13-cumulative") else { return };
    let s = Session::open(&fx.data(), provenance(true)).unwrap();
    let (b, rx, _, s) = bridge(&fx, Some(s));
    drop_folder(&b, &fx.folder("success", json!({})));
    let k1 = run(&b, next(&rx), &probe(), None);
    drop_folder(&b, &fx.folder("success", json!({})));
    let k2 = run(&b, next(&rx), &probe(), None);
    b.shutdown();
    keep(&fx, "first", &k1);
    keep(&fx, "second", &k2);
    let s = s.unwrap();
    let (rows, _) = fx.envelope(&s, "cumulative", "complete");
    assert_eq!(of(&rows, "session-end")[0]["complete"], json!(true));
    let second = of(&rows, "child-launch")[1];
    assert_eq!(second["argv"].as_array().unwrap().len(), 12, "two folders after --");
}

#[test]
fn c14_queued_work_cancelled_before_admission() {
    let Some(fx) = Fx::new("C14") else { return };
    let s = Session::open(&fx.data(), provenance(true)).unwrap();
    let (b, rx, _, s) = bridge(&fx, Some(s));
    drop_folder(&b, &fx.folder("success", json!({})));
    let w = next(&rx);
    b.start_over();
    let k = run(&b, w, &probe(), None);
    b.shutdown();
    assert!(k.receipt.is_null(), "no child ran");
    let s = s.unwrap();
    let (rows, _) = fx.envelope(&s, "skipped", "complete");
    assert_eq!(of(&rows, "work-skipped").len(), 1);
    assert!(of(&rows, "job-admit").is_empty() && of(&rows, "child-launch").is_empty() && of(&rows, "cleanup").is_empty());
}

#[test]
fn c15_c16_routes_and_refusals() {
    let Some(fx) = Fx::new("C15-C16") else { return };
    let s = Session::open(&fx.data(), provenance(true)).unwrap();
    let (b, _rx, _, s) = bridge(&fx, Some(s));
    let file = fx.root.join("Not a song.txt");
    fs::write(&file, b"text").unwrap();
    b.drop_routed(Route::ControlledTest, json!([file]), drops::classify);
    b.drop_routed(Route::ControlledTest, json!([]), drops::classify);
    b.drop_routed(Route::ControlledTest, json!("not a list"), drops::classify);
    b.drop_routed(Route::ControlledTest, json!([1]), drops::classify);
    b.shutdown();
    let s = s.unwrap();
    let (rows, _) = fx.envelope(&s, "refusals", "complete");
    assert!(of(&rows, "ingress").iter().all(|i| i["route"] == "controlled-test"), "a test never claims a native gesture");
    let d: Vec<_> = of(&rows, "drop").iter().map(|d| (d["decision"].as_str().unwrap().to_owned(), d["reason"].as_str().unwrap().to_owned())).collect();
    assert_eq!(d, [("reject".into(), "not-folder".into()), ("no-change".into(), "empty".into()), ("reject".into(), "not-a-list".into()), ("reject".into(), "invalid-path".into())]);
    assert!(of(&rows, "job-admit").is_empty() && of(&rows, "child-launch").is_empty());
}

#[test]
fn c19_malformed_report_retained() {
    let Some(fx) = Fx::new("C19") else { return };
    let s = Session::open(&fx.data(), provenance(true)).unwrap();
    let (k, view, s, _) = flow(&fx, Some(s), "malformed", json!({}), "malformed");
    let s = s.unwrap();
    let (rows, _) = fx.envelope(&s, "malformed", "incomplete");
    assert_eq!(view.view, "problem");
    assert_blobs_match(&rows, &fx, &s, &k);
    let end = of(&rows, "session-end")[0];
    assert_eq!(end["complete"], json!(false));
    assert!(end["reason"].as_str().unwrap().split(';').any(|r| r == "invalid-original-report"), "{end}");
}

#[test]
fn c20_unknown_provenance_incomplete() {
    let Some(fx) = Fx::new("C20") else { return };
    let s = Session::open(&fx.data(), provenance(false)).unwrap();
    let (_, _, s, _) = flow(&fx, Some(s), "success", json!({}), "unknown");
    let s = s.unwrap();
    let (rows, _) = fx.envelope(&s, "unknown", "incomplete");
    assert!(of(&rows, "session")[0]["source_commit"].is_null());
    assert!(of(&rows, "session-end")[0]["reason"].as_str().unwrap().split(';').any(|r| r == "unknown-provenance"));
}

/// F332-2: BUILD.json names the source only for the exact running executable.
#[test]
fn c20_source_bound_to_the_running_app() {
    let (Some(ingest), Some(tapectl)) = (crate::children::INGEST.sha256, crate::children::TAPECTL.sha256) else {
        eprintln!("C20-binding: UNEXECUTED, child pins not compiled in");
        return;
    };
    let p = provenance(true);
    let head = "a".repeat(40);
    let meta = |files: Value| serde_json::to_vec(&json!({"source_head": head, "child_pin": ingest, "tapectl_pin": tapectl, "files": files})).unwrap();
    let entry = |name: &str, sha: &str| json!({"name": name, "bytes": 1, "sha256": sha});
    let other = "d".repeat(64);
    assert_eq!(diagnostics::bound_source(&meta(json!([entry("digital-tape.exe", &p.app_sha256), entry("ingest.exe", ingest)])), &p.app_sha256), Some(head.clone()));
    for (why, build) in [
        ("stale sidecar: same pins, another app", meta(json!([entry("digital-tape.exe", &other)]))),
        ("no app entry", meta(json!([entry("ingest.exe", ingest)]))),
        ("two app entries", meta(json!([entry("digital-tape.exe", &p.app_sha256), entry("digital-tape.exe", &p.app_sha256)]))),
        ("no files", serde_json::to_vec(&json!({"source_head": head, "child_pin": ingest, "tapectl_pin": tapectl})).unwrap()),
        ("other child pin", serde_json::to_vec(&json!({"source_head": head, "child_pin": other, "tapectl_pin": tapectl, "files": [entry("digital-tape.exe", &p.app_sha256)]})).unwrap()),
    ] {
        assert_eq!(diagnostics::bound_source(&build, &p.app_sha256), None, "{why}");
    }
    assert_eq!(diagnostics::bound_source(&meta(json!([entry("digital-tape.exe", "")])), ""), None, "an unmeasured app binds nothing");

    // A stale sidecar leaves the source unknown, and so does an unmeasured app: neither
    // session may be complete.
    let Some(fx) = Fx::new("C20-binding") else { return };
    let stale = Provenance { source_commit: diagnostics::bound_source(&meta(json!([entry("digital-tape.exe", &other)])), &p.app_sha256), ..p.clone() };
    let unmeasured = Provenance { app_path: String::new(), app_sha256: String::new(), ..p.clone() };
    for (tag, prov, expect) in [("stale", stale, "incomplete"), ("unmeasured", unmeasured, "invalid")] {
        let s = Session::open(&fx.data(), prov).unwrap();
        s.finish();
        // receipts.py rejects a header without an app path/hash outright ("invalid"); the
        // writer still never calls it complete.
        let (rows, _) = fx.envelope(&s, tag, expect);
        let end = of(&rows, "session-end")[0];
        assert_eq!(end["complete"], json!(false), "{tag}");
        assert_eq!(end["reason"], json!("unknown-provenance"), "{tag}");
    }
}

/// The exact bytes Session writes for an ingress record (same construction).
fn ingress_len(id: &str, seq: u64, drop_id: &str, paths: &[String], generation: u64) -> usize {
    serde_json::to_vec(&json!({"schema": 1, "session": id, "seq": seq, "kind": "ingress", "data": {"drop_id": drop_id, "route": "controlled-test", "paths": paths, "generation": generation}})).unwrap().len() + 1
}
#[test]
fn c21_line_limit() {
    let Some(fx) = Fx::new("C21") else { return };
    let s = Session::open(&fx.data(), provenance(true)).unwrap();
    let id = s.id();
    let (b, _rx, _, s) = bridge(&fx, Some(s));
    let fit = |seq: u64, drop: &str, want: usize| {
        let mut p = String::from("C:\\x");
        let base = ingress_len(&id, seq, drop, &[p.clone()], 0);
        p.push_str(&"y".repeat(want - base));
        assert_eq!(ingress_len(&id, seq, drop, &[p.clone()], 0), want);
        p
    };
    let exact = fit(1, "drop-0", 65_536);
    b.drop_routed(Route::ControlledTest, json!([exact]), drops::classify);
    let over = fit(3, "drop-1", 65_537);
    b.drop_routed(Route::ControlledTest, json!([over]), drops::classify);
    b.shutdown();
    let s = s.unwrap();
    let (rows, _) = fx.envelope(&s, "line", "incomplete");
    let raw = fs::read(s.path_in(&fx.data()).join("records.jsonl")).unwrap();
    let lens: Vec<usize> = raw.split_inclusive(|&b| b == b'\n').map(<[u8]>::len).collect();
    assert_eq!(lens[1], 65_536, "the boundary line is accepted");
    assert_eq!(of(&rows, "incomplete")[0]["reason"], json!("record-line-over-limit"));
    assert_eq!(kinds(&rows).last().unwrap(), "incomplete");
}

#[test]
fn c22_blob_limit() {
    let Some(fx) = Fx::new("C22") else { return };
    let s = Session::open(&fx.data(), provenance(true)).unwrap();
    let (b, rx, _, s) = bridge(&fx, Some(s));
    drop_folder(&b, &fx.folder("success", json!({"stdout_bytes": 4_194_304})));
    let k1 = run(&b, next(&rx), &probe(), None);
    b.start_over();
    drop_folder(&b, &fx.folder("success", json!({"stdout_bytes": 4_194_305})));
    let k2 = run(&b, next(&rx), &probe(), None);
    let view = b.snapshot();
    let cleaned = !PathBuf::from(k2.receipt["job_dir"].as_str().unwrap()).exists();
    b.shutdown();
    let s = s.unwrap();
    let (rows, _) = fx.envelope(&s, "blob", "incomplete");
    let outs: Vec<_> = of(&rows, "blob").into_iter().filter(|b| b["role"] == "stdout").collect();
    assert_eq!(outs.len(), 1);
    assert_eq!(outs[0]["bytes"], json!(4_194_304));
    // F332-1: the over-limit original is named missing, then collection stops there.
    let at = rows.iter().position(|r| r["kind"] == "missing").unwrap();
    assert_eq!(rows[at]["data"]["role"], json!("stdout"));
    assert_eq!(kinds(&rows[at + 1..]), ["incomplete"], "nothing is recorded after the limit");
    assert_eq!(of(&rows, "incomplete")[0]["reason"], json!("blob-limit"));
    // The child's own outcome and cleanup go on outside the sink.
    assert_eq!((k2.receipt["exit"].clone(), view.view, cleaned), (json!(0), "ready", true));
    assert_eq!((k1.stdout.len(), k2.stdout.len()), (4_194_304, 4_194_305), "originals are never truncated");
    assert!(s.total() <= diagnostics::SESSION_LIMIT);
}

/// The exact bytes Session writes for a footer (same construction).
fn footer_len(id: &str, seq: u64, reason: &str) -> usize {
    serde_json::to_vec(&json!({"schema": 1, "session": id, "seq": seq, "kind": "session-end", "data": {"complete": false, "reason": reason}})).unwrap().len() + 1
}
/// F332-1: the footer obeys the 64 KiB line bound like every other record.
#[test]
fn c21_footer_line_limit() {
    let Some(fx) = Fx::new("C21-footer") else { return };
    for (tag, want) in [("exact", 65_536usize), ("over", 65_537)] {
        let s = Session::open(&fx.data(), provenance(true)).unwrap();
        let id = s.id();
        let reason = format!("r{}", "x".repeat(want - footer_len(&id, 1, "r")));
        assert_eq!(footer_len(&id, 1, &reason), want);
        s.finish_with(reason);
        let (rows, _) = fx.envelope(&s, tag, "incomplete");
        let raw = fs::read(s.path_in(&fx.data()).join("records.jsonl")).unwrap();
        let lens: Vec<usize> = raw.split_inclusive(|&b| b == b'\n').map(<[u8]>::len).collect();
        assert!(lens.iter().all(|&n| n as u64 <= diagnostics::LINE_LIMIT), "{tag}: {lens:?}");
        if want == 65_536 {
            assert_eq!((kinds(&rows).last().unwrap().as_str(), lens[1]), ("session-end", 65_536), "the boundary footer is written");
        } else {
            assert_eq!(kinds(&rows), ["session", "incomplete"], "an over-limit footer is never written");
            assert_eq!(of(&rows, "incomplete")[0]["reason"], json!("footer-line-over-limit"));
        }
    }
}

#[test]
fn c23_session_limit() {
    let Some(fx) = Fx::new("C23") else { return };
    let s = Session::open(&fx.data(), provenance(true)).unwrap();
    let (b, rx, _, s) = bridge(&fx, Some(s));
    let mut views = Vec::new();
    for _ in 0..4 {
        drop_folder(&b, &fx.folder("success", json!({"stdout_bytes": 4_194_304})));
        run(&b, next(&rx), &probe(), None);
        views.push(b.snapshot().view);
        b.start_over();
    }
    b.shutdown();
    let s = s.unwrap();
    let (rows, _) = fx.envelope(&s, "total", "incomplete");
    assert!(views.iter().all(|v| *v == "ready"), "exhaustion never changes outcomes");
    assert!(s.total() <= diagnostics::SESSION_LIMIT, "{}", s.total());
    assert_eq!(of(&rows, "incomplete")[0]["reason"], json!("session-limit"));
    assert_eq!(kinds(&rows).last().unwrap(), "incomplete");
}

#[test]
fn c24_c25_sink_failures_stop_without_changing_outcomes() {
    let Some(fx) = Fx::new("C24-C25") else { return };
    let folder = fx.folder("success", json!({}));
    let (healthy, hv, _, hc) = flow_in(&fx, None, &folder, "healthy");
    let base = projection(&healthy, &hv, hc);
    let mut results = serde_json::Map::new();
    // Write 1 is the session record; 2-6 are ingress/drop/admit/launch/terminal; the
    // first blob write (report) is write 8 after the outcome record.
    for (tag, fault, expect) in [("create", Fault::Create(1), "incomplete"), ("short-blob", Fault::ShortWrite(8), "incomplete"),
        ("short-record", Fault::ShortWrite(4), "invalid"), ("full", Fault::NoSpace(5), "incomplete"), ("dead", Fault::DeadFrom(5), "incomplete")] {
        let s = Session::open_faulty(&fx.data(), provenance(true), crate::children::nonce(), Some(fault)).unwrap();
        let (k, v, s, c) = flow_in(&fx, Some(s), &folder, tag);
        let p = projection(&k, &v, c);
        assert_eq!(p, base, "{tag}: a sink failure changed the child's outcome, reaping or cleanup");
        let s = s.unwrap();
        let raw = fs::read(s.path_in(&fx.data()).join("records.jsonl")).unwrap();
        fx.evidence(&format!("records-{tag}.jsonl"), &raw);
        let (rows, _) = fx.envelope(&s, tag, expect);
        assert!(rows.iter().all(|r| r["kind"] != "session-end"), "{tag}: no complete footer after a failure");
        results.insert(tag.into(), json!({"projection": p, "last_kind": rows.last().map(|r| r["kind"].clone()), "torn": !raw.ends_with(b"\n")}));
    }
    fx.json("faults.json", &json!({"healthy": base, "faults": results}));
}
