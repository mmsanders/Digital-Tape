/* entropy.h — OS CSPRNG UUID and wall-clock epoch for provision (§3). */
#ifndef HOST_ENTROPY_H
#define HOST_ENTROPY_H
#include <stdint.h>
int entropy_uuid(uint8_t out[16]);   /* 0, or -1 if the OS refused */
int entropy_epoch(uint32_t *out);    /* u32 seconds since 1970 UTC */
#endif
