#!/usr/bin/env python3
"""Causal checker controls, synthetic fixtures; no Product acceptance."""
import copy,json,tempfile,subprocess
from pathlib import Path
import check
from asset import extract

def reject(reason,call):
    try:call()
    except AssertionError as e:
        assert reason in str(e),(reason,str(e));return
    raise AssertionError('control survived: '+reason)

def encoded(rows):return (''.join(json.dumps(r)+'\n' for r in rows)).encode()
def main():
    m=check.load();old=[{'id':1,'value':8,'events':[{'op':'write','ordinal':0,'lba':2},{'op':'flush','ordinal':1}]}]
    new=copy.deepcopy(old);new[0]['events'].insert(0,{'op':'read','ordinal':0,'lba':9});new[0]['events'][1]['ordinal']=1;new[0]['events'][2]['ordinal']=2
    assert check.transition(encoded(old),encoded(new),1)['changed_records']==1
    bad=copy.deepcopy(new);bad[0]['value']=9
    reject('non-event',lambda:check.transition(encoded(old),encoded(bad),1))
    bad=copy.deepcopy(new);bad[0]['events'][1]['lba']=3
    reject('write/flush',lambda:check.transition(encoded(old),encoded(bad),1))
    bad=copy.deepcopy(new);bad[0]['events'][1:]=reversed(bad[0]['events'][1:])
    reject('write/flush',lambda:check.transition(encoded(old),encoded(bad),1))
    reject('case census',lambda:check.transition(encoded(old),b'',1))
    with tempfile.TemporaryDirectory() as d:
        root=Path(d);raw=root/'observations.jsonl';raw.write_bytes(encoded(new))
        toy={'engine_tree':m['engine_tree'],'suites':{'toy':{'cases':1,'new':{'raw_sha256':check.sha(raw.read_bytes()),'files':{'observations.jsonl':check.sha(raw.read_bytes())}}}}}
        sel={'suite':'toy','comparison_engine':m['engine_tree']};check.regenerate(raw,'toy',sel,toy);check.authenticate('toy',root,'new',toy)
        raw.write_bytes(encoded(new).rstrip(b'\n')+b' \n')
        reject('exact regenerated',lambda:check.regenerate(raw,'toy',sel,toy))
        reject('archive/file',lambda:check.authenticate('toy',root,'new',toy))
        bad=copy.deepcopy(new);bad[0]['events'][0]['lba']=10;raw.write_bytes(encoded(bad))
        reject('exact regenerated',lambda:check.regenerate(raw,'toy',sel,toy))
        reject('selection identity',lambda:check.regenerate(raw,'toy',{'suite':'toy','comparison_engine':'0'*40},toy))
        reject('whole release',lambda:extract(b'corrupt',root,m))
    with tempfile.TemporaryDirectory() as d:
        root=Path(d);(root/'engine').mkdir();(root/'engine/code.c').write_text('literal synthetic source\n');(root/'adapter.py').write_text('literal synthetic adapter\n')
        def git(*args):return subprocess.check_output(['git',*args],cwd=root,text=True,stderr=subprocess.DEVNULL).strip()
        git('init','-q');git('config','user.name','Checker');git('config','user.email','checker@example.invalid');git('add','.');git('commit','-qm','synthetic baseline')
        toy={'epoch':'synthetic','engine_tree':git('rev-parse','HEAD:engine'),'suites':{'toy':{'source_build_profile':{'adapter.py':check.sha((root/'adapter.py').read_bytes())}}}}
        check.select(root,'toy',m=toy)
        (root/'adapter.py').write_text('changed adapter\n');git('add','.');git('commit','-qm','wrong profile')
        reject('adapter/build profile',lambda:check.select(root,'toy',m=toy))
        git('reset','--hard','HEAD~1');(root/'engine/code.c').write_text('changed engine\n');git('add','.');git('commit','-qm','wrong engine')
        reject('unsupported ordinary engine',lambda:check.select(root,'toy',m=toy))
        (root/'engine/code.c').write_text('dirty engine\n')
        reject('committed execution source',lambda:check.select(root,'toy',m=toy))
    rows=[{'mutation':n,'selection_pass':True,'build_pass':True,'failure_kind':'behavior','oracle':'unchanged literal oracle','assertion':'expected PCM mismatch','actual_commit':'1'*40,'actual_engine':'2'*40} for n in m['mutation_patches'] if n!='00-benign-comment']
    report={k:True for k in ('baseline_behavior_pass','baseline_raw_pass','baseline_selection_pass','benign_behavior_pass','benign_raw_pass','benign_selection_pass')};report['mutations']=rows
    check.mutation_census(report,m)
    for key,reason in [('baseline_raw_pass','green unmutated'),('baseline_behavior_pass','green unmutated'),('benign_behavior_pass','benign mutation')]:
        bad=copy.deepcopy(report);bad[key]=False;reject(reason,lambda:check.mutation_census(bad,m))
    for key,value,reason in [('failure_kind','raw','causal behavior'),('failure_kind','provenance','causal behavior'),('build_pass',False,'provenance/build'),('selection_pass',False,'provenance/build'),('actual_engine',m['engine_tree'],'truthful mutant')]:
        bad=copy.deepcopy(report);bad['mutations'][0][key]=value;reject(reason,lambda:check.mutation_census(bad,m))
    bad=copy.deepcopy(report);bad['mutations'].pop();reject('seven mutation',lambda:check.mutation_census(bad,m))
    print('PASS: transition, exact raw/read array, omission, identity and mutation-causality controls (synthetic only)')
if __name__=='__main__':main()
