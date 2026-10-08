#ifndef READ1_COUNTING_DEVICE_H
#define READ1_COUNTING_DEVICE_H
#include <stdint.h>
#include <stdio.h>
typedef struct {
    FILE *image, *trace;
    uint8_t *dirty;
    uint32_t blocks, seed;
    int read_only, fail_read, fail_write, fail_flush;
    /* On the next failing read, copy this many prefix blocks before failure.
       The callback still reports no completion; its entire destination is invalid. */
    uint32_t fail_read_prefix;
} read1_device;
int read1_open(read1_device *, const char *, const char *, uint32_t, uint32_t, int);
void read1_close(read1_device *);
int read1_read(void *, uint32_t, uint32_t, void *);
int read1_write(void *, uint32_t, uint32_t, const void *);
int read1_flush(void *);
#endif
