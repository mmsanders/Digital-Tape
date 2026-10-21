#!/usr/bin/env python3
"""Source-only cardinality derivation packaging, never builds/imports/runs a decoder."""
import argparse, hashlib, json, os, pathlib, re, subprocess, sys, time
ROOT=pathlib.Path(__file__).resolve().parents[2]
SOURCE='b9f430c8c9b33532abf07eea0ed2653310639f2d'
sys.path.insert(0,str(ROOT/'tests/codec_cardinality_r2'))
from oracle import OBLIGATIONS,check_ledger,premise_model

COMMANDS=[]
RAW=None
def git(*args):
 start=time.monotonic_ns();argv=['git',*args];p=subprocess.Popen(argv,cwd=ROOT,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
 out,err=p.communicate();i=len(COMMANDS)
 (RAW/(str(i)+'-stdout.bin')).write_bytes(out);(RAW/(str(i)+'-stderr.bin')).write_bytes(err)
 COMMANDS.append(dict(argv=argv,pid=p.pid,parent=os.getpid(),exit=p.returncode,start_ns=start,end_ns=time.monotonic_ns(),stdout_sha256=hashlib.sha256(out).hexdigest(),stderr_sha256=hashlib.sha256(err).hexdigest()))
 if p.returncode:raise RuntimeError(err.decode())
 return out
def sha(b):return hashlib.sha256(b).hexdigest()
def save(p,x):p.write_text(json.dumps(x,indent=2,sort_keys=True)+'\n',encoding='utf-8')

def main():
 global RAW
 ap=argparse.ArgumentParser();ap.add_argument('--out',type=pathlib.Path,required=True);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=False)
 RAW=a.out/'commands';RAW.mkdir()
 start=time.process_time_ns();wall=time.monotonic_ns()
 prefixes=['host/ingest/vendor/symphonia-bundle-mp3/src/','host/ingest/vendor/symphonia-codec-aac/src/',
           'host/ingest/vendor/symphonia-core/src/audio/','host/ingest/vendor/symphonia-common/src/mpeg/audio/']
 paths=git('ls-tree','-r','--name-only',SOURCE,'host/ingest').decode().splitlines()
 paths=[p for p in paths if (p.endswith('.rs') and any(p.startswith(x) for x in prefixes)) or
        p in ['host/ingest/src/mpeg.rs','host/ingest/src/aac.rs','host/ingest/src/common.rs','host/ingest/src/lib.rs',
              'host/ingest/Cargo.lock','host/ingest/vendor/symphonia-core/src/lib.rs']]
 files={};text={};search=[];declarations=[]
 for p in paths:
  data=git('show',SOURCE+':'+p);q=a.out/'source'/p;q.parent.mkdir(parents=True,exist_ok=True);q.write_bytes(data)
  text[p]=data.decode();files[p]=dict(sha256=sha(data),blob=git('rev-parse',SOURCE+':'+p).decode().strip(),bytes=len(data))
  for no,line in enumerate(text[p].splitlines(),1):
   if re.search(r'AudioBuffer|AudioSpec|self\.planes|self\.spec|self\.buf\s*=|unsafe|fn\s+(plane|render|trim|clear|reset)',line):
    search.append(dict(path=p,line=no,text=line.strip()))
   if re.search(r'\bfn\s+\w+',line):declarations.append(dict(path=p,line=no,text=line.strip()))
 save(a.out/'SOURCE-PINS.json',dict(source=SOURCE,files=files))
 save(a.out/'CAPABILITY-CENSUS.json',dict(search_terms='AudioBuffer/AudioSpec/outer planes/spec assignment/buffer replacement/unsafe/mutator signatures',
       search=search,declarations=declarations,scope='cardinality capability graph; NOT all arithmetic call graph'))
 aliases={'buf':'host/ingest/vendor/symphonia-core/src/audio/buf.rs','audio':'host/ingest/vendor/symphonia-core/src/audio/mod.rs',
 'channels':'host/ingest/vendor/symphonia-core/src/audio/channels.rs','generic':'host/ingest/vendor/symphonia-core/src/audio/generic.rs',
 'mp3':'host/ingest/vendor/symphonia-bundle-mp3/src/decoder.rs','mcommon':'host/ingest/vendor/symphonia-bundle-mp3/src/common.rs',
 'header':'host/ingest/vendor/symphonia-bundle-mp3/src/header.rs','layer':'host/ingest/vendor/symphonia-bundle-mp3/src/layer3/mod.rs',
 'synthesis':'host/ingest/vendor/symphonia-bundle-mp3/src/synthesis.rs','aac':'host/ingest/vendor/symphonia-codec-aac/src/aac/mod.rs',
 'cpe':'host/ingest/vendor/symphonia-codec-aac/src/aac/cpe.rs','ics':'host/ingest/vendor/symphonia-codec-aac/src/aac/ics/mod.rs',
 'dsp':'host/ingest/vendor/symphonia-codec-aac/src/aac/dsp.rs','asc':'host/ingest/vendor/symphonia-common/src/mpeg/audio/mod.rs',
 'hostmp3':'host/ingest/src/mpeg.rs','hostaac':'host/ingest/src/aac.rs','hostcommon':'host/ingest/src/common.rs'}
 nodes=[]
 def node(id,key,function,effect,error='Error/panic is not a successful frame; no outer plane/spec mutation is introduced.',occ=0):
  p=aliases[key];s=text[p]
  # Locate exact function declaration. End is next declaration or EOF (over-inclusive context).
  found=list(re.finditer(r'\bfn\s+'+re.escape(function)+r'\b',s));assert len(found)>occ,(id,function)
  m=found[occ];first=s[:m.start()].count('\n')+1
  other=re.search(r'\bfn\s+\w+',s[m.end():]);last=len(s.splitlines()) if not other else s[:m.end()+other.start()].count('\n')
  n=dict(id=id,path=p,sha256=files[p]['sha256'],blob=files[p]['blob'],function=function,first_line=first,last_line=last,
      review='AUDITED',success_effect=effect,error_effect=error,
      ownership='Safe Rust owned/private buffer state; borrowed slices cannot resize outer Vec/SmallVec or mutate privately owned AudioSpec.',edges=[])
  nodes.append(n);return id
 node('BNEW','buf','new','C=count(owned spec); resize_with(C) builds C vectors of capacity; same moved spec, num_frames0. Valid allocation and nonzero admitted C assumed.')
 node('BUNUSED','buf','is_unused','Only capacity/count read; no state write.')
 node('BCLEAR','buf','clear','Only num_frames=0; P and spec unchanged, including error cleanup.')
 node('BRENDER','buf','render_uninit','Asserts num_frames+new<=capacity, advances count only; spec/planes unchanged.')
 node('BSHIFT','buf','shift','Clear if shift>=frames; otherwise copy_within each EXISTING plane and decrease frames only.')
 node('BTRUNC','buf','truncate','Only decreases num_frames.')
 node('BTRIM','buf','trim','truncate then shift; no plane removal or spec mutation.')
 node('BSPEC','buf','spec','Returns immutable &owned spec.')
 node('BPLANES','buf','num_planes','Returns outer SmallVec len, not valid frames or bitmask.')
 node('BFRAMES','buf','frames','Returns valid num_frames, independent of P.')
 node('BPLANE','buf','plane','Returns &plane[0..num_frames], no outer mutation.')
 node('BPMUT','buf','plane_mut','Returns only mutable sample slice selected by index; no outer-plane/spec capability escapes.')
 node('BITER','buf','iter_planes','Read-only iterator over existing planes and valid frame range.')
 node('COUNT','channels','count','Positioned=count_ones(bits); Discrete=u16 count; Ambisonic=(1+order)^2; Custom=len; None0. Admitted1/2 avoids overflow.')
 node('SPECNEW','audio','new','Owned AudioSpec moves channel representation and rate.',occ=0)
 node('SPECCHAN','audio','channels','Only immutable channel reference returned.')
 node('ACOPY','audio','copy_to_vecs_planar','Resizes destination OUTER vector to num_planes P, each destination to valid samples_planar then copies every plane.')
 node('GCOPY','generic','copy_to_vecs_planar','Macro dispatch borrows concrete buffer unchanged; F32 arm invokes concrete Audio trait copy.',occ=1)
 node('MSTATE','mp3','new','Codec ID match constructs Layer3 only for CODEC_ID_MP3; no audio buffer receives this state.')
 node('MNEW','mp3','try_new','Checks codec membership, owns params clone/state, starts default empty buffer, no frame returned yet.')
 node('MINNER','mp3','decode_inner','Header length check; unused buffer REPLACED by newly constructed same header spec; otherwise rejects different spec. Clear, layer match, trim, success.')
 node('MRESET','mp3','reset','Replaces codec state only; existing audio buffer identity/spec/planes retained.')
 node('MREF','mp3','decode_ref','Err clears frames and returns Err; successful branch borrows same self.buf via GenericAudioBufferRef F32.')
 node('MSPEC','mcommon','spec','Header n_channels selects MONO/STEREO positioned layouts (counts1/2), AudioSpec new with same sample rate.')
 node('MNCHAN','mcommon','n_channels','Delegates channel_mode.count(), no output state capability.')
 node('MHDR','header','read_frame_header','Parses header into owned value; only reader reference, cannot mutate decoder buffer.')
 node('LDECODE','layer','decode','Only out mutations: render_uninit(Some576), then plane_mut(ch) to synthesis sample slice. Other callees receive self state/header/frame-data, never out.')
 node('LSYNTH','synthesis','synthesis','Mutable destination is fixed-length [f32] slice; cannot replace AudioBuffer/spec/outer planes.')
 node('ANEW','aac','try_new','AAC/LC/noSBR/<=2/1024 admission; reads/clones ASC channels into owned spec, buffer created from same C, no sharing.')
 node('ASETPAIR','aac','set_pair','Mutates pairs vector only; validates channel/is_pair on reuse and channel bound against owned asc count before Ok.')
 node('AGA','aac','decode_ga','Decode element IDs into pair/ICS state; rejects unsupported. set_pair bounds; synth loop only via ChannelPair::synth_audio(&mut buf). ASC/spec not reassigned.')
 node('AINNER','aac','decode_inner','Clear frames, render capacity via render_uninit(None), only LC dispatch decode_ga, then Ok.')
 node('ARESET','aac','reset','Resets pair internal ICS state only; buf/spec/planes unchanged.')
 node('AREF','aac','decode_ref','Error clears only frames and returns Err; success borrows same owned f32 buffer.')
 node('ASYNTH','cpe','synth_audio','Only plane_mut(channel/channel+1) -> expect -> ICS synth_channel on returned slice. No whole-buffer replacement or spec write.')
 node('ICS','ics','synth_channel','Receives only &mut[f32] destination; pulse/TNS touch coefficient arrays, DSP receives same fixed slice.')
 node('DSP','dsp','synth','Sample-array/delay/fixed-slice writes; no AudioBuffer/spec/plane-container authority.')
 node('ASC','asc','read','Owned configuration parse; no output-buffer argument; constructor later owns spec derived from channels.')
 node('HMP3','hostmp3','decode','Host admits LayerIII only; stable mono/rate frame walk, fresh decoder. Each successful frame checks actual spec count==C BEFORE copy; C allocated host vectors append all P=C vectors; finish.')
 node('HHDR','hostmp3','header','Refuses LayerI/II/reserved; mono field from mode bits; stable version/rate/channel guards in decode.')
 node('HASC','hostaac','parse_asc','Host accepts LC, config1/2,1024, no core/unsupported extensions; owned Asc channel scalar.')
 node('HUNIT','hostaac','decode_units','Fresh AAC decoder; each successful return checks actual spec count==host ch and1024 frames, copy then C-vector append, CRC failure returns before append.')
 node('HADTS','hostaac','decode_adts','Validated ADTS units with consistent configuration -> decode_units -> Decoded.finish; no decoder object escape.')
 node('HMP4','hostaac','decode_mp4','MP4/esds ASC and units -> same decode_units -> finish; new decoder per stream, no cross-stream alias.')
 node('HALLOC','hostcommon','alloc','try_reserve_exact returns empty Vec with CAPACITY only; host outer loop pushes exactly C entries; allocation failure is not success.')
 node('HFIN','hostcommon','finish','Validates declared channels/rate, per-plane raw length/finite/trim. It does NOT check outer-plane count; caller inductive construction provides that premise.')
 by={n['id']:n for n in nodes}
 edges={'BNEW':['COUNT'],'BUNUSED':['COUNT'],'BSPEC':['SPECCHAN'],'BTRIM':['BTRUNC','BSHIFT','BFRAMES'],
 'BSHIFT':['BCLEAR'],'ACOPY':['BPLANES','BFRAMES','BITER'],'GCOPY':['ACOPY'],
 'MNEW':['MSTATE'],'MINNER':['MHDR','BUNUSED','BNEW','MSPEC','BSPEC','BCLEAR','LDECODE','BTRIM'],
 'MREF':['MINNER','BCLEAR'],'MSPEC':['MNCHAN','SPECNEW'],'LDECODE':['BRENDER','BPMUT','LSYNTH'],
 'ANEW':['ASC','COUNT','SPECNEW','BNEW'],'ASETPAIR':['COUNT'],'AGA':['ASETPAIR','ASYNTH'],
 'AINNER':['BCLEAR','BRENDER','AGA'],'AREF':['AINNER','BCLEAR'],'ASYNTH':['BPMUT','ICS'],'ICS':['DSP'],
 'HMP3':['HHDR','MNEW','MREF','COUNT','GCOPY','HALLOC','HFIN'],
 'HUNIT':['ANEW','AREF','COUNT','GCOPY','HALLOC'],
 'HADTS':['HASC','HUNIT','HFIN'],'HMP4':['HASC','HUNIT','HFIN']}
 for id,targets in edges.items():by[id]['edges'] += [dict(kind='AUDITED',target=t) for t in targets]
 contracts=[
 ('BNEW','Pinned SmallVec/Vec resize_with/move/clone contracts: successful resize gives requested length, allocation/panic not successful return.'),
 ('BPMUT','Rust safe slice borrow cannot access private owner fields or resize parent outer storage; compiler/container memory safety is an explicit conditional premise.'),
 ('LSYNTH','Cooperating Rust safe fixed-slice operations preserve owner metadata by capability separation, irrespective of sample arithmetic.'),
 ('DSP','Cooperating Rust safe fixed-slice operations preserve owner metadata; no numerical-quality or no-panic theorem.'),
 ('GCOPY','Generic dispatch macro maps F32 to concrete f32 borrow, AsGenericAudioBufferRef generated implementation is same object reference.'),
 ('ACOPY','Standard resize/zip/slice iteration and conversion contracts; carried239 per-plane copy bridge, no additional outer-plane mutation.'),
 ('MRESET','State reset cannot mutate disjoint private audio buffer under safe exclusive Rust ownership.'),
 ('ARESET','Pair reset has no buffer/spec reference and no retained mutable alias to private buffer; see source structs/lifetimes.'),
 ('HFIN','Safe Vec push/extend/zip lengths with valid allocation, ordinary integer representability and carried239 bridge. finish alone is NOT P=C proof.')]
 for id,arg in contracts:by[id]['edges'].append(dict(kind='NAMED_CONTRACT',argument=arg,source_pin=files[by[id]['path']]['blob']))
 for id in ['LDECODE','AGA','ICS','DSP']:
  by[id]['edges'].append(dict(kind='PROVED_UNREACHABLE',argument='Cardinality write through arithmetic-only callees without owner/spec/container capability: explicit arguments are separate codec state, immutable header/data or fixed sample slices. Safe-code module forbids unsafe; no static owner alias. Numerical output/callee arithmetic is outside this invariant, not assumed numerically correct.',source_pin=files[by[id]['path']]['blob']))
 by['MSTATE']['edges'].append(dict(kind='PROVED_UNREACHABLE',argument='Layer1/2 decoding branches are compiled alternatives but host HHDR rejects their frame layer and HMP3 creates CODEC_ID_MP3 state. No registry-based alternative constructor is used by this host path.',source_pin=files[aliases['hostmp3']]['blob']))
 # Each row has a distinct argument; Software conditional derivation still requires independent source judgment.
 shared={
 'constructor':('BNEW','Constructor count equals resize_with length and stores same owned spec; valid allocation and stable container contracts are named, zero frames does not change P.'),
 'ownership_alias':('BPMUT','Private AudioBuffer owns spec and SmallVec; decoder owns buffer; public spec is immutable and plane_mut yields only a slice. No mutable spec/outer-plane alias escapes in the capability census.'),
 'spec_count':('COUNT','Channels::count uses popcount for positioned mask, not raw bitmask; admitted mono/stereo count1/2. Owned cloned representation remains stable.'),
 'clear_trim_render':('BTRIM','clear/render/truncate/shift write frame count or existing samples only. trim composes truncate+shift; no spec or outer length mutation, including zero frames.'),
 'returned_frame':('GCOPY','Successful decode_ref returns generated F32 borrow of exact owned buffer. Generic macro dispatch and concrete num_planes/frames/plane slicing preserve correspondence.'),
 'host_copy_finish':('HFIN','Host spec-count guard gives bufferC=hostC; constructor+mutator induction gives P=bufferC. Copy outer resize=P and host outer construction=C make zip exhaustive. finish validates lengths but cannot supply missing outer-count premise by itself.')}
 mp={
 'admission':('HMP3','Host HHDR only LayerIII; frame walk rejects version/rate/mono change; fresh MP3-coded decoder uses same units. Bit parsing success and bounds errors remain error/refusal exits.'),
 'dispatch':('MSTATE','CODEC_ID_MP3 selects Layer3. decode_inner additionally matches Layer3 header; host refuses LayerI/II. Other constructors/registry entry points are not used in this admitted path.'),
 'mutable_decode':('LDECODE','Clear then Layer3 may render valid frames and synthesize through fixed slices only. Body passes no output buffer into bitstream/requantization/stereo/hybrid callees; no output metadata capability crosses those calls.'),
 'reuse_reset':('MRESET','Reset replaces separate codec state, retaining invariant buffer. Error decode_ref clear preserves P/spec, so later reuse starts valid even if reservoir/internal numerical state was corrupted.'),
 'replacement_transition':('MINNER','Default buffer is never returned as successful frame before unused branch constructs fresh AudioBuffer from header spec. Later differing spec rejects before decode; whole replacement reestablishes invariant, not transfer by name. New host stream creates new decoder.'),
 'success_error':('MREF','Every decode error clears frames then returns Err; no successful frame is inferred from error/panic. Partial sample/frame mutations before error do not mutate P/spec and clear restores zero valid frames.')}
 aa={
 'admission':('ANEW','Host ASC admits LC/config1/2/1024; constructor independently rejects nonAAC, unknown channels, nonLC/SBR/>2 or non1024. Successful host frames additionally guard actual specC=host ch, so disagreement refuses before append.'),
 'dispatch':('AINNER','Only LC decode_ga branch can return Ok under constructor. Unsupported element/coupling/PCE/SBR paths refuse; no alternate codec engine can be returned by direct AacDecoder constructor.'),
 'mutable_decode':('AGA','decode_ga changes pair/ICS/CRC state then synth_audio. set_pair validates indices; synth_audio passes only plane_mut slices into ICS/DSP. No buffer/spec/outer-vector replacement exists in its source.'),
 'reuse_reset':('ARESET','Reset mutates pair state only. Error path clear leaves buffer P/spec unchanged; failed set_pair may leave pair state but later success revalidates indices, and even invalid pair panic cannot become successful frame.'),
 'replacement_transition':('ANEW','ASC/spec/buffer are owned at constructor. No subsequent assignment to buf/spec/planes/ASC channels exists in reachable AAC methods. New ADTS/MP4 host stream constructs fresh decoder; host guards actual channel correspondence each returned unit.'),
 'success_error':('AREF','decode_inner may render before a later error; decode_ref error clears only valid frames and returns Err. P/spec were preserved by all capability-carrying edges, so a later successful reuse remains valid.')}
 assumptions=['Rust type/privacy/borrow/memory safety and no UB outside safe contracts',
  'Successful valid allocation; SmallVec/Vec length, clone, iteration and slice contracts at locked dependency versions',
  'Owned stable AudioSpec/channel representation; no foreign mutation/unsafe fabricated private states',
  'Successful admitted host packet/frame path only; integer/count arithmetic representable in mono/stereo valid allocations',
  'Carried239 exact copy/count/PCM/FLAC bridges remain conditional at their original scope']
 codecs={}
 for codec,extra in [('MP3',mp),('AAC',aa)]:
  rows={}
  for obligation,(id,arg) in {**shared,**extra}.items():rows[obligation]=dict(verdict='PROVED_CONDITIONAL',argument=arg,premises=assumptions,nodes=[id])
  assert set(rows)==set(OBLIGATIONS);codecs[codec]=rows
 ledger=dict(source=SOURCE,new_decoder_runs=0,scope='CARDINALITY_ONLY',library_assumptions_explicit=True,nodes=nodes,codecs=codecs,
             lemmas={'MP3':'PROVED_CONDITIONAL','AAC':'PROVED_CONDITIONAL'},global_internal='UNPROVED',fixture_outcomes_prove_universal=False,
             graph_roots=['HMP3','HADTS','HMP4'],assumptions=assumptions,
             graph_interpretation='Complete owner/spec/outer-plane capability closure; sample-only arithmetic graph cut has explicit safe-type argument, not numerical audit.')
 shape=check_ledger(ledger);save(a.out/'LEDGER.json',ledger)
 keys=['admitted','stable_spec','count_not_mask','constructor','all_mutators','exclusive_owner','replacement','transition','reset','clear_trim_render','dispatch','success_guard','return_correspondence','host_guard','append_copy','finish']
 controls=[]
 for key in keys:
  request={k:True for k in keys};request[key]=False;accepted=premise_model(request);assert accepted is False
  controls.append(dict(kind='ABSTRACT PRIVATE-STATE PREMISE FALSIFIER, NOT admitted codec input',false_premise=key,input=request,accepted=accepted))
 save(a.out/'CONTROLS.json',controls)
 result=dict(source=SOURCE,method='4c84472d1c7b474a3a9e6ec679889e0d89a9a6fc',shape=shape,nodes=len(nodes),source_files=len(files),premise_falsifiers=len(controls),
             new_decoder_runs=0,new_codec_builds=0,software_lemmas=ledger['lemmas'],independent_disposition='PENDING',
             parent_cpu_ns=time.process_time_ns()-start,wall_ns=time.monotonic_ns()-wall,
             conservative_total_cpu_reserve_seconds=600,child_git_cpu_not_individually_measured=True,
             source_helper_sha256=sha(pathlib.Path(__file__).read_bytes()),pid=os.getpid(),parent=os.getppid())
 save(a.out/'COMMANDS.json',COMMANDS)
 save(a.out/'RESULT.json',result)
 save(a.out/'FILES.json',{p.relative_to(a.out).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p.read_bytes())) for p in sorted(a.out.rglob('*')) if p.is_file()})
 print(json.dumps(result))
if __name__=='__main__':main()
