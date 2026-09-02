#include <string.h>
#include "dev_file.h"

static int file_seek(struct tape_dev_file *st, uint32_t lba)
{
    long off = (long)lba * (long)TAPE_BLOCK_SIZE;
    if (fseek(st->fp, off, SEEK_SET) != 0) {
        return TAPE_ERR_IO;
    }
    return TAPE_OK;
}

static int file_read(void *ctx, uint32_t lba, uint32_t count, void *buf)
{
    struct tape_dev_file *st = (struct tape_dev_file *)ctx;
    int rc;

    if (lba > st->block_count || count > st->block_count - lba) {
        return TAPE_ERR_RANGE;
    }
    rc = file_seek(st, lba);
    if (rc != TAPE_OK) {
        return rc;
    }
    if (fread(buf, TAPE_BLOCK_SIZE, count, st->fp) != count) {
        return TAPE_ERR_IO;
    }
    return TAPE_OK;
}

static int file_write(void *ctx, uint32_t lba, uint32_t count, const void *buf)
{
    struct tape_dev_file *st = (struct tape_dev_file *)ctx;
    int rc;

    if (lba > st->block_count || count > st->block_count - lba) {
        return TAPE_ERR_RANGE;
    }
    rc = file_seek(st, lba);
    if (rc != TAPE_OK) {
        return rc;
    }
    if (fwrite(buf, TAPE_BLOCK_SIZE, count, st->fp) != count) {
        return TAPE_ERR_IO;
    }
    return TAPE_OK;
}

static int file_flush(void *ctx)
{
    struct tape_dev_file *st = (struct tape_dev_file *)ctx;
    return (fflush(st->fp) == 0) ? TAPE_OK : TAPE_ERR_IO;
}

static void file_bind(struct tape_dev_file *st, struct tape_dev *dev)
{
    dev->read        = file_read;
    /* Read-only is the absence of a function, not a flag someone can clear. */
    dev->write       = st->writable ? file_write : NULL;
    dev->flush       = file_flush;
    dev->ctx         = st;
    dev->block_count = st->block_count;
}

int tape_dev_file_open(struct tape_dev_file *st, struct tape_dev *dev,
                       const char *path, int writable)
{
    long size;

    memset(st, 0, sizeof *st);
    st->fp = fopen(path, writable ? "r+b" : "rb");
    if (st->fp == NULL) {
        return TAPE_ERR_IO;
    }
    if (fseek(st->fp, 0, SEEK_END) != 0 || (size = ftell(st->fp)) < 0) {
        (void)fclose(st->fp);
        st->fp = NULL;
        return TAPE_ERR_IO;
    }
    st->block_count = (uint32_t)((unsigned long)size / TAPE_BLOCK_SIZE);
    st->writable    = writable;
    file_bind(st, dev);
    return TAPE_OK;
}

int tape_dev_file_create(struct tape_dev_file *st, struct tape_dev *dev,
                         const char *path, uint32_t blocks)
{
    static const unsigned char zero[TAPE_BLOCK_SIZE] = { 0 };
    uint32_t i;

    memset(st, 0, sizeof *st);
    st->fp = fopen(path, "w+b");
    if (st->fp == NULL) {
        return TAPE_ERR_IO;
    }
    for (i = 0; i < blocks; i++) {
        if (fwrite(zero, TAPE_BLOCK_SIZE, 1, st->fp) != 1) {
            (void)fclose(st->fp);
            st->fp = NULL;
            return TAPE_ERR_IO;
        }
    }
    st->block_count = blocks;
    st->writable    = 1;
    file_bind(st, dev);
    return TAPE_OK;
}

int tape_dev_file_close(struct tape_dev_file *st)
{
    int rc = TAPE_OK;
    if (st->fp != NULL) {
        if (fclose(st->fp) != 0) {
            rc = TAPE_ERR_IO;
        }
        st->fp = NULL;
    }
    return rc;
}
