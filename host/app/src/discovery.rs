//! The card line (APP-1 §2) from the bundled S2 `tapectl cards` (APP-1A §5). Discovery
//! is a hint only: it never enables Make, and the app itself never opens a device. A
//! hint needs exit 0, the current nonce/version report and complete stdout; anything
//! else is unknown and shows the generic sentence. The child's actual exit is kept.

use crate::jobdir::Job;
use crate::messages::GENERIC_INGEST;
use crate::report::{self, Reading, Tool};
use serde::Serialize;
use serde_json::Value;
use std::io::Read;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};

/// Nominal gap between one child's terminal and the next start.
pub const INTERVAL_MS: u64 = 2000;
/// One discovery child may run this long before the app stops it.
pub const TIMEOUT_MS: u64 = 10_000;
const LIMIT: u64 = (1 << 53) - 1;

/// Single-flight poll schedule in milliseconds since the poller started. The next run is
/// due INTERVAL_MS after the previous terminal; nothing starts while one is running,
/// while Making or once stopped, and missed ticks never catch up.
#[derive(Debug)]
pub struct Schedule {
    due: Option<u64>,
    busy: bool,
}

impl Schedule {
    pub fn new(start_ms: u64) -> Self {
        Self { due: Some(start_ms + INTERVAL_MS), busy: false }
    }
    /// Whether a run starts at `now_ms`.
    pub fn tick(&mut self, now_ms: u64, making: bool, stopped: bool) -> bool {
        if stopped || making || self.busy || !self.due.is_some_and(|d| now_ms >= d) {
            return false;
        }
        self.busy = true;
        self.due = None;
        true
    }
    /// The running child reached its terminal at `now_ms`.
    pub fn terminal(&mut self, now_ms: u64) {
        self.busy = false;
        self.due = Some(now_ms + INTERVAL_MS);
    }
}

/// What one complete, current enumeration offered.
#[derive(Debug, Clone, PartialEq, Serialize)]
pub struct Hint {
    pub sizes: Vec<u64>,
    pub unprobed: u64,
}

#[derive(Debug, Clone, PartialEq)]
pub struct Judged {
    /// None: unknown (failure, stale, partial or malformed).
    pub hint: Option<Hint>,
    /// The current report's terminal ID on a nonzero exit, for Show details only.
    pub id_specific: Option<String>,
}

/// The one sentence for the card line. A size is the OS capacity in decimal GB, rounded.
pub fn line(hint: Option<&Hint>) -> String {
    match hint.map(|h| h.sizes.as_slice()) {
        None => GENERIC_INGEST.into(),
        Some([]) => "Put a card in.".into(),
        Some([bytes]) => format!("Card ready ({} GB).", (bytes + 500_000_000) / 1_000_000_000),
        Some(_) => "Leave just one card in the computer.".into(),
    }
}

/// Judge one child: its actual exit, stdout and report bytes against the nonce and version
/// this app passed.
pub fn judge(exit: Option<i32>, stdout: &[u8], report_bytes: Option<&[u8]>, nonce: &str, version: &str) -> Judged {
    let reading = match (exit, report_bytes) {
        (Some(e), Some(b)) => Some(report::read(b, Tool::Cards, nonce, version, e, 0)),
        _ => None,
    };
    let id_specific = match &reading {
        Some(Reading::Usable { refusal: Some(r), .. }) => Some(r.id.clone()),
        _ => None,
    };
    if exit != Some(0) || !matches!(reading, Some(Reading::Usable { .. })) {
        return Judged { hint: None, id_specific };
    }
    Judged { hint: offered(stdout), id_specific: None }
}

fn integer(v: &Value) -> Option<u64> {
    v.as_u64().filter(|&n| n <= LIMIT)
}

fn keys(v: &Value) -> Option<Vec<&str>> {
    Some(v.as_object()?.keys().map(String::as_str).collect())
}

/// Complete stdout: card lines, then exactly one summary that counts them.
fn offered(stdout: &[u8]) -> Option<Hint> {
    let text = std::str::from_utf8(stdout).ok()?.strip_suffix('\n')?;
    let mut rows = Vec::new();
    for l in text.split('\n') {
        if !report::unique_keys(l) {
            return None;
        }
        rows.push(serde_json::from_str::<Value>(l).ok()?);
    }
    let summary = rows.pop()?;
    if keys(&summary)? != ["t", "offered", "unprobed"] || summary["t"] != "summary" {
        return None;
    }
    let (count, unprobed) = (integer(&summary["offered"])?, integer(&summary["unprobed"])?);
    let mut paths = Vec::new();
    let mut sizes = Vec::new();
    for r in &rows {
        if keys(r)? != ["t", "path", "bytes"] || r["t"] != "card" {
            return None;
        }
        let path = r["path"].as_str().filter(|p| !p.is_empty() && !p.contains('\0') && !paths.contains(p))?;
        paths.push(path);
        sizes.push(integer(&r["bytes"]).filter(|&n| n > 0)?);
    }
    (sizes.len() as u64 == count).then_some(Hint { sizes, unprobed })
}

/// Ordinary invocation observations; not an outcome selector.
#[derive(Debug, Default, Clone, Serialize)]
pub struct Request {
    pub exe: PathBuf,
    pub argv: Vec<String>,
    pub cwd: PathBuf,
    pub report: PathBuf,
    pub nonce: String,
    pub version: String,
}

/// The only discovery invocation: `tapectl cards --report FILE --report-nonce N`, from the
/// job directory, unelevated and without a shell or console window.
pub fn command(bin: &Path, version: &str, job: &Job) -> (Command, Request) {
    let nonce = crate::children::nonce();
    let report = job.control.join(format!("cards-{nonce}.jsonl"));
    let mut cmd = Command::new(bin);
    cmd.arg("cards").arg("--report").arg(&report).arg("--report-nonce").arg(&nonce);
    cmd.current_dir(&job.dir).stdin(Stdio::null()).stdout(Stdio::piped()).stderr(Stdio::piped());
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        cmd.creation_flags(0x0800_0000); // CREATE_NO_WINDOW: polled every 2 s from a GUI app
    }
    let argv = std::iter::once(bin.to_string_lossy().into_owned()).chain(cmd.get_args().map(|a| a.to_string_lossy().into_owned())).collect();
    (cmd, Request { exe: bin.to_owned(), argv, cwd: job.dir.clone(), report, nonce, version: version.to_owned() })
}

/// One child's terminal observation.
#[derive(Debug, Default, Clone, Serialize)]
pub struct Ran {
    pub pid: Option<u32>,
    /// None: stopped by the app, killed, or never started.
    pub exit: Option<i32>,
    pub stdout: Vec<u8>,
    pub stderr: Vec<u8>,
    pub report: Option<Vec<u8>>,
    pub timed_out: bool,
    pub cancelled: bool,
    pub spawn_error: Option<String>,
}

/// A started child as the supervisor sees it.
pub trait Child {
    /// Some(exit) once it has terminated.
    fn poll(&mut self) -> Option<Option<i32>>;
    /// Stop it and wait for its terminal.
    fn stop(&mut self) -> Option<i32>;
}

impl Child for std::process::Child {
    fn poll(&mut self) -> Option<Option<i32>> {
        match self.try_wait() {
            Ok(Some(s)) => Some(s.code()),
            Ok(None) => None,
            Err(_) => Some(self.wait().ok().and_then(|s| s.code())),
        }
    }
    fn stop(&mut self) -> Option<i32> {
        let _ = self.kill();
        self.wait().ok().and_then(|s| s.code())
    }
}

/// How a supervised child ended.
#[derive(Debug, PartialEq, Eq)]
pub enum End {
    Exited(Option<i32>),
    TimedOut,
    Cancelled,
}

/// Wait for `child` until it exits, `cancel` is set, or TIMEOUT_MS passes on `now_ms`.
/// On timeout `on_timeout` runs first (the caller invalidates its ticket), then the child
/// is stopped; either way this returns only after the child's terminal.
pub fn supervise(child: &mut dyn Child, cancel: &AtomicBool, now_ms: &mut dyn FnMut() -> u64, on_timeout: &mut dyn FnMut(), on_cancel: &mut dyn FnMut()) -> End {
    let start = now_ms();
    loop {
        if let Some(exit) = child.poll() {
            return End::Exited(exit);
        }
        if cancel.load(Ordering::SeqCst) {
            on_cancel();
            child.stop();
            return End::Cancelled;
        }
        if now_ms().saturating_sub(start) >= TIMEOUT_MS {
            on_timeout();
            on_cancel();
            child.stop();
            return End::TimedOut;
        }
        std::thread::sleep(std::time::Duration::from_millis(20));
    }
}

/// Run the real child for `request` under `supervise`, capturing stdout, stderr and the report.
pub fn run(mut cmd: Command, request: &Request, cancel: &AtomicBool, on_timeout: &mut dyn FnMut(), on_cancel: &mut dyn FnMut()) -> Ran {
    let mut child = match cmd.spawn() {
        Ok(c) => c,
        Err(e) => return Ran { spawn_error: Some(format!("cannot start tapectl: {e}")), ..Default::default() },
    };
    let pid = Some(child.id());
    let mut out = child.stdout.take().expect("piped stdout");
    let mut err = child.stderr.take().expect("piped stderr");
    let out = std::thread::spawn(move || { let mut b = Vec::new(); let _ = out.read_to_end(&mut b); b });
    let err = std::thread::spawn(move || { let mut b = Vec::new(); let _ = err.read_to_end(&mut b); b });
    let clock = std::time::Instant::now();
    let end = supervise(&mut child, cancel, &mut || clock.elapsed().as_millis() as u64, on_timeout, on_cancel);
    let stdout = out.join().unwrap_or_default();
    let stderr = err.join().unwrap_or_default();
    let report = std::fs::read(&request.report).ok();
    match end {
        End::Exited(exit) => Ran { pid, exit, stdout, stderr, report, ..Default::default() },
        End::TimedOut => Ran { pid, stdout, stderr, report, timed_out: true, ..Default::default() },
        End::Cancelled => Ran { pid, stdout, stderr, report, cancelled: true, ..Default::default() },
    }
}

/// Plain Show-details text for one judged run (never shown on the card line).
pub fn details(ran: &Ran, judged: &Judged) -> String {
    let mut s = match (&judged.hint, ran.exit) {
        (Some(h), _) => format!("Card check: {} offered, {} not checked.", h.sizes.len(), h.unprobed),
        (None, Some(e)) => format!("Card check failed: tapectl cards exited {e}{}.", judged.id_specific.as_deref().map(|id| format!(" ({id})")).unwrap_or_default()),
        (None, None) if ran.timed_out => "Card check failed: tapectl cards took too long and was stopped.".into(),
        (None, None) => ran.spawn_error.clone().unwrap_or_else(|| "Card check failed: tapectl cards did not finish.".into()),
    };
    if judged.hint.is_none() && !ran.stderr.is_empty() {
        s.push('\n');
        s.push_str(String::from_utf8_lossy(&ran.stderr).trim_end());
    }
    s
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn schedule_is_single_flight() {
        let mut s = Schedule::new(0);
        assert!(!s.tick(1999, false, false));
        assert!(s.tick(2000, false, false));
        assert!(!s.tick(4000, false, false), "busy");
        s.terminal(7000);
        assert!(!s.tick(8000, false, false));
        assert!(!s.tick(9000, true, false), "Making");
        assert!(!s.tick(9000, false, true), "stopped");
        assert!(s.tick(20000, false, false));
        assert!(!s.tick(20001, false, false), "no catch-up burst");
    }

    #[test]
    fn decimal_gb_lines() {
        let one = |b| line(Some(&Hint { sizes: vec![b], unprobed: 0 }));
        assert_eq!(one(63_600_000_000), "Card ready (64 GB).");
        assert_eq!(one(64_400_000_000), "Card ready (64 GB).");
        assert_eq!(one(1 << 37), "Card ready (137 GB).");
        assert_eq!(line(Some(&Hint { sizes: vec![], unprobed: 3 })), "Put a card in.");
        assert_eq!(line(Some(&Hint { sizes: vec![1, 2], unprobed: 0 })), "Leave just one card in the computer.");
        assert_eq!(line(None), GENERIC_INGEST);
    }

    #[test]
    fn stdout_must_be_complete() {
        assert_eq!(offered(b"{\"t\":\"summary\",\"offered\":0,\"unprobed\":2}\n"), Some(Hint { sizes: vec![], unprobed: 2 }));
        assert_eq!(offered(b"{\"t\":\"summary\",\"offered\":0,\"unprobed\":2}"), None);
        assert_eq!(offered(b"{\"t\":\"card\",\"path\":\"A\",\"bytes\":5,\"bytes\":6}\n{\"t\":\"summary\",\"offered\":1,\"unprobed\":0}\n"), None);
        assert_eq!(offered(b"{\"t\":\"card\",\"path\":\"A\",\"bytes\":5}\n{\"t\":\"summary\",\"offered\":2,\"unprobed\":0}\n"), None);
    }
}
