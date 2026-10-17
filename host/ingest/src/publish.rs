//! Pair transaction (contract §6): an exclusively created stage beside DEST holding only
//! audio.wav and manifest.json, flushed, then published by one no-replace directory
//! rename. Ordinary errors remove only this run's stage.

use crate::common::*;
use crate::observe;
use std::fs::{self, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};

pub const STAGE_MARK: &str = ".ingest-stage-";

fn io<T>(what: &str, p: &Path, r: std::io::Result<T>) -> Res<T> {
    r.map_err(|e| Fail::io(IO_DEST, format!("{what} {}: {e}", p.display())))
}

/// Create, write and flush one staged file; `which` is `audio` or `manifest` (the
/// test build's milestone, cut and fault names).
fn write_new(p: &Path, parts: &[&[u8]], which: &str) -> Res<()> {
    let mut f = io("cannot create", p, OpenOptions::new().write(true).create_new(true).open(p))?;
    observe::mark("output_open");
    observe::cut(&format!("{which}-open"));
    // APP-1A §4 `write`: stage WAV bytes written, of 44 + 4 * total_frames.
    let total: u64 = if which == "audio" { parts.iter().map(|b| b.len() as u64).sum() } else { 0 };
    let mut done = 0u64;
    for b in parts {
        io("cannot write", p, observe::io_fault(&format!("{which}-write")).and_then(|_| f.write_all(b)))?;
        if which == "audio" {
            done += b.len() as u64;
            crate::report::progress("write", done, total);
        }
    }
    io("cannot flush", p, observe::io_fault(&format!("{which}-flush")).and_then(|_| f.sync_all()))?;
    drop(f);
    observe::mark(&format!("{which}_flush_close"));
    observe::cut(&format!("{which}-flush"));
    Ok(())
}

fn sync_dir(_p: &Path) -> Res<()> {
    #[cfg(unix)]
    {
        let d = io("cannot open", _p, fs::File::open(_p))?;
        io("cannot flush", _p, d.sync_all())?;
    }
    Ok(())
}

#[cfg(target_os = "linux")]
pub(crate) fn rename_noreplace(a: &Path, b: &Path) -> std::io::Result<()> {
    use std::ffi::CString;
    use std::os::unix::ffi::OsStrExt;
    let ca = CString::new(a.as_os_str().as_bytes())?;
    let cb = CString::new(b.as_os_str().as_bytes())?;
    // SAFETY: valid NUL-terminated paths; renameat2 has no other preconditions.
    let r = unsafe {
        libc::syscall(libc::SYS_renameat2, libc::AT_FDCWD, ca.as_ptr(), libc::AT_FDCWD, cb.as_ptr(), libc::RENAME_NOREPLACE)
    };
    if r == 0 { Ok(()) } else { Err(std::io::Error::last_os_error()) }
}

#[cfg(target_os = "macos")]
pub(crate) fn rename_noreplace(a: &Path, b: &Path) -> std::io::Result<()> {
    use std::ffi::CString;
    use std::os::unix::ffi::OsStrExt;
    let ca = CString::new(a.as_os_str().as_bytes())?;
    let cb = CString::new(b.as_os_str().as_bytes())?;
    // SAFETY: valid NUL-terminated paths.
    let r = unsafe { libc::renamex_np(ca.as_ptr(), cb.as_ptr(), libc::RENAME_EXCL) };
    if r == 0 { Ok(()) } else { Err(std::io::Error::last_os_error()) }
}

#[cfg(windows)]
pub(crate) fn rename_noreplace(a: &Path, b: &Path) -> std::io::Result<()> {
    use std::os::windows::ffi::OsStrExt;
    use windows_sys::Win32::Storage::FileSystem::MoveFileExW;
    let wa: Vec<u16> = a.as_os_str().encode_wide().chain(Some(0)).collect();
    let wb: Vec<u16> = b.as_os_str().encode_wide().chain(Some(0)).collect();
    // SAFETY: valid NUL-terminated wide paths. Flags 0: never replace an existing target.
    let ok = unsafe { MoveFileExW(wa.as_ptr(), wb.as_ptr(), 0) };
    if ok != 0 { Ok(()) } else { Err(std::io::Error::last_os_error()) }
}

#[cfg(not(any(target_os = "linux", target_os = "macos", windows)))]
pub(crate) fn rename_noreplace(_a: &Path, _b: &Path) -> std::io::Result<()> {
    Err(std::io::Error::new(std::io::ErrorKind::Unsupported, "no no-replace rename on this platform"))
}

/// DEST must not exist (checked up front, and again atomically by the rename).
pub fn check_dest(dest: &Path) -> Res<()> {
    if fs::symlink_metadata(dest).is_ok() {
        return Err(Fail::refuse(DEST_EXISTS, format!("{}: already exists; ingest never overwrites", dest.display())));
    }
    let parent = parent_of(dest);
    match fs::metadata(&parent) {
        Ok(m) if m.is_dir() => Ok(()),
        _ => Err(Fail::io(IO_DEST, format!("{}: the parent folder does not exist", parent.display()))),
    }
}

fn parent_of(dest: &Path) -> PathBuf {
    match dest.parent() {
        Some(p) if !p.as_os_str().is_empty() => p.to_path_buf(),
        _ => PathBuf::from("."),
    }
}

pub fn publish(dest: &Path, wav: &[&[u8]], manifest: &[u8]) -> Res<()> {
    let parent = parent_of(dest);
    let name = dest.file_name().ok_or_else(|| Fail::refuse(DEST_NAME_INVALID, format!("{}: not a usable destination name", dest.display())))?;
    let mut stage = None;
    observe::cut("before-stage");
    for i in 0..1000u32 {
        let mut n = std::ffi::OsString::from(".");
        n.push(name);
        n.push(format!("{STAGE_MARK}{}-{i}", std::process::id()));
        let p = parent.join(n);
        match observe::io_fault("stage-create").and_then(|_| fs::create_dir(&p)) {
            Ok(()) => {
                observe::mark_with("stage_create", ",\"exclusive\":true,\"adjacent\":true");
                stage = Some(p);
                break;
            }
            Err(e) if e.kind() == std::io::ErrorKind::AlreadyExists => continue,
            Err(e) => return Err(Fail::io(IO_DEST, format!("cannot create stage {}: {e}", p.display()))),
        }
    }
    let stage = stage.ok_or_else(|| Fail::io(IO_DEST, "cannot create a fresh stage folder"))?;
    let result = (|| -> Res<()> {
        write_new(&stage.join("audio.wav"), wav, "audio")?;
        write_new(&stage.join("manifest.json"), &[manifest], "manifest")?;
        sync_dir(&stage)?;
        observe::cut("before-publish");
        match observe::io_fault("publish").and_then(|_| rename_noreplace(&stage, dest)) {
            Ok(()) => {
                observe::mark("publish_dir_noreplace");
            }
            Err(e) if e.kind() == std::io::ErrorKind::AlreadyExists || fs::symlink_metadata(dest).is_ok() => {
                return Err(Fail::refuse(DEST_APPEARED, format!("{}: appeared while ingest ran; not overwritten", dest.display())))
            }
            Err(e) => return Err(Fail::io(IO_DEST, format!("cannot publish {}: {e}", dest.display()))),
        }
        sync_dir(&parent)
    })();
    if result.is_err() && stage.exists() {
        let _ = fs::remove_file(stage.join("audio.wav"));
        let _ = fs::remove_file(stage.join("manifest.json"));
        let _ = fs::remove_dir(&stage);
    }
    result
}
