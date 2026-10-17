//! APP-1A §1 report reading: what a child's report may tell the app, and when it must be
//! ignored. The exit code is primary. A report only ever narrows a nonzero exit to an
//! ID-specific message; it never turns a failure into success and never authorizes
//! anything. Every rule that makes a report unusable falls back to the exit alone.

use serde_json::{Map, Value};

/// The bundled child a report came from.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum Tool {
    Ingest,
    Cards,
    Make,
}

impl Tool {
    pub fn name(self) -> &'static str {
        match self {
            Tool::Ingest => "ingest",
            Tool::Cards => "tapectl cards",
            Tool::Make => "tapectl make",
        }
    }
    fn steps(self) -> &'static [&'static str] {
        match self {
            Tool::Ingest => &["list", "decode", "convert", "write", "publish"],
            Tool::Cards => &["enumerate"],
            Tool::Make => &["safety", "provision", "load", "commit", "verify_a", "verify_b"],
        }
    }
}

/// APP-1A §2 closed ingest IDs by exit.
pub const INGEST_EXIT2: &[&str] = &[
    "INGEST_USAGE", "INGEST_LENGTH_INVALID", "INGEST_TOO_LONG", "INGEST_RIFF_LIMIT", "FOLDER_SYMLINK",
    "FOLDER_UNREADABLE", "FOLDER_NOT_FOLDER", "FOLDER_DUPLICATE", "FOLDER_EMPTY", "FOLDER_NAME_COLLISION",
    "FOLDER_NAME_NOT_UNICODE", "ENTRY_SYMLINK", "ENTRY_NESTED_FOLDER", "ENTRY_NOT_REGULAR", "ENTRY_NAME_INVALID",
    "SOURCE_PROTECTED", "SOURCE_NOT_AUDIO", "SOURCE_TOO_SHORT", "SOURCE_CHANGED", "SOURCE_NON_FINITE",
    "SOURCE_LEVEL", "SOURCE_TRIM_UNSUPPORTED", "SOURCE_OUTSIDE_INGEST1", "SOURCE_CORRUPT", "JOIN_PEAK",
    "JOINED_PEAK", "DEST_EXISTS", "DEST_APPEARED", "DEST_NAME_INVALID",
];
pub const INGEST_EXIT1: &[&str] = &["IO_SOURCE", "IO_FOLDER", "IO_DEST", "IO_MEMORY", "INTERNAL"];

/// IDs whose subject is a source logical path, a folder ordinal, or a boundary pair.
const SOURCE_SUBJECT: &[&str] = &[
    "ENTRY_SYMLINK", "ENTRY_NESTED_FOLDER", "ENTRY_NOT_REGULAR", "ENTRY_NAME_INVALID", "SOURCE_PROTECTED",
    "SOURCE_NOT_AUDIO", "SOURCE_TOO_SHORT", "SOURCE_CHANGED", "SOURCE_NON_FINITE", "SOURCE_LEVEL",
    "SOURCE_TRIM_UNSUPPORTED", "SOURCE_OUTSIDE_INGEST1", "SOURCE_CORRUPT", "IO_SOURCE",
];
const FOLDER_SUBJECT: &[&str] = &[
    "FOLDER_SYMLINK", "FOLDER_UNREADABLE", "FOLDER_NOT_FOLDER", "FOLDER_DUPLICATE", "FOLDER_EMPTY",
    "FOLDER_NAME_COLLISION", "FOLDER_NAME_NOT_UNICODE", "IO_FOLDER",
];

#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Subject {
    None,
    /// `ordinal/NFC_name`, split.
    Source { ordinal: usize, name: String },
    Folder(usize),
    Boundary(usize, usize),
}

#[derive(Debug, Clone, PartialEq)]
pub struct Refusal {
    pub id: String,
    pub subject: Subject,
    pub payload: Map<String, Value>,
}

/// What the app may use from a report.
#[derive(Debug, Clone, PartialEq)]
pub enum Reading {
    /// Well formed and consistent with the actual exit: `refusal` is the terminal ID, if
    /// any; `stderr` holds make's diagnostic lines; `last_progress` the latest counter.
    Usable { refusal: Option<Refusal>, stderr: Vec<String>, last_progress: Option<(String, u64, u64)> },
    /// Use the actual exit and generic failure only. The reason is for Show details.
    Unusable(&'static str),
}

fn keys(m: &Map<String, Value>) -> Vec<&str> {
    m.keys().map(|k| k.as_str()).collect()
}

fn counter(v: Option<&Value>) -> Option<u64> {
    v.and_then(Value::as_u64).filter(|&n| n <= (1u64 << 53) - 1)
}

fn logical(v: &Value) -> Option<(usize, String)> {
    let s = v.as_str()?;
    let (o, name) = s.split_once('/')?;
    if o.is_empty() || !o.bytes().all(|c| c.is_ascii_digit()) || name.is_empty() || (o.len() > 1 && o.starts_with('0')) {
        return None;
    }
    Some((o.parse().ok()?, name.to_string()))
}

fn ordinal(v: &Value) -> Option<usize> {
    let s = v.as_str()?;
    if s.is_empty() || !s.bytes().all(|c| c.is_ascii_digit()) || (s.len() > 1 && s.starts_with('0')) {
        return None;
    }
    s.parse().ok()
}

/// Validate an ingest refusal's subject and payload against APP-1A §2.
fn ingest_refusal(id: &str, m: &Map<String, Value>) -> Option<Refusal> {
    let subj = m.get("subject")?;
    let subject = if SOURCE_SUBJECT.contains(&id) {
        let (o, n) = logical(subj)?;
        Subject::Source { ordinal: o, name: n }
    } else if FOLDER_SUBJECT.contains(&id) {
        Subject::Folder(ordinal(subj)?)
    } else if id == "JOIN_PEAK" {
        let a = subj.as_array().filter(|a| a.len() == 2)?;
        Subject::Boundary(logical(&a[0])?.0, logical(&a[1])?.0)
    } else if subj.is_null() {
        Subject::None
    } else {
        return None;
    };
    let extra: Vec<&str> = keys(m).into_iter().skip(3).collect();
    let want: &[&str] = match id {
        "INGEST_TOO_LONG" => &["total_frames", "capacity_frames", "excess_frames"],
        "FOLDER_DUPLICATE" => &["same_as"],
        "JOIN_PEAK" | "JOINED_PEAK" => &["dbtp"],
        _ => &[],
    };
    if extra != want {
        return None;
    }
    let mut payload = Map::new();
    match id {
        "INGEST_TOO_LONG" => {
            let t = counter(m.get("total_frames"))?;
            let c = counter(m.get("capacity_frames"))?;
            let e = counter(m.get("excess_frames"))?;
            if e < 1 || t.checked_sub(c)? != e {
                return None;
            }
        }
        "FOLDER_DUPLICATE" => {
            let j = ordinal(m.get("same_as")?)?;
            if !matches!(subject, Subject::Folder(i) if j < i) {
                return None;
            }
        }
        "JOIN_PEAK" | "JOINED_PEAK" => {
            let d = m.get("dbtp")?.as_str()?;
            let ok = d.strip_prefix('-').unwrap_or(d).split_once('.').is_some_and(|(a, b)| {
                !a.is_empty() && a.bytes().all(|c| c.is_ascii_digit()) && b.len() == 6 && b.bytes().all(|c| c.is_ascii_digit())
            });
            if !ok {
                return None;
            }
        }
        _ => {}
    }
    for k in want {
        payload.insert((*k).to_string(), m[*k].clone());
    }
    Some(Refusal { id: id.to_string(), subject, payload })
}

/// Read `bytes` as the report of `tool`, launched with `nonce`, whose pinned version
/// string is `version`, and which actually exited with `exit`.
pub fn read(bytes: &[u8], tool: Tool, nonce: &str, version: &str, exit: i32) -> Reading {
    use Reading::Unusable as U;
    // An unterminated final line is ignored; the rest is judged.
    let Some(end) = bytes.iter().rposition(|&b| b == b'\n') else { return U("empty or unterminated") };
    let Ok(text) = std::str::from_utf8(&bytes[..end]) else { return U("not UTF-8") };
    let mut recs = Vec::new();
    for l in text.split('\n') {
        match serde_json::from_str::<Value>(l) {
            Ok(Value::Object(m)) => recs.push(m),
            _ => return U("malformed record"),
        }
    }
    let first = &recs[0];
    if keys(first) != ["t", "tool", "version", "nonce"] || first["t"] != "start" {
        return U("first record is not start");
    }
    if first["tool"] != tool.name() || first["nonce"] != nonce {
        return U("stale or foreign report (tool or nonce)");
    }
    if first["version"] != version {
        return U("version differs from the bundled child");
    }
    let last = recs.last().unwrap();
    if recs.len() < 2 || keys(last) != ["t", "exit"] || last["t"] != "end" {
        return U("missing end");
    }
    if last["exit"].as_i64() != Some(exit as i64) {
        return U("end differs from the actual exit");
    }
    let (mut refusal, mut stderr, mut prog): (Option<Refusal>, Vec<String>, Option<(String, u64, u64)>) = (None, vec![], None);
    let mut seen: Vec<&str> = Vec::new();
    for m in &recs[1..recs.len() - 1] {
        match m.get("t").and_then(Value::as_str) {
            Some("progress") if refusal.is_none() => {
                if keys(m) != ["t", "step", "done", "total"] {
                    return U("progress keys");
                }
                let Some(step) = m["step"].as_str().filter(|s| tool.steps().contains(s)) else { return U("unknown step") };
                let (Some(done), Some(total)) = (counter(m.get("done")), counter(m.get("total"))) else { return U("progress counters") };
                if total > 0 && done > total {
                    return U("done exceeds total");
                }
                let rank = |s: &str| tool.steps().iter().position(|x| *x == s).unwrap();
                match &prog {
                    Some((s, d, t)) if s == step => {
                        if done < *d || (*t != 0 && total != *t) {
                            return U("progress went backwards");
                        }
                    }
                    Some((s, _, _)) if rank(s) > rank(step) || seen.contains(&step) => return U("progress step order"),
                    _ => {}
                }
                if !seen.contains(&step) {
                    seen.push(step);
                }
                prog = Some((step.to_string(), done, total));
            }
            Some("stderr") if tool == Tool::Make => {
                if keys(m) != ["t", "text"] {
                    return U("stderr keys");
                }
                let Some(t) = m["text"].as_str() else { return U("stderr text") };
                stderr.push(t.to_string());
            }
            Some("refusal") if refusal.is_none() => {
                if keys(m).get(..3) != Some(&["t", "id", "subject"][..]) {
                    return U("refusal keys");
                }
                let Some(id) = m["id"].as_str() else { return U("refusal id") };
                let r = match tool {
                    Tool::Ingest => {
                        let closed = match exit {
                            2 => INGEST_EXIT2,
                            1 => INGEST_EXIT1,
                            _ => return U("refusal on an exit with no IDs"),
                        };
                        if !closed.contains(&id) {
                            return U("unknown ID for this exit");
                        }
                        match ingest_refusal(id, m) {
                            Some(r) => r,
                            None => return U("invalid subject or payload"),
                        }
                    }
                    // tapectl cards/make IDs are read by S2/S3, which are not built in this
                    // slice: their refusals cannot yet select a specific message.
                    Tool::Cards | Tool::Make => return U("tapectl IDs are not read by this build"),
                };
                refusal = Some(r);
            }
            _ => return U("unknown or misplaced record"),
        }
    }
    if exit == 0 && refusal.is_some() {
        return U("refusal on success");
    }
    Reading::Usable { refusal, stderr, last_progress: prog }
}

#[cfg(test)]
mod tests {
    use super::*;
    const N: &str = "0123456789abcdef0123456789abcdef";
    const V: &str = "0.1.0 INGEST-1 arithmetic-profile INGEST1-AP4";
    fn start() -> String {
        format!("{{\"t\":\"start\",\"tool\":\"ingest\",\"version\":\"{V}\",\"nonce\":\"{N}\"}}\n")
    }
    fn rd(body: &str, exit: i32) -> Reading {
        read(format!("{}{body}", start()).as_bytes(), Tool::Ingest, N, V, exit)
    }

    #[test]
    fn overage_payload_and_exact_counts() {
        let r = rd("{\"t\":\"refusal\",\"id\":\"INGEST_TOO_LONG\",\"subject\":null,\"total_frames\":158760001,\"capacity_frames\":158760000,\"excess_frames\":1}\n{\"t\":\"end\",\"exit\":2}\n", 2);
        let Reading::Usable { refusal: Some(f), .. } = r else { panic!("{r:?}") };
        assert_eq!(f.id, "INGEST_TOO_LONG");
        assert_eq!(f.payload["excess_frames"], 1);
        // excess inconsistent with total - capacity: unusable
        let r = rd("{\"t\":\"refusal\",\"id\":\"INGEST_TOO_LONG\",\"subject\":null,\"total_frames\":10,\"capacity_frames\":5,\"excess_frames\":4}\n{\"t\":\"end\",\"exit\":2}\n", 2);
        assert!(matches!(r, Reading::Unusable(_)));
    }

    #[test]
    fn stale_malformed_unknown_and_mismatch() {
        let stale = format!("{{\"t\":\"start\",\"tool\":\"ingest\",\"version\":\"{V}\",\"nonce\":\"{}\"}}\n{{\"t\":\"end\",\"exit\":0}}\n", "f".repeat(32));
        assert!(matches!(read(stale.as_bytes(), Tool::Ingest, N, V, 0), Reading::Unusable(_)));
        assert!(matches!(rd("not json\n{\"t\":\"end\",\"exit\":1}\n", 1), Reading::Unusable(_)));
        assert!(matches!(rd("{\"t\":\"refusal\",\"id\":\"FUTURE\",\"subject\":null}\n{\"t\":\"end\",\"exit\":2}\n", 2), Reading::Unusable(_)));
        assert!(matches!(rd("{\"t\":\"end\",\"exit\":1}\n", 0), Reading::Unusable(_)));
        assert!(matches!(rd("{\"t\":\"refusal\",\"id\":\"IO_DEST\",\"subject\":null}\n{\"t\":\"end\",\"exit\":2}\n", 2), Reading::Unusable(_)));
        assert!(matches!(rd("{\"t\":\"refusal\",\"id\":\"SOURCE_CORRUPT\",\"subject\":null}\n{\"t\":\"end\",\"exit\":2}\n", 2), Reading::Unusable(_)));
        // no end (later write failure): exit only
        assert!(matches!(rd("{\"t\":\"progress\",\"step\":\"list\",\"done\":1,\"total\":1}\n", 0), Reading::Unusable(_)));
    }

    #[test]
    fn unterminated_final_line_ignored() {
        let r = rd("{\"t\":\"end\",\"exit\":0}\n{\"t\":\"refusal\",\"id\":\"SOURCE", 0);
        assert!(matches!(r, Reading::Usable { refusal: None, .. }));
    }

    #[test]
    fn subjects_and_progress_rules() {
        let r = rd("{\"t\":\"progress\",\"step\":\"list\",\"done\":1,\"total\":2}\n{\"t\":\"refusal\",\"id\":\"SOURCE_PROTECTED\",\"subject\":\"1/Song 3.m4a\"}\n{\"t\":\"end\",\"exit\":2}\n", 2);
        let Reading::Usable { refusal: Some(f), .. } = r else { panic!() };
        assert_eq!(f.subject, Subject::Source { ordinal: 1, name: "Song 3.m4a".into() });
        let back = rd("{\"t\":\"progress\",\"step\":\"decode\",\"done\":1,\"total\":2}\n{\"t\":\"progress\",\"step\":\"list\",\"done\":1,\"total\":2}\n{\"t\":\"end\",\"exit\":0}\n", 0);
        assert!(matches!(back, Reading::Unusable(_)));
        let dup = rd("{\"t\":\"refusal\",\"id\":\"FOLDER_DUPLICATE\",\"subject\":\"2\",\"same_as\":\"0\"}\n{\"t\":\"end\",\"exit\":2}\n", 2);
        assert!(matches!(dup, Reading::Usable { refusal: Some(_), .. }));
    }
}
