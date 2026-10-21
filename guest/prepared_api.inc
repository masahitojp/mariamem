/* Public embedded statement owner. Included after wire_core in wire_api.inc.
 * Internal request: 'P','S',version1,operation,u32 generation,u32 handle,
 * u32 payload length,payload. Never export MYSQL_STMT pointers.
 */
#define PS_VERSION 1
#define PS_HEADER 16
#define PS_MAX_ENVELOPE (32U << 20)
#define PS_MAX_SQL (1U << 20)
_Static_assert(sizeof(float)==4 && sizeof(double)==8,"prepared numeric ABI requires IEEE-width native buffers");

typedef struct ps_slot {
  union {
    uint8_t u8; uint16_t u16; uint32_t u32; uint64_t u64;
    float f32; double f64; MYSQL_TIME time;
  } value;
  unsigned char *bytes;
  unsigned long length;
  my_bool null_value, error;
} ps_slot;
typedef struct ps_buffers {
  MYSQL_BIND *bind;
  ps_slot *slots;
  unsigned int count;
} ps_buffers;
static void ps_buffers_free(ps_buffers *p)
{
  if (!p) return;
  if (p->slots) for (unsigned int i=0; i<p->count; ++i) free(p->slots[i].bytes);
  free(p->slots); free(p->bind); free(p);
}
static ps_buffers *ps_buffers_new(unsigned int count)
{
  ps_buffers *p= calloc(1,sizeof(*p));
  if (!p) return NULL;
  p->count= count;
  if (count) {
    p->bind= calloc(count,sizeof(*p->bind));
    p->slots= calloc(count,sizeof(*p->slots));
    if (!p->bind || !p->slots) {ps_buffers_free(p);return NULL;}
    for (unsigned int i=0;i<count;++i) {
      p->bind[i].length= &p->slots[i].length;
      p->bind[i].is_null= &p->slots[i].null_value;
      p->bind[i].error= &p->slots[i].error;
    }
  }
  return p;
}
typedef struct ps_entry {
  MYSQL_STMT *stmt;
  uint32_t id;
  ps_buffers *parameters, *results;
  struct ps_entry *next;
} ps_entry;
static _Thread_local ps_entry *ps_entries;
static _Thread_local uint32_t ps_generation, ps_next;

static uint32_t ps_u32(const unsigned char *p)
{
  return (uint32_t)p[0] | (uint32_t)p[1]<<8 | (uint32_t)p[2]<<16 | (uint32_t)p[3]<<24;
}

/* All statements must be destroyed before their owning MYSQL is closed. */
static int ps_clear(void)
{
  int failed= 0;
  while (ps_entries) {
    ps_entry *e= ps_entries;
    ps_entries= e->next;
    if (e->stmt && mysql_stmt_close(e->stmt)) failed= 1;
    ps_buffers_free(e->parameters);ps_buffers_free(e->results);
    free(e);
  }
  return failed;
}
static int ps_begin_session(void)
{
  if (ps_entries || ps_generation == UINT32_MAX) return 1;
  ++ps_generation;
  ps_next= 0;
  return 0;
}
static ps_entry *ps_find(uint32_t id)
{
  for (ps_entry *e= ps_entries; e; e= e->next)
    if (e->id == id) return e;
  return NULL;
}
static char *ps_error(MYSQL_STMT *stmt)
{
  unsigned int code= mysql_stmt_errno(stmt);
  if (!code) return NULL;
  return wire_error(code, mysql_stmt_error(stmt), mysql_stmt_sqlstate(stmt));
}
static int ps_columns(buf_t *b, MYSQL_RES *res)
{
  unsigned int count= res ? mysql_num_fields(res) : 0;
  MYSQL_FIELD *fields= res ? mysql_fetch_fields(res) : NULL;
  char text[160];
  if (count && !fields) return 1;
  if (buf_putc(b, '[')) return 1;
  for (unsigned int i= 0; i < count; ++i) {
    MYSQL_FIELD *f= fields+i;
    if ((i && buf_putc(b, ',')) || buf_putc(b, '{') ||
        wire_name(b,"name",f->name,f->name_length) || buf_putc(b,',') ||
        wire_name(b,"org_name",f->org_name,f->org_name_length) || buf_putc(b,',') ||
        wire_name(b,"table",f->table,f->table_length) || buf_putc(b,',') ||
        wire_name(b,"org_table",f->org_table,f->org_table_length) || buf_putc(b,',') ||
        wire_name(b,"db",f->db,f->db_length) || buf_putc(b,',') ||
        wire_name(b,"catalog",f->catalog,f->catalog_length)) return 1;
    snprintf(text,sizeof(text),",\"type\":%u,\"charset\":%u,\"flags\":%u,\"length\":%lu,\"decimals\":%u}",
             (unsigned)f->type,f->charsetnr,f->flags,f->length,f->decimals);
    if (buf_puts(b,text) || b->n > PS_MAX_ENVELOPE-512) return 1;
  }
  return buf_putc(b, ']');
}

/* Positive = fixed numeric width, -1 = bytes, -2 = MYSQL_TIME, -3 = invalid. */
static int ps_shape(unsigned int type)
{
  switch (type) {
  case 1: return 1;
  case 2: case 13: return 2;
  case 3: case 9: case 4: return 4;
  case 8: case 5: return 8;
  case 6: return 0;
  case 7: case 10: case 11: case 12: case 14: return -2;
  case 0: case 15: case 16: case 246: case 247: case 248:
  case 249: case 250: case 251: case 252: case 253: case 254: case 255: return -1;
  default: return -3;
  }
}
static int ps_temporal_length(unsigned int type, size_t n)
{
  if (!n) return 1;
  if (type==10 || type==14) return n==4;
  if (type==11) return n==8 || n==12;
  return n==4 || n==7 || n==11;
}
static uint64_t ps_uint(const unsigned char *p,unsigned int n)
{
  uint64_t v=0;
  for (unsigned int i=0;i<n;++i) v|=(uint64_t)p[i]<<(8*i);
  return v;
}
static void ps_little(unsigned char *p,uint64_t v,unsigned int n)
{
  for (unsigned int i=0;i<n;++i) p[i]=(unsigned char)(v>>(8*i));
}
/* Check the entire independent envelope before allocation or native binding. */
static int ps_check_values(const unsigned char *data,size_t size,unsigned long count)
{
  if (size<4 || size>PS_MAX_ENVELOPE-PS_HEADER || count>UINT16_MAX || ps_u32(data)!=count) return 1;
  const unsigned char *p=data+4;size_t remaining=size-4;
  for (unsigned long i=0;i<count;++i) {
    if (remaining<8 || (p[1]&~3U) || p[2] || p[3]) return 1;
    uint32_t n=ps_u32(p+4);int shape=ps_shape(p[0]);
    if (n>remaining-8 || shape==-3) return 1;
    if (p[1]&2) {if (n) return 1;}
    else if (shape>=0) {if (!shape || n!=(unsigned int)shape) return 1;}
    else if (shape==-2 && !ps_temporal_length(p[0],n)) return 1;
    p+=8+n;remaining-=8+n;
  }
  return remaining!=0;
}
static void ps_time_input(MYSQL_TIME *t,unsigned int type,const unsigned char *p,unsigned int n)
{
  memset(t,0,sizeof(*t));
  t->time_type= type==11 ? MYSQL_TIMESTAMP_TIME : (type==10 || type==14 ? MYSQL_TIMESTAMP_DATE : MYSQL_TIMESTAMP_DATETIME);
  if (!n) return;
  if (type==11) {
    t->neg=p[0]!=0;t->day=ps_u32(p+1);t->hour=p[5];t->minute=p[6];t->second=p[7];
    if (n==12) t->second_part=ps_u32(p+8);
  } else {
    t->year=(unsigned int)ps_uint(p,2);t->month=p[2];t->day=p[3];
    if (n>=7) {t->hour=p[4];t->minute=p[5];t->second=p[6];}
    if (n==11) t->second_part=ps_u32(p+7);
  }
}
static ps_buffers *ps_parameters(const unsigned char *data,unsigned int count)
{
  ps_buffers *p=ps_buffers_new(count);
  if (!p) return NULL;
  const unsigned char *v=data+4;
  for (unsigned int i=0;i<count;++i) {
    unsigned int type=v[0],n=ps_u32(v+4);int shape=ps_shape(type);
    MYSQL_BIND *b=p->bind+i;ps_slot *s=p->slots+i;
    b->buffer_type=(enum enum_field_types)type;b->is_unsigned=(v[1]&1)!=0;s->null_value=(v[1]&2)!=0;s->length=n;
    const unsigned char *bytes=v+8;
    if (s->null_value) b->buffer=&s->value;
    else if (shape>0) {
      uint64_t bits=ps_uint(bytes,n);
      if (type==4) {uint32_t f=(uint32_t)bits;memcpy(&s->value.f32,&f,4);b->buffer=&s->value.f32;}
      else if (type==5) {memcpy(&s->value.f64,&bits,8);b->buffer=&s->value.f64;}
      else if (n==1) {s->value.u8=(uint8_t)bits;b->buffer=&s->value.u8;}
      else if (n==2) {s->value.u16=(uint16_t)bits;b->buffer=&s->value.u16;}
      else if (n==4) {s->value.u32=(uint32_t)bits;b->buffer=&s->value.u32;}
      else {s->value.u64=bits;b->buffer=&s->value.u64;}
      b->buffer_length=n;
    } else if (shape==-2) {
      ps_time_input(&s->value.time,type,bytes,n);b->buffer=&s->value.time;b->buffer_length=sizeof(MYSQL_TIME);
      /* Embedded emb_insert_params reads *length as a native structure size,
       * not as the client protocol's 0/4/7/8/11/12-byte temporal body length. */
      s->length=sizeof(MYSQL_TIME);
    } else {
      s->bytes=malloc(n ? n : 1);
      if (!s->bytes) {ps_buffers_free(p);return NULL;}
      if (n) memcpy(s->bytes,bytes,n);
      b->buffer=s->bytes;b->buffer_length=n;
    }
    v+=8+n;
  }
  return p;
}
static unsigned int ps_time_output(unsigned char *p,const MYSQL_TIME *t,unsigned int type)
{
  if (type==11) {
    if (!t->day && !t->hour && !t->minute && !t->second && !t->second_part) return 0;
    p[0]=t->neg!=0;ps_little(p+1,(uint64_t)t->day+t->hour/24,4);
    p[5]=(unsigned char)(t->hour%24);p[6]=(unsigned char)t->minute;p[7]=(unsigned char)t->second;
    if (t->second_part) {ps_little(p+8,t->second_part,4);return 12;}
    return 8;
  }
  if (!t->year && !t->month && !t->day && !t->hour && !t->minute && !t->second && !t->second_part) return 0;
  ps_little(p,t->year,2);p[2]=(unsigned char)t->month;p[3]=(unsigned char)t->day;
  if (type==10 || type==14) return 4;
  p[4]=(unsigned char)t->hour;p[5]=(unsigned char)t->minute;p[6]=(unsigned char)t->second;
  if (t->second_part) {ps_little(p+7,t->second_part,4);return 11;}
  return t->hour || t->minute || t->second ? 7 : 4;
}
static ps_buffers *ps_result_bindings(MYSQL_RES *meta)
{
  unsigned int count=mysql_num_fields(meta);MYSQL_FIELD *fields=mysql_fetch_fields(meta);
  if (count && !fields) return NULL;
  ps_buffers *p=ps_buffers_new(count);
  if (!p) return NULL;
  for (unsigned int i=0;i<count;++i) {
    MYSQL_BIND *b=p->bind+i;ps_slot *s=p->slots+i;unsigned int type=fields[i].type;int shape=ps_shape(type);
    if (shape==-3) {ps_buffers_free(p);return NULL;}
    b->buffer_type=(enum enum_field_types)type;b->is_unsigned=(fields[i].flags&32)!=0;
    b->buffer=&s->value;
    if (shape>=0) {
      if (type==13) b->buffer_type=MYSQL_TYPE_SHORT;
      if (type==9) b->buffer_type=MYSQL_TYPE_LONG;
      b->buffer_length=(unsigned long)shape;
    } else if (shape==-2) {
      if (type==14) b->buffer_type=MYSQL_TYPE_DATE;
      b->buffer_length=sizeof(MYSQL_TIME);
    } else {
      /* One-byte scratch satisfies the pinned API's nonzero-buffer assertion;
       * actual lengths drive checked fetch_column, never truncated success. */
      b->buffer_type=MYSQL_TYPE_BLOB;b->buffer=&s->value.u8;b->buffer_length=1;
    }
  }
  return p;
}
static int ps_cell(buf_t *b,MYSQL_STMT *stmt,ps_buffers *p,MYSQL_FIELD *fields,unsigned int i)
{
  ps_slot *s=p->slots+i;unsigned int type=fields[i].type;int shape=ps_shape(type);
  unsigned char raw[12];const unsigned char *bytes=raw;unsigned long n=0;
  if (s->null_value) return buf_puts(b,"null");
  if (shape>=0) {
    if (!shape || s->error || s->length!=(unsigned long)shape) return 1;
    n=(unsigned long)shape;
    if (type==4) {uint32_t v;memcpy(&v,&s->value.f32,4);ps_little(raw,v,4);}
    else if (type==5) {uint64_t v;memcpy(&v,&s->value.f64,8);ps_little(raw,v,8);}
    else if (n==1) ps_little(raw,s->value.u8,1);
    else if (n==2) ps_little(raw,s->value.u16,2);
    else if (n==4) ps_little(raw,s->value.u32,4);
    else ps_little(raw,s->value.u64,8);
  } else if (shape==-2) {
    if (s->error || s->length!=sizeof(MYSQL_TIME)) return 1;
    n=ps_time_output(raw,&s->value.time,type);
  } else {
    n=s->length;
    if (b->n>PS_MAX_ENVELOPE-512 || n>(PS_MAX_ENVELOPE-512-b->n)/2) return 1;
    if (n) {
      unsigned char *full=malloc(n);
      if (!full) return 1;
      MYSQL_BIND column=p->bind[i];my_bool null_value=0,error=0;unsigned long length=0;
      column.buffer=full;column.buffer_length=n;column.length=&length;column.is_null=&null_value;column.error=&error;
      int failed=mysql_stmt_fetch_column(stmt,&column,i,0) || null_value || error || length!=n;
      if (!failed) failed=buf_puts(b,"{\"$h\":") || buf_put_json_hex(b,(const char *)full,n) || buf_putc(b,'}');
      free(full);return failed;
    }
  }
  if (b->n>PS_MAX_ENVELOPE-512 || n>(PS_MAX_ENVELOPE-512-b->n)/2) return 1;
  return buf_puts(b,"{\"$h\":") || buf_put_json_hex(b,(const char *)bytes,n) || buf_putc(b,'}');
}
static char *ps_execute(MYSQL *db,ps_entry *e,const unsigned char *data,size_t size)
{
  unsigned long count=mysql_stmt_param_count(e->stmt);
  if (ps_check_values(data,size,count)) return wire_error(1835,"invalid prepared typed values","HY000");
  ps_buffers *params=ps_parameters(data,(unsigned int)count);
  if (!params) return NULL;
  if (count && mysql_stmt_bind_param(e->stmt,params->bind)) {
    /* A failed bind may have copied pointers before reporting an API error.
     * Destroy the native handle before releasing either binding allocation.
     * NULL fails the transport rather than presenting this partial bind as OK. */
    mysql_stmt_close(e->stmt);e->stmt=NULL;
    ps_buffers_free(params);return NULL;
  }
  ps_buffers_free(e->parameters);e->parameters=params;
  if (mysql_stmt_execute(e->stmt)) {
    /* Preserve the native error before cleanup clears it. An EXECUTE may
     * already have produced a result; never leave it blocking the next SQL
     * command, and never retry SQL to repair changed result metadata. */
    char *error=ps_error(e->stmt);
    if (mysql_stmt_errno(e->stmt)==2008) {
      /* Metadata allocation can have replaced/freed the old field arena.
       * Do not reuse that partially rebuilt handle after out-of-memory. */
      mysql_stmt_close(e->stmt);e->stmt=NULL;free(error);return NULL;
    }
    if (mysql_stmt_free_result(e->stmt) || (db->server_status&8)) {free(error);return NULL;}
    return error;
  }
  unsigned int columns=mysql_stmt_field_count(e->stmt);
  MYSQL_RES *meta=columns ? mysql_stmt_result_metadata(e->stmt) : NULL;
  if (columns && (!meta || columns>UINT16_MAX || mysql_num_fields(meta)!=columns)) {if(meta)mysql_free_result(meta);return NULL;}
  buf_t b={0};char text[200];char *error=NULL;
  snprintf(text,sizeof(text),"{\"ok\":true,\"binary_rows\":true,\"statement_id\":%u,\"affected\":\"%llu\",\"insert_id\":\"%llu\"",
           e->id,(unsigned long long)mysql_stmt_affected_rows(e->stmt),(unsigned long long)mysql_stmt_insert_id(e->stmt));
  int failed=buf_puts(&b,text);
  if (!failed && meta) {
    ps_buffers *bindings=ps_result_bindings(meta);
    if (!bindings) failed=1;
    else if (mysql_stmt_bind_result(e->stmt,bindings->bind)) {
      mysql_stmt_close(e->stmt);e->stmt=NULL;ps_buffers_free(bindings);failed=1;
    } else {
      ps_buffers_free(e->results);e->results=bindings;
      if (mysql_stmt_store_result(e->stmt)) {error=ps_error(e->stmt);failed=1;}
      if (!failed) failed=buf_puts(&b,",\"columns\":") || ps_columns(&b,meta) || buf_puts(&b,",\"rows\":[");
      unsigned int first=1;
      while (!failed) {
        int rc=mysql_stmt_fetch(e->stmt);
        if (rc==MYSQL_NO_DATA) break;
        if (rc!=0 && rc!=MYSQL_DATA_TRUNCATED) {error=ps_error(e->stmt);failed=1;break;}
        failed=(!first && buf_putc(&b,',')) || buf_putc(&b,'[');first=0;
        for (unsigned int i=0;!failed && i<columns;++i)
          failed=(i && buf_putc(&b,',')) || ps_cell(&b,e->stmt,bindings,mysql_fetch_fields(meta),i);
        if (!failed) failed=buf_putc(&b,']');
      }
      if (!failed) failed=buf_putc(&b,']');
    }
  }
  if (meta) mysql_free_result(meta);
  if (e->stmt && mysql_stmt_free_result(e->stmt)) failed=1;
  /* P3 will add explicit result chains. Never discard MORE_RESULTS as success. */
  if (db->server_status&8) {free(error);error=NULL;failed=1;}
  if (!failed) failed=wire_state(&b) || buf_putc(&b,'}') || b.n>PS_MAX_ENVELOPE-128;
  if (failed) {free(b.p);return error;}
  free(error);return b.p;
}
static char *ps_prepare(MYSQL *db, const unsigned char *sql, size_t size)
{
  if (!size || size > PS_MAX_SQL) return wire_error(1153,"prepared SQL length must be 1..1048576 bytes","08S01");
  if (ps_next == UINT32_MAX) return wire_error(1461,"prepared statement identifiers exhausted","42000");
  MYSQL_STMT *stmt= mysql_stmt_init(db);
  if (!stmt) return NULL;
  if (mysql_stmt_prepare(stmt,(const char *)sql,(unsigned long)size)) {
    char *error= ps_error(stmt);
    mysql_stmt_close(stmt);
    return error;
  }
  unsigned long params= mysql_stmt_param_count(stmt);
  unsigned int columns= mysql_stmt_field_count(stmt);
  if (params > UINT16_MAX || columns > UINT16_MAX) {
    mysql_stmt_close(stmt);
    return wire_error(1235,"prepared metadata exceeds protocol field width","42000");
  }
  MYSQL_RES *meta= mysql_stmt_result_metadata(stmt);
  if (columns && !meta) {
    char *error= ps_error(stmt);
    mysql_stmt_close(stmt);
    return error;
  }
  if (meta && mysql_num_fields(meta) != columns) {mysql_free_result(meta);mysql_stmt_close(stmt);return NULL;}
  ps_entry *e= calloc(1,sizeof(*e));
  if (!e) { if (meta) mysql_free_result(meta); mysql_stmt_close(stmt); return NULL; }
  e->stmt= stmt; e->id= ++ps_next;
  buf_t b= {0}; char text[160];
  snprintf(text,sizeof(text),"{\"ok\":true,\"statement_id\":%u,\"param_count\":%lu,\"columns\":",e->id,params);
  int failed= buf_puts(&b,text) || ps_columns(&b,meta) || wire_state(&b) || buf_putc(&b,'}');
  if (meta) mysql_free_result(meta);
  if (failed) { free(b.p); mysql_stmt_close(stmt); free(e); return NULL; }
  e->next= ps_entries; ps_entries= e;
  return b.p;
}
static char *ps_dispatch(MYSQL *db, const unsigned char *data, size_t size)
{
  if (size < PS_HEADER || size > PS_MAX_ENVELOPE || data[0]!='P' || data[1]!='S' || data[2]!=PS_VERSION ||
      ps_u32(data+12)!=size-PS_HEADER)
    return wire_error(1235,"invalid prepared request envelope","HY000");
  unsigned int op= data[3];
  uint32_t generation= ps_u32(data+4), id= ps_u32(data+8);
  size_t length= size-PS_HEADER;
  if (op < 22 || op > 26) return wire_error(1235,"unknown prepared operation","HY000");
  if (!generation || generation != ps_generation)
    return wire_error(1243,"prepared session generation mismatch","HY000");
  if (op==22) {
    if (id) return wire_error(1235,"PREPARE cannot reference a handle","HY000");
    return ps_prepare(db,data+PS_HEADER,length);
  }
  ps_entry *e= id ? ps_find(id) : NULL;
  if (!e) return wire_error(1243,"unknown prepared statement handle","HY000");
  if (op==23) return ps_execute(db,e,data+PS_HEADER,length);
  if (op==25 || op==26) {
    if (length) return wire_error(1235,"unexpected prepared lifecycle payload","HY000");
    if (op==26) {
      if (mysql_stmt_reset(e->stmt)) return ps_error(e->stmt);
    } else {
      ps_entry **link= &ps_entries;
      while (*link != e) link= &(*link)->next;
      *link= e->next;
      int failed= mysql_stmt_close(e->stmt);
      ps_buffers_free(e->parameters);ps_buffers_free(e->results);
      free(e);
      if (failed) return NULL;
    }
    buf_t b= {0};
    if (buf_puts(&b,"{\"ok\":true") || wire_state(&b) || buf_putc(&b,'}')) {free(b.p);return NULL;}
    return b.p;
  }
  return wire_error(1235,"prepared operation not implemented","42000");
}
static char *ps_call(MYSQL *db, const unsigned char *data, size_t size)
{
  ps_entry *previous= ps_entries;
  int preparing= size >= 4 && data[3]==22;
  char *body= ps_dispatch(db,data,size);
  if (!body) return NULL;
  buf_t b= {0}; char prefix[112];
  snprintf(prefix,sizeof(prefix),"{\"prepared_version\":%u,\"session_generation\":%u,",PS_VERSION,ps_generation);
  int failed= body[0]!='{' || buf_puts(&b,prefix) || buf_puts(&b,body+1) || b.n > PS_MAX_ENVELOPE-128;
  free(body);
  if (failed) {
    if (preparing && ps_entries != previous) {
      ps_entry *e= ps_entries; ps_entries= e->next;
      mysql_stmt_close(e->stmt); free(e);
    }
    free(b.p);return NULL;
  }
  return b.p;
}
