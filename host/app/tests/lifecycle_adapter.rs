//! Test-only adapter over actual production state, delivery gate, directories and runner.
//! No UI, oracle implementation, alternate child or shipping switch.
use dtapp::{ingest_job::{self, Outcome, RunReceipt}, jobdir, messages, report::{self, Tool}, state::App};
use serde_json::{json, Value};
use sha2::{Digest, Sha256};
use std::{fs, path::{Path, PathBuf}, sync::{Arc, atomic::AtomicBool}};
const VERSION: &str = "0.1.1 INGEST-1 arithmetic-profile INGEST1-AP4";
const PIN: &str = "3895f3f356c91b8a9fe870c33694da64bf2765df308bef118d657c1be4bb9a20";
fn sha(p: &Path) -> String { Sha256::digest(fs::read(p).unwrap()).iter().map(|b|format!("{b:02x}")).collect() }
fn outcome(c: &Value, cancelled: bool) -> Outcome {
 let exit=c["exit"].as_i64().unwrap() as i32;
 Outcome {exit:Some(exit),stderr:c["stderr"].as_str().unwrap().into(),reading:report::read(c["report"].as_str().unwrap().as_bytes(),Tool::Ingest,&"a".repeat(32),VERSION,exit,1),total_frames:if c["pair"]==true {Some(88200)}else{None},cancelled}
}
fn visible(a: &App) -> Value {
 let v=a.view();
 let view=if v.checking {"Checking"}else{match v.view {"empty"=>"Empty","ready"=>"Ready",_=>"Problem"}};
 let category=if view=="Ready" {json!("success")}else if view=="Problem" {
  if v.message.as_deref()==Some(messages::GENERIC_INGEST) {json!("generic")}else if v.message.as_deref().unwrap_or("").contains("isn't music") {json!("folder-nonmusic")}else{json!("UNCLASSIFIED")}
 }else{Value::Null};
 json!({"view":view,"category":category,"total_frames":if view=="Ready" {v.bar.map(|x|(x*158760000.0).round() as u64)}else{None},"details":a.details,"make_enabled":v.make_enabled})
}
fn save(p: &Path, v: &Value) { fs::write(p,serde_json::to_vec_pretty(v).unwrap()).unwrap(); }
fn main() {
 let args:Vec<String>=std::env::args().collect();assert_eq!(args.len(),5,"adapter WORK CASES BINARY FIXTURE");
 let work=PathBuf::from(&args[1]);let cases:Value=serde_json::from_slice(&fs::read(&args[2]).unwrap()).unwrap();let bin=PathBuf::from(&args[3]);let fixture=PathBuf::from(&args[4]);
 assert!(!work.exists());fs::create_dir(&work).unwrap();assert_eq!(sha(&bin),PIN);
 let music=work.join("Music");fs::create_dir(&music).unwrap();fs::copy(&fixture,music.join("song.wav")).unwrap();
 let input_sha=sha(&music.join("song.wav"));assert_eq!(input_sha,"48f1b3c7ce7fe27a90469364f841803087a9d274a4af9a4ec8ee195a2846ac18");
 let empty=work.join("Empty");fs::create_dir(&empty).unwrap();let sentinel=work.join("foreign.txt");fs::write(&sentinel,b"UNCHANGED\n").unwrap();let sentinel_sha=sha(&sentinel);
 let data=work.join("app-private");jobdir::prepare(&data).unwrap();
 let mut trace=json!({"source_head":option_env!("DT_SOURCE_HEAD").unwrap_or("UNBOUND"),"scope":"backend lifecycle only","raw_refs":["trace.raw.json","raw/P0/receipt.json","raw/P1/receipt.json"],"elevated":false,"shipping_test_switch":false,"make_enabled":false,"state_rows":{},"delivery_rows":{}});
 for c in cases["state_cases"].as_array().unwrap() {
  let mut app=App::default();app.folders=vec![PathBuf::from("Music")];app.finished(&outcome(c,false));
  trace["state_rows"][c["id"].as_str().unwrap()]=visible(&app);
 }
 for (name,events) in cases["sequences"].as_object().unwrap() {
  let mut app=App::default();app.folders=vec![PathBuf::from("Music")];let mut rows=Vec::new();
  for event in events.as_array().unwrap() {
   match event["op"].as_str().unwrap() {
    "begin"=>{app.begin_job(event["job"].as_str().unwrap());},
    "start-over"=>app.start_over(),
    "complete"=>{let c=&cases["state_cases"][event["case"].as_u64().unwrap() as usize];app.finish_job(event["generation"].as_u64().unwrap(),event["job"].as_str().unwrap(),&outcome(c,event["cancelled"]==true));},
    _=>panic!("unissued event")
   }
   rows.push(json!({"generation":app.generation(),"active_job":app.active_job(),"visible":visible(&app)}));
  }
  trace["delivery_rows"][name]=json!(rows);
 }
 save(&work.join("trace.partial.json"),&trace);
 let collision=jobdir::create(&data,"collision").unwrap();let marker=fs::read(collision.dir.join(jobdir::MARKER)).unwrap();
 let exclusive=jobdir::create(&data,"collision").is_err();let unchanged=fs::read(collision.dir.join(jobdir::MARKER)).unwrap()==marker;
 let foreign=data.join("jobs/foreign");fs::create_dir(&foreign).unwrap();fs::write(foreign.join("keep"),b"FOREIGN\n").unwrap();
 let mut raw_rows=Vec::new();let mut exits=Vec::new();let mut totals=Vec::new();let mut ids=Vec::new();let mut removed=Vec::new();let mut pair_present=Vec::new();let mut bound=Vec::new();let mut private_reports=Vec::new();
 for (name,folder) in [("P0",&music),("P1",&empty)] {
  let job=jobdir::create(&data,name).unwrap();let mut app=App::default();let next=app.dropped(&[folder.clone()]);let generation=app.begin_job(name);let checking=app.view().checking;
  let cancel=Arc::new(AtomicBool::new(false));let deadline=cancel.clone();std::thread::spawn(move||{std::thread::sleep(std::time::Duration::from_secs(120));deadline.store(true,std::sync::atomic::Ordering::SeqCst);});
  let mut receipt=RunReceipt::default();let o=ingest_job::run_recorded(&bin,VERSION,&job,&[folder.clone()],cancel,&mut receipt);
  let applied=app.finish_job(generation,name,&o);let raw=work.join("raw").join(name);fs::create_dir_all(&raw).unwrap();
  fs::write(raw.join("stdout.bin"),&receipt.stdout).unwrap();fs::write(raw.join("stderr.bin"),&receipt.stderr).unwrap();
  if let Some(bytes)=&receipt.report_bytes {fs::write(raw.join("report.jsonl"),bytes).unwrap();}
  save(&raw.join("receipt.json"),&serde_json::to_value(&receipt).unwrap());
  let pair=receipt.dest.join("audio.wav").is_file()&&receipt.dest.join("manifest.json").is_file();let mut manifest=Value::Null;
  if pair {for n in ["audio.wav","manifest.json"] {fs::copy(receipt.dest.join(n),raw.join(n)).unwrap();}manifest=serde_json::from_slice(&fs::read(receipt.dest.join("manifest.json")).unwrap()).unwrap();}
  let id=match &o.reading {report::Reading::Usable{refusal:Some(r),..}=>Some(r.id.clone()),_=>None};
  bound.push(matches!(&o.reading,report::Reading::Usable{..}) && receipt.pid.is_some() && receipt.version==VERSION && receipt.exit==o.exit);
  private_reports.push(receipt.report.starts_with(&job.control) && !receipt.report.starts_with(&receipt.dest) && !receipt.report.starts_with(folder));
  raw_rows.push(json!({"case":name,"drop_next":format!("{next:?}"),"checking":checking,"generation":generation,"applied":applied,"visible":visible(&app),"receipt":"receipt.json","pair_present":pair,"total_frames":o.total_frames,"manifest":manifest,"refusal":id}));
  exits.push(o.exit);totals.push(o.total_frames);ids.push(id);pair_present.push(pair);removed.push(jobdir::remove(&job));
  save(&work.join("trace.raw.json"),&json!(raw_rows));
 }
 let superseded=jobdir::create(&data,"superseded").unwrap();fs::write(superseded.control.join("partial"),b"owned partial").unwrap();let superseded_removed=jobdir::remove(&superseded);
 let no_external_cleanup=jobdir::clean_stale(&data)==1 && foreign.join("keep").exists();
 trace["ordinary_job_files"]=json!({"exclusive_second_create_refused":exclusive,"collision_bytes_unchanged":unchanged,"control_out_distinct":collision.control!=collision.out,"under_app_private_root":collision.dir.starts_with(&data),"report_outside_sources_dest_stage":private_reports.iter().all(|x|*x),"own_completed_job_removed":removed.iter().all(|x|*x),"own_superseded_job_removed":superseded_removed,"foreign_sibling_unchanged":fs::read(foreign.join("keep")).unwrap()==b"FOREIGN\n","source_bytes_unchanged":sha(&music.join("song.wav"))==input_sha&&sha(&fixture)==input_sha,"sentinel_bytes_unchanged":sha(&sentinel)==sentinel_sha,"raw_refs":["trace.raw.json","filesystem.private.json"],"no_external_cleanup":no_external_cleanup});
 trace["real_runner"]=json!({"pinned_original_s1":sha(&bin)==PIN,"current_nonce_version_exit_end_bound":bound.iter().all(|x|*x),"actual_source_runner":true,"binary_sha256":PIN,"child_source":"35b23cacae886d9b3693b7104f581d8646ea5667","report_version":VERSION,"p0_exit":exits[0],"p0_exact_pair_frames":totals[0],"p1_exit":exits[1],"p1_id":ids[1],"p1_no_dest":!pair_present[1],"raw_refs":["raw/P0/receipt.json","raw/P1/receipt.json","trace.raw.json"],"fake_child":false});
 save(&work.join("filesystem.private.json"),&json!({"data":data,"collision_marker_original":marker,"collision_exists_after_cleanup":collision.dir.exists(),"foreign":foreign,"foreign_bytes":fs::read(foreign.join("keep")).unwrap(),"source_sha256":input_sha,"sentinel_sha256":sentinel_sha,"completed_removed":removed,"superseded_removed":superseded_removed}));
 save(&work.join("trace.json"),&trace);
}
