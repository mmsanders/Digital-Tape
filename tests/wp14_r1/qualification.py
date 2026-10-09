#!/usr/bin/env python3
"""Completeness gate for Stage2 evidence. Never authenticates CI by assertion."""
import argparse
import json
from pathlib import Path
from catalog import image_cases,IMAGE_CONTROLS
from native import requests,audit_response,capture_identity

def census(completed,expected):
    assert len(completed)==len(set(completed)), 'duplicate case'
    assert set(expected)<=set(completed), 'case omitted'
    extras=set(completed)-set(expected)
    assert extras and all(x.startswith('replay-') for x in extras)
    assert {'replay-before-first-write','replay-after-final-flush'}<=extras
    return extras

def audit(images,natives,head):
    assert set(images)==set(natives)=={'linux','macos','windows'}
    summaries={}
    for platform in images:
        image=images[platform]; native=natives[platform]
        assert image['kind']=='candidate-image-cases' and image['platform']==platform
        assert image['head_sha']==head and image['cases']==image_cases()
        assert image['controls_killed']==IMAGE_CONTROLS and image['full_c60']
        assert native['kind']=='native-candidate-cases' and native['platform']==platform
        assert native['head_sha']==head and native['os_build']
        rows=native['results']; byname={r['case']:r for r in rows}
        expected=requests(platform,Path('owned-backing.img'))
        extras=census([r['case'] for r in rows],[r['case'] for r in expected])
        for planned in expected:
            actual=byname[planned['case']]['request']
            for key,value in planned.items():
                if key not in ('backing','target_bytes','facts'):
                    assert actual[key]==value, 'request expectation changed: '+planned['case']+'/'+key
        for row in rows:
            request,response=row['request'],row['response']
            assert request['case']==row['case'] and response['head_sha']==head
            capture_identity(request,response) # not catchable as a killed mutant
            if request.get('expect_oracle_reject'):
                assert row['verdict']=='control-killed'
                # Mutation linkage/raw artifact authentication is a separate
                # mandatory human audit. Here retain its intended exception.
                if request['command']!='symbols':
                    try: audit_response(request,response)
                    except AssertionError: pass
                    else: raise AssertionError('control no longer rejected')
            else:
                assert row['verdict']=='observations-pass'
                if request['command']!='symbols': audit_response(request,response)
        summaries[platform]={'image_cases':len(image['cases']),'image_controls':len(image['controls_killed']),
                             'native_cases':len(rows),'native_static':len(expected),'replay_cases':len(extras)}
    return {'kind':'evidence-completeness','head':head,'counts':summaries,'accepted':False,
            'remaining':'authenticate CI/artifact identity and raw capture/mutation linkage, A8 Git identities/Phase1 suites, physical and Windows10 holds'}

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--head',required=True)
    p.add_argument('bundle',type=Path,help='contains image-OS.json and native-OS.json for all 3 OSes')
    a=p.parse_args(); platforms=('linux','macos','windows')
    print(json.dumps(audit({x:json.loads((a.bundle/('image-'+x+'.json')).read_text()) for x in platforms},
                           {x:json.loads((a.bundle/('native-'+x+'.json')).read_text()) for x in platforms},a.head),indent=2))
