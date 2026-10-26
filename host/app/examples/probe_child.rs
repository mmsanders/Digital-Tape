//! TEST-ONLY harmless child for Software594's controlled C01-C28 method (Verification332).
//! Never bundled, pinned or shipped, and never the real INGEST. It takes the production
//! ingest argv unchanged; its behavior comes from an owned fixture file `probe.json` in
//! the first folder argument, never from a flag. It reads its own console association,
//! PID, OS creation time, argv and cwd into the fixture's observation file, writes only
//! the report, the DEST pair it is told to, fixed stdout/stderr bytes, and exits.
use std::io::Write;
use std::path::PathBuf;

#[cfg(windows)]
#[link(name = "kernel32")]
extern "system" {
    fn GetConsoleWindow() -> *mut std::ffi::c_void;
    fn GetCurrentProcess() -> *mut std::ffi::c_void;
    fn GetProcessTimes(p: *mut std::ffi::c_void, c: *mut u64, e: *mut u64, k: *mut u64, u: *mut u64) -> i32;
}

fn console_window() -> Option<bool> {
    #[cfg(windows)]
    // SAFETY: no arguments; returns this process's console window or null.
    return Some(!unsafe { GetConsoleWindow() }.is_null());
    #[cfg(not(windows))]
    None
}

fn own_start_ns() -> Option<u64> {
    #[cfg(windows)]
    {
        let (mut c, mut e, mut k, mut u) = (0u64, 0u64, 0u64, 0u64);
        // SAFETY: the pseudo-handle and four writable FILETIME-sized slots.
        if unsafe { GetProcessTimes(GetCurrentProcess(), &mut c, &mut e, &mut k, &mut u) } == 0 { return None; }
        return c.checked_sub(116_444_736_000_000_000).map(|t| t * 100);
    }
    #[cfg(not(windows))]
    None
}

fn main() {
    let argv: Vec<String> = std::env::args().collect();
    let at = |flag: &str| argv.iter().position(|a| a == flag).map(|i| argv[i + 1].clone()).expect(flag);
    let (report, nonce, dest) = (PathBuf::from(at("--report")), at("--report-nonce"), PathBuf::from(at("--out")));
    let folders: Vec<String> = argv[argv.iter().position(|a| a == "--").expect("--") + 1..].to_vec();
    let config: serde_json::Value = serde_json::from_slice(&std::fs::read(PathBuf::from(&folders[0]).join("probe.json")).expect("probe.json")).expect("config");
    let text = |k: &str| config[k].as_str().unwrap_or_default().to_owned();
    let observed = serde_json::json!({"pid": std::process::id(), "console_window": console_window(), "os_start_ns": own_start_ns(),
        "argv": argv, "cwd": std::env::current_dir().map(|p| p.to_string_lossy().into_owned()).unwrap_or_default()});
    std::fs::write(text("observe"), serde_json::to_vec_pretty(&observed).unwrap()).expect("observation");
    let mode = text("mode");
    let mut r = std::fs::File::create(&report).expect("report");
    let start = serde_json::json!({"t": "start", "tool": "ingest", "version": text("version"), "nonce": nonce});
    // Fixed originals: NUL, non-UTF-8 and CRLF bytes must survive capture unchanged.
    let out_bytes = config["stdout_bytes"].as_u64().map_or_else(|| b"PROBE-OUT\0\xff\r\n".to_vec(), |n| vec![b'o'; n as usize]);
    std::io::stdout().write_all(&out_bytes).unwrap();
    std::io::stderr().write_all(b"PROBE-ERR\r\n\xfe<diagnostic>\n").unwrap();
    let exit = match mode.as_str() {
        "success" => {
            writeln!(r, "{start}").unwrap();
            let frames = config["frames"].as_u64().unwrap_or(4);
            std::fs::create_dir(&dest).expect("DEST");
            let data = (frames * 4) as u32;
            let mut wav = Vec::new();
            for part in [&b"RIFF"[..], &(36 + data).to_le_bytes(), b"WAVEfmt ", &16u32.to_le_bytes(), &1u16.to_le_bytes(), &2u16.to_le_bytes(),
                &44100u32.to_le_bytes(), &176400u32.to_le_bytes(), &4u16.to_le_bytes(), &16u16.to_le_bytes(), b"data", &data.to_le_bytes()] { wav.extend_from_slice(part); }
            wav.resize(wav.len() + data as usize, 0);
            std::fs::write(dest.join("audio.wav"), wav).unwrap();
            std::fs::write(dest.join("manifest.json"), format!("{{\"total_frames\":{frames}}}\n")).unwrap();
            writeln!(r, "{}", serde_json::json!({"t": "end", "exit": 0})).unwrap();
            0
        }
        "refusal" => {
            writeln!(r, "{start}").unwrap();
            writeln!(r, "{}", serde_json::json!({"t": "refusal", "id": "FOLDER_EMPTY", "subject": "0"})).unwrap();
            writeln!(r, "{}", serde_json::json!({"t": "end", "exit": 2})).unwrap();
            2
        }
        "malformed" => {
            r.write_all(b"not a report \xff\n").unwrap();
            2
        }
        "sleep" => {
            writeln!(r, "{start}").unwrap();
            r.flush().unwrap();
            std::thread::sleep(std::time::Duration::from_secs(120));
            0
        }
        other => panic!("unknown probe mode {other}"),
    };
    drop(r);
    std::process::exit(exit);
}
