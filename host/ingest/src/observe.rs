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
//!   and blocks until `<path>` exists (the runner mutates a source or creates DEST);
//! - `INGEST_OBSERVE_PROBE=parent|child` turns the process into the native observer's
//!   selftest probe (see `probe`), so the probe needs no other program on the host;
//! - `INGEST_HEAP_LIMIT=<bytes>` caps live heap bytes through `CapAlloc`, the test
//!   build's global allocator, so an allocation beyond it fails as the OS would when
//!   memory is exhausted (bounded-memory method where no OS limit applies).

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
        // Streamed through a fixed buffer: the seam must not add an allocation the
        // bounded-memory stress would land on (an infallible one would abort).
        let Ok(mut f) = std::fs::File::create(d.join("before").join(format!("{pos}.f64"))) else { return };
        let mut b = [0u8; 16 * 512];
        for (lc, rc) in l.chunks(512).zip(r.chunks(512)) {
            for (i, (a, c)) in lc.iter().zip(rc).enumerate() {
                b[i * 16..i * 16 + 8].copy_from_slice(&a.to_le_bytes());
                b[i * 16 + 8..i * 16 + 16].copy_from_slice(&c.to_le_bytes());
            }
            if f.write_all(&b[..lc.len().min(rc.len()) * 16]).is_err() {
                return;
            }
        }
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

    /// Observer selftest probe. `parent FILE CREATED CHILD DEVICE [PUBLISH]`: read FILE, run
    /// CHILD (`child FILE`, which reads FILE), create CREATED, open DEVICE for reading and
    /// close it without reading; with PUBLISH, create folder `PUBLISH.stage` and publish it to
    /// PUBLISH with the shipping no-replace rename twice (the second attempt must fail because
    /// PUBLISH exists); exit 0. Returns None when this process is not a probe.
    pub fn probe() -> Option<i32> {
        let role = std::env::var("INGEST_OBSERVE_PROBE").ok()?;
        let a: Vec<std::ffi::OsString> = std::env::args_os().skip(1).collect();
        let arg = |i: usize| a.get(i).cloned().unwrap_or_default();
        let _ = std::fs::read(arg(0));
        if role == "parent" {
            let _ = std::process::Command::new(arg(2)).arg(arg(0)).env("INGEST_OBSERVE_PROBE", "child").status();
            let _ = std::fs::File::create(arg(1));
            let _ = std::fs::OpenOptions::new().read(true).open(arg(3));
            if let Some(publish) = a.get(4).map(PathBuf::from) {
                let mut stage = publish.clone().into_os_string();
                stage.push(".stage");
                let stage = PathBuf::from(stage);
                let _ = std::fs::create_dir(&stage);
                let _ = crate::publish::rename_noreplace(&stage, &publish);
                let _ = std::fs::create_dir(&stage);
                let _ = crate::publish::rename_noreplace(&stage, &publish);
            }
        }
        Some(0)
    }

    use std::alloc::{GlobalAlloc, Layout, System};
    use std::sync::atomic::AtomicUsize;

    static LIVE: AtomicUsize = AtomicUsize::new(0);
    static LIMIT: AtomicUsize = AtomicUsize::new(0);

    /// Reads `INGEST_HEAP_LIMIT` once at startup (reading the environment allocates,
    /// so it cannot happen inside the allocator). Zero means unlimited.
    pub fn init_heap_limit() {
        if dir().is_none() {
            return;
        }
        if let Some(n) = std::env::var("INGEST_HEAP_LIMIT").ok().and_then(|v| v.parse::<usize>().ok()) {
            LIMIT.store(n, Ordering::SeqCst);
        }
    }

    pub struct CapAlloc;

    unsafe impl GlobalAlloc for CapAlloc {
        unsafe fn alloc(&self, l: Layout) -> *mut u8 {
            let limit = LIMIT.load(Ordering::Relaxed);
            if limit != 0 && LIVE.load(Ordering::Relaxed).saturating_add(l.size()) > limit {
                return std::ptr::null_mut();
            }
            let p = unsafe { System.alloc(l) };
            if !p.is_null() {
                LIVE.fetch_add(l.size(), Ordering::Relaxed);
            }
            p
        }
        unsafe fn dealloc(&self, p: *mut u8, l: Layout) {
            unsafe { System.dealloc(p, l) };
            LIVE.fetch_sub(l.size(), Ordering::Relaxed);
        }
        unsafe fn realloc(&self, p: *mut u8, l: Layout, n: usize) -> *mut u8 {
            let limit = LIMIT.load(Ordering::Relaxed);
            if limit != 0 && n > l.size() && LIVE.load(Ordering::Relaxed).saturating_add(n - l.size()) > limit {
                return std::ptr::null_mut();
            }
            let q = unsafe { System.realloc(p, l, n) };
            if !q.is_null() {
                LIVE.fetch_add(n, Ordering::Relaxed);
                LIVE.fetch_sub(l.size(), Ordering::Relaxed);
            }
            q
        }
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
    #[inline(always)]
    pub fn init_heap_limit() {}
    #[inline(always)]
    pub fn probe() -> Option<i32> {
        None
    }
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
