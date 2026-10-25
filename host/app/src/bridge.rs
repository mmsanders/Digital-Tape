//! One production coordinator, a serial ingest worker and a single-flight discovery poller.
//! App owns current-result acceptance.
use crate::{children, discovery::{self, Judged, Ran, Request}, drops, ingest_job::{self, Outcome}, jobdir, state::{App, Next, View}};
use serde_json::Value;
use std::{path::PathBuf, sync::{Arc, Mutex, Weak, mpsc, atomic::{AtomicBool, Ordering}}, thread, time::{Duration, Instant}};

pub struct Work { pub id:String, pub generation:u64, pub folders:Vec<PathBuf>, pub cancel:Arc<AtomicBool> }
enum Message { Check(Work), Stop }
struct Core { app:App, cancel:Option<Arc<AtomicBool>>, cards_cancel:Option<Arc<AtomicBool>> }
pub struct Bridge {
    core:Mutex<Core>,
    // Mutations/publications are serialized; emit never holds the core lock.
    publication:Mutex<()>, data:PathBuf, emit:Arc<dyn Fn(View)+Send+Sync>,
    sender:mpsc::Sender<Message>, worker:Mutex<Option<thread::JoinHandle<()>>>,
    stop_polls:AtomicBool, poller:Mutex<Option<thread::JoinHandle<()>>>,
    #[cfg(test)] trace:Mutex<Vec<String>>,
}
impl Bridge {
    fn channel(data:PathBuf,emit:Arc<dyn Fn(View)+Send+Sync>)->(Arc<Self>,mpsc::Receiver<Message>) {
        let(sender,receiver)=mpsc::channel();
        (Arc::new(Self{core:Mutex::new(Core{app:App::default(),cancel:None,cards_cancel:None}),publication:Mutex::new(()),data,emit,sender,worker:Mutex::new(None),
            stop_polls:AtomicBool::new(false),poller:Mutex::new(None),#[cfg(test)]trace:Mutex::new(Vec::new())}),receiver)
    }
    pub fn new(data:PathBuf,emit:impl Fn(View)+Send+Sync+'static)->Arc<Self> {
        let(bridge,receiver)=Self::channel(data,Arc::new(emit));
        let weak:Weak<Self>=Arc::downgrade(&bridge);
        let worker=thread::spawn(move||while let Ok(message)=receiver.recv(){
            let Message::Check(work)=message else{break};
            let Some(bridge)=weak.upgrade() else{break};
            bridge.execute(work,|job,work|{
                let bin=children::resolve(&children::INGEST).map_err(|e|e.0)?;
                Ok(ingest_job::run(&bin,children::INGEST.version.unwrap_or_default(),job,&work.folders,work.cancel.clone()))
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
            if bridge.stop_polls.load(Ordering::SeqCst){break}
            // S3 Make does not exist in this build, so discovery is never paused for Making.
            if schedule.tick(ms(),false,false){bridge.discover(Self::run_cards);schedule.terminal(ms());}
            drop(bridge);thread::sleep(Duration::from_millis(50));
        }
    }
    /// The production discovery child: the pinned tapectl beside the app, cards only.
    fn run_cards(job:&jobdir::Job,cancel:&AtomicBool,on_timeout:&mut dyn FnMut(),on_cancel:&mut dyn FnMut())->(Ran,Request){
        let version=children::TAPECTL.version.unwrap_or_default();
        match children::resolve(&children::TAPECTL){
            Ok(bin)=>{let(cmd,request)=discovery::command(&bin,version,job);(discovery::run(cmd,&request,cancel,on_timeout,on_cancel),request)}
            Err(e)=>(Ran{spawn_error:Some(e.0),..Default::default()},Request{version:version.into(),..Default::default()}),
        }
    }
    /// One discovery run, shared by the poller and controlled tests: a fresh ticket and owned
    /// job, the child, current-only publication, then removal of only this run's job.
    fn discover(&self,run:impl FnOnce(&jobdir::Job,&AtomicBool,&mut dyn FnMut(),&mut dyn FnMut())->(Ran,Request))->Option<(Ran,Request,Judged)>{
        let(ticket,cancel)={let mut core=self.core.lock().unwrap();let cancel=Arc::new(AtomicBool::new(false));core.cards_cancel=Some(cancel.clone());(core.app.begin_cards(),cancel)};
        self.note("cards:worker-start");
        let job=match jobdir::create(&self.data,&format!("cards-{}",children::nonce())){
            Ok(job)=>job,
            Err(e)=>{self.publish_cards(ticket,&Judged{hint:None,id_specific:None},format!("Card check failed: cannot create the app's own folder: {e}"));return None}
        };
        let(ran,request)=run(&job,&cancel,&mut||self.invalidate_cards(ticket,true),&mut||self.note("cards:cancel"));
        self.note("cards:child-terminal");
        let judged=discovery::judge(ran.exit,&ran.stdout,ran.report.as_deref(),&request.nonce,&request.version);
        self.publish_cards(ticket,&judged,discovery::details(&ran,&judged));
        // Sole target is this run's freshly created Job, only after the child's terminal.
        jobdir::remove(&job);self.note("cards:remove-owned-job");
        let mut core=self.core.lock().unwrap();
        if core.cards_cancel.as_ref().is_some_and(|c|Arc::ptr_eq(c,&cancel)){core.cards_cancel=None;}
        Some((ran,request,judged))
    }
    fn publish_cards(&self,ticket:u64,judged:&Judged,details:String){
        let _serial=self.publication.lock().unwrap();
        let view={let mut core=self.core.lock().unwrap();if !core.app.finish_cards(ticket,judged,details){drop(core);self.note("cards:stale-dropped");return}core.app.view()};
        (self.emit)(view);self.note("cards:published");
    }
    /// A timeout: this run stops being current and the old hint is cleared before the child is stopped.
    fn invalidate_cards(&self,ticket:u64,timed_out:bool){
        let _serial=self.publication.lock().unwrap();
        let why=timed_out.then(||"Card check failed: tapectl cards took too long and was stopped.".to_owned());
        let view={let mut core=self.core.lock().unwrap();let changed=core.app.invalidate_cards(ticket,why);self.note("cards:invalidate-current");changed.then(||core.app.view())};
        if let Some(view)=view{(self.emit)(view);}
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
        (self.emit)(view.clone());view
    }
    fn begin(core:&mut Core,id:String)->Work{
        if let Some(old)=core.cancel.take(){old.store(true,Ordering::SeqCst);}
        let cancel=Arc::new(AtomicBool::new(false));core.cancel=Some(cancel.clone());
        Work{generation:core.app.begin_job(&id),id,folders:core.app.folders.clone(),cancel}
    }
    pub fn drop_paths(&self,payload:Value)->View{self.drop_using(payload,drops::classify)}
    fn drop_using(&self,payload:Value,classify:impl FnOnce(&[PathBuf],&[PathBuf])->drops::Drop)->View{
        let _serial=self.publication.lock().unwrap();
        let Some(array)=payload.as_array()else{return self.snapshot()};
        if array.is_empty(){return self.snapshot()}
        let Some(paths)=array.iter().map(|x|x.as_str().filter(|s|!s.is_empty()&&!s.contains('\0')).map(PathBuf::from)).collect::<Option<Vec<_>>>()else{return self.snapshot()};
        let(view,work)={
            let mut core=self.core.lock().unwrap();
            let classified=classify(&paths,&core.app.folders);
            let next=core.app.admit_drop(classified);
            let work=if next==Next::RunIngest{
                if core.cancel.is_some(){self.note("cancel-request");}
                Some(Self::begin(&mut core,format!("ingest-{}",children::nonce())))
            }else{None};(core.app.view(),work)
        };
        (self.emit)(view.clone());
        if let Some(work)=work{let _=self.sender.send(Message::Check(work));}view
    }
    pub fn start_over(&self)->View{
        let _serial=self.publication.lock().unwrap();
        let view={let mut core=self.core.lock().unwrap();core.app.start_over();self.note("invalidate-current");
            if let Some(cancel)=core.cancel.take(){cancel.store(true,Ordering::SeqCst);self.note("cancel-request");}core.app.view()};
        (self.emit)(view.clone());self.note("empty-view");view
    }
    // Both production and controlled tests enter this same worker/completion closure.
    fn execute(&self,work:Work,run:impl FnOnce(&jobdir::Job,&Work)->Result<Outcome,String>){
        if work.cancel.load(Ordering::SeqCst){return;}
        self.note("worker-enter");
        let job=match jobdir::create(&self.data,&work.id){Ok(job)=>job,Err(error)=>{self.fail(work.generation,&work.id,&format!("cannot create the app's own folder: {error}"));return}};
        let outcome=run(&job,&work);self.note("worker-terminal");
        match outcome{Ok(outcome)=>{self.deliver(work.generation,&work.id,&outcome);},Err(why)=>self.fail(work.generation,&work.id,&why)}
        // Sole target is this worker's freshly created Job, only after run terminates.
        jobdir::remove(&job);self.note("remove-owned-job");
    }
    fn deliver(&self,generation:u64,id:&str,outcome:&Outcome)->bool{
        let _serial=self.publication.lock().unwrap();
        let view={let mut core=self.core.lock().unwrap();if !core.app.finish_job(generation,id,outcome){return false;}core.cancel=None;core.app.view()};
        (self.emit)(view);self.note("completion-delivered");true
    }
    fn fail(&self,generation:u64,id:&str,why:&str){
        let _serial=self.publication.lock().unwrap();
        let view={let mut core=self.core.lock().unwrap();if !core.app.fail_job(generation,id,why){return;}core.cancel=None;core.app.view()};(self.emit)(view);
    }
    pub fn shutdown(&self){
        self.stop_polls.store(true,Ordering::SeqCst);self.note("stop-polls");
        {let _serial=self.publication.lock().unwrap();let mut core=self.core.lock().unwrap();
            if let Some(ticket)=core.app.cards_active(){core.app.invalidate_cards(ticket,None);self.note("cards:invalidate-current");}
            if let Some(cancel)=core.cards_cancel.take(){cancel.store(true,Ordering::SeqCst);}}
        if let Some(poller)=self.poller.lock().unwrap().take(){let _=poller.join();}
        self.start_over();let _=self.sender.send(Message::Stop);if let Some(worker)=self.worker.lock().unwrap().take(){let _=worker.join();}
    }
}
#[cfg(test)]
#[path="../tests/bridge_component.rs"]
mod component;
#[cfg(test)]
#[path="../tests/discovery_component.rs"]
mod discovery_component;
