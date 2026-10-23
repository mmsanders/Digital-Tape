// The window shell: Tauri glue only. State lives in dtapp::state; every outcome comes
// from a bundled child. G1: nothing in the app opens a device (tools/app1a/g1_static.py).
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use dtapp::children::{self, INGEST};
use dtapp::jobdir::{self, Job};
use dtapp::state::{App, Next, View};
use dtapp::ingest_job;
use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::{Arc, Mutex};
use tauri::{AppHandle, DragDropEvent, Emitter, Manager, State, WindowEvent};

struct Shared {
    app: Mutex<App>,
    data: PathBuf,
    cancel: Mutex<Option<Arc<AtomicBool>>>,
    /// The job holding the latest checked DEST (kept for Make, deleted when replaced).
    current: Mutex<Option<Job>>,
}

type Sh<'a> = State<'a, Arc<Shared>>;

fn emit(h: &AppHandle, s: &Shared) {
    let v = s.app.lock().unwrap().view();
    let _ = h.emit("state", v);
}

fn replace_current(s: &Shared, job: Option<Job>) {
    if let Some(old) = std::mem::replace(&mut *s.current.lock().unwrap(), job) {
        jobdir::remove(&old);
    }
}

/// Cancel any running check and its DEST, then check every folder so far.
fn start_ingest(h: AppHandle, s: Arc<Shared>, job_id: String, generation: u64) {
    if let Some(c) = s.cancel.lock().unwrap().take() {
        c.store(true, Ordering::SeqCst);
    }
    replace_current(&s, None);
    let bin = match children::resolve(&INGEST) {
        Ok(b) => b,
        Err(e) => {
            s.app.lock().unwrap().fail_job(generation, &job_id, &e.0);
            return emit(&h, &s);
        }
    };
    let job = match jobdir::create(&s.data, &job_id) {
        Ok(j) => j,
        Err(e) => {
            s.app.lock().unwrap().fail_job(generation, &job_id, &format!("cannot create the app's own folder: {e}"));
            return emit(&h, &s);
        }
    };
    let cancel = Arc::new(AtomicBool::new(false));
    let folders = {
        let app = s.app.lock().unwrap();
        if app.generation() != generation || app.active_job() != Some(job_id.as_str()) {
            jobdir::remove(&job);
            return;
        }
        *s.cancel.lock().unwrap() = Some(cancel.clone());
        app.folders.clone()
    };
    emit(&h, &s);
    std::thread::spawn(move || {
        let o = ingest_job::run(&bin, INGEST.version.unwrap_or_default(), &job, &folders, cancel);
        let mut app = s.app.lock().unwrap();
        if !app.finish_job(generation, &job_id, &o) {
            jobdir::remove(&job);
            return;
        }
        if o.exit == Some(0) {
            replace_current(&s, Some(job));
        } else {
            jobdir::remove(&job);
        }
        drop(app);
        emit(&h, &s);
    });
}

#[tauri::command]
fn view(s: Sh) -> View {
    s.app.lock().unwrap().view()
}

#[tauri::command]
fn set_label(h: AppHandle, s: Sh, text: String) -> View {
    s.app.lock().unwrap().set_label(&text);
    let v = s.app.lock().unwrap().view();
    emit(&h, &s);
    v
}

#[tauri::command]
fn start_over(h: AppHandle, s: Sh) -> View {
    {
        let mut app = s.app.lock().unwrap();
        if let Some(c) = s.cancel.lock().unwrap().take() {
            c.store(true, Ordering::SeqCst);
        }
        app.start_over();
        replace_current(&s, None);
    }
    emit(&h, &s);
    s.app.lock().unwrap().view()
}

/// Show details: the raw stderr of the last child, copyable.
#[tauri::command]
fn details(s: Sh) -> String {
    s.app.lock().unwrap().details.clone()
}

fn main() {
    tauri::Builder::default()
        .setup(|app| {
            let data = app.path().app_local_data_dir().expect("per-user app data folder");
            jobdir::prepare(&data)?;
            jobdir::clean_stale(&data);
            app.manage(Arc::new(Shared {
                app: Mutex::new(App::default()),
                data,
                cancel: Mutex::new(None),
                current: Mutex::new(None),
            }));
            Ok(())
        })
        .on_window_event(|w, e| {
            if let WindowEvent::DragDrop(DragDropEvent::Drop { paths, .. }) = e {
                let h = w.app_handle().clone();
                let s = h.state::<Arc<Shared>>().inner().clone();
                let job_id = format!("ingest-{}", children::nonce());
                let (next, generation) = {
                    let mut app = s.app.lock().unwrap();
                    let next = app.dropped(paths);
                    let generation = if next == Next::RunIngest { app.begin_job(&job_id) } else { app.generation() };
                    (next, generation)
                };
                match next {
                    Next::RunIngest => start_ingest(h, s, job_id, generation),
                    Next::Nothing => emit(&h, &s),
                }
            }
        })
        .invoke_handler(tauri::generate_handler![view, set_label, start_over, details])
        .run(tauri::generate_context!())
        .expect("the Digital Tape window");
}
