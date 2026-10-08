#!/usr/bin/env python3
"""Build and execute the unchanged READ-1 package; retain factual artifacts."""
import argparse,hashlib,json,os,subprocess,sys,tarfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
PACKAGE=ROOT/'tests/playback_readonly_r1'
ADAPTER=Path(__file__).resolve().parent
BASELINE='9e902cf04b6d0c02363870fb9bc201e40239b509'
FLAGS=['-std=c99','-Os','-Wall','-Wextra','-Werror','-fno-common','-g','-fPIC']

def run(args,**kwargs):
    print('+ '+ ' '.join(map(str,args)),flush=True)
    subprocess.run(list(map(str,args)),check=True,**kwargs)
def output(args):return subprocess.check_output(list(map(str,args)),text=True).strip()
def sha(p):
    h=hashlib.sha256()
    with open(p,'rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()
def build(source,dest,observed=False):
    dest.mkdir(parents=True,exist_ok=True)
    inc=['-I'+str(source/'engine/include'),'-I'+str(source/'engine/src'),'-I'+str(ROOT/'engine/src')]
    flags=FLAGS+(['-DTAPE_READ1_OBSERVE'] if observed else [])
    units=sorted((source/'engine/src').glob('*.c'))
    objects=[];layers={'preprocess':[],'object':[],'link':[]}
    for unit in units+[ADAPTER/'bridge.c',PACKAGE/'counting_device.c']:
        obj=dest/(unit.stem+'.o');objects.append(obj)
        run(['cc',*flags,*inc,'-c',unit,'-o',obj])
        if unit in units:
            pre=dest/(unit.stem+'.i')
            with pre.open('w') as f:run(['cc',*flags,*inc,'-E','-P',unit],stdout=f)
            layers['preprocess'].append(pre)
            record=dest/(unit.stem+'.object.txt')
            with record.open('w') as f:
                run(['nm','-a',obj],stdout=f);run(['objdump','-drs',obj],stdout=f);run(['size','-A',obj],stdout=f)
            layers['object'].append(record)
    library=dest/'libengine.so';linkmap=dest/'engine.map'
    run(['cc','-shared',*objects,'-Wl,-Map='+str(linkmap),'-o',library])
    symbols=dest/'link-symbols.txt'
    with symbols.open('w') as f:run(['nm','-a',library],stdout=f);run(['objdump','-h',library],stdout=f)
    layers['link']=[linkmap,symbols]
    executable=dest/'adapter'
    run(['cc',*FLAGS,'-DADAPTER_PATH="'+str(ADAPTER/'adapter.py')+'"','-DLIBRARY_PATH="'+str(library)+'"',ADAPTER/'launcher.c','-o',executable])
    return executable,library,units,layers

def main():
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);p.add_argument('--small',action='store_true');a=p.parse_args()
    out=Path(a.out).resolve();out.mkdir(parents=True,exist_ok=True)
    head=output(['git','rev-parse','HEAD']);tree=output(['git','rev-parse','HEAD:engine'])
    if output(['git','status','--porcelain','--untracked-files=no']):raise RuntimeError('qualification requires committed source')
    for name in ('check_pins.py','selftest.py'):run([sys.executable,'-B',PACKAGE/name])
    instrumented,ilib,units,ilayers=build(ROOT,out/'build/instrumented',True)
    shipping,slib,_,slayers=build(ROOT,out/'build/shipping')
    baseline_root=out/'baseline-source';baseline_root.mkdir(exist_ok=True)
    archive=subprocess.check_output(['git','archive',BASELINE,'engine'])
    import io
    with tarfile.open(fileobj=io.BytesIO(archive)) as t:t.extractall(baseline_root)
    baseline,blib,_,_=build(baseline_root,out/'build/baseline')
    provenance={'product_commit':head,'engine_tree':tree,'import_tree':output(['git','rev-parse','HEAD:tests/playback_readonly_r1']),
                'compiler':output(['cc','--version']),'flags':FLAGS,'observed_define':'TAPE_READ1_OBSERVE',
                'sources':{str(p.relative_to(ROOT)):sha(p) for p in [*units,*sorted(ADAPTER.glob('*.c')),*sorted(ADAPTER.glob('*.py')),ROOT/'engine/src/read1_observe.h']},
                'instrumented_library_sha256':sha(ilib),'shipping_library_sha256':sha(slib),'baseline_library_sha256':sha(blib),
                'baseline_commit':BASELINE,'baseline_engine_tree':output(['git','rev-parse',BASELINE+':engine']),
                'adapter_sha256':sha(instrumented),'shipping_adapter_sha256':sha(shipping),'baseline_adapter_sha256':sha(baseline)}
    (out/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
    for name,layers,kind in [('shipping',slayers,'actual-shipping-absence'),('leak',ilayers,'actual-deliberate-shipping-leak')]:
        manifest={'kind':kind,'product_commit':head,'engine_tree':tree,'translation_units':[str(u.relative_to(ROOT)) for u in units],
                  'layers':{l:[{'file':str(f.relative_to(out)),'sha256':sha(f)} for f in fs] for l,fs in layers.items()}}
        (out/(name+'-absence.json')).write_text(json.dumps(manifest,indent=2)+'\n')
    args=[sys.executable,'-B',PACKAGE/'runner.py','--adapter',instrumented,'--shipping-adapter',shipping,'--baseline-adapter',baseline,
          '--baseline-product-commit',BASELINE,'--product-commit',head,'--engine-tree',tree,'--adapter-sha256',sha(instrumented),'--out',out/'run']
    if a.small:
        sys.path.insert(0,str(PACKAGE));import cases
        for c in cases.cases():
            if c['id']!='full-C60-b1024':args+=['--case',c['id']]
    run(args)
    run([sys.executable,'-B',PACKAGE/'controls.py','--adapter',instrumented,'--product-commit',head,'--engine-tree',tree,'--out',out/'controls'])
    if not a.small:run([sys.executable,'-B',PACKAGE/'qualification.py','--run',out/'run','--controls',out/'controls','--product-commit',head,'--engine-tree',tree])
    with (out/'absence-result.json').open('w') as f:
        run([sys.executable,'-B',PACKAGE/'absence.py','--shipping',out/'shipping-absence.json','--leak-control',out/'leak-absence.json','--product-commit',head,'--engine-tree',tree],stdout=f)
    if not a.small:run([sys.executable,'-B',PACKAGE/'runner.py','--replay',out/'run/observations.jsonl.gz','--out',out/'replay'])
    # Images and their intentional sparse holes are reproducible fixture inputs.
    # Retain every raw callback log and observation; omit only image/dirty media.
    with tarfile.open(out/'evidence.tar.gz','w:gz',compresslevel=1) as tar:
        for f in sorted(out.rglob('*')):
            if f.is_file() and f.name!='evidence.tar.gz' and f.suffix!='.img' and 'baseline-source' not in f.parts:
                tar.add(f,arcname=str(f.relative_to(out)),recursive=False)
    (out/'SHA256SUMS').write_text(sha(out/'evidence.tar.gz')+'  evidence.tar.gz\n')
if __name__=='__main__':main()
