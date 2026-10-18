/* EXPERIMENT ONLY: public embedded mysql_stmt API, bounded type/row coverage.
 * Wire command payload is session-owned; no MYSQL pointers cross the boundary.
 * Upstream recipe insertion lives in guest/experimental.patch. */
#include <stdint.h>
static char *wire_error(unsigned int, const char *, const char *);
static int wire_state(buf_t *);
static int wire_name(buf_t *, const char *, const char *, unsigned int);
#define PST_LIMIT 64
#define PST_BYTES 4096
static _Thread_local struct pst_entry {
  MYSQL_STMT *stmt;
  uint32_t id;
  unsigned short types[PST_LIMIT];
  int have_types;
  unsigned char long_data[PST_LIMIT];
  char *long_bytes[PST_LIMIT];
  size_t long_lengths[PST_LIMIT];
} pst_entries[PST_LIMIT];
static _Thread_local uint32_t pst_next;
static uint32_t pst_u32(const unsigned char *p) {
  return (uint32_t)p[0] | (uint32_t)p[1]<<8 | (uint32_t)p[2]<<16 | (uint32_t)p[3]<<24;
}
static void pst_clear(void) {
  for (int i=0;i<PST_LIMIT;i++) {
    if (pst_entries[i].stmt) mysql_stmt_close(pst_entries[i].stmt);
    for(int j=0;j<PST_LIMIT;j++) free(pst_entries[i].long_bytes[j]);
    memset(&pst_entries[i],0,sizeof(pst_entries[i]));
  }
  /* Do not reuse IDs when this worker's session slot is reopened. */
}
static int pst_fields(buf_t *b, MYSQL_RES *res) {
  unsigned int n=res ? mysql_num_fields(res) : 0;
  MYSQL_FIELD *fs=res ? mysql_fetch_fields(res) : NULL;
  char t[160];
  if (buf_puts(b,"[")) return 1;
  for (unsigned int i=0;i<n;i++) {
    MYSQL_FIELD *f=fs+i;
    if ((i && buf_putc(b,',')) || buf_putc(b,'{') ||
        wire_name(b,"name",f->name,f->name_length) || buf_putc(b,',') ||
        wire_name(b,"org_name",f->org_name,f->org_name_length) || buf_putc(b,',') ||
        wire_name(b,"table",f->table,f->table_length) || buf_putc(b,',') ||
        wire_name(b,"org_table",f->org_table,f->org_table_length) || buf_putc(b,',') ||
        wire_name(b,"db",f->db,f->db_length) || buf_putc(b,',') ||
        wire_name(b,"catalog",f->catalog,f->catalog_length)) return 1;
    snprintf(t,sizeof(t),",\"type\":%u,\"charset\":%u,\"flags\":%u,\"length\":%lu,\"decimals\":%u}",
      (unsigned)f->type,f->charsetnr,f->flags,f->length,f->decimals);
    if(buf_puts(b,t)) return 1;
  }
  return buf_putc(b,']');
}
static char *pst_error(MYSQL_STMT *s) {
  return wire_error(mysql_stmt_errno(s),mysql_stmt_error(s),mysql_stmt_sqlstate(s));
}
static int pst_len(const unsigned char **p,const unsigned char *end,size_t *n) {
  if(*p==end) return 1;
  unsigned c=*(*p)++; unsigned width=0;
  if(c<251) { *n=c; return 0; }
  if(c==252) width=2; else if(c==253) width=3; else if(c==254) width=8; else return 1;
  if((size_t)(end-*p)<width) return 1;
  uint64_t x=0;
  for(unsigned i=0;i<width;i++) x|=(uint64_t)(*p)[i]<<(8*i);
  *p+=width;
  if(x>1048576) return 1;
  *n=(size_t)x; return 0;
}
static char *pst_call(MYSQL *db,const unsigned char *p,size_t size) {
  const unsigned char *end=p+size;
  if(!size) return wire_error(1235,"empty prepared command","HY000");
  unsigned cmd=*p++;
  struct pst_entry *e=NULL;
  buf_t b={0}; char t[192]; MYSQL_RES *meta=NULL;
  if(cmd==27) {
    if((size_t)(end-p)!=2) return wire_error(1235,"unsupported prepared opcode","42000");
    unsigned option=(unsigned)p[0] | (unsigned)p[1]<<8;
    if(mysql_set_server_option(db,(enum enum_mysql_set_option)option))
      return wire_error(mysql_errno(db),mysql_error(db),mysql_sqlstate(db));
    if(buf_puts(&b,"{\"ok\":true") || wire_state(&b) || buf_putc(&b,'}')) goto oom;
    return b.p;
  }
  if(cmd==22) {
    for(int i=0;i<PST_LIMIT;i++) if(!pst_entries[i].stmt) { e=pst_entries+i; break; }
    if(!e || pst_next==UINT32_MAX) return wire_error(1461,"spike statement limit","42000");
    MYSQL_STMT *s=mysql_stmt_init(db);
    if(!s) return wire_error(2000,"mysql_stmt_init failed","HY000");
    if(mysql_stmt_prepare(s,(const char *)p,(unsigned long)(end-p))) {
      char *err=pst_error(s); mysql_stmt_close(s); return err;
    }
    if(mysql_stmt_param_count(s)>PST_LIMIT || mysql_stmt_field_count(s)>PST_LIMIT) {
      mysql_stmt_close(s); return wire_error(1235,"spike parameter/column limit","42000");
    }
    e->stmt=s; e->id=++pst_next;
    meta=mysql_stmt_result_metadata(s);
    if(mysql_stmt_field_count(s) && !meta) {char *err=pst_error(s);mysql_stmt_close(s);memset(e,0,sizeof(*e));return err;}
    snprintf(t,sizeof(t),"{\"ok\":true,\"stmt_id\":%u,\"param_count\":%lu,\"param_metadata_null\":%s,\"columns\":",
      e->id,mysql_stmt_param_count(s),mysql_stmt_param_metadata(s)==NULL ? "true":"false");
    if(buf_puts(&b,t) || pst_fields(&b,meta) || wire_state(&b) || buf_putc(&b,'}')) goto oom;
    if(meta) mysql_free_result(meta);
    return b.p;
  }
  if((size_t)(end-p)<4) return wire_error(1235,"short prepared handle","HY000");
  uint32_t id=pst_u32(p); p+=4;
  for(int i=0;i<PST_LIMIT;i++) if(pst_entries[i].stmt && pst_entries[i].id==id) {e=pst_entries+i;break;}
  if(!e) return wire_error(1243,"unknown prepared statement handle","HY000");
  MYSQL_STMT *s=e->stmt;
  if(cmd==25) {
    if(p!=end) return wire_error(1235,"long close packet","HY000");
    int rc=mysql_stmt_close(s);
    for(int j=0;j<PST_LIMIT;j++) free(e->long_bytes[j]);
    memset(e,0,sizeof(*e));
    if(rc) return wire_error(2000,"mysql_stmt_close failed","HY000");
  } else if(cmd==26) {
    if(p!=end) return wire_error(1235,"long reset packet","HY000");
    if(mysql_stmt_reset(s)) return pst_error(s);
    for(int j=0;j<PST_LIMIT;j++) {free(e->long_bytes[j]);e->long_bytes[j]=NULL;e->long_lengths[j]=0;}
    memset(e->long_data,0,sizeof(e->long_data));
  } else if(cmd==24) {
    if((size_t)(end-p)<2) return wire_error(1235,"short long-data packet","HY000");
    unsigned idx=p[0]|(unsigned)p[1]<<8; p+=2;
    if(idx>=mysql_stmt_param_count(s)) return wire_error(1210,"long-data parameter index","HY000");
    size_t len=(size_t)(end-p);
    if(len>1048576-e->long_lengths[idx]) return wire_error(1235,"spike long-data limit","42000");
    char *next=realloc(e->long_bytes[idx],e->long_lengths[idx]+len+1);
    if(!next) return NULL;
    memcpy(next+e->long_lengths[idx],p,len);e->long_bytes[idx]=next;
    e->long_lengths[idx]+=len;e->long_data[idx]=1;
  } else if(cmd==23) {
    if((size_t)(end-p)<5 || p[0]!=0 || pst_u32(p+1)!=1)
      return wire_error(1235,"spike supports non-cursor execute only","42000");
    p+=5;
    unsigned n=(unsigned)mysql_stmt_param_count(s);
    MYSQL_BIND binds[PST_LIMIT]; unsigned long lengths[PST_LIMIT]; my_bool nulls[PST_LIMIT];
    union { unsigned long long u64; double f64; unsigned char bytes[8]; } values[PST_LIMIT];
    memset(binds,0,sizeof(binds)); memset(values,0,sizeof(values));
    if(n) {
      size_t bitmap=(n+7)/8;
      if((size_t)(end-p)<bitmap+1) return wire_error(1235,"short execute bitmap","HY000");
      const unsigned char *nullmap=p; p+=bitmap;
      unsigned fresh=*p++;
      if(fresh>1 || (fresh && (size_t)(end-p)<2*n)) return wire_error(1235,"invalid type descriptors","HY000");
      if(fresh) {
        for(unsigned i=0;i<n;i++) { e->types[i]=p[0]|(unsigned short)p[1]<<8; p+=2; }
        e->have_types=1;
      }
      if(!e->have_types) return wire_error(1210,"missing parameter types","HY000");
      for(unsigned i=0;i<n;i++) {
        MYSQL_BIND *v=binds+i; unsigned ty=e->types[i]&255;
        if(e->types[i]&0x7f00) return wire_error(1235,"unsupported parameter flags","HY000");
        nulls[i]=!!(nullmap[i/8]&(1<<(i%8))) || ty==MYSQL_TYPE_NULL;
        v->is_null=nulls+i; v->is_unsigned=!!(e->types[i]&0x8000); v->buffer_type=(enum enum_field_types)ty;
        v->length=lengths+i; lengths[i]=0;
        if(nulls[i] || e->long_data[i]) continue;
        unsigned width= ty==1 ? 1 : (ty==2 || ty==13) ? 2 : (ty==3 || ty==9 || ty==4) ? 4 : (ty==8 || ty==5) ? 8 : 0;
        if(width) {
          if((size_t)(end-p)<width) return wire_error(1235,"short numeric value","HY000");
          memcpy(values[i].bytes,p,width); p+=width;
          v->buffer=values[i].bytes; v->buffer_length=width;
        } else if(ty==0 || ty==15 || ty==16 || ty==246 || (ty>=249 && ty<=254)) {
          size_t len;
          if(pst_len(&p,end,&len) || (size_t)(end-p)<len) return wire_error(1235,"short string value","HY000");
          v->buffer=(void *)p; v->buffer_length=lengths[i]=(unsigned long)len; p+=len;
        } else return wire_error(1235,"parameter type outside spike","42000");
      }
      if(mysql_stmt_bind_param(s,binds)) return pst_error(s);
    }
    if(p!=end) return wire_error(1235,"trailing execute bytes","HY000");
    for(unsigned i=0;i<n;i++) if(e->long_data[i])
      if(mysql_stmt_send_long_data(s,i,e->long_bytes[i],(unsigned long)e->long_lengths[i])) return pst_error(s);
    int exec_rc=mysql_stmt_execute(s);
    for(unsigned i=0;i<n;i++) {free(e->long_bytes[i]);e->long_bytes[i]=NULL;e->long_lengths[i]=0;}
    memset(e->long_data,0,sizeof(e->long_data));
    if(exec_rc) return pst_error(s);
    if(mysql_stmt_store_result(s)) return pst_error(s);
    meta=mysql_stmt_result_metadata(s);
    if(mysql_stmt_field_count(s) && !meta) {mysql_stmt_free_result(s);return pst_error(s);}
    unsigned cols=meta ? mysql_num_fields(meta) : 0;
    if(cols>PST_LIMIT) { if(meta) mysql_free_result(meta); mysql_stmt_free_result(s); return wire_error(1235,"result columns outside spike","42000"); }
    snprintf(t,sizeof(t),"{\"ok\":true,\"affected\":\"%llu\",\"insert_id\":\"%llu\"",
      (unsigned long long)mysql_stmt_affected_rows(s),(unsigned long long)mysql_stmt_insert_id(s));
    if(buf_puts(&b,t) || wire_state(&b)) goto oom;
    if(cols) {
      if(buf_puts(&b,",\"columns\":") || pst_fields(&b,meta) || buf_puts(&b,",\"rows\":[")) goto oom;
      MYSQL_BIND outs[PST_LIMIT]; unsigned long lens[PST_LIMIT]; my_bool ns[PST_LIMIT], errs[PST_LIMIT];
      /* Heap buffer avoids adding 256KiB to each worker's Wasm stack. */
      char *data=calloc(cols,PST_BYTES);
      if(!data) goto oom;
      memset(outs,0,sizeof(outs));
      memset(lens,0,sizeof(lens)); memset(ns,0,sizeof(ns)); memset(errs,0,sizeof(errs));
      for(unsigned i=0;i<cols;i++) {
        outs[i].buffer_type=MYSQL_TYPE_BLOB; outs[i].buffer=data+i*PST_BYTES; outs[i].buffer_length=PST_BYTES;
        outs[i].length=lens+i; outs[i].is_null=ns+i; outs[i].error=errs+i;
      }
      if(mysql_stmt_bind_result(s,outs)) { free(data); goto stmt_fail; }
      unsigned rows=0; int rc;
      while((rc=mysql_stmt_fetch(s))==0) {
        if(rows>=1024) { free(data); goto bounds; }
        if((rows++ && buf_putc(&b,',')) || buf_putc(&b,'[')) {free(data); goto oom;}
        for(unsigned i=0;i<cols;i++) {
          if(!ns[i] && (lens[i]>PST_BYTES || errs[i])) {free(data); goto bounds;}
          if((i && buf_putc(&b,',')) || (ns[i] ? buf_puts(&b,"null") :
             (buf_puts(&b,"{\"$h\":") || buf_put_json_hex(&b,data+i*PST_BYTES,lens[i]) || buf_putc(&b,'}')))) {free(data); goto oom;}
        }
        if(buf_putc(&b,']')) {free(data);goto oom;}
      }
      free(data);
      if(rc==MYSQL_DATA_TRUNCATED) goto bounds;
      if(rc!=MYSQL_NO_DATA) goto stmt_fail;
      if(buf_putc(&b,']')) goto oom;
    }
    if(meta) { mysql_free_result(meta);meta=NULL; }
    mysql_stmt_free_result(s);
    if(buf_putc(&b,'}')) goto oom;
    return b.p;
stmt_fail: {
      char *err=pst_error(s); if(meta)mysql_free_result(meta);mysql_stmt_free_result(s);free(b.p);return err;
    }
bounds:
    if(meta)mysql_free_result(meta);mysql_stmt_free_result(s);free(b.p);
    return wire_error(1235,"result size outside spike","42000");
  } else return wire_error(1235,"unsupported prepared opcode","42000");
  if(buf_puts(&b,"{\"ok\":true") || wire_state(&b) || buf_putc(&b,'}')) goto oom;
  return b.p;
oom:
  if(meta)mysql_free_result(meta);free(b.p);return NULL;
}
