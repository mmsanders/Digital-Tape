/*
 * discover_test.c — the TAPECTL_TEST cards facts seam (APP-1A §5 test route).
 *
 * COMPILED ONLY WITH -DTAPECTL_TEST, into build/host/tapectl-test. The shipped
 * build/host/tapectl does not contain it (host/test_seam.sh checks the symbol
 * tapectl_test_cards_seam is absent there and present here).
 *
 * With TAPECTL_TEST_CARDS=FILE set, each line `PATH key=value ...` replaces
 * those facts of the real disk the platform enumerator listed at PATH; every
 * other fact, and every other disk, stays as the OS reported it. Keys:
 *   whole removable_or_sd virtual holds_os mbr   value 1, 0 or -1 (unknown)
 * A virtual disk (loop, hdiutil image, VHD) is never a card to the shipped
 * policy; this lets a real one stand in for removable media in a test.
 *
 * With TAPECTL_TEST_CARDS_VECTOR=FILE set, the platform enumerator is replaced
 * by FILE's disks, one per line, every fact given (-1 unknown):
 *   path=P whole=W removable_or_sd=R virtual=V holds_os=O bytes=N|-1
 *   n_mounted=M mbr=X mounted_unattributed=U n_parts=K
 *   p=INDEX,TYPE,START_BYTES,LENGTH_BYTES,MOUNTED   (repeated, K times)
 * or a single line `unavailable=REASON` for a failed enumeration. The listed
 * disks then go through the same policy and printing as enumerated ones: the
 * fixed discovery vectors of Verification #208 (tests/wp15_cards_make_r1).
 *
 * With TAPECTL_TEST_DISC_FAULT=POINT[,POINT...] set, the real platform
 * enumerator treats each named query as failed (DISC_FAULT in discover_<os>.c):
 * a compiled control for an OS query failure, not a native observation.
 */

#ifdef TAPECTL_TEST

#include "discover.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

int tapectl_test_disc_fault(const char *point)
{
    const char *list = getenv("TAPECTL_TEST_DISC_FAULT"), *s;
    size_t n = strlen(point);
    if (list == NULL) { return 0; }
    for (s = list; (s = strstr(s, point)) != NULL; s += n) {
        if ((s == list || s[-1] == ',') && (s[n] == '\0' || s[n] == ',')) { return 1; }
    }
    return 0;
}

void tapectl_test_cards_seam(struct disc_disk *d)
{
    const char *file = getenv("TAPECTL_TEST_CARDS");
    char line[512];
    FILE *fp;

    if (file == NULL || *file == '\0' || (fp = fopen(file, "r")) == NULL) { return; }
    while (fgets(line, sizeof line, fp) != NULL) {
        char *tok;
        line[strcspn(line, "\r\n")] = '\0';
        tok = strtok(line, " ");
        if (tok == NULL || strcmp(tok, d->path) != 0) { continue; }
        while ((tok = strtok(NULL, " ")) != NULL) {
            char *eq = strchr(tok, '=');
            int v;
            if (eq == NULL) { continue; }
            *eq = '\0';
            v = atoi(eq + 1);
            if (v < DISC_UNKNOWN || v > DISC_YES) { continue; }
            if (strcmp(tok, "whole") == 0) { d->whole = v; }
            else if (strcmp(tok, "removable_or_sd") == 0) { d->removable_or_sd = v; }
            else if (strcmp(tok, "virtual") == 0) { d->is_virtual = v; }
            else if (strcmp(tok, "holds_os") == 0) { d->holds_os = v; }
            else if (strcmp(tok, "mbr") == 0) { d->mbr = v; }
        }
    }
    fclose(fp);
}

static long long num(const char *v) { return strtoll(v, NULL, 10); }

int tapectl_test_cards_vector(disc_each each, void *ctx, char *err, size_t cap)
{
    const char *file = getenv("TAPECTL_TEST_CARDS_VECTOR");
    static struct disc_disk disks[DISC_MAX_DISKS];
    char line[2048];
    FILE *fp;
    int n = 0, i;

    if (file == NULL || *file == '\0') { return 1; }
    if ((fp = fopen(file, "r")) == NULL) { snprintf(err, cap, "cannot read %s", file); return -1; }
    while (fgets(line, sizeof line, fp) != NULL) {
        struct disc_disk *d;
        char *tok;
        line[strcspn(line, "\r\n")] = '\0';
        if (strncmp(line, "unavailable=", 12) == 0) { snprintf(err, cap, "%s", line + 12); fclose(fp); return -1; }
        if (line[0] == '\0') { continue; }
        if (n >= DISC_MAX_DISKS) { snprintf(err, cap, "too many disks in %s", file); fclose(fp); return -1; }
        d = &disks[n++];
        discover_init(d);
        d->n_parts = 0;
        for (tok = strtok(line, " "); tok != NULL; tok = strtok(NULL, " ")) {
            char *v = strchr(tok, '=');
            if (v == NULL) { continue; }
            *v++ = '\0';
            if (strcmp(tok, "path") == 0) { snprintf(d->path, sizeof d->path, "%s", v); }
            else if (strcmp(tok, "whole") == 0) { d->whole = (int)num(v); }
            else if (strcmp(tok, "removable_or_sd") == 0) { d->removable_or_sd = (int)num(v); }
            else if (strcmp(tok, "virtual") == 0) { d->is_virtual = (int)num(v); }
            else if (strcmp(tok, "holds_os") == 0) { d->holds_os = (int)num(v); }
            else if (strcmp(tok, "bytes") == 0) { d->bytes_known = num(v) >= 0; d->bytes = d->bytes_known ? strtoull(v, NULL, 10) : 0; }
            else if (strcmp(tok, "n_mounted") == 0) { d->n_mounted = (int)num(v); }
            else if (strcmp(tok, "mbr") == 0) { d->mbr = (int)num(v); }
            else if (strcmp(tok, "mounted_unattributed") == 0) { d->mounted_unattributed = (int)num(v); }
            else if (strcmp(tok, "n_parts") == 0 && num(v) < 0) { d->n_parts = DISC_UNKNOWN; }
            else if (strcmp(tok, "p") == 0 && d->n_parts >= 0 && d->n_parts < DISC_MAX_PARTS) {
                struct disc_part *q = &d->parts[d->n_parts++];
                long long f[5] = {0, -1, -1, -1, -1};
                int k = 0;
                char *s = v;
                while (k < 5) { f[k++] = strtoll(s, &s, 10); if (*s != ',') { break; } s++; }
                q->index = (int)f[0]; q->type = (int)f[1]; q->start = f[2]; q->length = f[3]; q->mounted = (int)f[4];
            }
        }
    }
    fclose(fp);
    for (i = 0; i < n; i++) { each(ctx, &disks[i], i + 1, n); }
    return 0;
}

#endif /* TAPECTL_TEST */
