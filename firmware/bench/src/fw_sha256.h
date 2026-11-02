/*
 * fw_sha256.h — SHA-256 (FIPS 180-4) for the F1 golden hook.
 *
 * Portable C99, no allocation. The firmware hashes the PCM it renders so a
 * golden check needs only one line over USB serial; the off-target harness
 * uses the same code, and checks it against known vectors first.
 */

#ifndef FW_SHA256_H
#define FW_SHA256_H

#include <stddef.h>
#include <stdint.h>

struct fw_sha256 {
    uint32_t h[8];
    uint64_t bytes;
    uint8_t  buf[64];
    uint32_t fill;
};

void fw_sha256_init(struct fw_sha256 *s);
void fw_sha256_update(struct fw_sha256 *s, const void *data, size_t len);
void fw_sha256_final(struct fw_sha256 *s, uint8_t out[32]);

/* Lower-case hex of a digest, NUL-terminated (65 bytes). */
void fw_sha256_hex(const uint8_t digest[32], char out[65]);

#endif /* FW_SHA256_H */
