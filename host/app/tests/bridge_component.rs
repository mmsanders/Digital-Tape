// Compiled only as a Rust unit test. No fake executable or shipping outcome switch.
use super::*;
use crate::{messages, report::{self, Reading, Tool}};
use serde_json::{json, Value};
use std::{fs, path::{Path,PathBuf}, sync::mpsc, time::Duration};
const VERSION:&str="0.1.1 INGEST-1 arithmetic-profile INGEST1-AP4";
fn save(p:&Path,v:&Value){fs::write(p,serde_json::to_vec_pretty(v).unwrap()).unwrap();}
fn pair(c:&Value,cancelled:bool)->Outcome{
    let exit=c["exit"].as_i64().unwrap() as i32;
    Outcome{exit:Some(exit),stderr:c["stderr"].as_str().unwrap().into(),
        reading:report::read(c["report"].as_str().unwrap().as_bytes(),Tool::Ingest,&"a".repeat(32),VERSION,exit,1),
        total_frames:if c["pair"]==true{Some(88200)}else{None},cancelled}
}
fn refusal(id:&str,subject:Value,excess:Option<u64>,bad_nonce:bool)->Outcome{
    let nonce=if bad_nonce{"b".repeat(32)}else{"a".repeat(32)};
    let mut r=json!({"t":"refusal","id":id,"subject":subject});
    if let Some(e)=excess{r["total_frames"]=json!(158760000u64+e);r["capacity_frames"]=json!(158760000);r["excess_frames"]=json!(e);}
    let text=format!("{}\n{}\n{}\n",json!({"t":"start","tool":"ingest","version":VERSION,"nonce":nonce}),r,json!({"t":"end","exit":2}));
    Outcome{exit:Some(2),stderr:"raw\r\n<unsafe>& diagnostics".into(),reading:report::read(text.as_bytes(),Tool::Ingest,&"a".repeat(32),VERSION,2,1),total_frames:None,cancelled:false}
}
fn begin(b:&Bridge,id:&str)->Work{let mut core=b.core.lock().unwrap();Bridge::begin(&mut core,id.into())}
fn visible(b:&Bridge)->Value{
    let v=b.snapshot();let name=if v.checking{"Checking"}else{match v.view{"empty"=>"Empty","ready"=>"Ready",_=>"Problem"}};
    let category=if name=="Ready"{json!("success")}else if name=="Problem"{
        if v.message.as_deref()==Some(messages::GENERIC_INGEST){json!("generic")}else if v.message.as_deref().unwrap_or("").contains("isn't music"){json!("folder-nonmusic")}else{json!("UNCLASSIFIED")}
    }else{Value::Null};
    json!({"view":name,"category":category,"total_frames":v.total_frames,"details":b.raw_details(),"make_enabled":v.make_enabled})
}
fn new(root:&Path)->(Arc<Bridge>,mpsc::Receiver<Message>,Arc<Mutex<Vec<Value>>>){
    let events=Arc::new(Mutex::new(Vec::new()));let out=events.clone();
    let(b,rx)=Bridge::channel(root.into(),Arc::new(move|v|out.lock().unwrap().push(serde_json::to_value(v).unwrap())));
    (b,rx,events)
}
fn seed(b:&Bridge){b.core.lock().unwrap().app.folders=vec![PathBuf::from("Music")];}
fn facts(p:&Path)->drops::Fact{
    let s=p.to_string_lossy();drops::Fact{plain_folder:!s.ends_with(".wav")&&!s.ends_with("symlink"),identity:if s.contains("unknown"){None}else{Some((1,if s.contains("A & literal")||s.ends_with("alias")||s.ends_with('A'){1}else if s.ends_with('B'){2}else{3}))}}
}
fn drop_model(b:&Bridge,payload:Value)->View{b.drop_using(payload,|p,c|drops::classify_with(p,c,facts))}
fn next(rx:&mpsc::Receiver<Message>)->Work{match rx.recv_timeout(Duration::from_secs(3)).unwrap(){Message::Check(w)=>w,_=>panic!("check expected")}}
fn folders(b:&Bridge)->Value{json!(b.core.lock().unwrap().app.folders)}
fn count(rx:&mpsc::Receiver<Message>)->usize{rx.try_iter().filter(|m|matches!(m,Message::Check(_))).count()}

#[test]
fn capture(){
    let Ok(output)=std::env::var("DT_BRIDGE_OUTPUT")else{return};
    let out=PathBuf::from(output);fs::create_dir_all(&out).unwrap();
    let inputs:Value=serde_json::from_slice(&fs::read(std::env::var("DT_BRIDGE_INPUT").unwrap()).unwrap()).unwrap();
    let frame_inputs:Value=serde_json::from_slice(&fs::read(std::env::var("DT_BRIDGE_FRAMES").unwrap()).unwrap()).unwrap();
    let root=PathBuf::from(std::env::var_os("LOCALAPPDATA").unwrap_or_else(||std::env::temp_dir().into())).join(format!("DigitalTapeComponent-{}",children::nonce()));
    fs::create_dir(&root).unwrap();
    let source=root.join("source-sentinel");let foreign=root.join("foreign-sentinel");
    fs::write(&source,b"SOURCE UNCHANGED\n").unwrap();fs::write(&foreign,b"FOREIGN UNCHANGED\n").unwrap();
    let before_source=fs::read(&source).unwrap();let before_foreign=fs::read(&foreign).unwrap();
    let head=std::env::var("DT_SOURCE_HEAD").unwrap();let mut state_rows=json!({});let mut delivery_rows=json!({});
    for c in inputs["state_cases"].as_array().unwrap(){
        let(b,_rx,_)=new(&root);seed(&b);let w=begin(&b,"case");b.execute(w,|_,_|Ok(pair(c,false)));
        state_rows[c["id"].as_str().unwrap()]=visible(&b);
    }
    for(name,seq)in inputs["sequences"].as_object().unwrap(){
        let(b,_rx,_)=new(&root);seed(&b);let mut rows=vec![];
        for e in seq.as_array().unwrap(){
            match e["op"].as_str().unwrap(){
                "begin"=>{begin(&b,e["job"].as_str().unwrap());},"start-over"=>{b.start_over();},
                "complete"=>{b.deliver(e["generation"].as_u64().unwrap(),e["job"].as_str().unwrap(),&pair(&inputs["state_cases"][e["case"].as_u64().unwrap()as usize],e["cancelled"]==true));},_=>panic!("unknown input")
            }
            let core=b.core.lock().unwrap();let generation=core.app.generation();let active=core.app.active_job().map(str::to_string);drop(core);
            rows.push(json!({"generation":generation,"active_job":active,"visible":visible(&b)}));
        }delivery_rows[name]=json!(rows);
    }
    let mut frame_rows=json!({});let mut frame_raw=json!({});
    for c in frame_inputs.as_array().unwrap(){
        let(b,_rx,_)=new(&root);seed(&b);let mut captured=vec![];
        for e in c["events"].as_array().unwrap(){
            let event=e.as_str().unwrap();match event{
                "begin-A"=>{begin(&b,"A");},"begin-B"=>{begin(&b,"B");},"start-over"=>{b.start_over();},"set-label"=>{b.set_label("Music");},
                "current-success-88200"=>{b.deliver(1,"A",&pair(&inputs["state_cases"][0],false));},
                "A-success"=>{b.deliver(1,"A",&pair(&inputs["state_cases"][0],false));},
                "cancelled-A-success"=>{b.deliver(1,"A",&pair(&inputs["state_cases"][0],true));},
                "current-valid-overage-1"|"current-valid-overage-8467200"|"current-valid-overage-max-safe"|"duplicate-overage"|"wrong-nonce-overage"=>{
                    let excess=match event{"current-valid-overage-8467200"=>8467200,"current-valid-overage-max-safe"=>9007199254740991u64-158760000,_=>1};
                    b.deliver(1,"A",&refusal("INGEST_TOO_LONG",Value::Null,Some(excess),event=="wrong-nonce-overage"));
                },
                "current-generic-failure"=>{b.deliver(1,"A",&pair(&inputs["state_cases"][4],false));},
                "exit0-no-pair-with-count"=>{b.deliver(1,"A",&pair(&inputs["state_cases"][1],false));},
                "progress-100-percent"=>{},"snapshot"=>{},_=>panic!("unissued frame event")
            }
            captured.push(json!({"event":event,"snapshot":b.snapshot()}));
        }
        frame_rows[c["id"].as_str().unwrap()]=json!(b.snapshot().total_frames);frame_raw[c["id"].as_str().unwrap()]=json!(captured);
    }
    save(&out.join("frames.raw.json"),&frame_raw);
    save(&out.join("frames.json"),&json!({"source_head":head,"evidence_class":"production bridge / controlled order","raw_refs":["frames.raw.json"],"adapter_ref":"host/app/tests/bridge_component.rs","rows":frame_rows,"inverse_bar_reconstruction":false,"progress_as_frames":false,"native_ui":false,"actual_snapshot_refs":["frames.raw.json"],"accepted_gate_refs":["src/state.rs:finish_job","src/bridge.rs:deliver"],"typed_outcome_refs":["host/app/tests/bridge_component.rs:pair/refusal"]}));
    let(b,rx,_)=new(&root);let f=&inputs["folders"];
    drop_model(&b,json!([f[0]]));let w1=next(&rx);let first=w1.folders.clone();
    drop_model(&b,json!([f[1],f[2]]));let w2=next(&rx);let second=w2.folders.clone();let admitted=folders(&b);
    let mut invalid=vec![];for p in inputs["invalid_payloads"].as_array().unwrap(){let(x,r,_)=new(&root);drop_model(&x,p.clone());invalid.push(count(&r));}
    let mut classified=json!({});for key in ["single_file","mixed","symlink","unknown_identity"]{
        let(x,r,_)=new(&root);drop_model(&x,json!([f[0]]));let _=next(&r);let before=folders(&x);
        let p=match key{"single_file"=>json!(["song.wav"]),"mixed"=>json!([f[1],"song.wav"]),"symlink"=>json!(["symlink"]),_=>json!(["unknown-identity-folder"])};
        drop_model(&x,p);let workers:Vec<_>=r.try_iter().filter_map(|m|if let Message::Check(w)=m{Some(w)}else{None}).collect();
        classified[key]=json!({"new_workers":workers.len(),"accepted_before":before,"accepted_after":folders(&x),"forwarded_to_ingest":workers.iter().any(|w|w.folders.contains(&PathBuf::from("unknown-identity-folder")))});
    }
    let(x,r,_)=new(&root);drop_model(&x,json!([f[0]]));let _=next(&r);drop_model(&x,json!(["alias"]));let duplicate=json!({"new_workers":count(&r),"accepted_after":folders(&x)});
    let(lock,_,_)=new(&root);seed(&lock);let w=begin(&lock,"probe");lock.execute(w,|_,_|{
        let acquired=lock.core.try_lock().is_ok();if acquired{lock.note("coordinator-lock-acquired");}Ok(pair(&inputs["state_cases"][0],false))
    });
    let lock_probe:Vec<_>=lock.trace.lock().unwrap().iter().filter(|s|["worker-enter","coordinator-lock-acquired","completion-delivered"].contains(&s.as_str())).cloned().collect();
    let(ordered,r,_)=new(&root);drop_model(&ordered,json!([f[0]]));let old=next(&r);
    let(entered_tx,entered_rx)=mpsc::channel();let(release_tx,release_rx)=mpsc::channel();let run=ordered.clone();let c=inputs["state_cases"][0].clone();
    let worker=thread::spawn(move||run.execute(old,|_,_|{entered_tx.send(()).unwrap();release_rx.recv().unwrap();Ok(pair(&c,false))}));
    entered_rx.recv_timeout(Duration::from_secs(3)).unwrap();drop_model(&ordered,json!([f[1],f[2]]));let replacement=next(&r);
    let ui_returned_before_release=!worker.is_finished();release_tx.send(()).unwrap();worker.join().unwrap();
    ordered.execute(replacement,|_,_|{ordered.note("replacement-worker-start");Ok(pair(&inputs["state_cases"][0],false))});
    let raw_cleanup=ordered.trace.lock().unwrap().clone();
    let cleanup_order:Vec<_>=raw_cleanup.iter().filter_map(|s|match s.as_str(){"cancel-request"=>Some("cancel-request"),"worker-terminal"=>Some("old-worker-terminal"),"remove-owned-job"=>Some("remove-old-owned-job"),"replacement-worker-start"=>Some("replacement-worker-start"),_=>None}).take(4).collect();
    let(reset,r,events)=new(&root);drop_model(&reset,json!([f[0]]));let work=next(&r);
    let(tx,entered)=mpsc::channel();let(release,wait)=mpsc::channel();let run=reset.clone();let c=inputs["state_cases"][0].clone();
    let worker=thread::spawn(move||run.execute(work,|_,_|{tx.send(()).unwrap();wait.recv().unwrap();Ok(pair(&c,false))}));
    entered.recv_timeout(Duration::from_secs(3)).unwrap();reset.start_over();let empty_before_terminal=reset.snapshot().view=="empty";release.send(()).unwrap();worker.join().unwrap();
    let raw_reset=reset.trace.lock().unwrap().clone();let reset_order:Vec<_>=raw_reset.iter().filter(|s|["invalidate-current","cancel-request","empty-view","worker-terminal","remove-owned-job"].contains(&s.as_str())).cloned().collect();
    let stale_before=events.lock().unwrap().len();reset.deliver(1,"other",&pair(&inputs["state_cases"][0],false));let stale_emissions=events.lock().unwrap().len()-stale_before;
    let(done,done_rx,emissions)=new(&root);seed(&done);let w=begin(&done,"A");done.execute(w,|_,_|Ok(pair(&inputs["state_cases"][0],false)));let before=emissions.lock().unwrap().len();done.deliver(1,"A",&pair(&inputs["state_cases"][3],false));let duplicate_emissions=emissions.lock().unwrap().len()-before;
    let mut raw=pair(&inputs["state_cases"][4],false);raw.stderr="raw\r\n<unsafe>& stderr".into();let work=begin(&done,"raw-details");done.execute(work,|_,_|Ok(raw));let actual_details=done.raw_details();done.set_label("Music");let label_jobs=count(&done_rx);
    // Production resolver/current executable and production Command construction, no spawn.
    let exe=std::env::current_exe().unwrap();let dir=exe.parent().unwrap();let original=PathBuf::from(std::env::var("DT_BRIDGE_INGEST").unwrap());fs::copy(original,dir.join("ingest.exe")).unwrap();
    let foreign_cwd=root.join("foreign-cwd");fs::create_dir(&foreign_cwd).unwrap();let old_cwd=std::env::current_dir().unwrap();std::env::set_current_dir(&foreign_cwd).unwrap();
    let bin=children::resolve(&children::INGEST).unwrap();let job=jobdir::create(&root,"request").unwrap();let paths:Vec<PathBuf>=f.as_array().unwrap().iter().map(|x|PathBuf::from(x.as_str().unwrap())).collect();
    let(cmd,receipt)=ingest_job::command(&bin,VERSION,&job,&paths);
    let request=json!({"tool":"ingest","binary_sha256":children::INGEST.sha256,"report_version":VERSION,"shell":false,"elevated":false,"length_seconds":3600,"folders":paths,"argv":receipt.argv,"resolved_child":cmd.get_program(),"executable_dir":dir,"private_root":root,"job":job.dir,"control":job.control,"dest":receipt.dest,"report":receipt.report,"nonce":receipt.nonce,"cwd":cmd.get_current_dir(),"invoker_cwd":std::env::current_dir().unwrap()});
    std::env::set_current_dir(old_cwd).unwrap();jobdir::remove(&job);
    save(&out.join("bridge.raw.json"),&json!({"cleanup_trace":raw_cleanup,"reset_trace":raw_reset,"empty_before_terminal":empty_before_terminal,"ui_returned_before_release":ui_returned_before_release,"request":request,"state_rows":state_rows,"delivery_rows":delivery_rows}));
    save(&out.join("bridge.json"),&json!({"source_head":head,"evidence_class":"production bridge / controlled order","raw_refs":["bridge.raw.json","frames.raw.json"],"adapter_ref":"host/app/tests/bridge_component.rs","actual_os_race":false,"native_ui":false,"real_child_executed":false,
        "capabilities":{"discovery":false,"make":false,"elevation":false,"raw_device":false,"shipping_fake_switch":false},"state_rows":state_rows,"delivery_rows":delivery_rows,
        "label_jobs":label_jobs,"details_text":actual_details,"stderr_selected_outcome":state_rows["stderr-is-not-id"]["category"]!="generic",
        "valid_drop_workers":[first,second],"accepted_folders":admitted,"invalid_payload_workers":invalid,"classified_drops":classified,"same_identity_duplicate":duplicate,"lock_probe":lock_probe,"cleanup_order":cleanup_order,"start_over_order":reset_order,
        "stale_emissions":stale_emissions,"duplicate_emissions":duplicate_emissions,"auto_relaunches":count(&rx),"ui_thread_waits_for_worker":!ui_returned_before_release,"foreign_sentinel_before":before_foreign,"foreign_sentinel_after":fs::read(&foreign).unwrap(),"source_before":before_source,"source_after":fs::read(&source).unwrap(),"external_cleanup_calls":[],"request":request,
        "linkage_refs":["host/app/src/bridge.rs","host/app/src/ingest_job.rs"],"unchanged_backend_blobs":["report.rs:b51d9d984461fe43b286df44da024505f9c8de1c","messages.rs:6d941f1e82238a452ac38eccce14d4dab16b9918","jobdir.rs:7f69618a59153618cbb3b02e467afe4d4cbe8904"],"tauri_entry_refs":["host/app/src/main.rs"]}));
    // Composed backend->renderer inputs: outcome copy/count comes from actual App.
    let screen:Value=serde_json::from_slice(&fs::read(std::env::var("DT_SCREEN_INPUT").unwrap()).unwrap()).unwrap();
    let mut views=json!({});
    for v in screen["views"].as_array().unwrap(){
        let id=v["id"].as_str().unwrap();if id.contains("projection-only"){continue;}
        let(x,_r,_)=new(&root);x.set_label(v["label"].as_str().unwrap());
        if id=="folders-only"{drop_model(&x,json!(["song.wav"]));}
        else if id!="empty"{
            seed(&x);let work=begin(&x,"screen");
            if id!="checking"{
                let mut outcome=match id{
                    "ready-two-seconds"=>pair(&inputs["state_cases"][0],false),
                    "exact-fit"=>{let mut o=pair(&inputs["state_cases"][0],false);o.total_frames=Some(158760000);o},
                    "overage-1"=>refusal("INGEST_TOO_LONG",Value::Null,Some(1),false),
                    "overage-8467200"=>refusal("INGEST_TOO_LONG",Value::Null,Some(8467200),false),
                    "protected"=>refusal("SOURCE_PROTECTED",json!("0/song.wav"),None,false),
                    "unusable"=>refusal("SOURCE_CORRUPT",json!("0/song.wav"),None,false),
                    "folder-content"=>refusal("FOLDER_EMPTY",json!("0"),None,false),
                    "escaped-name"=>refusal("SOURCE_CORRUPT",json!("0/<img src=x onerror=alert(1)>.wav"),None,false),
                    "generic"=>pair(&inputs["state_cases"][4],false),_=>panic!("unknown screen fixture")
                };
                outcome.stderr=v["details"].as_str().unwrap().into();x.execute(work,|_,_|Ok(outcome));
            }
        }
        views[id]=json!({"view":x.snapshot(),"details":x.raw_details()});
    }
    let transport:Value=serde_json::from_slice(&fs::read("docs/REVIEW/software562/screen-run3/screen-observations.json").unwrap()).unwrap();let mut drops=json!({});let mut drop_raw=json!({});
    for(id,batches)in transport["drop_transport"].as_object().unwrap(){
        let(x,r,_)=new(&root);let mut accepted_batches=vec![];let mut checks=0;let mut snapshots=vec![];
        for batch in batches.as_array().unwrap(){
            let before=x.core.lock().unwrap().app.folders.len();drop_model(&x,batch.clone());
            checks+=count(&r);let all=x.core.lock().unwrap().app.folders.clone();
            if all.len()>before{accepted_batches.push(all[before..].to_vec());}
            snapshots.push(json!({"transport":batch,"view":x.snapshot(),"accepted":folders(&x)}));
        }
        drops[id]=json!({"accepted":folders(&x),"accepted_check_requests":checks,"transport_batches":batches,"accepted_batches":accepted_batches,"sentence":x.snapshot().message});drop_raw[id]=json!(snapshots);
    }
    let(reset,_,_)=new(&root);seed(&reset);reset.set_label("old");let w=begin(&reset,"reset-composed");reset.execute(w,|_,_|Ok(pair(&inputs["state_cases"][3],false)));reset.start_over();
    save(&out.join("screen-host.json"),&json!({"source_head":head,"views":views,"drops":drops,"drop_raw":drop_raw,"start_over":{"accepted":folders(&reset),"label":reset.snapshot().label,"details":reset.raw_details(),"state":visible(&reset)["view"],"frames":reset.snapshot().total_frames,"make_disabled":!reset.snapshot().make_enabled},"live_card_line":reset.snapshot().card_line}));
    fs::remove_dir_all(root).unwrap();
}
