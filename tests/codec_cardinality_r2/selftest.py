"""Causal premise falsifiers; zero decoder/fixture/vendor/helper execution."""
import copy,json
from oracle import premise_model,check_ledger,OBLIGATIONS
keys=('admitted','stable_spec','count_not_mask','constructor','all_mutators','exclusive_owner','replacement','transition','reset','clear_trim_render','dispatch','success_guard','return_correspondence','host_guard','append_copy','finish')
good={k:True for k in keys};assert premise_model(good)
for k in keys:
 bad=dict(good);bad[k]=False;assert not premise_model(bad),k
n=dict(id='synthetic-only',path='EXPLICIT_SYNTHETIC.rs',sha256='a'*64,function='abstract',first_line=1,last_line=2,review='AUDITED',success_effect='conditional invariant',error_effect='not a returned success frame',ownership='abstract owned value',edges=[])
row=dict(verdict='PROVED_CONDITIONAL',argument='SYNTHETIC ledger checker positive; not a source argument',premises=['abstract premise'],nodes=[n['id']])
d=dict(source='b9f430c8c9b33532abf07eea0ed2653310639f2d',new_decoder_runs=0,scope='CARDINALITY_ONLY',library_assumptions_explicit=True,nodes=[n],codecs={c:{k:copy.deepcopy(row) for k in OBLIGATIONS} for c in ('MP3','AAC')},lemmas={'MP3':'PROVED_CONDITIONAL','AAC':'PROVED_CONDITIONAL'},global_internal='UNPROVED',fixture_outcomes_prove_universal=False)
check_ledger(d);badcases=[]
for codec in ('MP3','AAC'):
 for k in OBLIGATIONS:
  b=copy.deepcopy(d);del b['codecs'][codec][k];badcases.append(b)
for kind in ('missing-callee','unreviewed','implicit-contract','false-closure','fixture-theorem','mask-substitution'):
 b=copy.deepcopy(d)
 if kind=='missing-callee':b['nodes'][0]['edges']=[dict(kind='AUDITED',target='missing')]
 elif kind=='unreviewed':b['nodes'][0]['review']='UNREVIEWED'
 elif kind=='implicit-contract':b['nodes'][0]['edges']=[dict(kind='NAMED_CONTRACT',argument='',source_pin='')]
 elif kind=='false-closure':b['codecs']['AAC']['replacement_transition']['verdict']='RESIDUAL'
 elif kind=='fixture-theorem':b['fixture_outcomes_prove_universal']=True
 else:del b['codecs']['MP3']['spec_count']
 badcases.append(b)
for b in badcases:
 try:check_ledger(b)
 except (AssertionError,KeyError):pass
 else:raise AssertionError('incomplete ledger admitted')
print(json.dumps(dict(premise_falsifiers=len(keys),ledger_rejections=len(badcases),decoder_runs=0,scope='synthetic shape/premises only; independent source proof still required')))
