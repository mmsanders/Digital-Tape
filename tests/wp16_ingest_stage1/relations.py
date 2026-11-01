"""Exact profile/platform/repetition and source-slice relations."""
import copy,json
import audit,model

def source_slices(raw,pcm):
    manifest=json.loads(raw)
    return [(s,pcm[4*s['start_frame']:4*(s['start_frame']+s['output_frames'])]) for s in manifest['sources']]

def repeated_sources(raw,pcm):
    seen={}
    for s,part in source_slices(raw,pcm):
        key=s['source_sha256'];normalized={k:v for k,v in s.items() if k not in ('logical_path','start_frame')}
        if key in seen:audit.require(seen[key]==(normalized,part),'identity','repeated source changed with neighbour/path')
        seen[key]=(normalized,part)
    return seen

def pair(a,b,mode):
    am,ap=a;bm,bp=b
    audit.require(ap==bp,'identity',mode+' PCM drift')
    aa=json.loads(am);bb=json.loads(bm)
    if mode=='different-target':
        for key in ('target_seconds','capacity_frames'):aa.pop(key);bb.pop(key)
    audit.require(model.canonical(aa)==model.canonical(bb),'identity',mode+' manifest drift')

def standalone(whole,individual):
    found=repeated_sources(*whole)
    for raw,pcm in individual:
        parts=source_slices(raw,pcm);audit.require(len(parts)==1,'identity','standalone not one source')
        s,part=parts[0];norm={k:v for k,v in s.items() if k not in ('logical_path','start_frame')}
        audit.require(found[s['source_sha256']]==(norm,part),'identity','standalone/batch changed source')
