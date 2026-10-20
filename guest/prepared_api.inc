/* Public embedded statement owner. Included after wire_core in wire_api.inc.
 * Internal request: 'P','S',version1,operation,u32 generation,u32 handle,
 * u32 payload length,payload. Never export MYSQL_STMT pointers.
 */
#define PS_VERSION 1
#define PS_HEADER 16
#define PS_MAX_ENVELOPE (32U << 20)
#define PS_MAX_SQL (1U << 20)

typedef struct ps_entry {
  MYSQL_STMT *stmt;
  uint32_t id;
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
    if (mysql_stmt_close(e->stmt)) failed= 1;
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
  if (op==25 || op==26) {
    if (length) return wire_error(1235,"unexpected prepared lifecycle payload","HY000");
    if (op==26) {
      if (mysql_stmt_reset(e->stmt)) return ps_error(e->stmt);
    } else {
      ps_entry **link= &ps_entries;
      while (*link != e) link= &(*link)->next;
      *link= e->next;
      int failed= mysql_stmt_close(e->stmt);
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
