/*
 * tape_crc32.h — CRC-32/ISO-HDLC.
 *
 * The index commit protocol stores a CRC alongside a sequence number, and mount
 * picks the higher sequence with a valid CRC (guardrail 07). This is that CRC.
 *
 * Parameters, named so there is no ambiguity across three streams and two
 * toolchains — CRC-32/ISO-HDLC, a.k.a. CRC-32, PKZIP, the one in zlib:
 *
 *     width   32          poly    0x04C11DB7  (0xEDB88320 reflected)
 *     init    0xFFFFFFFF  refin   true        refout true
 *     xorout  0xFFFFFFFF  check   0xCBF43F26  ("123456789")
 *     residue 0xDEBB20E3
 */

#ifndef TAPE_CRC32_H
#define TAPE_CRC32_H

#include <stddef.h>
#include <stdint.h>

/* One-shot over a buffer. */
uint32_t tape_crc32(const void *buf, size_t len);

/*
 * Streaming, for data that does not arrive contiguously — a commit spans a
 * header and an entry array that are not adjacent in memory.
 *
 *     uint32_t c = tape_crc32_init();
 *     c = tape_crc32_update(c, a, na);
 *     c = tape_crc32_update(c, b, nb);
 *     uint32_t crc = tape_crc32_final(c);
 */
uint32_t tape_crc32_init(void);
uint32_t tape_crc32_update(uint32_t state, const void *buf, size_t len);
uint32_t tape_crc32_final(uint32_t state);

#endif /* TAPE_CRC32_H */
