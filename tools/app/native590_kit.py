"""Software590: the owned fixture/receipt kit for Michael's human-operated 564 rows (PM588).

Writes files only under a fresh ordinary directory. It launches nothing (no app, child,
collector or browser) and touches no app data. The WAV and labels come from the imported
Verification packages, not from a second generator.

  python -B tools/app/native590_kit.py prepare --root KIT --candidate DIR
  python -B tools/app/native590_kit.py hash --root KIT --out FILE     (before/after sentinels)
"""
import argparse,ctypes,hashlib,importlib.util,json,os,platform,sys
from pathlib import Path

REPO=Path(__file__).resolve().parents[2]
def load(name):
    s=importlib.util.spec_from_file_location(name,REPO/'tests'/name/'contract.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
FLOW=load('windows_native_flow_r1');SCREEN=load('windows_screen_r1')
PINS={'digital-tape.exe':FLOW.APP,'ingest.exe':FLOW.CHILD,'tapectl.exe':'82798af2899e9364b9c9bfaa2021daf6cc51ccd0c6562598d50e0a86944bb7a9'}
FOREIGN=b'FOREIGN sentinel: not app-owned; must survive every Start over and close.\n'
NOTE=b'This is not a song. Drop it to see the app refuse a file.\n'

def sha(b):return hashlib.sha256(b).hexdigest()
def ordinary(p):
    p=Path(os.path.abspath(p))
    if str(p).startswith('\\\\'):raise SystemExit('refused: network/device path')
    for q in [p,*p.parents]:
        if q.exists() and os.lstat(q).st_file_attributes&0x400:raise SystemExit(f'refused: reparse point {q}')
    return p
def tree(root):
    """Every directory and file under root with size and SHA-256, in a fixed order."""
    out={}
    for d,dirs,files in os.walk(root):
        dirs.sort();rel=Path(d).relative_to(root).as_posix()
        out[rel+'/']=None
        for f in sorted(files):b=(Path(d)/f).read_bytes();out[(Path(rel)/f).as_posix()]=dict(bytes=len(b),sha256=sha(b))
    return out
def context():
    v=sys.getwindowsversion()
    return dict(platform=platform.platform(),windows_build=f'{v.major}.{v.minor}.{v.build}',python=sys.version.split()[0],
        effective_admin=bool(ctypes.windll.shell32.IsUserAnAdmin()),user_profile=os.environ.get('USERPROFILE'))

def prepare(root,candidate):
    root=ordinary(root);candidate=ordinary(candidate)
    got={n:sha((candidate/n).read_bytes()) for n in PINS}
    if got!=PINS:raise SystemExit(f'refused: candidate564 bytes differ from the pins: {got}')
    if root.exists():raise SystemExit('refused: --root must not exist (fresh kit only)')
    music=root/'fixtures'/'Music';empty=root/'fixtures'/'Empty'
    for d in [music,empty,root/'foreign-sentinel',root/'receipts'/'raw']:d.mkdir(parents=True)
    wav=FLOW.wav();assert len(wav)==352844 and sha(wav)=='48f1b3c7ce7fe27a90469364f841803087a9d274a4af9a4ec8ee195a2846ac18'
    (music/'two-seconds.wav').write_bytes(wav)
    (root/'fixtures'/'Not a song.txt').write_bytes(NOTE)
    (root/'foreign-sentinel'/'keep').write_bytes(FOREIGN)
    # One attempted value per line, for paste into the label box. NUL cannot be pasted
    # naturally; that subrow is recorded as unsupported, never injected.
    lines=[f"{i+1}\tbefore={x['before']!r}\tattempt={x['attempt']!r}\texpect={x['after']!r}" for i,x in enumerate(SCREEN.LABELS)]
    (root/'labels.txt').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    for i,x in enumerate(SCREEN.LABELS):
        if '\0' not in x['attempt']:(root/'labels'/f'{i+1}.txt').parent.mkdir(exist_ok=True);(root/'labels'/f'{i+1}.txt').write_text(x['attempt'],encoding='utf-8')
    index=dict(app_sha256=FLOW.APP,child_sha256=FLOW.CHILD,scope='actual native controls/live IPC/app-driven child',
        actor='Michael (human, real mouse/keyboard)',provider=None,permission_mode=None,user_task_authorization_ref=None,
        raw_refs=[],genuine_folder_gesture_ref=None,injection=False,fake_child=False,direct_cli_substitute=False,
        session_seconds=None,no_card_make_elevation=True,source_before=None,source_after=None,foreign_before=None,foreign_after=None,
        rows={n:dict(status='UNEXECUTED',raw_refs=[]) for n in FLOW.ROWS},
        note='Pointers only. Statuses stay UNEXECUTED until an original receipt supports them; nothing here is a prefilled pass.')
    (root/'receipts'/'INDEX.json').write_text(json.dumps(index,indent=1)+'\n',encoding='utf-8')
    manifest=dict(kind='Software590 kit, before any session',candidate=str(candidate),candidate_sha256=got,
        fixture_wav=dict(bytes=len(wav),sha256=sha(wav),frames=88200),context=context(),tree=tree(root/'fixtures'),
        foreign=tree(root/'foreign-sentinel'),labels_source='tests/windows_screen_r1 LABELS',fixture_source='tests/windows_native_flow_r1 wav()')
    (root/'MANIFEST.before.json').write_text(json.dumps(manifest,indent=1)+'\n',encoding='utf-8')
    print(json.dumps(dict(root=str(root),manifest_sha256=sha((root/'MANIFEST.before.json').read_bytes()),fixtures=manifest['tree']),indent=1))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','hash']);p.add_argument('--root',required=True)
    p.add_argument('--candidate');p.add_argument('--out');a=p.parse_args()
    if a.action=='prepare':prepare(a.root,a.candidate)
    else:
        root=ordinary(a.root);w=json.dumps(dict(fixtures=tree(root/'fixtures'),foreign=tree(root/'foreign-sentinel')),indent=1)+'\n'
        Path(a.out).write_text(w,encoding='utf-8') if a.out else print(w,end='')
