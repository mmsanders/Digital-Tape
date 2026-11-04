"""V382 public-schema row qualification bindings, not electrical qualification."""
import argparse
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path
import sys

def row():
    return dict(method='rig-r2',bus_mode='spi',busy_line='MISO',sck_hz=4000000,
      payload_complete=True,data_response_accepted=True,busy_entry_us=100.0,
      capture_armed_us=90.0,cut_command_us=140.0,rail_open_us=150.0,
      rail_edges_us=[150.0],busy_end_edges_us=[],capture_end_us=200.0)

def cases():
    out=[]
    def add(name,change=lambda r:None,qualifies=False,reason=None):
        r=row();change(r);out.append((name,r,qualifies,reason))
    add('positive-declared-row',qualifies=True)
    for edge,expected,reason in [(148.999,False,'before'),(149.0,False,'ambiguous'),
                                (150.0,False,'ambiguous'),(151.0,False,'ambiguous'),(151.001,True,None)]:
        add('busy-edge-'+str(edge),lambda r,edge=edge:r.update(busy_end_edges_us=[edge]),expected,reason)
    add('busy-ends-equal-entry',lambda r:r.update(busy_end_edges_us=[100.0]))
    add('capture-armed-late',lambda r:r.update(capture_armed_us=100.001))
    add('capture-at-entry',lambda r:r.update(capture_armed_us=100.0),True)
    add('uncertainty-window-short',lambda r:r.update(capture_end_us=150.999))
    add('uncertainty-window-exact',lambda r:r.update(capture_end_us=151.0),True)
    add('no-opening',lambda r:r.update(rail_open_us=None,rail_edges_us=[]))
    add('opening-before-entry',lambda r:r.update(rail_open_us=99.0,rail_edges_us=[99.0]))
    add('opening-at-entry',lambda r:r.update(rail_open_us=100.0,rail_edges_us=[100.0]))
    add('delayed-opening',lambda r:r.update(cut_command_us=140.0,rail_open_us=640.001,rail_edges_us=[640.001],capture_end_us=700.0))
    add('delay-bound-exact',lambda r:r.update(cut_command_us=140.0,rail_open_us=640.0,rail_edges_us=[640.0],capture_end_us=700.0),True)
    add('opening-before-command',lambda r:r.update(cut_command_us=150.001))
    add('gpio-and-old-sample-do-not-replace-edge',lambda r:(r.pop('rail_open_us'),r.update(busy_sampled_us=120,cut_us=1000000)))
    add('old-fields-diagnostic-only',lambda r:r.update(busy_sampled_us=-100,cut_us=1000000,busy_deassert_us=1),True)
    add('operator-cannot-shrink-U',lambda r:r.update(U_US=0,busy_end_edges_us=[151.0]),reason='ambiguous')
    add('operator-cannot-increase-delay',lambda r:r.update(CUT_DELAY_MAX_US=1e9,rail_open_us=641.0,rail_edges_us=[641.0],capture_end_us=700.0))
    for key in ('payload_complete','data_response_accepted'):
        add(key+'-false',lambda r,key=key:r.update({key:False}))
    add('wrong-busy-line',lambda r:r.update(busy_line='DAT0'))
    for key in ('busy_entry_us','capture_armed_us','cut_command_us','rail_open_us','capture_end_us','rail_edges_us','busy_end_edges_us'):
        add('missing-'+key,lambda r,key=key:r.pop(key))
    for key in ('busy_entry_us','capture_armed_us','cut_command_us','rail_open_us','capture_end_us'):
        for label,bad in [('nan',float('nan')),('inf',float('inf')),('negative',-1),('bool',True),('string','150')]:
            add(key+'-'+label,lambda r,key=key,bad=bad:r.update({key:bad}))
    for key in ('rail_edges_us','busy_end_edges_us'):
        for label,bad in [('non-list','150'),('nan',[float('nan')]),('bool',[True]),('before-window',[89.0]),('after-window',[201.0]),('backwards',[160.0,150.0])]:
            add(key+'-'+label,lambda r,key=key,bad=bad:r.update({key:bad}))
    add('claimed-opening-with-no-edge',lambda r:r.update(rail_edges_us=[]))
    add('claimed-opening-not-recorded',lambda r:r.update(rail_edges_us=[149.0]))
    add('capture-window-before-arm',lambda r:r.update(capture_end_us=80.0))
    return out

def agrees(actual,expected,reason):
    return isinstance(actual,(tuple,list)) and len(actual)>=2 and actual[0] is expected and (
        reason is None or reason.lower() in str(actual[1]).lower())

def controls():
    cs=cases()
    assert all(agrees((expected,reason or ''),expected,reason) for _,_,expected,reason in cs)
    for blanket in (True,False):
        assert any(not agrees((blanket,''),expected,reason) for _,_,expected,reason in cs)
    e=next(c for c in cs if c[0]=='busy-edge-149.0')
    assert not agrees((False,'busy ended before the rail opened'),e[2],e[3])
    for name in ('busy-edge-149.0','busy-edge-151.0','operator-cannot-shrink-U','claimed-opening-with-no-edge'):
        e=next(c for c in cs if c[0]==name)
        assert not agrees((True,''),e[2],e[3])
    return ['always-qualify','never-qualify','lower-equality-misclassified-completed',
            'lower-equality-counted','upper-equality-counted','operator-shrunk-U','unobserved-opening-counted']

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--qualifier',type=Path);ap.add_argument('--selftest',action='store_true');ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    result=dict(scope='declared-model row tests only; no calibrated timing or physical evidence',
                cases=len(cases()),controls_detected=controls(),physical_run=False,method_clearance=False)
    if a.selftest:
        assert not a.qualifier;result.update(mode='harness-selftest-only',product_executed=False)
    else:
        assert a.qualifier and a.qualifier.is_file()
        spec=importlib.util.spec_from_file_location('v382_qualifier',a.qualifier)
        m=importlib.util.module_from_spec(spec);sys.modules[spec.name]=m;spec.loader.exec_module(m)
        observations=[]
        for name,r,expected,reason in cases():
            try:actual=m.qualifies(copy.deepcopy(r));passed=agrees(actual,expected,reason)
            except Exception as exc:actual=[None,repr(exc)];passed=False
            observations.append(dict(case=name,expected=expected,required_reason=reason,observed=actual,passed=passed))
        result.update(mode='candidate-row-qualification',qualifier_sha256=hashlib.sha256(a.qualifier.read_bytes()).hexdigest(),
                      observations=observations,passed=all(o['passed'] for o in observations))
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='observations'}));return 0 if result.get('passed',True) else 1

if __name__=='__main__':raise SystemExit(main())
