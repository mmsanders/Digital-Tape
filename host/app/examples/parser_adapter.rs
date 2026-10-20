//! Test transport for Verification's APP-1A parser package (tests/wp15_app1a_r1,
//! ADAPTER.md): one JSON case per stdin line in, `{valid, message}` per stdout line out.
//! Every answer comes from the app's own `report::read` and `messages::choose`; this
//! file only maps the app's choice onto the package's category names. It decides
//! nothing from a case's name or expected fields, and it is not a shipping interface.
//! Ingest only: cards and make reports are read by S2/S3, which this build lacks.

use dtapp::messages::{choose, Choice};
use dtapp::report::{read, Reading, Tool};
use serde_json::{json, Value};
use std::io::{BufRead, Write};

fn main() {
    let out = std::io::stdout();
    let mut out = out.lock();
    for line in std::io::stdin().lock().lines() {
        let c: Value = serde_json::from_str(&line.expect("stdin")).expect("case JSON");
        assert_eq!(c["tool"], "ingest", "this build reads ingest reports only");
        let hex = c["raw_hex"].as_str().unwrap();
        let raw: Vec<u8> = (0..hex.len()).step_by(2).map(|i| u8::from_str_radix(&hex[i..i + 2], 16).unwrap()).collect();
        let exit = c["exit"].as_i64().unwrap() as i32;
        let folders = c["folders"].as_array().unwrap().len();
        let r = read(&raw, Tool::Ingest, c["nonce"].as_str().unwrap(), c["version"].as_str().unwrap(), exit, folders);
        let message = match choose(exit, &r, c["pair"].as_bool().unwrap()) {
            Choice::Success => json!(["success", null]),
            Choice::Generic => json!(["generic", null]),
            Choice::Overage(secs) => json!(["overage", secs]),
            Choice::Protected(s) => json!(["protected", s.text()]),
            Choice::FolderNonMusic(s) => json!(["folder-nonmusic", s.text()]),
            Choice::Unusable(s) => json!(["unusable", s.text()]),
        };
        let valid = matches!(r, Reading::Usable { .. });
        writeln!(out, "{}", json!({"valid": valid, "message": message})).unwrap();
    }
}
