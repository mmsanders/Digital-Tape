//! PM593 APP-1A §8 opt-in first-party receipts, schema 1 (Verification332). Default OFF:
//! only `digital-tape.exe --diagnostic-receipts` opens a Session, and without one nothing
//! here runs. A Session is one exclusive fresh directory `control\diag-<session>` in the
//! app's private data folder, created and written only through held, non-reparse
//! directory handles (handle-relative NtCreateFile), so a replaced path is never written
//! through. It records the same production ingress/admission/worker/child/cleanup path
//! the app runs anyway; it never changes an outcome, retries a child or delays cleanup.
//! A write failure or limit stops collection with an `incomplete` record when one still
//! fits. These are first-party observations, not whole-machine absence proof.

use crate::ingest_job::RunReceipt;
use crate::report::Reading;
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::collections::{BTreeMap, BTreeSet};
use std::ffi::OsString;
use std::fs::File;
use std::io::{self, Read, Write};
use std::path::Path;
use std::sync::Mutex;

pub const OPT_IN: &str = "--diagnostic-receipts";
pub const MARKER: &str = ".digital-tape-diagnostic-session";
pub const SESSION_LIMIT: u64 = 16_777_216;
pub const LINE_LIMIT: u64 = 65_536;
pub const BLOB_LIMIT: u64 = 4_194_304;
/// Kept back from every ordinary record so one `incomplete` or footer still fits.
const RESERVE: u64 = 1024;

/// Exactly `[app, "--diagnostic-receipts"]`; anything else is OFF.
pub fn opted_in(args: &[OsString]) -> bool {
    args.len() == 2 && args[1] == OPT_IN
}

/// Ingress boundaries that really exist. Tests name themselves; nothing is relabelled.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Route {
    NativeEvent,
    TauriCommand,
    ControlledTest,
}
impl Route {
    fn name(self) -> &'static str {
        match self {
            Route::NativeEvent => "native-event",
            Route::TauriCommand => "tauri-command",
            Route::ControlledTest => "controlled-test",
        }
    }
}

/// Identity facts read once at open. Unknown stays null and makes the receipt incomplete.
#[derive(Debug, Clone)]
pub struct Provenance {
    pub app_path: String,
    pub app_sha256: String,
    pub source_commit: Option<String>,
    pub os_build: Option<String>,
    pub app_os_start_ns: Option<u128>,
}

fn hex(b: &[u8]) -> String {
    b.iter().map(|x| format!("{x:02x}")).collect()
}
fn sha(b: &[u8]) -> String {
    hex(&Sha256::digest(b))
}
fn sha_file(p: &Path) -> io::Result<(String, u64)> {
    let mut f = File::open(p)?;
    let (mut h, mut n, mut buf) = (Sha256::new(), 0u64, vec![0u8; 1 << 16]);
    loop {
        let k = f.read(&mut buf)?;
        if k == 0 { break; }
        h.update(&buf[..k]);
        n += k as u64;
    }
    Ok((hex(&h.finalize()), n))
}
fn is_hex(s: &str, n: usize) -> bool {
    s.len() == n && s.bytes().all(|c| c.is_ascii_digit() || (b'a'..=b'f').contains(&c))
}

impl Provenance {
    /// This executable, and its source only from a BUILD.json beside it that binds both
    /// this build's child pins and this exact executable (`bound_source`).
    pub fn of_running_app() -> Provenance {
        let exe = std::env::current_exe().ok();
        let app_sha256 = exe.as_deref().and_then(|p| sha_file(p).ok()).map(|x| x.0).unwrap_or_default();
        let source_commit = exe.as_deref().and_then(Path::parent).and_then(|d| std::fs::read(d.join("BUILD.json")).ok())
            .and_then(|b| bound_source(&b, &app_sha256));
        Provenance { app_path: exe.map(|p| p.to_string_lossy().into_owned()).unwrap_or_default(), app_sha256, source_commit, os_build: os_build(), app_os_start_ns: own_start_ns() }
    }

    /// Anything unknown: no complete receipt can be written under it.
    fn unknown(&self) -> bool {
        self.app_path.is_empty() || !is_hex(&self.app_sha256, 64) || self.source_commit.is_none() || self.os_build.is_none() || self.app_os_start_ns.is_none()
    }
}

/// BUILD.json's source head, only when its child pins equal the ones compiled into this
/// build AND its single digital-tape.exe entry is the measured running executable. The
/// pins alone are shared by many app heads, so a stale sidecar must not name the source.
pub fn bound_source(build: &[u8], app_sha256: &str) -> Option<String> {
    let m: Value = serde_json::from_slice(build).ok()?;
    let pins = crate::children::INGEST.sha256.is_some() && m["child_pin"].as_str() == crate::children::INGEST.sha256
        && m["tapectl_pin"].as_str() == crate::children::TAPECTL.sha256;
    let apps: Vec<&Value> = m["files"].as_array()?.iter().filter(|f| f["name"] == "digital-tape.exe").collect();
    let app = is_hex(app_sha256, 64) && apps.len() == 1 && apps[0]["sha256"].as_str() == Some(app_sha256);
    m["source_head"].as_str().filter(|s| pins && app && is_hex(s, 40)).map(str::to_owned)
}
#[cfg(windows)]
fn os_build() -> Option<String> { crate::win::os_build() }
#[cfg(not(windows))]
fn os_build() -> Option<String> { None }
#[cfg(windows)]
fn own_start_ns() -> Option<u128> { crate::win::own_start_ns() }
#[cfg(not(windows))]
fn own_start_ns() -> Option<u128> { None }

/// Controlled sink faults at the production write boundary (tests only).
#[cfg(test)]
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Fault {
    /// The nth blob leaf create fails.
    Create(u32),
    /// The nth write stores only half its bytes.
    ShortWrite(u32),
    /// The nth write reports a full volume.
    NoSpace(u32),
    /// Every write from the nth on fails: even `incomplete` cannot be stored.
    DeadFrom(u32),
}

struct Dirs {
    // Held for the session's life: no rename or delete of any of them while open.
    _root: File,
    _control: File,
    _session: File,
    blobs: File,
}

#[derive(Default)]
struct Ledger {
    ingress: BTreeSet<String>,
    drops: BTreeSet<String>,
    scheduled: BTreeSet<String>,
    jobs: BTreeSet<String>,
    skipped: BTreeSet<String>,
    outcomes: BTreeSet<String>,
    cleaned: BTreeSet<String>,
    /// work -> (cancelled, exit) at terminal
    terminal: BTreeMap<String, (bool, Option<i32>)>,
    roles: BTreeMap<String, BTreeSet<&'static str>>,
    launched: BTreeSet<String>,
    flaws: Vec<&'static str>,
}

impl Ledger {
    /// Each reason once, in first-seen order, so the footer's reason stays short.
    fn flaw(&mut self, f: &'static str) {
        if !self.flaws.contains(&f) { self.flaws.push(f); }
    }
}

struct Inner {
    id: String,
    dirs: Dirs,
    records: File,
    seq: u64,
    total: u64,
    next_drop: u64,
    stopped: bool,
    ledger: Ledger,
    #[cfg(test)]
    fault: Option<Fault>,
    #[cfg(test)]
    creates: u32,
    #[cfg(test)]
    writes: u32,
}

pub struct Session {
    inner: Mutex<Inner>,
    pub dir_name: String,
}

#[cfg(test)]
thread_local! {
    /// Sink operations on this thread: OFF runs must leave it at zero (C09).
    pub static SINK_CALLS: std::cell::Cell<u64> = const { std::cell::Cell::new(0) };
}
#[cfg(test)]
fn count_sink() { SINK_CALLS.with(|c| c.set(c.get() + 1)); }

fn plain_root(data: &Path) -> io::Result<File> {
    #[cfg(windows)]
    {
        use std::os::windows::fs::OpenOptionsExt;
        let f = std::fs::OpenOptions::new().access_mode(crate::win::DIR_OPEN_ACCESS).share_mode(crate::win::SHARE_NO_DELETE)
            .custom_flags(crate::win::OPEN_DIRECTORY_ITSELF).open(data)?;
        crate::win::plain(&f, true)?;
        Ok(f)
    }
    #[cfg(not(windows))]
    {
        let _ = data;
        Err(io::Error::other("diagnostic receipts are Windows-only"))
    }
}

impl Session {
    /// Create `control\diag-<session>` and its marker, then the `session` record.
    pub fn open(data: &Path, provenance: Provenance) -> io::Result<Session> {
        Self::open_with(data, provenance, crate::children::nonce(), None)
    }

    #[cfg(test)]
    pub fn open_faulty(data: &Path, provenance: Provenance, id: String, fault: Option<Fault>) -> io::Result<Session> {
        Self::open_with(data, provenance, id, fault)
    }

    #[allow(unused_variables)]
    fn open_with(data: &Path, provenance: Provenance, id: String, fault: Option<FaultArg>) -> io::Result<Session> {
        #[cfg(test)]
        count_sink();
        #[cfg(not(windows))]
        return Err(io::Error::other("diagnostic receipts are Windows-only"));
        #[cfg(windows)]
        {
            use crate::win;
            let root = plain_root(data)?;
            let control = win::open_or_create_dir_at(&root, "control")?;
            let dir_name = format!("diag-{id}");
            let session = win::create_dir_at(&control, &dir_name)?;
            let mut marker = win::create_file_at(&session, MARKER)?;
            let marker_bytes = json!({"schema": 1, "session": id}).to_string().into_bytes();
            marker.write_all(&marker_bytes)?;
            let records = win::create_file_at(&session, "records.jsonl")?;
            let blobs = win::create_dir_at(&session, "blobs")?;
            let inner = Inner { id, dirs: Dirs { _root: root, _control: control, _session: session, blobs }, records, seq: 0,
                total: marker_bytes.len() as u64, next_drop: 0, stopped: false, ledger: Ledger::default(),
                #[cfg(test)] fault, #[cfg(test)] creates: 0, #[cfg(test)] writes: 0 };
            let s = Session { inner: Mutex::new(inner), dir_name };
            {
                let mut g = s.inner.lock().unwrap();
                if provenance.unknown() { g.ledger.flaw("unknown-provenance"); }
                let pins = json!({"DT_INGEST_SHA256": crate::children::INGEST.sha256, "DT_INGEST_VERSION": crate::children::INGEST.version,
                    "DT_TAPECTL_SHA256": crate::children::TAPECTL.sha256, "DT_TAPECTL_VERSION": crate::children::TAPECTL.version});
                g.record("session", json!({"app_path": provenance.app_path, "app_sha256": provenance.app_sha256, "source_commit": provenance.source_commit,
                    "os": std::env::consts::OS, "os_build": provenance.os_build, "arch": std::env::consts::ARCH, "app_pid": std::process::id(),
                    "app_os_start_ns": provenance.app_os_start_ns.map(|n| n as u64), "pins": pins, "control_scope": "app-private/control", "opt_in": OPT_IN}));
                if g.stopped { return Err(io::Error::other("cannot write the session record")); }
            }
            Ok(s)
        }
    }

    pub fn id(&self) -> String {
        self.inner.lock().unwrap().id.clone()
    }

    pub fn ingress(&self, route: Route, paths: &[String], generation: u64) -> String {
        let mut g = self.inner.lock().unwrap();
        let id = format!("drop-{}", g.next_drop);
        g.next_drop += 1;
        if g.record("ingress", json!({"drop_id": id, "route": route.name(), "paths": paths, "generation": generation})) {
            g.ledger.ingress.insert(id.clone());
        }
        id
    }

    pub fn drop_decision(&self, drop_id: &str, decision: &str, reason: Option<&str>, next: &str, generation: u64, work_id: Option<&str>) {
        let mut g = self.inner.lock().unwrap();
        if g.record("drop", json!({"drop_id": drop_id, "decision": decision, "reason": reason, "next": next, "generation": generation, "work_id": work_id})) {
            g.ledger.drops.insert(drop_id.into());
            if let Some(w) = work_id { g.ledger.scheduled.insert(w.into()); }
        }
    }

    pub fn reset(&self, old_generation: u64, new_generation: u64) {
        self.inner.lock().unwrap().record("reset", json!({"old_generation": old_generation, "new_generation": new_generation}));
    }

    pub fn cancel_request(&self, work_id: &str, generation: u64) {
        self.inner.lock().unwrap().record("cancel-request", json!({"work_id": work_id, "generation": generation}));
    }

    pub fn work_skipped(&self, work_id: &str, generation: u64) {
        let mut g = self.inner.lock().unwrap();
        if g.record("work-skipped", json!({"work_id": work_id, "generation": generation, "reason": "cancelled-before-admission"})) {
            g.ledger.skipped.insert(work_id.into());
        }
    }

    pub fn job_admit(&self, work_id: &str, generation: u64, drop_id: &str, job_dir: &Path) {
        let mut g = self.inner.lock().unwrap();
        if g.record("job-admit", json!({"work_id": work_id, "generation": generation, "drop_id": drop_id, "job_dir": job_dir.to_string_lossy()})) {
            g.ledger.jobs.insert(work_id.into());
        }
    }

    /// Right after spawn, before any wait: the actual invocation.
    pub fn child_launch(&self, work_id: &str, generation: u64, r: &RunReceipt) {
        let exe = r.argv.first().cloned().unwrap_or_default();
        let exe_sha256 = sha_file(Path::new(&exe)).ok().map(|x| x.0);
        let mut g = self.inner.lock().unwrap();
        let Some(exe_sha256) = exe_sha256 else { g.stop("exe-hash-unavailable"); return };
        if r.os_start_ns.is_none() { g.ledger.flaw("unknown-child-creation-time"); }
        if g.record("child-launch", json!({"work_id": work_id, "generation": generation, "pid": r.pid, "os_start_ns": r.os_start_ns.map(|n| n as u64),
            "spawn_call_ns": r.spawn_call_ns as u64, "exe": exe, "exe_sha256": exe_sha256, "version": r.version, "argv": r.argv,
            "cwd": r.cwd.to_string_lossy(), "report_path": r.report.to_string_lossy(), "dest": r.dest.to_string_lossy(), "nonce": r.nonce,
            "creation_flags": r.creation_flags, "env_sha256": r.env_sha256})) {
            g.ledger.launched.insert(work_id.into());
        }
    }

    pub fn child_not_launched(&self, work_id: &str, generation: u64, reason: &str) {
        let mut g = self.inner.lock().unwrap();
        if g.record("child-not-launched", json!({"work_id": work_id, "generation": generation, "reason": reason})) {
            g.ledger.launched.insert(work_id.into());
        }
    }

    /// The actual terminal, right after the wait.
    pub fn child_terminal(&self, work_id: &str, generation: u64, r: &RunReceipt) {
        let mut g = self.inner.lock().unwrap();
        if g.record("child-terminal", json!({"work_id": work_id, "generation": generation, "pid": r.pid, "exit": r.exit,
            "cancelled": r.cancelled, "wait_kind": r.wait_kind, "end_ns": r.end_ns as u64})) {
            g.ledger.terminal.insert(work_id.into(), (r.cancelled, r.exit));
        }
    }

    /// After the actual wait and before the job is deleted: the original report/stdout/
    /// stderr bytes and, for exit 0, the manifest bytes plus a streamed audio hash (the
    /// audio itself is never copied).
    pub fn capture(&self, work_id: &str, generation: u64, r: &RunReceipt, reading: &Reading) {
        let mut g = self.inner.lock().unwrap();
        if !g.ledger.terminal.contains_key(work_id) { return; }
        let pid = r.pid;
        match &r.report_bytes {
            Some(b) => {
                g.blob(work_id, generation, pid, "report", b);
                if !r.cancelled && matches!(reading, Reading::Unusable(_)) { g.ledger.flaw("invalid-original-report"); }
                // A killed child's report is kept as it was left: never a finished chain.
                if r.cancelled { g.ledger.flaw("cancelled-child-report"); }
            }
            // Killed before it created a report: the absence is recorded, never complete.
            None if r.cancelled => {
                g.ledger.flaw("cancelled-before-report");
                g.missing(work_id, generation, "report", "cancelled before the child created its report");
            }
            None => g.missing(work_id, generation, "report", "no report file after the child's wait"),
        }
        g.blob(work_id, generation, pid, "stdout", &r.stdout);
        g.blob(work_id, generation, pid, "stderr", &r.stderr);
        if r.exit == Some(0) && !r.cancelled {
            match std::fs::read(r.dest.join("manifest.json")) {
                Ok(b) => {
                    g.blob(work_id, generation, pid, "manifest", &b);
                    let frames = serde_json::from_slice::<Value>(&b).ok().and_then(|m| m["total_frames"].as_u64());
                    match (sha_file(&r.dest.join("audio.wav")), frames) {
                        (Ok((h, n)), Some(f)) => {
                            if g.record("audio", json!({"work_id": work_id, "generation": generation, "pid": pid, "sha256": h, "bytes": n, "total_frames": f})) {
                                g.ledger.roles.entry(work_id.into()).or_default().insert("audio");
                            }
                        }
                        (Err(e), _) => g.missing(work_id, generation, "audio", &format!("cannot hash audio.wav: {e}")),
                        (_, None) => g.missing(work_id, generation, "audio", "manifest has no total_frames"),
                    }
                }
                Err(e) => g.missing(work_id, generation, "manifest", &format!("cannot read manifest.json: {e}")),
            }
        }
    }

    pub fn outcome(&self, work_id: &str, generation: u64, disposition: &str, state_ref: &str) {
        let mut g = self.inner.lock().unwrap();
        if g.record("outcome", json!({"work_id": work_id, "generation": generation, "disposition": disposition, "state_ref": state_ref})) {
            g.ledger.outcomes.insert(work_id.into());
        }
    }

    pub fn cleanup(&self, work_id: &str, generation: u64, job_dir: &Path, removed: bool) {
        let mut g = self.inner.lock().unwrap();
        let (result, error) = if removed { ("removed", None) } else if job_dir.exists() { ("failed", Some("remove_dir_all failed")) } else { ("missing", None) };
        if g.record("cleanup", json!({"work_id": work_id, "generation": generation, "job_dir": job_dir.to_string_lossy(), "result": result, "error": error})) {
            g.ledger.cleaned.insert(work_id.into());
        }
    }

    /// Stop collecting because the caller could not observe a required fact.
    pub fn incomplete(&self, reason: &str) {
        self.inner.lock().unwrap().stop(reason);
    }

    /// The footer, after the worker has joined: complete only if every fact is present.
    pub fn finish(&self) {
        let mut g = self.inner.lock().unwrap();
        if g.stopped { return; }
        let reason = g.gap();
        g.footer(json!({"complete": reason.is_none(), "reason": reason}));
    }

    /// The production footer path with a chosen reason, for the line-bound boundary.
    #[cfg(test)]
    pub fn finish_with(&self, reason: String) {
        let mut g = self.inner.lock().unwrap();
        if g.stopped { return; }
        g.footer(json!({"complete": false, "reason": reason}));
    }

    /// Exact test reads of the session's files, by leaf, through held handles' names.
    #[cfg(test)]
    pub fn path_in(&self, data: &Path) -> std::path::PathBuf {
        data.join("control").join(&self.dir_name)
    }
    #[cfg(test)]
    pub fn total(&self) -> u64 {
        self.inner.lock().unwrap().total
    }
}

#[cfg(test)]
type FaultArg = Fault;
#[cfg(not(test))]
type FaultArg = ();

impl Inner {
    /// The reason the receipt is not complete, if any.
    fn gap(&self) -> Option<String> {
        let l = &self.ledger;
        if !l.flaws.is_empty() { return Some(l.flaws.join(";")); }
        if l.ingress != l.drops { return Some("ingress-without-decision".into()); }
        if l.jobs != l.outcomes || l.jobs != l.cleaned { return Some("work-without-outcome-or-cleanup".into()); }
        let accounted: BTreeSet<String> = l.jobs.union(&l.skipped).cloned().collect();
        if l.scheduled != accounted { return Some("scheduled-work-unaccounted".into()); }
        for (w, (cancelled, exit)) in &l.terminal {
            let roles = l.roles.get(w).cloned().unwrap_or_default();
            if *cancelled {
                if !roles.contains("report") { return Some("cancelled-before-report".into()); }
                continue;
            }
            let mut need = vec!["report", "stdout", "stderr"];
            if *exit == Some(0) { need.extend(["manifest", "audio"]); }
            if !need.iter().all(|r| roles.contains(r)) { return Some("missing-capture".into()); }
        }
        None
    }

    #[cfg(test)]
    fn inject_create(&mut self) -> io::Result<()> {
        count_sink();
        self.creates += 1;
        if self.fault == Some(Fault::Create(self.creates)) { return Err(io::Error::other("injected create failure")); }
        Ok(())
    }
    #[cfg(not(test))]
    fn inject_create(&mut self) -> io::Result<()> { Ok(()) }

    /// Every byte the session stores goes through here.
    fn put(&mut self, which: Option<&mut File>, bytes: &[u8]) -> io::Result<()> {
        #[cfg(test)]
        {
            count_sink();
            self.writes += 1;
            match self.fault {
                Some(Fault::ShortWrite(n)) if n == self.writes => {
                    let half = &bytes[..bytes.len() / 2];
                    match which { Some(f) => f.write_all(half)?, None => self.records.write_all(half)? }
                    self.total += half.len() as u64;
                    return Err(io::Error::new(io::ErrorKind::WriteZero, "injected short write"));
                }
                Some(Fault::NoSpace(n)) if n == self.writes => return Err(io::Error::other("injected full volume")),
                Some(Fault::DeadFrom(n)) if self.writes >= n => return Err(io::Error::other("injected dead volume")),
                _ => {}
            }
        }
        match which { Some(f) => f.write_all(bytes)?, None => self.records.write_all(bytes)? }
        self.total += bytes.len() as u64;
        Ok(())
    }

    fn line(&self, kind: &str, data: Value) -> Vec<u8> {
        let mut b = serde_json::to_vec(&json!({"schema": 1, "session": self.id, "seq": self.seq, "kind": kind, "data": data})).expect("record");
        b.push(b'\n');
        b
    }

    /// One ordinary record, inside the reserve. False once collection has stopped.
    fn record(&mut self, kind: &str, data: Value) -> bool {
        if self.stopped { return false; }
        let b = self.line(kind, data);
        if b.len() as u64 > LINE_LIMIT { self.stop("record-line-over-limit"); return false; }
        if self.total + b.len() as u64 > SESSION_LIMIT - RESERVE { self.stop("session-limit"); return false; }
        if let Err(e) = self.put(None, &b) { self.fail(e); return false; }
        self.seq += 1;
        true
    }

    /// A fact that could not be kept: the receipt can no longer be complete.
    fn missing(&mut self, work_id: &str, generation: u64, role: &str, reason: &str) {
        self.ledger.flaw("missing-capture");
        self.record("missing", json!({"work_id": work_id, "generation": generation, "role": role, "reason": reason}));
    }

    /// One original, byte-exact, in its own fresh leaf named by the record that cites it.
    /// An original over the blob limit is named missing and collection stops (APP-1A §8):
    /// nothing after it is recorded, while the child's own outcome and cleanup go on.
    fn blob(&mut self, work_id: &str, generation: u64, pid: Option<u32>, role: &'static str, bytes: &[u8]) {
        if self.stopped { return; }
        if bytes.len() as u64 > BLOB_LIMIT {
            self.missing(work_id, generation, role, &format!("original is {} bytes, over the {BLOB_LIMIT}-byte blob limit", bytes.len()));
            return self.stop("blob-limit");
        }
        let leaf = format!("{:08}-{role}.bin", self.seq);
        let cite = self.line("blob", json!({"work_id": work_id, "generation": generation, "pid": pid, "role": role, "leaf": format!("blobs/{leaf}"),
            "bytes": bytes.len(), "sha256": sha(bytes)}));
        if self.total + bytes.len() as u64 + cite.len() as u64 > SESSION_LIMIT - RESERVE { return self.stop("session-limit"); }
        let created = self.inject_create().and_then(|_| self.create_blob(&leaf));
        let mut file = match created { Ok(f) => f, Err(e) => return self.fail(e) };
        if let Err(e) = self.put(Some(&mut file), bytes) { return self.fail(e); }
        drop(file);
        if self.record("blob", serde_json::from_slice::<Value>(&cite).expect("own record")["data"].take()) {
            self.ledger.roles.entry(work_id.into()).or_default().insert(role);
        }
    }

    #[cfg(windows)]
    fn create_blob(&mut self, leaf: &str) -> io::Result<File> { crate::win::create_file_at(&self.dirs.blobs, leaf) }
    #[cfg(not(windows))]
    fn create_blob(&mut self, _leaf: &str) -> io::Result<File> { Err(io::Error::other("Windows-only")) }

    fn fail(&mut self, e: io::Error) {
        let reason = format!("sink-failure: {e}");
        self.stop(&reason);
    }

    /// End collection: one `incomplete` record from the reserve if it still fits.
    fn stop(&mut self, reason: &str) {
        if self.stopped { return; }
        self.stopped = true;
        let b = self.line("incomplete", json!({"reason": reason}));
        if b.len() as u64 <= LINE_LIMIT && self.total + b.len() as u64 <= SESSION_LIMIT && self.put(None, &b).is_ok() {
            self.seq += 1;
        }
    }

    /// The footer obeys the same per-line bound as every record; one that would not fit
    /// ends the session as `incomplete` instead.
    fn footer(&mut self, data: Value) {
        let b = self.line("session-end", data);
        if b.len() as u64 > LINE_LIMIT { return self.stop("footer-line-over-limit"); }
        self.stopped = true;
        if self.total + b.len() as u64 <= SESSION_LIMIT && self.put(None, &b).is_ok() { self.seq += 1; }
    }
}
