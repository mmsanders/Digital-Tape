//! APP-1A §1 report reading: what a child's report may tell the app, and when it must be
//! ignored. The exit code is primary. A report only ever narrows a nonzero exit to an
//! ID-specific message; it never turns a failure into success and never authorizes
//! anything. Every rule that makes a report unusable falls back to the exit alone.

use serde::de::{self, Deserialize, Deserializer, MapAccess, SeqAccess, Visitor};
use serde_json::{Map, Value};
use unicode_normalization::is_nfc;

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
    /// Two neighbouring source logical paths, as (ordinal, name) pairs.
    Boundary((usize, String), (usize, String)),
}

impl Subject {
    /// The subject exactly as the report wrote it (None for null or a boundary).
    pub fn text(&self) -> Option<String> {
        match self {
            Subject::Source { ordinal, name } => Some(format!("{ordinal}/{name}")),
            Subject::Folder(i) => Some(i.to_string()),
            Subject::None | Subject::Boundary(..) => None,
        }
    }
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

/// A decimal ordinal string naming one of the `folders` dropped folders.
fn ordinal_str(s: &str, folders: usize) -> Option<usize> {
    if s.is_empty() || !s.bytes().all(|c| c.is_ascii_digit()) || (s.len() > 1 && s.starts_with('0')) {
        return None;
    }
    s.parse().ok().filter(|&i| i < folders)
}

fn ordinal(v: &Value, folders: usize) -> Option<usize> {
    ordinal_str(v.as_str()?, folders)
}

/// An INGEST logical path `ordinal/NFC_name`: a dropped folder's ordinal and one plain
/// NFC basename (no separator, no `.`/`..`, no NUL).
fn logical(v: &Value, folders: usize) -> Option<(usize, String)> {
    let (o, name) = v.as_str()?.split_once('/')?;
    let o = ordinal_str(o, folders)?;
    if name.is_empty() || name == "." || name == ".." || name.contains(['/', '\\', '\0']) || !is_nfc(name) {
        return None;
    }
    Some((o, name.to_string()))
}

fn boundary(v: &Value, folders: usize) -> Option<Subject> {
    let a = v.as_array().filter(|a| a.len() == 2)?;
    Some(Subject::Boundary(logical(&a[0], folders)?, logical(&a[1], folders)?))
}

/// No insignificant whitespace: none outside string literals (APP-1A §1).
fn compact(line: &str) -> bool {
    let (mut quoted, mut escaped) = (false, false);
    for c in line.chars() {
        if quoted {
            if escaped {
                escaped = false;
            } else if c == '\\' {
                escaped = true;
            } else if c == '"' {
                quoted = false;
            }
        } else if c == '"' {
            quoted = true;
        } else if matches!(c, ' ' | '\t' | '\r' | '\n') {
            return false;
        }
    }
    true
}

/// A JSON value walked only to refuse a repeated key in any object (serde_json's map
/// would silently keep the last).
struct Unique;

impl<'de> Deserialize<'de> for Unique {
    fn deserialize<D: Deserializer<'de>>(d: D) -> Result<Self, D::Error> {
        d.deserialize_any(UniqueVisitor)
    }
}

struct UniqueVisitor;

impl<'de> Visitor<'de> for UniqueVisitor {
    type Value = Unique;
    fn expecting(&self, f: &mut std::fmt::Formatter) -> std::fmt::Result {
        f.write_str("a JSON value")
    }
    fn visit_bool<E>(self, _: bool) -> Result<Unique, E> {
        Ok(Unique)
    }
    fn visit_i64<E>(self, _: i64) -> Result<Unique, E> {
        Ok(Unique)
    }
    fn visit_u64<E>(self, _: u64) -> Result<Unique, E> {
        Ok(Unique)
    }
    fn visit_f64<E>(self, _: f64) -> Result<Unique, E> {
        Ok(Unique)
    }
    fn visit_str<E>(self, _: &str) -> Result<Unique, E> {
        Ok(Unique)
    }
    fn visit_unit<E>(self) -> Result<Unique, E> {
        Ok(Unique)
    }
    fn visit_seq<A: SeqAccess<'de>>(self, mut a: A) -> Result<Unique, A::Error> {
        while a.next_element::<Unique>()?.is_some() {}
        Ok(Unique)
    }
    fn visit_map<A: MapAccess<'de>>(self, mut a: A) -> Result<Unique, A::Error> {
        let mut seen = std::collections::HashSet::new();
        while let Some(k) = a.next_key::<String>()? {
            if !seen.insert(k) {
                return Err(de::Error::custom("duplicate key"));
            }
            a.next_value::<Unique>()?;
        }
        Ok(Unique)
    }
}

/// Validate an ingest refusal's subject and payload against APP-1A §2.
fn ingest_refusal(id: &str, m: &Map<String, Value>, folders: usize) -> Option<Refusal> {
    let subj = m.get("subject")?;
    let subject = if SOURCE_SUBJECT.contains(&id) {
        let (o, n) = logical(subj, folders)?;
        Subject::Source { ordinal: o, name: n }
    } else if FOLDER_SUBJECT.contains(&id) {
        Subject::Folder(ordinal(subj, folders)?)
    } else if id == "JOIN_PEAK" {
        // Two different neighbouring sources.
        boundary(subj, folders).filter(|b| matches!(b, Subject::Boundary(x, y) if x != y))?
    } else if id == "JOINED_PEAK" && !subj.is_null() {
        boundary(subj, folders)?
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
            let j = ordinal(m.get("same_as")?, folders)?;
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

const ENGINE_ERRORS: &[&str] = &[
    "IO", "BAD_MAGIC", "CRC", "VERSION", "UNSUPPORTED_STATE", "GEOMETRY", "INCOMPLETE",
    "INCONSISTENT", "NO_VALID_INDEX", "READ_ONLY", "CARTRIDGE_FULL", "INDEX_FULL",
    "DEST_TOO_SMALL", "SEQUENCE_EXHAUSTED", "FAULTED", "NOT_MOUNTED", "BUSY", "UNDERRUN", "INVALID_ARG",
];

fn engine_error(v: &Value) -> bool {
    v.as_str().and_then(|s| s.strip_prefix("TAPE_ERR_")).is_some_and(|s| ENGINE_ERRORS.contains(&s))
}

/// WP14 emitted finding order, including side and per-side frame order. This reads
/// structured diagnostics only; it does not inspect a card or interpret its layout.
fn valid_findings(v: &Value) -> Option<()> {
    let fs = v.as_array().filter(|a| !a.is_empty())?;
    let order = ["MBR_LAYOUT", "PARTITION_TYPE", "PARTITION_TRUNCATED", "MOUNT", "NEEDS_REPAIR", "SIDE_B_DEGRADED", "READ_ERROR"];
    let (mut rank, mut mount_side, mut read_side) = (0, 0, 0);
    let mut singleton = [false; 7];
    let mut mounts = [false; 2];
    let mut frames: [Option<u64>; 2] = [None, None];
    for f in fs {
        let m = f.as_object()?;
        let n = m.get("f")?.as_str()?;
        let r = order.iter().position(|s| *s == n)?;
        if r < rank { return None; }
        rank = r;
        match n {
            "MOUNT" | "READ_ERROR" => {
                let side = match m.get("side")?.as_str()? { "A" => 0, "B" => 1, _ => return None };
                if n == "MOUNT" {
                    if keys(m) != ["f", "side", "result"] || !engine_error(m.get("result")?) || mounts[side] || side < mount_side { return None; }
                    mounts[side] = true; mount_side = side;
                } else {
                    if keys(m) != ["f", "side", "frame"] || mounts[side] || side < read_side { return None; }
                    let frame = counter(m.get("frame"))?;
                    if frames[side].is_some_and(|old| frame <= old) { return None; }
                    frames[side] = Some(frame); read_side = side;
                }
            }
            _ => {
                if keys(m) != ["f"] || singleton[r] { return None; }
                singleton[r] = true;
            }
        }
    }
    Some(())
}

fn tapectl_refusal(id: &str, m: &Map<String, Value>, tool: Tool, exit: i32) -> Option<Refusal> {
    if !m.get("subject")?.is_null() { return None; }
    let required: &[&str] = match (tool, exit, id) {
        (Tool::Cards, 2, "USAGE") => &[],
        (Tool::Cards, 1, "CARDS_ENUM_UNAVAILABLE") => &["os_error"],
        (Tool::Make, 2, "USAGE" | "LABEL_INVALID" | "LENGTH_INVALID" | "NOT_PROVISIONED" | "P2_TOO_LARGE") => &[],
        (Tool::Make, 2, "WAV_INVALID") => {
            if !["open", "riff", "fmt", "pcm", "channels", "rate", "bits", "align", "data", "chunk"].contains(&m.get("reason")?.as_str()?) { return None; }
            &["reason"]
        }
        (Tool::Make, 2, "DEVICE_OPEN_FAILED") => &["os_error"],
        (Tool::Make, 2, "TOO_LONG") => {
            let (t, c, e) = (counter(m.get("total_frames"))?, counter(m.get("capacity_frames"))?, counter(m.get("excess_frames"))?);
            if e == 0 || t.checked_sub(c)? != e { return None; }
            &["total_frames", "capacity_frames", "excess_frames"]
        }
        (Tool::Make, 2, "WAV_TRUNCATED") => {
            if m.get("phase")?.as_str()? != "load" { return None; }
            &["phase"]
        }
        (Tool::Make, 3, "REFUSE_NOT_WHOLE_DEVICE" | "REFUSE_NOT_REMOVABLE" | "REFUSE_TOO_LARGE" | "REFUSE_SYSTEM_DISK" | "REFUSE_ERASE_NOT_CONFIRMED") => &[],
        (Tool::Make, 3, "REFUSE_FOREIGN_MOUNT") => {
            if let Some(v) = m.get("unmount_failed") { if v != &Value::Bool(true) { return None; } }
            &[]
        }
        (Tool::Make, 1, "ENGINE") => {
            if !["provision", "capacity", "load", "commit"].contains(&m.get("phase")?.as_str()?) || !engine_error(m.get("result")?) { return None; }
            &["phase", "result"]
        }
        (Tool::Make, 1, "IO") => {
            let phase = m.get("phase")?.as_str()?;
            let op = m.get("op")?.as_str()?;
            if !(phase == "provision" && ["entropy", "read_lba0", "clear_lba0", "write_p1", "build_mbr", "write_mbr"].contains(&op) || phase == "verify" && op == "read_lba0") { return None; }
            &["phase", "op"]
        }
        (Tool::Make, 1, "VERIFY_FINDINGS") => { valid_findings(m.get("findings")?)?; &["findings"] }
        (Tool::Make, 1, "CARD_CHANGED" | "HOST_QUERY_FAILED") => {
            if !["safety", "provision", "load", "commit", "verify"].contains(&m.get("phase")?.as_str()?) { return None; }
            if id == "HOST_QUERY_FAILED" {
                if m.get("op")?.as_str()? != "media_query" { return None; }
                &["phase", "op", "os_error"]
            } else { &["phase", "os_error"] }
        }
        _ => return None,
    };
    let mut want = vec!["t", "id", "subject"];
    want.extend_from_slice(required);
    if id == "REFUSE_FOREIGN_MOUNT" && m.contains_key("unmount_failed") { want.push("unmount_failed"); }
    if keys(m) != want || (required.contains(&"os_error") && !m.get("os_error")?.is_string()) { return None; }
    let mut payload = Map::new();
    for k in want.into_iter().skip(3) { payload.insert(k.to_owned(), m[k].clone()); }
    Some(Refusal { id: id.to_owned(), subject: Subject::None, payload })
}

/// Read `bytes` as the report of `tool`, launched with `nonce` over `folders` dropped
/// folders, whose pinned version string is `version`, and which actually exited with
/// `exit`.
pub fn read(bytes: &[u8], tool: Tool, nonce: &str, version: &str, exit: i32, folders: usize) -> Reading {
    use Reading::Unusable as U;
    if nonce.len() != 32 || !nonce.bytes().all(|c| c.is_ascii_digit() || (b'a'..=b'f').contains(&c)) {
        return U("invalid invocation nonce");
    }
    // An unterminated final line is ignored; the rest is judged.
    let Some(end) = bytes.iter().rposition(|&b| b == b'\n') else { return U("empty or unterminated") };
    let Ok(text) = std::str::from_utf8(&bytes[..end]) else { return U("not UTF-8") };
    let mut recs = Vec::new();
    for l in text.split('\n') {
        if !compact(l) {
            return U("insignificant whitespace");
        }
        if serde_json::from_str::<Unique>(l).is_err() {
            return U("malformed record or repeated key");
        }
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
                let Some(t) = m["text"].as_str().filter(|s| !s.contains('\n')) else { return U("stderr text") };
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
                        match ingest_refusal(id, m, folders) {
                            Some(r) => r,
                            None => return U("invalid subject or payload"),
                        }
                    }
                    Tool::Cards | Tool::Make => match tapectl_refusal(id, m, tool, exit) {
                        Some(r) => r,
                        None => return U("invalid tapectl ID, subject or payload"),
                    },
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
        read(format!("{}{body}", start()).as_bytes(), Tool::Ingest, N, V, exit, 3)
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
        assert!(matches!(read(stale.as_bytes(), Tool::Ingest, N, V, 0, 3), Reading::Unusable(_)));
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

    fn refuses(id: &str, rest: &str) -> bool {
        let r = rd(&format!("{{\"t\":\"refusal\",\"id\":\"{id}\",{rest}}}\n{{\"t\":\"end\",\"exit\":2}}\n"), 2);
        matches!(r, Reading::Usable { refusal: Some(_), .. })
    }

    #[test]
    fn issued_subject_grammar() {
        // JOINED_PEAK: null or a boundary pair; JOIN_PEAK: two different sources.
        assert!(refuses("JOINED_PEAK", "\"subject\":null,\"dbtp\":\"-0.100000\""));
        assert!(refuses("JOINED_PEAK", "\"subject\":[\"0/a.wav\",\"1/b.wav\"],\"dbtp\":\"-0.100000\""));
        assert!(!refuses("JOIN_PEAK", "\"subject\":[\"0/a.wav\",\"0/a.wav\"],\"dbtp\":\"-0.100000\""));
        // Ordinals name a dropped folder (three here).
        assert!(refuses("FOLDER_EMPTY", "\"subject\":\"2\""));
        assert!(!refuses("FOLDER_EMPTY", "\"subject\":\"3\""));
        assert!(!refuses("SOURCE_CORRUPT", "\"subject\":\"3/song.wav\""));
        // A plain NFC basename only.
        for bad in ["0/../song.wav", "0/..", "0/.", "0/a\\\\b.wav", "0/a\\u0000b", "0/e\u{301}.wav"] {
            assert!(!refuses("SOURCE_CORRUPT", &format!("\"subject\":\"{bad}\"")), "{bad}");
        }
        assert!(refuses("SOURCE_CORRUPT", "\"subject\":\"0/\u{e9}.wav\""));
    }

    #[test]
    fn repeated_keys_and_whitespace_are_unusable() {
        assert!(!refuses("FOLDER_EMPTY", "\"subject\":\"0\",\"subject\":\"1\""));
        let spaced = rd("{\"t\": \"end\",\"exit\":0}\n", 0);
        assert!(matches!(spaced, Reading::Unusable(_)));
        let in_string = rd("{\"t\":\"refusal\",\"id\":\"SOURCE_CORRUPT\",\"subject\":\"0/My Song.wav\"}\n{\"t\":\"end\",\"exit\":2}\n", 2);
        assert!(matches!(in_string, Reading::Usable { refusal: Some(_), .. }));
    }
}
