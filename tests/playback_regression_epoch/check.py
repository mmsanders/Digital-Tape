#!/usr/bin/env python3
"""ADR-172 raw epoch authentication; never substitutes for behavior oracles."""
import argparse, gzip, hashlib, json, os, re, subprocess, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def require(ok, reason):
    if not ok:
        raise AssertionError(reason)

def sha(data):
    return hashlib.sha256(data).hexdigest()

def load():
    m = json.loads((ROOT / 'DECLARATION.json').read_text())
    require(m['epoch'] == 'READOPT-D10-1', 'issued epoch')
    require(m['engine_tree'] == 'd96b4245e04d74078f8938744b1394c3018516f7', 'issued engine')
    require(sha((ROOT/'PLAYBACK-REGRESSION-BINDING.md').read_bytes()) == m['authority']['sha256'], 'authority bytes')
    require(len(m['suites']) == 6 and sum(s['cases'] for s in m['suites'].values()) == 10162, 'issued suite census')
    return m

def raw(path):
    b = Path(path).read_bytes()
    return gzip.decompress(b) if str(path).endswith('.gz') else b

def records(data, count):
    rows = [json.loads(line) for line in data.splitlines()]
    require(len(rows) == count, 'case census')
    return rows

def authenticate(suite, directory, which, m=None):
    m = m or load(); pin = m['suites'][suite][which]; root = Path(directory)
    require(which in ('old','new'), 'bundle role')
    for name, expected in pin['files'].items():
        require(sha((root/name).read_bytes()) == expected, which+' archive/file identity '+name)
    path = root / ('observations.jsonl.gz' if 'observations.jsonl.gz' in pin['files'] else 'observations.jsonl')
    b = raw(path)
    require(sha(b) == pin['raw_sha256'], which+' raw identity')
    records(b, m['suites'][suite]['cases'])
    return b

def without_events(x):
    if isinstance(x, dict):
        return {k: without_events(v) for k,v in x.items() if k != 'events'}
    if isinstance(x, list):
        return [without_events(v) for v in x]
    return x

def event_arrays(x):
    if isinstance(x, dict):
        result = []
        for k,v in x.items():
            if k == 'events':
                require(isinstance(v,list), 'event array schema'); result.append(v)
            else:
                result.extend(event_arrays(v))
        return result
    if isinstance(x,list):
        return [e for v in x for e in event_arrays(v)]
    return []

def transition(old, new, count):
    a,b = records(old,count),records(new,count); changed = 0
    for x,y in zip(a,b):
        require(without_events(x) == without_events(y), 'non-event transition')
        ex,ey = event_arrays(x),event_arrays(y)
        require(len(ex) == len(ey), 'event array topology')
        for left,right in zip(ex,ey):
            def ordered(events):
                require(all(isinstance(e,dict) and e.get('op') in ('read','write','flush') for e in events), 'event operation schema')
                return [{k:v for k,v in e.items() if k != 'ordinal'} for e in events if e['op'] != 'read']
            require(ordered(left) == ordered(right), 'ordered write/flush transition')
        changed += x != y
    return {'cases':count, 'changed_records':changed}

def git(root, *args, env=None):
    return subprocess.check_output(['git',*args],cwd=root,env=env,text=True).strip()

def select(root, suite, mutation=None, m=None):
    m=m or load(); root=Path(root).resolve(); pin=m['suites'][suite]
    require(not git(root,'status','--porcelain','--untracked-files=no'), 'committed execution source')
    for path,expected in pin['source_build_profile'].items():
        require(sha((root/path).read_bytes()) == expected, 'adapter/build profile '+path)
    actual = git(root,'rev-parse','HEAD:engine')
    if mutation is None:
        require(actual == m['engine_tree'], 'unsupported ordinary engine')
    else:
        require(mutation in m['mutation_patches'], 'registered deliberate mutation')
        patch = m['mutation_patches'][mutation]
        require(sha((root/patch['path']).read_bytes()) == patch['sha256'], 'mutation patch identity')
        require(git(root,'rev-parse',m['audited_execution_commit']+':engine') == m['engine_tree'], 'unmutated comparison engine')
        with tempfile.TemporaryDirectory() as d:
            env=dict(os.environ, GIT_INDEX_FILE=str(Path(d)/'index'))
            git(root,'read-tree',m['audited_execution_commit'],env=env)
            subprocess.run(['git','apply','--cached',str(root/patch['path'])],cwd=root,env=env,check=True,capture_output=True)
            tree=git(root,'write-tree',env=env)
            expected=git(root,'ls-tree',tree,'engine').split()[2]
        require(actual == expected, 'actual mutated engine does not equal registered patch')
    return {'epoch':m['epoch'],'suite':suite,'mode':'deliberate-mutation' if mutation else 'ordinary',
            'comparison_engine':m['engine_tree'],'actual_engine':actual,'mutation':mutation,
            'actual_commit':git(root,'rev-parse','HEAD'),'actual_root_tree':git(root,'rev-parse','HEAD^{tree}')}

def regenerate(fresh, suite, selection, m=None):
    m=m or load(); pin=m['suites'][suite]
    require(selection['suite']==suite and selection['comparison_engine']==m['engine_tree'], 'selection identity')
    data=raw(fresh); records(data,pin['cases'])
    require(sha(data)==pin['new']['raw_sha256'],'exact regenerated raw stream')
    return {'raw_sha256':sha(data),'cases':pin['cases']}

def mutation_census(report, m=None):
    m=m or load()
    require(report['baseline_behavior_pass'] and report['baseline_raw_pass'] and report['baseline_selection_pass'], 'green unmutated baseline')
    require(report['benign_behavior_pass'] and report['benign_raw_pass'] and report['benign_selection_pass'], 'benign mutation must survive')
    rows=report['mutations']; names=set(m['mutation_patches'])-{'00-benign-comment'}
    require(len(rows)==7 and {r['mutation'] for r in rows}==names, 'seven mutation census')
    for r in rows:
        require(r['selection_pass'] and r['build_pass'], 'mutation provenance/build is not a behavior catch')
        require(r['failure_kind']=='behavior' and bool(r['oracle']) and bool(r['assertion']), 'causal behavior catch required')
        require(bool(re.fullmatch('[0-9a-f]{40}',r['actual_commit'])) and bool(re.fullmatch('[0-9a-f]{40}',r['actual_engine'])) and r['actual_engine']!=m['engine_tree'], 'truthful mutant identities')
    return {'mutations':7,'baseline':'green','benign':'survived','note':'actual logs and unchanged oracle execution require independent final audit'}

def main():
    p=argparse.ArgumentParser(description=__doc__); sub=p.add_subparsers(dest='command',required=True)
    a=sub.add_parser('transition');a.add_argument('--root',required=True)
    a=sub.add_parser('authenticate');a.add_argument('--suite',required=True);a.add_argument('--directory',required=True);a.add_argument('--which',choices=('old','new'),required=True)
    a=sub.add_parser('regenerate');a.add_argument('--product',required=True);a.add_argument('--suite',required=True);a.add_argument('--fresh',required=True);a.add_argument('--mutation')
    a=sub.add_parser('mutation-census');a.add_argument('--report',required=True)
    args=p.parse_args();m=load()
    if args.command=='transition':
        out={s:transition(authenticate(s,Path(args.root)/s/'old','old',m),authenticate(s,Path(args.root)/s/'new','new',m),pin['cases']) for s,pin in m['suites'].items()}
    elif args.command=='authenticate':
        out={'raw_sha256':sha(authenticate(args.suite,args.directory,args.which,m))}
    elif args.command=='regenerate':
        sel=select(args.product,args.suite,args.mutation,m);out={'selection':sel,'regeneration':regenerate(args.fresh,args.suite,sel,m)}
    else:out=mutation_census(json.loads(Path(args.report).read_text()),m)
    print(json.dumps(out,indent=2))
if __name__=='__main__':main()
