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
// The recheck runs a card check child, so these run off the window's thread.
#[tauri::command(async)]
fn make_cartridge(s:Shared)->View{s.make_cartridge()}
#[tauri::command(async)]
fn make_confirm(s:Shared)->View{s.make_confirm()}
#[tauri::command]
fn make_cancel(s:Shared)->View{s.make_cancel()}
#[tauri::command]
fn make_another(s:Shared)->View{s.make_another()}
fn main(){
    let app=tauri::Builder::default().setup(|app|{
        let data=app.path().app_local_data_dir()?;
        jobdir::prepare(&data)?;
        // APP-1A §8: receipts only for exactly `digital-tape.exe --diagnostic-receipts`.
        // A session that cannot be opened leaves the app running without one.
        let args:Vec<std::ffi::OsString>=std::env::args_os().collect();
        let diag=diagnostics::opted_in(&args).then(||Session::open(&data,Provenance::of_running_app()).ok()).flatten();
        let handle:AppHandle=app.handle().clone();
        let bridge=Bridge::with_diagnostics(data,move|view|handle.emit("app-state",view).map_err(|e|e.to_string()),diag);
        // The UAC prompt for the make child belongs to this window, so it comes up in front.
        #[cfg(windows)]
        if let Some(window)=app.get_webview_window("main"){if let Ok(h)=window.hwnd(){bridge.set_owner(h.0 as isize);}}
        app.manage(bridge);
        Ok(())
    }).on_window_event(|window,event|{
        match event{
            WindowEvent::DragDrop(DragDropEvent::Drop{paths,..})=>{
                let bridge=window.app_handle().state::<Arc<Bridge>>();
                // Serialization rejects non-Unicode paths instead of lossy conversion.
                if let Ok(payload)=serde_json::to_value(paths){bridge.drop_from(Route::NativeEvent,payload);}
            }
            // APP-1 §5: closing while Making is refused with "Wait until the cartridge is finished."
            WindowEvent::CloseRequested{api,..}=>{if window.app_handle().state::<Arc<Bridge>>().close_requested(){api.prevent_close();}}
            _=>{}
        }
    }).invoke_handler(tauri::generate_handler![snapshot,set_label,drop_paths,start_over,raw_details,make_cartridge,make_confirm,make_cancel,make_another])
      .build(tauri::generate_context!()).expect("Digital Tape app");
    app.run(|handle,event|if let tauri::RunEvent::ExitRequested{api,..}=event{
        let bridge=handle.state::<Arc<Bridge>>();
        if bridge.close_requested(){api.prevent_exit();}else{bridge.shutdown();}
    });
}
