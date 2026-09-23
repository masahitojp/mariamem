/* Included after lite4mariadb.c. Keep the original JSON API unchanged.
 * V2 preserves column positions and byte values and returns native metadata.
 * No diagnostic SQL is run between client statements.
 */
#include <stdint.h>

static int wire_state(buf_t *b)
{
  char text[96];
  snprintf(text, sizeof(text), ",\"api_version\":2,\"server_status\":%u,\"warnings\":%u",
           g_mysql ? g_mysql->server_status : 0,
           g_mysql ? mysql_warning_count(g_mysql) : 0);
  return buf_puts(b, text);
}

static char *wire_error(unsigned int code, const char *message, const char *state)
{
  buf_t b= {0};
  char text[64];
  snprintf(text, sizeof(text), "{\"ok\":false,\"errno\":%u,\"error\":", code);
  if (buf_puts(&b, text) || buf_put_json_str(&b, message ? message : "") ||
      buf_puts(&b, ",\"sqlstate\":") || buf_put_json_str(&b, state ? state : "HY000") ||
      wire_state(&b) || buf_putc(&b, '}'))
  {
    free(b.p);
    return NULL; /* Transport terminates instead of reporting a fabricated OK. */
  }
  return b.p;
}

static int wire_name(buf_t *b, const char *key, const char *value, unsigned int length)
{
  return buf_put_json_str(b, key) || buf_putc(b, ':') ||
         buf_put_json_strn(b, value ? value : "", value ? length : 0);
}

EMSCRIPTEN_KEEPALIVE
char *l4m_query_v2(const char *sql, unsigned long length)
{
  MYSQL_RES *res= NULL;
  buf_t b= {0};
  char text[256];
  if (!g_open || !g_mysql)
    return wire_error(2006, "not open", "HY000");
  if (!sql)
    return wire_error(1065, "null SQL", "42000");
  if (mysql_real_query(g_mysql, sql, length))
    return wire_error(mysql_errno(g_mysql), mysql_error(g_mysql), mysql_sqlstate(g_mysql));

  res= mysql_store_result(g_mysql);
  if (!res && mysql_field_count(g_mysql))
    return wire_error(mysql_errno(g_mysql), mysql_error(g_mysql), mysql_sqlstate(g_mysql));

  /* Read the statement's state before freeing the result or advancing it.
   * Decimal strings preserve full unsigned 64-bit counters in JSON clients. */
  snprintf(text, sizeof(text), "{\"ok\":true,\"affected\":\"%llu\",\"insert_id\":\"%llu\"",
           (unsigned long long)mysql_affected_rows(g_mysql),
           (unsigned long long)mysql_insert_id(g_mysql));
  if (buf_puts(&b, text) || wire_state(&b))
    goto oom;
  if (res)
  {
    unsigned int count= mysql_num_fields(res);
    MYSQL_FIELD *fields= mysql_fetch_fields(res);
    if (buf_puts(&b, ",\"columns\":["))
      goto oom;
    for (unsigned int i= 0; i < count; i++)
    {
      MYSQL_FIELD *f= &fields[i];
      if ((i && buf_putc(&b, ',')) || buf_putc(&b, '{') ||
          wire_name(&b, "name", f->name, f->name_length) || buf_putc(&b, ',') ||
          wire_name(&b, "org_name", f->org_name, f->org_name_length) || buf_putc(&b, ',') ||
          wire_name(&b, "table", f->table, f->table_length) || buf_putc(&b, ',') ||
          wire_name(&b, "org_table", f->org_table, f->org_table_length) || buf_putc(&b, ',') ||
          wire_name(&b, "db", f->db, f->db_length) || buf_putc(&b, ',') ||
          wire_name(&b, "catalog", f->catalog, f->catalog_length))
        goto oom;
      snprintf(text, sizeof(text), ",\"type\":%u,\"charset\":%u,\"flags\":%u,\"length\":%lu,\"decimals\":%u}",
               (unsigned int)f->type, f->charsetnr, f->flags, f->length, f->decimals);
      if (buf_puts(&b, text))
        goto oom;
    }
    if (buf_puts(&b, "],\"rows\":["))
      goto oom;
    MYSQL_ROW row;
    int first= 1;
    while ((row= mysql_fetch_row(res)))
    {
      unsigned long *lengths= mysql_fetch_lengths(res);
      if (!lengths || (!first && buf_putc(&b, ',')) || buf_putc(&b, '['))
        goto oom;
      first= 0;
      for (unsigned int i= 0; i < count; i++)
      {
        if (i && buf_putc(&b, ','))
          goto oom;
        if (!row[i])
        {
          if (buf_puts(&b, "null"))
            goto oom;
        }
        else if (buf_puts(&b, "{\"$h\":") || buf_put_json_hex(&b, row[i], lengths[i]) || buf_putc(&b, '}'))
          goto oom;
      }
      if (buf_putc(&b, ']'))
        goto oom;
    }
    if (buf_putc(&b, ']'))
      goto oom;
    mysql_free_result(res);
    res= NULL;
  }
  if (buf_putc(&b, '}'))
    goto oom;
  return b.p;
oom:
  if (res)
    mysql_free_result(res);
  free(b.p);
  return NULL;
}

