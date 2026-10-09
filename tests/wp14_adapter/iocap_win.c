/*
 * iocap_win.c — external OS-call capture for the SHIPPED tapectl.exe
 * (WP-14 binding, Product #392). Test transport only; never linked into tapectl.
 *
 * Built twice:
 *   -DIOCAP_DLL   iocap.dll: on load, patches the main module's import table
 *                 for CreateFileW, ReadFile, WriteFile, FlushFileBuffers and
 *                 DeviceIoControl, so each call is logged to IOCAP_LOG and
 *                 forwarded unchanged; results are returned unchanged.
 *   (default)     iocap.exe launcher: iocap.exe DLL TARGET [ARGS...] starts
 *                 TARGET suspended, loads the DLL into it, resumes it, waits,
 *                 and exits with TARGET's exit code.
 *
 * One JSON object per line:
 *   {"call":"open","path":...,"access":a,"write":bool,"handle":h,"error":e}
 *   {"call":"pread"|"pwrite","handle":h,"offset":o,"bytes":b,"ok":bool,"done":n,"error":e}
 *   {"call":"flush","handle":h,"ok":bool,"error":e}
 */

#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <wchar.h>

#ifdef IOCAP_DLL

static HANDLE (WINAPI *real_CreateFileW)(LPCWSTR, DWORD, DWORD, LPSECURITY_ATTRIBUTES, DWORD, DWORD, HANDLE);
static BOOL (WINAPI *real_ReadFile)(HANDLE, LPVOID, DWORD, LPDWORD, LPOVERLAPPED);
static BOOL (WINAPI *real_WriteFile)(HANDLE, LPCVOID, DWORD, LPDWORD, LPOVERLAPPED);
static BOOL (WINAPI *real_FlushFileBuffers)(HANDLE);

static void logline(const char *fmt, ...)
{
    char path[1024];
    DWORD saved = GetLastError();
    FILE *fp;
    va_list ap;
    if (GetEnvironmentVariableA("IOCAP_LOG", path, sizeof path) == 0) { SetLastError(saved); return; }
    fp = fopen(path, "a");
    if (fp == NULL) { SetLastError(saved); return; }
    va_start(ap, fmt);
    vfprintf(fp, fmt, ap);
    va_end(ap);
    fputc('\n', fp);
    fclose(fp);
    SetLastError(saved);
}

static unsigned long long ov_offset(LPOVERLAPPED ov)
{
    return ov ? ((unsigned long long)ov->OffsetHigh << 32) | ov->Offset : 0ull;
}

static HANDLE WINAPI cap_CreateFileW(LPCWSTR name, DWORD access, DWORD share, LPSECURITY_ATTRIBUTES sa,
                                     DWORD disp, DWORD flags, HANDLE tmpl)
{
    HANDLE h = real_CreateFileW(name, access, share, sa, disp, flags, tmpl);
    DWORD err = h == INVALID_HANDLE_VALUE ? GetLastError() : 0;
    char utf8[1024], esc[2048];
    size_t i, j = 0;
    WideCharToMultiByte(CP_UTF8, 0, name, -1, utf8, sizeof utf8, NULL, NULL);
    for (i = 0; utf8[i] && j < sizeof esc - 2; i++) {
        if (utf8[i] == '"' || utf8[i] == '\\') { esc[j++] = '\\'; }
        esc[j++] = utf8[i];
    }
    esc[j] = '\0';
    logline("{\"call\":\"open\",\"path\":\"%s\",\"access\":%lu,\"write\":%s,\"handle\":%llu,\"error\":%lu}",
            esc, (unsigned long)access, (access & (GENERIC_WRITE | FILE_WRITE_DATA | GENERIC_ALL)) ? "true" : "false",
            (unsigned long long)(ULONG_PTR)h, (unsigned long)err);
    SetLastError(err);
    return h;
}

static BOOL WINAPI cap_ReadFile(HANDLE h, LPVOID buf, DWORD n, LPDWORD got, LPOVERLAPPED ov)
{
    BOOL ok = real_ReadFile(h, buf, n, got, ov);
    DWORD err = ok ? 0 : GetLastError();
    logline("{\"call\":\"pread\",\"handle\":%llu,\"offset\":%llu,\"bytes\":%lu,\"ok\":%s,\"done\":%lu,\"error\":%lu}",
            (unsigned long long)(ULONG_PTR)h, ov_offset(ov), (unsigned long)n, ok ? "true" : "false",
            (unsigned long)(got ? *got : 0), (unsigned long)err);
    SetLastError(err);
    return ok;
}

static BOOL WINAPI cap_WriteFile(HANDLE h, LPCVOID buf, DWORD n, LPDWORD got, LPOVERLAPPED ov)
{
    BOOL ok = real_WriteFile(h, buf, n, got, ov);
    DWORD err = ok ? 0 : GetLastError();
    logline("{\"call\":\"pwrite\",\"handle\":%llu,\"offset\":%llu,\"bytes\":%lu,\"ok\":%s,\"done\":%lu,\"error\":%lu}",
            (unsigned long long)(ULONG_PTR)h, ov_offset(ov), (unsigned long)n, ok ? "true" : "false",
            (unsigned long)(got ? *got : 0), (unsigned long)err);
    SetLastError(err);
    return ok;
}

static BOOL WINAPI cap_FlushFileBuffers(HANDLE h)
{
    BOOL ok = real_FlushFileBuffers(h);
    DWORD err = ok ? 0 : GetLastError();
    logline("{\"call\":\"flush\",\"handle\":%llu,\"ok\":%s,\"error\":%lu}", (unsigned long long)(ULONG_PTR)h,
            ok ? "true" : "false", (unsigned long)err);
    SetLastError(err);
    return ok;
}

/* Patch the main module's IAT entry for `name` in KERNEL32.dll. */
static int patch(const char *name, void *repl, void **orig)
{
    HMODULE base = GetModuleHandleW(NULL);
    IMAGE_DOS_HEADER *dos = (IMAGE_DOS_HEADER *)base;
    IMAGE_NT_HEADERS *nt = (IMAGE_NT_HEADERS *)((BYTE *)base + dos->e_lfanew);
    IMAGE_DATA_DIRECTORY dir = nt->OptionalHeader.DataDirectory[IMAGE_DIRECTORY_ENTRY_IMPORT];
    IMAGE_IMPORT_DESCRIPTOR *imp = (IMAGE_IMPORT_DESCRIPTOR *)((BYTE *)base + dir.VirtualAddress);
    int patched = 0;
    for (; imp->Name; imp++) {
        IMAGE_THUNK_DATA *names = (IMAGE_THUNK_DATA *)((BYTE *)base + (imp->OriginalFirstThunk ? imp->OriginalFirstThunk : imp->FirstThunk));
        IMAGE_THUNK_DATA *addrs = (IMAGE_THUNK_DATA *)((BYTE *)base + imp->FirstThunk);
        for (; names->u1.AddressOfData; names++, addrs++) {
            IMAGE_IMPORT_BY_NAME *ibn;
            DWORD old;
            if (IMAGE_SNAP_BY_ORDINAL(names->u1.Ordinal)) { continue; }
            ibn = (IMAGE_IMPORT_BY_NAME *)((BYTE *)base + names->u1.AddressOfData);
            if (strcmp((const char *)ibn->Name, name) != 0) { continue; }
            if (*orig == NULL) { *orig = (void *)addrs->u1.Function; }
            VirtualProtect(&addrs->u1.Function, sizeof addrs->u1.Function, PAGE_READWRITE, &old);
            addrs->u1.Function = (ULONG_PTR)repl;
            VirtualProtect(&addrs->u1.Function, sizeof addrs->u1.Function, old, &old);
            patched++;
        }
    }
    return patched;
}

BOOL WINAPI DllMain(HINSTANCE inst, DWORD reason, LPVOID reserved)
{
    (void)inst; (void)reserved;
    if (reason == DLL_PROCESS_ATTACH) {
        int n = 0;
        n += patch("CreateFileW", (void *)cap_CreateFileW, (void **)&real_CreateFileW);
        n += patch("ReadFile", (void *)cap_ReadFile, (void **)&real_ReadFile);
        n += patch("WriteFile", (void *)cap_WriteFile, (void **)&real_WriteFile);
        n += patch("FlushFileBuffers", (void *)cap_FlushFileBuffers, (void **)&real_FlushFileBuffers);
        logline("{\"call\":\"iocap_attach\",\"patched\":%d}", n);
    }
    return TRUE;
}

#else /* launcher */

int wmain(int argc, wchar_t **argv)
{
    STARTUPINFOW si;
    PROCESS_INFORMATION pi;
    wchar_t cmd[32768];
    size_t used = 0;
    int i;
    void *remote;
    HANDLE th;
    DWORD code = 99;
    size_t dll_bytes;

    if (argc < 3) { fwprintf(stderr, L"usage: iocap.exe DLL TARGET [ARGS...]\n"); return 99; }
    cmd[0] = L'\0';
    for (i = 2; i < argc; i++) {
        /* Quote every argument (CommandLineToArgvW rules for plain arguments). */
        used += (size_t)swprintf(cmd + used, 32768 - used, L"%s\"%ls\"", i > 2 ? L" " : L"", argv[i]);
    }
    memset(&si, 0, sizeof si);
    si.cb = sizeof si;
    if (!CreateProcessW(argv[2], cmd, NULL, NULL, TRUE, CREATE_SUSPENDED, NULL, NULL, &si, &pi)) {
        fwprintf(stderr, L"iocap: CreateProcess failed %lu\n", GetLastError());
        return 99;
    }
    dll_bytes = (wcslen(argv[1]) + 1) * sizeof(wchar_t);
    remote = VirtualAllocEx(pi.hProcess, NULL, dll_bytes, MEM_COMMIT, PAGE_READWRITE);
    if (remote == NULL || !WriteProcessMemory(pi.hProcess, remote, argv[1], dll_bytes, NULL)) {
        fwprintf(stderr, L"iocap: cannot write DLL path %lu\n", GetLastError());
        TerminateProcess(pi.hProcess, 99);
        return 99;
    }
    th = CreateRemoteThread(pi.hProcess, NULL, 0,
                            (LPTHREAD_START_ROUTINE)(void *)GetProcAddress(GetModuleHandleW(L"kernel32.dll"), "LoadLibraryW"),
                            remote, 0, NULL);
    if (th == NULL) {
        fwprintf(stderr, L"iocap: CreateRemoteThread failed %lu\n", GetLastError());
        TerminateProcess(pi.hProcess, 99);
        return 99;
    }
    WaitForSingleObject(th, INFINITE);
    GetExitCodeThread(th, &code);
    CloseHandle(th);
    if (code == 0) {
        fwprintf(stderr, L"iocap: LoadLibrary failed in target\n");
        TerminateProcess(pi.hProcess, 99);
        return 99;
    }
    ResumeThread(pi.hThread);
    WaitForSingleObject(pi.hProcess, INFINITE);
    GetExitCodeProcess(pi.hProcess, &code);
    CloseHandle(pi.hThread);
    CloseHandle(pi.hProcess);
    return (int)code;
}

#endif
