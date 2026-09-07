import copy
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib
from cases import cases, authenticate, CF, SEED, idx, sb
from fixture_audit import audit
from ownership import free_next, ordinary_allocation, ordinary_write
from run import check
ROOT=Path(__file__).resolve().parent

# This fabricates observations to test the ASSERTION CHECKER. It does not call or
# simulate an engine. Its green result is never reported as engine evidence.
def synthetic(c):
    exp=c.expected();repair=c.repair is not None and exp.get('writable') and c.allowed==(0,)
    ev=[] if c.phase0 else [dict(op='read',lba=lba,count=count,rc=0) for lba,count in [(0,1),(c.blocks-1,1),(8,512)]]
    supers=[s.hex() for s in c.supers]
    if repair:
        ev.extend([dict(op='write',lba=0 if c.repair==0 else c.blocks-1,count=1,rc=int(bool(c.fail_write))),
                   dict(op='write_bytes',hex=c.supers[c.selected].hex())])
        if not c.fail_write:
            supers[c.repair]=c.supers[c.selected].hex()
            ev.append(dict(op='flush',lba=0,count=0,rc=int(bool(c.fail_flush))))
    return dict(init=0,result=c.allowed[0],info_result=0,tell_result=0,position=min(c.resume,exp.get('total_frames',0)),
                reads=sum(e['op']=='read' for e in ev),writes=sum(e['op']=='write' for e in ev),
                flushes=sum(e['op']=='flush' for e in ev),oob=0,chunk_reads=0,info=exp,events=ev,superblocks=supers)

class PackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.cc=cases();cls.byid={c.id:c for c in cls.cc}
    def test_authenticated_inputs(self):authenticate(ROOT/'spec')
    def test_crc_and_literal_byte_layout(self):
        self.assertEqual(zlib.crc32(b'123456789'),0xCBF43926)
        image=idx(1,[(0x01020304,7,9)],sequence=0x11223344)
        self.assertEqual(image[:20].hex(),'5441504549445801443322110100000001000000')
        self.assertEqual(image[512:524].hex(),'040302010700000009000000')
        self.assertEqual(image[64:512],bytes(448))
        self.assertEqual(sb()[:8],b'TAPEFS\0\x01')
        self.assertEqual(struct.unpack_from('<I',sb(),508)[0],zlib.crc32(sb()[:508]))
    def test_fixture_verdicts_independent_decoder(self):
        for c in self.cc:
            with self.subTest(c.id):
                result,selected,aa,bb=audit(c)
                self.assertIn(result,c.allowed)
                if result==0:
                    # Byte-identical superblocks permit either chosen copy.
                    self.assertEqual(c.supers[selected],c.supers[c.selected])
                    self.assertEqual(aa,c.live_a);self.assertEqual(bb,c.live_b)
    def test_envelope_and_determinism(self):
        again=cases()
        self.assertEqual([c.encode() for c in self.cc],[c.encode() for c in again])
        for c in self.cc:
            self.assertEqual(len(c.encode()),32+1024+4*65536)
            self.assertEqual(c.encode()[:4],b'VM08')
        self.assertEqual(SEED,0xD8A607)
        manifest=''.join(hashlib.sha256(c.encode()).hexdigest()+'  '+c.id+'.bin\n' for c in self.cc)
        self.assertEqual(manifest,(ROOT/'fixtures.sha256').read_text())
    def test_checker_synthetic_transcripts(self):
        for c in self.cc:
            with self.subTest(c.id):self.assertEqual(check(c,synthetic(c)),[])
    def test_checker_rejects_mutations(self):
        base=self.byid['M-base-A'];repair=self.byid['M-repair-0-stale-rw'];phase=self.byid['M-phase0-0']
        mutations=[]
        def mutation(c,fn):
            o=synthetic(c);fn(o);mutations.append((c,o))
        mutation(base,lambda o:o.update(result=8))
        mutation(base,lambda o:o['info'].update(free_chunks=999))
        mutation(base,lambda o:o['info'].update(side_b_valid=0))
        mutation(base,lambda o:o.update(position=1))
        mutation(base,lambda o:o.update(chunk_reads=1))
        mutation(base,lambda o:o['events'].append(dict(op='read',lba=2048,count=1,rc=0)))
        mutation(base,lambda o:o['events'].append(dict(op='write',lba=8,count=1,rc=0)))
        mutation(base,lambda o:o.update(oob=1))
        mutation(repair,lambda o:o['events'][-2].update(hex='00'*512))
        mutation(repair,lambda o:o['events'][-3].update(lba=0))
        mutation(repair,lambda o:o['info'].update(needs_repair=1))
        mutation(repair,lambda o:o['events'].pop())
        mutation(phase,lambda o:o['events'].append(dict(op='flush',lba=0,count=0,rc=0)))
        mutation(base,lambda o:o['superblocks'].__setitem__(0,'00'*512))
        for c,o in mutations:
            with self.subTest(c.id):self.assertTrue(check(c,o))
    def test_ownership_boundaries(self):
        self.assertEqual(free_next(3,[(0,0,4)]),3) # lawful reference owned by A
        self.assertEqual(free_next(3,[(4,CF-1,2)]),6)
        self.assertEqual(free_next(3,[]),3)
        self.assertEqual(free_next(3,[(8,0,1)]),9) # holes below 9 are expected
        self.assertTrue(ordinary_allocation(3,5,8,5,3))
        for start,count in [(2,1),(4,1),(6,1),(5,4),(5,0),(5,0xffffffff)]:
            self.assertFalse(ordinary_allocation(3,5,8,start,count))
        self.assertTrue(ordinary_write(3,8,2048+3*1024,1))
        self.assertFalse(ordinary_write(3,8,2048+3*1024-1,1))
        self.assertFalse(ordinary_write(3,8,2048+8*1024-1,2))
    def test_missing_engine_is_error(self):
        r=subprocess.run([sys.executable,str(ROOT/'run.py')],capture_output=True,text=True)
        self.assertEqual(r.returncode,2);self.assertIn('--adapter is required',r.stderr)
    def test_probe_callback_instrumentation(self):
        r=subprocess.run([str(ROOT/'build/probe_selftest')],capture_output=True,text=True)
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertEqual(json.loads(r.stdout)['probe_selftest'],'PASS')
    def test_deliberately_wrong_engine_is_red(self):
        with tempfile.TemporaryDirectory() as tmp:
            log=Path(tmp)/'negative.jsonl'
            r=subprocess.run([sys.executable,str(ROOT/'run.py'),'--adapter',str(ROOT/'build/rejecting_probe'),
                              '--case','M-base-A','--log',str(log)],capture_output=True,text=True)
            self.assertEqual(r.returncode,1,r.stdout+r.stderr)
            records=[json.loads(line) for line in log.read_text().splitlines()]
            self.assertEqual(records[1]['status'],'FAIL')
            self.assertIn('result 19 not in (0,)',records[1]['errors'])
if __name__=='__main__':unittest.main()
