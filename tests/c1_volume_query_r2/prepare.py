"""Probe-only typed ERROR_NOT_READY control over a genuinely mounted hosted VHD.

The initial census and target identity come from real OS queries. Only the extent
response for a volume on that same target is replaced by the typed error21 input.
This is not a claim that Windows generated21 in this session or that a card was run.
The test reuses the already independent r1 positive/policy harness and VHD setup.
"""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
text=(root/'c1_volume_query_r1/probe.c').read_text()
start=text.index('static BOOL WINAPI controlled_paths(')
end=text.index('/* The Product error-name helper',start)
text=text[:start]+r'''
static DWORD selected_disk;
static BOOL WINAPI controlled_paths(LPCWSTR volume, LPWSTR names, DWORD cap, PDWORD needed)
{
    return GetVolumePathNamesForVolumeNameW(volume, names, cap, needed);
}
static BOOL WINAPI controlled_ioctl(HANDLE device, DWORD code, LPVOID input, DWORD insize,
                                    LPVOID output, DWORD outsize, LPDWORD returned, LPOVERLAPPED ov)
{
    if (fail_paths && code == IOCTL_VOLUME_GET_VOLUME_DISK_EXTENTS) {
        STORAGE_DEVICE_NUMBER number;
        DWORD got = 0;
        if (DeviceIoControl(device, IOCTL_STORAGE_GET_DEVICE_NUMBER, NULL, 0,
                            &number, sizeof number, &got, NULL)
            && number.DeviceType == FILE_DEVICE_DISK && number.DeviceNumber == selected_disk) {
            failed_calls++;
            actual_error = ERROR_NOT_READY; /* Typed failure, not a measured OS error. */
            SetLastError(ERROR_NOT_READY);
            return FALSE;
        }
    }
    return DeviceIoControl(device, code, input, insize, output, outsize, returned, ov);
}
''' + text[end:]
text=text.replace('#define GetVolumePathNamesForVolumeNameW controlled_paths',
                  '#define DeviceIoControl controlled_ioctl\n#define GetVolumePathNamesForVolumeNameW controlled_paths')
text=text.replace('#undef GetVolumePathNamesForVolumeNameW',
                  '#undef GetVolumePathNamesForVolumeNameW\n#undef DeviceIoControl')
needle='if (argc != 2) { return 2; }';assert text.count(needle)==1
text=text.replace(needle,needle+'\n    selected_disk = (DWORD)strtoul(argv[1] + 17, NULL, 10);')
assert text.count('actual_error != ERROR_MORE_DATA')==1
text=text.replace('actual_error != ERROR_MORE_DATA','actual_error != ERROR_NOT_READY')
text=text.replace('actual VHD probe; removable-policy model only; no raw writes',
                  'mounted VHD facts; typed ERROR_NOT_READY response; removable-policy model; no make')
text=text.replace('actual_os_error','typed_error_code')
text='/* GENERATED independent typed-error controller. See tests/c1_volume_query_r2/prepare.py. */\n'+text[text.index('#include <windows.h>'):]
Path('probe-not-ready.c').write_text(text)
