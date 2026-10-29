"""Causal controls qualify only the independent checks, never Product acceptance."""
import copy, json, tempfile
from pathlib import Path
import static_check, g3, pe_manifest

def rejected(f,*args):
    try: f(*args)
    except (AssertionError,KeyError): return
    raise AssertionError('negative control escaped')

with tempfile.TemporaryDirectory() as t:
    p=Path(t)/'src'; p.mkdir(); f=p/'main.rs'
    f.write_text('fn main() { std::fs::File::open("ordinary.wav"); }')
    assert not static_check.scan(t)['hits']
    for s in ['PhysicalDrive99','/dev/disk99s1','DeviceIoControl(handle)', 'CreateFileW(path)', 'tape_mount(ctx)']:
        f.write_text(s); assert static_check.scan(t)['hits'],s
rows=[]
for c in g3.CASES:
    r=dict(c,bridge_refs=['SYNTHETIC'],raw_refs=['SYNTHETIC'],details_copyable=True,auto_relaunches=0,
           real_tool_outcome=True,exit=2,report_ref='SYNTHETIC',process_ref='SYNTHETIC',
           message_changed_stderr=c['message'],production_action=True,forged_child_report=False)
    rows.append(r)
assert g3.check(rows)==len(g3.CASES)
for index,c in enumerate(g3.CASES):
    r=copy.deepcopy(rows)
    if c['message'] is not None: r[index]['message']='wrong'
    else: r[index]['make_children']=1
    rejected(g3.check,r)
rejected(g3.check,rows[:-1])
for index in (0,1):
    r=copy.deepcopy(rows);r[index].update(details='',details_copyable=False)
    assert g3.check(r)==len(rows)
    r[index]['new_children']=1;rejected(g3.check,r)
    r=copy.deepcopy(rows);r[index].update(details='actual diagnostic',details_copyable=False)
    rejected(g3.check,r)
r=copy.deepcopy(rows);r[-1]['details_copyable']=False;rejected(g3.check,r)
assert pe_manifest.invoker(dict(levels=[],manifests=[]))=='no-elevation-request; default-invoker'
assert pe_manifest.invoker(dict(levels=[dict(level='asInvoker',uiAccess='false')],manifests=[]))=='explicit-asInvoker'
for level in ('requireAdministrator','highestAvailable'):
    rejected(pe_manifest.invoker,dict(levels=[dict(level=level)],manifests=[]))
rejected(pe_manifest.invoker,dict(levels=[dict(level='asInvoker',uiAccess='true')],manifests=[]))
print(json.dumps(dict(method_controls='PASS',static_mutants=5,bridge_message_or_launch_mutants=len(rows),synthetic=True)))
