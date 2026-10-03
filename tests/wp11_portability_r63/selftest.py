#!/usr/bin/env python3
"""Synthetic hook + arithmetic controls. This is not candidate evidence."""
import json
import pathlib
import subprocess
import tempfile
import argparse
ROOT=pathlib.Path(__file__).resolve().parent
HOOK='int16_t tape_test_interp(int16_t a,int16_t b,uint32_t f)'
GOOD='int64_t d=((int64_t)b-(int64_t)a)*f; uint64_t m=d<0?(uint64_t)(-d):(uint64_t)d; int64_t q=d<0?-(int64_t)((m+UINT64_C(4294967295))/UINT64_C(4294967296)):(int64_t)(m/UINT64_C(4294967296)); return (int16_t)((int64_t)a+q);'
CONTROLS={
 'negative_truncates':'int64_t d=((int64_t)b-(int64_t)a)*f; return (int16_t)(a+d/INT64_C(4294967296));',
 'round_nearest':'int64_t d=((int64_t)b-(int64_t)a)*f; return (int16_t)(a+(d+INT64_C(2147483648))/INT64_C(4294967296));',
 'late_narrow_subtraction':'int32_t d=(int32_t)b-(int32_t)a; d=((d+32768)&65535)-32768; int64_t p=(int64_t)d*f; return (int16_t)(a+p/INT64_C(4294967296));',
 'fraction_endpoint':'return f==UINT32_MAX?b:a;',
 'swapped_operands':GOOD.replace('((int64_t)b-(int64_t)a)','((int64_t)a-(int64_t)b)')}
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--compiler',action='append'); args=ap.parse_args()
 results={}
 with tempfile.TemporaryDirectory() as d:
  p=pathlib.Path(d); (p/'tape_test_hooks.h').write_text('#include <stdint.h>\n'+HOOK+';\n')
  for cc in (args.compiler or ('gcc','clang')):
   for name,body in {'synthetic_conforming':GOOD,**CONTROLS}.items():
    (p/'hook.c').write_text('#include <stdint.h>\n'+HOOK+'{'+body+'}\n')
    subprocess.run([cc,'-std=c99','-O2','-Wall','-Wextra','-Werror','-I',str(p),str(ROOT/'differential.c'),str(p/'hook.c'),'-o',str(p/'test')],check=True)
    r=subprocess.run([str(p/'test')],capture_output=True,text=True)
    assert (r.returncode==0)==(name=='synthetic_conforming'),(cc,name,r.stdout,r.stderr)
    results[cc+'/'+name]={'returncode':r.returncode,'output':(r.stdout+r.stderr).strip()}
 print(json.dumps(results,indent=2,sort_keys=True))
if __name__=='__main__':main()
