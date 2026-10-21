"""Authoring checks and detecting count/order/gap/threshold controls only."""
import copy,json,math
from pathlib import Path
from cases import corpus,facts,wav,BLOCK
from reference import measure,kernel,report
c=corpus();f=[facts(x) for x in c]
assert f==json.loads(Path(__file__).with_name('MANIFEST.json').read_text())
pcm=sum(s['frames']*s['channels']*2 for x in c for folder in x['folders'] for s in folder)
assert pcm<32*1024*1024 and len(c)<=24
assert all(s['frames']<17640 for x in c for folder in x['folders'] for s in folder)
assert [x['total_frames'] for x in f[-4:]]==[BLOCK-1,BLOCK,BLOCK+1,BLOCK+2]
assert f[9]['total_frames']-f[8]['total_frames']==88200
controls=0
def check_inventory(x):
    at=0;previous=0;gaps=[]
    for i,s in enumerate(x['sources']):
        folder=int(s['path'].split('/')[0])
        if i and folder!=previous:
            assert folder==previous+1
            gaps.append(dict(start_frame=at,frames=88200));at+=88200
        assert s['bytes']==44+s['frames']*s['channels']*2
        assert s['start_frame']==at and s['frames']>0 and s['channels'] in [1,2]
        at+=s['frames'];previous=folder
    assert at==x['total_frames']<=x['capacity_frames'] and gaps==x['gaps']
def rejects(x):
    try:check_inventory(x)
    except AssertionError:return
    raise AssertionError('corrupt inventory accepted')
for x in f:
    check_inventory(x)
    bad=copy.deepcopy(x);bad['sources'][0]['frames']+=1
    rejects(bad);controls+=1
for delta in [-1,1]:
    bad=copy.deepcopy(f[9]);bad['gaps'][0]['frames']+=delta
    rejects(bad);controls+=1
h,l1=kernel();assert 1<l1<10
v=measure({0:(2048,2048)})
assert v['no_boost_quantized_reference_upper']<10**(-1.1/20)
assert measure({0:(32767,32767)})['sampled_peak_amplitude']>10**(-1.1/20);controls+=1
assert measure({0:(2048,2048),1:(-2048,-2048)})!=measure({0:(2048,2048),2:(-2048,-2048)});controls+=1
def same(a,b):
    if type(a) is float:
        assert abs(a-b)<=1e-9
    elif type(a) is list:
        assert len(a)==len(b)
        for x,y in zip(a,b):same(x,y)
    elif type(a) is dict:
        assert a.keys()==b.keys()
        for k in a:same(a[k],b[k])
    else:assert a==b
same(report(),json.loads(Path(__file__).with_name('REFERENCE.json').read_text()))
print(f'PASS18 frozen cases, {controls} detecting structural/reference contrasts; input PCM {pcm} bytes; no actual witness')
