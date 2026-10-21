"""One bounded C254 activation, with original-byte inputs and no shipping CLI.

Build is a minimal test crate containing exact pinned Product modules plus listed
observation-only insertions. No decoder, publisher or engine is linked. Native
operations pass through the unchanged cleared recorder's Python helper contract.
"""
import argparse
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import secrets
import shutil
import struct
import subprocess
import sys
import time
import wave
import zipfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
SOURCE = 'b9f430c8c9b33532abf07eea0ed2653310639f2d'
sha = lambda b: hashlib.sha256(b).hexdigest()


def emit(p, obj):
    with p.open('xb') as f:
        f.write((json.dumps(obj, sort_keys=True, indent=2)+'\n').encode())


def loadmod(name, path):
    sp=importlib.util.spec_from_file_location(name,path)
    m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m);return m


def git(path):
    return subprocess.check_output(['git','show',SOURCE+':'+path],cwd=REPO)


def inventory(root):
    return {p.relative_to(root).as_posix():dict(bytes=p.stat().st_size,sha256=sha(p.read_bytes()))
            for p in sorted(root.rglob('*')) if p.is_file()}


def prepare(work):
    work.mkdir()
    src=work/'crate'/'src';src.mkdir(parents=True)
    pins={}
    for name in ('common','dsp','convert','observe','mem'):
        raw=git('host/ingest/src/'+name+'.rs');pins[name]=sha(raw)
        (src/(name+'.rs')).write_bytes(raw)
    assert pins['dsp']=='fb77778e7f271f2acb1c385ee9e8235e0752f3f1318caf3e7fddcc410a230ffc'
    dsp=(src/'dsp.rs').read_text()
    edits=[
      ('        if hi <= lo {','        crate::trace(format!("{{\\"kind\\":\\"range\\",\\"length\\":{},\\"lo\\":{lo},\\"hi\\":{hi}}}",x.len()));\n        if hi <= lo {'),
      ('                gmax = gmax.max(v);','                let old_gmax = gmax;\n                gmax = gmax.max(v);'),
      ('                if v > 0.0 && v >= gmax * 0.90 && v >= prev && v >= next {','                let decision = v > 0.0 && v >= gmax * 0.90 && v >= prev && v >= next;\n                if old_gmax != gmax || decision { crate::trace(format!("{{\\"kind\\":\\"history\\",\\"n0\\":{n0},\\"lane\\":{p},\\"v_le\\":\\"{}\\",\\"prev_le\\":\\"{}\\",\\"next_le\\":\\"{}\\",\\"gmax_le\\":\\"{}\\",\\"refine\\":{decision}}}",s513hex(&v.to_le_bytes()),s513hex(&prev.to_le_bytes()),s513hex(&next.to_le_bytes()),s513hex(&gmax.to_le_bytes()))); }\n                if decision {'),
      ('        best\n    }','        crate::trace(format!("{{\\"kind\\":\\"range-result\\",\\"peak_le\\":\\"{}\\"}}",s513hex(&best.to_le_bytes())));\n        best\n    }')]
    for old,new in edits:
        assert dsp.count(old)==1,(old,dsp.count(old));dsp=dsp.replace(old,new)
    dsp+='\n'+(HERE/'expose.rs').read_text()
    (src/'dsp.rs').write_text(dsp)
    cv=(src/'convert.rs').read_text()
    old='        let lin_gain = libm::pow(10.0, g / 20.0);'
    new=old+'\n        crate::trace(format!("{{\\"kind\\":\\"attempt\\",\\"gain_db_le\\":\\"{}\\",\\"linear_gain_le\\":\\"{}\\",\\"limited\\":{limited}}}",dsp::s513hex(&g.to_le_bytes()),dsp::s513hex(&lin_gain.to_le_bytes())));'
    assert cv.count(old)==1;cv=cv.replace(old,new);(src/'convert.rs').write_text(cv)
    shutil.copyfile(HERE/'main.rs',src/'main.rs')
    # Exact production dependency identity/checksum is in its retained lockfile.
    (work/'crate'/'Cargo.toml').write_text('[package]\nname="meter-precision-513"\nversion="0.0.0"\nedition="2021"\n[dependencies]\nlibm={version="=0.2.16",default-features=false}\n[features]\nobserve=[]\n[profile.release]\nopt-level=3\ncodegen-units=1\nlto="thin"\npanic="abort"\noverflow-checks=true\n[workspace]\n')
    (work/'production-Cargo.lock').write_bytes(git('host/ingest/Cargo.lock'))
    emit(work/'SOURCE.json',dict(source=SOURCE,original_modules=pins,observation_edits=edits,
         compiled=inventory(src),scope='test-only modules, no shipping decoder/CLI/publish/engine'))
    model=git('tests/wp16_ingest_stage1/model.py')
    assert sha(model)=='4dfc0d0987eea047968db046e088e4124dcc55ca47a618f66fa51ea9cea1e9d9'
    (work/'pinned-independent-model.py').write_bytes(model)


def run(work, archive):
    # Resource total includes prepared/build workspace; never hide target storage.
    import resource
    from os import cpu_count
    started=time.monotonic();wall=time.time_ns()
    out=work/'return';out.mkdir()
    emit(out/'ACTIVATION.json',dict(source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip(),
          production_source=SOURCE,recorder_clearance='87e94160f62922a06346d00dc69f4dfcda987328',
          method='79890e243c387ef0663a1278276c3c6792f29073',start_unix_ns=wall,
          cpu_reserve_seconds=600,limit_cpu=7200,limit_bytes=536870912))
    binary=work/'crate'/'target'/'release'/'meter-precision-513'
    assert binary.is_file()
    recorder=loadmod('recorder',REPO/'host/evidence-recorder/recorder.py')
    assert sha((REPO/'host/evidence-recorder/recorder.py').read_bytes())=='eb3597ad4ff378d2d140e116b659be467489c03ec77d60f24a2ecb91ccec7cf2'
    oracle=loadmod('coordinates',REPO/'tests/meter_precision_r1/oracle.py')
    model=loadmod('pinned_quantizer',work/'pinned-independent-model.py')
    selected=json.loads((REPO/'tests/meter_precision_r1/SELECTED.json').read_bytes())
    assert sha(archive.read_bytes())==selected['original_inner_sha256']
    z=zipfile.ZipFile(archive)
    inputs=out/'inputs';inputs.mkdir()
    for case in selected['cases']:
        for fact in case['original_files']:
            raw=z.read(fact['path']);assert len(raw)==fact['bytes'] and sha(raw)==fact['sha256']
            p=inputs/fact['path'];p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw)
    requests=out/'requests';requests.mkdir()
    domain=out/'domain';domain.mkdir()
    observations=[];evaluations=[];pending_stream=[]

    def gate():
        ch=resource.getrusage(resource.RUSAGE_CHILDREN)
        cpu=600+time.process_time()+ch.ru_utime+ch.ru_stime
        size=sum(p.stat().st_size for p in work.rglob('*') if p.is_file())
        assert cpu+60<7200 and size+32*1024*1024<536870912, (cpu,size)

    def invoke(name, mode, inp, extra, named):
        gate()
        dd=domain/name
        argv=[str(binary),mode,str(inp),str(dd/'trace.jsonl'),*map(str,extra)]
        payload=dict(domain_dir=str(dd),argv=argv,binary_sha256=sha(binary.read_bytes()),source=SOURCE,
                     inputs={str(inp):sha(inp.read_bytes()),**{str(p):sha(p.read_bytes()) for p in named}})
        pp=requests/(name+'-payload.json');emit(pp,payload)
        nonce=secrets.token_hex(16);stage=out/'owned'/'incoming'/name/'input.bin'
        request=dict(case_id=name,argv=[str(Path(sys.executable).resolve()),'-B',str(HERE/'adapter.py'),
                      '--input',str(stage),'--nonce',nonce],nonce=nonce,mode='text',
                     input_sha256=sha(pp.read_bytes()),binary_sha256=sha(Path(sys.executable).resolve().read_bytes()),
                     helper_sha256=sha((HERE/'adapter.py').read_bytes()),source_commit=payload_source)
        emit(requests/(name+'.json'),request)
        recorder.record(out/'owned',request,pp)
        recorder.validate_case(out/'owned'/'cases'/name,request)
        lines=[json.loads(x) for x in (dd/'trace.jsonl').read_text().splitlines()]
        assert lines[0]['pid']==json.loads((dd/'LAUNCH.json').read_bytes())['pid']
        observations.append(dict(name=name,domain_manifest=sha((dd/'MANIFEST.json').read_bytes()),events=len(lines)))
        return lines,dd

    payload_source=json.loads((out/'ACTIVATION.json').read_bytes())['source']
    try:
      first=True
      for case in selected['cases']:
        name=case['name'];base=inputs/name
        manifest=json.loads((base/'published/manifest.json').read_bytes())
        for idx,s in enumerate(manifest['sources']):
            original=base/('folder'+s['logical_path'])
            with wave.open(io.BytesIO(original.read_bytes())) as w:
                assert w.getframerate()==44100 and w.getsampwidth()==2
                channels=w.getnchannels();pcm=w.readframes(w.getnframes())
            assert s['trim_head']==s['trim_tail']==0
            ip=inputs/(name+'-source-'+str(idx)+'.bin');ip.write_bytes(pcm)
            op=domain/(name+'-source-'+str(idx))/'converted.pcm'
            lines,dd=invoke(name+'-source-'+str(idx),'convert',ip,[op,channels],[])
            attempts=[x for x in lines if x['kind']=='attempt'];gain=struct.unpack('<d',bytes.fromhex(attempts[-1]['linear_gain_le']))[0]
            rows=([v/32768*gain for v in row] for row in struct.iter_unpack('<h' if channels==1 else '<hh',pcm))
            expected=model.quantize(rows,mono=channels==1)
            old=base/('converted-'+s['logical_path'].replace('/','-')+'.pcm')
            observations[-1].update(attempts=len(attempts),gain_bits=attempts[-1]['linear_gain_le'],
                independent_quantizer_equal=expected==op.read_bytes(),original_pcm_equal=old.read_bytes()==op.read_bytes(),
                dither_reset='original quantize calls Xorshift::new per source/attempt; seed6d2b79f5; no shared state')
        # Original assembled PCM coordinates; never generated replacement shipping bytes.
        with wave.open(io.BytesIO((base/'published/audio.wav').read_bytes())) as w:
            assert w.getnchannels()==2 and w.getsampwidth()==2
            pcm=w.readframes(w.getnframes());frames=len(pcm)//4
        boundaries={0,frames}
        for s in manifest['sources']: boundaries.update((s['start_frame'],s['start_frame']+s['output_frames']))
        lo=-256
        while lo<frames+256:
            hi=min(lo+(1<<20),frames+256);boundaries.update((lo,hi));lo=hi
        points=sorted({divmod(((b+d)*256+q)+r,256) for b in boundaries
             for d in (-257,-256,-255,-1,0,1,255,256,257) for q in (0,64,128,192) for r in (-63,-1,0,1,63)})
        coords=inputs/(name+'-coords.txt');coords.write_text(''.join(f'{n} {q}\n' for n,q in points))
        for channel in (0,1):
            plane=b''.join(struct.pack('<f',r[channel]/32768) for r in struct.iter_unpack('<hh',pcm))
            ip=inputs/(name+'-channel-'+str(channel)+'.f32');ip.write_bytes(plane)
            mode='coeff' if first else 'eval';extra=[coords]
            if first:extra.append(domain/(name+'-channel-'+str(channel))/'coefficients.f32')
            lines,dd=invoke(name+'-channel-'+str(channel),mode,ip,extra,[coords]);first=False
            vals=[x for x in lines if x['kind']=='evaluation'];assert len(vals)==len(points)
            for row in vals:
                n,q=row['n0'],row['q'];oracle.ieee(row['at_le'],'f32')
                assert row['grid_le']==row['grid_at_abs_le']
                # Both global and streamed-buffer mappings are externally bound.
                block_lo=max(-256, -256+((n+256)//(1<<20))*(1<<20))
                bind=dict(signed_phase=n*256+q,n0=n,q=q,support=[n-255,n+256],source_start=0,
                          source_local=n,global_sample=n,block_lo=block_lo,buffer_local=n-block_lo+258)
                oracle.coordinates(bind)
                support=b''.join(plane[k*4:k*4+4] if 0<=k<frames else bytes(4) for k in range(n-255,n+257))
                evaluations.append(dict(case=name,channel=channel,**bind,at_le=row['at_le'],support_sha256=sha(support)))
            pending_stream.append((name,channel,ip,coords))
      emit(out/'EVALUATIONS.json',evaluations)
      # Actual observation-copy mutations with original external coordinate request.
      mutants=[]
      good=evaluations[0]
      for key,val in [('q',(good['q']+1)%256),('support',[good['support'][0]+1,good['support'][1]]),
                      ('global_sample',good['global_sample']+1),('block_lo',good['block_lo']+1)]:
          bad=copy.deepcopy(good);bad[key]=val
          try:oracle.coordinates(bad)
          except AssertionError:rejected=True
          else:rejected=False
          assert rejected;mutants.append(dict(mutation=key,observation=bad,sha256=sha(json.dumps(bad,sort_keys=True).encode()),rejected=True))
      exact=next(o['gain_bits'] for o in observations if o.get('gain_bits'))
      rounded=struct.pack('<d',round(struct.unpack('<d',bytes.fromhex(exact))[0],6)).hex()
      # If the first gain is exactly 1, use the already observed attenuated source.
      if rounded==exact:
          exact=next(o['gain_bits'] for o in observations if o.get('gain_bits') and struct.pack('<d',round(struct.unpack('<d',bytes.fromhex(o['gain_bits']))[0],6)).hex()!=o['gain_bits'])
          rounded=struct.pack('<d',round(struct.unpack('<d',bytes.fromhex(exact))[0],6)).hex()
      assert not oracle.bind_gain(rounded,'f64',exact,'f64')
      mutants.append(dict(mutation='rounded-gain',original=exact,observation=rounded,rejected=True))
      emit(out/'MUTANTS.json',mutants)
      # Full actual streamed histories run last. The first timeout/failure stops
      # the activation; earlier complete originals are still usable finite facts.
      for name,ch,ip,coords in pending_stream:
          invoke(name+'-stream-'+str(ch),'stream',ip,[coords],[coords])
    except Exception as error:
      emit(out/'STOP.json',dict(type=type(error).__name__,message=str(error),no_retry=True))
      raise
    finally:
      emit(out/'OBSERVATIONS.json',observations)
      emit(out/'FINAL-TIMING.json',dict(wall_ns=round((time.monotonic()-started)*1e9),reserve_cpu_seconds=600,
           used_parent_seconds=time.process_time(),used_children_seconds=resource.getrusage(resource.RUSAGE_CHILDREN).ru_utime+resource.getrusage(resource.RUSAGE_CHILDREN).ru_stime,
           build_time_receipt='separate GNU time receipt, included in600 reservation; gate before every native command',host_cpus=cpu_count()))
      emit(out/'FILES.json',inventory(out))
      with zipfile.ZipFile(work/'software513-exact-return.zip','x',zipfile.ZIP_DEFLATED) as zz:
          for f in sorted(out.rglob('*')):
              if f.is_file():zz.write(f,f.relative_to(out).as_posix())


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('mode',choices=['prepare','run']);p.add_argument('--work',type=Path,required=True);p.add_argument('--archive',type=Path)
    a=p.parse_args();w=a.work.resolve()
    if a.mode=='prepare':prepare(w)
    else:run(w,a.archive.resolve())
