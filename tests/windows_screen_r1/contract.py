"""305 production-renderer/input predicates. Test DOM only; no native UI claim."""
import argparse, copy, json, math, re
from html.parser import HTMLParser
from pathlib import Path

CAPACITY=158760000
GENERIC='Something went wrong. Nothing else on your computer was changed.'
FOLDERS='Drop a folder of music, not single songs.'
def overage(frames):
    seconds=(frames+44099)//44100
    return f'This music is {seconds//60} min {seconds%60} s too long for a 60-minute cartridge. Take some songs out and drop the folder again.' if seconds>=60 else f'This music is {seconds} s too long for a 60-minute cartridge. Take some songs out and drop the folder again.'

VIEWS=[
 dict(id='empty',state='Empty',label='',frames=0,ratio=0,indeterminate=False,too_long=False,sentence='',details='',action=None,card='Put a card in.'),
 dict(id='checking',state='Checking',label='Music',frames=None,ratio=None,indeterminate=True,too_long=False,sentence='Checking the music…',details='',action=None,card='Put a card in.'),
 dict(id='ready-two-seconds',state='Ready',label='Music',frames=88200,ratio=88200/CAPACITY,indeterminate=False,too_long=False,sentence='',details='',action='Start over',card='Put a card in.'),
 dict(id='exact-fit',state='Ready',label='Music',frames=CAPACITY,ratio=1,indeterminate=False,too_long=False,sentence='',details='',action='Start over',card='Put a card in.'),
 *[dict(id='overage-'+str(n),state='Problem',label='Music',frames=CAPACITY+n,ratio=1,indeterminate=False,too_long=True,sentence=overage(n),details='raw overage diagnostic',action='Start over',card='Put a card in.',excess_frames=n) for n in [1,8467200]],
 *[dict(id=k,state='Problem',label='Music',frames=None,ratio=None,indeterminate=False,too_long=False,sentence=m,details='raw\r\n<unsafe>& diagnostics',action='Start over',card='Put a card in.') for k,m in [
  ('folders-only',FOLDERS),('protected','"song.wav" is copy-protected, so it can\'t go on a cartridge. Take it out of the folder.'),
  ('unusable','"song.wav" can\'t be used. Take it out of the folder.'),
  ('folder-content','The folder "Music" has something in it that isn\'t music. Use a folder with only songs in it.'),('generic',GENERIC)]],
 dict(id='making-projection-only',state='Making',label='Music',frames=None,ratio=None,indeterminate=False,too_long=False,sentence='Writing the music…',details='',action=None,card='Put a card in.',progress=[0,.2,.2,.8,1]),
 dict(id='done-projection-only',state='Done',label='Music',frames=None,ratio=None,indeterminate=False,too_long=False,sentence='Your cartridge is ready. You can take the card out now.',details='',action='Make another',card='Put a card in.'),
 dict(id='escaped-name',state='Problem',label='Music',frames=None,ratio=None,indeterminate=False,too_long=False,sentence='"<img src=x onerror=alert(1)>.wav" can\'t be used. Take it out of the folder.',details='<script>unsafe</script>',action='Start over',card='Put a card in.'),
]
LABELS=[dict(before=a,attempt=b,after=c) for a,b,c in [('', 'A','A'),('', 'x'*32,'x'*32),('x'*32,'x'*33,'x'*32),('', 'é'*16,'é'*16),('é'*16,'é'*16+'x','é'*16),('', '😀'*8,'😀'*8),('😀'*8,'😀'*8+'x','😀'*8),('Music','Music\0','Music')]]
DROPS=[dict(id='ordered',gestures=[[dict(kind='folder',path='A')],[dict(kind='folder',path='B'),dict(kind='folder',path='C')]],accepted=['A','B','C'],calls=2),
       dict(id='file',gestures=[[dict(kind='folder',path='A')],[dict(kind='file',path='song.wav')]],accepted=['A'],calls=1),
       dict(id='mixed',gestures=[[dict(kind='folder',path='A')],[dict(kind='folder',path='B'),dict(kind='file',path='song.wav')]],accepted=['A'],calls=1)]

class HTML(HTMLParser):
    def __init__(self):super().__init__();self.bad=[]
    def handle_starttag(self,tag,attrs):
        if tag in ['ul','ol','select','option','table','audio','video','img','script']:self.bad.append(tag)
        if any(k.startswith('on') for k,v in attrs):self.bad.append('inline-handler')

def view(got,want):
    assert got['label']==want['label'] and got['state']==want['state']
    assert got['make_disabled'] and got['enumerated_items']==[]
    assert got['sentence']==want['sentence'] and got['card']==want['card']
    assert got['action']==want['action'] and got['frames']==want['frames']
    assert got['too_long']==want['too_long'] and got['indeterminate']==want['indeterminate']
    if want['ratio'] is None:assert got['ratio'] is None
    else:assert type(got['ratio']) in [int,float] and math.isfinite(got['ratio']) and abs(got['ratio']-want['ratio'])<1e-12
    if want['state']=='Problem':assert got['details']==want['details'] and got['details_copyable']
    if want['state']=='Making':
        assert got['progress_bar_count']==1 and got['progress']==want['progress']
    h=HTML();h.feed(got['html']);assert not h.bad
    assert got['html'] and got['raw_ref']

def qualify(r,head):
    assert re.fullmatch('[0-9a-f]{40}',head) and r['source_head']==head
    assert r['evidence_class']=='production component / test DOM' and r['raw_refs'] and r['adapter_ref']
    assert not r['native_ui'] and not r['shipping_test_switch'] and not r['make_enabled']
    assert set(r['views'])=={x['id'] for x in VIEWS}
    for x in VIEWS:view(r['views'][x['id']],x)
    assert r['labels']==LABELS # after is actual DOM value after input, never a predicted trace
    assert set(r['drops'])=={x['id'] for x in DROPS}
    for x in DROPS:
        y=r['drops'][x['id']];assert y['accepted']==x['accepted'] and y['accepted_check_requests']==x['calls']
        assert y['transport_batches']==[[z['path'] for z in batch] for batch in x['gestures']]
        assert y['accepted_batches']==[[z['path'] for z in batch] for batch in x['gestures'] if all(z['kind']=='folder' for z in batch)]
        if x['id']!='ordered':assert y['sentence']==FOLDERS
    reset=r['start_over'];assert reset['callbacks']==1 and reset['accepted']==[] and reset['label']=='' and reset['details']=='' and reset['state']=='Empty' and reset['frames']==0 and reset['make_disabled']
    assert r['malformed_drop_callbacks']==0 and r['mount_side_effects']==[]
    return 'ONLY production renderer/input component; actual Windows UI UNEXECUTED'

def controls():
    good=dict(VIEWS[0],make_disabled=True,enumerated_items=[],html='<main><input value=""><button disabled>Make cartridge</button></main>',raw_ref='SYNTHETIC')
    view(good,VIEWS[0])
    for k,v in [('label','prefilled'),('make_disabled',False),('enumerated_items',['song']),('ratio',.1),('html','<ul><li>song</li></ul>')]:
        bad=copy.deepcopy(good);bad[k]=v
        try:view(bad,VIEWS[0])
        except AssertionError:continue
        raise AssertionError('screen causal control survived: '+k)
    assert overage(1).startswith('This music is 1 s') and '3 min 12 s' in overage(8467200)
    assert len(('é'*16).encode())==32 and len(('😀'*8).encode())==32
    fixture=dict(source_head='a'*40,evidence_class='production component / test DOM',raw_refs=['SYNTHETIC'],adapter_ref='SYNTHETIC',native_ui=False,shipping_test_switch=False,make_enabled=False,
                 views={v['id']:dict(v,make_disabled=True,enumerated_items=[],html='<main>fixture</main>',raw_ref='SYNTHETIC',details_copyable=True,progress_bar_count=1) for v in VIEWS},labels=copy.deepcopy(LABELS),
                 drops={d['id']:dict(accepted=d['accepted'],accepted_check_requests=d['calls'],transport_batches=[[z['path'] for z in b] for b in d['gestures']],accepted_batches=[[z['path'] for z in b] for b in d['gestures'] if all(z['kind']=='folder' for z in b)],sentence=FOLDERS) for d in DROPS},
                 start_over=dict(callbacks=1,accepted=[],label='',details='',state='Empty',frames=0,make_disabled=True),malformed_drop_callbacks=0,mount_side_effects=[])
    qualify(fixture,'a'*40)
    mutations=[lambda q:q['labels'][2].update(after='x'*32+'y'),lambda q:q['drops']['mixed'].update(accepted=['A','B']),lambda q:q['drops']['ordered'].update(accepted_batches=[['A'],['C','B']]),lambda q:q['drops']['mixed'].update(transport_batches=[['A'],['B']]),
               lambda q:q['start_over'].update(label='old'),lambda q:q['views']['generic'].update(details='filtered'),lambda q:q['views']['overage-1'].update(sentence=overage(8467200)),
               lambda q:q.update(native_ui=True),lambda q:q.update(malformed_drop_callbacks=1),lambda q:q.update(mount_side_effects=['cards'])]
    for change in mutations:
        q=copy.deepcopy(fixture);change(q)
        try:qualify(q,'a'*40)
        except AssertionError:continue
        raise AssertionError('input/reset/copy/provenance causal control survived')
    print('PASS screen/UTF8/bar/copy/no-list causal controls; ZERO Product/DOM/native execution')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--emit',action='store_true');p.add_argument('--input',type=Path);p.add_argument('--candidate');a=p.parse_args()
    if a.emit:print(json.dumps(dict(views=VIEWS,labels=LABELS,drops=DROPS,malformed_drop_inputs=[None,{},'A',[dict(kind='unknown',path='A')]]),ensure_ascii=True,indent=2))
    elif a.input:print(qualify(json.loads(a.input.read_text(encoding='utf-8-sig')),a.candidate))
    else:controls()
