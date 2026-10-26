// Compiled only as a Rust unit test. Verification324: one actual production Bridge per case,
// driven line by line by the test-document adapter (tools/app/interactions-dom.cjs) so the
// production binding's own host calls enter the coordinator. Typed child outcomes enter the
// actual execute/discover/poll_once closures; no child, device or fake shipping route.
use super::*;
use crate::{discovery::{Child, End, INTERVAL_MS}, report::Reading};
use serde_json::{json, Value};
use std::{collections::VecDeque, fs, io::{BufRead, Write}, path::Path, sync::atomic::AtomicUsize};

const NONCE: &str = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa";
const VERSION: &str = "tapectl-wp15-s2+bbbbbbbbbbbb";

/// A started discovery child that exits only when the adapter releases it.
struct Gate { exit: Arc<Mutex<Option<Option<i32>>>>, polled: Arc<AtomicBool> }
impl Child for Gate {
    fn poll(&mut self) -> Option<Option<i32>> { self.polled.store(true, Ordering::SeqCst); *self.exit.lock().unwrap() }
    fn stop(&mut self) -> Option<i32> { None }
}
struct Blocked { exit: Arc<Mutex<Option<Option<i32>>>>, case: Arc<Mutex<Option<Value>>>, thread: thread::JoinHandle<()> }
struct Pending { generation: u64, id: String, release: mpsc::Sender<Outcome>, thread: thread::JoinHandle<()> }

struct Session {
    root: PathBuf, foreign: PathBuf, b: Arc<Bridge>, views: Arc<Mutex<Vec<View>>>, sent: usize,
    rx: mpsc::Receiver<Message>, works: VecDeque<Work>, requests: usize,
    checks: VecDeque<Pending>, done: Vec<(u64, String)>, cards: Option<Blocked>,
    poll: Option<(thread::JoinHandle<bool>, mpsc::Sender<()>)>, live: Arc<AtomicUsize>, peak: Arc<AtomicUsize>,
}

fn typed(c: &Value) -> Ran {
    Ran { pid: Some(1), exit: c["exit"].as_i64().map(|e| e as i32), stdout: c["stdout"].as_str().unwrap_or("").as_bytes().to_vec(),
        stderr: c["stderr"].as_str().unwrap_or("").as_bytes().to_vec(),
        report: c["report"].as_str().filter(|r| !r.is_empty()).map(|r| r.as_bytes().to_vec()), ..Default::default() }
}
fn request(job: &jobdir::Job) -> Request {
    Request { exe: "tapectl.exe".into(), argv: vec![], cwd: job.dir.clone(), report: job.control.join("r"), nonce: NONCE.into(), version: VERSION.into() }
}
fn outcome(o: &Value) -> Outcome {
    Outcome { exit: o["exit"].as_i64().map(|e| e as i32), stderr: o["stderr"].as_str().unwrap_or("").into(),
        reading: Reading::Unusable("controlled typed outcome"), total_frames: o["frames"].as_u64(), cancelled: false }
}
/// Each distinct dropped name is one plain folder (metadata facts only, never outcomes).
fn facts(p: &Path) -> drops::Fact {
    let n = p.to_string_lossy().bytes().fold(7u64, |h, c| h.wrapping_mul(131).wrapping_add(c as u64));
    drops::Fact { plain_folder: true, identity: Some((1, n)) }
}

impl Session {
    fn new() -> Self {
        let root = std::env::temp_dir().join(format!("DigitalTapeInteraction-{}", children::nonce()));
        jobdir::prepare(&root).unwrap();
        let foreign = root.join("jobs").join("foreign");
        fs::create_dir_all(&foreign).unwrap();
        fs::write(foreign.join("keep"), b"FOREIGN\n").unwrap();
        let views = Arc::new(Mutex::new(Vec::new()));
        let out = views.clone();
        let (b, rx) = Bridge::channel(root.clone(), Arc::new(move |v| out.lock().unwrap().push(v)));
        Session { root, foreign, b, views, sent: 0, rx, works: VecDeque::new(), requests: 0, checks: VecDeque::new(), done: Vec::new(),
            cards: None, poll: None, live: Arc::new(AtomicUsize::new(0)), peak: Arc::new(AtomicUsize::new(0)) }
    }
    fn pump(&mut self) {
        for m in self.rx.try_iter() { if let Message::Check(w) = m { self.requests += 1; self.works.push_back(w); } }
    }
    /// A run closure for one typed card outcome that records single-flight occupancy.
    fn card_run(&self, c: Value) -> impl FnOnce(&jobdir::Job, &AtomicBool, &mut dyn FnMut(), &mut dyn FnMut()) -> (Ran, Request) {
        let (live, peak) = (self.live.clone(), self.peak.clone());
        move |job, _, _, _| {
            let n = live.fetch_add(1, Ordering::SeqCst) + 1;
            peak.fetch_max(n, Ordering::SeqCst);
            live.fetch_sub(1, Ordering::SeqCst);
            (typed(&c), request(job))
        }
    }
    fn tickets(&self) -> u64 { self.b.trace.lock().unwrap().iter().filter(|e| *e == "cards:worker-start").count() as u64 }
    fn op(&mut self, cmd: &Value) -> Value {
        let a = &cmd["arg"];
        let result = match cmd["op"].as_str().unwrap() {
            "snapshot" => json!(self.b.snapshot()),
            "set_label" => json!(self.b.set_label(a.as_str().unwrap())),
            "start_over" => json!(self.b.start_over()),
            "raw_details" => json!(self.b.raw_details()),
            "drop_paths" => json!(self.b.drop_using(a.clone(), |p, c| drops::classify_with(p, c, facts))),
            // The serial worker: one admitted Work through the production execute closure.
            "check" => {
                self.pump();
                let w = self.works.pop_front().expect("admitted work");
                self.done.push((w.generation, w.id.clone()));
                let o = outcome(a);
                self.b.execute(w, move |_, _| Ok(o));
                Value::Null
            }
            "check_begin" => {
                self.pump();
                let w = self.works.pop_front().expect("admitted work");
                let (generation, id) = (w.generation, w.id.clone());
                let (release, wait) = mpsc::channel::<Outcome>();
                let (entered_tx, entered) = mpsc::channel();
                let b = self.b.clone();
                let thread = thread::spawn(move || b.execute(w, move |_, _| { entered_tx.send(()).unwrap(); Ok(wait.recv().unwrap()) }));
                entered.recv().unwrap();
                self.checks.push_back(Pending { generation, id, release, thread });
                Value::Null
            }
            "check_release" => {
                let p = self.checks.pop_front().expect("running check");
                p.release.send(outcome(a)).unwrap();
                p.thread.join().unwrap();
                self.done.push((p.generation, p.id));
                Value::Null
            }
            // A completed check's terminal delivered again (`index` into completed checks).
            "check_duplicate" => {
                let (generation, id) = self.done[a["index"].as_u64().unwrap() as usize].clone();
                json!(self.b.deliver(generation, &id, &outcome(&a["outcome"])))
            }
            "cards" => { let run = self.card_run(a.clone()); self.b.discover(run); Value::Null }
            "cards_block" => {
                let exit = Arc::new(Mutex::new(None));
                let case = Arc::new(Mutex::new(None::<Value>));
                let polled = Arc::new(AtomicBool::new(false));
                let (b, e, c, p, live, peak) = (self.b.clone(), exit.clone(), case.clone(), polled.clone(), self.live.clone(), self.peak.clone());
                let thread = thread::spawn(move || {
                    b.discover(move |job, cancel, on_timeout, on_cancel| {
                        let n = live.fetch_add(1, Ordering::SeqCst) + 1;
                        peak.fetch_max(n, Ordering::SeqCst);
                        let clock = std::time::Instant::now();
                        let end = discovery::supervise(&mut Gate { exit: e, polled: p }, cancel, &mut || clock.elapsed().as_millis() as u64, on_timeout, on_cancel);
                        live.fetch_sub(1, Ordering::SeqCst);
                        let ran = match end { End::Exited(_) => typed(c.lock().unwrap().as_ref().unwrap()), _ => Ran { cancelled: end == End::Cancelled, timed_out: end == End::TimedOut, ..Default::default() } };
                        (ran, request(job))
                    });
                });
                while !polled.load(Ordering::SeqCst) { thread::sleep(std::time::Duration::from_millis(2)); }
                self.cards = Some(Blocked { exit, case, thread });
                Value::Null
            }
            "cards_release" => {
                let blocked = self.cards.take().expect("blocked poll");
                *blocked.case.lock().unwrap() = Some(a.clone());
                *blocked.exit.lock().unwrap() = Some(a["exit"].as_i64().map(|e| e as i32));
                blocked.thread.join().unwrap();
                Value::Null
            }
            // The same completion delivered again for the most recent registered run.
            "cards_duplicate" => {
                let judged = discovery::judge(a["exit"].as_i64().map(|e| e as i32), a["stdout"].as_str().unwrap().as_bytes(), a["report"].as_str().map(str::as_bytes), NONCE, VERSION);
                self.b.publish_cards(self.tickets(), &judged, discovery::details(&typed(a), &judged));
                Value::Null
            }
            "poll_pause" => {
                let (paused_tx, paused) = mpsc::channel();
                let (resume, resume_rx) = mpsc::channel::<()>();
                *self.b.before_admission.lock().unwrap() = Some(Box::new(move || { paused_tx.send(()).unwrap(); resume_rx.recv().unwrap(); }));
                let (b, run) = (self.b.clone(), self.card_run(a.clone()));
                let thread = thread::spawn(move || { let mut s = discovery::Schedule::new(0); b.poll_once(&mut s, &|| INTERVAL_MS, run) });
                paused.recv().unwrap();
                self.poll = Some((thread, resume));
                Value::Null
            }
            "poll_resume" => {
                let (thread, resume) = self.poll.take().expect("paused poll");
                resume.send(()).unwrap();
                json!(thread.join().unwrap())
            }
            "shutdown" => {
                self.b.shutdown();
                // The blocked child saw shutdown's cancellation; its run reaches its terminal.
                if let Some(blocked) = self.cards.take() { blocked.thread.join().unwrap(); }
                Value::Null
            }
            "facts" => {
                self.pump();
                let jobs: Vec<String> = fs::read_dir(self.root.join("jobs")).unwrap().flatten().map(|e| e.file_name().to_string_lossy().into_owned()).collect();
                let core = self.b.core.lock().unwrap();
                json!({"trace": *self.b.trace.lock().unwrap(), "folders": core.app.folders.iter().map(|p| drops::display_name(p)).collect::<Vec<_>>(),
                    "check_requests": self.requests, "cards_active": core.app.cards_active(), "max_concurrent": self.peak.load(Ordering::SeqCst),
                    "jobs": jobs, "foreign_intact": fs::read(self.foreign.join("keep")).ok().as_deref() == Some(&b"FOREIGN\n"[..]),
                    "emissions": self.views.lock().unwrap().len()})
            }
            other => panic!("unknown op {other}"),
        };
        let views = self.views.lock().unwrap();
        let emitted: Vec<Value> = views[self.sent..].iter().map(|v| json!(v)).collect();
        self.sent = views.len();
        json!({"result": result, "emitted": emitted})
    }
}

/// Serves the adapter over stdin/stdout ("@@ " lines). `new` starts a fresh Bridge.
#[test]
fn serve() {
    if std::env::var("DT_INTERACTION_SERVE").is_err() { return }
    let mut session: Option<Session> = None;
    let stdout = std::io::stdout();
    for line in std::io::stdin().lock().lines() {
        let cmd: Value = serde_json::from_str(&line.unwrap()).unwrap();
        let reply = if cmd["op"] == "new" {
            if let Some(old) = session.take() { let _ = fs::remove_dir_all(&old.root); }
            session = Some(Session::new());
            json!({"result": null, "emitted": []})
        } else if cmd["op"] == "end" {
            break
        } else {
            session.as_mut().unwrap().op(&cmd)
        };
        let mut out = stdout.lock();
        writeln!(out, "@@ {}", reply).unwrap();
        out.flush().unwrap();
    }
    if let Some(old) = session.take() { let _ = fs::remove_dir_all(&old.root); }
}
