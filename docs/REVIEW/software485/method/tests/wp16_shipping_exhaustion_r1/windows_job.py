"""Independent Windows launcher: limit the actual shipping child before its first instruction.

Native DWORD status is retained (not translated to exit1). No observation allocator.
Microsoft: JOBOBJECT_EXTENDED_LIMIT_INFORMATION / CreateProcessW / AssignProcessToJobObject.
"""
import ctypes as C, subprocess, time, os
from ctypes import wintypes as W

def run(argv, limit, stdout, stderr, cwd):
    import msvcrt
    K=C.WinDLL('kernel32',use_last_error=True)
    SIZE=C.c_size_t; U64=C.c_ulonglong
    class BASIC(C.Structure):
        _fields_=[('ProcessTime',C.c_longlong),('JobTime',C.c_longlong),('Flags',W.DWORD),('MinWS',SIZE),('MaxWS',SIZE),('Active',W.DWORD),('Affinity',SIZE),('Priority',W.DWORD),('Scheduling',W.DWORD)]
    class IO(C.Structure):_fields_=[(n,U64) for n in ['ReadOps','WriteOps','OtherOps','ReadBytes','WriteBytes','OtherBytes']]
    class EXT(C.Structure):_fields_=[('Basic',BASIC),('IO',IO),('ProcessMemory',SIZE),('JobMemory',SIZE),('PeakProcess',SIZE),('PeakJob',SIZE)]
    class START(C.Structure):
        _fields_=[('cb',W.DWORD),('Reserved',W.LPWSTR),('Desktop',W.LPWSTR),('Title',W.LPWSTR)]+[(n,W.DWORD) for n in ['X','Y','XSize','YSize','XChars','YChars','Fill','Flags']]+[('Show',W.WORD),('Reserved2Size',W.WORD),('Reserved2',C.POINTER(W.BYTE)),('In',W.HANDLE),('Out',W.HANDLE),('Err',W.HANDLE)]
    class PROC(C.Structure):_fields_=[('Process',W.HANDLE),('Thread',W.HANDLE),('PID',W.DWORD),('TID',W.DWORD)]
    signatures={
      'CreateJobObjectW':([W.LPVOID,W.LPCWSTR],W.HANDLE),
      'SetInformationJobObject':([W.HANDLE,C.c_int,W.LPVOID,W.DWORD],W.BOOL),
      'AssignProcessToJobObject':([W.HANDLE,W.HANDLE],W.BOOL),
      'CreateProcessW':([W.LPCWSTR,W.LPWSTR,W.LPVOID,W.LPVOID,W.BOOL,W.DWORD,W.LPVOID,W.LPCWSTR,C.POINTER(START),C.POINTER(PROC)],W.BOOL),
      'ResumeThread':([W.HANDLE],W.DWORD), 'WaitForSingleObject':([W.HANDLE,W.DWORD],W.DWORD),
      'GetExitCodeProcess':([W.HANDLE,C.POINTER(W.DWORD)],W.BOOL),
      'TerminateJobObject':([W.HANDLE,W.UINT],W.BOOL),'CloseHandle':([W.HANDLE],W.BOOL)}
    for n,(a,r) in signatures.items():getattr(K,n).argtypes=a;getattr(K,n).restype=r
    def check(ok):
        if not ok:raise C.WinError(C.get_last_error())
    job=K.CreateJobObjectW(None,None);check(job)
    pi=PROC();started=False
    try:
        info=EXT();info.Basic.Flags=0x2000 # kill children on final Job handle close
        if limit is not None:info.Basic.Flags|=0x100;info.ProcessMemory=limit
        check(K.SetInformationJobObject(job,9,C.byref(info),C.sizeof(info)))
        with open(os.devnull,'rb') as inp,open(stdout,'wb') as out,open(stderr,'wb') as err:
            handles=[msvcrt.get_osfhandle(f.fileno()) for f in [inp,out,err]]
            for h in handles:os.set_handle_inheritable(h,True)
            si=START();si.cb=C.sizeof(si);si.Flags=0x100;si.In,si.Out,si.Err=handles
            cmd=C.create_unicode_buffer(subprocess.list2cmdline([str(x) for x in argv]))
            t=time.monotonic()
            check(K.CreateProcessW(str(argv[0]),cmd,None,None,True,0x4,None,str(cwd),C.byref(si),C.byref(pi)));started=True
            check(K.AssignProcessToJobObject(job,pi.Process))
            if K.ResumeThread(pi.Thread)==0xffffffff:raise C.WinError(C.get_last_error())
            wait=K.WaitForSingleObject(pi.Process,30000);timed_out=wait==258
            if timed_out:check(K.TerminateJobObject(job,1460));check(K.WaitForSingleObject(pi.Process,5000)==0)
            elif wait!=0:raise C.WinError(C.get_last_error())
            code=W.DWORD();check(K.GetExitCodeProcess(pi.Process,C.byref(code)))
            return dict(exit=code.value,exit_hex=f'0x{code.value:08X}',timed_out=timed_out,seconds=time.monotonic()-t,method='Windows Job PROCESS_MEMORY, suspended assignment')
    finally:
        # Closing the Job kills a child if setup fails after process creation.
        K.CloseHandle(job)
        if started:K.CloseHandle(pi.Thread);K.CloseHandle(pi.Process)
