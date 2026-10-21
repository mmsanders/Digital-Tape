"""Frozen recorder obligations, authored before Software511 implementation."""
def corpus():
 rows=[]
 def add(name,kind,expected):rows.append(dict(name=name,kind=kind,expected=expected))
 for n in ('text','binary','empty','exit7','unicode-input','second-case'):
  add('complete-'+n,'actual-helper','COMPLETE_EVIDENCE')
 for n in ('producer-killed-after-ready','recorder-killed-after-ready','parser-raises','cleanup-raises'):
  add(n,'actual-interruption','INCOMPLETE_RAW_RETAINED')
 for n in ('duplicate-id','existing-case-path','path-traversal'):
  add(n,'actual-exclusive-path','REFUSED_UNCHANGED')
 for n in ('changed-stdout','truncated-stderr','missing-exit','missing-input','stale-timing-checksum',
  'wrong-argv','wrong-binary','wrong-source','wrong-input-identity','wrong-nonce','wrong-pid',
  'unlisted-case-file','incomplete-promoted','wrong-stream-count','negative-timing'):
  add(n,'actual-positive-copy-corruption','REJECTED')
 for n in ('archive-extra','archive-duplicate','archive-traversal','archive-truncated'):
  add(n,'actual-positive-archive-corruption','REJECTED')
 assert len(rows)==32
 return rows
