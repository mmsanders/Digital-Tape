"""324 r2: Windows selection-direction constant corrected per HTML Standard; r1 preserved."""
import argparse,copy,json,re
from pathlib import Path

CASES=[]
def case(id,family,setup,steps,eq=None,same=(),contains=None,absent=None):
    CASES.append(dict(id=id,family=family,setup=setup,steps=steps,
        eq=eq or {},same=list(same),contains=contains or {},absent=absent or {}))

# 'before' is captured AFTER the deliberate edit/open/selection, before the background
# operations. 'after' is captured after settling the listed operations, without a new
# focus/selection action. These are obligations, never a second renderer/state machine.
EDIT_SAME=['label_value','focus','label_selection']
for id,value,selection,steps in [
 ('ascii-caret','Road Trip',[4,4,'none'],['unchanged cards completion','settle its snapshot']),
 ('ascii-backward-selection','Road Trip',[0,4,'backward'],['changed cards completion: zero -> one hint','settle snapshot']),
 ('two-byte-selection','é'*16,[2,10,'forward'],['Checking -> Ready completion with previous label in delayed view']),
 ('astral-caret','😀'*8,[6,6,'none'],['Checking -> Problem completion with previous label in delayed view']),
 ('paste-exact-limit','x'*32,[32,32,'none'],['paste exact32 bytes through actual handler','stale cards snapshot, then current check snapshot']),
 ('reject-ascii-excess','x'*32,[8,16,'forward'],['attempt entire33byte ASCII value','unrelated cards snapshot']),
 ('reject-multibyte-excess','é'*16,[0,8,'backward'],['attempt entire34byte multibyte value','Ready snapshot']),
 ('reject-nul','Music',[2,2,'none'],['attempt Music + NUL','changed cards snapshot']),
 ('delete-to-empty','',[0,0,'none'],['delete last character through actual handler','older nonempty label acknowledgement arrives']),
 ('two-edits-reversed-acks','Latest 😀',[9,9,'none'],['send Old then Latest 😀 label edits','resolve latest acknowledgement first, older last']),
 ('late-initial-snapshot','New label',[3,7,'forward'],['mount initial snapshot Promise remains pending','edit before initial snapshot resolves','resolve initial old label snapshot']),
 ('paste-replaces-astral-selection','😀'*7+'abcd',[14,18,'backward'],['replace selected astral character with abcd: total32bytes','changed unprobed cards and Checking snapshot'])]:
    case('E-'+id,'editing',dict(label=value,selection=selection,focus='label',music='Checking or Ready as named'),steps,
         eq={'label_value':value,'focus':'label','label_selection':[selection[0],selection[1],'forward' if selection[2]=='none' else selection[2]],**({'invalid_label_callbacks':0} if id.startswith('reject-') else {})},same=EDIT_SAME)

DETAIL_SAME=['details_visible','details_text','focus','dom_selection','selection_text','details_scroll']
case('D-ingest-poll','details',dict(music='current INGEST failure',cards='zero',details='INGEST-DIAG\n<plain>& text\n'+'retained raw diagnostic line\n'*40,open=True,focus='details',select='DIAG',scroll='nonzero reading position'),
     ['three unchanged cards completions at nominal gaps'],eq={'details_visible':True},same=DETAIL_SAME)
case('D-cards-check-snapshot','details',dict(music='Checking',cards='current unavailable failure with40 lines of typed diagnostic stderr',open=True,focus='details',select='current diagnostic',scroll='nonzero'),
     ['unrelated Checking -> Ready snapshot with identical card diagnostic'],eq={'details_visible':True},same=DETAIL_SAME)
case('D-combined-unchanged','details',dict(music='INGEST-DIAG',cards='CARDS-DIAG',open=True,focus='details',select='INGEST-DIAG'),
     ['unchanged combined diagnostics delivered twice'],eq={'details_visible':True},same=DETAIL_SAME,contains={'details_text':['INGEST-DIAG','CARDS-DIAG']})
case('D-copy-plain-selection','details',dict(music='failure',details='raw\r\n<img>& text\nlast line',open=True,focus='details',select='<img>& text'),
     ['record Selection.toString (copyable plain-text range; do NOT use OS clipboard)','unchanged poll','record same range/text'],
     eq={'details_visible':True,'selection_text':'<img>& text'},same=DETAIL_SAME)
case('D-changed-diagnostic','details',dict(cards='CARDS-OLD',open=True),
     ['current card diagnostic changes to CARDS-NEW','open current details if hidden and settle callback'],contains={'details_text':['CARDS-NEW']},absent={'details_text':['CARDS-OLD']})
case('D-cards-success-keeps-ingest','details',dict(music='INGEST-CURRENT',cards='CARDS-FAILED',open=True),
     ['fresh successful card result clears card error only','open current details if needed'],contains={'details_text':['INGEST-CURRENT']},absent={'details_text':['CARDS-FAILED']})
case('D-ingest-success-keeps-cards','details',dict(music='INGEST-FAILED',cards='CARDS-CURRENT',open=True),
     ['fresh successful music check replaces music failure only','open current details if needed'],contains={'details_text':['CARDS-CURRENT']},absent={'details_text':['INGEST-FAILED']})
case('D-reset-closes-music-details','details',dict(music='INGEST-OLD',cards='zero no diagnostic',open=True,label='Road Trip'),
     ['intentional Start over through actual action','settle reset view'],eq={'label_value':'','details_visible':False},absent={'details_text':['INGEST-OLD']})
case('D-late-details-response','details',dict(cards='CARDS-OLD',open=True,details_promise='pending'),
     ['replace with current CARDS-NEW','request current details and resolve it','resolve older CARDS-OLD response last'],
     contains={'details_text':['CARDS-NEW']},absent={'details_text':['CARDS-OLD']})
case('D-dismiss-by-clear','details',dict(music='valid',cards='CARDS-FAILED',open=True),
     ['fresh card success clears current card diagnostic','settle view','late previous details response arrives'],
     eq={'details_visible':False},absent={'details_text':['CARDS-FAILED']})

def order(id,steps,eq,contains=None,absent=None):
    case('O-'+id,'ordering',dict(coordinator='actual production Bridge; typed outcomes; real emitted View sequence',renderer='mountApp over those Views',active_control='label edit or open details while named coordinator steps occur; raw callback/selection capture required'),steps,eq=eq,contains=contains,absent=absent)
order('drop-check-card-ready',['admit folder A -> Checking','cards zero -> one hint','current check succeeds88200frames'],
      {'state':'Ready','frames':88200,'card_line':'Card ready (64 GB).','accepted_folders':['A'],'check_requests':1,'label_unchanged':True})
order('card-then-check-failure',['admit folder A','successful one-hint card completion','current check fails typed INGEST-DIAG','open details'],
      {'state':'Problem','card_line':'Card ready (64 GB).'},contains={'details_text':['INGEST-DIAG']})
order('check-failure-then-card',['current check fails INGEST-DIAG','fresh card success','open current details'],
      {'state':'Problem'},contains={'details_text':['INGEST-DIAG']})
order('check-success-card-failure',['current check succeeds88200frames','cards current failure CARDS-DIAG','open details'],
      {'state':'Ready','frames':88200},contains={'details_text':['CARDS-DIAG']})
order('reset-while-checking',['admit A, worker pending','Start over invalidates before cancellation','late old check success and duplicate arrive'],
      {'state':'Empty','label_value':'','accepted_folders':[],'late_publications':0,'replacement_before_old_cleanup':0})
order('reset-due-poll',['due poll is paused before admission','Start over resets music/label (not shutdown)','resume one current poll'],
      {'state':'Empty','label_value':'','poll_workers':1,'max_concurrent':1,'foreign_cleanup':[]})
order('reset-inflight-poll',['current poll blocked','Start over resets music/label','current poll completes with zero offered/unprobed','duplicate completion delivered'],
      {'state':'Empty','label_value':'','duplicate_publications':0,'max_concurrent':1,'card_line':'Put a card in.'})
order('shutdown-due-poll',['pause due poll after preliminary stop read','complete shutdown cancellation pass','resume poll registration'],
      {'poll_workers_after_stop':0,'late_publications':0,'active_cards':None,'foreign_cleanup':[]})
order('shutdown-inflight',['registered typed poll blocked','shutdown stops polls and invalidates -> cancel -> child terminal -> owned cleanup','late/duplicate completion'],
      {'late_publications':0,'cleanup_before_terminal':0,'new_workers_after_stop':0,'foreign_cleanup':[]})
order('supersede-and-destroy',['admit A check then append B/C','old check terminal/cleanup then replacement','old completion repeats','destroy binding with details/snapshot Promise pending','deliver queued event/Promise'],
      {'accepted_folders':['A','B','C'],'check_requests':2,'replacement_before_old_cleanup':0,'late_publications':0,'mutations_after_destroy':0,'remaining_subscriptions':0})

def qualify(r,head):
    assert re.fullmatch('[0-9a-f]{40}',head) and r['source_head']==head
    assert r['evidence_class']=='production renderer/binding/coordinator controlled interaction'
    for k in ['adapter_refs','raw_refs','source_blobs','commands','actual_emission_refs']:assert r[k]
    assert r['native_ui'] is False and r['real_child_runs']==r['live_metadata_runs']==0
    assert r['shipping_fake_route'] is False and r['reference_ui_model'] is False
    assert r['entry_points']==['mountApp','mountScreen','Bridge']
    assert set(r['cases'])=={c['id'] for c in CASES}
    for c in CASES:
        x=r['cases'][c['id']];before=x['before'];after=x['after']
        assert x['steps_ref'] and x['raw_ref'] and x['actual_production_calls_ref']
        assert x['event_order']==c['steps'],'unissued reorder/skip: '+c['id']
        assert x['producer_expected_trace_used'] is False
        for o in [before,after]:
            assert o['make_enabled'] is False and o['forbidden_nodes']==[]
            if 'label_value' in o:
                assert '\0' not in o['label_value'] and len(o['label_value'].encode('utf-8'))<=32
                assert o['utf8_bytes']==len(o['label_value'].encode('utf-8'))
        for k,want in c['eq'].items():assert after[k]==want,(c['id'],k,after[k],want)
        for k in c['same']:assert before[k]==after[k],(c['id'],k,'background update disrupted active control')
        for k,words in c['contains'].items():assert all(w in after[k] for w in words),(c['id'],k)
        for k,words in c['absent'].items():assert not any(w in after[k] for w in words),(c['id'],k)
    return 'ONLY covered controlled interactions; no native/input/IPC/real-child/device/fullAPP acceptance'

def fixture():
    # SYNTHETIC predicate self-test only. No UI events or state transitions are implemented.
    observations={}
    for c in CASES:
        a=dict(make_enabled=False,forbidden_nodes=[],label_value='Music',utf8_bytes=5,focus='label',label_selection=[1,2,'forward'],
               details_visible=True,details_text='INGEST-DIAG CARDS-DIAG',dom_selection=[0,2],selection_text='DIAG',details_scroll=30)
        a.update(c['eq'])
        for k,words in c['contains'].items():a[k]=' '.join(words)
        for k,words in c['absent'].items():a[k]=a.get(k,'').replace(words[0],'') if words else a.get(k,'')
        a['utf8_bytes']=len(a['label_value'].encode())
        observations[c['id']]=dict(before=copy.deepcopy(a),after=a,event_order=c['steps'],steps_ref='SYNTHETIC',raw_ref='SYNTHETIC',actual_production_calls_ref='SYNTHETIC',producer_expected_trace_used=False)
    return dict(source_head='a'*40,evidence_class='production renderer/binding/coordinator controlled interaction',adapter_refs=['SYNTHETIC'],raw_refs=['SYNTHETIC'],source_blobs=['SYNTHETIC'],commands=['SYNTHETIC'],actual_emission_refs=['SYNTHETIC'],native_ui=False,real_child_runs=0,live_metadata_runs=0,shipping_fake_route=False,reference_ui_model=False,entry_points=['mountApp','mountScreen','Bridge'],cases=observations)
def controls():
    assert len(CASES)==32 and {f:sum(c['family']==f for c in CASES) for f in ['editing','details','ordering']}==dict(editing=12,details=10,ordering=10)
    good=fixture();qualify(good,'a'*40)
    mutations=[lambda r:r['cases']['E-ascii-caret']['after'].update(label_value='OLD',utf8_bytes=3),
        lambda r:r['cases']['E-ascii-backward-selection']['after'].update(label_selection=[0,0,'none']),
        lambda r:r['cases']['D-ingest-poll']['after'].update(details_visible=False),
        lambda r:r['cases']['D-copy-plain-selection']['after'].update(selection_text=''),
        lambda r:r['cases']['D-cards-success-keeps-ingest']['after'].update(details_text=''),
        lambda r:r['cases']['D-late-details-response']['after'].update(details_text='CARDS-OLD'),
        lambda r:r['cases']['O-reset-while-checking']['after'].update(late_publications=1),
        lambda r:r['cases']['O-shutdown-due-poll']['after'].update(poll_workers_after_stop=1),
        lambda r:r['cases']['O-supersede-and-destroy']['after'].update(mutations_after_destroy=1),
        lambda r:r['cases']['O-check-failure-then-card'].update(event_order=[]),
        lambda r:r.update(reference_ui_model=True),lambda r:r.update(real_child_runs=1)]
    for mutation in mutations:
        bad=copy.deepcopy(good);mutation(bad)
        try:qualify(bad,'a'*40)
        except AssertionError:continue
        raise AssertionError('interaction negative control survived')
    print('PASS32 r2 interaction obligations/12 causal index controls; ZERO Product/DOM/native execution')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--emit',action='store_true');p.add_argument('--input',type=Path);p.add_argument('--candidate');a=p.parse_args()
    if a.emit:print(json.dumps(dict(cases=CASES,scope='controlled production components only; no runtime admission'),ensure_ascii=True,indent=2))
    elif a.input:print(qualify(json.loads(a.input.read_text(encoding='utf-8-sig')),a.candidate))
    else:controls()
