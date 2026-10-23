//! The bundled children. The app runs only the `ingest` and `tapectl` executables that
//! ship beside it, and only when their SHA-256 equals the hash pinned into this build;
//! otherwise the launch is the app event SPAWN_FAILED. Pins are build inputs
//! (DT_INGEST_SHA256 / DT_INGEST_VERSION at compile time), not runtime switches.

use sha2::{Digest, Sha256};
use std::path::{Path, PathBuf};

pub struct Pin {
    pub file: &'static str,
    pub sha256: Option<&'static str>,
    pub version: Option<&'static str>,
}

pub const INGEST: Pin = Pin {
    file: if cfg!(windows) { "ingest.exe" } else { "ingest" },
    sha256: option_env!("DT_INGEST_SHA256"),
    version: option_env!("DT_INGEST_VERSION"),
};

/// Why a child cannot be launched; shown under Show details.
#[derive(Debug)]
pub struct NotLaunchable(pub String);

/// The bundled child's path, verified against its pin.
pub fn resolve(pin: &Pin) -> Result<PathBuf, NotLaunchable> {
    let (Some(want), Some(_)) = (pin.sha256, pin.version) else {
        return Err(NotLaunchable(format!("this build has no pinned {}", pin.file)));
    };
    let exe = std::env::current_exe().map_err(|e| NotLaunchable(format!("cannot locate the app: {e}")))?;
    let dir = exe.parent().ok_or_else(|| NotLaunchable("cannot locate the app folder".into()))?;
    let p = dir.join(pin.file);
    let got = sha256_file(&p).map_err(|e| NotLaunchable(format!("cannot read bundled {}: {e}", pin.file)))?;
    if got != want {
        return Err(NotLaunchable(format!("bundled {} is {got}, not the pinned {want}", pin.file)));
    }
    Ok(p)
}

fn sha256_file(p: &Path) -> std::io::Result<String> {
    let b = std::fs::read(p)?;
    Ok(Sha256::digest(&b).iter().map(|x| format!("{x:02x}")).collect())
}

/// A fresh report nonce: 128 random bits as 32 lowercase hex digits (APP-1A §1).
pub fn nonce() -> String {
    let mut b = [0u8; 16];
    getrandom::fill(&mut b).expect("OS random source");
    b.iter().map(|x| format!("{x:02x}")).collect()
}

#[cfg(test)]
mod tests {
    #[test]
    fn nonce_grammar() {
        let n = super::nonce();
        assert_eq!(n.len(), 32);
        assert!(n.bytes().all(|c| matches!(c, b'0'..=b'9' | b'a'..=b'f')));
        assert_ne!(n, super::nonce());
    }
}
