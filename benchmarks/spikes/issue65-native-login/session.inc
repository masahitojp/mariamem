/* Experiment-only native entry. All normal protocol bytes come from upstream. */
#include "sql_acl.h"
#include "sql_parse.h"
#include <cerrno>

typedef size_t (*spike_read_cb)(void *, unsigned char *, size_t);
typedef size_t (*spike_write_cb)(void *, const unsigned char *, size_t);
struct SpikeVio {
  Vio vio;
  void *ctx;
  spike_read_cb read_cb;
  spike_write_cb write_cb;
  int error;
  bool blocking, timedout;
};
static SpikeVio *spike_v(Vio *v) { return reinterpret_cast<SpikeVio *>(v); }
static size_t spike_read(Vio *v, uchar *p, size_t n) {
  auto *s=spike_v(v);size_t r=s->read_cb(s->ctx,p,n);
  s->error=(r==size_t(-1))?EIO:0;return r;
}
static size_t spike_write(Vio *v,const uchar *p,size_t n) {
  auto *s=spike_v(v);size_t r=s->write_cb(s->ctx,p,n);
  s->error=(r==size_t(-1))?EIO:0;return r;
}
static int spike_errno(Vio *v){return spike_v(v)->error;}
static my_bool spike_false(Vio *){return false;}
static my_bool spike_timeout(Vio *v){return spike_v(v)->timedout;}
static int spike_set_timeout(Vio *,uint,my_bool){return 0;}
static int spike_blocking(Vio *v,my_bool b,my_bool *old){*old=spike_v(v)->blocking;spike_v(v)->blocking=b;return 0;}
static my_bool spike_is_blocking(Vio *v){return spike_v(v)->blocking;}
static int spike_nop(Vio *){return 0;}
static int spike_keepalive(Vio *,my_bool){return 0;}
static my_bool spike_peer(Vio *,char *p,uint16 *port,size_t n){snprintf(p,n,"127.0.0.1");*port=0;return false;}
static void spike_addr(Vio *,struct sockaddr_storage *a){memset(a,0,sizeof(*a));auto *s=(struct sockaddr_in*)a;s->sin_family=AF_INET;s->sin_addr.s_addr=htonl(INADDR_LOOPBACK);}
static int spike_close(Vio *v){v->state=VIO_STATE_CLOSED;return 0;}
static int spike_shutdown(Vio *v,int){v->state=VIO_STATE_SHUTDOWN;return 0;}
static my_bool spike_connected(Vio *v){return v->state==VIO_STATE_ACTIVE;}
static int spike_wait(Vio *,enum enum_vio_io_event,int){return 1;}
static void spike_delete(Vio *v){spike_close(v);}
extern unsigned long mariamem_spike_decodes;
extern "C" unsigned long mariamem_spike_decode_count(){return mariamem_spike_decodes;}
extern "C" int mariamem_spike_session(void *ctx,spike_read_cb read_cb,spike_write_cb write_cb)
{
  SpikeVio transport{};Vio *vio=&transport.vio;
  transport.ctx=ctx;transport.read_cb=read_cb;transport.write_cb=write_cb;transport.blocking=true;
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
  thd->thread_stack=(char*)&thd;thd->store_globals();
  auto *s=thd->security_ctx;s->host_or_ip=s->host=(char*)my_localhost;
  if(my_net_init(&thd->net,vio,thd,MYF(MY_THREAD_SPECIFIC)))return 11;
  int result=0;
  if(acl_authenticate(thd,0))result=12;
  else {
    // The product ignores placeholder credentials and executes as its fixed root.
    my_free(const_cast<char *>(s->user));s->user=my_strdup(PSI_NOT_INSTRUMENTED,"root",MYF(0));
    s->host_or_ip=s->host=(char*)my_localhost;
    strmake_buf(s->priv_user,"root");strmake_buf(s->priv_host,"localhost");
  }
  thd->protocol->end_statement();
  if(net_flush(&thd->net))result=13;
  while(!result){
    if(thd->client_params!=NULL)abort();
    auto rc=do_command(thd,true);
    if(rc==DISPATCH_COMMAND_CLOSE_CONNECTION){if(thd->net.error)result=16;break;}
    if(rc!=DISPATCH_COMMAND_SUCCESS){result=14;break;}
    if(net_flush(&thd->net)){result=15;break;}
  }
  server_threads.erase(thd);
  net_end(&thd->net);thd->net.vio=NULL;
  delete thd;
  set_current_thd(NULL);if(old)old->store_globals();
  fprintf(stderr,"SESSION_RETIRED result=%d decodes=%lu\n",result,mariamem_spike_decodes);
  return result;
}
