//! APP-1 §6 / APP-1A §2–§3 messages as data. A child-origin message comes from the real
//! exit plus a usable report ID; an app-origin message from a named app event. Nothing
//! here reads stderr text.

use crate::report::{Reading, Refusal, Subject};

/// Pure APP-1A make selector. Report diagnostics never select an outcome.
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub enum MakeChoice { Success, Generic, CardSmall, CardInterrupted, VerifyFinding, MusicChanged, CardRefused }

pub fn choose_make(exit: i32, reading: &Reading) -> MakeChoice {
    use MakeChoice::*;
    if exit == 0 { return Success; }
    let Reading::Usable { refusal: Some(r), .. } = reading else { return Generic; };
    let text = |k: &str| r.payload.get(k).and_then(|v| v.as_str());
    match r.id.as_str() {
        "TOO_LONG" => CardSmall,
        "ENGINE" if text("phase") == Some("provision") && text("result") == Some("TAPE_ERR_GEOMETRY") => CardSmall,
        "CARD_CHANGED" | "HOST_QUERY_FAILED" | "DEVICE_OPEN_FAILED" => CardInterrupted,
        "IO" if !matches!(text("op"), Some("entropy" | "build_mbr")) => CardInterrupted,
        "ENGINE" if text("result") == Some("TAPE_ERR_IO") => CardInterrupted,
        "VERIFY_FINDINGS" => VerifyFinding,
        "WAV_TRUNCATED" => MusicChanged,
        _ if exit == 3 => CardRefused,
        _ => Generic,
    }
}

pub fn make(exit: i32, reading: &Reading) -> Option<String> {
    use MakeChoice::*;
    Some(match choose_make(exit, reading) {
        Success => return None,
        Generic => "The cartridge wasn't finished. Start over and try again.",
        CardSmall => "This card is too small. Use a bigger card.",
        CardInterrupted => "The card was taken out before it was finished. Put it back in and press Make cartridge again.",
        VerifyFinding => "Something went wrong writing this card. Press Make cartridge to try again.",
        MusicChanged => "The music file changed while the cartridge was being made. Start over and drop the folder again.",
        CardRefused => "This card can't be used right now. Check the card and try again.",
    }.into())
}

/// Discovery failures use the generic child failure copy. Discovery is a hint;
/// parsing it provides no authorization to open a device.
pub fn cards(exit: i32) -> Option<String> {
    if exit == 0 { None } else { Some(GENERIC_INGEST.into()) }
}

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

/// Which ingest message applies (APP-1A §3), before any name is filled in. Exit 0 is
/// success only with the published pair; an unusable report or an ID without its own
/// row is the generic failure.
#[derive(Debug, Clone, PartialEq, Eq)]
pub enum Choice {
    Success,
    Generic,
    /// Excess in whole seconds, rounded up.
    Overage(u64),
    Protected(Subject),
    FolderNonMusic(Subject),
    Unusable(Subject),
}

pub fn choose(exit: i32, reading: &Reading, pair: bool) -> Choice {
    if exit == 0 {
        return if pair { Choice::Success } else { Choice::Generic };
    }
    let Reading::Usable { refusal: Some(r), .. } = reading else { return Choice::Generic };
    let s = r.subject.clone();
    match r.id.as_str() {
        "INGEST_TOO_LONG" => match r.payload.get("excess_frames").and_then(|v| v.as_u64()) {
            Some(e) => Choice::Overage(e.div_ceil(44100)),
            None => Choice::Generic,
        },
        "SOURCE_PROTECTED" => Choice::Protected(s),
        "SOURCE_NOT_AUDIO" | "ENTRY_NOT_REGULAR" | "ENTRY_NESTED_FOLDER" | "ENTRY_SYMLINK" | "FOLDER_SYMLINK" | "FOLDER_EMPTY" => {
            Choice::FolderNonMusic(s)
        }
        "SOURCE_CORRUPT" | "SOURCE_OUTSIDE_INGEST1" | "SOURCE_TRIM_UNSUPPORTED" | "SOURCE_LEVEL" | "SOURCE_NON_FINITE"
        | "IO_SOURCE" | "SOURCE_TOO_SHORT" | "SOURCE_CHANGED" | "ENTRY_NAME_INVALID" | "FOLDER_NAME_COLLISION"
        | "FOLDER_NAME_NOT_UNICODE" => Choice::Unusable(s),
        _ => Choice::Generic,
    }
}

/// The actual ingest result sentence. Exit 0 is success only with the published
/// pair; a missing pair uses the same generic failure selector and display.
/// `folder_name(i)` is the dropped folder's own name for ordinal i; the app never
/// shows full paths.
pub fn ingest(exit: i32, reading: &Reading, pair: bool, folder_name: &dyn Fn(usize) -> Option<String>) -> Option<String> {
    render(&choose(exit, reading, pair), folder_name)
}

fn render(c: &Choice, folder_name: &dyn Fn(usize) -> Option<String>) -> Option<String> {
    let file = |s: &Subject| match s {
        Subject::Source { name, .. } => Some(name.clone()),
        _ => None,
    };
    let folder = |s: &Subject| match s {
        Subject::Source { ordinal, .. } | Subject::Folder(ordinal) => folder_name(*ordinal),
        _ => None,
    };
    Some(match c {
        Choice::Success => return None,
        Choice::Generic => GENERIC_INGEST.into(),
        Choice::Overage(secs) => format!(
            "This music is {} too long for a 60-minute cartridge. Take some songs out and drop the folder again.",
            too_long(secs * 44100)
        ),
        Choice::Protected(s) => format!("\"{}\" is copy-protected, so it can't go on a cartridge. Take it out of the folder.", file(s)?),
        Choice::FolderNonMusic(s) => {
            format!("The folder \"{}\" has something in it that isn't music. Use a folder with only songs in it.", folder(s)?)
        }
        Choice::Unusable(s @ Subject::Source { .. }) => format!("\"{}\" can't be used. Take it out of the folder.", file(s)?),
        Choice::Unusable(s) => format!("\"{}\" can't be used. Take it out of the folder.", folder(s)?),
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
        let m = ingest(2, &refusal("INGEST_TOO_LONG", Subject::None, json!({"excess_frames": 1})), false, &names).unwrap();
        assert_eq!(m, "This music is 1 s too long for a 60-minute cartridge. Take some songs out and drop the folder again.");
    }

    #[test]
    fn rows_name_file_or_folder_never_paths() {
        let s = Subject::Source { ordinal: 1, name: "Song 3.m4a".into() };
        assert_eq!(
            ingest(2, &refusal("SOURCE_PROTECTED", s.clone(), json!({})), false, &names).unwrap(),
            "\"Song 3.m4a\" is copy-protected, so it can't go on a cartridge. Take it out of the folder."
        );
        assert_eq!(
            ingest(2, &refusal("SOURCE_NOT_AUDIO", s, json!({})), false, &names).unwrap(),
            "The folder \"Bedtime\" has something in it that isn't music. Use a folder with only songs in it."
        );
        let b = Subject::Boundary((0, "a.wav".into()), (1, "b.wav".into()));
        assert_eq!(ingest(2, &refusal("JOIN_PEAK", b, json!({})), false, &names).unwrap(), GENERIC_INGEST);
        assert_eq!(ingest(1, &Reading::Unusable("x"), true, &names).unwrap(), GENERIC_INGEST);
        assert_eq!(ingest(0, &Reading::Unusable("x"), true, &names), None);
    }
}
