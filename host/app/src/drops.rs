//! APP-1 §2 drops and APP-1A §2 deduplication. Folders only: a gesture containing any
//! non-folder adds nothing and is the app event DROP_NOT_FOLDER, with zero child calls.
//! The app only reads metadata of dropped paths; it never opens or lists them (INGEST-1
//! does that, and remains authoritative for symlinks, unreadable folders and duplicates).

use std::path::{Path, PathBuf};

#[derive(Debug, PartialEq, Eq)]
pub enum Drop {
    /// The folders to append, in the OS-reported order, after deduplication.
    Folders(Vec<PathBuf>),
    /// Nothing changes: no new child call.
    NoChange,
    NotFolder,
}

/// OS filesystem identity of a real (non-symlink) directory, when it can be established.
fn identity(p: &Path) -> Option<(u64, u64)> {
    let md = std::fs::symlink_metadata(p).ok()?;
    if !md.is_dir() || md.file_type().is_symlink() {
        return None;
    }
    #[cfg(unix)]
    {
        use std::os::unix::fs::MetadataExt;
        Some((md.dev(), md.ino()))
    }
    #[cfg(windows)]
    {
        // Volume serial and file index need a handle; without one the identity is
        // unknown and INGEST stays authoritative for duplicates.
        let _ = md;
        None
    }
}

/// Classify one drop gesture against the folders already appended.
pub fn classify(paths: &[PathBuf], current: &[PathBuf]) -> Drop {
    if paths.is_empty() {
        return Drop::NoChange;
    }
    for p in paths {
        // A symlink to a folder is passed through: INGEST refuses it (FOLDER_SYMLINK).
        let Ok(md) = std::fs::symlink_metadata(p) else { return Drop::NotFolder };
        let is_folder = md.is_dir() || (md.file_type().is_symlink() && std::fs::metadata(p).is_ok_and(|m| m.is_dir()));
        if !is_folder {
            return Drop::NotFolder;
        }
    }
    let mut known: Vec<(u64, u64)> = current.iter().filter_map(|p| identity(p)).collect();
    let mut add = Vec::new();
    for p in paths {
        match identity(p) {
            Some(id) if known.contains(&id) => continue,
            Some(id) => known.push(id),
            None => {}
        }
        add.push(p.clone());
    }
    if add.is_empty() {
        Drop::NoChange
    } else {
        Drop::Folders(add)
    }
}

/// The dropped folder's own name, for messages. Never a full path.
pub fn display_name(p: &Path) -> String {
    p.file_name().map(|n| n.to_string_lossy().into_owned()).unwrap_or_else(|| p.to_string_lossy().into_owned())
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn folders_only_and_dedupe() {
        let t = std::env::temp_dir().join(format!("dtapp-drops-{}", std::process::id()));
        let (a, b) = (t.join("A"), t.join("B"));
        std::fs::create_dir_all(&a).unwrap();
        std::fs::create_dir_all(&b).unwrap();
        std::fs::write(t.join("song.wav"), b"x").unwrap();
        assert_eq!(classify(&[a.clone(), t.join("song.wav")], &[]), Drop::NotFolder);
        assert_eq!(classify(&[a.clone(), b.clone()], &[]), Drop::Folders(vec![a.clone(), b.clone()]));
        #[cfg(unix)]
        {
            assert_eq!(classify(&[a.clone()], &[a.clone()]), Drop::NoChange);
            assert_eq!(classify(&[b.clone(), a.clone()], &[a.clone()]), Drop::Folders(vec![b.clone()]));
            assert_eq!(classify(&[a.join("."), a.clone()], &[]), Drop::Folders(vec![a.join(".")]));
        }
        assert_eq!(display_name(&a), "A");
        std::fs::remove_dir_all(&t).unwrap();
    }
}
