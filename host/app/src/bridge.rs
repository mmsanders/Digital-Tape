//! One production coordinator, a serial ingest worker and a single-flight discovery poller.
//! App owns current-result acceptance.
use crate::{children, diagnostics::{Route, Session}, discovery::{self, Judged, Ran, Request}, drops, ingest_job::{self, Outcome, RunReceipt}, jobdir, state::{App, Next, View}};
use serde_json::Value;
use std::{cell::Cell, path::PathBuf, sync::{Arc, Mutex, Weak, mpsc, atomic::{AtomicBool, Ordering}}, thread, time::{Duration, Instant}};

/// `drop_id` names the receipt ingress that scheduled this work (diagnostics ON only).
pub struct Work { pub id:String, pub generation:u64, pub folders:Vec<PathBuf>, pub cancel:Arc<AtomicBool>, pub drop_id:Option<String> }
enum Message { Check(Work), Stop }
// `stopped` is set under this lock by shutdown, so a discovery run is either registered
// before shutdown's cancellation pass or refused; none crosses that boundary.
struct Core { app:App, cancel:Option<Arc<AtomicBool>>, active:Option<(String,u64)>, cards_cancel:Option<Arc<AtomicBool>>, stopped:bool }
type Effect=dyn Fn(View)->Result<(),String>+Send+Sync;
/// The launch callback a discovery run calls once its child exists, before any wait.
type Launched<'a>=&'a mut dyn FnMut(&Ran,&Request);
pub struct Bridge {
    core:Mutex<Core>,
    // Mutations/publications are serialized; emit never holds the core lock.
    // The effect reports a failed delivery (production: the Tauri emit); only discovery
    // receipts record it, and no outcome depends on it.
    publication:Mutex<()>, data:PathBuf, emit:Arc<Effect>,
    sender:mpsc::Sender<Message>, worker:Mutex<Option<thread::JoinHandle<()>>>,
    stop_polls:AtomicBool, poller:Mutex<Option<thread::JoinHandle<()>>>,
    /// APP-1A §8 opt-in receipts; None (the default) means no diagnostic I/O at all.
    diag:Option<Arc<Session>>,
    #[cfg(test)] trace:Mutex<Vec<String>>,
    /// Controlled tests pause a due poll here, after its stop read and before registration.
    #[cfg(test)] before_admission:Mutex<Option<Box<dyn FnOnce()+Send>>>,
}
impl Bridge {
    #[cfg(test)]
    fn channel(data:PathBuf,emit:Arc<dyn Fn(View)+Send+Sync>)->(Arc<Self>,mpsc::Receiver<Message>) {Self::channel_with(data,emit,None)}
    #[cfg(test)]
    fn channel_with(data:PathBuf,emit:Arc<dyn Fn(View)+Send+Sync>,diag:Option<Arc<Session>>)->(Arc<Self>,mpsc::Receiver<Message>) {
        Self::channel_effect(data,Arc::new(move|v|{emit(v);Ok(())}),diag)
    }
    fn channel_effect(data:PathBuf,emit:Arc<Effect>,diag:Option<Arc<Session>>)->(Arc<Self>,mpsc::Receiver<Message>) {
        let(sender,receiver)=mpsc::channel();
        (Arc::new(Self{core:Mutex::new(Core{app:App::default(),cancel:None,active:None,cards_cancel:None,stopped:false}),publication:Mutex::new(()),data,emit,sender,worker:Mutex::new(None),
            stop_polls:AtomicBool::new(false),poller:Mutex::new(None),diag,#[cfg(test)]trace:Mutex::new(Vec::new()),#[cfg(test)]before_admission:Mutex::new(None)}),receiver)
    }
    pub fn new(data:PathBuf,emit:impl Fn(View)+Send+Sync+'static)->Arc<Self> {Self::with_diagnostics(data,move|v|{emit(v);Ok(())},None)}
    /// The one production coordinator; `diag` is Some only for an opted-in launch.
    pub fn with_diagnostics(data:PathBuf,emit:impl Fn(View)->Result<(),String>+Send+Sync+'static,diag:Option<Session>)->Arc<Self> {
        let(bridge,receiver)=Self::channel_effect(data,Arc::new(emit),diag.map(Arc::new));
        let weak:Weak<Self>=Arc::downgrade(&bridge);
        let worker=thread::spawn(move||while let Ok(message)=receiver.recv(){
            let Message::Check(work)=message else{break};
            let Some(bridge)=weak.upgrade() else{break};
            bridge.execute_with(work,|job,work,receipt,spawned|{
                let bin=children::resolve(&children::INGEST).map_err(|e|e.0)?;
                Ok(ingest_job::run_hooked(&bin,children::INGEST.version.unwrap_or_default(),job,&work.folders,work.cancel.clone(),receipt,spawned))
            });
        });
        *bridge.worker.lock().unwrap()=Some(worker);
        // A build without a pinned discovery child keeps its truthful card line and never polls.
        if children::TAPECTL.sha256.is_some(){
            let weak=Arc::downgrade(&bridge);
            *bridge.poller.lock().unwrap()=Some(thread::spawn(move||Self::poll(weak)));
        }
        bridge
    }
    fn poll(weak:Weak<Self>){
        let clock=Instant::now();let ms=||clock.elapsed().as_millis() as u64;
        let mut schedule=discovery::Schedule::new(0);
        loop{
            let Some(bridge)=weak.upgrade() else{break};
            if !bridge.poll_once(&mut schedule,&ms,Self::run_cards){break}
            drop(bridge);thread::sleep(Duration::from_millis(50));
        }
    }
    /// One poller step; false once polls are stopped. The stop read here is only a fast
    /// exit: `discover` rechecks under the core lock before registering a run.
    fn poll_once(&self,schedule:&mut discovery::Schedule,ms:&dyn Fn()->u64,
        run:impl FnOnce(&jobdir::Job,&AtomicBool,&mut dyn FnMut(),&mut dyn FnMut(),Launched)->(Ran,Request))->bool{
        if self.stop_polls.load(Ordering::SeqCst){return false}
        // S3 Make does not exist in this build, so discovery is never paused for Making.
        if schedule.tick(ms(),false,false){
            #[cfg(test)]if let Some(pause)=self.before_admission.lock().unwrap().take(){pause()}
            self.discover(run);schedule.terminal(ms());
        }
        true
    }
    /// The production discovery child: the pinned tapectl beside the app, cards only.
    fn run_cards(job:&jobdir::Job,cancel:&AtomicBool,on_timeout:&mut dyn FnMut(),on_cancel:&mut dyn FnMut(),launched:Launched)->(Ran,Request){
        let version=children::TAPECTL.version.unwrap_or_default();
        match children::resolve(&children::TAPECTL){
            Ok(bin)=>{let(cmd,request)=discovery::command(&bin,version,job);let ran=discovery::run(cmd,&request,cancel,on_timeout,on_cancel,&mut|r|launched(r,&request));(ran,request)}
            Err(e)=>(Ran{spawn_error:Some(e.0),..Default::default()},Request{version:version.into(),..Default::default()}),
        }
    }
    /// One discovery run, shared by the poller and controlled tests: a fresh ticket and owned
    /// job, the child, current-only publication, then removal of only this run's job.
    /// With diagnostics ON each step is also recorded (cards-1); nothing waits on it.
    fn discover(&self,run:impl FnOnce(&jobdir::Job,&AtomicBool,&mut dyn FnMut(),&mut dyn FnMut(),Launched)->(Ran,Request))->Option<(Ran,Request,Judged)>{
        let(ticket,cancel)={let mut core=self.core.lock().unwrap();
            if core.stopped{drop(core);self.note("cards:admission-refused");if let Some(d)=&self.diag{d.cards_admission_refused();}return None}
            let cancel=Arc::new(AtomicBool::new(false));core.cards_cancel=Some(cancel.clone());(core.app.begin_cards(),cancel)};
        self.note("cards:worker-start");
        let created=jobdir::create(&self.data,&format!("cards-{}",children::nonce()));
        let failed=created.as_ref().err().map(|e|format!("Card check failed: cannot create the app's own folder: {e}"));
        let rid=self.diag.as_ref().map(|d|d.cards_admit(ticket,match &created{Ok(job)=>Ok(job.dir.as_path()),Err(_)=>Err(failed.as_deref().unwrap_or_default())}));
        let diag=self.diag.as_deref().zip(rid.as_deref());
        let job=match created{
            Ok(job)=>job,
            Err(_)=>{
                let why=failed.unwrap_or_default();
                if let Some((d,r))=diag{d.cards_not_launched(r,ticket,&why);}
                self.publish_cards(ticket,&Judged{hint:None,id_specific:None},why,rid.as_deref());
                if let Some((d,r))=diag{d.cards_cleanup(r,ticket,None,false);}
                return None}
        };
        let launched=Cell::new(false);
        let(ran,request)=run(&job,&cancel,&mut||self.invalidate_cards(ticket,true,rid.as_deref()),&mut||self.note("cards:cancel"),
            &mut|r,q|{launched.set(true);if let Some((d,id))=diag{d.cards_launch(id,ticket,r,q);}});
        self.note("cards:child-terminal");
        if let Some((d,r))=diag{
            if launched.get(){d.cards_terminal(r,ticket,&ran);}
            else{d.cards_not_launched(r,ticket,ran.spawn_error.as_deref().unwrap_or("no child was started"));}
        }
        let judged=discovery::judge(ran.exit,&ran.stdout,ran.report.as_deref(),&request.nonce,&request.version);
        self.publish_cards(ticket,&judged,discovery::details(&ran,&judged),rid.as_deref());
        // Originals are kept after publication and before the job they live in is removed.
        if let(Some((d,r)),true)=(diag,launched.get()){d.cards_capture(r,ticket,&ran,&request);}
        // Sole target is this run's freshly created Job, only after the child's terminal.
        let removed=jobdir::remove(&job);self.note("cards:remove-owned-job");
        if let Some((d,r))=diag{d.cards_cleanup(r,ticket,Some(&job.dir),removed);}
        let mut core=self.core.lock().unwrap();
        if core.cards_cancel.as_ref().is_some_and(|c|Arc::ptr_eq(c,&cancel)){core.cards_cancel=None;}
        Some((ran,request,judged))
    }
    /// The state a card publication leaves, for its receipt.
    fn cards_ref(view:&View,generation:u64)->String{format!("view={} card_line={:?} card_details_available={} generation={}",view.view,view.card_line,view.card_details_available,generation)}
    fn publish_cards(&self,ticket:u64,judged:&Judged,details:String,rid:Option<&str>){
        let _serial=self.publication.lock().unwrap();
        let(current,view,state)={let mut core=self.core.lock().unwrap();let current=core.app.finish_cards(ticket,judged,details);
            let view=core.app.view();let state=Self::cards_ref(&view,core.app.generation());(current,view,state)};
        let diag=self.diag.as_deref().zip(rid);
        if let Some((d,r))=diag{d.cards_publication_attempt(r,ticket,if current{"publish"}else{"stale-drop"},&state);}
        if !current{self.note("cards:stale-dropped");if let Some((d,r))=diag{d.cards_publication(r,ticket,&state,"stale-dropped",None);}return}
        let delivered=(self.emit)(view);self.note("cards:published");
        if let Some((d,r))=diag{match &delivered{Ok(())=>d.cards_publication(r,ticket,&state,"published",None),Err(e)=>d.cards_publication(r,ticket,&state,"failed",Some(e))}}
    }
    /// A timeout: this run stops being current and the old hint is cleared before the child is stopped.
    fn invalidate_cards(&self,ticket:u64,timed_out:bool,rid:Option<&str>){
        let _serial=self.publication.lock().unwrap();
        let why=timed_out.then(||"Card check failed: tapectl cards took too long and was stopped.".to_owned());
        let view={let mut core=self.core.lock().unwrap();let changed=core.app.invalidate_cards(ticket,why);self.note("cards:invalidate-current");changed.then(||core.app.view())};
        if let(Some(d),Some(r),true)=(&self.diag,rid,timed_out){d.cards_invalidate(r,ticket,view.is_some());}
        if let Some(view)=view{let _=(self.emit)(view);}
    }
    fn note(&self,event:&str){
        #[cfg(test)]self.trace.lock().unwrap().push(event.to_owned());
        #[cfg(not(test))]let _=event;
    }
    pub fn snapshot(&self)->View{self.core.lock().unwrap().app.view()}
    pub fn raw_details(&self)->String{
        let core=self.core.lock().unwrap();let(ingest,cards)=(&core.app.details,&core.app.cards.details);
        if cards.is_empty(){ingest.clone()}else if ingest.is_empty(){cards.clone()}else{format!("{ingest}\n\n{cards}")}
    }
    pub fn set_label(&self,text:&str)->View{
        let _serial=self.publication.lock().unwrap();
        let view={let mut core=self.core.lock().unwrap();core.app.set_label(text);core.app.view()};
        let _=(self.emit)(view.clone());view
    }
    #[cfg(test)]
    fn begin(core:&mut Core,id:String)->Work{Self::begin_from(core,id,None)}
    fn begin_from(core:&mut Core,id:String,drop_id:Option<String>)->Work{
        if let Some(old)=core.cancel.take(){old.store(true,Ordering::SeqCst);}
        let cancel=Arc::new(AtomicBool::new(false));core.cancel=Some(cancel.clone());
        let generation=core.app.begin_job(&id);core.active=Some((id.clone(),generation));
        Work{generation,id,folders:core.app.folders.clone(),cancel,drop_id}
    }
    /// A drop from an actual boundary: the native window callback or the Tauri command.
    pub fn drop_from(&self,route:Route,payload:Value)->View{self.drop_routed(route,payload,drops::classify)}
    #[cfg(test)]
    fn drop_using(&self,payload:Value,classify:impl FnOnce(&[PathBuf],&[PathBuf])->drops::Drop)->View{self.drop_routed(Route::ControlledTest,payload,classify)}
    fn drop_routed(&self,route:Route,payload:Value,classify:impl FnOnce(&[PathBuf],&[PathBuf])->drops::Drop)->View{
        let _serial=self.publication.lock().unwrap();
        let ingress=self.diag.as_ref().map(|d|{
            let raw:Vec<String>=payload.as_array().map(|a|a.iter().map(|x|x.as_str().map_or_else(||x.to_string(),str::to_owned)).collect()).unwrap_or_default();
            let generation=self.core.lock().unwrap().app.generation();(d.clone(),d.ingress(route,&raw,generation))
        });
        // Refused before classification: recorded with its reason, then the unchanged view.
        let refuse=|reason:&str|{let view=self.snapshot();if let Some((d,id))=&ingress{
            d.drop_decision(id,if reason=="empty"{"no-change"}else{"reject"},Some(reason),"Nothing",self.core.lock().unwrap().app.generation(),None);}view};
        let Some(array)=payload.as_array()else{return refuse("not-a-list")};
        if array.is_empty(){return refuse("empty")}
        let Some(paths)=array.iter().map(|x|x.as_str().filter(|s|!s.is_empty()&&!s.contains('\0')).map(PathBuf::from)).collect::<Option<Vec<_>>>()else{return refuse("invalid-path")};
        let(view,work)={
            let mut core=self.core.lock().unwrap();
            let classified=classify(&paths,&core.app.folders);
            let(decision,reason)=match &classified{drops::Drop::NotFolder=>("reject","not-folder"),drops::Drop::NoChange=>("no-change","no-change"),drops::Drop::Folders(_)=>("no-change","problem-shown")};
            let next=core.app.admit_drop(classified);
            let work=if next==Next::RunIngest{
                if core.cancel.is_some(){self.note("cancel-request");if let(Some((d,_)),Some((w,g)))=(&ingress,&core.active){d.cancel_request(w,*g);}}
                let work=Self::begin_from(&mut core,format!("ingest-{}",children::nonce()),ingress.as_ref().map(|x|x.1.clone()));
                if let Some((d,id))=&ingress{d.drop_decision(id,"schedule",None,"RunIngest",work.generation,Some(&work.id));}
                Some(work)
            }else{
                if let Some((d,id))=&ingress{d.drop_decision(id,decision,Some(reason),"Nothing",core.app.generation(),None);}
                None
            };(core.app.view(),work)
        };
        let _=(self.emit)(view.clone());
        if let Some(work)=work{let _=self.sender.send(Message::Check(work));}view
    }
    pub fn start_over(&self)->View{
        let _serial=self.publication.lock().unwrap();
        let view={let mut core=self.core.lock().unwrap();let old=core.app.generation();core.app.start_over();self.note("invalidate-current");
            if let Some(d)=&self.diag{if let(Some((w,g)),true)=(&core.active,core.cancel.is_some()){d.cancel_request(w,*g);}d.reset(old,core.app.generation());}
            core.active=None;
            if let Some(cancel)=core.cancel.take(){cancel.store(true,Ordering::SeqCst);self.note("cancel-request");}core.app.view()};
        let _=(self.emit)(view.clone());self.note("empty-view");view
    }
    // Both production and controlled tests enter this same worker/completion closure.
    #[cfg(test)]
    fn execute(&self,work:Work,run:impl FnOnce(&jobdir::Job,&Work)->Result<Outcome,String>){self.execute_with(work,|job,work,_,_|run(job,work))}
    /// The serial worker: admission, the child (reporting its spawn through `spawned`),
    /// current-only delivery, then removal of only this work's job. With diagnostics ON
    /// each step is also recorded; capture happens after the wait and before the removal.
    fn execute_with(&self,work:Work,run:impl FnOnce(&jobdir::Job,&Work,&mut RunReceipt,&dyn Fn(&RunReceipt))->Result<Outcome,String>){
        let diag=self.diag.as_deref().filter(|_|work.drop_id.is_some());
        if work.cancel.load(Ordering::SeqCst){if let Some(d)=diag{d.work_skipped(&work.id,work.generation);}return;}
        self.note("worker-enter");
        let job=match jobdir::create(&self.data,&work.id){Ok(job)=>job,Err(error)=>{
            if let Some(d)=diag{d.incomplete("job-directory-not-created");}
            self.fail(work.generation,&work.id,&format!("cannot create the app's own folder: {error}"));return}};
        if let(Some(d),Some(drop_id))=(diag,&work.drop_id){d.job_admit(&work.id,work.generation,drop_id,&job.dir);}
        let(mut receipt,launched)=(RunReceipt::default(),std::cell::Cell::new(false));
        let spawned=|r:&RunReceipt|{launched.set(true);if let Some(d)=diag{d.child_launch(&work.id,work.generation,r);}};
        let outcome=run(&job,&work,&mut receipt,&spawned);self.note("worker-terminal");
        if let Some(d)=diag{
            if launched.get(){d.child_terminal(&work.id,work.generation,&receipt);}
            else{d.child_not_launched(&work.id,work.generation,&match(&outcome,&receipt.spawn_error){(Err(why),_)=>why.clone(),(Ok(_),Some(e))=>e.clone(),_=>"no child was started".into()});}
        }
        let disposition=match &outcome{
            Ok(o)=>if self.deliver(work.generation,&work.id,o){"delivered"}else{"stale-dropped"},
            Err(why)=>if self.fail(work.generation,&work.id,why){"failed"}else{"stale-dropped"}};
        if let Some(d)=diag{
            d.outcome(&work.id,work.generation,disposition,&self.state_ref());
            if let(Ok(o),true)=(&outcome,launched.get()){d.capture(&work.id,work.generation,&receipt,&o.reading);}
        }
        // Sole target is this worker's freshly created Job, only after run terminates.
        let removed=jobdir::remove(&job);self.note("remove-owned-job");
        if let Some(d)=diag{d.cleanup(&work.id,work.generation,&job.dir,removed);}
    }
    fn state_ref(&self)->String{let core=self.core.lock().unwrap();let v=core.app.view();format!("view={} checking={} resets={} generation={}",v.view,v.checking,v.resets,core.app.generation())}
    fn deliver(&self,generation:u64,id:&str,outcome:&Outcome)->bool{
        let _serial=self.publication.lock().unwrap();
        let view={let mut core=self.core.lock().unwrap();if !core.app.finish_job(generation,id,outcome){return false;}core.cancel=None;core.active=None;core.app.view()};
        let _=(self.emit)(view);self.note("completion-delivered");true
    }
    fn fail(&self,generation:u64,id:&str,why:&str)->bool{
        let _serial=self.publication.lock().unwrap();
        let view={let mut core=self.core.lock().unwrap();if !core.app.fail_job(generation,id,why){return false;}core.cancel=None;core.active=None;core.app.view()};let _=(self.emit)(view);true
    }
    pub fn shutdown(&self){
        self.stop_polls.store(true,Ordering::SeqCst);self.note("stop-polls");
        {let _serial=self.publication.lock().unwrap();let mut core=self.core.lock().unwrap();core.stopped=true;
            if let Some(ticket)=core.app.cards_active(){core.app.invalidate_cards(ticket,None);self.note("cards:invalidate-current");}
            if let Some(cancel)=core.cards_cancel.take(){cancel.store(true,Ordering::SeqCst);}}
        if let Some(poller)=self.poller.lock().unwrap().take(){let _=poller.join();}
        self.start_over();let _=self.sender.send(Message::Stop);if let Some(worker)=self.worker.lock().unwrap().take(){let _=worker.join();}
        if let Some(d)=&self.diag{d.finish();}
    }
}
#[cfg(test)]
#[path="../tests/bridge_component.rs"]
mod component;
#[cfg(test)]
#[path="../tests/discovery_component.rs"]
mod discovery_component;
#[cfg(test)]
#[path="../tests/interaction_component.rs"]
mod interaction_component;
#[cfg(test)]
#[path="../tests/diagnostics_component.rs"]
mod diagnostics_component;
