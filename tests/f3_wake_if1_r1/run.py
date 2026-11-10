"""Exercise declared fwhost wake-sim, without a port, device or Product imports."""
import argparse,copy,json,re,subprocess
from pathlib import Path
from cases import cases
FIELDS=['trigger','status','elapsed_us','cycles','cpu_hz','millis','engine_us','warm','mount','position','inject_us','id']

def parse(raw):
 text=raw.decode('ascii');lines=text.splitlines();assert len(lines)==1 and lines[0].startswith('WAKE ')
 parts=lines[0].split(' ');assert len(parts)==25 and parts[1::2]==FIELDS
 d=dict(zip(parts[1::2],parts[2::2]));assert d['trigger'] in ('button','serial') and d['status'] in ('ok','timeout','wrap','clock_changed','mount_failed')
 assert re.fullmatch('[0-9a-f]{32}',d['id']) and d['warm'] in ('0','1')
 for k in ('cpu_hz','millis','position','inject_us'):assert re.fullmatch('0|[1-9][0-9]*',d[k])
 for k in ('elapsed_us','cycles','engine_us'):assert d[k]=='-' or re.fullmatch('0|[1-9][0-9]*',d[k])
 assert re.fullmatch('0|-?[1-9][0-9]*',d['mount'])
 return d

def agrees(raw,wanted):
 try:d=parse(raw);return all(d.get(k)==v for k,v in wanted.items())
 except (AssertionError,UnicodeError):return False

def line(values):
 d=dict(trigger='button',status='ok',elapsed_us='99000',cycles='59400000',cpu_hz='600000000',millis='99',engine_us='99000',warm='1',mount='0',position='44100',inject_us='0',id='a'*32);d.update(values)
 return ('WAKE '+' '.join(k+' '+d[k] for k in FIELDS)+'\n').encode()

def main():
 ap=argparse.ArgumentParser();g=ap.add_mutually_exclusive_group(required=True);g.add_argument('--selftest',action='store_true');g.add_argument('--host',type=Path);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=False);obs=[]
 for c in cases():
  if a.selftest:raw=line(c['expected']);good=agrees(raw,c['expected'])
  else:
   p=a.out/'scenario.json';p.write_text(json.dumps(c['scenario']),encoding='utf-8');q=subprocess.run([str(a.host.resolve()),'wake-sim',str(p.resolve())],capture_output=True);raw=q.stdout;good=q.returncode==0 and agrees(raw,c['expected'])
  obs.append(dict(case=c['name'],expected=c['expected'],observed=raw.decode('ascii',errors='replace'),passed=good))
 controls=[]
 for name,edit in [('floor-instead-of-ceil',dict(elapsed_us='1')),('measure-first-engine-instead-of-audible',dict(elapsed_us='20000')),('short-time-after-wrap-fault',dict(status='ok',elapsed_us='1',cycles='600')),('drop-build-id',dict(id='b'*32))]:
  target={'floor-instead-of-ceil':'ceil-not-floor','measure-first-engine-instead-of-audible':'first-engine-block-is-not-first-nonsilent','short-time-after-wrap-fault':'fault-wrap-cannot-report-short-ok','drop-build-id':'warm-button-99ms'}[name];c=next(c for c in cases() if c['name']==target);d=dict(c['expected']);d.update(edit);assert not agrees(line(d),c['expected']);controls.append(name)
 for bad in [b'WAKE garbage\n',line({})+line({}),line({}).replace(b'elapsed_us 99000',b'elapsed_us 099000'),line({}).replace(b'cycles 59400000',b'cycles True')]:assert not agrees(bad,cases()[0]['expected'])
 controls.append('malformed-grammar-four-controls')
 result=dict(mode='wire-predicate-selftest' if a.selftest else 'actual-fwhost-wake-sim',cases=obs,controls_detected=controls,passed=all(x['passed'] for x in obs),candidate_executed=not a.selftest,physical_run=False,accepted=False)
 (a.out/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8');print(json.dumps({k:v for k,v in result.items() if k!='cases'}));return 0 if result['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
