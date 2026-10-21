import copy
from oracle import check,ROWS,OBSERVER,FILTER
b=dict(mode='PREPARATION_ONLY',synthetic=True,native_calls=0,token_probes=0,capture_launches=0,helper_image='probe-235.exe',pointer_bits=64,observer_sha256=OBSERVER,filter_sha256=FILTER,nonce='a'*32,owned=r'C:\owned\fixture.bin',missing=r'C:\owned\missing.bin')
for k in ('source_bound','runtime_bound','abi_windows_unicode_pointer_correct','immediate_error','success_error_ignored','clock_pid_nonce_contract','owned_cleanup_only','private_archive_contract','future_commands_not_authorized','fresh_authorization_required'):b[k]=True
b['cases']=[]
for name,target,access in ROWS:
 path=b['owned'] if target=='owned' else b['missing'] if target=='missing' else r'\\.\NUL' if target=='nul' else '\\\\.\\DTVerify235_'+b['nonce']
 b['cases'].append(dict(id=name,path=path,access=access,share=7,disposition=3,flags=128,security_null=True,template_null=True,attempts=1))
assert check(b)=='SYNTHETIC_READINESS_CONTROLS_ONLY'
mutants=[]
for k,v in [('helper_image','python.exe'),('pointer_bits',16),('observer_sha256','0'*64),('filter_sha256','0'*64),('native_calls',1),('token_probes',1),('capture_launches',1),('synthetic',False),('nonce','')]:
 m=copy.deepcopy(b);m[k]=v;mutants.append(m)
for k in ('source_bound','runtime_bound','abi_windows_unicode_pointer_correct','immediate_error','success_error_ignored','clock_pid_nonce_contract','owned_cleanup_only','private_archive_contract','future_commands_not_authorized','fresh_authorization_required'):
 m=copy.deepcopy(b);m[k]=False;mutants.append(m)
for k,v in [('path',r'\\.\PhysicalDrive0'),('path',r'\\?\Volume{unissued}'),('path',r'\\.\OtherDosName'),('path',r'C:\owned\..\outside'),('access',0x40000000),('share',0),('disposition',2),('flags',0x40000000),('attempts',2)]:
 m=copy.deepcopy(b);m['cases'][0][k]=v;mutants.append(m)
for m in mutants:
 try:check(m)
 except AssertionError:pass
 else:raise AssertionError('negative control admitted')
print('PASS: synthetic6-template readiness and28 rejection controls; ZERO native/capture/token execution')
