//! APP-1A §1 diagnostic report: `--report FILE --report-nonce N`, opt-in. Without
//! both flags nothing here runs and no file is created. The report is never ingest
//! output: it does not sit in DEST or its stage and says nothing about success.
//!
//! Lines are compact JSON objects with keys in APP-1A's order, one write per line, no
//! flush. The first failed or short write stops all report writing, prints one stderr
//! warning, and changes nothing else: exits and outputs are the command's own.

use crate::common::*;
use std::ffi::{OsStr, OsString};
use std::fs::File;
use std::io::Write;
use std::path::Path;
use std::sync::Mutex;

/// APP-1A §4 ingest steps, in order.
pub const STEPS: [&str; 5] = ["list", "decode", "convert", "write", "publish"];

struct Report {
    file: Option<File>,
    path: String,
    /// The step index, last 1/64 bucket and last `done` emitted for it.
    step: Option<(usize, u64, u64)>,
}

static REPORT: Mutex<Option<Report>> = Mutex::new(None);

/// The report flags, removed from argv before ordinary parsing. Report flags after a
/// bare `--` are folder paths, exactly as before.
pub struct Flags {
    pub file: OsString,
    pub nonce: String,
}

/// Split the report flags from argv. `Ok(None)`: neither flag is present and argv is
/// returned untouched. `Err`: an invalid pairing, repeat, missing value or nonce.
pub fn take_flags(argv: Vec<OsString>) -> Result<(Vec<OsString>, Option<Flags>), String> {
    let mut rest = Vec::with_capacity(argv.len());
    let (mut file, mut nonce) = (None, None);
    let mut it = argv.into_iter();
    let mut only_paths = false;
    while let Some(a) = it.next() {
        if !only_paths && a == "--" {
            only_paths = true;
        } else if !only_paths && a == "--report" {
            let v = it.next().ok_or("--report needs FILE")?;
            if file.replace(v).is_some() {
                return Err("--report given twice".into());
            }
            continue;
        } else if !only_paths && a == "--report-nonce" {
            let v = it.next().ok_or("--report-nonce needs N")?;
            if nonce.replace(v).is_some() {
                return Err("--report-nonce given twice".into());
            }
            continue;
        }
        rest.push(a);
    }
    match (file, nonce) {
        (None, None) => Ok((rest, None)),
        (Some(_), None) | (None, Some(_)) => Err("--report and --report-nonce must be given together".into()),
        (Some(file), Some(n)) => {
            let n = n.to_str().filter(|s| s.len() == 32 && s.bytes().all(|c| matches!(c, b'0'..=b'9' | b'a'..=b'f')));
            let Some(n) = n else {
                return Err("--report-nonce must be 32 lowercase hexadecimal digits".into());
            };
            if file.is_empty() {
                return Err("--report needs FILE".into());
            }
            Ok((rest, Some(Flags { file, nonce: n.to_string() })))
        }
    }
}

/// Exclusive creation: an existing leaf of any kind (file, directory, symlink,
/// dangling symlink, reparse point) is refused and never followed or overwritten, and
/// the immediate parent must be a real directory, not a symlink or reparse point.
fn create_exclusive(path: &OsStr) -> std::io::Result<File> {
    let p = Path::new(path);
    let leaf = p.file_name().filter(|n| *n != "." && *n != "..").ok_or_else(|| {
        std::io::Error::new(std::io::ErrorKind::InvalidInput, "not a file name")
    })?;
    let parent = match p.parent() {
        Some(d) if !d.as_os_str().is_empty() => d,
        _ => Path::new("."),
    };
    #[cfg(unix)]
    {
        use std::os::unix::ffi::OsStrExt;
        use std::os::unix::io::FromRawFd;
        let cp = std::ffi::CString::new(parent.as_os_str().as_bytes())?;
        let cl = std::ffi::CString::new(leaf.as_bytes())?;
        // SAFETY: NUL-terminated paths; each descriptor is checked before use.
        unsafe {
            let d = libc::open(cp.as_ptr(), libc::O_RDONLY | libc::O_DIRECTORY | libc::O_NOFOLLOW | libc::O_CLOEXEC);
            if d < 0 {
                return Err(std::io::Error::last_os_error());
            }
            let fd = libc::openat(
                d,
                cl.as_ptr(),
                libc::O_WRONLY | libc::O_CREAT | libc::O_EXCL | libc::O_NOFOLLOW | libc::O_CLOEXEC,
                0o600 as libc::c_uint,
            );
            let err = std::io::Error::last_os_error();
            libc::close(d);
            if fd < 0 {
                return Err(err);
            }
            Ok(File::from_raw_fd(fd))
        }
    }
    #[cfg(windows)]
    {
        use std::os::windows::fs::{MetadataExt, OpenOptionsExt};
        const FILE_ATTRIBUTE_REPARSE_POINT: u32 = 0x400;
        const FILE_FLAG_OPEN_REPARSE_POINT: u32 = 0x0020_0000;
        let md = std::fs::symlink_metadata(parent)?;
        if !md.is_dir() || md.file_attributes() & FILE_ATTRIBUTE_REPARSE_POINT != 0 {
            return Err(std::io::Error::new(std::io::ErrorKind::InvalidInput, "the folder is not a plain directory"));
        }
        std::fs::OpenOptions::new()
            .write(true)
            .create_new(true)
            .share_mode(0)
            .custom_flags(FILE_FLAG_OPEN_REPARSE_POINT)
            .open(parent.join(leaf))
    }
}

/// Create FILE and write the start record. On failure the caller exits 1 with the
/// returned reason on stderr and does no other work.
pub fn start(f: &Flags, version: &str) -> Result<(), String> {
    let path = Path::new(&f.file).display().to_string();
    let file = create_exclusive(&f.file).map_err(|e| format!("cannot create {path} ({e})"))?;
    *REPORT.lock().unwrap() = Some(Report { file: Some(file), path, step: None });
    let mut l = String::from("{\"t\":\"start\",\"tool\":\"ingest\",\"version\":");
    js(&mut l, version);
    l.push_str(",\"nonce\":");
    js(&mut l, &f.nonce);
    l.push('}');
    line(l);
    Ok(())
}

pub fn active() -> bool {
    REPORT.lock().unwrap().as_ref().is_some_and(|r| r.file.is_some())
}

/// One progress counter. Records are sparse: the first value seen for a step, each
/// new 1/64 of `total` (every 2^20 units while `total` is 0), and `done == total`.
/// Steps only move forward; a value for an earlier step is ignored.
pub fn progress(step: &'static str, done: u64, total: u64) {
    let Some(k) = STEPS.iter().position(|s| *s == step) else { return };
    let emit = {
        let mut g = REPORT.lock().unwrap();
        let Some(r) = g.as_mut().filter(|r| r.file.is_some()) else { return };
        let bucket = if total > 0 { (done.min(total) as u128 * 64 / total as u128) as u64 } else { done >> 20 };
        match r.step {
            Some((s, _, _)) if s > k => false,
            Some((s, _, d)) if s == k && done <= d => false,
            Some((s, b, _)) if s == k && bucket <= b && done != total => false,
            _ => {
                r.step = Some((k, bucket, done));
                true
            }
        }
    };
    if emit {
        line(format!("{{\"t\":\"progress\",\"step\":\"{step}\",\"done\":{done},\"total\":{total}}}"));
    }
}

/// The terminal refusal or failure record.
pub fn refusal(f: &Fail) {
    if !active() {
        return;
    }
    let mut l = String::from("{\"t\":\"refusal\",\"id\":");
    js(&mut l, f.id);
    l.push_str(",\"subject\":");
    match &f.subject {
        Subject::None => l.push_str("null"),
        Subject::Source(s) => js(&mut l, s),
        Subject::Folder(i) => js(&mut l, &i.to_string()),
        Subject::Boundary(a, b) => {
            l.push('[');
            js(&mut l, a);
            l.push(',');
            js(&mut l, b);
            l.push(']');
        }
    }
    if let Some((t, c, e)) = f.payload.frames {
        l.push_str(&format!(",\"total_frames\":{t},\"capacity_frames\":{c},\"excess_frames\":{e}"));
    }
    if let Some(j) = f.payload.same_as {
        l.push_str(&format!(",\"same_as\":\"{j}\""));
    }
    if let Some(d) = &f.payload.dbtp {
        l.push_str(",\"dbtp\":");
        js(&mut l, d);
    }
    l.push('}');
    line(l);
}

pub fn end(code: i32) {
    if active() {
        line(format!("{{\"t\":\"end\",\"exit\":{code}}}"));
    }
}

fn line(mut l: String) {
    l.push('\n');
    let mut g = REPORT.lock().unwrap();
    let Some(r) = g.as_mut() else { return };
    let Some(f) = r.file.as_mut() else { return };
    let res = f.write(l.as_bytes()).and_then(|n| {
        if n == l.len() {
            Ok(())
        } else {
            Err(std::io::Error::new(std::io::ErrorKind::WriteZero, "short write"))
        }
    });
    if let Err(e) = crate::observe::io_fault("report-write").and(res) {
        eprintln!("ingest: warning: report: cannot write {} ({e})", r.path);
        r.file = None;
    }
}

/// A JSON string. Paths are UTF-8 here (INGEST-1 logical paths are NFC strings).
fn js(out: &mut String, s: &str) {
    out.push('"');
    for c in s.chars() {
        match c {
            '"' => out.push_str("\\\""),
            '\\' => out.push_str("\\\\"),
            '\n' => out.push_str("\\n"),
            '\r' => out.push_str("\\r"),
            '\t' => out.push_str("\\t"),
            c if (c as u32) < 0x20 => out.push_str(&format!("\\u{:04x}", c as u32)),
            c => out.push(c),
        }
    }
    out.push('"');
}
