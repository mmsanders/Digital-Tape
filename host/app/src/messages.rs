//! APP-1 §6 / APP-1A §2–§3 messages as data. A child-origin message comes from the real
//! exit plus a usable report ID; an app-origin message from a named app event. Nothing
//! here reads stderr text.

use crate::report::{Reading, Refusal, Subject};

/// The four APP-1 app-origin events (P2V15-004).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum AppEvent {
    DropNotFolder,
    SpawnFailed,
    ElevationDeclined,
    CardRecheckMismatch,
}

pub fn app_event(e: AppEvent) -> String {
    match e {
        AppEvent::DropNotFolder => "Drop a folder of music, not single songs.".into(),
        AppEvent::SpawnFailed => GENERIC_INGEST.into(),
        AppEvent::ElevationDeclined => {
            "The computer said no, so the card wasn't changed. Press Make cartridge to try again.".into()
        }
        // Back to Ready with the card line (§2); the caller shows that line.
        AppEvent::CardRecheckMismatch => String::new(),
    }
}

pub const GENERIC_INGEST: &str = "Something went wrong. Nothing else on your computer was changed.";

/// WP-14 A7 overage phrasing from exact frames: ceil(excess / 44100) seconds as
/// "M min S s", omitting a zero part, "S s" under a minute.
pub fn too_long(excess_frames: u64) -> String {
    let secs = excess_frames.div_ceil(44100);
    let (m, s) = (secs / 60, secs % 60);
    match (m, s) {
        (0, s) => format!("{s} s"),
        (m, 0) => format!("{m} min"),
        (m, s) => format!("{m} min {s} s"),
    }
}

/// The ingest message for an actual exit and its report reading. `folder_name(i)` is
/// the dropped folder's own name for ordinal i; the app never shows full paths.
pub fn ingest(exit: i32, reading: &Reading, folder_name: &dyn Fn(usize) -> Option<String>) -> Option<String> {
    if exit == 0 {
        return None;
    }
    let Reading::Usable { refusal: Some(r), .. } = reading else { return Some(GENERIC_INGEST.into()) };
    Some(ingest_refusal(r, folder_name).unwrap_or_else(|| GENERIC_INGEST.into()))
}

fn ingest_refusal(r: &Refusal, folder_name: &dyn Fn(usize) -> Option<String>) -> Option<String> {
    let file = || match &r.subject {
        Subject::Source { name, .. } => Some(name.clone()),
        _ => None,
    };
    let folder = || match &r.subject {
        Subject::Source { ordinal, .. } | Subject::Folder(ordinal) => folder_name(*ordinal),
        _ => None,
    };
    let id = r.id.as_str();
    Some(match id {
        "INGEST_TOO_LONG" => format!(
            "This music is {} too long for a 60-minute cartridge. Take some songs out and drop the folder again.",
            too_long(r.payload["excess_frames"].as_u64()?)
        ),
        "SOURCE_PROTECTED" => format!("\"{}\" is copy-protected, so it can't go on a cartridge. Take it out of the folder.", file()?),
        "SOURCE_CORRUPT" | "SOURCE_OUTSIDE_INGEST1" | "SOURCE_TRIM_UNSUPPORTED" | "SOURCE_LEVEL" | "SOURCE_NON_FINITE"
        | "IO_SOURCE" => format!("\"{}\" can't be used. Take it out of the folder.", file()?),
        "SOURCE_NOT_AUDIO" | "ENTRY_NOT_REGULAR" | "ENTRY_NESTED_FOLDER" | "ENTRY_SYMLINK" | "FOLDER_SYMLINK" | "FOLDER_EMPTY" => {
            format!("The folder \"{}\" has something in it that isn't music. Use a folder with only songs in it.", folder()?)
        }
        "SOURCE_TOO_SHORT" | "SOURCE_CHANGED" | "ENTRY_NAME_INVALID" => {
            format!("\"{}\" can't be used. Take it out of the folder.", file()?)
        }
        "FOLDER_NAME_COLLISION" | "FOLDER_NAME_NOT_UNICODE" => {
            format!("\"{}\" can't be used. Take it out of the folder.", folder()?)
        }
        _ => return None,
    })
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn refusal(id: &str, subject: Subject, payload: serde_json::Value) -> Reading {
        Reading::Usable {
            refusal: Some(Refusal { id: id.into(), subject, payload: payload.as_object().cloned().unwrap_or_default() }),
            stderr: vec![],
            last_progress: None,
        }
    }
    fn names(i: usize) -> Option<String> {
        ["Road Trip", "Bedtime"].get(i).map(|s| s.to_string())
    }

    #[test]
    fn overage_phrasing() {
        assert_eq!(too_long(1), "1 s");
        assert_eq!(too_long(8_467_200), "3 min 12 s");
        assert_eq!(too_long(44100 * 120), "2 min");
        let m = ingest(2, &refusal("INGEST_TOO_LONG", Subject::None, json!({"excess_frames": 1})), &names).unwrap();
        assert_eq!(m, "This music is 1 s too long for a 60-minute cartridge. Take some songs out and drop the folder again.");
    }

    #[test]
    fn rows_name_file_or_folder_never_paths() {
        let s = Subject::Source { ordinal: 1, name: "Song 3.m4a".into() };
        assert_eq!(
            ingest(2, &refusal("SOURCE_PROTECTED", s.clone(), json!({})), &names).unwrap(),
            "\"Song 3.m4a\" is copy-protected, so it can't go on a cartridge. Take it out of the folder."
        );
        assert_eq!(
            ingest(2, &refusal("SOURCE_NOT_AUDIO", s, json!({})), &names).unwrap(),
            "The folder \"Bedtime\" has something in it that isn't music. Use a folder with only songs in it."
        );
        assert_eq!(ingest(2, &refusal("JOIN_PEAK", Subject::Boundary(0, 1), json!({})), &names).unwrap(), GENERIC_INGEST);
        assert_eq!(ingest(1, &Reading::Unusable("x"), &names).unwrap(), GENERIC_INGEST);
        assert_eq!(ingest(0, &Reading::Unusable("x"), &names), None);
    }
}
