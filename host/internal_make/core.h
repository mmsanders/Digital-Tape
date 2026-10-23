/* Internal host composition only. Not wired to tapectl or the app. */
#ifndef DT_INTERNAL_MAKE_CORE_H
#define DT_INTERNAL_MAKE_CORE_H
#include <stdint.h>
#include "tape_dev.h"

enum im_phase { IM_SAFETY, IM_PROVISION, IM_LOAD, IM_COMMIT, IM_VERIFY };
enum im_watch { IM_UNCHANGED, IM_CHANGED, IM_REMOVED, IM_QUERY_ERROR, IM_UNKNOWN };
enum im_fact {
    IM_WHOLE=1u, IM_REMOVABLE=2u, IM_SIZE=4u, IM_NOT_SYSTEM=8u,
    IM_MOUNTS=16u, IM_ERASE=32u, IM_ALL_FACTS=63u
};
struct im_facts { uint32_t known, pass; };
/* Strings are borrowed from the caller and must remain valid through return.
   These are internal observations, not a new shipping report grammar. */
struct im_result {
    int exit_code;
    const char *id;
    enum im_phase phase;
    const char *op;
    const char *os_error;
};
struct im_ops {
    void *ctx;
    int (*query_initial)(void *, struct im_facts *, const char **);
    struct im_result (*open_authorized)(void *, void **session);
    struct im_result (*provision)(void *, void *session);
    struct im_result (*load)(void *, void *session);
    struct im_result (*commit)(void *, void *session);
    const tape_dev *(*bind_readonly)(void *, void *session);
    struct im_result (*verify)(void *, void *session, const tape_dev *);
    /* Optional declared component callback. Not an OS monitor or cadence. */
    enum im_watch (*monitor)(void *, void *session, enum im_phase, const char **);
    struct im_result (*close)(void *, void *session);
};
/* No allocation, open/reopen, native query or engine/format implementation here.
   Caller callbacks own the actual existing host operations and their stdout.
   The same non-NULL session is passed throughout, including NULL-write verify. */
struct im_result im_compose(const struct im_ops *);
#endif
