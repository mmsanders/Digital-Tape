#include "core.h"
#include <stddef.h>

static struct im_result result(int code, const char *id, enum im_phase phase,
                               const char *op, const char *error)
{
    struct im_result r;
    r.exit_code=code; r.id=id; r.phase=phase; r.op=op; r.os_error=error;
    return r;
}

static struct im_result watch(const struct im_ops *ops, void *session, enum im_phase phase)
{
    const char *error=NULL;
    enum im_watch w=IM_UNCHANGED;
    if (ops->monitor!=NULL) { w=ops->monitor(ops->ctx,session,phase,&error); }
    if (w==IM_UNCHANGED) { return result(0,NULL,phase,NULL,NULL); }
    if (w==IM_CHANGED || w==IM_REMOVED) { return result(1,"CARD_CHANGED",phase,NULL,NULL); }
    if (w==IM_QUERY_ERROR) { return result(1,"HOST_QUERY_FAILED",phase,"media_query",error); }
    /* Unknown monitoring results cannot authorize another operation. */
    return result(1,NULL,phase,"unknown monitoring facts",NULL);
}

struct im_result im_compose(const struct im_ops *ops)
{
    static const uint32_t fact[6]={IM_WHOLE,IM_REMOVABLE,IM_SIZE,IM_NOT_SYSTEM,IM_MOUNTS,IM_ERASE};
    static const char *const refusal[6]={"REFUSE_NOT_WHOLE_DEVICE","REFUSE_NOT_REMOVABLE",
        "REFUSE_TOO_LARGE","REFUSE_SYSTEM_DISK","REFUSE_FOREIGN_MOUNT","REFUSE_ERASE_NOT_CONFIRMED"};
    struct im_facts facts={0u,0u};
    struct im_result r,closed;
    void *session=NULL;
    const char *error=NULL;
    const tape_dev *readonly=NULL;
    unsigned i;
    if (ops==NULL || ops->query_initial==NULL || ops->open_authorized==NULL ||
        ops->provision==NULL || ops->load==NULL || ops->commit==NULL ||
        ops->bind_readonly==NULL || ops->verify==NULL || ops->close==NULL) {
        return result(1,NULL,IM_SAFETY,"incomplete internal interface",NULL);
    }
    if (ops->query_initial(ops->ctx,&facts,&error)!=0) {
        return result(1,"HOST_QUERY_FAILED",IM_SAFETY,"media_query",error);
    }
    if ((facts.known & IM_ALL_FACTS)!=IM_ALL_FACTS) {
        return result(1,NULL,IM_SAFETY,"unknown required safety facts",NULL);
    }
    for (i=0u;i<6u;i++) {
        if ((facts.pass & fact[i])==0u) { return result(3,refusal[i],IM_SAFETY,NULL,NULL); }
    }
    r=ops->open_authorized(ops->ctx,&session);
    if (r.exit_code!=0) { return r; }
    if (session==NULL) { return result(1,NULL,IM_SAFETY,"missing owned session",NULL); }
    r=watch(ops,session,IM_PROVISION);
    if (r.exit_code==0) { r=ops->provision(ops->ctx,session); }
    if (r.exit_code==0) { r=watch(ops,session,IM_LOAD); }
    if (r.exit_code==0) { r=ops->load(ops->ctx,session); }
    if (r.exit_code==0) { r=watch(ops,session,IM_COMMIT); }
    if (r.exit_code==0) { r=ops->commit(ops->ctx,session); }
    if (r.exit_code==0) { r=watch(ops,session,IM_VERIFY); }
    if (r.exit_code==0) {
        readonly=ops->bind_readonly(ops->ctx,session);
        if (readonly==NULL || readonly->write!=NULL || readonly->read==NULL || readonly->flush==NULL) {
            r=result(1,NULL,IM_VERIFY,"unproved NULL-write binding",NULL);
        } else { r=ops->verify(ops->ctx,session,readonly); }
    }
    /* Only owned close follows any terminal boundary. Earlier stdout is not rewritten.
       Operation callbacks include their original phase-local cleanup before return. */
    closed=ops->close(ops->ctx,session);
    if (r.exit_code==0 && closed.exit_code!=0) { r=closed; }
    return r;
}
