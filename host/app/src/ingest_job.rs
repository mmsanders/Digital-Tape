//! One background `ingest` run for the length bar (APP-1 §2): all folders so far into an
//! app-owned DEST, `--length 3600`, with a fresh report nonce. The bar comes only from
//! the published manifest's exact `total_frames`; an overage only from INGEST_TOO_LONG.

use crate::jobdir::Job;
use crate::report::{self, Reading, Tool};
use std::io::Read;
use std::path::{Path, PathBuf};
use std::process::{Command, Stdio};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use serde::Serialize;

/// Ordinary invocation observations. This is not a shipping command or outcome selector.
#[derive(Debug, Default, Serialize)]
pub struct RunReceipt {
    pub argv: Vec<String>,
    pub cwd: PathBuf,
    pub nonce: String,
    pub version: String,
    pub report: PathBuf,
    pub dest: PathBuf,
    pub pid: Option<u32>,
    pub exit: Option<i32>,
    pub start_ns: u128,
    pub end_ns: u128,
    pub stdout: Vec<u8>,
    pub stderr: Vec<u8>,
    pub report_bytes: Option<Vec<u8>>,
    /// The process creation flags actually set on the Command.
    pub creation_flags: u32,
    /// SHA-256 of the environment the child inherits (the app's own, unchanged).
    pub env_sha256: String,
    /// Wall time just before the spawn call, distinct from the OS creation time below.
    pub spawn_call_ns: u128,
    /// The child's actual OS creation time, when the OS reports it.
    pub os_start_ns: Option<u128>,
    pub spawn_error: Option<String>,
    pub cancelled: bool,
    /// How the terminal status was obtained: "try_wait-terminal" or "wait".
    pub wait_kind: &'static str,
}

fn now() -> u128 {
    std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).expect("system time").as_nanos()
}

fn capture(receipt: &mut RunReceipt, report_path: &Path, out: std::thread::JoinHandle<Vec<u8>>, err: std::thread::JoinHandle<Vec<u8>>, exit: Option<i32>) {
    receipt.stdout = out.join().unwrap_or_default();
    receipt.stderr = err.join().unwrap_or_default();
    receipt.report_bytes = std::fs::read(report_path).ok();
    receipt.exit = exit;
    receipt.end_ns = now();
}

pub const CAPACITY_FRAMES: u64 = 3600 * 44100;

/// CREATE_NO_WINDOW. The app is a GUI-subsystem program, so a console child started
/// without it gets a console window of its own (F328-1). Nothing else changes.
pub const INGEST_CREATION_FLAGS: u32 = 0x0800_0000;

/// SHA-256 over the inherited environment, sorted by name: what the child receives.
pub fn env_sha256() -> String {
    use sha2::{Digest, Sha256};
    let mut vars: Vec<_> = std::env::vars_os().collect();
    vars.sort();
    let mut h = Sha256::new();
    for (k, v) in vars {
        for part in [k.as_encoded_bytes(), b"=", v.as_encoded_bytes(), b"\0"] { h.update(part); }
    }
    h.finalize().iter().map(|x| format!("{x:02x}")).collect()
}

#[derive(Debug)]
pub struct Outcome {
    /// None: killed by a signal, cancelled, or never started.
    pub exit: Option<i32>,
    pub stderr: String,
    pub reading: Reading,
    /// Exact frames of a published pair (exit 0 only).
    pub total_frames: Option<u64>,
    pub cancelled: bool,
}

fn published_total(dest: &Path) -> Option<u64> {
    let mut names: Vec<String> =
        std::fs::read_dir(dest).ok()?.flatten().map(|e| e.file_name().to_string_lossy().into_owned()).collect();
    names.sort();
    if names != ["audio.wav", "manifest.json"] {
        return None;
    }
    let m: serde_json::Value = serde_json::from_slice(&std::fs::read(dest.join("manifest.json")).ok()?).ok()?;
    m.get("total_frames")?.as_u64()
}

pub fn run(bin: &Path, version: &str, job: &Job, folders: &[PathBuf], cancel: Arc<AtomicBool>) -> Outcome {
    run_recorded(bin, version, job, folders, cancel, &mut RunReceipt::default())
}

/// Construct the actual production invocation without spawning it.
pub fn command(bin: &Path, version: &str, job: &Job, folders: &[PathBuf]) -> (Command, RunReceipt) {
    let nonce = crate::children::nonce();
    let report_path = job.control.join(format!("ingest-{nonce}.jsonl"));
    let dest = job.out.join("DEST");
    let mut cmd = Command::new(bin);
    cmd.arg("--report").arg(&report_path).arg("--report-nonce").arg(&nonce);
    cmd.arg("--out").arg(&dest).arg("--length").arg("3600").arg("--").args(folders);
    cmd.current_dir(&job.dir).stdin(Stdio::null()).stdout(Stdio::piped()).stderr(Stdio::piped());
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        cmd.creation_flags(INGEST_CREATION_FLAGS);
    }
    let receipt = RunReceipt { argv: std::iter::once(bin.to_string_lossy().into_owned()).chain(cmd.get_args().map(|a| a.to_string_lossy().into_owned())).collect(),
        cwd: job.dir.clone(), nonce: nonce.clone(), version: version.to_owned(), report: report_path.clone(), dest: dest.clone(), start_ns: now(),
        creation_flags: if cfg!(windows) { INGEST_CREATION_FLAGS } else { 0 }, env_sha256: env_sha256(), wait_kind: "none", ..Default::default() };
    (cmd, receipt)
}

pub fn run_recorded(bin: &Path, version: &str, job: &Job, folders: &[PathBuf], cancel: Arc<AtomicBool>, receipt: &mut RunReceipt) -> Outcome {
    run_hooked(bin, version, job, folders, cancel, receipt, &|_| {})
}

/// The production run, calling `spawned` once the child exists (before any wait).
pub fn run_hooked(bin: &Path, version: &str, job: &Job, folders: &[PathBuf], cancel: Arc<AtomicBool>, receipt: &mut RunReceipt, spawned: &dyn Fn(&RunReceipt)) -> Outcome {
    let (cmd, prepared) = command(bin, version, job, folders);
    *receipt = prepared;
    run_command(cmd, version, folders, cancel, receipt, spawned)
}

/// Spawn a Command built by `command` and observe it to its terminal. Controlled tests
/// may alter that Command (C02 clears its flags) and record what they set.
pub fn run_command(mut cmd: Command, version: &str, folders: &[PathBuf], cancel: Arc<AtomicBool>, receipt: &mut RunReceipt, spawned: &dyn Fn(&RunReceipt)) -> Outcome {
    let report_path = receipt.report.clone();
    receipt.spawn_call_ns = now();
    let mut child = match cmd.spawn() {
        Ok(c) => c,
        Err(e) => {
            receipt.end_ns = now();
            receipt.spawn_error = Some(format!("cannot start ingest: {e}"));
            receipt.stderr = format!("cannot start ingest: {e}").into_bytes();
            return Outcome {
                exit: None,
                stderr: format!("cannot start ingest: {e}"),
                reading: Reading::Unusable("not started"),
                total_frames: None,
                cancelled: false,
            }
        }
    };
    receipt.pid = Some(child.id());
    #[cfg(windows)]
    {
        use std::os::windows::io::AsRawHandle;
        receipt.os_start_ns = crate::win::process_start_ns(child.as_raw_handle());
    }
    spawned(receipt);
    let mut out = child.stdout.take().unwrap();
    let out_reader = std::thread::spawn(move || {
        let mut b = Vec::new();
        let _ = out.read_to_end(&mut b);
        b
    });
    let mut err = child.stderr.take().unwrap();
    let reader = std::thread::spawn(move || {
        let mut s = Vec::new();
        let _ = err.read_to_end(&mut s);
        s
    });
    let status = loop {
        if cancel.load(Ordering::SeqCst) {
            let _ = child.kill();
            let exit = child.wait().ok().and_then(|s| s.code());
            receipt.cancelled = true;
            receipt.wait_kind = "wait";
            capture(receipt, &report_path, out_reader, reader, exit);
            return Outcome {
                exit: None,
                stderr: String::from_utf8_lossy(&receipt.stderr).into_owned(),
                reading: Reading::Unusable("cancelled"),
                total_frames: None,
                cancelled: true,
            };
        }
        match child.try_wait() {
            Ok(Some(s)) => {
                receipt.wait_kind = "try_wait-terminal";
                break s;
            }
            Ok(None) => std::thread::sleep(std::time::Duration::from_millis(50)),
            Err(_) => {
                receipt.wait_kind = "wait";
                break child.wait().expect("wait");
            }
        }
    };
    let exit = status.code();
    capture(receipt, &report_path, out_reader, reader, exit);
    let stderr = String::from_utf8_lossy(&receipt.stderr).into_owned();
    let reading = match (exit, &receipt.report_bytes) {
        (Some(e), Some(b)) => report::read(b, Tool::Ingest, &receipt.nonce, version, e, folders.len()),
        _ => Reading::Unusable("no report"),
    };
    // APP-1A §1: ingest exit 0 also requires its published pair.
    let total_frames = if exit == Some(0) { published_total(&receipt.dest) } else { None };
    Outcome { exit, stderr, reading, total_frames, cancelled: false }
}
