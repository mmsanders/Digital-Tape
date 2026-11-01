//! APP-1 §4 Make cartridge: the one elevated `tapectl make` child (APP-1A §3-§4). The app
//! passes the card path its recheck printed and its own ingested WAV, never anything the
//! person typed or chose, and it never opens a device: every outcome comes from the
//! child's exit and its report. Only this child is elevated (one UAC prompt per Make);
//! the app, `ingest` and `tapectl cards` stay `asInvoker`.

use crate::jobdir::Job;
use crate::messages::{self, AppEvent};
use crate::report::{self, Reading, Tool};
use std::path::{Path, PathBuf};

/// Fixed for the 60-minute cartridge (APP-1 §8 item 1).
pub const LENGTH_S: &str = "3600";

/// Recorded bar weights per make step (APP-1A §4): safety, provision, load, commit,
/// verify_a, verify_b. The bar is a running maximum and never implies success.
pub const WEIGHTS: [(&str, f64); 6] = [("safety", 1.0), ("provision", 4.0), ("load", 60.0), ("commit", 5.0), ("verify_a", 15.0), ("verify_b", 15.0)];

/// The one plain line naming the current step (APP-1 §2 Making).
pub fn step_line(step: &str) -> &'static str {
    match step {
        "safety" => "Checking the card…",
        "provision" => "Getting the card ready…",
        "load" => "Copying the music…",
        "commit" => "Finishing the copy…",
        _ => "Checking the cartridge…",
    }
}

/// The invocation, built once and passed whole to the launcher.
#[derive(Debug, Clone)]
pub struct Request {
    pub exe: PathBuf,
    pub args: Vec<String>,
    pub dir: PathBuf,
    pub report: PathBuf,
    pub nonce: String,
    pub version: String,
}

/// `tapectl make DEV --label L --length-s 3600 --wav WAV --erase DEV --report FILE --report-nonce N`.
pub fn request(exe: &Path, version: &str, job: &Job, dev: &str, label: &str, wav: &Path) -> Request {
    let nonce = crate::children::nonce();
    let report = job.control.join(format!("make-{nonce}.jsonl"));
    let args = ["make", dev, "--label", label, "--length-s", LENGTH_S, "--wav", &wav.to_string_lossy(), "--erase", dev,
        "--report", &report.to_string_lossy(), "--report-nonce", &nonce].iter().map(|s| s.to_string()).collect();
    Request { exe: exe.to_owned(), args, dir: job.dir.clone(), report, nonce, version: version.to_owned() }
}

/// One Windows command line from `args`, quoted so CommandLineToArgvW (tapectl's own
/// argv reader) returns exactly `args`.
pub fn command_line(args: &[String]) -> String {
    let mut out = String::new();
    for (i, a) in args.iter().enumerate() {
        if i > 0 { out.push(' '); }
        if !a.is_empty() && !a.contains([' ', '\t', '\n', '\u{b}', '"']) {
            out.push_str(a);
            continue;
        }
        out.push('"');
        let mut slashes = 0;
        for c in a.chars() {
            match c {
                '\\' => slashes += 1,
                '"' => { out.extend(std::iter::repeat('\\').take(slashes * 2 + 1)); out.push('"'); slashes = 0; }
                _ => { out.extend(std::iter::repeat('\\').take(slashes)); out.push(c); slashes = 0; }
            }
        }
        out.extend(std::iter::repeat('\\').take(slashes * 2));
        out.push('"');
    }
    out
}

/// What the launcher saw. `Declined` and `NotStarted` mean no make child ran.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Launched {
    /// The person answered No to the elevation prompt (ELEVATION_DECLINED).
    Declined,
    /// The child could not be started (SPAWN_FAILED); the OS's reason.
    NotStarted(String),
    /// The child ran to its own exit.
    Exited(i32),
}

/// The launcher the bridge calls: blocks until the child exits, calling `tick` about every
/// 200 ms while it runs. Production is `elevated`; component tests supply their own.
pub type Launch = dyn Fn(&Request, &mut dyn FnMut()) -> Launched + Send + Sync;

/// The production launcher: ShellExecuteExW "runas" on the pinned tapectl, hidden, owned
/// by the app's window so the prompt comes up in front of it.
#[cfg(windows)]
pub fn elevated(owner: isize) -> impl Fn(&Request, &mut dyn FnMut()) -> Launched + Send + Sync {
    move |req: &Request, tick: &mut dyn FnMut()| match crate::win::runas(&req.exe, &command_line(&req.args), &req.dir, owner) {
        crate::win::Elevated::Declined => Launched::Declined,
        crate::win::Elevated::Failed(why) => Launched::NotStarted(why),
        crate::win::Elevated::Started(process) => loop {
            if let Some(code) = process.wait_ms(200) { break Launched::Exited(code as i32); }
            tick();
        },
    }
}

/// Elsewhere there is no elevation route in this build (ADR-191: Windows 11 only).
#[cfg(not(windows))]
pub fn elevated(_owner: isize) -> impl Fn(&Request, &mut dyn FnMut()) -> Launched + Send + Sync {
    |_: &Request, _: &mut dyn FnMut()| Launched::NotStarted("this build can only make cartridges on Windows".into())
}

/// The bar fraction (0..=1) and the current step from the report's complete lines so far.
/// Unknown or malformed lines are skipped: progress never selects an outcome.
pub fn progress(bytes: &[u8]) -> Option<(f64, &'static str)> {
    let end = bytes.iter().rposition(|&b| b == b'\n')?;
    let text = std::str::from_utf8(&bytes[..end]).ok()?;
    let total: f64 = WEIGHTS.iter().map(|w| w.1).sum();
    let mut best: Option<(f64, &'static str)> = None;
    for line in text.split('\n') {
        let Ok(v) = serde_json::from_str::<serde_json::Value>(line) else { continue };
        if v["t"] != "progress" { continue; }
        let (Some(step), Some(done), Some(of)) = (v["step"].as_str(), v["done"].as_u64(), v["total"].as_u64()) else { continue };
        let Some(i) = WEIGHTS.iter().position(|w| w.0 == step) else { continue };
        let before: f64 = WEIGHTS[..i].iter().map(|w| w.1).sum();
        let part = if of > 0 { (done.min(of) as f64) / (of as f64) } else { 0.0 };
        let f = (before + WEIGHTS[i].1 * part) / total;
        if best.map_or(true, |(b, _)| f >= b) { best = Some((f, WEIGHTS[i].0)); }
    }
    best
}

/// A finished Make: `message` None is success (exit 0); otherwise the APP-1 §6 sentence.
/// `details` is what Show details offers.
#[derive(Debug, Clone, PartialEq)]
pub struct Outcome {
    pub message: Option<String>,
    pub details: String,
}

/// Judge the launcher's result with the report the child left (APP-1A §1/§3).
pub fn judge(launched: &Launched, report_bytes: Option<&[u8]>, nonce: &str, version: &str) -> Outcome {
    match launched {
        Launched::Declined => Outcome { message: Some(messages::app_event(AppEvent::ElevationDeclined)),
            details: "The elevation prompt was declined; tapectl make was not started.".into() },
        Launched::NotStarted(why) => Outcome { message: Some(messages::app_event(AppEvent::SpawnFailed)),
            details: format!("tapectl make could not be started: {why}") },
        Launched::Exited(code) => {
            let reading = match report_bytes {
                Some(b) => report::read(b, Tool::Make, nonce, version, *code, 0),
                None => Reading::Unusable("no report"),
            };
            let mut details = match &reading {
                Reading::Usable { stderr, .. } if !stderr.is_empty() => stderr.join("\n"),
                _ => report_bytes.map(|b| String::from_utf8_lossy(b).into_owned()).unwrap_or_default(),
            };
            if let Reading::Unusable(why) = &reading { details = format!("tapectl make exited {code}; report unusable ({why})\n{details}"); }
            Outcome { message: messages::make(*code, &reading), details }
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn command_line_round_trips_windows_quoting() {
        let args: Vec<String> = ["make", r"\\host\DEV3", "--label", "Road \"Trip\" ✓", "--wav", r"C:\Users\A B\x\audio.wav", "", r"ends\"]
            .iter().map(|s| s.to_string()).collect();
        let line = command_line(&args);
        assert_eq!(line, r#"make \\host\DEV3 --label "Road \"Trip\" ✓" --wav "C:\Users\A B\x\audio.wav" "" ends\"#);
    }

    #[test]
    fn progress_is_weighted_and_monotonic() {
        let r = b"{\"t\":\"start\"}\n{\"t\":\"progress\",\"step\":\"safety\",\"done\":1,\"total\":1}\n{\"t\":\"progress\",\"step\":\"load\",\"done\":50,\"total\":100}\n{\"t\":\"progress\",\"step\":\"load\",\"done\":60";
        let (f, step) = progress(r).unwrap();
        assert_eq!(step, "load");
        assert!((f - (1.0 + 4.0 + 30.0) / 100.0).abs() < 1e-9, "{f}");
        assert_eq!(progress(b"{\"t\":\"start\"}\n"), None);
    }

    #[test]
    fn app_origin_outcomes() {
        let d = judge(&Launched::Declined, None, "", "");
        assert_eq!(d.message.unwrap(), "The computer said no, so the card wasn't changed. Press Make cartridge to try again.");
        let s = judge(&Launched::NotStarted("x".into()), None, "", "");
        assert_eq!(s.message.unwrap(), messages::GENERIC_INGEST);
        let n = judge(&Launched::Exited(1), None, "", "");
        assert_eq!(n.message.unwrap(), "The cartridge wasn't finished. Start over and try again.");
        assert_eq!(judge(&Launched::Exited(0), None, "", "").message, None);
    }
}
