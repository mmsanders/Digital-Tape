"""Contract-first bridge observations. No Product code or private tests imported."""
import argparse, json
from pathlib import Path

GENERIC='Something went wrong. Nothing else on your computer was changed.'
PULLED='The card was taken out before it was finished. Put it back in and press Make cartridge again.'
CASES=[]
def add(name, origin, trigger, message, **extra):
    CASES.append(dict(id=name, origin=origin, trigger=trigger, message=message, **extra))

add('drop-file','app','drop one ordinary file through production drop handler',
    'Drop a folder of music, not single songs.', new_children=0, additions=0)
add('drop-mixed','app','drop folder plus file in one gesture through production handler',
    'Drop a folder of music, not single songs.', new_children=0, additions=0)
add('spawn-failed','app','production launcher returns OS spawn failure for ingest',GENERIC)
add('elevation-declined','app','production make-launch dependency returns UAC cancellation',
    "The computer said no, so the card wasn't changed. Press Make cartridge to try again.", make_children=0)
for phase in ('before-confirm','after-confirm'):
    for change in ('zero','two','different-path','different-capacity'):
        add('recheck-'+phase+'-'+change,'app',f'production make recheck {phase}: {change}',
            None, state='Ready', make_children=0, card_line_current=True)
for name,tool,trigger,message in [
    ('overage-one','ingest','real one-frame overage at 3600s', 'This music is 1 s too long for a 60-minute cartridge. Take some songs out and drop the folder again.'),
    ('overage-192','ingest','real 8467200-frame excess including gaps','This music is 3 min 12 s too long for a 60-minute cartridge. Take some songs out and drop the folder again.'),
    ('protected','ingest','real protected source named locked.m4a','"locked.m4a" is copy-protected, so it can\'t go on a cartridge. Take it out of the folder.'),
    ('corrupt','ingest','real corrupt source named broken.wav','"broken.wav" can\'t be used. Take it out of the folder.'),
    ('nonmusic','ingest','real folder Music containing a text file','The folder "Music" has something in it that isn\'t music. Use a folder with only songs in it.'),
    ('empty','ingest','real empty folder Music','The folder "Music" has something in it that isn\'t music. Use a folder with only songs in it.'),
    ('source-short','ingest','real zero-frame source short.wav','"short.wav" can\'t be used. Take it out of the folder.'),
    ('small','make','real geometry or capacity refusal on private target','This card is too small. Use a bigger card.'),
    ('removed','make','real CI target removal during make',PULLED),
    ('device-io','make','real device I/O failure on CI target',PULLED),
    ('host-query','make','real required boundary-query OS failure on CI target',PULLED),
    ('verify-findings','make','real verify finding on CI target','Something went wrong writing this card. Press Make cartridge to try again.'),
    ('wav-truncated','make','real source truncation after make starts','The music file changed while the cartridge was being made. Start over and drop the folder again.'),
    ('safety-refusal','make','real exit3 refusal on private target',"This card can't be used right now. Check the card and try again."),
    ('generic-make','make','real make usage or invalid-label refusal before device work',"The cartridge wasn't finished. Start over and try again."),
    ('discovery-unavailable','cards','real failed discovery query',GENERIC),
]: add(name,'child',trigger,message,tool=tool)

def check(rows):
    assert len(rows)==len(CASES)
    assert [r['id'] for r in rows]==[c['id'] for c in CASES], 'missing/duplicate/reordered case'
    for c,r in zip(CASES,rows):
        assert r['bridge_refs'] and r['raw_refs']
        assert r['message']==c['message'] if c['message'] is not None else r['card_line_current'] is True
        for key in ('new_children','make_children','additions','state','card_line_current'):
            if key in c: assert r[key]==c[key], (c['id'],key)
        # A rejected drop has no child stderr. Do not demand nonempty copyable
        # diagnostics from that zero-child notice. This says nothing about the
        # native Show-details control, which remains a separate G4/C2 check.
        if c['id'] not in ('drop-file','drop-mixed') or r.get('details'):
            assert r['details_copyable']
        assert r['auto_relaunches']==0
        if c['origin']=='child':
            assert r['real_tool_outcome'] and r['exit']!=0
            assert r['report_ref'] and r['process_ref']
            assert r['message_changed_stderr']==r['message'], 'stderr selected outcome'
        else: assert r['production_action'] and not r['forged_child_report']
    return len(rows)

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('result',nargs='?',type=Path); p.add_argument('--emit',action='store_true'); a=p.parse_args()
    if a.emit: print(json.dumps(CASES,indent=2))
    else: print(check(json.loads(a.result.read_text())['rows']), 'bridge rows pass')
