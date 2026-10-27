"""Evaluate candidate observation packets against the frozen complete census.
This emits a gate report, never an automatic shipping/physical acceptance.
"""
import argparse,json,unicodedata
from pathlib import Path
import numpy as np
import asset,audit,cases,formats,fixtures,model,conversion,qualification,relations,large,filter_bounds

def reviewed(receipts,key,hashes=()):
    r=receipts['checks'][key]
    audit.require(r['decision']=='PASS' and r['reviewer']=='Verification' and bool(r['notes']),'review','independent review missing: '+key)
    audit.require(set(hashes)<=set(r['artifact_sha256']),'review','unbound evidence: '+key)


def inside(root,name):
    p=(root/name).resolve();assert p.is_relative_to(root.resolve()),'escaping evidence path';return p

def check(root,source_root,receipts):
    root=Path(root);source_root=Path(source_root)
    index=json.loads((root/'INDEX.json').read_text(encoding='utf-8'));facts=json.loads((source_root/'SOURCES.json').read_text(encoding='utf-8'))
    assert asset.sha_file(source_root/'SOURCES.json')==json.loads((Path(__file__).parent/'ASSET.json').read_text(encoding='utf-8'))['sources_sha256']
    catalog=cases.expand(facts)
    observations=index['cases'];assert set(observations)=={c['id'] for c in catalog},'missing/extra cases; no waived matrix members'
    for key in ('candidate_sha','binary_sha256','tool_version','profile','platform','architecture','config_sha256'):assert index[key]
    assert (index['platform'],index['architecture']) in [('windows11','x64'),('macos','arm64'),('linux','x64')]
    assert all(receipts[k]==index[k] for k in ('candidate_sha','binary_sha256','profile','platform','config_sha256'))
    path=inside(root,index['profile_file']);profile=json.loads(path.read_text(encoding='utf-8'));reviewed(receipts,'profile',[asset.sha_file(path)])
    for key in ('decoder-mapping','libraries-config','manifest-field-truth','filesystem','observer-controls','instrumented-shipping-equivalence','meter-math'):reviewed(receipts,key)
    results=[];outputs={};qualified_rates=set()
    for case in catalog:
        record=json.loads(inside(root,observations[case['id']]).read_text(encoding='utf-8'));code=record['exit'];expected=case['expected_exit']
        assert code is None or type(code)is int,'noninteger command exit'
        assert expected is None or code==expected or isinstance(expected,list) and code in expected,(case['id'],'exit')
        assert record['argv'] and record['stdout_file'] and record['stderr_file'] and record['config_sha256']==index['config_sha256']
        stdout=inside(root,record['stdout_file']).read_bytes().decode(record.get('stdout_encoding','utf-8'))
        stderr=unicodedata.normalize('NFC',inside(root,record['stderr_file']).read_bytes().decode(record.get('stderr_encoding','utf-8')))
        native_path=inside(root,record['native_record']);native=json.loads(native_path.read_text(encoding='utf-8'));assert native['exit']==code
        expected_scenario=case.get('scenario') or ('success' if code==0 else 'preflight-refusal' if code==2 else 'write-error')
        assert native['scenario']==expected_scenario,'wrong native scenario for '+case['id']
        trace=inside(root,record['raw_trace']);assert asset.sha_file(trace)==native['raw_trace_sha256']
        reviewed(receipts,'native:'+case['id'],[asset.sha_file(inside(root,observations[case['id']])),asset.sha_file(native_path),asset.sha_file(trace)])
        native['raw_review']='PASS' # Established above by Verification, not Software.
        audit.transaction(native)
        if case.get('scenario')=='informational':
            assert not native['dest_after'] and not native['owned_stage_after'] and not any(e['op'] in ('stage_create','output_open','device_open') for e in native['events'])
            assert stdout.strip()
            if case['id']=='cli/version':assert index['tool_version'] in stdout and index['profile'] in stdout
        if (code!=0 and native['dest_after']!=['audio.wav','manifest.json']) or case.get('scenario')=='informational':
            if code==2:
                assert stderr.strip(),case['id']+' unnamed refusal'
                if case['id'].startswith(('asset/','adr180/neighbour/')) or case['id']=='trim/outside-neighbour':
                    bad=[e for folder in case['folders'] for e in folder if facts[e['asset']].get('refuse')]
                    if not bad:bad=[e for folder in case['folders'] for e in folder]
                    assert any(e['name'] in stderr for e in bad),'source name missing'
                if case['id'].startswith('zero/') or case['id'] in ('asset/zero-192-n1.wav','asset/zero-192-n2.wav'):
                    assert 'too short' in stderr.lower() and any(e['name'] in stderr for folder in case['folders'] for e in folder if e['asset'].startswith('zero-'))
                if case['id'] in ('capacity/one-over','capacity/gap-one-over'):assert '1' in stderr and '00:01' in stderr,'exact overage diagnostic'
            results.append({'id':case['id'],'gates':'exit/native predicates checked'});continue
        if case['id']=='capacity/riff-largest-legal':
            raw=inside(root,record['manifest']).read_bytes();f=facts['riff-largest-source.wav']
            assert asset.sha_file(source_root/f['path'])==f['sha256']
            outputs[case['id']]=large.check(inside(root,record['wav']),raw,f,case['folders'][0][0]['name'],case['seconds'],record['before'],record['joined_dbtp'])
            manifest=json.loads(raw);assert manifest['tool_version']==index['tool_version'] and manifest['build_profile']==index['profile']
            assert record['summary']=={'peak_limited':0,'unmeasurable':0,'gapless_unknown':0}
            reviewed(receipts,'summary:'+case['id'],[asset.sha_file(inside(root,record['stdout_file']))]);results.append({'id':case['id'],'gates':'streamed full large zero WAV/native/manifest'});continue
        pcm=model.pcm_from_wav(inside(root,record['wav']).read_bytes());raw=inside(root,record['manifest']).read_bytes()
        ordered=[];names=[]
        for folder in case['folders']:
            group=sorted(folder,key=lambda f:model.name_key(f['name']));names.append([f['name'] for f in group]);ordered.extend(group)
        source_facts=[]
        for entry in ordered:
            f=dict(facts[entry['asset']]);assert asset.sha_file(source_root/f['path'])==f['sha256'];f['source_sha256']=f['sha256']
            mapping=receipts.get('source_raw_mappings',{}).get(entry['asset'])
            if mapping:
                reviewed(receipts,'mapping:'+entry['asset'])
                assert set(mapping)=={'raw_frames','trim_head','trim_tail','effective_frames'} and mapping['effective_frames']==f['effective_frames']
                assert mapping['raw_frames']-mapping['trim_head']-mapping['trim_tail']==f['effective_frames']
                f.update(mapping)
            source_facts.append(f)
        # Alternative raw decoder origins require an independent mapping review.
        # A Software-supplied arbitrary override is not admitted by this checker.
        manifest=audit.manifest(raw,pcm,source_facts,names,case['seconds'])
        assert manifest['tool_version']==index['tool_version'] and manifest['build_profile']==index['profile']
        assert len(record['before'])==len(ordered)
        for pos,(entry,f,s) in enumerate(zip(ordered,source_facts,manifest['sources'])):
            before=np.fromfile(inside(root,record['before'][pos]),dtype='<f8').reshape(-1,2)
            decoded=conversion.decoded(source_root,facts[entry['asset']]);original=decoded if f['input_rate']==44100 and not f.get('lossy') else None
            if f['input_rate']==44100:expected_float=decoded
            else:
                desc=dict(profile['resamplers'][str(f['input_rate'])])
                if desc['kind']=='fir':
                    if 'coefficients_file' in desc:
                        path=inside(root,desc['coefficients_file']);assert asset.sha_file(path)==desc['coefficients_sha256'];desc['coefficients']=np.fromfile(path,dtype='<f8')
                    if f['input_rate'] not in qualified_rates:
                        filter_bounds.certify(desc['coefficients'],f['input_rate']);qualified_rates.add(f['input_rate'])
                    expected_float=conversion.fir(decoded,f['input_rate'],desc)
                else:
                    reviewed(receipts,'resampler-math:'+str(f['input_rate']))
                    reviewed(receipts,'src-bounds:'+str(f['input_rate']))
                    ref=receipts['reference_floats'][entry['asset']];path=Path(ref['path']);assert asset.sha_file(path)==ref['sha256']
                    expected_float=np.fromfile(path,dtype='<f8').reshape(-1,2)
            conversion.compare(before,expected_float,bool(f.get('lossy')),source_scale=float(np.max(abs(decoded),initial=0)))
            if f.get('family')=='endpoint':audit.latency(before,decoded,f['input_rate'])
            start=s['start_frame']*4;chunk=pcm[start:start+s['output_frames']*4]
            ceiling=receipts.get('ceiling_proofs',{}).get(case['id'],{}).get(str(pos))
            if ceiling is not None:reviewed(receipts,'ceiling:'+case['id']+':'+str(pos),[model.digest(chunk)])
            audit.audio(before,chunk,s,original=original,mono=f['input_channels']==1,exact=entry['asset'].startswith('dither-'),physical_upper=ceiling,digital_source=not np.any(decoded))
            if f.get('family')=='src-quality':audit.quality(before,f['input_rate'],f['frequency'],f['amplitude'],f['window_output_frames'])
            qualification.check(f,s)
        ceiling=receipts.get('ceiling_proofs',{}).get(case['id'],{}).get('joined')
        if ceiling is not None:reviewed(receipts,'ceiling:'+case['id']+':joined',[model.digest(pcm)])
        audit.joined(pcm,record['joined_dbtp'],physical_upper=ceiling)
        expected_counts={'peak_limited':sum(s['peak_limited'] for s in manifest['sources']),'unmeasurable':sum(s['loudness_status']=='unmeasurable' for s in manifest['sources']),'gapless_unknown':sum(s['gapless_status']=='gapless_unknown' for s in manifest['sources'])}
        assert record['summary']==expected_counts
        reviewed(receipts,'summary:'+case['id'],[asset.sha_file(inside(root,record['stdout_file']))])
        relations.repeated_sources(raw,pcm);outputs[case['id']]=(raw,pcm)
        for number,other in enumerate(record.get('comparisons',[])):
            reviewed(receipts,'comparison:'+case['id']+':'+str(number),[asset.sha_file(inside(root,other['manifest'])),asset.sha_file(inside(root,other['wav'])),asset.sha_file(inside(root,other['raw_trace']))])
            other_output=(inside(root,other['manifest']).read_bytes(),model.pcm_from_wav(inside(root,other['wav']).read_bytes()))
            if other['mode']=='standalone-versus-batch':relations.standalone(other_output,[(raw,pcm)])
            else:
                assert other['mode'] in ('repeat','relocate','different-target')
                relations.pair((raw,pcm),other_output,other['mode'])
        if case['id'].startswith('identity/') and case['id']!='identity/cross-os':assert record.get('comparisons'),'missing actual relation run'
        results.append({'id':case['id'],'gates':'manifest/audio/quality/native predicates checked'})
    for id_ in ('joins/sources','joins/folder-gaps','trim/repeated-mp3','trim/repeated-bmff'):
        c=next(c for c in catalog if c['id']==id_)
        individuals=[outputs['asset/'+e['asset']] for folder in c['folders'] for e in folder]
        relations.standalone(outputs[id_],individuals)
    return {'candidate_sha':index['candidate_sha'],'profile':index['profile'],'tool_version':index['tool_version'],'config_sha256':index['config_sha256'],'platform':index['platform'],'cases':results,'status':'ALL PUBLISHED GATES CHECKED; exact-head Verification disposition still required'},outputs

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('packet');ap.add_argument('--sources',required=True);ap.add_argument('--verification-receipts',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    report,_=check(a.packet,a.sources,json.loads(a.verification_receipts.read_text(encoding='utf-8')));a.out.write_text(json.dumps(report,indent=2)+'\n');print(report['status'])
