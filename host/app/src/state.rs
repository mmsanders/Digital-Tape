//! The window's state (APP-1 §2) as plain data, so every transition is testable without
//! a window. The card line comes from S2 discovery when this build pins its tapectl;
//! discovery is a hint only and Make cartridge is never enabled (no S3 in this build).

use crate::discovery::{self, Judged};
use crate::drops::{self, Drop};
use crate::ingest_job::{Outcome, CAPACITY_FRAMES};
use crate::messages::{self, AppEvent};
use crate::report::{Reading, Refusal};
use serde::Serialize;
use std::path::PathBuf;

pub const CARD_LINE_UNBUILT: &str = "Finding cards isn't part of this build yet.";

/// Discovery's place in the window: survives Start over, never authorizes Make.
#[derive(Debug, Clone)]
pub struct Cards {
    /// The sentence shown; empty until the first result of a build with discovery.
    pub line: String,
    pub details: String,
    ticket: u64,
    active: Option<u64>,
}

impl Default for Cards {
    fn default() -> Self {
        let line = if crate::children::TAPECTL.sha256.is_some() { String::new() } else { CARD_LINE_UNBUILT.into() };
        Cards { line, details: String::new(), ticket: 0, active: None }
    }
}

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
    /// Exact current accepted manifest/refusal total, never inferred from the bar.
    pub total_frames: Option<u64>,
    pub too_long: bool,
    /// The one sentence shown, if any.
    pub message: Option<String>,
    pub label: String,
    pub card_line: String,
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
    generation: u64,
    active_job: Option<String>,
    pub cards: Cards,
}

/// What the shell must do after a drop.
#[derive(Debug, PartialEq, Eq)]
pub enum Next {
    /// Cancel any running ingest, delete its DEST, run ingest over `App::folders`.
    RunIngest,
    Nothing,
}

impl App {
    /// Start one identified invocation. The same lock must protect drop and ticket creation.
    pub fn begin_job(&mut self, job: &str) -> u64 {
        self.generation = self.generation.checked_add(1).expect("job generation exhausted");
        self.active_job = Some(job.to_owned());
        self.check = Some(Check::Running);
        self.notice = None;
        self.details.clear();
        self.generation
    }

    pub fn generation(&self) -> u64 { self.generation }

    /// The discovery run that may still publish, if any.
    pub fn cards_active(&self) -> Option<u64> { self.cards.active }

    /// Start one discovery run; any earlier run stops being current.
    pub fn begin_cards(&mut self) -> u64 {
        self.cards.ticket = self.cards.ticket.checked_add(1).expect("discovery ticket exhausted");
        self.cards.active = Some(self.cards.ticket);
        self.cards.ticket
    }

    /// The run `ticket` will not publish. With `failed` (a timeout) the old hint is cleared.
    pub fn invalidate_cards(&mut self, ticket: u64, failed: Option<String>) -> bool {
        if self.cards.active != Some(ticket) { return false; }
        self.cards.active = None;
        if let Some(why) = failed {
            self.cards.line = discovery::line(None);
            self.cards.details = why;
        }
        true
    }

    /// Publish the current run's judged result exactly once; a failure clears the old hint.
    pub fn finish_cards(&mut self, ticket: u64, judged: &Judged, details: String) -> bool {
        if self.cards.active != Some(ticket) { return false; }
        self.cards.active = None;
        self.cards.line = discovery::line(judged.hint.as_ref());
        self.cards.details = details;
        true
    }
    pub fn active_job(&self) -> Option<&str> { self.active_job.as_deref() }

    /// Consume exactly one terminal delivery from the current identified invocation.
    pub fn finish_job(&mut self, generation: u64, job: &str, outcome: &Outcome) -> bool {
        if outcome.cancelled || generation != self.generation || self.active_job.as_deref() != Some(job) {
            return false;
        }
        self.active_job = None;
        self.finished(outcome);
        true
    }

    pub fn fail_job(&mut self, generation: u64, job: &str, why: &str) -> bool {
        if generation != self.generation || self.active_job.as_deref() != Some(job) { return false; }
        self.active_job = None;
        self.spawn_failed(why);
        true
    }
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
            total_frames: match &check { Check::Fits(t) => Some(*t), Check::TooLong { total, .. } => Some(*total), _ => None },
            checking: check == Check::Running,
            bar,
            too_long,
            message: message.or_else(|| self.notice.clone()),
            label: self.label.clone(),
            card_line: self.cards.line.clone(),
            make_enabled: false,
            details_available: !self.details.is_empty(),
        }
    }

    /// A drop gesture. A file or a mix adds nothing (DROP_NOT_FOLDER, zero child calls).
    pub fn dropped(&mut self, paths: &[PathBuf]) -> Next {
        self.admit_drop(drops::classify(paths, &self.folders))
    }

    /// Apply the existing classifier's atomic admission result under the coordinator lock.
    pub fn admit_drop(&mut self, classified: Drop) -> Next {
        if matches!(self.check, Some(Check::Problem(_))) {
            return Next::Nothing; // Problem offers Start over only
        }
        match classified {
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
        let generation = self.generation.checked_add(1).expect("job generation exhausted");
        let cards = std::mem::take(&mut self.cards);
        *self = App::default();
        self.generation = generation;
        self.cards = cards;
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
        // Without a pinned discovery child the line says so; with one it starts empty.
        let unpinned = crate::children::TAPECTL.sha256.is_none();
        assert_eq!(v.card_line, if unpinned { CARD_LINE_UNBUILT } else { "" });
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
