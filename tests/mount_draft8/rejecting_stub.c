/* Deliberately wrong negative control. Never a reference engine or acceptance target. */
#include "candidate_api.h"
struct tape { int placeholder; };
size_t tape_instance_size(void) {return sizeof(tape);}
tape_result tape_init(void *m,size_t n,const tape_dev *d,void *p,size_t pn,void *r,size_t rn,tape **t) {
 (void)n;(void)d;(void)p;(void)pn;(void)r;(void)rn;*t=m;return TAPE_OK;
}
tape_result tape_mount(tape *t,tape_side s,uint64_t f,const tape_warm_start *w) {
 (void)t;(void)s;(void)f;(void)w;return TAPE_ERR_INVALID_ARG;
}
tape_result tape_get_info(const tape *t,tape_info *i) {(void)t;(void)i;return TAPE_ERR_NOT_MOUNTED;}
tape_result tape_tell(const tape *t,uint64_t *f) {(void)t;(void)f;return TAPE_ERR_NOT_MOUNTED;}
