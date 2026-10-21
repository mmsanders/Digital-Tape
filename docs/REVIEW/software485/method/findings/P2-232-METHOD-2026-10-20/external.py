"""Authenticate the approved external shipping artifact; delegate unchanged judge.

No builds, downloads, Product imports or execution in --authenticate-only mode.
"""
import argparse, hashlib, importlib.util, json, platform, sys, zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KIT = 'ffb0f78ac3980fa1bb130f0aff22d53ebb100ed3323a8e50ba62a6ee1819c865'
BINARY = 'd923613badda95baeb387d5415d5212a5dedb7c5c7144b21874479babd178f5b'
SOURCE = 'd36663d1e4f05abaac699a6c14e0fa86724db9b4decdb8c96abe0c9d1f645821'
DEPS = {
 'runner.py': 'f8bb18aaf35ed13ff4acb74591d74f83874c8267f4e4a133db795db2606161b0',
 'windows_job.py': '76ca60dd088bbf27c9b5a035d4572cdb24c37485bc96068b08e0ef84605b16ad',
 'selftest.py': '050a5d812a2b253483870b28b606fe310c8d5d569477651d58508305075ada42',
}

def sha(p):
 h = hashlib.sha256()
 with Path(p).open('rb') as f:
  while b := f.read(1024 * 1024): h.update(b)
 return h.hexdigest()

def authenticate(kit, binary, source, dependencies, pins=(KIT, BINARY, SOURCE)):
 # Parameterized pins serve causal synthetic controls only; CLI cannot override.
 k, b, s = pins
 assert sha(kit) == k, 'kit identity'
 assert sha(binary) == b, 'external executable identity'
 assert sha(source) == s, 'admitted input identity'
 with zipfile.ZipFile(kit) as z:
  assert z.namelist().count('ingest.exe') == 1, 'unique shipping member'
  assert hashlib.sha256(z.read('ingest.exe')).hexdigest() == b, 'shipping member identity'
 for name, expected in DEPS.items():
  assert sha(dependencies / name) == expected, 'judge dependency identity: ' + name
 return dict(kit_sha256=k, binary_sha256=b, source_sha256=s, kit_member='ingest.exe', dependencies=DEPS)

def main():
 p = argparse.ArgumentParser(description=__doc__)
 for n in ('kit', 'binary', 'source', 'out'): p.add_argument('--' + n, type=Path, required=True)
 p.add_argument('--authenticate-only', action='store_true'); a = p.parse_args()
 deps = ROOT / 'tests/wp16_shipping_exhaustion_r1'
 identity = authenticate(a.kit, a.binary, a.source, deps)
 assert not a.out.exists(), 'fresh output required'
 if a.authenticate_only:
  print(json.dumps(dict(identity=identity, executed=False), indent=2)); return
 assert sys.platform == 'win32', 'issued external Windows Job method only'
 import winreg
 with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r'SOFTWARE\Microsoft\Windows NT\CurrentVersion') as key:
  os_facts = {n: winreg.QueryValueEx(key, n)[0] for n in ('ProductName', 'EditionID', 'CurrentBuildNumber', 'UBR', 'InstallationType')}
 host = dict(platform=platform.platform(), machine=platform.machine(), python=sys.version, windows=os_facts)
 sys.path.insert(0, str(deps))
 spec = importlib.util.spec_from_file_location('runner232', deps / 'runner.py')
 runner = importlib.util.module_from_spec(spec); spec.loader.exec_module(runner)
 assert runner.BOUNDS == [3, 4, 6, 8, 12, 64, None]
 assert runner.SOURCE == SOURCE
 try:
  runner.run(a.binary.resolve(), BINARY, a.source.resolve(), a.out.resolve(), 'candidate')
 finally:
  # Retain partial/failed observations as well. Exceptions remain failures.
  if a.out.exists():
   assert authenticate(a.kit, a.binary, a.source, deps) == identity, 'post-run identity'
   (a.out / 'BINDING.json').write_text(json.dumps(dict(identity=identity, host=host, adapter_sha256=sha(__file__), scope='actual executable and recorded host/input/seven caps only'), indent=2) + '\n')
   files = {str(f.relative_to(a.out).as_posix()): dict(bytes=f.stat().st_size, sha256=sha(f)) for f in sorted(a.out.rglob('*')) if f.is_file() and f.name != 'FILES.json'}
   (a.out / 'FILES.json').write_text(json.dumps(files, indent=2) + '\n')

if __name__ == '__main__': main()
