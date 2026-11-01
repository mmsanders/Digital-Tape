//! TEST-ONLY harmless child for Software594's controlled C01-C28 method (Verification332).
//! Never bundled, pinned or shipped, and never the real INGEST. It takes the production
//! ingest argv unchanged; its behavior comes from an owned fixture file `probe.json` in
//! the first folder argument, never from a flag. It reads its own console association,
//! PID, OS creation time, argv and cwd into the fixture's observation file, writes only
//! the report, the DEST pair it is told to, fixed stdout/stderr bytes, and exits.
//! Software612 (Verification352 P1-P6): copied beside the test executable as the pinned
//! `tapectl.exe`, it takes the production `cards --report R --report-nonce N` argv
//! unchanged and reads its behavior from `probe-cards.json` beside itself. It writes only
//! that report, fixed stdout/stderr bytes and its observation (with the SHA-256 of every
//! byte it wrote), and never opens a device.
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

fn hex_sha(b: &[u8]) -> String {
    use sha2::{Digest, Sha256};
    Sha256::digest(b).iter().map(|x| format!("{x:02x}")).collect()
}

/// The cards stand-in: a report and stdout in the accepted S2 shapes, or a chosen failure.
fn cards(argv: &[String]) -> ! {
    let at = |flag: &str| argv.iter().position(|a| a == flag).map(|i| argv[i + 1].clone()).expect(flag);
    let (report, nonce) = (PathBuf::from(at("--report")), at("--report-nonce"));
    let me = std::env::current_exe().expect("own path");
    let config: serde_json::Value = serde_json::from_slice(&std::fs::read(me.with_file_name("probe-cards.json")).expect("probe-cards.json")).expect("config");
    let text = |k: &str| config[k].as_str().unwrap_or_default().to_owned();
    let mode = text("mode");
    let start = serde_json::json!({"t": "start", "tool": "tapectl cards", "version": text("version"), "nonce": nonce}).to_string();
    let (rep, out, exit): (Vec<u8>, Vec<u8>, i32) = match mode.as_str() {
        "offered" => (format!("{start}\n{{\"t\":\"end\",\"exit\":0}}\n").into_bytes(),
            b"{\"t\":\"card\",\"path\":\"PROBE-DISK-0\",\"bytes\":64000000000}\n{\"t\":\"summary\",\"offered\":1,\"unprobed\":0}\n".to_vec(), 0),
        "refusal" => (format!("{start}\n{{\"t\":\"refusal\",\"id\":\"CARDS_ENUM_UNAVAILABLE\",\"subject\":null,\"os_error\":\"PROBE\"}}\n{{\"t\":\"end\",\"exit\":1}}\n").into_bytes(), Vec::new(), 1),
        "malformed" => (b"not a report \xff\n".to_vec(), b"{\"t\":\"summary\",\"offered\":0,\"unprobed\":0}\n".to_vec(), 0),
        "max-stdout" => (format!("{start}\n{{\"t\":\"end\",\"exit\":0}}\n").into_bytes(), vec![b'o'; 4_194_304], 0),
        "big-stdout" => (format!("{start}\n{{\"t\":\"end\",\"exit\":0}}\n").into_bytes(), vec![b'o'; 4_194_305], 0),
        "sleep" => (format!("{start}\n").into_bytes(), Vec::new(), 0),
        other => panic!("unknown probe cards mode {other}"),
    };
    let err = b"PROBE-CARDS-ERR\0\xff\r\n".to_vec();
    let observed = serde_json::json!({"pid": std::process::id(), "console_window": console_window(), "os_start_ns": own_start_ns(),
        "argv": argv, "cwd": std::env::current_dir().map(|p| p.to_string_lossy().into_owned()).unwrap_or_default(),
        "sha256": {"report": hex_sha(&rep), "stdout": hex_sha(&out), "stderr": hex_sha(&err)}});
    std::fs::write(text("observe"), serde_json::to_vec_pretty(&observed).unwrap()).expect("observation");
    std::fs::write(&report, &rep).expect("report");
    std::io::stdout().write_all(&out).unwrap();
    std::io::stderr().write_all(&err).unwrap();
    std::io::stdout().flush().unwrap();
    // Stopped while waiting here, the run is a timeout or a cancel, never a finished check.
    if mode == "sleep" { std::thread::sleep(std::time::Duration::from_secs(120)); }
    std::process::exit(exit);
}

fn main() {
    let argv: Vec<String> = std::env::args().collect();
    if argv.get(1).map(String::as_str) == Some("cards") { cards(&argv); }
    let at = |flag: &str| argv.iter().position(|a| a == flag).map(|i| argv[i + 1].clone()).expect(flag);
    let (report, nonce, dest) = (PathBuf::from(at("--report")), at("--report-nonce"), PathBuf::from(at("--out")));
    let folders: Vec<String> = argv[argv.iter().position(|a| a == "--").expect("--") + 1..].to_vec();
    let config: serde_json::Value = serde_json::from_slice(&std::fs::read(PathBuf::from(&folders[0]).join("probe.json")).expect("probe.json")).expect("config");
    let text = |k: &str| config[k].as_str().unwrap_or_default().to_owned();
    let observed = serde_json::json!({"pid": std::process::id(), "console_window": console_window(), "os_start_ns": own_start_ns(),
        "argv": argv, "cwd": std::env::current_dir().map(|p| p.to_string_lossy().into_owned()).unwrap_or_default()});
    std::fs::write(text("observe"), serde_json::to_vec_pretty(&observed).unwrap()).expect("observation");
    let mode = text("mode");
    // Stopped while waiting here, the child never creates its report.
    if mode == "sleep-before-report" { std::thread::sleep(std::time::Duration::from_secs(120)); }
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
        "sleep-before-report" => 0,
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
