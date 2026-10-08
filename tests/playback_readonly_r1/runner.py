#!/usr/bin/env python3
"""Live Product observation execution and byte-identical offline schedule replay.

Adapter is a JSONL public-call bridge, specified in ADAPTER.md. This runner owns
fixtures, call schedule, independent callback trace and all expectations. Adapter
returns facts only. No candidate source is needed to author or run this package.
"""
from __future__ import annotations
import argparse
import copy
import gzip
import hashlib
import json
import struct
import subprocess
import queue
import threading
from pathlib import Path
import cases
import fixtures as fx
from pcm import PCM
from oracle import Work,check_render,require,COUNTERS,OK,IO,FAULTED,UNDERRUN

def canonical(o):return json.dumps(o,sort_keys=True,separators=(',',':'))
def file_sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(65536),b''):digest.update(b)
    return digest.hexdigest()

class Bridge:
    def __init__(self,adapter,root,writer,case_id,shipping=False,control=None):
        self.root=Path(root);self.root.mkdir(parents=True,exist_ok=True)
        self.writer=writer;self.case_id=case_id;self.shipping=shipping;self.control=control
        self.trace=self.root/'callbacks.bin';self.trace_pos=0
        self.trace.write_bytes(b'') # fresh trace; subsequent device reopen appends
        self.stderr=(self.root/'adapter.stderr').open('w')
        self.proc=subprocess.Popen([adapter],stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                                   stderr=self.stderr,text=True,bufsize=1)
        self.digest=hashlib.sha256();self.calls=0
        self.responses=queue.Queue(maxsize=1)
        def read_responses():
            for line in self.proc.stdout:self.responses.put(line)
            self.responses.put('')
        threading.Thread(target=read_responses,daemon=True).start()
    def call(self,cmd):
        wire=dict(cmd)
        wire['ordinal']=self.calls
        if cmd['fn']=='init':
            wire.update(image_path=str(self.root/'metadata.img'),trace_path=str(self.trace),
                        shipping=self.shipping,control=self.control)
        if cmd['fn']=='replace_unmounted_fixture':wire['image_path']=str(self.root/'metadata.img')
        self.proc.stdin.write(canonical(wire)+'\n');self.proc.stdin.flush()
        try:line=self.responses.get(timeout=120)
        except queue.Empty:raise AssertionError('adapter RPC failed to return (host orchestration ceiling)')
        require(bool(line),'adapter terminated without response')
        obs=json.loads(line)
        require(obs.pop('ordinal')==self.calls,'adapter response ordinal')
        require(not any(k in obs for k in ('expected','passed','verdict','expected_pcm')),'adapter oracle contamination')
        events=[]
        if self.trace.exists():
            with self.trace.open('rb') as trace:
                trace.seek(self.trace_pos);raw=trace.read();self.trace_pos+=len(raw)
            require(len(raw)%20==0,'independent callback trace truncation')
            events=[list(x) for x in struct.iter_unpack('<IIIII',raw)]
        normalized={k:v for k,v in obs.items() if k!='counters'}
        self.digest.update((canonical({'command':cmd,'observation':normalized,'events':events})+'\n').encode())
        self.calls+=1
        if self.shipping:obs['counters']=dict.fromkeys(COUNTERS,0)
        rec={'case':self.case_id,'command':cmd,'observation':obs,'events':events}
        self.writer.write(canonical(rec)+'\n')
        return obs,events
    def close(self):
        self.proc.stdin.close();rc=self.proc.wait(timeout=30)
        self.stderr.close()
        require(rc==0,'adapter exit status')

class Replay:
    def __init__(self,reader,case_id,**kw):self.reader=reader;self.case_id=case_id;self.calls=0;self.digest=hashlib.sha256()
    def call(self,cmd):
        line=self.reader.readline();require(bool(line),'missing replay call')
        r=json.loads(line);require(r['case']==self.case_id and r['command']==cmd,'canonical schedule mismatch')
        obs=r['observation'];events=r['events'];self.calls+=1
        normalized={k:v for k,v in obs.items() if k!='counters'}
        self.digest.update((canonical({'command':cmd,'observation':normalized,'events':events})+'\n').encode())
        return obs,events
    def close(self):pass

class Session:
    def __init__(self,c,bridge,root,shipping=False):
        self.c=c;self.bridge=bridge;self.root=Path(root);self.shipping=shipping
        self.fixture=fx.make(c['fixture']);self.model=PCM(self.fixture,c['side']);self.total_work=None
        self.work=Work(fx.entries(self.fixture,c['side']));self.seam_results=[]
        self.budget_zero_result=None
    def call(self,fn,expected=OK,idle=False,**args):
        cmd={'fn':fn,**args};obs,ev=self.bridge.call(cmd)
        require(type(obs.get('result')) is int,'result schema')
        if expected is not None:require(obs['result']==expected,f'{fn} result')
        if fn not in ('init','inject','replace_unmounted_fixture'):
            self.work.add(cmd,obs,ev,self.fixture,idle=idle and not self.shipping)
        return obs,ev
    def init(self,writable=False,warm=None,resume=0):
        self.root.mkdir(parents=True,exist_ok=True)
        identity=fx.write(self.fixture,self.root/'metadata.img')
        init,_=self.call('init',fixture=self.fixture,fixture_sha256=identity,writable=writable,
                        play_ring_len=65536,rec_ring_len=65536)
        require(init['write_callback_null'] is (not writable),'literal NULL binding observation')
        o,e=self.call('tape_mount',side=self.c['side'],resume=resume,warm=warm)
        require(all(op==1 for op,*_ in e),'clean mount wrote/flushed')
        self.model=PCM(self.fixture,self.c['side'],resume)
        if warm is not None and self.c.get('warm')=='valid' and not self.shipping:
            require(o['counters']['refill_copy_bytes']+o['counters']['warm_adoption_copy_bytes']<=warm['data_bytes'],
                    'one-time warm adoption copy ceiling')
        if warm is None:self.work=Work(fx.entries(self.fixture,self.model.side)) # cold after-mount reset
        return o
    def episode(self):
        self.work.finish(episode=True)
        self.work=Work(fx.entries(self.fixture,self.model.side))
    def rate(self,r):self.episode();self.call('tape_set_rate',rate=r);self.model.set_rate(r)
    def seek(self,n):self.episode();self.call('tape_seek',frame=n);self.model.seek(n)
    def service(self,budget=None):
        b=self.c['budget'] if budget is None else budget
        # Finite orchestration ceiling only, not a loosened acceptance limit. A
        # filled 64KiB ring needs <=128 payload blocks; much larger allowance
        # avoids choosing a Product watermark or mandating full-ring refill.
        for _ in range(self.fixture['block_count']+4096):
            o,_=self.call('tape_service',budget=b)
            require(type(o['more_work']) is bool,'more_work boolean')
            if not o['more_work']:return
        raise AssertionError('service-until-done failed to converge')
    def render(self,n,complete=False,zero=False,progress=False):
        o,_=self.call('tape_render',expected=None,frames=n)
        if progress and copy.copy(self.model).render(n):require(o['rendered']>0,'serviced extreme-rate first sample missing')
        return check_render(self.model,{'frames':n},o,complete=complete,zero=zero)
    def idle(self):
        for _ in range(16):self.call('tape_service',budget=self.c['budget'],idle=True)
    def finish(self):
        self.work.finish(episode=True)
        o,e=self.call('tape_unmount');require(not e,'unmount I/O')
        require(o['position_frame']==self.model.pos>>32,'unmount whole position')
        self.bridge.close()
    def run(self):
        c=self.c;mode=c['mode'];warm=None;resume=0
        if mode=='warm':
            warm={'data_hex':b''.join(fx.frame(self.fixture,c['side'],i) for i in range(256)).hex(),
                  'data_bytes':1024,'valid_frames':256,'start_frame':0,
                  'uuid':self.fixture['uuid'],'side':c['side']}
            w=c['warm'];resume=1
            if w=='null-data':warm['data_hex']=None
            if w=='zero-frames':warm['valid_frames']=0
            if w=='short-bytes':warm['data_bytes']=1023
            if w=='past-end':warm['start_frame']=35000
            if w=='overflow':warm.update(start_frame=0xfffffff0,valid_frames=256)
            if w=='outside':resume=300
            if w=='uuid':warm['uuid']='00'*16
            if w=='side':warm['side']='A'
        self.init(writable=mode in ('overwrite','splice','faulted-drain'),warm=warm,resume=resume)
        if mode=='warm':
            info,_=self.call('tape_get_info');require(info['warm_start_used'] is (c['warm']=='valid'),'ordered warm predicate')
        if mode=='traverse':
            # Initial set_rate belongs within the after-mount traversal reset.
            self.call('tape_set_rate',rate=65536);self.model.set_rate(65536)
            out_frames=0
            while out_frames<self.model.total:
                self.service();n=min(128,self.model.total-out_frames)
                out_frames+=len(self.render(n,complete=True))//4
            self.service();self.render(1,complete=True)
            if not self.shipping:
                self.total_work=self.work.finish(self.model.total*4,c['budget'],c['fixture'].startswith('fragment'))
            self.finish();return
        self.rate(c.get('rate',65536))
        if mode=='rate':
            self.seek(self.model.total if c['rate']<0 else 0);self.service()
            for _ in range(5):
                self.render(128,complete=abs(c['rate'])<=786432,progress=True);self.service()
        elif mode in ('idle-playing','idle-stopped'):
            if mode=='idle-stopped':self.rate(0)
            self.service();self.idle()
        elif mode=='empty':self.service();self.render(128,complete=True)
        elif mode=='budget-zero':
            before=copy.copy(self.model)
            o,ev=self.call('tape_service',expected=None,budget=0)
            self.budget_zero_result=o['result'];require(not ev,'budget zero device I/O')
            tell,_=self.call('tape_tell');require(tell['position_frame']==self.model.pos>>32,'budget zero changed position')
            status,_=self.call('tape_status')
            require(status['at_start'] is self.model.start and status['at_end'] is self.model.end,'budget zero changed flags')
            require(self.model.__dict__==before.__dict__,'zero budget model mutation')
            self.service();self.render(128,complete=True)
        elif mode in ('read-fail','partial-read-fail'):
            self.call('inject',fail_read=True,fail_read_prefix=1 if mode=='partial-read-fail' else 0)
            # Large transfer makes the incomplete-prefix control non-vacuous.
            _,ev=self.call('tape_service',expected=IO,budget=1024)
            require(any(op==1 and lba>=fx.BASE and rc for op,lba,n,rc,done in ev),'required payload read error absent')
            self.render(128,zero=True)
            self.service();self.render(128,complete=True)
        elif mode=='warm':
            # A valid warm range supplies immediate exact PCM, before card refill.
            if c['warm']=='valid':self.render(4,complete=True)
            self.service();self.render(128,complete=True)
            if c['warm']=='valid':
                self.episode();self.call('tape_set_side',side=c['side']);self.model.set_side(c['side'])
                info,_=self.call('tape_get_info');require(info['warm_start_used'] is False,'side switch retained warm flag')
                self.render(4,zero=True);self.service();self.render(4,complete=True)
        elif mode=='remount-changed':
            self.service();self.render(128,complete=True);self.episode()
            o,ev=self.call('tape_unmount');require(not ev,'unmount wrote')
            self.fixture=copy.deepcopy(self.fixture);self.fixture['seed']=0x101
            fx.write(self.fixture,self.root/'metadata.img')
            identity=hashlib.sha256(canonical(self.fixture).encode()).hexdigest()
            self.call('replace_unmounted_fixture',fixture=self.fixture,fixture_sha256=identity)
            self.work=Work(fx.entries(self.fixture,c['side'])) # episode begins before initiating mount
            self.call('tape_mount',side=c['side'],resume=0,warm=None)
            self.model=PCM(self.fixture,c['side'])
            self.rate(65536);self.service();self.render(128,complete=True)
        elif mode in ('same-side','other-side'):
            self.service();self.render(128,complete=True);self.episode()
            side=c['side'] if mode=='same-side' else 'A'
            self.work.E=fx.entries(self.fixture,side)
            self.call('tape_set_side',side=side);self.model.set_side(side)
            self.render(128,zero=True);self.service();self.render(128,complete=True)
        elif mode in ('overwrite','splice','faulted-drain'):
            self.service();self.render(128,complete=True)
            if mode!='faulted-drain':self.rate(0)
            self.seek(127);self.service() # establish valid old PCM at the edit point
            before=b''.join(fx.frame(self.fixture,'B',i) for i in range(self.model.total))
            raw=bytes.fromhex('ff7f0080')*129
            self.call('tape_arm',mode=2 if mode=='splice' else 0)
            o,_=self.call('tape_feed',frames=129,pcm_hex=raw.hex());require(o['accepted']==129,'feed exact accept')
            self.service()
            if mode=='faulted-drain':
                # Commit's failed durability barrier establishes actual FAULTED.
                self.call('inject',fail_flush=True)
                _,ev=self.call('tape_commit',expected=IO)
                require(any(op==3 and rc for op,lba,n,rc,done in ev),'real failed flush absent')
                _,ev=self.call('tape_service',expected=FAULTED,budget=1);require(not ev,'FAULTED service I/O')
                # Drain actual previously serviced PCM at the retained positive rate.
                # Bound by the caller's 16384-frame ring; no device work can refill it.
                drained=0;underrun=False
                for _ in range(130):
                    o,ev=self.call('tape_render',expected=None,frames=128)
                    require(not ev,'FAULTED render I/O')
                    drained+=len(check_render(self.model,{'frames':128},o))//4
                    if o['result']==UNDERRUN:underrun=True;break
                require(drained>0 and underrun,'nonvacuous finite FAULTED buffered drain')
                self.call('tape_abort')
            else:
                self.episode();self.call('tape_commit')
                self.model.timeline_override=before[:127*4]+raw+(before[127*4:] if mode=='splice' else b'')
                self.work.E=3 if mode=='splice' else 2
                self.seek(126);self.rate(65536);self.service();self.render(128,complete=True)
        elif mode in ('seek-covered','seek-uncovered','lookahead','wrap'):
            self.service();self.render(128,complete=True)
            if mode=='wrap':
                for _ in range(260):self.service();self.render(128,complete=True)
            else:
                self.seek({'seek-covered':127,'seek-uncovered':30000,'lookahead':127}[mode])
                if mode=='lookahead':self.rate(32768)
                self.service();self.render(128,complete=True)
        elif mode=='beyond-end':
            self.service();self.render(128,complete=True)
            self.seek((1<<40)+self.model.total);self.render(1,complete=True)
            self.rate(-65536);self.service();self.render(4,complete=True)
        else:raise AssertionError('unhandled canonical mode '+mode)
        self.finish()

def run_case(c,adapter,root,writer,shipping=False,reader=None,control=None):
    path=Path(root)/c['id'];path.mkdir(parents=True,exist_ok=True)
    bridge=Replay(reader,c['id']) if reader else Bridge(adapter,path,writer,c['id'],shipping,control)
    session=Session(c,bridge,path,shipping)
    try:session.run()
    finally:
        if isinstance(bridge,Bridge) and bridge.proc.poll() is None:bridge.proc.kill();bridge.proc.wait()
        if isinstance(bridge,Bridge):bridge.stderr.close()
    return {'id':c['id'],'row':c['row'],'calls':bridge.calls,'equivalence_sha256':bridge.digest.hexdigest(),
            'work':session.total_work,'budget_zero_result':session.budget_zero_result}

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--adapter');p.add_argument('--shipping-adapter');p.add_argument('--replay')
    p.add_argument('--out',required=True);p.add_argument('--case',action='append')
    p.add_argument('--product-commit');p.add_argument('--engine-tree');p.add_argument('--adapter-sha256')
    p.add_argument('--baseline-adapter');p.add_argument('--baseline-product-commit')
    a=p.parse_args();require(bool(a.adapter)^bool(a.replay),'choose live adapter or replay')
    root=Path(a.out).resolve();root.mkdir(parents=True,exist_ok=True)
    selected=[c for c in cases.cases() if not a.case or c['id'] in a.case]
    require(len(selected)==(len(a.case) if a.case else len(cases.cases())),'unknown/duplicate case selection')
    results=[];shipping_artifacts=[]
    with gzip.open(root/'observations.jsonl.gz','wt') as writer:
        if a.replay:
            with gzip.open(a.replay,'rt') as reader:
                for c in selected:results.append(run_case(c,None,root,writer,reader=reader))
                require(not reader.readline(),'extra replay observations')
        else:
            require(a.product_commit and a.engine_tree and a.adapter_sha256,'exact live provenance required')
            require(file_sha(a.adapter)==a.adapter_sha256,'adapter binary SHA256')
            for c in selected:
                instrumented=run_case(c,str(Path(a.adapter).resolve()),root/'instrumented',writer)
                if a.shipping_adapter:
                    with gzip.open(root/(c['id']+'-shipping.jsonl.gz'),'wt') as sw:
                        shipping=run_case(c,str(Path(a.shipping_adapter).resolve()),root/'shipping',sw,shipping=True)
                    require(shipping['equivalence_sha256']==instrumented['equivalence_sha256'],'instrumentation changes PCM/results/status/device trace')
                    shipping_artifacts.append({'id':c['id'],'file':c['id']+'-shipping.jsonl.gz',
                                               'sha256':file_sha(root/(c['id']+'-shipping.jsonl.gz'))})
                results.append(instrumented)
    baseline=None
    if a.adapter and a.baseline_adapter:
        require(a.baseline_product_commit=='9e902cf04b6d0c02363870fb9bc201e40239b509','issued pre-change baseline pin')
        c=next(c for c in cases.cases() if c['id']=='budget-zero')
        with gzip.open(root/'budget-zero-baseline.jsonl.gz','wt') as bw:
            baseline=run_case(c,str(Path(a.baseline_adapter).resolve()),root/'baseline',bw,shipping=True)
        observed=next((c['budget_zero_result'] for c in results if c['id']=='budget-zero'),None)
        if observed is not None:require(observed==baseline['budget_zero_result'],'zero-budget result changed from accepted baseline')
        baseline.update(product_commit=a.baseline_product_commit,adapter_sha256=file_sha(a.baseline_adapter),
                        observation_sha256=file_sha(root/'budget-zero-baseline.jsonl.gz'))
    manifest={'schema':'read1-run-v1','kind':'offline-replay' if a.replay else 'actual-Product-observations',
              'product_commit':a.product_commit,'engine_tree':a.engine_tree,'adapter_sha256':a.adapter_sha256,
              'complete_case_census':not bool(a.case),'shipping_equivalence_executed':bool(a.shipping_adapter),
              'shipping_adapter_sha256':file_sha(a.shipping_adapter) if a.shipping_adapter else None,
              'shipping_observations':shipping_artifacts,
              'baseline_budget_zero':baseline,
              'cases':results,'observation_sha256':file_sha(a.replay if a.replay else root/'observations.jsonl.gz'),
              'product_controls':'required separately by controls.py; this run alone is not acceptance'}
    (root/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');print(canonical({'cases':len(results),'out':str(root),'acceptance':False}))

if __name__=='__main__':main()
