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
   32768 sectors; p2 0xDA from 34816 to the device end; no p3 or p4, and no
   mounted volume but p1. DISC_UNKNOWN when any fact it needs is unknown, else
   DISC_YES or DISC_NO. */
static int own_p1_view(const struct disc_disk *d)
{
    const struct disc_part *p1 = NULL, *p2 = NULL;
    int i, other = 0;

    if (d->mbr == DISC_UNKNOWN || d->n_parts == DISC_UNKNOWN || d->mounted_unattributed == DISC_UNKNOWN) {
        return DISC_UNKNOWN;
    }
    for (i = 0; i < d->n_parts; i++) {
        const struct disc_part *q = &d->parts[i];
        if (q->index == 1) { p1 = q; }
        else if (q->index == 2) { p2 = q; }
        else { other = 1; }
        if (q->mounted == DISC_UNKNOWN) { return DISC_UNKNOWN; }
    }
    if ((p1 && (p1->type == DISC_UNKNOWN || p1->start == DISC_UNKNOWN || p1->length == DISC_UNKNOWN))
        || (p2 && (p2->type == DISC_UNKNOWN || p2->start == DISC_UNKNOWN || p2->length == DISC_UNKNOWN))) {
        return DISC_UNKNOWN;
    }
    if (d->mbr != DISC_YES || p1 == NULL || p2 == NULL || other || d->mounted_unattributed == DISC_YES) { return DISC_NO; }
    if (p1->type != (int)LAYOUT_P1_TYPE || p1->start != (int64_t)LAYOUT_P1_START * 512
        || p1->length != (int64_t)LAYOUT_P1_SECTORS * 512) { return DISC_NO; }
    if (p2->type != (int)LAYOUT_P2_TYPE || p2->start != (int64_t)LAYOUT_P2_START * 512
        || (uint64_t)(p2->start + p2->length) != d->bytes) { return DISC_NO; }
    return (p1->mounted == DISC_YES && p2->mounted == DISC_NO) ? DISC_YES : DISC_NO;
}

enum disc_verdict discover_policy(const struct disc_disk *d)
{
    int view;

    if (d->whole == DISC_UNKNOWN || d->is_virtual == DISC_UNKNOWN || d->removable_or_sd == DISC_UNKNOWN
        || d->holds_os == DISC_UNKNOWN || !d->bytes_known || d->n_mounted == DISC_UNKNOWN) { return DISC_UNPROBED; }
    if (d->whole == DISC_NO || d->is_virtual == DISC_YES || d->removable_or_sd == DISC_NO
        || d->holds_os == DISC_YES) { return DISC_REFUSE; }
    if (d->bytes == 0) { return DISC_UNPROBED; }          /* no medium size: unknown, not a card */
    if (d->bytes > SAFETY_TOO_LARGE) { return DISC_REFUSE; }
    if (d->n_mounted == 0) { return DISC_OFFER; }          /* a bare card may be a candidate */
    view = own_p1_view(d);
    return view == DISC_YES ? DISC_OFFER : view == DISC_NO ? DISC_REFUSE : DISC_UNPROBED;
}
