//! Pair transaction (contract §6): an exclusively created stage beside DEST holding only
//! audio.wav and manifest.json, flushed, then published by one no-replace directory
//! rename. Ordinary errors remove only this run's stage.

use crate::common::*;
use std::fs::{self, File, OpenOptions};
use std::io::Write;
use std::path::{Path, PathBuf};

pub const STAGE_MARK: &str = ".ingest-stage-";

fn io<T>(what: &str, p: &Path, r: std::io::Result<T>) -> Res<T> {
    r.map_err(|e| Fail::Io(format!("{what} {}: {e}", p.display())))
}

fn write_new(p: &Path, parts: &[&[u8]]) -> Res<()> {
    let mut f = io("cannot create", p, OpenOptions::new().write(true).create_new(true).open(p))?;
    for b in parts {
        io("cannot write", p, f.write_all(b))?;
    }
    io("cannot flush", p, f.sync_all())
}

fn sync_dir(_p: &Path) -> Res<()> {
    #[cfg(unix)]
    {
        let d = io("cannot open", _p, File::open(_p))?;
        io("cannot flush", _p, d.sync_all())?;
    }
    Ok(())
}

#[cfg(target_os = "linux")]
fn rename_noreplace(a: &Path, b: &Path) -> std::io::Result<()> {
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
fn rename_noreplace(a: &Path, b: &Path) -> std::io::Result<()> {
    use std::ffi::CString;
    use std::os::unix::ffi::OsStrExt;
    let ca = CString::new(a.as_os_str().as_bytes())?;
    let cb = CString::new(b.as_os_str().as_bytes())?;
    // SAFETY: valid NUL-terminated paths.
    let r = unsafe { libc::renamex_np(ca.as_ptr(), cb.as_ptr(), libc::RENAME_EXCL) };
    if r == 0 { Ok(()) } else { Err(std::io::Error::last_os_error()) }
}

#[cfg(windows)]
fn rename_noreplace(a: &Path, b: &Path) -> std::io::Result<()> {
    use std::os::windows::ffi::OsStrExt;
    use windows_sys::Win32::Storage::FileSystem::MoveFileExW;
    let wa: Vec<u16> = a.as_os_str().encode_wide().chain(Some(0)).collect();
    let wb: Vec<u16> = b.as_os_str().encode_wide().chain(Some(0)).collect();
    // SAFETY: valid NUL-terminated wide paths. Flags 0: never replace an existing target.
    let ok = unsafe { MoveFileExW(wa.as_ptr(), wb.as_ptr(), 0) };
    if ok != 0 { Ok(()) } else { Err(std::io::Error::last_os_error()) }
}

#[cfg(not(any(target_os = "linux", target_os = "macos", windows)))]
fn rename_noreplace(_a: &Path, _b: &Path) -> std::io::Result<()> {
    Err(std::io::Error::new(std::io::ErrorKind::Unsupported, "no no-replace rename on this platform"))
}

/// DEST must not exist (checked up front, and again atomically by the rename).
pub fn check_dest(dest: &Path) -> Res<()> {
    if fs::symlink_metadata(dest).is_ok() {
        return Err(Fail::Refuse(format!("{}: already exists; ingest never overwrites", dest.display())));
    }
    let parent = parent_of(dest);
    match fs::metadata(&parent) {
        Ok(m) if m.is_dir() => Ok(()),
        _ => Err(Fail::Io(format!("{}: the parent folder does not exist", parent.display()))),
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
    let name = dest.file_name().ok_or_else(|| Fail::Refuse(format!("{}: not a usable destination name", dest.display())))?;
    let mut stage = None;
    for i in 0..1000u32 {
        let mut n = std::ffi::OsString::from(".");
        n.push(name);
        n.push(format!("{STAGE_MARK}{}-{i}", std::process::id()));
        let p = parent.join(n);
        match fs::create_dir(&p) {
            Ok(()) => {
                stage = Some(p);
                break;
            }
            Err(e) if e.kind() == std::io::ErrorKind::AlreadyExists => continue,
            Err(e) => return Err(Fail::Io(format!("cannot create stage {}: {e}", p.display()))),
        }
    }
    let stage = stage.ok_or_else(|| Fail::Io("cannot create a fresh stage folder".into()))?;
    let result = (|| -> Res<()> {
        write_new(&stage.join("audio.wav"), wav)?;
        write_new(&stage.join("manifest.json"), &[manifest])?;
        sync_dir(&stage)?;
        match rename_noreplace(&stage, dest) {
            Ok(()) => {}
            Err(e) if e.kind() == std::io::ErrorKind::AlreadyExists || fs::symlink_metadata(dest).is_ok() => {
                return Err(Fail::Refuse(format!("{}: appeared while ingest ran; not overwritten", dest.display())))
            }
            Err(e) => return Err(Fail::Io(format!("cannot publish {}: {e}", dest.display()))),
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
