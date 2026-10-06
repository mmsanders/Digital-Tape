/*
 * hport.c — the public host port: the platform halves, plus (test build only)
 * the TAPECTL_TEST observation and fault seam of tseam.h.
 *
 * In the shipped build each function here is a direct call to its platform
 * half. With -DTAPECTL_TEST every open, write and flush is also recorded from
 * here, inside the port, and the flush fault controls are applied here.
 */

#include "hport.h"
#include "tseam.h"

int hport_open(struct hport *p, const char *path, int is_device, int writable)
{
    int rc = hport_os_open(p, path, is_device, writable);
#ifdef TAPECTL_TEST
    tseam_open(path, is_device, writable, rc == 0);
#endif
    return rc;
}

int hport_create(struct hport *p, const char *path, uint64_t bytes)
{
    int rc = hport_os_create(p, path, bytes);
#ifdef TAPECTL_TEST
    tseam_open(path, 0, 1, rc == 0);
#endif
    return rc;
}

int hport_write(struct hport *p, uint64_t off, const void *buf, size_t len)
{
    int rc = hport_os_write(p, off, buf, len);
#ifdef TAPECTL_TEST
    tseam_write(off, len, rc == 0);
#endif
    return rc;
}

int hport_flush(struct hport *p)
{
    int rc;
    p->flushes++;
#ifdef TAPECTL_TEST
    if (tseam_fault_noop_flush()) {             /* control: no barrier at all */
        p->flush_how = "none";
        tseam_flush("none", 0, 1);
        return 0;
    }
    rc = hport_os_flush(p);
    if (tseam_fault_hidden_flush_error()) {     /* control: OS failure hidden */
        tseam_flush(p->flush_how, 0, 1);
        return 0;
    }
    tseam_flush(p->flush_how, rc == 0, rc == 0);
    return rc;
#else
    rc = hport_os_flush(p);
    return rc;
#endif
}
