//! Test-build observation seam (cargo feature `observe`). The shipping build compiles
//! every function here to a no-op: no environment is read, no file is written, and
//! `tools/check_seam.py` proves the shipping binary carries none of these strings.
//!
//! With the feature, and only when `INGEST_OBSERVE_DIR` is set:
//! - `mark(op)` records a normalized milestone in `events.jsonl` and performs one
//!   `stat` of `<dir>/.mark/<seq>-<op>` so the native observer's raw trace carries the
//!   milestone in order with the real file operations;
//! - `before(pos, l, r)` writes source `pos`'s isolated pre-gain 44.1 kHz floats as
//!   interleaved stereo little-endian f64 (`before/<pos>.f64`);
//! - `joined(db)` writes `joined.json`;
//! - `INGEST_KILL_AT=<cut>` aborts the process at that cut (no cleanup runs);
//! - `INGEST_FAULT=<op>` makes that operation fail as an I/O error;
//! - `INGEST_PAUSE_AT=<op>` with `INGEST_PAUSE_FILE=<path>` creates `<path>.waiting`
//!   and blocks until `<path>` exists (the runner mutates a source or creates DEST).

#[cfg(feature = "observe")]
mod imp {
    use std::io::Write;
    use std::path::PathBuf;
    use std::sync::atomic::{AtomicU64, Ordering};

    static SEQ: AtomicU64 = AtomicU64::new(0);

    fn dir() -> Option<PathBuf> {
        std::env::var_os("INGEST_OBSERVE_DIR").map(PathBuf::from)
    }

    fn env_is(key: &str, v: &str) -> bool {
        dir().is_some() && std::env::var(key).map(|x| x == v).unwrap_or(false)
    }

    pub fn mark_with(op: &str, extra: &str) {
        let Some(d) = dir() else { return };
        let seq = SEQ.fetch_add(1, Ordering::SeqCst);
        let _ = std::fs::metadata(d.join(".mark").join(format!("{seq}-{op}")));
        let line = format!("{{\"seq\":{seq},\"op\":\"{op}\"{extra}}}\n");
        if let Ok(mut f) = std::fs::OpenOptions::new().create(true).append(true).open(d.join("events.jsonl")) {
            let _ = f.write_all(line.as_bytes());
        }
    }

    pub fn cut(name: &str) {
        if env_is("INGEST_KILL_AT", name) {
            mark_with("kill", &format!(",\"cut\":\"{name}\""));
            std::process::abort();
        }
        if env_is("INGEST_PAUSE_AT", name) {
            if let Some(p) = std::env::var_os("INGEST_PAUSE_FILE").map(PathBuf::from) {
                let mut w = p.clone().into_os_string();
                w.push(".waiting");
                let _ = std::fs::write(&w, b"");
                while !p.exists() {
                    std::thread::sleep(std::time::Duration::from_millis(20));
                }
            }
        }
    }

    pub fn fault(op: &str) -> bool {
        env_is("INGEST_FAULT", op)
    }

    pub fn before(pos: usize, l: &[f64], r: &[f64]) {
        let Some(d) = dir() else { return };
        let _ = std::fs::create_dir_all(d.join("before"));
        let mut b = Vec::with_capacity(l.len() * 16);
        for (a, c) in l.iter().zip(r) {
            b.extend_from_slice(&a.to_le_bytes());
            b.extend_from_slice(&c.to_le_bytes());
        }
        let _ = std::fs::write(d.join("before").join(format!("{pos}.f64")), b);
    }

    pub fn before_zero(pos: usize, frames: u64) {
        let Some(d) = dir() else { return };
        let _ = std::fs::create_dir_all(d.join("before"));
        let _ = std::fs::write(
            d.join("before").join(format!("{pos}.json")),
            format!("{{\"kind\":\"entire-zero\",\"frames\":{frames}}}\n"),
        );
    }

    pub fn joined(db: Option<f64>) {
        let Some(d) = dir() else { return };
        let v = db.map(|x| format!("{x:?}")).unwrap_or_else(|| "null".into());
        let _ = std::fs::write(d.join("joined.json"), format!("{{\"joined_dbtp\":{v}}}\n"));
    }
}

#[cfg(not(feature = "observe"))]
mod imp {
    #[inline(always)]
    pub fn mark_with(_op: &str, _extra: &str) {}
    #[inline(always)]
    pub fn cut(_name: &str) {}
    #[inline(always)]
    pub fn fault(_op: &str) -> bool {
        false
    }
    #[inline(always)]
    pub fn before(_pos: usize, _l: &[f64], _r: &[f64]) {}
    #[inline(always)]
    pub fn before_zero(_pos: usize, _frames: u64) {}
    #[inline(always)]
    pub fn joined(_db: Option<f64>) {}
}

pub use imp::*;

pub fn mark(op: &str) {
    mark_with(op, "")
}

/// An injected I/O failure at `op` (test build only).
pub fn io_fault(op: &str) -> std::io::Result<()> {
    if fault(op) {
        Err(std::io::Error::other(format!("injected test fault at {op}")))
    } else {
        Ok(())
    }
}
