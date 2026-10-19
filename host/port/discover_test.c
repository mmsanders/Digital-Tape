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
 */

#ifdef TAPECTL_TEST

#include "discover.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

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

#endif /* TAPECTL_TEST */
