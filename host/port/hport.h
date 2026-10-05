/*
 * hport.h — the WP-14 host port: one port for image files and devices.
 *
 * Normative: docs/WP14-CLI-CONTRACT.md §6.
 *   - 64-bit byte offsets everywhere (pread/pwrite; ReadFile/WriteFile with
 *     OVERLAPPED offsets on Windows).
 *   - A durable flush: fsync (Linux), F_FULLFSYNC (macOS), FlushFileBuffers
 *     (Windows). It returns success only after the OS call does.
 *   - No write coalescing: each write is issued, in order, before it returns.
 *
 * partview.c presents a block range of an hport as the engine's tape_dev.
 * engine/port/dev_file.c is untouched and still serves the Phase 1 suites.
 */

#ifndef HOST_HPORT_H
#define HOST_HPORT_H

#include <stddef.h>
#include <stdint.h>

#include "tape_dev.h"

struct hport {
#if defined(_WIN32)
    void *h;                  /* HANDLE */
#else
    int fd;
#endif
    int is_device;
    int writable;
    uint64_t bytes;           /* size of the file, or capacity of the device */
    const char *flush_how;    /* the OS call flush uses, for diagnostics */
    unsigned long long flushes;
};

/* What a target path names, before anything is opened. */
enum hport_path { HPORT_MISSING, HPORT_REGULAR, HPORT_DEVICE, HPORT_OTHER };
enum hport_path hport_classify(const char *path);

/* Open an existing image or a device. A device is opened for raw access
   (macOS: /dev/diskN is opened as /dev/rdiskN). writable=0 is a read-only open. */
int hport_open(struct hport *p, const char *path, int is_device, int writable);

/* Create or truncate an image file to exactly `bytes` (sparse where the OS can). */
int hport_create(struct hport *p, const char *path, uint64_t bytes);

/* Whole transfers at a byte offset; 0 on success, -1 on any failure or short I/O. */
int hport_read(struct hport *p, uint64_t off, void *buf, size_t len);
int hport_write(struct hport *p, uint64_t off, const void *buf, size_t len);

/* The durable flush. 0 only after the OS reports the data on the medium. */
int hport_flush(struct hport *p);

int hport_close(struct hport *p);

/* A partition view: blocks [base, base + blocks) of `p` as a tape_dev.
   `writable` = 0 binds a NULL write callback (the WP-36 pattern), whatever
   the underlying open allows. Out-of-range transfers fail without I/O. */
struct partview {
    struct hport *p;
    uint64_t base;
    uint32_t blocks;
    unsigned long long reads, writes, flushes;
};

void partview_bind(struct partview *v, tape_dev *dev, struct hport *p,
                   uint64_t base_lba, uint32_t blocks, int writable);

#endif /* HOST_HPORT_H */
