//! The window's state (APP-1 §2) as plain data, so every transition is testable without
//! a window. The card line comes from S2 discovery when this build pins its tapectl.
//! Discovery is a hint only: Make cartridge is enabled exactly when APP-1 §2/§4 allow it
//! (one offered card, a label, a successful check whose audio the app still holds, nothing
//! running), and the elevated `tapectl make` child alone decides what happens to a card.

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
    /// The current details are a diagnostic (a failure, or cards that were not checked),
    /// so Show details offers them whatever the music's state.
    pub diagnostic: bool,
    /// The one offered card (path, bytes) of the current result; None for 0, 2+ or unknown.
    pub card: Option<(String, u64)>,
    ticket: u64,
    active: Option<u64>,
}

impl Default for Cards {
    fn default() -> Self {
        let line = if crate::children::TAPECTL.sha256.is_some() { String::new() } else { CARD_LINE_UNBUILT.into() };
        Cards { line, details: String::new(), diagnostic: false, card: None, ticket: 0, active: None }
    }
}

/// Make cartridge (APP-1 §4), once the music check has passed.
#[derive(Debug, Clone, PartialEq)]
pub enum Making {
    Idle,
    /// The erase confirmation is showing for this rechecked card.
    Confirm { dev: String, bytes: u64 },
    /// The elevated child is running; the bar's running maximum and its step.
    Running { fraction: f64, step: &'static str },
    Done,
}

impl Default for Making {
    fn default() -> Self { Making::Idle }
}

pub const MADE: &str = "Your cartridge is ready. You can take the card out now.";
pub const WAIT: &str = "Wait until the cartridge is finished.";

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
    /// "empty" | "ready" | "problem" | "making" | "done".
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
    /// INGEST's details, offered only while the music is a Problem.
    pub details_available: bool,
    /// The current card check's diagnostic, offered in any state.
    pub card_details_available: bool,
    /// Start overs so far. The window owns the label box between them, so only a view
    /// from a newer Start over may rewrite it.
    pub resets: u64,
    /// The erase confirmation (APP-1 §4 step 2) is showing.
    pub confirm: bool,
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
    resets: u64,
    /// The current check's published audio, held by the app for Make; None until the
    /// bridge has retained it for this generation, and after a cartridge is made.
    pub audio: Option<PathBuf>,
    pub making: Making,
    /// A window close was refused while Making.
    close_refused: bool,
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
            self.cards.diagnostic = true;
            self.cards.card = None;
        }
        true
    }

    /// Publish the current run's judged result exactly once; a failure clears the old hint.
    pub fn finish_cards(&mut self, ticket: u64, judged: &Judged, details: String) -> bool {
        if self.cards.active != Some(ticket) { return false; }
        self.cards.active = None;
        self.cards.card = judged.hint.as_ref().filter(|h| h.paths.len() == 1 && h.sizes.len() == 1).map(|h| (h.paths[0].clone(), h.sizes[0]));
        self.cards.line = discovery::line(judged.hint.as_ref());
        self.cards.diagnostic = judged.hint.as_ref().map_or(true, |h| h.unprobed > 0);
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
        let (mut view, mut bar, too_long, mut message) = match &check {
            Check::Problem(m) => ("problem", None, false, Some(m.clone())),
            Check::TooLong { total, excess } => {
                let _ = total;
                ("ready", Some(1.0), true, Some(too_long_sentence(*excess)))
            }
            Check::Fits(t) => ("ready", Some((*t as f64 / CAPACITY_FRAMES as f64).min(1.0)), false, None),
            Check::Running => (if self.folders.is_empty() { "empty" } else { "ready" }, None, false, None),
            Check::Idle => ("empty", Some(0.0), false, None),
        };
        match &self.making {
            Making::Running { fraction, step } => {
                (view, bar) = ("making", Some(*fraction));
                message = Some(if self.close_refused { WAIT.into() } else { crate::make::step_line(step).into() });
            }
            Making::Done => (view, bar, message) = ("done", None, Some(MADE.into())),
            Making::Idle | Making::Confirm { .. } => {}
        }
        View {
            view,
            total_frames: match &check { Check::Fits(t) => Some(*t), Check::TooLong { total, .. } => Some(*total), _ => None },
            checking: check == Check::Running,
            bar,
            too_long,
            message: message.or_else(|| self.notice.clone()),
            label: self.label.clone(),
            card_line: self.cards.line.clone(),
            make_enabled: self.make_card().is_some(),
            details_available: !self.details.is_empty(),
            card_details_available: self.cards.diagnostic && !self.cards.details.is_empty(),
            resets: self.resets,
            confirm: matches!(self.making, Making::Confirm { .. }),
        }
    }

    /// The card Make cartridge would use, exactly when APP-1 §2/§4 allow Make: one offered
    /// card, a non-empty label, a successful check whose audio the app still holds, no
    /// check running and no Make under way.
    pub fn make_card(&self) -> Option<(String, u64)> {
        let ready = self.making == Making::Idle && matches!(self.check, Some(Check::Fits(_))) && !self.label.is_empty()
            && self.audio.is_some() && self.active_job.is_none();
        if ready { self.cards.card.clone() } else { None }
    }

    pub fn is_making(&self) -> bool { matches!(self.making, Making::Running { .. }) }

    /// Step 2: show the erase confirmation if the recheck printed the same single card the
    /// person saw (`seen`, taken before the recheck) and Make is still allowed with it;
    /// otherwise stay Ready with the card line (CARD_RECHECK_MISMATCH).
    pub fn confirm(&mut self, seen: &(String, u64), rechecked: Option<(String, u64)>) -> bool {
        match (self.make_card(), rechecked) {
            (Some(card), Some(again)) if card == again && &again == seen => {
                self.notice = None;
                self.making = Making::Confirm { dev: card.0, bytes: card.1 };
                true
            }
            _ => false,
        }
    }

    /// Keep card: back to Ready, nothing started.
    pub fn keep_card(&mut self) {
        if matches!(self.making, Making::Confirm { .. }) { self.making = Making::Idle; }
    }

    /// Step 3: the second recheck must still print the confirmed card; then Making starts.
    /// Returns what to launch: (DEV, label, audio).
    pub fn start_making(&mut self, rechecked: Option<(String, u64)>) -> Option<(String, String, PathBuf)> {
        let Making::Confirm { dev, bytes } = &self.making else { return None };
        let confirmed = (dev.clone(), *bytes);
        let audio = self.audio.clone();
        match (rechecked, audio) {
            (Some(again), Some(audio)) if again == confirmed && self.cards.card.as_ref() == Some(&confirmed) => {
                self.making = Making::Running { fraction: 0.0, step: "safety" };
                self.close_refused = false;
                Some((confirmed.0, self.label.clone(), audio))
            }
            _ => {
                self.making = Making::Idle;
                None
            }
        }
    }

    /// Progress from the child's report: the bar only ever moves forward.
    pub fn made_progress(&mut self, f: f64, now: &'static str) -> bool {
        match &mut self.making {
            Making::Running { fraction, step } if f > *fraction || (f == *fraction && *step != now) => {
                (*fraction, *step) = (f.max(*fraction), now);
                true
            }
            _ => false,
        }
    }

    /// The child finished. Success is Done (the bridge has deleted the audio); any other
    /// outcome returns to Ready with its sentence and Show details.
    pub fn made(&mut self, message: Option<String>, details: String) {
        self.close_refused = false;
        match message {
            None => {
                self.making = Making::Done;
                self.audio = None;
            }
            Some(m) => {
                self.making = Making::Idle;
                self.notice = Some(m);
                self.details = details;
            }
        }
    }

    /// Closing the window while Making is refused; true if it was.
    pub fn refuse_close(&mut self) -> bool {
        if !self.is_making() { return false; }
        self.close_refused = true;
        true
    }

    /// Make another, after Done: the same folders and label, checked again.
    pub fn make_another(&mut self) -> Next {
        if self.making != Making::Done { return Next::Nothing; }
        self.making = Making::Idle;
        if self.folders.is_empty() { Next::Nothing } else { Next::RunIngest }
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
        if self.making != Making::Idle {
            return Next::Nothing; // nothing is added while confirming, Making or Done
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
        let resets = self.resets + 1;
        *self = App::default();
        self.generation = generation;
        self.cards = cards;
        self.resets = resets;
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

    fn one_card(a: &mut App, path: &str, bytes: u64) {
        let t = a.begin_cards();
        let hint = crate::discovery::Hint { sizes: vec![bytes], unprobed: 0, paths: vec![path.into()] };
        assert!(a.finish_cards(t, &Judged { hint: Some(hint), id_specific: None }, String::new()));
    }

    #[test]
    fn make_is_enabled_exactly_when_app1_allows() {
        let mut a = App::default();
        a.folders.push("/x".into());
        a.finished(&outcome(0, Reading::Unusable("no report"), Some(CAPACITY_FRAMES / 2)));
        a.set_label("Road Trip");
        one_card(&mut a, "D1", 64_000_000_000);
        assert!(!a.view().make_enabled, "no retained audio yet");
        a.audio = Some("/jobs/ready/out/DEST/audio.wav".into());
        assert!(a.view().make_enabled);
        a.label.clear();
        assert!(!a.view().make_enabled, "empty label");
        a.set_label("Road Trip");
        let t = a.begin_cards();
        a.finish_cards(t, &Judged { hint: Some(crate::discovery::Hint { sizes: vec![1, 2], unprobed: 0, paths: vec!["D1".into(), "D2".into()] }), id_specific: None }, String::new());
        assert!(!a.view().make_enabled, "two cards");
        one_card(&mut a, "D1", 64_000_000_000);
        assert!(!a.confirm(&("D1".into(), 64_000_000_000), Some(("D2".into(), 64_000_000_000))), "recheck mismatch stays Ready");
        assert!(a.confirm(&("D1".into(), 64_000_000_000), Some(("D1".into(), 64_000_000_000))));
        assert!(a.view().confirm && !a.view().make_enabled);
        a.keep_card();
        assert!(!a.view().confirm && a.view().make_enabled);
        assert!(a.confirm(&("D1".into(), 64_000_000_000), Some(("D1".into(), 64_000_000_000))));
        assert_eq!(a.start_making(None), None, "a card gone at the second recheck starts nothing");
        assert!(a.confirm(&("D1".into(), 64_000_000_000), Some(("D1".into(), 64_000_000_000))));
        let (dev, label, wav) = a.start_making(Some(("D1".into(), 64_000_000_000))).unwrap();
        assert_eq!((dev.as_str(), label.as_str(), wav), ("D1", "Road Trip", PathBuf::from("/jobs/ready/out/DEST/audio.wav")));
        assert_eq!(a.view().view, "making");
        assert!(a.made_progress(0.5, "load") && !a.made_progress(0.4, "load"));
        assert_eq!(a.view().bar, Some(0.5));
        assert_eq!(a.dropped(&["/y".into()]), Next::Nothing, "no drops while Making");
        assert!(a.refuse_close());
        assert_eq!(a.view().message.as_deref(), Some(WAIT));
        a.made(None, String::new());
        assert_eq!((a.view().view, a.view().message.as_deref()), ("done", Some(MADE)));
        assert_eq!(a.make_another(), Next::RunIngest);
        assert!(!a.view().make_enabled, "Make another checks the music again");
    }

    #[test]
    fn never_offers_make_without_retained_audio() {
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
