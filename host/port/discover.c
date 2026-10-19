/*
 * discover.c — the cards discovery policy (APP-1A §5). Pure: facts in, verdict out.
 */

#include "discover.h"
#include "layout.h"
#include "safety.h"

#include <string.h>

void discover_init(struct disc_disk *d)
{
    memset(d, 0, sizeof *d);
    d->whole = d->removable_or_sd = d->is_virtual = d->holds_os = d->mbr = DISC_UNKNOWN;
    d->n_parts = d->n_mounted = DISC_UNKNOWN;
    d->mounted_unattributed = DISC_UNKNOWN;
}

/* The OS-view own-partition-1 pattern (APP-1A §5): MBR; p1 0x0E at 2048 for
   32768 sectors; p2 0xDA from 34816 to the device end; nothing else, and no
   mounted volume but p1. DISC_YES, DISC_NO, or DISC_UNKNOWN when a fact it
   needs is unknown. */
static int own_p1_view(const struct disc_disk *d)
{
    const struct disc_part *p1 = NULL, *p2 = NULL;
    int i, unknown = 0;
    int64_t end;

    if (d->mbr == DISC_NO) { return DISC_NO; }
    if (d->mbr != DISC_YES || d->n_parts == DISC_UNKNOWN || !d->bytes_known
        || d->mounted_unattributed == DISC_UNKNOWN) { return DISC_UNKNOWN; }
    if (d->mounted_unattributed == DISC_YES || d->n_parts != 2) { return DISC_NO; }
    for (i = 0; i < d->n_parts; i++) {
        if (d->parts[i].index == 1) { p1 = &d->parts[i]; }
        else if (d->parts[i].index == 2) { p2 = &d->parts[i]; }
    }
    if (p1 == NULL || p2 == NULL) { return DISC_NO; }
    end = (int64_t)(d->bytes / 512u);
    if (p1->type == DISC_UNKNOWN || p1->start == DISC_UNKNOWN || p1->sectors == DISC_UNKNOWN) { unknown = 1; }
    else if (p1->type != (int)LAYOUT_P1_TYPE || p1->start != (int64_t)LAYOUT_P1_START
             || p1->sectors != (int64_t)LAYOUT_P1_SECTORS) { return DISC_NO; }
    if (p2->type == DISC_UNKNOWN || p2->start == DISC_UNKNOWN || p2->sectors == DISC_UNKNOWN) { unknown = 1; }
    else if (p2->type != (int)LAYOUT_P2_TYPE || p2->start != (int64_t)LAYOUT_P2_START
             || p2->start + p2->sectors != end) { return DISC_NO; }
    if (p2->mounted == DISC_YES) { return DISC_NO; }
    if (p1->mounted == DISC_UNKNOWN || p2->mounted == DISC_UNKNOWN) { unknown = 1; }
    return unknown ? DISC_UNKNOWN : DISC_YES;
}

enum disc_verdict discover_policy(const struct disc_disk *d)
{
    int unknown = 0, view;

    if (d->whole == DISC_NO || d->is_virtual == DISC_YES || d->removable_or_sd == DISC_NO
        || d->holds_os == DISC_YES) { return DISC_REFUSE; }
    if (d->bytes_known && (d->bytes == 0 || d->bytes > SAFETY_TOO_LARGE)) { return DISC_REFUSE; }
    if (d->whole == DISC_UNKNOWN || d->is_virtual == DISC_UNKNOWN || d->removable_or_sd == DISC_UNKNOWN
        || d->holds_os == DISC_UNKNOWN || !d->bytes_known) { unknown = 1; }

    if (d->n_mounted == DISC_UNKNOWN) {
        unknown = 1;
    } else if (d->n_mounted > 0) {
        /* Only a possible own p1 may be mounted; OS-visible boot/system use
           already refused above. */
        view = own_p1_view(d);
        if (view == DISC_NO) { return DISC_REFUSE; }
        if (view == DISC_UNKNOWN) { unknown = 1; }
    }
    return unknown ? DISC_UNPROBED : DISC_OFFER;
}
