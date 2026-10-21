"""Offline synthetic readiness discriminator. No native/system/process APIs."""
import re
OBSERVER='28495e642b2a465474a4edc58380eaf8b7ee580f3fbcb4141061deadafe9b885'
FILTER='6bc51ab36ed855ef86a903808d899ab349827122db04b7e0bb13fe285adc2f74'
ROWS=[('file-read','owned',0x80000000),('file-zero','owned',0),('missing-read','missing',0x80000000),('nul-zero','nul',0),('nul-read','nul',0x80000000),('absent-dos-zero','absent',0)]
def check(b):
 assert b['mode']=='PREPARATION_ONLY' and b['synthetic'] is True
 assert b['native_calls']==b['token_probes']==b['capture_launches']==0
 assert b['helper_image']=='probe-235.exe' and b['pointer_bits'] in (32,64)
 assert b['observer_sha256']==OBSERVER and b['filter_sha256']==FILTER
 for k in ('source_bound','runtime_bound','abi_windows_unicode_pointer_correct','immediate_error','success_error_ignored','clock_pid_nonce_contract','owned_cleanup_only','private_archive_contract','future_commands_not_authorized','fresh_authorization_required'):
  assert b[k] is True,k
 assert re.fullmatch('[0-9a-f]{32}',b['nonce'])
 assert b['owned']==r'C:\owned\fixture.bin' and b['missing']==r'C:\owned\missing.bin'
 assert len(b['cases'])==6
 for c,(name,target,access) in zip(b['cases'],ROWS):
  expected=b['owned'] if target=='owned' else b['missing'] if target=='missing' else r'\\.\NUL' if target=='nul' else '\\\\.\\DTVerify235_'+b['nonce']
  assert c==dict(id=name,path=expected,access=access,share=7,disposition=3,flags=128,security_null=True,template_null=True,attempts=1)
 return 'SYNTHETIC_READINESS_CONTROLS_ONLY'
