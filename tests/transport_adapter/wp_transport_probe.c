#ifndef TAPE_PUBLIC_HEADER
#define TAPE_PUBLIC_HEADER "tape.h"
#endif
#include TAPE_PUBLIC_HEADER
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <stdbool.h>

#define ADAPTER_KIND "product"
#define OBS_FORMAT "WP-TRANSPORT-OBSERVATION-1"

#define VO_BLOCK 512u
#define VO_SLOT_BYTES 65536u
#define VO_SLOT_BLOCKS (VO_SLOT_BYTES / VO_BLOCK)
#define VO_SLOTS 4u
#define VO_HEADER 8u
#define VO_SIZE (VO_HEADER + 2u * VO_BLOCK + VO_SLOTS * VO_SLOT_BYTES)
#define LBA_PRIMARY 0u
#define LBA_A0 8u
#define LBA_CHUNK_BASE 2048u
#define MAX_CHUNKS 64u
#define POISON_BYTE 0xA5u
#define SERVICE_BUDGET 1024u
#define SERVICE_GUARD 65536u
#define INSTANCE_BYTES 262144u

struct media {
    uint32_t blocks;
    unsigned char primary[VO_BLOCK];
    unsigned char mirror[VO_BLOCK];
    unsigned char slots[VO_SLOTS][VO_SLOT_BYTES];
    unsigned char *chunk[MAX_CHUNKS];
};
static struct media g_media;

static const char *result_name(tape_result r) {
    switch (r) {
    case TAPE_OK: return "TAPE_OK";
    case TAPE_ERR_IO: return "TAPE_ERR_IO";
    case TAPE_ERR_BAD_MAGIC: return "TAPE_ERR_BAD_MAGIC";
    case TAPE_ERR_CRC: return "TAPE_ERR_CRC";
    case TAPE_ERR_VERSION: return "TAPE_ERR_VERSION";
    case TAPE_ERR_UNSUPPORTED_STATE: return "TAPE_ERR_UNSUPPORTED_STATE";
    case TAPE_ERR_GEOMETRY: return "TAPE_ERR_GEOMETRY";
    case TAPE_ERR_INCOMPLETE: return "TAPE_ERR_INCOMPLETE";
    case TAPE_ERR_INCONSISTENT: return "TAPE_ERR_INCONSISTENT";
    case TAPE_ERR_NO_VALID_INDEX: return "TAPE_ERR_NO_VALID_INDEX";
    case TAPE_ERR_READ_ONLY: return "TAPE_ERR_READ_ONLY";
    case TAPE_ERR_CARTRIDGE_FULL: return "TAPE_ERR_CARTRIDGE_FULL";
    case TAPE_ERR_INDEX_FULL: return "TAPE_ERR_INDEX_FULL";
    case TAPE_ERR_DEST_TOO_SMALL: return "TAPE_ERR_DEST_TOO_SMALL";
    case TAPE_ERR_SEQUENCE_EXHAUSTED: return "TAPE_ERR_SEQUENCE_EXHAUSTED";
    case TAPE_ERR_FAULTED: return "TAPE_ERR_FAULTED";
    case TAPE_ERR_NOT_MOUNTED: return "TAPE_ERR_NOT_MOUNTED";
    case TAPE_ERR_BUSY: return "TAPE_ERR_BUSY";
    case TAPE_ERR_UNDERRUN: return "TAPE_ERR_UNDERRUN";
    case TAPE_ERR_INVALID_ARG: return "TAPE_ERR_INVALID_ARG";
    default: return "TAPE_ERR_UNKNOWN";
    }
}

struct event {
    const char *phase;
    const char *op;
    uint32_t lba, count;
    int rc;
    bool has_extent;
};
#define MAX_EVENTS 32768u
static struct event g_events[MAX_EVENTS];
static size_t g_event_count;
static bool g_event_overflow;
static const char *g_phase = "init";

static void record_event(const char *op, uint32_t lba, uint32_t count, int rc, bool extent) {
    struct event *e;
    if (g_event_count >= MAX_EVENTS) { g_event_overflow = true; return; }
    e = &g_events[g_event_count++];
    e->phase = g_phase; e->op = op; e->lba = lba; e->count = count; e->rc = rc; e->has_extent = extent;
}

struct call_rec {
    const char *phase;
    const char *fn;
    const char *result;
    const char *side;
    const char *mode;
    bool has_frame; uint64_t frame;
    bool has_requested; uint32_t requested;
    bool has_rendered; uint32_t rendered;
    bool has_rate; int32_t rate;
    bool has_more_work; bool more_work;
    bool has_evcount; unsigned long evcount;

    bool has_at_end; bool at_end;
    bool has_at_start; bool at_start;

    bool has_warm_used; bool warm_used;
    bool has_total_frames; uint64_t total_frames;
    bool has_entry_count; uint32_t entry_count;
    bool has_entries_free; uint32_t entries_free;
    bool has_side_b_valid; bool side_b_valid;

    bool has_resume; uint64_t resume_frame;
    bool has_warm_present; bool warm_present;
    bool has_warm_data_present; bool warm_data_present;
    bool has_warm_data_bytes; uint32_t warm_data_bytes;
    bool has_warm_valid_frames; uint32_t warm_valid_frames;
    bool has_warm_start_frame; uint32_t warm_start_frame;
    bool has_warm_uuid; unsigned char warm_uuid[16];
    bool has_warm_side; tape_side warm_side;
};
#define MAX_CALLS 256u
static struct call_rec g_calls[MAX_CALLS];
static size_t g_call_count;

static struct call_rec *push_call(const char *phase, const char *fn, tape_result r) {
    struct call_rec *c;
    if (g_call_count >= MAX_CALLS) return NULL;
    c = &g_calls[g_call_count++];
    memset(c, 0, sizeof *c);
    c->phase = phase; c->fn = fn; c->result = result_name(r);
    return c;
}

static unsigned char *block_at(uint32_t lba, bool alloc) {
    if (lba == LBA_PRIMARY) return g_media.primary;
    if (lba == g_media.blocks - 1u) return g_media.mirror;
    if (lba >= LBA_A0 && lba < LBA_A0 + VO_SLOTS * VO_SLOT_BLOCKS) {
        uint32_t off = lba - LBA_A0;
        return g_media.slots[off / VO_SLOT_BLOCKS] + (off % VO_SLOT_BLOCKS) * VO_BLOCK;
    }
    if (lba >= LBA_CHUNK_BASE && lba < g_media.blocks - 1u) {
        uint32_t rel = lba - LBA_CHUNK_BASE;
        uint32_t ci = rel / TAPE_CHUNK_BLOCKS;
        if (ci >= MAX_CHUNKS) return NULL;
        if (g_media.chunk[ci] == NULL) {
            if (!alloc) return NULL;
            g_media.chunk[ci] = malloc((size_t)TAPE_CHUNK_BLOCKS * VO_BLOCK);
            if (g_media.chunk[ci] == NULL) return NULL;
            memset(g_media.chunk[ci], (int)POISON_BYTE, (size_t)TAPE_CHUNK_BLOCKS * VO_BLOCK);
        }
        return g_media.chunk[ci] + (rel % TAPE_CHUNK_BLOCKS) * VO_BLOCK;
    }
    return NULL;
}
static bool in_range(uint32_t lba, uint32_t count) {
    return count != 0u && (uint64_t)lba + (uint64_t)count <= (uint64_t)g_media.blocks;
}
static int dev_read(void *ctx, uint32_t lba, uint32_t count, void *dst) {
    unsigned char *out = dst; uint32_t i; (void)ctx;
    if (!in_range(lba,count)) { record_event("read",lba,count,-1,true); return -1; }
    for (i=0;i<count;i++) {
        const unsigned char *src = block_at(lba+i,false);
        if (src) memcpy(out + (size_t)i*VO_BLOCK, src, VO_BLOCK);
        else memset(out + (size_t)i*VO_BLOCK, (int)POISON_BYTE, VO_BLOCK);
    }
    record_event("read",lba,count,0,true); return 0;
}
static int dev_write(void *ctx, uint32_t lba, uint32_t count, const void *src) {
    const unsigned char *in = src; uint32_t i; (void)ctx;
    if (!in_range(lba,count)) { record_event("write",lba,count,-1,true); return -1; }
    for(i=0;i<count;i++) {
        unsigned char *dst = block_at(lba+i,true);
        if (!dst) { record_event("write",lba,count,-1,true); return -1; }
        memcpy(dst, in + (size_t)i*VO_BLOCK, VO_BLOCK);
    }
    record_event("write",lba,count,0,true); return 0;
}
static int dev_flush(void *ctx) { (void)ctx; record_event("flush",0,0,0,false); return 0; }

static int media_load(const char *path) {
    static unsigned char buf[VO_SIZE];
    FILE *f=fopen(path,"rb"); size_t got; unsigned s; size_t p;
    if(!f){fprintf(stderr,"cannot open input %s\n",path);return -1;}
    got=fread(buf,1u,sizeof buf,f);
    if(got!=sizeof buf || fgetc(f)!=EOF){fprintf(stderr,"bad VO08 size\n");fclose(f);return -1;}
    fclose(f);
    if(memcmp(buf,"VO08",4)!=0){fprintf(stderr,"bad VO08 magic\n");return -1;}
    memset(&g_media,0,sizeof g_media);
    g_media.blocks=(uint32_t)buf[4]|((uint32_t)buf[5]<<8)|((uint32_t)buf[6]<<16)|((uint32_t)buf[7]<<24);
    p=VO_HEADER;
    memcpy(g_media.primary,buf+p,VO_BLOCK); p+=VO_BLOCK;
    memcpy(g_media.mirror,buf+p,VO_BLOCK); p+=VO_BLOCK;
    for(s=0;s<VO_SLOTS;s++){memcpy(g_media.slots[s],buf+p,VO_SLOT_BYTES);p+=VO_SLOT_BYTES;}
    return 0;
}
static int media_store(const char *path) {
    static unsigned char buf[VO_SIZE];
    FILE *f; size_t p=VO_HEADER; unsigned s;
    memcpy(buf,"VO08",4);
    buf[4]=(unsigned char)(g_media.blocks&0xffu); buf[5]=(unsigned char)((g_media.blocks>>8)&0xffu);
    buf[6]=(unsigned char)((g_media.blocks>>16)&0xffu); buf[7]=(unsigned char)((g_media.blocks>>24)&0xffu);
    memcpy(buf+p,g_media.primary,VO_BLOCK);p+=VO_BLOCK;
    memcpy(buf+p,g_media.mirror,VO_BLOCK);p+=VO_BLOCK;
    for(s=0;s<VO_SLOTS;s++){memcpy(buf+p,g_media.slots[s],VO_SLOT_BYTES);p+=VO_SLOT_BYTES;}
    f=fopen(path,"wb"); if(!f)return -1;
    if(fwrite(buf,1u,sizeof buf,f)!=sizeof buf){fclose(f);return -1;}
    return fclose(f)==0?0:-1;
}

static void emit_uuid(const unsigned char u[16]) {
    size_t i;
    printf("\"");
    for(i=0;i<16;i++) printf("%02x",(unsigned)u[i]);
    printf("\"");
}
static void emit_json(void) {
    size_t i;
    printf("{\"format\":\"%s\",\"adapter_kind\":\"%s\",\"calls\":[",OBS_FORMAT,ADAPTER_KIND);
    for(i=0;i<g_call_count;i++) {
        const struct call_rec *c=&g_calls[i];
        if(i) printf(",");
        printf("{\"phase\":\"%s\",\"fn\":\"%s\",\"result\":\"%s\"",c->phase,c->fn,c->result);
        if(c->side) printf(",\"side\":\"%s\"",c->side);
        if(c->mode) printf(",\"mode\":\"%s\"",c->mode);
        if(c->has_frame) printf(",\"frame\":%llu",(unsigned long long)c->frame);
        if(c->has_requested) printf(",\"requested\":%lu",(unsigned long)c->requested);
        if(c->has_rendered) printf(",\"rendered\":%lu",(unsigned long)c->rendered);
        if(c->has_rate) printf(",\"rate_q16_16\":%ld",(long)c->rate);
        if(c->has_more_work) printf(",\"more_work\":%s",c->more_work?"true":"false");
        if(c->has_evcount) printf(",\"events_from_call\":%lu",c->evcount);
        if(c->has_at_end) printf(",\"at_end\":%s",c->at_end?"true":"false");
        if(c->has_at_start) printf(",\"at_start\":%s",c->at_start?"true":"false");
        if(c->has_warm_used) printf(",\"warm_start_used\":%s",c->warm_used?"true":"false");
        if(c->has_total_frames) printf(",\"total_frames\":%llu",(unsigned long long)c->total_frames);
        if(c->has_entry_count) printf(",\"entry_count\":%lu",(unsigned long)c->entry_count);
        if(c->has_entries_free) printf(",\"entries_free\":%lu",(unsigned long)c->entries_free);
        if(c->has_side_b_valid) printf(",\"side_b_valid\":%s",c->side_b_valid?"true":"false");
        if(c->has_resume) printf(",\"resume_frame\":%llu",(unsigned long long)c->resume_frame);
        if(c->has_warm_present) printf(",\"warm_present\":%s",c->warm_present?"true":"false");
        if(c->has_warm_data_present) printf(",\"warm_data_present\":%s",c->warm_data_present?"true":"false");
        if(c->has_warm_data_bytes) printf(",\"warm_data_bytes\":%lu",(unsigned long)c->warm_data_bytes);
        if(c->has_warm_valid_frames) printf(",\"warm_valid_frames\":%lu",(unsigned long)c->warm_valid_frames);
        if(c->has_warm_start_frame) printf(",\"warm_start_frame\":%lu",(unsigned long)c->warm_start_frame);
        if(c->has_warm_uuid) { printf(",\"warm_uuid_hex\":"); emit_uuid(c->warm_uuid); }
        if(c->has_warm_side) printf(",\"warm_side\":\"%s\"",c->warm_side==TAPE_SIDE_B?"B":"A");
        printf("}");
    }
    printf("],\"events\":[");
    for(i=0;i<g_event_count;i++) {
        const struct event *e=&g_events[i];
        if(i) printf(",");
        if(e->has_extent) printf("{\"phase\":\"%s\",\"op\":\"%s\",\"lba\":%lu,\"count\":%lu,\"rc\":%d}",e->phase,e->op,(unsigned long)e->lba,(unsigned long)e->count,e->rc);
        else printf("{\"phase\":\"%s\",\"op\":\"%s\",\"rc\":%d}",e->phase,e->op,e->rc);
    }
    printf("],\"event_overflow\":%s}\n",g_event_overflow?"true":"false");
}

static unsigned char g_inst[INSTANCE_BYTES];
static unsigned char g_play[TAPE_PLAY_RING_MIN];
static unsigned char g_rec[TAPE_REC_RING_MIN];
static int16_t g_pcm[512];
static int16_t g_warm_data[32];
static tape_dev g_dev;

static tape_result open_instance(tape **out) {
    size_t need=tape_instance_size();
    if(need>sizeof g_inst){fprintf(stderr,"instance too large: %zu\n",need);return TAPE_ERR_INVALID_ARG;}
    g_dev.read=dev_read;g_dev.write=dev_write;g_dev.flush=dev_flush;g_dev.ctx=NULL;g_dev.block_count=g_media.blocks;
    return tape_init(g_inst,need,&g_dev,g_play,sizeof g_play,g_rec,sizeof g_rec,out);
}
static struct call_rec *record_mount(tape *t, tape_side side, uint64_t resume, const tape_warm_start *warm, bool present) {
    struct call_rec *c; tape_result r; g_phase="mount"; r=tape_mount(t,side,resume,warm);
    c=push_call("mount","tape_mount",r);
    if(c){
        c->side=side==TAPE_SIDE_B?"B":"A"; c->has_resume=true;c->resume_frame=resume;
        c->has_warm_present=true;c->warm_present=present;
        if(present && warm){
            c->has_warm_data_present=true;c->warm_data_present=warm->data!=NULL;
            c->has_warm_data_bytes=true;c->warm_data_bytes=warm->data_bytes;
            c->has_warm_valid_frames=true;c->warm_valid_frames=warm->valid_frames;
            c->has_warm_start_frame=true;c->warm_start_frame=warm->start_frame;
            c->has_warm_uuid=true;memcpy(c->warm_uuid,warm->uuid,16);
            c->has_warm_side=true;c->warm_side=warm->side;
        }
    }
    return c;
}
static tape_result step_info(tape *t,const char *phase,struct call_rec **outc) {
    tape_info info; tape_result r; struct call_rec *c;
    memset(&info,0,sizeof info);g_phase=phase;r=tape_get_info(t,&info);c=push_call(phase,"tape_get_info",r);
    if(c && r==TAPE_OK){
        c->has_warm_used=true;c->warm_used=info.warm_start_used;
        c->has_total_frames=true;c->total_frames=info.total_frames;
        c->has_entry_count=true;c->entry_count=info.entry_count;
        c->has_entries_free=true;c->entries_free=info.entries_free;
        c->has_side_b_valid=true;c->side_b_valid=info.side_b_valid;
    }
    if(outc) *outc=c;
    return r;
}
static tape_result step_tell(tape *t,const char *phase) {
    uint64_t f=0; tape_result r; struct call_rec *c;g_phase=phase;r=tape_tell(t,&f);c=push_call(phase,"tape_tell",r);
    if(c&&r==TAPE_OK){c->has_frame=true;c->frame=f;} return r;
}
static tape_result step_status(tape *t,const char *phase) {
    tape_status_t st; tape_result r; struct call_rec *c;memset(&st,0,sizeof st);g_phase=phase;r=tape_status(t,&st);c=push_call(phase,"tape_status",r);
    if(c&&r==TAPE_OK){c->has_at_end=true;c->at_end=st.at_end;c->has_at_start=true;c->at_start=st.at_start;} return r;
}
static tape_result step_rate(tape *t,const char *phase,int32_t rate) {
    tape_result r;struct call_rec*c;g_phase=phase;r=tape_set_rate(t,rate);c=push_call(phase,"tape_set_rate",r);if(c){c->has_rate=true;c->rate=rate;}return r;
}
static tape_result step_seek(tape *t,const char *phase,uint64_t f) {
    tape_result r;struct call_rec*c;g_phase=phase;r=tape_seek(t,f);c=push_call(phase,"tape_seek",r);if(c){c->has_frame=true;c->frame=f;}return r;
}
static tape_result step_set_side(tape *t,const char *phase,tape_side side) {
    tape_result r;struct call_rec*c;g_phase=phase;r=tape_set_side(t,side);c=push_call(phase,"tape_set_side",r);if(c)c->side=side==TAPE_SIDE_B?"B":"A";return r;
}
static tape_result step_arm(tape *t) {
    tape_result r;struct call_rec*c;g_phase="arm";r=tape_arm(t,TAPE_REC_OVERWRITE);c=push_call("arm","tape_arm",r);if(c)c->mode="overwrite";return r;
}
static tape_result step_abort(tape *t) { tape_result r;g_phase="abort";r=tape_abort(t);push_call("abort","tape_abort",r);return r; }
static tape_result step_unmount(tape *t) { tape_result r;g_phase="unmount";r=tape_unmount(t,NULL);push_call("unmount","tape_unmount",r);return r; }
static tape_result step_render(tape *t,const char *phase,uint32_t n) {
    uint32_t rendered=0; size_t before=g_event_count; tape_result r; struct call_rec*c;
    g_phase=phase;r=tape_render(t,g_pcm,n,&rendered);c=push_call(phase,"tape_render",r);
    if(c){c->has_requested=true;c->requested=n;c->has_rendered=true;c->rendered=rendered;c->has_evcount=true;c->evcount=(unsigned long)(g_event_count-before);}
    return r;
}
static int service_to_idle(tape *t,const char *phase) {
    bool more=true;uint32_t iter=0;
    while(more){
        tape_result r;struct call_rec*c;
        if(iter++>=SERVICE_GUARD){fprintf(stderr,"service guard\n");return -1;}
        g_phase=phase;r=tape_service(t,SERVICE_BUDGET,&more);c=push_call(phase,"tape_service",r);
        if(c){c->has_more_work=true;c->more_work=more;}
        if(r!=TAPE_OK)return -1;
    }
    return 0;
}

enum script { SC_PLAYING,SC_IDLE,SC_SAME,SC_DEGRADED,SC_DEGRADED_SAME,SC_ARMED,SC_WARM };
struct warm_row { bool present; bool data_present; uint32_t data_bytes; uint32_t valid_frames; uint32_t start_frame; uint64_t resume_frame; bool uuid_bad; tape_side warm_side; };
struct case_row { const char *id; enum script script; tape_side mount_side; struct warm_row warm; };

#define WNONE {false,false,0u,0u,0u,0u,false,TAPE_SIDE_A}
static const struct case_row g_cases[] = {
    {"SS-PLAYING-A-TO-B",SC_PLAYING,TAPE_SIDE_A,WNONE},
    {"SS-IDLE-A-TO-B",SC_IDLE,TAPE_SIDE_A,WNONE},
    {"SS-SAME-A",SC_SAME,TAPE_SIDE_A,WNONE},
    {"SS-DEGRADED-B",SC_DEGRADED,TAPE_SIDE_A,WNONE},
    {"SS-DEGRADED-SAME-A",SC_DEGRADED_SAME,TAPE_SIDE_A,WNONE},
    {"SS-ARMED-BUSY",SC_ARMED,TAPE_SIDE_B,WNONE},
    {"WARM-NULL",SC_WARM,TAPE_SIDE_A,{false,false,0u,0u,0u,40u,false,TAPE_SIDE_A}},
    {"WARM-DATA-NULL",SC_WARM,TAPE_SIDE_A,{true,false,64u,16u,32u,40u,false,TAPE_SIDE_A}},
    {"WARM-ZERO-FRAMES",SC_WARM,TAPE_SIDE_A,{true,true,64u,0u,32u,32u,false,TAPE_SIDE_A}},
    {"WARM-SHORT-BUF",SC_WARM,TAPE_SIDE_A,{true,true,63u,16u,32u,40u,false,TAPE_SIDE_A}},
    {"WARM-PAST-END",SC_WARM,TAPE_SIDE_A,{true,true,64u,16u,250u,250u,false,TAPE_SIDE_A}},
    {"WARM-U32-OVERFLOW",SC_WARM,TAPE_SIDE_A,{true,true,64u,16u,0xfffffff8u,250u,false,TAPE_SIDE_A}},
    {"WARM-RESUME-OUT",SC_WARM,TAPE_SIDE_A,{true,true,64u,16u,32u,48u,false,TAPE_SIDE_A}},
    {"WARM-UUID",SC_WARM,TAPE_SIDE_A,{true,true,64u,16u,32u,40u,true,TAPE_SIDE_A}},
    {"WARM-SIDE",SC_WARM,TAPE_SIDE_A,{true,true,64u,16u,32u,40u,false,TAPE_SIDE_B}},
    {"WARM-VALID-METADATA",SC_WARM,TAPE_SIDE_A,{true,true,64u,16u,32u,40u,false,TAPE_SIDE_A}}
};

static int run_case(const struct case_row *row) {
    tape *t=NULL; struct call_rec *mountc=NULL; tape_result r; struct call_rec *info_c=NULL;
    if(open_instance(&t)!=TAPE_OK)return 1;
    if(row->script==SC_WARM){
        tape_warm_start w; const tape_warm_start *wp=NULL; unsigned i;
        memset(&w,0,sizeof w);
        if(row->warm.present){
            w.data=row->warm.data_present?(const void *)g_warm_data:NULL;
            w.data_bytes=row->warm.data_bytes;w.valid_frames=row->warm.valid_frames;w.start_frame=row->warm.start_frame;w.side=row->warm.warm_side;
            for(i=0;i<16;i++)w.uuid[i]=row->warm.uuid_bad?0xffu:(unsigned char)i;
            wp=&w;
        }
        mountc=record_mount(t,row->mount_side,row->warm.resume_frame,wp,row->warm.present);
        if(!mountc || strcmp(mountc->result,"TAPE_OK")!=0)return 1;
        r=step_info(t,"info",&info_c); if(r!=TAPE_OK)return 1;
        if(mountc && info_c && info_c->has_warm_used){mountc->has_warm_used=true;mountc->warm_used=info_c->warm_used;}
        if(step_tell(t,"tell")!=TAPE_OK)return 1;
        if(step_unmount(t)!=TAPE_OK)return 1;
        return 0;
    }

    mountc=record_mount(t,row->mount_side,0u,NULL,false);
    if(!mountc || strcmp(mountc->result,"TAPE_OK")!=0)return 1;

    if(row->script==SC_PLAYING){
        if(step_rate(t,"pre-rate",65536)!=TAPE_OK)return 1;
        if(service_to_idle(t,"pre-service")!=0)return 1;
        if(step_render(t,"pre-render-to-end",256u)!=TAPE_OK)return 1;
        if(step_status(t,"pre-status")!=TAPE_OK)return 1;
        if(step_set_side(t,"set-side",TAPE_SIDE_B)!=TAPE_OK)return 1;
        if(step_tell(t,"post-switch-tell")!=TAPE_OK)return 1;
        if(step_status(t,"post-switch-status")!=TAPE_OK)return 1;
        if(step_info(t,"post-switch-info",NULL)!=TAPE_OK)return 1;
        (void)step_render(t,"pre-service-render",1u);
        if(service_to_idle(t,"post-switch-service")!=0)return 1;
        if(step_render(t,"post-service-render",1u)!=TAPE_OK)return 1;
        if(step_tell(t,"post-service-tell")!=TAPE_OK)return 1;
    } else if(row->script==SC_IDLE){
        if(step_seek(t,"pre-seek",10u)!=TAPE_OK)return 1;
        if(step_set_side(t,"set-side",TAPE_SIDE_B)!=TAPE_OK)return 1;
        if(step_tell(t,"post-switch-tell")!=TAPE_OK)return 1;
        if(step_status(t,"post-switch-status")!=TAPE_OK)return 1;
        if(step_info(t,"post-switch-info",NULL)!=TAPE_OK)return 1;
        if(step_rate(t,"post-switch-rate",65536)!=TAPE_OK)return 1;
        (void)step_render(t,"pre-service-render",1u);
        if(service_to_idle(t,"post-switch-service")!=0)return 1;
        if(step_render(t,"post-service-render",1u)!=TAPE_OK)return 1;
        if(step_tell(t,"post-service-tell")!=TAPE_OK)return 1;
    } else if(row->script==SC_SAME || row->script==SC_DEGRADED_SAME){
        if(step_seek(t,"pre-seek",10u)!=TAPE_OK)return 1;
        if(step_set_side(t,"set-side",TAPE_SIDE_A)!=TAPE_OK)return 1;
        if(step_tell(t,"post-switch-tell")!=TAPE_OK)return 1;
        if(step_info(t,"post-switch-info",NULL)!=TAPE_OK)return 1;
    } else if(row->script==SC_DEGRADED){
        if(step_seek(t,"pre-seek",10u)!=TAPE_OK)return 1;
        if(step_info(t,"pre-info",NULL)!=TAPE_OK)return 1;
        if(step_set_side(t,"set-side",TAPE_SIDE_B)!=TAPE_ERR_NO_VALID_INDEX)return 1;
        if(step_tell(t,"post-refusal-tell")!=TAPE_OK)return 1;
        if(step_info(t,"post-refusal-info",NULL)!=TAPE_OK)return 1;
    } else if(row->script==SC_ARMED){
        if(step_seek(t,"pre-seek",10u)!=TAPE_OK)return 1;
        if(step_arm(t)!=TAPE_OK)return 1;
        if(step_set_side(t,"set-side",TAPE_SIDE_A)!=TAPE_ERR_BUSY)return 1;
        if(step_tell(t,"post-refusal-tell")!=TAPE_OK)return 1;
        if(step_info(t,"post-refusal-info",NULL)!=TAPE_OK)return 1;
        if(step_abort(t)!=TAPE_OK)return 1;
    }
    if(step_unmount(t)!=TAPE_OK)return 1;
    return 0;
}

int main(int argc,char **argv) {
    const struct case_row *row=NULL; size_t i; int failed;
    if(argc!=4){fprintf(stderr,"usage: %s CASE_ID INPUT.vo08 OUTPUT.vo08\n",argv[0]);return 2;}
    for(i=0;i<sizeof g_cases/sizeof g_cases[0];i++)if(strcmp(argv[1],g_cases[i].id)==0){row=&g_cases[i];break;}
    if(!row){fprintf(stderr,"unknown case %s\n",argv[1]);return 2;}
    if(media_load(argv[2])!=0)return 2;
    failed=run_case(row);
    if(media_store(argv[3])!=0)failed=1;
    emit_json();
    return failed?1:0;
}
