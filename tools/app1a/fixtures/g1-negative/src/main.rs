// The window shell: Tauri glue only. State lives in dtapp::state; every outcome comes
// from a bundled child. G1: nothing in the app opens a device (tools/app1a/g1_static.py).
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use dtapp::children::{self, INGEST};
use dtapp::jobdir::{self, Job};
use dtapp::state::{App, Next, View};
use dtapp::ingest_job;
use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, AtomicU64, Ordering};
use std::sync::{Arc, Mutex};
use tauri::{AppHandle, DragDropEvent, Emitter, Manager, State, WindowEvent};

struct Shared {
    app: Mutex<App>,
    data: PathBuf,
    /// Generation of the latest ingest request; older runs are stale.
    gen: AtomicU64,
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
fn start_ingest(h: AppHandle, s: Arc<Shared>) {
    if let Some(c) = s.cancel.lock().unwrap().take() {
        c.store(true, Ordering::SeqCst);
    }
    replace_current(&s, None);
    let gen = s.gen.fetch_add(1, Ordering::SeqCst) + 1;
    let bin = match children::resolve(&INGEST) {
        Ok(b) => b,
        Err(e) => {
            s.app.lock().unwrap().spawn_failed(&e.0);
            return emit(&h, &s);
        }
    };
    let job = match jobdir::create(&s.data, &format!("ingest-{}", children::nonce())) {
        Ok(j) => j,
        Err(e) => {
            s.app.lock().unwrap().spawn_failed(&format!("cannot create the app's own folder: {e}"));
            return emit(&h, &s);
        }
    };
    let folders = s.app.lock().unwrap().folders.clone();
    let cancel = Arc::new(AtomicBool::new(false));
    *s.cancel.lock().unwrap() = Some(cancel.clone());
    emit(&h, &s);
    std::thread::spawn(move || {
        let o = ingest_job::run(&bin, INGEST.version.unwrap_or_default(), &job, &folders, cancel);
        if o.cancelled || s.gen.load(Ordering::SeqCst) != gen {
            jobdir::remove(&job);
            return;
        }
        s.app.lock().unwrap().finished(&o);
        if o.exit == Some(0) {
            replace_current(&s, Some(job));
        } else {
            jobdir::remove(&job);
        }
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
    if let Some(c) = s.cancel.lock().unwrap().take() {
        c.store(true, Ordering::SeqCst);
    }
    s.gen.fetch_add(1, Ordering::SeqCst);
    replace_current(&s, None);
    s.app.lock().unwrap().start_over();
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
                gen: AtomicU64::new(0),
                cancel: Mutex::new(None),
                current: Mutex::new(None),
            }));
            Ok(())
        })
        .on_window_event(|w, e| {
            if let WindowEvent::DragDrop(DragDropEvent::Drop { paths, .. }) = e {
                let h = w.app_handle().clone();
                let s = h.state::<Arc<Shared>>().inner().clone();
                let next = s.app.lock().unwrap().dropped(paths);
                match next {
                    Next::RunIngest => start_ingest(h, s),
                    Next::Nothing => emit(&h, &s),
                }
            }
        })
        .invoke_handler(tauri::generate_handler![view, set_label, start_over, details])
        .run(tauri::generate_context!())
        .expect("the Digital Tape window");
}
