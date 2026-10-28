#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
use dtapp::{bridge::Bridge, diagnostics::{self, Provenance, Route, Session}, jobdir, state::View};
use std::sync::Arc;
use tauri::{AppHandle, DragDropEvent, Emitter, Manager, State, WindowEvent};
type Shared<'a> = State<'a, Arc<Bridge>>;
#[tauri::command]
fn snapshot(s:Shared)->View{s.snapshot()}
#[tauri::command]
fn set_label(s:Shared,text:String)->View{s.set_label(&text)}
#[tauri::command]
fn drop_paths(s:Shared,paths:serde_json::Value)->View{s.drop_from(Route::TauriCommand,paths)}
#[tauri::command]
fn start_over(s:Shared)->View{s.start_over()}
#[tauri::command]
fn raw_details(s:Shared)->String{s.raw_details()}
fn main(){
    let app=tauri::Builder::default().setup(|app|{
        let data=app.path().app_local_data_dir()?;
        jobdir::prepare(&data)?;
        // APP-1A §8: receipts only for exactly `digital-tape.exe --diagnostic-receipts`.
        // A session that cannot be opened leaves the app running without one.
        let args:Vec<std::ffi::OsString>=std::env::args_os().collect();
        let diag=diagnostics::opted_in(&args).then(||Session::open(&data,Provenance::of_running_app()).ok()).flatten();
        let handle:AppHandle=app.handle().clone();
        app.manage(Bridge::with_diagnostics(data,move|view|handle.emit("app-state",view).map_err(|e|e.to_string()),diag));
        Ok(())
    }).on_window_event(|window,event|{
        if let WindowEvent::DragDrop(DragDropEvent::Drop{paths,..})=event{
            let bridge=window.app_handle().state::<Arc<Bridge>>();
            // Serialization rejects non-Unicode paths instead of lossy conversion.
            if let Ok(payload)=serde_json::to_value(paths){bridge.drop_from(Route::NativeEvent,payload);}
        }
    }).invoke_handler(tauri::generate_handler![snapshot,set_label,drop_paths,start_over,raw_details])
      .build(tauri::generate_context!()).expect("Digital Tape app");
    app.run(|handle,event|if let tauri::RunEvent::ExitRequested{..}=event{handle.state::<Arc<Bridge>>().shutdown();});
}
