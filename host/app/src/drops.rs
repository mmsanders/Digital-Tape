//! APP-1 §2 drops and APP-1A §2 deduplication. Folders only: a gesture containing any
//! non-folder adds nothing and is the app event DROP_NOT_FOLDER, with zero child calls.
//! The app only reads metadata of dropped paths; it never opens or lists them (INGEST-1
//! does that, and remains authoritative for unreadable content and unknown identities).

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

/// Minimal metadata facts shared by the production classifier and controlled unit inputs.
#[derive(Clone, Debug)]
pub struct Fact { pub plain_folder: bool, pub identity: Option<(u64, u64)> }

fn fact(p: &Path) -> Fact {
    let plain_folder = std::fs::symlink_metadata(p).is_ok_and(|m| {
        #[cfg(windows)]
        { use std::os::windows::fs::MetadataExt; m.is_dir() && !m.file_type().is_symlink() && m.file_attributes() & 0x400 == 0 }
        #[cfg(not(windows))]
        { m.is_dir() && !m.file_type().is_symlink() }
    });
    Fact { plain_folder, identity: if plain_folder { identity(p) } else { None } }
}

/// Classify one complete gesture. Reject symlinks/reparse points before scheduling.
pub fn classify(paths: &[PathBuf], current: &[PathBuf]) -> Drop {
    classify_with(paths, current, fact)
}

/// Classification has one implementation; tests supply metadata facts, never job outcomes.
pub fn classify_with<F: Fn(&Path) -> Fact>(paths: &[PathBuf], current: &[PathBuf], facts: F) -> Drop {
    if paths.is_empty() { return Drop::NoChange; }
    let incoming: Vec<_> = paths.iter().map(|p| facts(p)).collect();
    if incoming.iter().any(|f| !f.plain_folder) { return Drop::NotFolder; }
    let mut known: Vec<_> = current.iter().filter_map(|p| {
        let f = facts(p); if f.plain_folder { f.identity } else { None }
    }).collect();
    let mut add = Vec::new();
    for (p, f) in paths.iter().zip(incoming) {
        if let Some(id) = f.identity {
            if known.contains(&id) { continue; }
            known.push(id);
        }
        add.push(p.clone());
    }
    if add.is_empty() { Drop::NoChange } else { Drop::Folders(add) }
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
