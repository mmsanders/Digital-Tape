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

pub const CAPACITY_FRAMES: u64 = 3600 * 44100;

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
    let nonce = crate::children::nonce();
    let report_path = job.control.join(format!("ingest-{nonce}.jsonl"));
    let dest = job.out.join("DEST");
    let mut cmd = Command::new(bin);
    cmd.arg("--report").arg(&report_path).arg("--report-nonce").arg(&nonce);
    cmd.arg("--out").arg(&dest).arg("--length").arg("3600").arg("--").args(folders);
    cmd.stdin(Stdio::null()).stdout(Stdio::null()).stderr(Stdio::piped());
    let mut child = match cmd.spawn() {
        Ok(c) => c,
        Err(e) => {
            return Outcome {
                exit: None,
                stderr: format!("cannot start ingest: {e}"),
                reading: Reading::Unusable("not started"),
                total_frames: None,
                cancelled: false,
            }
        }
    };
    let mut err = child.stderr.take().unwrap();
    let reader = std::thread::spawn(move || {
        let mut s = Vec::new();
        let _ = err.read_to_end(&mut s);
        String::from_utf8_lossy(&s).into_owned()
    });
    let status = loop {
        if cancel.load(Ordering::SeqCst) {
            let _ = child.kill();
            let _ = child.wait();
            return Outcome {
                exit: None,
                stderr: reader.join().unwrap_or_default(),
                reading: Reading::Unusable("cancelled"),
                total_frames: None,
                cancelled: true,
            };
        }
        match child.try_wait() {
            Ok(Some(s)) => break s,
            Ok(None) => std::thread::sleep(std::time::Duration::from_millis(50)),
            Err(_) => break child.wait().expect("wait"),
        }
    };
    let stderr = reader.join().unwrap_or_default();
    let exit = status.code();
    let reading = match (exit, std::fs::read(&report_path)) {
        (Some(e), Ok(b)) => report::read(&b, Tool::Ingest, &nonce, version, e, folders.len()),
        _ => Reading::Unusable("no report"),
    };
    // APP-1A §1: ingest exit 0 also requires its published pair.
    let total_frames = if exit == Some(0) { published_total(&dest) } else { None };
    Outcome { exit, stderr, reading, total_frames, cancelled: false }
}
