"""Synthetic causal artifact-binding controls; no Product executable is run."""
import tempfile, zipfile
from pathlib import Path
import external as e

def refuses(fn):
 try: fn()
 except (AssertionError, FileNotFoundError): return
 raise AssertionError('mutation escaped')

with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as d:
 r = Path(d); k = r/'kit.zip'; b = r/'synthetic.bin'; s = r/'ordinary.wav'
 deps = e.ROOT/'tests/wp16_shipping_exhaustion_r1'
 b.write_bytes(b'synthetic shipping'); s.write_bytes(b'synthetic admitted bytes')
 with zipfile.ZipFile(k, 'w') as z: z.writestr('ingest.exe', b.read_bytes())
 original_kit = k.read_bytes()
 pins = (e.sha(k), e.sha(b), e.sha(s))
 check = lambda: e.authenticate(k,b,s,deps,pins)
 assert check()['binary_sha256'] == pins[1]
 for path in (k,b,s):
  old = path.read_bytes(); path.write_bytes(old+b'damaged'); refuses(check); path.write_bytes(old)
 s.unlink(); refuses(check); s.write_bytes(b'synthetic admitted bytes')
 with zipfile.ZipFile(k, 'w') as z: z.writestr('ingest.exe', b'observation substitute')
 refuses(lambda: e.authenticate(k,b,s,deps,(e.sha(k),pins[1],pins[2])))
 k.write_bytes(original_kit)
 bad = r/'deps'; bad.mkdir()
 for n in e.DEPS: (bad/n).write_bytes((deps/n).read_bytes())
 for n in e.DEPS:
  old = (bad/n).read_bytes(); (bad/n).write_bytes(old+b'\n# drift')
  refuses(lambda: e.authenticate(k,b,s,bad,pins)); (bad/n).write_bytes(old)
print('PASS: positive binding and 8 detecting controls; authoring only, no shipping execution')
