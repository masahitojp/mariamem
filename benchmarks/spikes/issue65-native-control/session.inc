/* Experiment-only native entry. All normal protocol bytes come from upstream. */
#include "sql_acl.h"
#include "sql_parse.h"
#include "transaction.h"
#include <cerrno>
#include "mariamem_control_abi.h"

typedef size_t (*spike_read_cb)(void *, unsigned char *, size_t);
typedef size_t (*spike_write_cb)(void *, const unsigned char *, size_t);
struct SpikeVio {
  Vio vio;
  void *ctx;
  spike_read_cb read_cb;
  spike_write_cb write_cb;
  SpikeIO *io;
  int error;
  bool blocking, timedout;
};
static SpikeVio *spike_v(Vio *v) { return reinterpret_cast<SpikeVio *>(v); }
static size_t spike_read(Vio *v, uchar *p, size_t n) {
  auto *s=spike_v(v);size_t r=s->read_cb(s->ctx,p,n);
  s->error=(r==size_t(-1))?s->io->error(s->ctx):0;return r;
}
static size_t spike_write(Vio *v,const uchar *p,size_t n) {
  auto *s=spike_v(v);size_t r=s->write_cb(s->ctx,p,n);
  s->error=(r==size_t(-1))?s->io->error(s->ctx):0;return r;
}
static int spike_errno(Vio *v){return spike_v(v)->error;}
static my_bool spike_false(Vio *){return false;}
static my_bool spike_timeout(Vio *v){return spike_v(v)->error==ETIMEDOUT;}
static int spike_set_timeout(Vio *,uint,my_bool){return 0;}
static int spike_blocking(Vio *v,my_bool b,my_bool *old){*old=spike_v(v)->blocking;spike_v(v)->blocking=b;return 0;}
static my_bool spike_is_blocking(Vio *v){return spike_v(v)->blocking;}
static int spike_nop(Vio *){return 0;}
static int spike_keepalive(Vio *,my_bool){return 0;}
static my_bool spike_peer(Vio *,char *p,uint16 *port,size_t n){snprintf(p,n,"127.0.0.1");*port=0;return false;}
static void spike_addr(Vio *,struct sockaddr_storage *a){memset(a,0,sizeof(*a));auto *s=(struct sockaddr_in*)a;s->sin_family=AF_INET;s->sin_addr.s_addr=htonl(INADDR_LOOPBACK);}
static int spike_close(Vio *v){v->state=VIO_STATE_CLOSED;spike_v(v)->io->close(spike_v(v)->ctx);return 0;}
static int spike_shutdown(Vio *v,int){v->state=VIO_STATE_SHUTDOWN;spike_v(v)->io->close(spike_v(v)->ctx);return 0;}
static my_bool spike_connected(Vio *v){return v->state==VIO_STATE_ACTIVE;}
static int spike_wait(Vio *v,enum enum_vio_io_event e,int ms){auto *s=spike_v(v);return s->io->wait(s->ctx,int(e),ms);}
static void spike_delete(Vio *v){spike_close(v);}
extern unsigned long mariamem_spike_decodes;
extern "C" unsigned long mariamem_spike_decode_count(){return __atomic_load_n(&mariamem_spike_decodes,__ATOMIC_RELAXED);}
// The caller pins the THD under its admission lock until UNREGISTER_THD.
extern "C" void mariamem_spike_kill(void *p) { static_cast<THD*>(p)->awake(KILL_CONNECTION); }
bool mariamem_spike_dispatch_start(THD *thd, enum enum_server_command command) {
 if(!thd->mariamem_native_wire)return false;
 auto *s=spike_v(thd->net.vio);
 return s->io->event(s->ctx,EXECUTE_START,thd,unsigned(command)) != 0;
}
extern "C" int mariamem_spike_control_session(SpikeIO *io)
{
  SpikeVio transport{};Vio *vio=&transport.vio;
  transport.ctx=io->ctx;transport.read_cb=io->read;transport.write_cb=io->write;transport.io=io;transport.blocking=true;
  vio->mysql_socket.fd=INVALID_SOCKET;vio->type=VIO_TYPE_MEMORY;
  vio->state=VIO_STATE_ACTIVE;vio->desc="spike memory queue";vio->localhost=true;
  vio->read=spike_read;vio->write=spike_write;vio->vioerrno=spike_errno;
  vio->should_retry=spike_false;vio->was_timeout=spike_timeout;vio->timeout=spike_set_timeout;
  vio->vioblocking=spike_blocking;vio->is_blocking=spike_is_blocking;
  vio->fastsend=spike_nop;vio->viokeepalive=spike_keepalive;
  vio->peer_addr=spike_peer;vio->in_addr=spike_addr;vio->vioclose=spike_close;
  vio->shutdown=spike_shutdown;vio->is_connected=spike_connected;vio->has_data=spike_false;
  vio->io_wait=spike_wait;vio->viodelete=spike_delete;
  THD *old=current_thd;THD *thd=create_spike_thd(0,true);
  // C API normally initializes these later; native sessions never bind them.
  thd->mysql=NULL;thd->client_params=NULL;
  thd->client_param_count=thd->client_stmt_id=0;
  thd->extra_data=NULL;thd->extra_length=0;
  thd->thread_stack=(char*)&thd;thd->store_globals();
  auto *s=thd->security_ctx;s->host_or_ip=s->host=(char*)my_localhost;
  int result=0;
  if(my_net_init(&thd->net,vio,thd,MYF(MY_THREAD_SPECIFIC)))result=11;
  if(io->event(io->ctx,REGISTER_THD,thd,0))result=17;
  if(!result && acl_authenticate(thd,0))result=12;
  else if(!result) {
    // The product ignores placeholder credentials and executes as its fixed root.
    my_free(const_cast<char *>(s->user));s->user=my_strdup(PSI_NOT_INSTRUMENTED,"root",MYF(0));
    s->host_or_ip=s->host=(char*)my_localhost;
    strmake_buf(s->priv_user,"root");strmake_buf(s->priv_host,"localhost");
  }
  if(!result) {
    thd->protocol->end_statement();
    if(net_flush(&thd->net))result=13;
    else if(io->event(io->ctx,AUTH_COMPLETE,thd,thd->server_status))result=17;
  }
  while(!result){
    if(thd->client_params!=NULL)abort();
    if(io->event(io->ctx,ARM_COMMAND,thd,thd->server_status)){result=17;break;}
    auto rc=do_command(thd,true);
    if(rc==DISPATCH_COMMAND_CLOSE_CONNECTION){
      net_flush(&thd->net);
      io->event(io->ctx,CONNECTION_COMPLETE,thd,thd->server_status);
      if(thd->net.error)result=16;
      break;
    }
    if(rc!=DISPATCH_COMMAND_SUCCESS){result=14;break;}
    if(net_flush(&thd->net)){result=15;break;}
    if(io->event(io->ctx,COMMAND_COMPLETE,thd,thd->server_status)){result=17;break;}
  }
  int rollback_error=trans_rollback(thd);
  if(rollback_error)result=19;
  io->event(io->ctx,CLEANUP_RESULT,thd,unsigned(rollback_error!=0));
  io->event(io->ctx,UNREGISTER_THD,thd,thd->net.last_errno ? thd->net.last_errno : thd->get_stmt_da()->sql_errno());
  thd->cleanup();
  server_threads.erase(thd);
  net_end(&thd->net);thd->net.vio=NULL;
  delete thd;
  set_current_thd(NULL);if(old)old->store_globals();
  fprintf(stderr,"SESSION_RETIRED result=%d decodes=%lu\n",result,mariamem_spike_decode_count());
  return result;
}
