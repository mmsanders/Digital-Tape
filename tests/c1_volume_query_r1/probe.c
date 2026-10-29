/* Independent APP-1A §7 regression over the exact candidate's covered probe.
 * Hosted disposable VHD only. No make, provision, write, unmount or UI call.
 * The API wrapper asks the real OS for mount paths with a zero-size buffer.
 * This exercises a real ERROR_MORE_DATA, not a fabricated failed query result.
 */
#include <windows.h>
#include <winioctl.h>
#include <stdio.h>
#include <stdlib.h>
#include "safety.h"

static int fail_paths;
static int failed_calls;
static DWORD actual_error;
static BOOL WINAPI controlled_paths(LPCWSTR volume, LPWSTR names, DWORD cap, PDWORD needed)
{
    if (fail_paths) {
        BOOL result = GetVolumePathNamesForVolumeNameW(volume, NULL, 0, needed);
        actual_error = GetLastError();
        failed_calls++;
        return result;
    }
    return GetVolumePathNamesForVolumeNameW(volume, names, cap, needed);
}

/* The Product error-name helper is irrelevant to whether query_failed is called;
 * keep this probe-only linkage explicit, with the actual OS code if it is called.
 */
const char *hport_os_errname(void)
{
    static char text[48];
    snprintf(text, sizeof text, "Windows error %lu", (unsigned long)GetLastError());
    return text;
}

#define GetVolumePathNamesForVolumeNameW controlled_paths
#include "probe_win.c"
#undef GetVolumePathNamesForVolumeNameW

int main(int argc, char **argv)
{
    struct device_facts before, after, model;
    enum refusal baseline_policy, failed_policy;
    int requirement_pass;
    if (argc != 2) { return 2; }
    probe_device(argv[1], &before);
    if (!before.whole_device || before.holds_os || before.n_mounted < 1 || before.query_error[0]) {
        fprintf(stderr, "invalid VHD positive: whole=%d system=%d mounts=%d query=%s\n",
                before.whole_device, before.holds_os, before.n_mounted, before.query_error);
        return 2;
    }
    model = before; model.removable = 1;
    baseline_policy = safety_policy(&model, 1, 1);
    if (baseline_policy != REFUSE_FOREIGN_MOUNT) { return 2; }
    fail_paths = 1;
    probe_device(argv[1], &after);
    if (failed_calls < 1 || actual_error != ERROR_MORE_DATA) { return 2; }
    model = after; model.removable = 1;
    failed_policy = safety_policy(&model, 1, 1);
    requirement_pass = after.query_error[0] != '\0';
    printf("{\"scope\":\"actual VHD probe; removable-policy model only; no raw writes\","
           "\"baseline_mounts\":%d,\"failed_calls\":%d,\"actual_os_error\":%lu,"
           "\"failed_mounts\":%d,\"query_error_recorded\":%s,"
           "\"baseline_removable_model_policy\":%d,\"failed_removable_model_policy\":%d,"
           "\"required_query_fail_stop_pass\":%s}\n",
           before.n_mounted, failed_calls, (unsigned long)actual_error, after.n_mounted,
           requirement_pass ? "true" : "false", (int)baseline_policy, (int)failed_policy,
           requirement_pass ? "true" : "false");
    return requirement_pass ? 0 : 1;
}
