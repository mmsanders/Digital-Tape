//! One production coordinator and serial worker. App owns current-result acceptance.
use crate::{children, drops, ingest_job::{self, Outcome}, jobdir, state::{App, Next, View}};
use serde_json::Value;
use std::{path::PathBuf, sync::{Arc, Mutex, Weak, mpsc, atomic::{AtomicBool, Ordering}}, thread};

pub struct Work { pub id:String, pub generation:u64, pub folders:Vec<PathBuf>, pub cancel:Arc<AtomicBool> }
enum Message { Check(Work), Stop }
struct Core { app:App, cancel:Option<Arc<AtomicBool>> }
pub struct Bridge {
    core:Mutex<Core>,
    // Mutations/publications are serialized; emit never holds the core lock.
    publication:Mutex<()>, data:PathBuf, emit:Arc<dyn Fn(View)+Send+Sync>,
    sender:mpsc::Sender<Message>, worker:Mutex<Option<thread::JoinHandle<()>>>,
    #[cfg(test)] trace:Mutex<Vec<String>>,
}
impl Bridge {
    fn channel(data:PathBuf,emit:Arc<dyn Fn(View)+Send+Sync>)->(Arc<Self>,mpsc::Receiver<Message>) {
        let(sender,receiver)=mpsc::channel();
        (Arc::new(Self{core:Mutex::new(Core{app:App::default(),cancel:None}),publication:Mutex::new(()),data,emit,sender,worker:Mutex::new(None),#[cfg(test)]trace:Mutex::new(Vec::new())}),receiver)
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
        *bridge.worker.lock().unwrap()=Some(worker);bridge
    }
    fn note(&self,event:&str){
        #[cfg(test)]self.trace.lock().unwrap().push(event.to_owned());
        #[cfg(not(test))]let _=event;
    }
    pub fn snapshot(&self)->View{self.core.lock().unwrap().app.view()}
    pub fn raw_details(&self)->String{self.core.lock().unwrap().app.details.clone()}
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
    pub fn shutdown(&self){self.start_over();let _=self.sender.send(Message::Stop);if let Some(worker)=self.worker.lock().unwrap().take(){let _=worker.join();}}
}
#[cfg(test)]
#[path="../tests/bridge_component.rs"]
mod component;
