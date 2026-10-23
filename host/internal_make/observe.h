/* Test-only link plumbing. Never included by a shipping build. */
#ifndef IM_OBSERVE_H
#define IM_OBSERVE_H
#include "hport.h"
int im_hport_open(struct hport *, const char *, int, int);
int im_hport_create(struct hport *, const char *, uint64_t);
int im_hport_read(struct hport *, uint64_t, void *, size_t);
int im_hport_write(struct hport *, uint64_t, const void *, size_t);
int im_hport_flush(struct hport *);
int im_hport_close(struct hport *);
#define hport_open im_hport_open
#define hport_create im_hport_create
#define hport_read im_hport_read
#define hport_write im_hport_write
#define hport_flush im_hport_flush
#define hport_close im_hport_close
#endif
