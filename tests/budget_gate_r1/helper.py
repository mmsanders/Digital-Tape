"""Harmless fixture child only; no Product/native APIs. All paths supplied as fresh owned files."""
import argparse,hashlib,json,os,sys,time
from pathlib import Path
def main():
 p=argparse.ArgumentParser();p.add_argument('--mode',required=True,choices=['ok','nonzero','timeout','incomplete','after-raw-failure']);p.add_argument('--spy',type=Path,required=True);p.add_argument('--nonce',required=True);a=p.parse_args()
 with a.spy.open('ab') as f:f.write((json.dumps(dict(pid=os.getpid(),nonce=a.nonce))+'\n').encode());f.flush()
 sys.stdout.buffer.write((json.dumps(dict(pid=os.getpid(),parent=os.getppid(),nonce=a.nonce))+'\n').encode()+b'\x00\xffretained\n');sys.stdout.buffer.flush();sys.stderr.buffer.write(b'\x80diagnostic\n');sys.stderr.buffer.flush()
 if a.mode=='timeout':time.sleep(10)
 return 7 if a.mode in ('nonzero','after-raw-failure') else 0
if __name__=='__main__':sys.exit(main())
