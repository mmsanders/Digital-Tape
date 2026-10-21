//! Test transport only. The production modules are compiled directly in place.
#[path = "../../src/report.rs"]
mod report;
#[path = "../../src/messages.rs"]
mod messages;
use serde_json::{json, Value};
use std::io::{self, BufRead};

fn main() {
    for line in io::stdin().lock().lines() {
        let c: Value = serde_json::from_str(&line.unwrap()).unwrap();
        let h = c["raw_hex"].as_str().unwrap();
        let raw: Vec<u8> = (0..h.len()).step_by(2).map(|i| u8::from_str_radix(&h[i..i+2], 16).unwrap()).collect();
        let tool = match c["tool"].as_str().unwrap() { "ingest" => report::Tool::Ingest, "tapectl cards" => report::Tool::Cards, "tapectl make" => report::Tool::Make, _ => panic!("unknown tool") };
        let exit = c["exit"].as_i64().unwrap() as i32;
        let folders = c["folders"].as_array().unwrap();
        let r = report::read(&raw, tool, c["nonce"].as_str().unwrap(), c["version"].as_str().unwrap(), exit, folders.len());
        let names = |i: usize| folders.get(i).and_then(Value::as_str).map(str::to_owned);
        // Category is serialized from the actual selector; no expected fields or
        // fixture labels are read. Rendered copy is returned from the actual mapper.
        let (category, fact, rendered): (&str, Value, Option<String>) = match tool {
            report::Tool::Ingest => {
                use messages::Choice::*;
                let choice = messages::choose(exit, &r, c["pair"].as_bool().unwrap());
                let (cat, fact) = match choice {
                    Success => ("success", Value::Null), Generic => ("generic", Value::Null),
                    Overage(s) => ("overage", json!(s)),
                    Protected(s) => ("protected", json!(s.text())),
                    FolderNonMusic(s) => ("folder-nonmusic", json!(s.text())),
                    Unusable(s) => ("unusable", json!(s.text())),
                };
                (cat, fact, messages::ingest(exit, &r, c["pair"].as_bool().unwrap(), &names))
            }
            report::Tool::Make => {
                use messages::MakeChoice::*;
                let cat = match messages::choose_make(exit, &r) {
                    Success => "success", Generic => "make-generic", CardSmall => "card-small",
                    CardInterrupted => "card-interrupted", VerifyFinding => "verify-finding",
                    MusicChanged => "music-changed", CardRefused => "card-refused",
                };
                (cat, Value::Null, messages::make(exit, &r))
            }
            report::Tool::Cards => (if exit == 0 { "success" } else { "generic" }, Value::Null, messages::cards(exit)),
        };
        println!("{}", json!({"valid":matches!(r, report::Reading::Usable { .. }),"message":[category,fact],"rendered":rendered,"reading":format!("{r:?}")}));
    }
}
