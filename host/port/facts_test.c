/*
 * facts_test.c — the TAPECTL_TEST facts seam (docs/WP14-CLI-CONTRACT.md §5).
 *
 * COMPILED ONLY WITH -DTAPECTL_TEST, into build/host/tapectl-test. The shipped
 * build/host/tapectl does not contain it: host/test_seam.sh checks that the
 * symbol tapectl_test_facts_seam is absent from the shipped binary and present
 * in the test binary, so the check itself is proven able to go red.
 *
 * With TAPECTL_TEST_FACTS=FILE set, the probe is replaced by FILE's facts:
 *
 *   whole=1 removable=1 sd_bus=0 bytes=67108864 holds_os=0 layout_ok=0
 *   mounted=1:/Volumes/DIGITALTAPE     (repeatable: partition:where)
 *
 * one key=value per line. Missing keys keep their refusing values, so a
 * truncated facts file refuses rather than permits.
 */

#ifdef TAPECTL_TEST

#include "safety.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int tapectl_test_facts_seam(const char *path, struct device_facts *f)
{
    const char *file = getenv("TAPECTL_TEST_FACTS");
    char line[512];
    FILE *fp;

    if (file == NULL || *file == '\0') { return 0; }
    memset(f, 0, sizeof *f);
    f->holds_os = 1;
    snprintf(f->detail, sizeof f->detail, "facts injected by TAPECTL_TEST for %s", path);
    fp = fopen(file, "r");
    if (fp == NULL) { f->n_mounted = SAFETY_MAX_MOUNTS + 1; return 1; }
    while (fgets(line, sizeof line, fp) != NULL) {
        char *eq = strchr(line, '='), *v;
        line[strcspn(line, "\r\n")] = '\0';
        if (eq == NULL) { continue; }
        *eq = '\0';
        v = eq + 1;
        if (strcmp(line, "whole") == 0)          { f->whole_device = atoi(v); }
        else if (strcmp(line, "removable") == 0) { f->removable = atoi(v); }
        else if (strcmp(line, "sd_bus") == 0)    { f->sd_bus = atoi(v); }
        else if (strcmp(line, "bytes") == 0)     { f->bytes = strtoull(v, NULL, 10); }
        else if (strcmp(line, "holds_os") == 0)  { f->holds_os = atoi(v); }
        else if (strcmp(line, "layout_ok") == 0) { f->layout_ok = atoi(v); }
        else if (strcmp(line, "mounted") == 0) {
            if (f->n_mounted >= SAFETY_MAX_MOUNTS) { f->n_mounted = SAFETY_MAX_MOUNTS + 1; continue; }
            f->mounted[f->n_mounted].partition = atoi(v);
            snprintf(f->mounted[f->n_mounted].where, sizeof f->mounted[0].where, "%s",
                     strchr(v, ':') ? strchr(v, ':') + 1 : v);
            f->n_mounted++;
        }
    }
    fclose(fp);
    return 1;
}

#endif /* TAPECTL_TEST */
