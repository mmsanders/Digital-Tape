/* Internal ordinary-file comparison adapter. Compile only; run once after admission.
 * Reference includes exact unmodified current-main tapectl.c. Composition includes
 * extracted candidate bodies. No shipping command/flag reaches this translation unit.
 */
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <io.h>
#include <fcntl.h>
#include <inttypes.h>
#include "observe.h"
#include "core.h"
#define main unused_shipping_main
#ifdef IM_REFERENCE
#include "reference/tapectl.c"
#else
#include "../tapectl.c"
#endif
#undef main
#undef hport_open
#undef hport_create
#undef hport_read
#undef hport_write
#undef hport_flush
#undef hport_close

#ifndef IM_HEAD
#error Build must bind exact source head
#endif
#define IMAGE_BYTES UINT64_C(20972032)
static const char *const cases[]={"positive","initial-query-failure","unknown-safety","policy-refusal",
 "provision-failure","load-failure","verify-failure","media-change","media-remove","query-failure"};
static const char *const phases[]={"safety","provision","load","commit","verify"};
struct context {
 const char *name,*fixture;
 char image[2048];
 FILE *journal;
 enum im_phase phase;
 unsigned opens;
 enum im_phase io_phase;
 unsigned read_ordinal,write_ordinal,flush_ordinal;
 int faulted,wav_opened,bind_rc,have_view;
 unsigned findings;
 struct wav_in in;
};
static struct context *current;
static void die(const char *why) { fprintf(stderr,"INTERNAL ADAPTER STOP: %s\n",why); exit(92); }
static void file_key(struct hport *p,char out[96]) {
 BY_HANDLE_FILE_INFORMATION i;
 if(!GetFileInformationByHandle(p->h,&i)) die("ordinary file identity unavailable");
 snprintf(out,96,"%08lx:%08lx:%08lx",(unsigned long)i.dwVolumeSerialNumber,(unsigned long)i.nFileIndexHigh,(unsigned long)i.nFileIndexLow);
}
static void event(struct hport *p,const char *op,const char *extra) {
 char key[96];file_key(p,key);
 fprintf(current->journal,"{\"op\":\"%s\",\"session\":\"%p\",\"file_id\":\"%s\",\"stdout_position\":%lld%s}\n",op,p->h,key,(long long)_ftelli64(stdout),extra?extra:"");
 if(fflush(current->journal)) die("journal flush");
}
#ifndef IM_REFERENCE
static void phase_event(enum im_phase ph) {
 char b[180];current->phase=ph;
 snprintf(b,sizeof b,",\"phase\":\"%s\",\"write_callback_null\":%s",phases[ph],g_tgt.dev.write==NULL?"true":"false");
 event(&g_tgt.hp,"phase",b);
}
static void failure_event(void) {
 char b[96];snprintf(b,sizeof b,",\"phase\":\"%s\"",phases[current->phase]);event(&g_tgt.hp,"phase-failure",b);
}
#endif

static void existing_facts(struct hport *p) {
 BY_HANDLE_FILE_INFORMATION info;
 FILE_STANDARD_INFO standard;
 if(!GetFileInformationByHandle(p->h,&info) ||
    !GetFileInformationByHandleEx(p->h,FileStandardInfo,&standard,sizeof standard)) die("ordinary file admission unavailable");
 if(info.dwFileAttributes & (FILE_ATTRIBUTE_REPARSE_POINT|FILE_ATTRIBUTE_SPARSE_FILE|FILE_ATTRIBUTE_DIRECTORY)) die("sparse/reparse/directory admission");
 if(p->is_device || p->bytes!=IMAGE_BYTES || standard.EndOfFile.QuadPart!=(LONGLONG)IMAGE_BYTES ||
    standard.AllocationSize.QuadPart<(LONGLONG)IMAGE_BYTES) die("ordinary materialized fixed allocation admission");
}
int im_hport_open(struct hport *p,const char *path,int device,int writable) {
 int status;
 if(current==NULL || device!=0 || strcmp(path,current->image)!=0 || hport_classify(path)!=HPORT_REGULAR) die("only owned existing ordinary image permitted");
#ifndef IM_REFERENCE
 if(current->opens!=0u) die("retained session reopen forbidden");
#endif
 ++current->opens;
 status=hport_open(p,path,0,writable);
 if(status==0) {
  existing_facts(p);
  event(p,"authorized-open",writable?",\"access\":\"readwrite\",\"ordinary_file\":true,\"existing_only\":true":",\"access\":\"read\",\"ordinary_file\":true,\"existing_only\":true");
 }
 return status;
}
/* Test-only admission substitution. Neither hport_create/hport_os_create nor
 * truncation/sparse/device APIs are invoked. Driver proves original zero twins. */
int im_hport_create(struct hport *p,const char *path,uint64_t bytes) {
 if(bytes!=IMAGE_BYTES) die("unexpected requested image geometry");
 return im_hport_open(p,path,0,1);
}
static unsigned ordinal(const char *op) {
 if(current->io_phase!=current->phase) {
  current->io_phase=current->phase;
  current->read_ordinal=current->write_ordinal=current->flush_ordinal=0u;
 }
 if(!strcmp(op,"read")) return ++current->read_ordinal;
 if(!strcmp(op,"write")) return ++current->write_ordinal;
 return ++current->flush_ordinal;
}
static int declared_fault(const char *operation,uint64_t offset) {
 int inject=0;
 if(current->faulted) return 0;
 if(!strcmp(current->name,"provision-failure")) inject=current->phase==IM_PROVISION && !strcmp(operation,"write");
 if(!strcmp(current->name,"load-failure")) inject=current->phase==IM_LOAD && !strcmp(operation,"read");
 if(!strcmp(current->name,"verify-failure")) inject=current->phase==IM_VERIFY && !strcmp(operation,"read") && offset>=UINT64_C(34816)*512u;
 if(inject) current->faulted=1;
 return inject;
}
static void io_event(struct hport *p,const char *op,uint64_t off,size_t n,int rc,unsigned ord,int injected,DWORD error) {
 char fields[384];
 snprintf(fields,sizeof fields,",\"phase\":\"%s\",\"offset\":%" PRIu64 ",\"length\":%zu,\"ordinal\":%u,\"result\":%d,\"fault_injected\":%s,\"os_error_code\":%lu",phases[current->phase],off,n,ord,rc,injected?"true":"false",(unsigned long)error);
 event(p,op,fields);
}
int im_hport_read(struct hport *p,uint64_t off,void *buf,size_t n) {
 int rc;DWORD error=0;unsigned ord=ordinal("read");int injected=declared_fault("read",off);
 if(injected) {
  struct hport borrowed=*p;
  hport_os_invalidate(&borrowed); /* COPY only; live owner remains valid. */
  rc=hport_os_read(&borrowed,off,buf,n);error=GetLastError();
 } else rc=hport_read(p,off,buf,n);
 io_event(p,"read",off,n,rc,ord,injected,error);return rc;
}
int im_hport_write(struct hport *p,uint64_t off,const void *buf,size_t n) {
 int rc;DWORD error=0;unsigned ord=ordinal("write");int injected=declared_fault("write",off);
 if(current->phase==IM_VERIFY) die("write after readonly binding");
 if(off>IMAGE_BYTES || n>IMAGE_BYTES-off) die("fixed image growth");
 if(injected) {
  struct hport borrowed=*p;
  hport_os_invalidate(&borrowed);
  rc=hport_os_write(&borrowed,off,buf,n);error=GetLastError();
 } else rc=hport_write(p,off,buf,n);
 io_event(p,"write",off,n,rc,ord,injected,error);return rc;
}
int im_hport_flush(struct hport *p) {
 unsigned ord=ordinal("flush");int rc=hport_flush(p);
 io_event(p,"flush",0,0,rc,ord,0,0);return rc;
}
int im_hport_close(struct hport *p) {
 existing_facts(p);event(p,"close",NULL);return hport_close(p);
}
static struct im_result answer(int code,const char *id,enum im_phase phase,const char *op,const char *error) {
 struct im_result r={code,id,phase,op,error};return r;
}
static int query(void *v,struct im_facts *f,const char **err) {
 struct context *c=v;f->known=IM_ALL_FACTS;f->pass=IM_ALL_FACTS;
 if(!strcmp(c->name,"initial-query-failure")){*err="MODEL_REQUIRED_QUERY_FAILURE";return -1;}
 if(!strcmp(c->name,"unknown-safety"))f->known&=~IM_SIZE;
 if(!strcmp(c->name,"policy-refusal"))f->pass&=~IM_WHOLE;
 return 0;
}
static enum im_watch monitor(void *v,void *session,enum im_phase ph,const char **err) {
 struct context *c=v;char b[180];
 if(session!=&g_tgt)die("callback session changed");
 c->phase=ph;
 if(ph!=IM_LOAD)return IM_UNCHANGED;
 if(!strcmp(c->name,"media-change") || !strcmp(c->name,"media-remove")) {
  int removed=!strcmp(c->name,"media-remove");
  snprintf(b,sizeof b,",\"phase\":\"load\",\"reason\":\"%s\"",removed?"removed":"changed");
#ifndef IM_REFERENCE
  event(&g_tgt.hp,"media-change",b);
#else
  fprintf(c->journal,"{\"op\":\"modeled-reference-boundary\"%s}\n",b);
#endif
  return removed?IM_REMOVED:IM_CHANGED;
 }
 if(!strcmp(c->name,"query-failure")) {
  *err="MODEL_OPTIONAL_QUERY_FAILURE";
#ifndef IM_REFERENCE
  event(&g_tgt.hp,"query-failure",",\"phase\":\"load\"");
#else
  fputs("{\"op\":\"modeled-reference-query-failure\",\"phase\":\"load\"}\n",c->journal);
#endif
  return IM_QUERY_ERROR;
 }
 return IM_UNCHANGED;
}
#ifndef IM_REFERENCE
static void unmount_owned(void) {
 if(g_t){uint64_t pos;(void)tape_unmount(g_t,&pos);g_t=NULL;}
}
static struct im_result op_open(void *v,void **session) {
 struct context *c=v;int rc;memset(&g_tgt,0,sizeof g_tgt);
 rc=im_hport_open(&g_tgt.hp,c->image,0,1);
 if(rc)return answer(2,NULL,IM_SAFETY,"ordinary open",NULL);
 g_tgt.open=1;g_tgt.sectors=IMAGE_BYTES/512u;*session=&g_tgt;
 return answer(0,NULL,IM_SAFETY,NULL,NULL);
}
static struct im_result phase_result(int rc,enum im_phase ph) {
 if(rc){unmount_owned();if(current->wav_opened){wav_close_read(&current->in);current->wav_opened=0;}failure_event();}
 return answer(rc,NULL,ph,NULL,NULL);
}
static struct im_result op_provision(void *v,void *session) {
 uint8_t uuid[16];tape_dev dry;tape_result r;int rc;struct context *c=v;
 if(c!=current || session!=&g_tgt)die("provision session");
 phase_event(IM_PROVISION);
 if(parse_uuid("00112233445566778899aabbccddeeff",uuid))die("fixed UUID");
 dry.read=dry_rw;dry.write=dry_w;dry.flush=dry_flush;dry.ctx=NULL;dry.block_count=6145u;
 r=tape_format(&dry,uuid,7u,"Internal",9u);
 rc=r==TAPE_ERR_IO?provision_existing(40961u,6145u,"Internal",uuid,7u,9u,0):engine_fail("provision",r==TAPE_OK?TAPE_ERR_IO:r);
 return phase_result(rc,IM_PROVISION);
}
static struct im_result op_load(void *v,void *session) {
 struct context *c=v;char err[96];int rc;
 if(c!=current || session!=&g_tgt)die("load session");
 phase_event(IM_LOAD);
 rc=wav_open_read(&c->in,c->fixture,err,sizeof err);
 if(rc)return phase_result(usage(err),IM_LOAD);
 c->wav_opened=1;rc=target_borrow_write(&g_tgt,c->image);
 if(!rc)rc=load_existing_feed(&c->in);
 return phase_result(rc,IM_LOAD);
}
static struct im_result op_commit(void *v,void *session) {
 struct context *c=v;int rc;
 if(c!=current || session!=&g_tgt)die("commit session");
 phase_event(IM_COMMIT);
 rc=commit_loaded();if(!rc)rc=run_long(1);
 if(c->wav_opened){wav_close_read(&c->in);c->wav_opened=0;}
 unmount_owned();return phase_result(rc,IM_COMMIT);
}
static const tape_dev *op_bind(void *v,void *session) {
 struct context *c=v;
 if(c!=current || session!=&g_tgt)die("readonly session");
 c->phase=IM_VERIFY;
 c->bind_rc=target_borrow_verify(&g_tgt,c->image,&c->findings,&c->have_view);
 if(c->bind_rc)die("unexpected readonly bind error");
 event(&g_tgt.hp,"bind-verify",g_tgt.dev.write==NULL?",\"write_callback_null\":true":",\"write_callback_null\":false");return &g_tgt.dev;
}
static struct im_result op_verify(void *v,void *session,const tape_dev *ro) {
 struct context *c=v;int rc;
 if(c!=current || session!=&g_tgt || ro!=&g_tgt.dev)die("verify session");
 phase_event(IM_VERIFY);
 rc=verify_existing(c->findings,c->have_view);return phase_result(rc,IM_VERIFY);
}
static struct im_result op_close(void *v,void *session) {
 struct context *c=v;int rc;
 if(c!=current || session!=&g_tgt)die("close session");
 if(c->wav_opened){wav_close_read(&c->in);c->wav_opened=0;}rc=finish(0);
 return answer(rc,NULL,c->phase,NULL,NULL);
}
#else
static struct im_result reference(void) {
 struct context *c=current;struct im_facts f;const char *error=NULL;int rc;enum im_watch w;
 char *prov[]={c->image,"--label","Internal","--length-s","9","--uuid","00112233445566778899aabbccddeeff","--epoch","7","--image-bytes","20972032"};
 char *load[]={c->image,(char *)c->fixture};char *verify[]={c->image};
 if(query(c,&f,&error))return answer(1,"HOST_QUERY_FAILED",IM_SAFETY,"media_query",error);
 if(f.known!=IM_ALL_FACTS)return answer(1,NULL,IM_SAFETY,"unknown required safety facts",NULL);
 if(!(f.pass&IM_WHOLE))return answer(3,"REFUSE_NOT_WHOLE_DEVICE",IM_SAFETY,NULL,NULL);
 c->phase=IM_PROVISION;rc=cmd_provision(11,prov);rc=finish(rc);
 if(rc)return answer(rc,NULL,IM_PROVISION,NULL,NULL);
 w=monitor(c,&g_tgt,IM_LOAD,&error);
 /* Reference has just closed its provision command. monitor needs no I/O; its
    journal event uses retained known identity, so use a separate plain event here. */
 if(w!=IM_UNCHANGED)return answer(1,w==IM_QUERY_ERROR?"HOST_QUERY_FAILED":"CARD_CHANGED",IM_LOAD,w==IM_QUERY_ERROR?"media_query":NULL,error);
 c->phase=IM_LOAD;rc=cmd_load(2,load);rc=finish(rc);
 if(rc)return answer(rc,NULL,IM_LOAD,NULL,NULL);
 c->phase=IM_VERIFY;rc=cmd_verify(1,verify);rc=finish(rc);
 return answer(rc,NULL,IM_VERIFY,NULL,NULL);
}
#endif
static void json_nullable(FILE *f,const char *s) {if(s)fprintf(f,"\"%s\"",s);else fputs("null",f);}
int main(int argc,char **argv) {
 unsigned i;const char *mode;
#ifdef IM_REFERENCE
 mode="reference";
#else
 mode="composition";
#endif
 if(argc!=3)die("adapter ROOT FIXTURE");
 for(i=0;i<sizeof cases/sizeof cases[0];i++) {
  struct context c;struct im_result r;char base[2048],path[2200];FILE *result;
  memset(&c,0,sizeof c);memset(&g_tgt,0,sizeof g_tgt);g_t=NULL;c.name=cases[i];c.fixture=argv[2];current=&c;
  if(snprintf(base,sizeof base,"%s/%s.%s",argv[1],cases[i],mode)>=(int)sizeof base)die("path length");
  if(snprintf(c.image,sizeof c.image,"%s.img",base)>=(int)sizeof c.image)die("image path length");
  snprintf(path,sizeof path,"%s.stdout.bin",base);if(!freopen(path,"wb",stdout))die("stdout capture");
  snprintf(path,sizeof path,"%s.stderr.bin",base);if(!freopen(path,"wb",stderr))abort();
  setvbuf(stdout,NULL,_IONBF,0);setvbuf(stderr,NULL,_IONBF,0);_setmode(_fileno(stdout),_O_BINARY);_setmode(_fileno(stderr),_O_BINARY);
  snprintf(path,sizeof path,"%s.events.jsonl",base);c.journal=fopen(path,"wb");if(!c.journal)die("journal open");
#ifdef IM_REFERENCE
  r=reference();
#else
  {struct im_ops ops={&c,query,op_open,op_provision,op_load,op_commit,op_bind,op_verify,monitor,op_close};r=im_compose(&ops);}
#endif
  snprintf(path,sizeof path,"%s.result.json",base);result=fopen(path,"wb");if(!result)die("result open");
  fprintf(result,"{\"source_head\":\"%s\",\"case\":\"%s\",\"mode\":\"%s\",\"exit\":%d,\"open_attempt_count\":%u,\"fault_triggered\":%s,\"terminal\":",IM_HEAD,c.name,mode,r.exit_code,c.opens,c.faulted?"true":"false");
  if(!r.exit_code)fputs("null",result);else {fputs("{\"id\":",result);json_nullable(result,r.id);fprintf(result,",\"phase\":\"%s\",\"op\":",phases[r.phase]);json_nullable(result,r.op);fputs(",\"os_error\":",result);json_nullable(result,r.os_error);fputs("}",result);}
  fputs("}\n",result);if(fclose(result)||fclose(c.journal))die("close evidence");
 }
 return 0;
}
