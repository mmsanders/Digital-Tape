//! APP-1 §2/§5 app-owned directories. Each job lives in its own directory under the
//! app's per-user data folder, marked by a marker file the app writes first. The app
//! writes only inside these directories and deletes only directories that carry its
//! marker; it never follows a symlink or reparse point into anything else.

use std::path::{Path, PathBuf};

pub const MARKER: &str = ".digital-tape-app-owned";
const MARKER_TEXT: &[u8] = b"digital-tape app job directory v1\n";

#[derive(Debug, Clone)]
pub struct Job {
    pub dir: PathBuf,
    /// Private control directory: report files only.
    pub control: PathBuf,
    /// The DEST parent: ingest's DEST and its stage are created here by ingest.
    pub out: PathBuf,
}

fn jobs_root(data: &Path) -> PathBuf {
    data.join("jobs")
}

fn is_plain_dir(p: &Path) -> bool {
    std::fs::symlink_metadata(p).is_ok_and(|m| m.is_dir() && !m.file_type().is_symlink() && !is_reparse(&m))
}

#[cfg(windows)]
fn is_reparse(m: &std::fs::Metadata) -> bool {
    use std::os::windows::fs::MetadataExt;
    m.file_attributes() & 0x400 != 0
}
#[cfg(not(windows))]
fn is_reparse(_m: &std::fs::Metadata) -> bool {
    false
}

/// The app's per-user data folder, created if missing.
pub fn prepare(data: &Path) -> std::io::Result<()> {
    std::fs::create_dir_all(data)
}

/// Whether `dir` is one of this app's job directories.
pub fn owned(dir: &Path) -> bool {
    if !is_plain_dir(dir) {
        return false;
    }
    let m = dir.join(MARKER);
    std::fs::symlink_metadata(&m).is_ok_and(|md| md.is_file()) && std::fs::read(&m).is_ok_and(|b| b == MARKER_TEXT)
}

/// A fresh job directory with its marker, control directory and DEST parent.
pub fn create(data: &Path, name: &str) -> std::io::Result<Job> {
    let root = jobs_root(data);
    std::fs::create_dir_all(&root)?;
    if !is_plain_dir(&root) {
        return Err(std::io::Error::other("the app's jobs folder is not a plain directory"));
    }
    let dir = root.join(name);
    std::fs::create_dir(&dir)?; // fails if anything already has this name
    std::fs::OpenOptions::new().write(true).create_new(true).open(dir.join(MARKER)).and_then(|mut f| {
        use std::io::Write;
        f.write_all(MARKER_TEXT)
    })?;
    let (control, out) = (dir.join("control"), dir.join("out"));
    std::fs::create_dir(&control)?;
    std::fs::create_dir(&out)?;
    Ok(Job { dir, control, out })
}

/// Remove one job directory, only if it is ours.
pub fn remove(job: &Job) -> bool {
    owned(&job.dir) && std::fs::remove_dir_all(&job.dir).is_ok()
}

/// At launch: remove only stale directories that carry this app's marker. Anything else
/// under the jobs folder, including symlinks, is left alone.
pub fn clean_stale(data: &Path) -> usize {
    let Ok(rd) = std::fs::read_dir(jobs_root(data)) else { return 0 };
    let mut n = 0;
    for e in rd.flatten() {
        let p = e.path();
        if owned(&p) && std::fs::remove_dir_all(&p).is_ok() {
            n += 1;
        }
    }
    n
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn deletes_only_marked_dirs() {
        let data = std::env::temp_dir().join(format!("dtapp-jobs-{}", std::process::id()));
        let _ = std::fs::remove_dir_all(&data);
        let j = create(&data, "j1").unwrap();
        assert!(owned(&j.dir));
        let foreign = data.join("jobs").join("not-ours");
        std::fs::create_dir_all(&foreign).unwrap();
        std::fs::write(foreign.join(MARKER), b"something else").unwrap();
        #[cfg(unix)]
        {
            let target = data.join("precious");
            std::fs::create_dir_all(&target).unwrap();
            std::fs::write(target.join(MARKER), MARKER_TEXT).unwrap();
            std::os::unix::fs::symlink(&target, data.join("jobs").join("link")).unwrap();
            assert_eq!(clean_stale(&data), 1);
            assert!(target.join(MARKER).exists(), "a symlinked marked directory is never followed");
        }
        #[cfg(not(unix))]
        assert_eq!(clean_stale(&data), 1);
        assert!(!j.dir.exists());
        assert!(foreign.exists());
        std::fs::remove_dir_all(&data).unwrap();
    }
}
