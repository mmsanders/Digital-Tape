/*
 * hport.c — the public host port: the platform halves, plus (test build only)
 * the TAPECTL_TEST observation and fault seam of tseam.h.
 *
 * In the shipped build each function here is a direct call to its platform
 * half. With -DTAPECTL_TEST every open, read, write and flush is also recorded
 * from here, inside the port, and the fault controls are applied here.
 *
 * Fault controls that need a failed OS call make a REAL one: the call is issued
 * on a copy of the port whose handle refers to no open file, so the OS itself
 * returns the failure (EBADF / ERROR_INVALID_HANDLE) and that result is what is
 * recorded and propagated. Nothing is reported as an OS result that the OS did
 * not return.
 */

#include "hport.h"
#include "tseam.h"

#include <string.h>

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

int hport_read(struct hport *p, uint64_t off, void *buf, size_t len)
{
#ifdef TAPECTL_TEST
    int rc;
    if (tseam_fault_target_read(off, len)) {      /* control: a real failed OS read */
        struct hport broken = *p;
        hport_os_invalidate(&broken);
        rc = hport_os_read(&broken, off, buf, len);
        tseam_read(off, len, rc == 0, rc == 0 ? NULL : hport_os_errname(), "target-read-error");
        return rc == 0 ? 0 : -1;
    }
    rc = hport_os_read(p, off, buf, len);
    tseam_read(off, len, rc == 0, rc == 0 ? NULL : hport_os_errname(), NULL);
    return rc;
#else
    return hport_os_read(p, off, buf, len);
#endif
}

#ifdef TAPECTL_TEST
/* read-error:LBA (partition-relative), applied by partview: the same real
   failed OS read, at the absolute offset the engine asked for. */
int hport_read_failing(struct hport *p, uint64_t off, void *buf, size_t len)
{
    struct hport broken = *p;
    int rc;
    hport_os_invalidate(&broken);
    rc = hport_os_read(&broken, off, buf, len);
    tseam_read(off, len, rc == 0, rc == 0 ? NULL : hport_os_errname(), "read-error");
    return -1;
}
#endif

int hport_write(struct hport *p, uint64_t off, const void *buf, size_t len)
{
    int rc = hport_os_write(p, off, buf, len);
#ifdef TAPECTL_TEST
    tseam_write(off, len, buf, rc == 0);
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
        tseam_flush("none", 0, NULL, 1, NULL, "noop-flush");
        return 0;
    }
    if (tseam_fault_hidden_flush_error() || tseam_fault_native_flush_error()) {
        /* A real barrier call that the OS fails. hidden-flush-error then
           reports success anyway (the control); native-flush-error propagates
           the failure (the production behaviour under a failing OS). */
        struct hport broken = *p;
        int hidden = tseam_fault_hidden_flush_error();
        hport_os_invalidate(&broken);
        rc = hport_os_flush(&broken);
        p->flush_how = broken.flush_how;
        tseam_flush(broken.flush_how, rc == 0, rc == 0 ? NULL : hport_os_errname(), hidden ? 1 : rc == 0,
                    broken.flush_note, hidden ? "hidden-flush-error" : "native-flush-error");
        return hidden ? 0 : rc;
    }
    rc = hport_os_flush(p);
    tseam_flush(p->flush_how, rc == 0, rc == 0 ? NULL : hport_os_errname(), rc == 0, p->flush_note, NULL);
    return rc;
#else
    rc = hport_os_flush(p);
    return rc;
#endif
}
