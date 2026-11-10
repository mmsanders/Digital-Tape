"""Prove the offline driver rejects an inert exit0 reporter; no Product code."""
import argparse,json
from pathlib import Path
from checker import run
STUB="""import sys,json
from pathlib import Path
b=Path(sys.argv[sys.argv.index('--offline')+1]);out=Path(sys.argv[sys.argv.index('--out')+1]);m=json.loads((b/'manifest.json').read_text());physical=m['session']['kind']=='physical' and any(x['provenance']=='actual' for x in m['observations'])
with out.open('x') as f:json.dump(dict(accepted=False,physical_run=physical),f)
"""
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();a.out.mkdir(parents=True,exist_ok=False);stub=a.out/'blanket_consistent.py';stub.write_text(STUB,encoding='utf-8');obs=run(stub,a.out)
 for name in ('control-149999','met-target-human-declines','decoded-image-marker-missing'):assert next(c for c in obs if c['case']==name)['passed'] is False
 result=dict(mode='checker-driver-negative-control',control='blanket-consistent-exit0',detected=True,failed_cases=[c['case'] for c in obs if not c['passed']],candidate_executed=False,physical_run=False,accepted=False)
 (a.out/'RESULT.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(dict(detected=True,failed_cases=len(result['failed_cases']))))
if __name__=='__main__':main()
