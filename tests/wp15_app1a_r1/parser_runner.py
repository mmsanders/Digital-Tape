"""Run independent parser inputs through an adapter to the actual app parser.

Adapter JSONL stdin: complete cases.py input. stdout: {valid,message} only.
Adapter must call actual Product parser/mapping, never this oracle.
"""
import argparse,json,subprocess
import cases

def compare(rows,got):
    assert len(got)==len(rows)
    for c,r in zip(rows,got):
        assert r['valid']==c['valid'],c['name']
        assert r['message']==c['message'],c['name']

def run(command):
    rows=cases.corpus();p=subprocess.run(command,input=''.join(json.dumps(c)+'\n' for c in rows),text=True,capture_output=True,check=True)
    got=[json.loads(s) for s in p.stdout.splitlines()];compare(rows,got)
    print(json.dumps(dict(parser_cases=len(rows),result='PASS actual supplied adapter; binding provenance still required')))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',nargs=argparse.REMAINDER);a=p.parse_args();assert a.command;run(a.command)
