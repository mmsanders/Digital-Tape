"""Independent INGEST-1 observation predicates. No Product imports/execution."""
import argparse, json, math
from pathlib import Path
import numpy as np
import model as m
import numerics as n

class Failure(AssertionError):
    def __init__(self,gate,detail):self.gate=gate;super().__init__(gate+': '+detail)
def require(ok,gate,detail):
    if not ok:raise Failure(gate,detail)
def close(a,b,tol,gate):
    require((a is None and b is None) or (a is not None and b is not None and abs(float(a)-float(b))<=tol),gate,str((a,b)))
def metric(value):return None if value is None else float(value)

def peak_metric(reported,reference):
    if reported is None or reference is None:close(reported,reference,0,'meter');return
    # The issued qualification bound is UNDER-read, not symmetric equality to
    # this particular reconstruction filter. The independently reviewed meter
    # definition binds reported values; do not apply the guard margin twice.
    delta=float(reported)-reference
    require(delta>=-.100001,'meter','true-peak observation underreads independent reference')

def audio(before,pcm,metadata,*,original=None,mono=False,exact=False,physical_upper=None,digital_source=None):
    """before is observed isolated floating SRC, corroborated by source/quality gates.

    The44100 lossless path uses independent decoded originals, not this observation.
    Six-decimal gain uncertainty is explicitly propagated, never a waveform hash.
    """
    x=np.asarray(before,float);q=np.frombuffer(pcm,dtype='<i2').reshape(-1,2).astype(float)/32768
    require(x.shape==q.shape and np.isfinite(x).all(),'count','isolated input/output dimensions')
    if original is not None:require(np.max(abs(x-original),initial=0)<=2e-6*np.max(abs(original),initial=0),'conversion','44100 lossless exceeds floating precision enclosure')
    silence=not np.any(x) if digital_source is None else digital_source
    g=metric(metadata['applied_gain_db']);require(g is not None and math.isfinite(g),'gain','finite constant required')
    il=n.loudness(x);ip=n.peak(x);ol=n.loudness(q);op=n.peak(q)
    close(metadata['input_lufs'],il,.1,'meter');peak_metric(metadata['input_dbtp'],ip)
    close(metadata['output_lufs'],ol,.1,'meter');peak_metric(metadata['output_dbtp'],op)
    if silence:
        require(pcm==bytes(len(pcm)) and g==0 and metadata['loudness_status']=='digital_silence' and all(metadata[k] is None for k in ('input_lufs','input_dbtp','output_lufs','output_dbtp')),'silence','whole silence bypass')
        require(metadata['loudness_reason'] is None and not metadata['peak_limited'],'status','silence status')
        return
    require(ip is not None,'peak','nonzero source requires valid input peak')
    require(op is not None or not np.any(q),'peak','undefined output peak on nonzero PCM')
    require(physical_upper is None or math.isfinite(physical_upper),'peak','nonfinite ceiling proof')
    require((op is None or (op<=-1+1e-6 if physical_upper is None else physical_upper<=-1)) and (metadata['output_dbtp'] is None or float(metadata['output_dbtp'])+.1<=-1+1e-9),'peak','source physical ceiling/reported guard')
    ideal=x*10**(g/20)
    uncertainty=np.abs(ideal)*math.expm1(math.log(10)*.00000051/20)
    uncertainty+=np.spacing(np.abs(ideal).astype(np.float32)).astype(float)/2
    require(np.all(np.abs(q-ideal)<=1.500001/32768+uncertainty),'constant-gain','PCM not one scalar plus issued TPDF/rounding')
    if mono:require(np.array_equal(q[:,0],q[:,1]),'mono','L/R differ')
    # Enclose only six-decimal gain and one floating multiplication rounding;
    # every source must still use the EXACT issued TPDF sequence/draw order.
    lower=np.frombuffer(m.quantize(ideal-uncertainty,mono=mono),dtype='<i2').astype(np.int32)
    upper=np.frombuffer(m.quantize(ideal+uncertainty,mono=mono),dtype='<i2').astype(np.int32)
    actual=np.frombuffer(pcm,dtype='<i2').astype(np.int32)
    require(np.all((actual>=np.minimum(lower,upper))&(actual<=np.maximum(lower,upper))),'dither','PCM outside exact PRNG/quantization interval')
    if exact:require(pcm==m.quantize(x,mono=mono),'dither','gain0 dyadic exact xorshift/draw/rounding')
    target=None if metadata['input_lufs'] is None else -16-float(metadata['input_lufs'])
    close(metadata['target_gain_db'],target,.000002,'gain')
    reported_peak=float(metadata['input_dbtp'])
    start=min(0,-1-reported_peak-.1) if il is None else min(target,-1-reported_peak-.1)
    require(g<=start+.000002,'gain','unlicensed boost/ceiling gain')
    if il is None:
        # Quantization correction may reduce gain very slightly for final ceiling.
        require(g>=start-.000002 or float(metadata['output_dbtp'])>=-1.101,'gain','unmeasurable arbitrary attenuation without final ceiling justification')
    if ol is None:
        require(metadata['loudness_status']=='unmeasurable' and metadata['loudness_reason']==('too_short' if len(x)<17640 else 'gated_out'),'status','undefined loudness reason')
    else:
        require(metadata['loudness_status']=='measured' and metadata['loudness_reason'] is None,'status','finite loudness reason')
        if il is not None and abs(ol+16)>.5:
            require(g<target and float(metadata['output_dbtp'])>=-1.13 and metadata['peak_limited'],'target','unjustified under-normalization')
    if target is not None:
        if abs(g-target)>.000002:require(metadata['peak_limited']==(g<target),'status','peak_limited disagrees with finite target/gain')
    elif metadata['peak_limited']:
        # Undefined loudness has no finite target. A profile may also label its
        # real ceiling attenuation as peak-limited, but cannot invent a claim.
        require(g<0 and float(metadata['output_dbtp'])>=-1.13,'status','unjustified unmeasurable peak-limited flag')

def quality(before,rate,frequency,amplitude,window=4410):
    x=np.asarray(before,float);require(len(x)>2*window,'src-quality','empty steady-state interval')
    t=np.arange(window,len(x)-window)/44100
    folded=abs((frequency+22050)%44100-22050)
    basis=np.stack((np.sin(2*np.pi*folded*t),np.cos(2*np.pi*folded*t)),axis=1)
    fit=np.linalg.lstsq(basis,x[window:-window],rcond=None)[0]
    response=20*np.log10(np.maximum(np.linalg.norm(fit,axis=0)/amplitude,1e-300))
    if frequency<=min(18000,.4*rate):require(np.all(abs(response)<=.1),'src-quality','passband '+str(response))
    if 22050<=frequency<rate/2:require(np.all(response<=-80),'src-quality','alias '+str(response))
    return response.tolist()

def latency(before,decoded,rate):
    require(len(before)>0 and np.any(before),'src-latency','lost endpoint impulse')
    at=int(np.argmax(np.max(abs(decoded),axis=1)));peak=int(np.argmax(np.max(abs(before),axis=1)))
    require(abs(peak-at*44100/rate)<=1,'src-latency','uncompensated endpoint/latency')

def joined(pcm,reported='REFERENCE',physical_upper=None):
    x=np.frombuffer(pcm,dtype='<i2').reshape(-1,2).astype(float)/32768
    p=n.peak(x)
    require(physical_upper is None or math.isfinite(physical_upper),'join-peak','nonfinite ceiling proof')
    if reported=='REFERENCE':reported=p
    peak_metric(reported,p)
    require(p is None or (p<=-1+1e-6 if physical_upper is None else physical_upper<=-1),'join-peak','physical joined ceiling')
    require(reported is None or float(reported)+.1<=-1+1e-6,'join-peak','unsafe reported concatenated boundary')

def identity(standalone,batch,repeat):
    require(standalone==batch==repeat,'identity','per-source isolated/batch/repeat differ')

def transaction(record):
    """Normalized native evidence facts; raw trace binding/coverage audited separately.
    Events strictly ordered; sequence gaps/truncation cannot establish absence.
    """
    events=record['events'];names=[e['op'] for e in events]
    require(all(type(record[k])is bool for k in ('complete','observer_selftest','owned_stage_after')),'trace','nonboolean native flags')
    for key in ('dest_after','dest_before'):
        if key in record:require(isinstance(record[key],list) and all(isinstance(name,str) for name in record[key]) and len(record[key])==len(set(record[key])),'trace','invalid directory snapshot census')
    for key in ('diagnostic_ok','competitor_unchanged','unrelated_unchanged'):
        if key in record:require(type(record[key])is bool,'trace','nonboolean scenario flag')
    require(record['complete'] and record['raw_trace_sha256'] and record['observer_selftest'],'trace','incomplete/unqualified observer')
    require([e['seq'] for e in events]==list(range(len(events))),'trace','event sequence gap')
    require(all(type(e['seq'])is int for e in events),'trace','noninteger event index')
    for event in events:
        if event['op']=='stage_create':require(type(event['exclusive'])is bool and type(event['adjacent'])is bool,'trace','nonboolean stage facts')
    require('device_open' not in names and 'preflight_disk_scratch' not in names,'io-scope','device/scratch open')
    scenario=record['scenario'];exit_=record['exit']
    staging=[i for i,k in enumerate(names) if k in ('stage_create','output_open')]
    if scenario=='informational':
        require(exit_==0 and not staging and not record['dest_after'] and not record['owned_stage_after'],'preflight','informational command created output')
    elif scenario=='preflight-refusal':
        require(exit_==2 and not staging and record['dest_after']==record.get('dest_before',[]) and not record['owned_stage_after'],'preflight','output opened or existing destination changed on refusal')
        if record.get('dest_before'):require(record['dest_before_sha256']==record['dest_after_sha256'],'preflight','existing destination bytes changed')
        require(record['diagnostic_ok'],'diagnostic','named plain refusal/overage')
    elif scenario in ('success','concurrent-dest','write-error','kill'):
        # I/O/resource failure during preflight cannot fabricate a completed
        # preflight. It must still leave no output/stage and preserve unrelateds.
        if scenario=='write-error' and 'preflight_complete' not in names:
            require(exit_==1 and not staging and not record['dest_after'] and not record['owned_stage_after'] and record['unrelated_unchanged'],'cleanup','preflight I/O failure leaked output')
            require(record['raw_review']=='PASS','trace','raw trace review required');return
        if scenario=='kill' and ('preflight_complete' not in names or 'sources_revalidated' not in names):
            require(not staging and not record['dest_after'] and not record['owned_stage_after'] and record['unrelated_unchanged'],'pair','preflight kill leaked output')
            require(record['raw_review']=='PASS','trace','raw trace review required');return
        require('preflight_complete' in names and 'sources_revalidated' in names,'mutation','source identities not revalidated')
        require(not staging or names.index('preflight_complete')<min(staging),'preflight','stage before complete preflight')
        if scenario=='success':
            require(exit_==0 and record['dest_after']==['audio.wav','manifest.json'] and not record['owned_stage_after'],'pair','missing/extra output or leftover stage')
            require(names.count('publish_dir_noreplace')==1 and 'publish_file' not in names,'pair','publication not one no-replace directory boundary')
            at=names.index('publish_dir_noreplace')
            require(all(names.count(op)==1 and names.index(op)<at for op in ('audio_flush_close','manifest_flush_close')),'pair','files not closed/flushed before publish')
            require(all(e.get('exclusive') and e.get('adjacent') for e in events if e['op']=='stage_create') and names.count('stage_create')==1,'pair','stage not exclusive/adjacent')
        elif scenario=='concurrent-dest':
            require(exit_ in (1,2) and record['competitor_unchanged'] and not record['owned_stage_after'] and 'publish_dir_noreplace' not in names,'pair','concurrent DEST overwritten')
        elif scenario=='write-error':
            require(exit_==1 and not record['dest_after'] and not record['owned_stage_after'] and record['unrelated_unchanged'],'cleanup','ordinary error cleanup')
        else:
            require((record['dest_after']==['audio.wav','manifest.json'] if 'publish_dir_noreplace' in names else not record['dest_after']) and record['unrelated_unchanged'],'pair','kill left partially published DEST')
            if 'publish_dir_noreplace' in names:
                at=names.index('publish_dir_noreplace')
                require(names.count('publish_dir_noreplace')==1 and 'publish_file' not in names and all(names.count(op)==1 and names.index(op)<at for op in ('audio_flush_close','manifest_flush_close')),'pair','post-publish kill lacked complete single boundary')
    elif scenario=='mutation':
        require(exit_==2 and 'source_mutation_detected' in names and not record['dest_after'],'mutation','mixed source versions')
        require(not record['owned_stage_after'],'cleanup','mutation stage not removed')
    else:raise Failure('trace','unknown scenario')
    require(record['raw_review']=='PASS','trace','native raw trace review required; normalized self-report insufficient')


def manifest(raw,pcm,facts,folders,seconds):
    try:return m.check_manifest(raw,pcm,facts,folders,seconds)
    except (AssertionError,ValueError,KeyError,TypeError) as e:raise Failure('manifest',str(e)) from e

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('observation',type=Path);a=ap.parse_args()
    transaction(json.loads(a.observation.read_text(encoding='utf-8')));print('Native normalized predicates PASS; require bound raw trace review')
