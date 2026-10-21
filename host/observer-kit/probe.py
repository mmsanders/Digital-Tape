"""Preparation-only launchable probe image; future native payload is dormant.

No Windows FFI is imported or bound by dry-run/validation. A dormant future-entry
branch requires separately issued scope; it is never invoked by preparation.
"""
import argparse
import hashlib
import json
import ntpath
import os
from pathlib import Path
import re
import struct
import sys
import time

OBSERVER='28495e642b2a465474a4edc58380eaf8b7ee580f3fbcb4141061deadafe9b885'
FILTER='6bc51ab36ed855ef86a903808d899ab349827122db04b7e0bb13fe285adc2f74'
ROWS=[('file-read','owned',0x80000000),('file-zero','owned',0),('missing-read','missing',0x80000000),
      ('nul-zero','nul',0),('nul-read','nul',0x80000000),('absent-dos-zero','absent',0)]
FLAGS=('source_bound','runtime_bound','abi_windows_unicode_pointer_correct','immediate_error',
       'success_error_ignored','clock_pid_nonce_contract','owned_cleanup_only',
       'private_archive_contract','future_commands_not_authorized','fresh_authorization_required')


def validate(config):
    if config.get('mode')!='PREPARATION_ONLY' or config.get('synthetic') is not True:
        raise ValueError('preparation/synthetic labels required')
    for key in ('native_calls','token_probes','capture_launches'):
        if type(config.get(key)) is not int or config[key]!=0:raise ValueError('nonzero '+key)
    if config.get('helper_image')!='probe-235.exe' or config.get('pointer_bits') not in (32,64):
        raise ValueError('helper image/pointer width mismatch')
    if config.get('observer_sha256')!=OBSERVER or config.get('filter_sha256')!=FILTER:
        raise ValueError('observer/filter must remain pinned')
    if any(config.get(key) is not True for key in FLAGS):raise ValueError('missing provenance/stop obligation')
    if not re.fullmatch('[0-9a-f]{32}',config.get('nonce','')):raise ValueError('nonce')
    if config.get('owned')!=r'C:\owned\fixture.bin' or config.get('missing')!=r'C:\owned\missing.bin':
        raise ValueError('fixed synthetic owned paths')
    expected=[]
    for name,target,access in ROWS:
        path=config['owned'] if target=='owned' else config['missing'] if target=='missing' else r'\\.\NUL' if target=='nul' else '\\\\.\\DTVerify235_'+config['nonce']
        expected.append(dict(id=name,path=path,access=access,share=7,disposition=3,flags=128,
                             security_null=True,template_null=True,attempts=1))
    if config.get('cases')!=expected:raise ValueError('exact six-template allowlist mismatch')
    return 'SYNTHETIC_READINESS_CONTROLS_ONLY'


def future_target(case, root, nonce):
    """Pure string validation BEFORE any FFI binding. No filesystem assertions."""
    if not re.fullmatch('[0-9a-f]{32}',nonce):raise ValueError('nonce')
    if not re.fullmatch(r'[A-Za-z]:\\[^:*?"<>|]+',root) or root.startswith('\\\\') or ntpath.normpath(root)!=root or '..' in root.split('\\'):
        raise ValueError('canonical ordinary local owned root required')
    known={name:(target,access) for name,target,access in ROWS}
    if case['id'] not in known:raise ValueError('unknown case')
    kind,access=known[case['id']]
    expected=ntpath.join(root,'fixture.bin') if kind=='owned' else ntpath.join(root,'missing.bin') if kind=='missing' else r'\\.\NUL' if kind=='nul' else '\\\\.\\DTVerify235_'+nonce
    wanted=dict(id=case['id'],path=expected,access=access,share=7,disposition=3,flags=128,
                security_null=True,template_null=True,attempts=1)
    if case!=wanted:raise ValueError('unissued target/parameters')
    return kind


def retain_call(operation, clocks, close, sink, identity):
    """Shared pure retention sequencing, also exercised with NO-NATIVE callbacks.

    operation captures any immediate error BEFORE returning. The first subsequent
    sink preserves those original facts. Later clock/close failures append their
    own incomplete diagnostics; they never replace the native event or retry close.
    """
    before=clocks()
    native=operation()
    result=dict(identity=identity,before=before,native=native,status='incomplete')
    try:
        sink(dict(kind='native-original',identity=identity,before=before,native=native))
        try:
            result['after']=clocks()
            sink(dict(kind='post-clock',after=result['after']))
            result['status']='complete'
        except Exception as error:
            result['clock_error']=str(error)
            sink(dict(kind='incomplete-clock',error=str(error)))
    finally:
        if native.get('valid_owned_handle') is True:
            try:
                result['close']=close(native['handle_raw'])
                sink(dict(kind='close-original',fact=result['close']))
                if not result['close']['success']:result['status']='incomplete'
            except Exception as error:
                result['status']='incomplete';result['close_error']=str(error)
                sink(dict(kind='incomplete-close',error=str(error),close_attempts=1))
    sink(dict(kind='completion',status=result['status']))
    return result


def validate_query_receipt(receipt, session, nonce, receipt_sha256):
    """Pure binding/order check. Actual evidence is required by the future runner."""
    if receipt_sha256!=session.get('query_receipt_sha256'):raise ValueError('unbound query receipt hash')
    identity=receipt['identity'];native=receipt['native']
    if receipt.get('status')!='complete' or identity.get('operation')!='absence-query':raise ValueError('incomplete/wrong query')
    if identity.get('nonce')!=nonce or session.get('nonce')!=nonce or identity.get('session_instance')!=session.get('session_instance'):
        raise ValueError('stale nonce/session query')
    if identity.get('source_sha256')!=session.get('payload_source_sha256') or identity.get('image_sha256')!=session.get('probe_image_sha256'):
        raise ValueError('unbound query payload/image')
    if native.get('name')!='DTVerify235_'+nonce or native.get('buffer_wchars')!=4096 or native.get('returned')!=0 or native.get('immediate_error')!=2:
        raise ValueError('exact one-name absence not established')
    before=receipt['before']['qpc'];after=receipt['after']['qpc']
    if not session['session_start_qpc']<=before<=after<session['capture_start_qpc']:
        raise ValueError('query stale or not before capture')
    if identity.get('qpc_frequency')!=session.get('qpc_frequency') or identity['qpc_frequency']<=0:
        raise ValueError('query clock frequency mismatch')
    return receipt


def future_native_payload(case, root, nonce, authorized_session, facts_path, query_receipt=None,
                          query_receipt_sha256=None, query_only=False):
    """NOT CALLED by this kit. Requires separately issued future integration.

    Source is auditable ABI preparation; this dormant routine alone is not an
    authorized capture session. The current task never invokes this branch.
    """
    kind=future_target(case,root,nonce)
    if authorized_session.get('fresh_scope') is not True or authorized_session.get('owned_instance') is not True:
        raise ValueError('fresh scope and already-authorized owned session required')
    # Actual future filesystem non-reparse/identity checks MUST already have been
    # independently bound by that separately issued runner, not by synthetic data.
    if authorized_session.get('actual_filesystem_identity_bound') is not True:
        raise ValueError('actual owned filesystem prerequisites missing')
    import ctypes  # Dormant until separately integrated; dry-run never imports it.
    from ctypes import wintypes
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    HANDLE=ctypes.c_void_p;DWORD=ctypes.c_uint32;BOOL=ctypes.c_int32
    kernel.CreateFileW.argtypes=[ctypes.c_wchar_p,DWORD,DWORD,ctypes.c_void_p,DWORD,DWORD,HANDLE]
    kernel.CreateFileW.restype=HANDLE
    kernel.CloseHandle.argtypes=[HANDLE];kernel.CloseHandle.restype=BOOL
    kernel.QueryDosDeviceW.argtypes=[ctypes.c_wchar_p,ctypes.c_wchar_p,DWORD]
    kernel.QueryDosDeviceW.restype=DWORD
    kernel.GetCurrentThreadId.argtypes=[];kernel.GetCurrentThreadId.restype=DWORD
    kernel.QueryPerformanceCounter.argtypes=[ctypes.POINTER(ctypes.c_int64)]
    kernel.QueryPerformanceCounter.restype=BOOL
    kernel.QueryPerformanceFrequency.argtypes=[ctypes.POINTER(ctypes.c_int64)]
    kernel.QueryPerformanceFrequency.restype=BOOL
    class FileTime(ctypes.Structure):
        _fields_=[('low',DWORD),('high',DWORD)]
    kernel.GetSystemTimePreciseAsFileTime.argtypes=[ctypes.POINTER(FileTime)]
    kernel.GetSystemTimePreciseAsFileTime.restype=None
    if ctypes.sizeof(DWORD)!=4 or ctypes.sizeof(BOOL)!=4 or ctypes.sizeof(HANDLE)*8 not in (32,64):
        raise ValueError('ABI width mismatch')
    # Opening this fresh ordinary owned facts stream precedes any target/query.
    # The separately issued runner must authenticate non-reparse filesystem facts.
    if ntpath.dirname(str(facts_path))!=root:raise ValueError('facts must be fresh within actual bound owned root')
    query=None
    if not query_only:
        query=validate_query_receipt(query_receipt,authorized_session,nonce,query_receipt_sha256)
    frequency=ctypes.c_int64();tid=kernel.GetCurrentThreadId()
    if not kernel.QueryPerformanceFrequency(ctypes.byref(frequency)) or frequency.value<=0:raise RuntimeError('QPC frequency unavailable')
    def clocks():
        ft=FileTime();qpc=ctypes.c_int64()
        kernel.GetSystemTimePreciseAsFileTime(ctypes.byref(ft))
        if not kernel.QueryPerformanceCounter(ctypes.byref(qpc)):
            error=ctypes.get_last_error()  # Original clock failure diagnostic before later work.
            raise RuntimeError('QPC unavailable; immediate_error='+str(error))
        return dict(filetime=(ft.high<<32)|ft.low,qpc=qpc.value)
    invalid=(1<<(ctypes.sizeof(HANDLE)*8))-1
    image=Path(sys.executable).resolve()
    identity=dict(case=case,nonce=nonce,marker=nonce+':'+('absence-query' if query_only else case['id']),
        operation='absence-query' if query_only else 'CreateFileW',session_instance=authorized_session['session_instance'],
        pid=os.getpid(),parent_pid=os.getppid(),tid=tid,qpc_frequency=frequency.value,
        source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),image=str(image),
        image_sha256=hashlib.sha256(image.read_bytes()).hexdigest(),
        target_utf16le=case['path'].encode('utf-16le').hex(),handle_bits=ctypes.sizeof(HANDLE)*8,
        absence_query=query,query_receipt_sha256=query_receipt_sha256,filetime_unit_ns=100,
        qpc_tick_seconds=1/frequency.value,
        utc_offset_seconds=-(time.altzone if time.daylight and time.localtime().tm_isdst else time.timezone))
    def operation():
        if query_only:
            if kind!='absent':raise ValueError('only issued generated absent name can be queried')
            name='DTVerify235_'+nonce;buffer=ctypes.create_unicode_buffer(4096)
            count=kernel.QueryDosDeviceW(name,buffer,4096)  # ONE pre-capture query only.
            error=ctypes.get_last_error() if count==0 else None  # IMMEDIATE, before clock/log/close.
            return dict(name=name,buffer_wchars=4096,returned=count,immediate_error=error,valid_owned_handle=False)
        handle=kernel.CreateFileW(case['path'],case['access'],7,None,3,128,None)
        raw=int(handle) if handle is not None else 0
        error=ctypes.get_last_error() if raw==invalid else None  # IMMEDIATE failure capture.
        return dict(handle_raw=raw,invalid_handle=raw==invalid,immediate_error=error,valid_owned_handle=raw!=invalid)
    def close(raw):
        success=bool(kernel.CloseHandle(HANDLE(raw)))  # Exactly once and valid only.
        error=ctypes.get_last_error() if not success else None  # IMMEDIATE close failure capture.
        return dict(success=success,immediate_error=error,attempts=1)
    with Path(facts_path).open('x',encoding='utf-8') as stream:
        def sink(event):
            stream.write(json.dumps(event,sort_keys=True)+'\n');stream.flush()
        result=retain_call(operation,clocks,close,sink,identity)
    if result['status']!='complete':raise RuntimeError('incomplete native facts retained at '+str(facts_path))
    if query_only and (result['native']['returned']!=0 or result['native']['immediate_error']!=2):
        raise RuntimeError('query failed absence prerequisite; original facts retained, stop before capture')
    return result


def main():
    p=argparse.ArgumentParser(description='PREPARATION ONLY; no collection CLI')
    p.add_argument('--dry-run',action='store_true')
    p.add_argument('--validate',type=Path)
    p.add_argument('--nonce',default='a'*32)
    p.add_argument('--future-execute',action='store_true',help='NOT AUTHORIZED in preparation; future separately issued scope only')
    p.add_argument('--future-query',action='store_true',help='NOT AUTHORIZED now; one exact future absence query BEFORE capture')
    p.add_argument('--query-receipt',type=Path)
    p.add_argument('--facts',type=Path)
    p.add_argument('--case-request',type=Path)
    p.add_argument('--authorized-session',type=Path)
    p.add_argument('--owned-root')
    p.add_argument('--marker')
    a=p.parse_args()
    if a.future_execute or a.future_query:
        if a.future_execute and a.future_query:p.error('query and case are separate future invocations')
        if a.future_execute and not a.query_receipt:p.error('original before-capture query receipt required for every case')
        if a.dry_run or a.validate or not all((a.case_request,a.authorized_session,a.owned_root,a.facts)):
            p.error('separate future scope/session and exact case request required')
        # File flags are operational prerequisites, not a grant of authority.
        # This branch must never be called by current preparation or dry-run tests.
        case=json.loads(a.case_request.read_bytes())
        session=json.loads(a.authorized_session.read_bytes())
        if a.marker!=a.nonce+':'+('absence-query' if a.future_query else case['id']):p.error('exact nonce:operation marker required')
        query_bytes=a.query_receipt.read_bytes() if a.query_receipt else None
        result=future_native_payload(case,a.owned_root,a.nonce,session,a.facts,
            json.loads(query_bytes) if query_bytes else None,
            hashlib.sha256(query_bytes).hexdigest() if query_bytes else None,query_only=a.future_query)
        image=Path(sys.executable).resolve()
        result.update(image=str(image),image_sha256=hashlib.sha256(image.read_bytes()).hexdigest(),
                      source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
        print(json.dumps(result,sort_keys=True));return 0
    if a.validate:
        try:print(validate(json.loads(a.validate.read_bytes())))
        except Exception as e:print(str(e),file=sys.stderr);return 2
        return 0
    if not a.dry_run:p.error('only --dry-run or --validate is available; collection NOT AUTHORIZED')
    if not re.fullmatch('[0-9a-f]{32}',a.nonce):p.error('nonce')
    image=Path(sys.executable).resolve()
    # Interpreter determines sys.executable from its actual image. The test driver
    # also binds the actual Popen argv/image file hash independently.
    result=dict(mode='ACTUAL_ORDINARY_DRY_RUN',synthetic_native_receipts=False,
                image=str(image),image_name=image.name,image_sha256=hashlib.sha256(image.read_bytes()).hexdigest(),
                source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                pid=os.getpid(),parent_pid=os.getppid(),nonce=a.nonce,instance_start_ns=time.time_ns(),
                pointer_bits=struct.calcsize('P')*8,python=sys.version,prefix=sys.prefix,
                ctypes_imported='ctypes' in sys.modules,native_target_calls=0,token_probes=0,capture_launches=0,
                collection_entry_point='future-execute gated and NOT AUTHORIZED; not invoked')
    if result['ctypes_imported']:raise RuntimeError('dry-run unexpectedly imported FFI')
    print(json.dumps(result,sort_keys=True));return 0


if __name__=='__main__':sys.exit(main())
