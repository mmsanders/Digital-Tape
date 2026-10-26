"""ASCII-safe diagnostic summary. The separate contract.py --input remains the acceptance gate."""
import argparse,copy,json
from pathlib import Path
import contract
def summarize(result,head):
    rows={}
    for c in contract.CASES:
        x=result['cases'][c['id']];before,after=x['before'],x['after'];fails=[]
        if x['event_order']!=c['steps']:fails.append('event_order')
        for o in [before,after]:
            if o['make_enabled'] is not False or o['forbidden_nodes']!=[]:fails.append('make_enabled/forbidden_nodes')
            if 'label_value' in o:
                try:ok='\0' not in o['label_value'] and len(o['label_value'].encode('utf-8'))<=32 and o['utf8_bytes']==len(o['label_value'].encode('utf-8'))
                except UnicodeError:ok=False
                if not ok:fails.append('label UTF8')
        fails += [f'eq {k}: {after.get(k)!r} != {v!r}' for k,v in c['eq'].items() if after.get(k,'<missing>')!=v]
        fails += [f'same {k}: {before.get(k)!r} -> {after.get(k)!r}' for k in c['same'] if before.get(k)!=after.get(k)]
        fails += [f'contains {k}' for k,v in c['contains'].items() if not all(w in after.get(k,'') for w in v)]
        fails += [f'absent {k}' for k,v in c['absent'].items() if any(w in after.get(k,'') for w in v)]
        rows[c['id']]=fails
    try:contract.qualify(result,head);qualified=True;error=None
    except (AssertionError,KeyError,TypeError,ValueError,UnicodeError) as e:qualified=False;error=repr(e)
    return dict(source_head=result['source_head'],passed=sum(not f for f in rows.values()),total=len(rows),qualified=qualified,qualifier_error=error,failures=rows)
def encode(result):return json.dumps(result,ensure_ascii=True,indent=1)+'\n'
def controls():
    r=contract.fixture();s=summarize(r,'a'*40);assert s['qualified'] and s['passed']==32
    bad=copy.deepcopy(r);bad['cases']['E-astral-caret']['after']['label_value']='old 😀'
    bad['cases']['E-astral-caret']['after']['utf8_bytes']=len('old 😀'.encode())
    failed=summarize(bad,'a'*40);assert not failed['qualified'] and failed['passed']==31
    wire=encode(failed);assert json.loads(wire)==failed and wire.encode('ascii').decode('ascii')==wire
    # The same diagnostic values survive a legacy Windows console encoding unchanged.
    assert json.loads(wire.encode('cp1252').decode('cp1252'))==failed
    print('PASS ASCII-safe Unicode diagnostic transport and retained failing-case detection; ZERO Product/browser execution')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--input',type=Path);p.add_argument('--candidate');p.add_argument('--out',type=Path);a=p.parse_args()
    if not a.input:controls()
    else:
        wire=encode(summarize(json.loads(a.input.read_text(encoding='utf-8-sig')),a.candidate))
        if a.out:a.out.write_bytes(wire.encode('ascii'))
        else:print(wire,end='')
