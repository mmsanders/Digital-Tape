"""Fixed, contract-authored inputs. Not actual process receipts."""
import copy

def discovery():
 base=dict(whole=True,removable_or_sd=True,nonvirtual=True,bytes=64000000000,not_system_boot_swap=True,mounts=[])
 rows=[('bare-known',base)]
 for k in base:rows.append(('unknown-'+k,dict(base,**{k:None})))
 for k in ['whole','removable_or_sd','nonvirtual','not_system_boot_swap']:rows.append(('refused-'+k,dict(base,**{k:False})))
 rows += [('size-boundary',dict(base,bytes=2**37)),('size-too-large',dict(base,bytes=2**37+1))]
 view=dict(style='MBR',p1_type=14,p1_start=2048,p1_sectors=32768,p2_type=218,p2_start=34816,p2_end_bytes=base['bytes'],p3=False,p4=False)
 own=dict(base,mounts=[1],partition_view=view)
 rows += [('own-hint',own),('own-hint-invalid-raw',dict(own,raw_layout_valid=False)),('own-hint-no-raw-fields',dict(own,raw_layout_valid=None)),('foreign-second-mount',dict(own,mounts=[1,2]))]
 for k,v in view.items():
  rows.append(('unknown-view-'+k,dict(own,partition_view=dict(view,**{k:None}))))
  rows.append(('wrong-view-'+k,dict(own,partition_view=dict(view,**{k:(not v if type(v)is bool else 'wrong' if isinstance(v,str) else v+1)}))))
 return [{'name':name,'facts':copy.deepcopy(f)} for name,f in rows]

def plan():
 return {
 'S2':['complete-empty','complete-single','complete-many','mixed-refused-unknown-offered','enumeration-unavailable','usage','report-exclusivity-no-follow','no-report-regression'],
 'S3-policy':['ordered-six-refusals','unknown-facts-refuse','own-p1-valid-exact','OS-own-hint-byte-invalid','bare-CRC-55AA-mounted','foreign-mount','erase-path-not-exact','raw-unmounted-positive'],
 'S3-session':['no-change','detected-remove-load','detected-remove-commit','detected-change-verify','equal-size-change-detected','same-path-no-reopen','NULL-write-verify','query-handles-read-only'],
 'S3-output':['equivalent-1-frame','equivalent-1023-frames','equivalent-1024-frames','equivalent-1025-frames','label-32-UTF8-bytes','label-33-UTF8-bytes','bad-WAV','WAV-truncated-after-start','geometry-before-write','commit-failure','verify-findings','CARD_CHANGED-precedence'],
 'S3-parent':['ordinary-exclusive-report','existing-leaf','dangling-link-leaf','symlink-leaf','substituted-parent','reparse-parent','cleanup-substitution-foreign-sentinel'],
 'native-held':['Win11-real-reader-remove-reinsert','Win11-equal-size-swap','Mac-arm64-real-reader-remove-reinsert','Mac-equal-size-swap','ordinary-security-app-runtime-G1','elevation-prompt-decline','G2']}
