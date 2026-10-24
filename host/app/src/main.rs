#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
use dtapp::{bridge::Bridge, jobdir, state::View};
use std::sync::Arc;
use tauri::{AppHandle, DragDropEvent, Emitter, Manager, State, WindowEvent};
type Shared<'a> = State<'a, Arc<Bridge>>;
#[tauri::command]
fn snapshot(s:Shared)->View{s.snapshot()}
#[tauri::command]
fn set_label(s:Shared,text:String)->View{s.set_label(&text)}
#[tauri::command]
fn drop_paths(s:Shared,paths:serde_json::Value)->View{s.drop_paths(paths)}
#[tauri::command]
fn start_over(s:Shared)->View{s.start_over()}
#[tauri::command]
fn raw_details(s:Shared)->String{s.raw_details()}
fn main(){
    let app=tauri::Builder::default().setup(|app|{
        let data=app.path().app_local_data_dir()?;
        jobdir::prepare(&data)?;
        let handle:AppHandle=app.handle().clone();
        app.manage(Bridge::new(data,move|view|{let _=handle.emit("app-state",view);}));
        Ok(())
    }).on_window_event(|window,event|{
        if let WindowEvent::DragDrop(DragDropEvent::Drop{paths,..})=event{
            let bridge=window.app_handle().state::<Arc<Bridge>>();
            // Serialization rejects non-Unicode paths instead of lossy conversion.
            if let Ok(payload)=serde_json::to_value(paths){bridge.drop_paths(payload);}
        }
    }).invoke_handler(tauri::generate_handler![snapshot,set_label,drop_paths,start_over,raw_details])
      .build(tauri::generate_context!()).expect("Digital Tape app");
    app.run(|handle,event|if let tauri::RunEvent::ExitRequested{..}=event{handle.state::<Arc<Bridge>>().shutdown();});
}
