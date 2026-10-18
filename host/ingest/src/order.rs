//! Folder listing, name validation and the issued natural order (contract §2).

use crate::common::*;
use std::cmp::Ordering;
use std::fs;
use std::path::{Path, PathBuf};
use unicode_normalization::UnicodeNormalization;

#[derive(Debug, PartialEq, Eq)]
enum Tok {
    Num(String), // ASCII digits, leading zeros stripped (value comparison)
    Text(Vec<char>),
}

fn tokens(nfc: &str) -> Vec<Tok> {
    let mut out = Vec::new();
    let cs: Vec<char> = nfc.chars().collect();
    let mut i = 0;
    while i < cs.len() {
        let digit = cs[i].is_ascii_digit();
        let s = i;
        while i < cs.len() && cs[i].is_ascii_digit() == digit {
            i += 1;
        }
        if digit {
            let d: String = cs[s..i].iter().collect();
            let t = d.trim_start_matches('0');
            out.push(Tok::Num(t.to_string()));
        } else {
            out.push(Tok::Text(cs[s..i].iter().map(|c| c.to_ascii_lowercase()).collect()));
        }
    }
    out
}

fn cmp_tok(a: &Tok, b: &Tok) -> Ordering {
    match (a, b) {
        (Tok::Num(x), Tok::Num(y)) => x.len().cmp(&y.len()).then_with(|| x.cmp(y)),
        (Tok::Num(_), Tok::Text(_)) => Ordering::Less,
        (Tok::Text(_), Tok::Num(_)) => Ordering::Greater,
        (Tok::Text(x), Tok::Text(y)) => x.cmp(y),
    }
}

/// Primary key: tokens; a token-prefix sorts first. Ties: NFC original-case scalars, then
/// original UTF-8 bytes.
pub fn natural_cmp(a_nfc: &str, a_raw: &str, b_nfc: &str, b_raw: &str) -> Ordering {
    let ta = tokens(a_nfc);
    let tb = tokens(b_nfc);
    for (x, y) in ta.iter().zip(&tb) {
        let o = cmp_tok(x, y);
        if o != Ordering::Equal {
            return o;
        }
    }
    ta.len()
        .cmp(&tb.len())
        .then_with(|| a_nfc.chars().cmp(b_nfc.chars()))
        .then_with(|| a_raw.as_bytes().cmp(b_raw.as_bytes()))
}

pub struct Entry {
    pub path: PathBuf,
    pub logical: String,
}

const WIN_RESERVED: [&str; 22] = [
    "CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8", "COM9", "LPT1",
    "LPT2", "LPT3", "LPT4", "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
];

/// A name a required OS (Windows 11, macOS, Linux) cannot represent is refused, not renamed.
fn check_name(name: &str) -> Result<(), String> {
    if name.chars().any(|c| (c as u32) < 0x20 || "<>:\"/\\|?*".contains(c)) {
        return Err("contains a character Windows or macOS cannot store in a file name".into());
    }
    if name.ends_with(' ') || name.ends_with('.') {
        return Err("ends in a space or dot, which Windows cannot store".into());
    }
    let stem = name.split('.').next().unwrap_or("").trim_end().to_ascii_uppercase();
    if WIN_RESERVED.contains(&stem.as_str()) {
        return Err("is a reserved Windows device name".into());
    }
    Ok(())
}

/// List one folder: immediate regular files only, validated and in natural order.
pub fn list_folder(dir: &Path, ordinal: usize) -> Res<Vec<Entry>> {
    // APP-1A §2 subjects: the folder by ordinal, or an entry by its logical path.
    let folder = || Subject::Folder(ordinal);
    let entry = |raw: &str| Subject::Source(format!("{ordinal}/{}", raw.nfc().collect::<String>()));
    let disp = dir.display();
    let rd = fs::read_dir(dir).map_err(|e| Fail::io(IO_FOLDER, format!("cannot read folder {disp}: {e}")).about(folder()))?;
    let mut items: Vec<(String, String, PathBuf)> = Vec::new();
    for ent in rd {
        let ent = ent.map_err(|e| Fail::io(IO_FOLDER, format!("cannot read folder {disp}: {e}")).about(folder()))?;
        let os = ent.file_name();
        let Some(raw) = os.to_str() else {
            return Err(Fail::refuse(FOLDER_NAME_NOT_UNICODE, format!(
                "{disp}: a file name is not valid Unicode ({})",
                os.to_string_lossy()
            ))
            .about(folder()));
        };
        let raw = raw.to_string();
        let ft = ent.file_type().map_err(|e| Fail::io(IO_FOLDER, format!("{disp}/{raw}: {e}")).about(folder()))?;
        if ft.is_symlink() {
            return Err(Fail::refuse(ENTRY_SYMLINK, format!("{disp}/{raw}: symbolic links are not followed; refusing")).about(entry(&raw)));
        }
        if ft.is_dir() {
            return Err(Fail::refuse(ENTRY_NESTED_FOLDER, format!("{disp}/{raw}: nested folders are not allowed; a source folder must hold only audio files")).about(entry(&raw)));
        }
        if !ft.is_file() {
            return Err(Fail::refuse(ENTRY_NOT_REGULAR, format!("{disp}/{raw}: not a regular file")).about(entry(&raw)));
        }
        let nfc: String = raw.nfc().collect();
        if let Err(why) = check_name(&nfc) {
            return Err(Fail::refuse(ENTRY_NAME_INVALID, format!("{disp}/{raw}: the name {why}")).about(entry(&raw)));
        }
        push(&mut items, (nfc, raw, ent.path()))?;
    }
    if items.is_empty() {
        return Err(Fail::refuse(FOLDER_EMPTY, format!("{disp}: the folder is empty")).about(folder()));
    }
    // Collisions: identical NFC logical paths, or names equal under case folding (refused
    // because Windows and macOS default volumes cannot hold both).
    let mut keys: Vec<(String, &str)> = collect(items.len(), items.iter().map(|(n, r, _)| (n.to_lowercase(), r.as_str())))?;
    keys.sort();
    for w in keys.windows(2) {
        if w[0].0 == w[1].0 {
            return Err(Fail::refuse(FOLDER_NAME_COLLISION, format!(
                "{disp}: '{}' and '{}' collide after Unicode normalization or case folding",
                w[0].1, w[1].1
            ))
            .about(folder()));
        }
    }
    items.sort_by(|a, b| natural_cmp(&a.0, &a.1, &b.0, &b.1));
    collect(items.len(), items.into_iter().map(|(nfc, _, path)| Entry { logical: format!("{ordinal}/{nfc}"), path }))
}

/// Filesystem identity used to require distinct folders.
pub fn identity(p: &Path) -> Res<String> {
    // A FOLDER argument that is itself a symbolic link is refused, like every other
    // symlink (contract §2: no symlink following).
    if fs::symlink_metadata(p).map(|m| m.file_type().is_symlink()).unwrap_or(false) {
        return Err(Fail::refuse(FOLDER_SYMLINK, format!("{}: the folder is a symbolic link; symbolic links are not followed", p.display())));
    }
    let md = fs::metadata(p).map_err(|e| Fail::refuse(FOLDER_UNREADABLE, format!("{}: folder does not exist or cannot be read ({e})", p.display())))?;
    if !md.is_dir() {
        return Err(Fail::refuse(FOLDER_NOT_FOLDER, format!("{}: not a folder", p.display())));
    }
    #[cfg(unix)]
    {
        use std::os::unix::fs::MetadataExt;
        Ok(format!("{}:{}", md.dev(), md.ino()))
    }
    #[cfg(not(unix))]
    {
        let c = fs::canonicalize(p).map_err(|e| Fail::io(IO_FOLDER, format!("{}: {e}", p.display())))?;
        Ok(c.to_string_lossy().to_lowercase())
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    fn sort(v: &[&str]) -> Vec<String> {
        let mut x: Vec<(String, String)> = v.iter().map(|s| (s.nfc().collect(), s.to_string())).collect();
        x.sort_by(|a, b| natural_cmp(&a.0, &a.1, &b.0, &b.1));
        x.into_iter().map(|p| p.1).collect()
    }
    #[test]
    fn contract_examples() {
        assert_eq!(sort(&["10", "2", "1"]), ["1", "2", "10"]);
        assert_eq!(sort(&["2", "02"]), ["02", "2"]);
        assert_eq!(sort(&["a", "A"]), ["A", "a"]);
        assert_eq!(sort(&["a1", "a"]), ["a", "a1"]);
        assert_eq!(sort(&["b", "1"]), ["1", "b"]);
        assert_eq!(sort(&["track 99999999999999999999999.wav", "track 100000000000000000000000.wav"]),
            ["track 99999999999999999999999.wav", "track 100000000000000000000000.wav"]);
        // non-ASCII digits are text
        assert_eq!(sort(&["\u{0663}", "5"]), ["5", "\u{0663}"]);
    }
}
