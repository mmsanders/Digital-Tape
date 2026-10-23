//! The window's state (APP-1 §2) as plain data, so every transition is testable without
//! a window. This slice (S4) has no card discovery or make: the card line says so and
//! Make cartridge is never enabled. Nothing here pretends otherwise.

use crate::drops::{self, Drop};
use crate::ingest_job::{Outcome, CAPACITY_FRAMES};
use crate::messages::{self, AppEvent};
use crate::report::{Reading, Refusal};
use serde::Serialize;
use std::path::PathBuf;

pub const CARD_LINE_UNBUILT: &str = "Finding cards isn't part of this build yet.";

#[derive(Debug, Clone, PartialEq)]
enum Check {
    Idle,
    Running,
    /// Exact frames from the published manifest.
    Fits(u64),
    /// INGEST_TOO_LONG's exact frames.
    TooLong { total: u64, excess: u64 },
    Problem(String),
}

#[derive(Debug, Clone, Serialize, PartialEq)]
pub struct View {
    /// "empty" | "ready" | "problem" ("making" and "done" arrive with S3).
    pub view: &'static str,
    pub checking: bool,
    /// 0..=1 of a 60-minute cartridge; None while unknown (indeterminate).
    pub bar: Option<f64>,
    pub too_long: bool,
    /// The one sentence shown, if any.
    pub message: Option<String>,
    pub label: String,
    pub card_line: &'static str,
    pub make_enabled: bool,
    pub details_available: bool,
}

#[derive(Debug, Default)]
pub struct App {
    pub folders: Vec<PathBuf>,
    pub label: String,
    check: Option<Check>,
    notice: Option<String>,
    pub details: String,
}

/// What the shell must do after a drop.
#[derive(Debug, PartialEq, Eq)]
pub enum Next {
    /// Cancel any running ingest, delete its DEST, run ingest over `App::folders`.
    RunIngest,
    Nothing,
}

impl App {
    pub fn view(&self) -> View {
        let check = self.check.clone().unwrap_or(Check::Idle);
        let (view, bar, too_long, message) = match &check {
            Check::Problem(m) => ("problem", None, false, Some(m.clone())),
            Check::TooLong { total, excess } => {
                let _ = total;
                ("ready", Some(1.0), true, Some(too_long_sentence(*excess)))
            }
            Check::Fits(t) => ("ready", Some((*t as f64 / CAPACITY_FRAMES as f64).min(1.0)), false, None),
            Check::Running => (if self.folders.is_empty() { "empty" } else { "ready" }, None, false, None),
            Check::Idle => ("empty", Some(0.0), false, None),
        };
        View {
            view,
            checking: check == Check::Running,
            bar,
            too_long,
            message: message.or_else(|| self.notice.clone()),
            label: self.label.clone(),
            card_line: CARD_LINE_UNBUILT,
            make_enabled: false,
            details_available: !self.details.is_empty(),
        }
    }

    /// A drop gesture. A file or a mix adds nothing (DROP_NOT_FOLDER, zero child calls).
    pub fn dropped(&mut self, paths: &[PathBuf]) -> Next {
        if matches!(self.check, Some(Check::Problem(_))) {
            return Next::Nothing; // Problem offers Start over only
        }
        match drops::classify(paths, &self.folders) {
            Drop::NotFolder => {
                self.notice = Some(messages::app_event(AppEvent::DropNotFolder));
                Next::Nothing
            }
            Drop::NoChange => Next::Nothing,
            Drop::Folders(add) => {
                self.notice = None;
                self.folders.extend(add);
                self.check = Some(Check::Running);
                Next::RunIngest
            }
        }
    }

    /// The child could not be launched (SPAWN_FAILED).
    pub fn spawn_failed(&mut self, why: &str) {
        self.details = why.to_string();
        self.check = Some(Check::Problem(messages::app_event(AppEvent::SpawnFailed)));
    }

    /// An ingest run finished for the current folder list.
    pub fn finished(&mut self, o: &Outcome) {
        if o.cancelled {
            return;
        }
        self.details = o.stderr.clone();
        let names = |i: usize| self.folders.get(i).map(|p| drops::display_name(p));
        self.check = Some(match (o.exit, &o.reading) {
            (Some(0), _) => match o.total_frames {
                Some(t) => Check::Fits(t),
                None => Check::Problem(messages::GENERIC_INGEST.into()),
            },
            (Some(2), Reading::Usable { refusal: Some(Refusal { id, payload, .. }), .. }) if id == "INGEST_TOO_LONG" => {
                let (Some(t), Some(e)) = (payload["total_frames"].as_u64(), payload["excess_frames"].as_u64()) else {
                    unreachable!("report::read validated the payload")
                };
                Check::TooLong { total: t, excess: e }
            }
            (Some(e), r) => Check::Problem(messages::ingest(e, r, o.total_frames.is_some(), &names).unwrap_or_else(|| messages::GENERIC_INGEST.into())),
            (None, _) => Check::Problem(messages::GENERIC_INGEST.into()),
        });
    }

    /// The label box asks to show `text`; returns whether it was accepted.
    pub fn set_label(&mut self, text: &str) -> bool {
        if crate::label::accept(text) {
            self.label = text.to_string();
            true
        } else {
            false
        }
    }

    pub fn start_over(&mut self) {
        *self = App::default();
    }
}

fn too_long_sentence(excess: u64) -> String {
    format!(
        "This music is {} too long for a 60-minute cartridge. Take some songs out and drop the folder again.",
        messages::too_long(excess)
    )
}

#[cfg(test)]
mod tests {
    use super::*;
    use serde_json::json;

    fn outcome(exit: i32, reading: Reading, total: Option<u64>) -> Outcome {
        Outcome { exit: Some(exit), stderr: "ingest: refused: …".into(), reading, total_frames: total, cancelled: false }
    }

    #[test]
    fn never_offers_make_in_this_slice() {
        let mut a = App::default();
        assert_eq!(a.view().view, "empty");
        a.folders.push("/x".into());
        a.finished(&outcome(0, Reading::Unusable("no report"), Some(CAPACITY_FRAMES / 2)));
        let v = a.view();
        assert_eq!((v.view, v.bar, v.make_enabled), ("ready", Some(0.5), false));
        assert_eq!(v.card_line, CARD_LINE_UNBUILT);
    }

    #[test]
    fn overage_and_generic_paths() {
        let mut a = App::default();
        a.folders.push("/x/Road Trip".into());
        let r = Reading::Usable {
            refusal: Some(Refusal {
                id: "INGEST_TOO_LONG".into(),
                subject: crate::report::Subject::None,
                payload: json!({"total_frames": 167227200u64, "capacity_frames": 158760000u64, "excess_frames": 8467200u64})
                    .as_object()
                    .cloned()
                    .unwrap(),
            }),
            stderr: vec![],
            last_progress: None,
        };
        a.finished(&outcome(2, r, None));
        let v = a.view();
        assert!(v.too_long && v.bar == Some(1.0));
        assert!(v.message.unwrap().contains("3 min 12 s"));
        // exit 0 without a published pair is not success
        a.finished(&outcome(0, Reading::Unusable("x"), None));
        assert_eq!(a.view().message.unwrap(), messages::GENERIC_INGEST);
    }

    #[test]
    fn label_never_truncates() {
        let mut a = App::default();
        assert!(a.set_label("Road Trip"));
        assert!(!a.set_label(&"x".repeat(33)));
        assert_eq!(a.label, "Road Trip");
    }
}
