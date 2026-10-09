"""Independent work/event/PCM verdicts, reusable for live run and offline replay."""
from __future__ import annotations
from dataclasses import dataclass,field
import copy
import struct
import fixtures as fx
from pcm import PCM

COUNTERS=('refill_copy_bytes','warm_adoption_copy_bytes','retained_move_bytes',
          'mapping_entry_visits','idle_loop_iterations')
OK,IO,FAULTED,UNDERRUN=0,1,15,18

def require(x,message):
    if not x:raise AssertionError(message)

def delta_check(d):
    require(set(d)==set(COUNTERS),'counter schema')
    require(all(type(v) is int and 0<=v<2**64 for v in d.values()),'wide nonnegative counters')

@dataclass
class Work:
    E:int
    payload_blocks:int=0
    payload_calls:int=0
    metadata_blocks:int=0
    metadata_calls:int=0
    completed_blocks:int=0
    errors:int=0
    F:int=0
    service_calls:int=0
    render_calls:int=0
    counts:dict=field(default_factory=lambda:dict.fromkeys(COUNTERS,0))
    def add(self,call,obs,events,f,*,idle=False):
        d=obs['counters'];delta_check(d)
        for k in COUNTERS:self.counts[k]+=d[k];require(self.counts[k]<2**64,'counter sum wrap')
        blocks=0;payload=0
        for op,lba,n,rc,completed in events:
            require(op in (1,2,3),'callback type')
            if op!=3:
                require(n>0 and lba+n<=f['block_count'],'device extent/count')
                require(completed==(0 if rc else n),'completion classification')
                blocks+=n
            else:require(lba==0 and n==0 and completed==0,'flush event')
            if op==1:
                p=max(0,min(lba+n,f['block_count']-1)-max(lba,fx.BASE))
                payload+=p;self.payload_blocks+=p
                self.metadata_blocks+=n-p
                if p:self.payload_calls+=1
                if p<n:self.metadata_calls+=1
                self.completed_blocks+=completed
                self.errors+=bool(rc)
            if call['fn']=='tape_render':require(False,'render I/O')
        if call['fn']=='tape_service':
            self.service_calls+=1
            require(blocks<=call['budget'],'sum-of-counts service budget')
        if call['fn']=='tape_render':self.F+=call['frames'];self.render_calls+=1
        if call['fn']=='tape_seek':require(d['mapping_entry_visits']<=2*self.E+32,'seek visit ceiling')
        if idle:
            require(not events,'idle device I/O')
            require(all(d[k]==0 for k in COUNTERS if k!='idle_loop_iterations'),'idle PCM/mapping work')
            require(d['idle_loop_iterations']<=8,'idle loop ceiling')
            require(obs['result']==OK and obs['more_work'] is False,'idle convergence')
    def finish(self,logical_bytes=None,budget=1024,fragmented=False,*,episode=False,warm_bytes=0):
        v=self.counts['mapping_entry_visits'];b=self.payload_blocks
        require(v<=4*self.E+4*b+(4*self.F if episode else 0)+32,'mapping visit ceiling')
        if logical_bytes is not None:
            n=fx.ceildiv(logical_bytes,512);t=fx.ceildiv(logical_bytes,32768);c=min(budget,64)
            max_b=n+2*self.E+128 if fragmented else n+130
            max_calls=t+2*self.E+3 if fragmented else t*fx.ceildiv(64,c)+fx.ceildiv(130,c)
            if not fragmented or budget==1024:require(b<=max_b,'payload reread ceiling')
            # Fragmented callback ceiling is issued only at budget 1024.
            if not fragmented or budget==1024:require(self.payload_calls<=max_calls,'tiny-transfer callback ceiling')
            require(not self.errors,'no-error traversal callback failures')
            require(self.counts['retained_move_bytes']==0,'retained monotone movement')
            require(self.counts['refill_copy_bytes']+self.counts['warm_adoption_copy_bytes']<=b*512+warm_bytes,'PCM copy ceiling')
        return copy.deepcopy(self.__dict__)

def check_render(model,call,obs,*,complete=False,zero=False):
    require(type(obs['rendered']) is int and 0<=obs['rendered']<=call['frames'],'render count')
    n=obs['rendered'];raw=bytes.fromhex(obs['pcm_hex']);require(len(raw)==n*4,'PCM output length')
    if zero:require(n==0,'invalidated ring returned stale samples')
    # Copy permits computing the endpoint maximum without changing the actual prefix state.
    probe=copy.copy(model);possible=probe.render(call['frames'])
    require(n<=len(possible)//4,'render beyond endpoint')
    expected=model.render(n);require(raw==expected,'exact PCM / interpolation / stale coverage')
    if complete:require(raw==possible,'serviced ordinary-rate request incomplete')
    # Endpoint flags may be set by a short endpoint-check iteration even when no PCM emits.
    endpoint_short=n==len(possible)//4 and n<call['frames']
    if endpoint_short:model.end=probe.end;model.start=probe.start
    want=OK if n==call['frames'] or endpoint_short else UNDERRUN
    require(obs['result']==want,'render result/underrun versus endpoint')
    require(obs['position_frame']==model.pos>>32,'tell exact truncation')
    require(obs['at_start'] is model.start and obs['at_end'] is model.end,'endpoint status')
    return raw
