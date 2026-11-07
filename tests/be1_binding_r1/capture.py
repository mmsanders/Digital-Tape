"""Independent raw-byte fake-port tests for the declared capture helper."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys

def cases():
    digest=b'SHA256 '+b'0'*64+b' FRAMES 0 RESULT 0\r\n'
    # This valid-looking digest is inside PCM, so it is not the stream's terminator.
    payload=digest+b'\0'*((-len(digest))%4)
    stream=b'PCM\r\n'+struct.pack('<I',len(payload)//4)+payload+struct.pack('<I',0)+digest
    return [('digest-byte-fragments',digest,1),('digest-crlf-split',digest,7),
            ('stream-fragments',stream,3),('binary-digest-is-not-terminator',stream,4096)]

def run(helper,out):
    result=[]
    for name,raw,fragment in cases():
        config=out/(name+'.fixture.json');capture=out/(name+'.raw');log=out/(name+'.log.json')
        config.write_text(json.dumps(dict(bytes=base64.b64encode(raw).decode(),fragment=fragment)),encoding='utf-8')
        proc=subprocess.run([sys.executable,'-B',str(Path(__file__).with_name('capture_guard.py')),str(helper.resolve()),str(config.resolve()),str(capture.resolve()),str(log.resolve())],capture_output=True,timeout=10)
        facts=json.loads(log.read_text(encoding='utf-8'))
        passed=proc.returncode==0 and not facts['violations'] and facts['ports']==['V382_FAKE_ONLY'] and not facts['command_writes'] and capture.is_file() and capture.read_bytes()==raw
        result.append(dict(case=name,passed=passed,exit=proc.returncode,expected_sha256=hashlib.sha256(raw).hexdigest(),facts=facts))
    return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--helper',type=Path);ap.add_argument('--out',type=Path,required=True);ap.add_argument('--selftest',action='store_true');a=ap.parse_args()
    out=a.out.resolve();out.mkdir(parents=True,exist_ok=False)
    if a.selftest:
        stub=out/'fake_helper.py'
        source="""import serial,sys
from pathlib import Path
s=serial.Serial('V382_FAKE_ONLY',timeout=0.1)
b=bytearray()
while True:
 p=s.read(4096)
 if not p:break
 b.extend(p)
Path(sys.argv[sys.argv.index('--out')+1]).write_bytes(bytes(b))
"""
        stub.write_text(source,encoding='utf-8');result=run(stub,out)
        assert all(r['passed'] for r in result)
        detected=[]
        for name,replacement in [('drop-byte','bytes(b)[:-1]'),('newline-rewrite',"bytes(b).replace(b'\\r\\n',b'\\n')")]:
            stub.write_text(source.replace('write_bytes(bytes(b))','write_bytes('+replacement+')'),encoding='utf-8')
            trial=out/name;trial.mkdir()
            assert all(not r['passed'] for r in run(stub,trial));detected.append(name)
        report=dict(mode='harness-selftest-only',product_executed=False,cases=result,controls_detected=detected,physical_run=False)
    else:
        assert a.helper and a.helper.is_file()
        report=dict(mode='candidate-fake-port',helper_sha256=hashlib.sha256(a.helper.read_bytes()).hexdigest(),cases=run(a.helper,out),physical_run=False)
    (out/'RESULT.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report));return 0 if all(r['passed'] for r in report['cases']) else 1

if __name__=='__main__':raise SystemExit(main())
