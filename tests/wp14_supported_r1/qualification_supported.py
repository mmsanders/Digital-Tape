"""ADR206 companion oracle. Original three-platform package remains immutable."""
import sys,re
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent.parent/'wp14_r1'))
from catalog import image_cases,IMAGE_CONTROLS
from native import requests,audit_response,capture_identity
from qualification import census
ALL=('linux','macos','windows')
def parse_platforms(value='linux,macos,windows'):
    if not isinstance(value,str):raise ValueError('platform list must be text')
    parts=value.split(',')
    if parts!=sorted(set(parts)) or not {'linux','windows'}<=set(parts)<=set(ALL):raise ValueError('sorted unique platforms must include linux and windows')
    return tuple(parts)
def validate_maps(images,natives,platforms=None):
    parts=parse_platforms(','.join(platforms)) if platforms is not None else ALL
    assert isinstance(images,dict) and isinstance(natives,dict)
    assert set(images)==set(natives)==set(parts),'named platform evidence missing or unexpected'
    return parts

def audit_platforms(images,natives,head,platforms=None):
    platforms=validate_maps(images,natives,platforms)
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
    return {'kind':'evidence-completeness','head':head,'counts':summaries,'accepted':False,'platforms':list(platforms),'deferred':sorted(set(ALL)-set(platforms)),
            'remaining':'authenticate CI/artifact identity and raw capture/mutation linkage, A8 Git identities/Phase1 suites, physical and Windows10 holds'}
