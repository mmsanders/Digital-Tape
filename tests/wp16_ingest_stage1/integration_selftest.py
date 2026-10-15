"""File-packet end-to-end reference selfcheck, never a Product/native run.

The unit catalog is explicitly reduced in-process only. Published review has no
skip/catalog override and always requires the full frozen1763-source census.
"""
import argparse,json,tempfile
from pathlib import Path
import asset,conversion,model,numerics,review
from selftest import metadata

def run(sources):
    sources=Path(sources);facts=json.loads((sources/'SOURCES.json').read_text(encoding='utf-8'))
    full=review.cases.expand(facts)
    ids=['asset/ordinary.wav','asset/short.wav','asset/silence.wav','asset/one-frame-quant-zero.wav','asset/mp3-44100-2-vbr.mp3','asset/aac-44100-2.m4a','joins/sources','joins/folder-gaps','trim/repeated-mp3','trim/repeated-bmff']
    catalog=[c for c in full if c['id'] in ids];assert len(catalog)==len(ids)
    with tempfile.TemporaryDirectory() as td:
        root=Path(td);index={'candidate_sha':'f'*40,'binary_sha256':'b'*64,'tool_version':'independent-reference','profile':'synthetic-ref','platform':'linux','architecture':'x64','config_sha256':'c'*64,'cases':{},'profile_file':'PROFILE.json'}
        (root/'PROFILE.json').write_bytes(model.canonical({'resamplers':{}}))
        receipt={k:index[k] for k in ('candidate_sha','binary_sha256','profile','platform','config_sha256')};receipt['checks']={}
        def approve(key,hashes=()):receipt['checks'][key]={'decision':'PASS','reviewer':'Verification','notes':'SYNTHETIC FILE-PACKET SELFTEST ONLY; not native/Product evidence','artifact_sha256':list(hashes)}
        approve('profile',[asset.sha_file(root/'PROFILE.json')])
        for key in ('decoder-mapping','libraries-config','manifest-field-truth','filesystem','observer-controls','instrumented-shipping-equivalence','meter-math'):approve(key)
        cache={}
        for c in catalog:
            d=root/c['id'];d.mkdir(parents=True)
            sources_meta=[];before_files=[];payload=bytearray();gaps=[]
            for ordinal,folder in enumerate(c['folders']):
                if ordinal:gaps.append({'start_frame':len(payload)//4,'frames':model.GAP});payload.extend(bytes(model.GAP*4))
                for entry in sorted(folder,key=lambda x:model.name_key(x['name'])):
                    name=entry['asset'];f=facts[name]
                    if name not in cache:
                        x=conversion.decoded(sources,f);pcm,r=numerics.reference_source(x,44100,'ref_fir_a',mono=f['input_channels']==1)
                        cache[name]=(x,pcm,r)
                    x,pcm,r=cache[name];before=d/('before-'+str(len(sources_meta))+'.f64');x.astype('<f8').tofile(before);before_files.append(str(before.relative_to(root)))
                    s={k:f[k] for k in ('container','codec','codec_profile','input_rate','input_channels','raw_frames','trim_head','trim_tail','trim_evidence','effective_frames')}
                    s.update(logical_path=str(ordinal)+'/'+entry['name'],source_sha256=f['sha256'],output_frames=len(pcm)//4,start_frame=len(payload)//4,gapless_status='gapless_known' if not f.get('lossy') or f['trim_evidence']!='none' else 'gapless_unknown',**metadata(x,pcm,r['gain']))
                    sources_meta.append(s);payload.extend(pcm)
            pcm=bytes(payload);m={'schema':1,'contract':'INGEST-1','tool_version':index['tool_version'],'build_profile':index['profile'],'libraries':{'reference':{'version':'1','config_sha256':'c'*64}},'resampler_profile':'ref_fir_a','meter_profile':'independent16x','dither_profile':'INGEST-1','target_seconds':c['seconds'],'capacity_frames':c['seconds']*44100,'total_frames':len(pcm)//4,'wav_sha256':model.digest(model.wav(pcm)),'folders':[{'ordinal':i,'source_count':len(folder)} for i,folder in enumerate(c['folders'])],'sources':sources_meta,'gaps':gaps}
            (d/'audio.wav').write_bytes(model.wav(pcm));(d/'manifest.json').write_bytes(model.canonical(m))
            summary={'peak_limited':sum(s['peak_limited'] for s in sources_meta),'unmeasurable':sum(s['loudness_status']=='unmeasurable' for s in sources_meta),'gapless_unknown':sum(s['gapless_status']=='gapless_unknown' for s in sources_meta)}
            (d/'stdout.txt').write_text(json.dumps(summary)+'\n');(d/'stderr.txt').write_text('');(d/'trace.txt').write_text('SYNTHETIC unit operation ledger, not native evidence\n')
            ops=['preflight_complete','sources_revalidated','stage_create','output_open','audio_flush_close','manifest_flush_close','publish_dir_noreplace']
            native={'scenario':'success','exit':0,'complete':True,'raw_trace_sha256':asset.sha_file(d/'trace.txt'),'observer_selftest':True,'raw_review':'UNREVIEWED','events':[{'seq':i,'op':op,'exclusive':True,'adjacent':True} for i,op in enumerate(ops)],'dest_after':['audio.wav','manifest.json'],'owned_stage_after':False}
            (d/'native.json').write_bytes(model.canonical(native))
            import numpy as np
            joined=numerics.peak(np.frombuffer(pcm,dtype='<i2').reshape(-1,2)/32768)
            record={'exit':0,'argv':['SYNTHETIC-reference','--length',str(c['seconds'])],'config_sha256':index['config_sha256'],'before':before_files,'summary':summary,'joined_dbtp':model.fixed(joined)}
            for key,name in [('stdout_file','stdout.txt'),('stderr_file','stderr.txt'),('raw_trace','trace.txt'),('native_record','native.json'),('wav','audio.wav'),('manifest','manifest.json')]:record[key]=str((d/name).relative_to(root))
            (d/'record.json').write_bytes(model.canonical(record));index['cases'][c['id']]=str((d/'record.json').relative_to(root))
            approve('native:'+c['id'],[asset.sha_file(d/'record.json'),asset.sha_file(d/'native.json'),asset.sha_file(d/'trace.txt')]);approve('summary:'+c['id'],[asset.sha_file(d/'stdout.txt')])
        (root/'INDEX.json').write_bytes(model.canonical(index))
        original=review.cases.expand
        try:
            review.cases.expand=lambda ignored:catalog
            report,outputs=review.check(root,sources,receipt);assert len(report['cases'])==len(catalog)
            # Full observed file set green, then causal completeness and actual
            # output faults without altering provenance/receipt/exit semantics.
            missing=dict(index,cases=dict(index['cases']));missing['cases'].pop(ids[0]);(root/'INDEX.json').write_bytes(model.canonical(missing))
            try:review.check(root,sources,receipt)
            except AssertionError as e:assert 'missing/extra cases' in str(e)
            else:raise AssertionError('missing case escaped')
            (root/'INDEX.json').write_bytes(model.canonical(index))
            # Source/batch relation checks use actual observed PCM slices, not
            # universally shared reference hashes.
            assert outputs['asset/ordinary.wav'][1]
        finally:review.cases.expand=original
    return {'result':'PASS','reference_cases':len(catalog),'negative_controls':['missing-case'],'scope':'file packet integration only; zero Product/native acceptance'}

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--sources',required=True);p.add_argument('--out',type=Path);a=p.parse_args();result=run(a.sources)
    if a.out:a.out.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result))
