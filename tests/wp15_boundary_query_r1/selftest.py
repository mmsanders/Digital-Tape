import copy,json
from cases import case,matrix
from oracle import check,parse_report,prior
def run():
 rows=matrix()
 assert len(rows)==49 and len({r['id'] for r in rows})==49
 for r in rows:check(r)
 base=case('safety','required-initial-failure')
 controls={
 'write-before-required-query':lambda r:r.update(write_mode_opens_before_query=1),
 'destruction-before-initial-query':lambda r:r.update(destructive_ops_before_query=1),
 'ignore-query-failure':lambda r:r.update(exit=0,ordinary_error=None),
 'query-error-as-engine-error':lambda r:r.update(engine_error_synthesized=True),
 'query-error-as-card-changed':lambda r:r['ordinary_error'].update(id='CARD_CHANGED'),
 'wrong-phase':lambda r:r['ordinary_error'].update(phase='load'),
 'wrong-op':lambda r:r['ordinary_error'].update(op='read_lba0'),
 'nonnull-subject':lambda r:r['ordinary_error'].update(subject='card'),
 'nonstring-os-error':lambda r:r['ordinary_error'].update(os_error=5),
 'continue-device-work':lambda r:r.update(continued_device_work=True),
 'reopen-after-stop':lambda r:r.update(session_reopened=True),
 'erase-earlier-stdout':lambda r:r.update(stdout_after_hex=''),
 'rollback-publication':lambda r:r.update(publication_after=['invented']),
 'claim-card-unchanged':lambda r:r.update(claimed_card_unchanged=True)}
 for name,mutate in controls.items():
  b=copy.deepcopy(base);mutate(b)
  try:check(b)
  except AssertionError:pass
  else:raise AssertionError(name)
 r=case('commit','changed-plus-query-error');r['ordinary_error']['id']='HOST_QUERY_FAILED'
 try:check(r)
 except AssertionError:pass
 else:raise AssertionError('positive change downgraded')
 r=case('commit','monitor-failure',True)
 for key,value in [('exit',0),('report_warning_count',0),('report_writes_after_failure',True)]:
  b=copy.deepcopy(r);b[key]=value
  try:check(b)
  except AssertionError:pass
  else:raise AssertionError(key)
 b=case('verify','query-success',True);b['exit']=1
 try:check(b)
 except AssertionError:pass
 else:raise AssertionError('report failure changed ordinary success')
 raw=bytes.fromhex(base['report_hex'])
 assert parse_report(raw,'fixture','0'*32,1)['refusal']['id']=='HOST_QUERY_FAILED'
 for mutant in (raw.replace(b'media_query',b'read_lba0'),raw.replace(b'"subject":null',b'"subject":"x"'),raw.replace(b'"exit":1',b'"exit":0'),raw.replace(b'"phase":"safety"',b'"phase":"capacity"')):
  assert parse_report(mutant,'fixture','0'*32,1) is None
 print(json.dumps({'authored_matrix_rows':len(rows),'detecting_controls':23,'scope':'synthetic authored oracle only; zero Product/native acceptance'},indent=2))
if __name__=='__main__':run()
