"""Proof-ledger completeness discriminator only; source arguments need human independent review."""
OBLIGATIONS=('admission','constructor','ownership_alias','spec_count','dispatch','mutable_decode','clear_trim_render','reuse_reset','replacement_transition','success_error','returned_frame','host_copy_finish')
def check_ledger(doc):
 assert doc['source']=='b9f430c8c9b33532abf07eea0ed2653310639f2d' and doc['new_decoder_runs']==0
 assert doc['scope']=='CARDINALITY_ONLY' and doc['library_assumptions_explicit'] is True
 nodes={n['id']:n for n in doc['nodes']};assert len(nodes)==len(doc['nodes'])
 for n in nodes.values():
  assert n['path'] and len(n['sha256'])==64 and n['function'] and 1<=n['first_line']<=n['last_line']
  assert n['review']=='AUDITED' and n['success_effect'] and n['error_effect'] and n['ownership']
  for edge in n['edges']:
   assert edge['kind'] in ('AUDITED','NAMED_CONTRACT','PROVED_UNREACHABLE')
   if edge['kind']=='AUDITED':assert edge['target'] in nodes
   else:assert edge['argument'] and edge['source_pin']
 for codec in ('MP3','AAC'):
  rows=doc['codecs'][codec];assert set(rows)==set(OBLIGATIONS)
  for k,r in rows.items():
   assert r['verdict'] in ('PROVED_CONDITIONAL','RESIDUAL','COUNTEREXAMPLE')
   assert r['argument'] and r['premises'] is not None and r['nodes'] and all(n in nodes for n in r['nodes'])
  closure=doc['lemmas'][codec]
  if closure=='PROVED_CONDITIONAL':assert all(r['verdict']=='PROVED_CONDITIONAL' for r in rows.values())
  else:assert closure in ('RESIDUAL','COUNTEREXAMPLE') and any(r['verdict']!='PROVED_CONDITIONAL' for r in rows.values())
 assert doc['global_internal']=='UNPROVED' and doc['fixture_outcomes_prove_universal'] is False
 return 'LEDGER_SHAPE_ONLY_NOT_SOURCE_PROOF'

def premise_model(p):
 """Deliberately abstract/private-state countermodels, never admitted decoder witnesses."""
 return all(p[k] is True for k in ('admitted','stable_spec','count_not_mask','constructor','all_mutators','exclusive_owner','replacement','transition','reset','clear_trim_render','dispatch','success_guard','return_correspondence','host_guard','append_copy','finish'))
