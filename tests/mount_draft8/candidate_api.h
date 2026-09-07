/* Verifier transcription of DRAFT-8 engine-api §§2-5,6 only.
 * For standalone harness compilation, NOT a product header or implementation.
 * Integration must use the actual public header with -DTAPE_PUBLIC_HEADER.
 */
#ifndef VERIFIER_CANDIDATE_API_H
#define VERIFIER_CANDIDATE_API_H
#include <stdint.h>
#include <stddef.h>
#include <stdbool.h>
typedef struct tape tape;
typedef enum {
 TAPE_OK=0,TAPE_ERR_IO,TAPE_ERR_BAD_MAGIC,TAPE_ERR_CRC,TAPE_ERR_VERSION,
 TAPE_ERR_UNSUPPORTED_STATE,TAPE_ERR_GEOMETRY,TAPE_ERR_INCOMPLETE,
 TAPE_ERR_INCONSISTENT,TAPE_ERR_NO_VALID_INDEX,TAPE_ERR_READ_ONLY,
 TAPE_ERR_CARTRIDGE_FULL,TAPE_ERR_INDEX_FULL,TAPE_ERR_DEST_TOO_SMALL,
 TAPE_ERR_SEQUENCE_EXHAUSTED,TAPE_ERR_FAULTED,TAPE_ERR_NOT_MOUNTED,
 TAPE_ERR_BUSY,TAPE_ERR_UNDERRUN,TAPE_ERR_INVALID_ARG
} tape_result;
typedef struct {
 int (*read)(void *,uint32_t,uint32_t,void *);
 int (*write)(void *,uint32_t,uint32_t,const void *);
 int (*flush)(void *);
 void *ctx;
 uint32_t block_count;
} tape_dev;
typedef enum {TAPE_SIDE_A=0,TAPE_SIDE_B=1} tape_side;
typedef struct {
 const void *data; uint32_t data_bytes,valid_frames,start_frame;
 uint8_t uuid[16]; tape_side side;
} tape_warm_start;
typedef struct {
 uint8_t uuid[16]; char label[33]; uint32_t nominal_length_s;
 uint64_t total_frames; uint32_t total_chunks,free_chunks,entry_count,entries_free;
 uint16_t version_minor; bool writable,side_b_valid,needs_repair,warm_start_used;
} tape_info;
size_t tape_instance_size(void);
tape_result tape_init(void *,size_t,const tape_dev *,void *,size_t,void *,size_t,tape **);
tape_result tape_mount(tape *,tape_side,uint64_t,const tape_warm_start *);
tape_result tape_get_info(const tape *,tape_info *);
tape_result tape_tell(const tape *,uint64_t *);
#endif
