"""APP-1A contract-only report/parser and discovery reference predicates.

Fixtures are parser inputs, never claims that a child actually emitted them.
No Product imports; no engine/layout parser. Python integers avoid JS rounding.
"""
import json,re,unicodedata

LIMIT=2**53-1
ERRORS=set(('IO BAD_MAGIC CRC VERSION UNSUPPORTED_STATE GEOMETRY INCOMPLETE INCONSISTENT NO_VALID_INDEX READ_ONLY CARTRIDGE_FULL INDEX_FULL DEST_TOO_SMALL SEQUENCE_EXHAUSTED FAULTED NOT_MOUNTED BUSY UNDERRUN INVALID_ARG').split())
ERRORS={'TAPE_ERR_'+s for s in ERRORS}
STEPS={'ingest':['list','decode','convert','write','publish'],
       'tapectl cards':['enumerate'],
       'tapectl make':['safety','provision','load','commit','verify_a','verify_b']}
I2='INGEST_USAGE INGEST_LENGTH_INVALID INGEST_TOO_LONG INGEST_RIFF_LIMIT FOLDER_SYMLINK FOLDER_UNREADABLE FOLDER_NOT_FOLDER FOLDER_DUPLICATE FOLDER_EMPTY FOLDER_NAME_COLLISION FOLDER_NAME_NOT_UNICODE ENTRY_SYMLINK ENTRY_NESTED_FOLDER ENTRY_NOT_REGULAR ENTRY_NAME_INVALID SOURCE_PROTECTED SOURCE_NOT_AUDIO SOURCE_TOO_SHORT SOURCE_CHANGED SOURCE_NON_FINITE SOURCE_LEVEL SOURCE_TRIM_UNSUPPORTED SOURCE_OUTSIDE_INGEST1 SOURCE_CORRUPT JOIN_PEAK JOINED_PEAK DEST_EXISTS DEST_APPEARED DEST_NAME_INVALID'.split()
I1='IO_SOURCE IO_FOLDER IO_DEST IO_MEMORY INTERNAL'.split()
M2='USAGE LABEL_INVALID LENGTH_INVALID WAV_INVALID DEVICE_OPEN_FAILED TOO_LONG WAV_TRUNCATED NOT_PROVISIONED P2_TOO_LARGE'.split()
M3='REFUSE_NOT_WHOLE_DEVICE REFUSE_NOT_REMOVABLE REFUSE_TOO_LARGE REFUSE_SYSTEM_DISK REFUSE_FOREIGN_MOUNT REFUSE_ERASE_NOT_CONFIRMED'.split()
M1='ENGINE IO VERIFY_FINDINGS CARD_CHANGED'.split()
IDS={'ingest':{1:I1,2:I2},'tapectl cards':{1:['CARDS_ENUM_UNAVAILABLE'],2:['USAGE']},'tapectl make':{1:M1,2:M2,3:M3}}
CONTENT=set('SOURCE_NOT_AUDIO ENTRY_NOT_REGULAR ENTRY_NESTED_FOLDER ENTRY_SYMLINK FOLDER_SYMLINK FOLDER_EMPTY'.split())
UNUSABLE=set('SOURCE_CORRUPT SOURCE_OUTSIDE_INGEST1 SOURCE_TRIM_UNSUPPORTED SOURCE_LEVEL SOURCE_NON_FINITE IO_SOURCE SOURCE_TOO_SHORT SOURCE_CHANGED ENTRY_NAME_INVALID FOLDER_NAME_COLLISION FOLDER_NAME_NOT_UNICODE'.split())

def integer(x):
    assert type(x) is int and 0<=x<=LIMIT,'counter'
    return x

def obj(pairs):
    assert len({k for k,v in pairs})==len(pairs),'duplicate key'
    return dict(pairs)

def compact(line):
    # JSON escaping is not pinned; only insignificant whitespace is forbidden.
    quoted=False;escaped=False
    for c in line:
        if quoted:
            if escaped:escaped=False
            elif c=='\\':escaped=True
            elif c=='"':quoted=False
        elif c=='"':quoted=True
        elif c in ' \t\r\n':return False
    return True

def exact_keys(r,required,optional=()):
    assert list(r)[:len(required)]==list(required),'key order'
    assert set(r)<=set(required)|set(optional) and set(required)<=set(r),'keys'

def logical(s,folders):
    assert isinstance(s,str) and '/' in s,'logical path'
    o,n=s.split('/',1);ordinal(o,folders)
    assert n and n not in ('.','..') and '/' not in n and '\\' not in n and '\x00' not in n
    assert unicodedata.normalize('NFC',n)==n
    return o,n

def ordinal(o,folders):
    assert isinstance(o,str) and re.fullmatch('0|[1-9][0-9]*',o) and int(o)<len(folders),'ordinal'

def excess(r):
    a,b,e=[integer(r[k]) for k in ('total_frames','capacity_frames','excess_frames')]
    assert e==a-b and e>=1,'excess arithmetic'
    return (e+44099)//44100

def refusal(r,tool,exit,folders):
    assert r.get('id') in IDS[tool].get(exit,[]),'closed ID/exit'
    id=r['id'];s=r.get('subject');payload=[];optional=[]
    if tool=='ingest':
        if id.startswith(('SOURCE_','ENTRY_')) or id=='IO_SOURCE':logical(s,folders)
        elif id.startswith('FOLDER_') or id=='IO_FOLDER':ordinal(s,folders)
        elif id=='JOIN_PEAK':
            assert isinstance(s,list) and len(s)==2
            for v in s:logical(v,folders)
            assert s[0]!=s[1]
        elif id=='JOINED_PEAK':
            if s is not None:
                assert isinstance(s,list) and len(s)==2
                for v in s:logical(v,folders)
        else:assert s is None,'null subject'
        if id=='FOLDER_DUPLICATE':
            payload=['same_as'];ordinal(r['same_as'],folders);assert int(r['same_as'])<int(s)
        if id in ('JOIN_PEAK','JOINED_PEAK'):
            payload=['dbtp'];assert isinstance(r.get('dbtp'),str) and re.fullmatch(r'-?[0-9]+\.[0-9]{6}',r['dbtp'])
    else:assert s is None,'null subject'
    if id in ('INGEST_TOO_LONG','TOO_LONG'):
        payload=['total_frames','capacity_frames','excess_frames'];excess(r)
    if tool=='tapectl cards' and id=='CARDS_ENUM_UNAVAILABLE':payload=['os_error']
    if tool=='tapectl make':
        if id in ('DEVICE_OPEN_FAILED','CARD_CHANGED'):payload=['os_error'] if id=='DEVICE_OPEN_FAILED' else ['phase','os_error']
        if id=='WAV_INVALID':payload=['reason'];assert r.get('reason') in 'open riff fmt pcm channels rate bits align data chunk'.split()
        if id=='WAV_TRUNCATED':payload=['phase'];assert r.get('phase')=='load'
        if id=='ENGINE':
            payload=['phase','result'];assert r.get('phase') in ('provision','capacity','load','commit')
            assert r.get('result') in ERRORS
        if id=='IO':
            payload=['phase','op'];assert (r.get('phase'),r.get('op')) in {('provision',x) for x in ['entropy','read_lba0','clear_lba0','write_p1','build_mbr','write_mbr']}|{('verify','read_lba0')}
        if id=='CARD_CHANGED':assert r.get('phase') in ('safety','provision','load','commit','verify')
        if id=='REFUSE_FOREIGN_MOUNT':
            optional=['unmount_failed']
            if 'unmount_failed' in r:assert r['unmount_failed'] is True
        if id=='VERIFY_FINDINGS':payload=['findings'];findings(r.get('findings'))
    if 'os_error' in payload:assert isinstance(r.get('os_error'),str)
    exact_keys(r,['t','id','subject']+payload,optional)

def findings(fs):
    assert isinstance(fs,list) and fs
    order=['MBR_LAYOUT','PARTITION_TYPE','PARTITION_TRUNCATED','MOUNT','NEEDS_REPAIR','SIDE_B_DEGRADED','READ_ERROR']
    seen_read={};mount=set();last_read_side=0;last_mount_side=0;last_rank=-1;singletons=set()
    for f in fs:
        assert isinstance(f,dict) and f.get('f') in order
        n=f['f'];extra=['side','result'] if n=='MOUNT' else ['side','frame'] if n=='READ_ERROR' else []
        exact_keys(f,['f']+extra)
        rank=order.index(n);assert rank>=last_rank;last_rank=rank
        if n not in ('MOUNT','READ_ERROR'):assert n not in singletons;singletons.add(n)
        if n in ('MOUNT','READ_ERROR'):
            assert f['side'] in ('A','B');side='AB'.index(f['side'])
            if n=='MOUNT':
                assert f['result'] in ERRORS and f['side'] not in mount
                assert side>=last_mount_side;last_mount_side=side;mount.add(f['side'])
            else:
                assert side>=last_read_side;last_read_side=side
                assert f['side'] not in mount;v=integer(f['frame']);assert v>seen_read.get(f['side'],-1);seen_read[f['side']]=v

def parse(data,tool,version,nonce,exit,folders=()):
    """None means no ID-specific selector, not a changed actual exit."""
    try:
        assert tool in STEPS and re.fullmatch('[0-9a-f]{32}',nonce)
        text=data.decode('utf-8');lines=text.split('\n')[:-1];assert lines
        rows=[]
        for line in lines:
            r=json.loads(line,object_pairs_hook=obj);assert isinstance(r,dict)
            assert compact(line)
            rows.append(r)
        exact_keys(rows[0],['t','tool','version','nonce'])
        assert rows[0]==dict(t='start',tool=tool,version=version,nonce=nonce)
        exact_keys(rows[-1],['t','exit']);assert rows[-1]==dict(t='end',exit=exit) and type(rows[-1]['exit']) is int
        previous=-1;counts={};terminal=None;diagnostics=[]
        for r in rows[1:-1]:
            t=r.get('t')
            if t=='progress':
                assert terminal is None;exact_keys(r,['t','step','done','total'])
                i=STEPS[tool].index(r['step']);assert i>=previous;previous=i
                d,v=integer(r['done']),integer(r['total']);assert v==0 or d<=v
                if i in counts:
                    a,b=counts[i];assert d>=a and (v==b or b==0 and v>0)
                counts[i]=(d,v)
            elif t=='stderr':
                assert tool=='tapectl make';exact_keys(r,['t','text']);assert isinstance(r['text'],str) and '\n' not in r['text'];diagnostics.append(r['text'])
            elif t=='refusal':assert terminal is None;refusal(r,tool,exit,folders);terminal=r
            else:raise AssertionError('unknown/order')
        assert exit!=0 or terminal is None
        return {'refusal':terminal,'diagnostics':diagnostics}
    except (AssertionError,KeyError,ValueError,TypeError,UnicodeError,OverflowError):return None

def message(tool,exit,parsed,pair=False):
    # Category plus structured facts; rendering actual default copy is separately checked.
    if exit==0:return ('success',None) if tool!='ingest' or pair else ('generic',None)
    r=parsed['refusal'] if parsed else None
    if not r:return ('make-generic' if tool=='tapectl make' else 'generic',None)
    id=r['id']
    if tool=='ingest':
        if id=='INGEST_TOO_LONG':return ('overage',excess(r))
        if id=='SOURCE_PROTECTED':return ('protected',r['subject'])
        if id in CONTENT:return ('folder-nonmusic',r['subject'])
        if id in UNUSABLE:return ('unusable',r['subject'])
        return ('generic',None)
    if tool=='tapectl make':
        if id=='TOO_LONG' or id=='ENGINE' and r['phase']=='provision' and r['result']=='TAPE_ERR_GEOMETRY':return ('card-small',None)
        if id in ('CARD_CHANGED','DEVICE_OPEN_FAILED') or id=='IO' and r['op'] not in ('entropy','build_mbr') or id=='ENGINE' and r['result']=='TAPE_ERR_IO':return ('card-interrupted',None)
        if id=='VERIFY_FINDINGS':return ('verify-finding',None)
        if id=='WAV_TRUNCATED':return ('music-changed',None)
        if exit==3:return ('card-refused',None)
        return ('make-generic',None)
    return ('generic',None)

def candidate(f):
    """OS fact predicate only. This never authorizes destructive access."""
    required=['whole','removable_or_sd','nonvirtual','bytes','not_system_boot_swap','mounts']
    if any(f.get(k) is None for k in required):return 'unprobed'
    if not all(f[k] for k in ('whole','removable_or_sd','nonvirtual','not_system_boot_swap')):return 'refused'
    if type(f['bytes']) is not int or f['bytes']<=0:return 'unprobed'
    if f['bytes']>2**37:return 'refused'
    if not f['mounts']:return 'candidate'
    if f.get('partition_view') is None:return 'unprobed'
    p=f['partition_view'];wanted={'style':'MBR','p1_type':14,'p1_start':2048,'p1_sectors':32768,'p2_type':218,'p2_start':34816,'p2_end_bytes':f['bytes'],'p3':False,'p4':False}
    if any(p.get(k) is None for k in wanted):return 'unprobed'
    return 'candidate' if all(p[k]==v for k,v in wanted.items()) and f['mounts']==[1] else 'refused'

def label_append(old,addition):
    new=old+addition
    try:return new if len(new.encode('utf-8'))<=32 and '\x00' not in new else old
    except UnicodeError:return old
