/* Historical output conversion retained only as an independent test oracle. */
static void ps_little(unsigned char *p,uint64_t v,unsigned int n)
{
  for (unsigned int i=0;i<n;++i) p[i]=(unsigned char)(v>>(8*i));
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
