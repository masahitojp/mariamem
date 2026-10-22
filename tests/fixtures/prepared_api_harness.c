/* Native ownership/failure harness, not an embedded MariaDB behavior oracle. */
#define _POSIX_C_SOURCE 200809L
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

typedef struct {char *p;size_t n;} buf_t;
static int fail_buffer, fail_wrapper, fail_entry, fail_close, live, prepared_calls, reset_calls;
static int buf_puts(buf_t *b,const char *s) {
  if (fail_buffer || (fail_wrapper && strstr(s,"{\"prepared_version\":")==s)) return 1;
  size_t n=strlen(s);char *p=realloc(b->p,b->n+n+1);if(!p)return 1;
  memcpy(p+b->n,s,n+1);b->p=p;b->n+=n;return 0;
}
static int buf_putc(buf_t *b,char c){char text[2]={c,0};return buf_puts(b,text);}
static int buf_put_json_hex(buf_t *b,const char *v,unsigned long n) {
 static const char hex[]="0123456789abcdef";
 if(buf_putc(b,'"'))return 1;
 for(unsigned long i=0;i<n;i++)if(buf_putc(b,hex[((unsigned char)v[i])>>4])||buf_putc(b,hex[((unsigned char)v[i])&15]))return 1;
 return buf_putc(b,'"');
}
static int wire_state(buf_t *b);
static int wire_name(buf_t *b,const char *key,const char *value,unsigned n) {
  if(buf_putc(b,'"')||buf_puts(b,key)||buf_puts(b,"\":\""))return 1;
  for(unsigned i=0;i<n;i++)if(buf_putc(b,value[i]))return 1;
  return buf_putc(b,'"');
}
static char *wire_error(unsigned code,const char *message,const char *state){
  buf_t b={0};char text[512];snprintf(text,sizeof(text),"{\"ok\":false,\"errno\":%u,\"error\":\"%s\",\"sqlstate\":\"%s\"}",code,message,state);
  size_t len=strlen(text);assert(len&&text[len-1]=='}');text[len-1]=0;
  if(buf_puts(&b,text)||wire_state(&b)||buf_putc(&b,'}')){free(b.p);return NULL;}return b.p;
}
typedef struct {unsigned server_status;} MYSQL;
static MYSQL *active_db;
static int wire_state(buf_t *b){char text[96];snprintf(text,sizeof(text),",\"api_version\":2,\"server_status\":%u,\"warnings\":0",active_db?active_db->server_status:2);return buf_puts(b,text);}

typedef char my_bool;
enum enum_field_types {MYSQL_TYPE_SHORT=2,MYSQL_TYPE_LONG=3,MYSQL_TYPE_DATE=10,MYSQL_TYPE_BLOB=252};
enum {MYSQL_TIMESTAMP_DATE,MYSQL_TIMESTAMP_DATETIME,MYSQL_TIMESTAMP_TIME};
typedef struct {unsigned year,month,day,hour,minute,second;unsigned long second_part;my_bool neg;int time_type;} MYSQL_TIME;
typedef struct {void *buffer;enum enum_field_types buffer_type;my_bool is_unsigned;unsigned long buffer_length,*length;my_bool *is_null,*error;} MYSQL_BIND;
#define MYSQL_NO_DATA 100
#define MYSQL_DATA_TRUNCATED 101
typedef struct {
 char *name,*org_name,*table,*org_table,*db,*catalog;
 unsigned name_length,org_name_length,table_length,org_table_length,db_length,catalog_length;
 unsigned type,charsetnr,flags;unsigned long length;unsigned decimals;
} MYSQL_FIELD;
typedef struct {unsigned count;MYSQL_FIELD *fields;} MYSQL_RES;
typedef struct {unsigned params,columns,errno_,fetched,type;int meta_fail;MYSQL *db;unsigned chain_index,chain_mode;MYSQL_BIND *param_bind,*result_bind;unsigned char *long_bytes;size_t long_length;int long_active;} MYSQL_STMT;
static int fail_bind_param,fail_bind_result,fail_fetch_column,fail_execute_sql,execute_calls;
static int fail_next,fail_long_send,fail_reset;
static unsigned char consumed_long[32];static size_t consumed_long_length;static int consumed_long_active;
static int pending_result,free_result_calls,fail_free_result,fail_execute_oom;
static MYSQL_STMT *mysql_stmt_init(MYSQL *db){(void)db;MYSQL_STMT *s=calloc(1,sizeof(*s));if(s){live++;s->db=db;}return s;}
static int mysql_stmt_prepare(MYSQL_STMT *s,const char *sql,unsigned long n){
 prepared_calls++;
 if(n==8&&!memcmp(sql,"call-two",8)){s->params=1;s->columns=1;s->chain_mode=1;}
 if(n==8&&!memcmp(sql,"SELECT ?",8))s->params=1;
 if(n==10&&!memcmp(sql,"one-result",10)){s->params=1;s->columns=1;}
 if(n==11&&!memcmp(sql,"blob-result",11)){s->columns=1;s->type=252;}
 if(n==3&&!memcmp(sql,"bad",3)){s->errno_=1064;return 1;}
 if(n==8&&!memcmp(sql,"params65",8))s->params=65;
 if(n==6&&!memcmp(sql,"cols65",6))s->columns=65;
 if(n==8&&!memcmp(sql,"meta-oom",8)){s->columns=1;s->meta_fail=1;s->errno_=2008;}
 if(n==8&&!memcmp(sql,"too-many",8))s->params=65536;
 return 0;
}
static unsigned long mysql_stmt_param_count(MYSQL_STMT *s){return s->params;}
static unsigned mysql_stmt_field_count(MYSQL_STMT *s){return s->columns;}
static unsigned mysql_stmt_errno(MYSQL_STMT *s){return s->errno_;}
static const char *mysql_stmt_error(MYSQL_STMT *s){(void)s;return "mock native error";}
static const char *mysql_stmt_sqlstate(MYSQL_STMT *s){return s->errno_==1064?"42000":s->errno_==1062?"23000":"HY000";}
static int mysql_stmt_close(MYSQL_STMT *s){assert(s&&live>0);live--;free(s->long_bytes);free(s);return fail_close;}
static int mysql_stmt_reset(MYSQL_STMT *s){assert(s);reset_calls++;if(fail_reset)return 1;free(s->long_bytes);s->long_bytes=NULL;s->long_length=0;s->long_active=0;return 0;}
static MYSQL_RES *mysql_stmt_result_metadata(MYSQL_STMT *s){
 if(!s->columns||s->meta_fail)return NULL;
 MYSQL_RES *m=calloc(1,sizeof(*m));assert(m);m->count=s->columns;m->fields=calloc(m->count,sizeof(*m->fields));assert(m->fields);
 for(unsigned i=0;i<m->count;i++){MYSQL_FIELD *f=m->fields+i;f->name="c";f->org_name=f->table=f->org_table=f->db="";f->catalog="def";f->name_length=1;f->catalog_length=3;f->type=s->type?s->type:3;f->charsetnr=63;f->length=11;}
 return m;
}
static void mysql_free_result(MYSQL_RES *m){free(m->fields);free(m);}
static unsigned mysql_num_fields(MYSQL_RES *m){return m->count;}
static MYSQL_FIELD *mysql_fetch_fields(MYSQL_RES *m){return m->fields;}
static int mysql_stmt_bind_param(MYSQL_STMT *s,MYSQL_BIND *b){
 s->param_bind=b;
 for(unsigned i=0;i<s->params;i++)if(b[i].buffer_type==7||b[i].buffer_type==10||b[i].buffer_type==11||b[i].buffer_type==12) {
  assert(*b[i].length==sizeof(MYSQL_TIME));assert(((uintptr_t)b[i].buffer)%_Alignof(MYSQL_TIME)==0);
 }
 return fail_bind_param;
}
static int mysql_stmt_bind_result(MYSQL_STMT *s,MYSQL_BIND *b){s->result_bind=b;return fail_bind_result;}
static int mysql_stmt_send_long_data(MYSQL_STMT *s,unsigned index,const char *data,unsigned long n){
 assert(index<s->params&&index==0&&s->param_bind&&s->param_bind[index].buffer_type==252);
 if(fail_long_send)return 1;
 unsigned char *p=realloc(s->long_bytes,s->long_length+n+1);assert(p);s->long_bytes=p;
 if(n)memcpy(p+s->long_length,data,n);s->long_length+=n;s->long_active=1;return 0;
}
static int mysql_stmt_execute(MYSQL_STMT *s){
 s->fetched=0;execute_calls++;s->errno_=fail_execute_oom?2008:fail_execute_sql?1062:0;
 consumed_long_active=s->long_active;consumed_long_length=s->long_length;
 assert(s->long_length<=sizeof(consumed_long));if(s->long_length)memcpy(consumed_long,s->long_bytes,s->long_length);
 free(s->long_bytes);s->long_bytes=NULL;s->long_length=0;s->long_active=0;
 pending_result=!!s->errno_;if(s->chain_mode){s->chain_index=0;s->columns=1;s->db->server_status=10;}return !!s->errno_;
}
static int mysql_stmt_next_result(MYSQL_STMT *s){
 assert(s->chain_mode && s->chain_index<3);
 if(fail_next){s->errno_=fail_next>0?1644:0;s->db->server_status=2;return fail_next;}
 s->chain_index++;s->fetched=0;
 s->columns=s->chain_index==1?2:s->chain_index==2?1:0;
 s->db->server_status=s->chain_index==3?2:s->chain_index==2?4106:10;
 return 0;
}
static int mysql_stmt_store_result(MYSQL_STMT *s){(void)s;return 0;}
static int mysql_stmt_free_result(MYSQL_STMT *s){
 free_result_calls++;pending_result=0;s->errno_=0;return fail_free_result;
}
static unsigned long long mysql_stmt_affected_rows(MYSQL_STMT *s){(void)s;return 0;}
static unsigned long long mysql_stmt_insert_id(MYSQL_STMT *s){(void)s;return 0;}
static int mysql_stmt_fetch(MYSQL_STMT *s){
 if(s->fetched++)return MYSQL_NO_DATA;
 assert(s->result_bind);
 for(unsigned i=0;i<s->columns;i++){
  MYSQL_BIND *b=s->result_bind+i;*b->is_null=0;*b->error=0;
  if(s->type==252){assert(b->buffer&&b->buffer_length==1);*b->length=8194;*b->error=1;}
  else {assert(b->buffer_length==4);uint32_t v=42;memcpy(b->buffer,&v,4);*b->length=4;}
 }
 return s->type==252?MYSQL_DATA_TRUNCATED:0;
}
static int mysql_stmt_fetch_column(MYSQL_STMT *s,MYSQL_BIND *b,unsigned i,unsigned long offset){
 (void)s;assert(i==0&&!offset&&b->buffer_length==8194);
 if(fail_fetch_column)return 1;
 for(unsigned long n=0;n<8194;n++)((unsigned char *)b->buffer)[n]=(n%2)?255:0;
 *b->length=8194;*b->is_null=0;*b->error=0;return 0;
}
static void *entry_calloc(size_t n,size_t s){return fail_entry?NULL:calloc(n,s);}
#define calloc entry_calloc
#include "prepared_api.inc"
#undef calloc

static void put32(unsigned char *p,uint32_t v){for(unsigned i=0;i<4;i++)p[i]=(unsigned char)(v>>(8*i));}
static MYSQL session_db={2};
static char *call_binary(unsigned op,uint32_t generation,uint32_t id,const unsigned char *body,size_t n){
 unsigned char *b=malloc(16+n);assert(b);
 b[0]='P';b[1]='S';b[2]=1;b[3]=(unsigned char)op;put32(b+4,generation);put32(b+8,id);put32(b+12,(uint32_t)n);
 if(n)memcpy(b+16,body,n);active_db=&session_db;char *reply=ps_call(&session_db,b,16+n);free(b);return reply;
}
static char *call(unsigned op,uint32_t generation,uint32_t id,const char *body){
 size_t n=body?strlen(body):0;unsigned char *b=malloc(16+n);assert(b);
 b[0]='P';b[1]='S';b[2]=1;b[3]=(unsigned char)op;put32(b+4,generation);put32(b+8,id);put32(b+12,(uint32_t)n);
 if(n)memcpy(b+16,body,n);active_db=&session_db;char *reply=ps_call(&session_db,b,16+n);free(b);return reply;
}
static void expect(char *reply,const char *fragment){assert(reply);if(!strstr(reply,fragment)){fputs(reply,stderr);abort();}free(reply);}
int main(int argc,char **argv){
 assert(!ps_begin_session()&&ps_generation==1);
 if(argc==2 && !strcmp(argv[1],"long-data")) {
  expect(call(22,1,0,"SELECT ?"),"\"ok\":true");
  unsigned char chunk[5]={0,0,'A',0,'B'},empty[2]={0,0},bad[3]={9,0,'x'};
  unsigned char placeholder[12]={1,0,0,0,252,2};
  expect(call_binary(24,1,1,chunk,5),"\"ok\":true");chunk[2]='Z';
  expect(call_binary(24,1,1,empty,2),"\"ok\":true");
  unsigned char tail[3]={0,0,'C'};expect(call_binary(24,1,1,tail,3),"\"ok\":true");
  assert(ps_entries->long_data[0]&&ps_entries->stmt->long_length==4);
  int prior=execute_calls;
  expect(call_binary(23,1,1,placeholder,12),"\"ok\":true");
  assert(execute_calls==prior+1&&consumed_long_active&&consumed_long_length==4&&!memcmp(consumed_long,"A\0BC",4));
  assert(!ps_entries->long_data);
  expect(call_binary(24,1,1,empty,2),"\"ok\":true");
  expect(call_binary(23,1,1,placeholder,12),"\"ok\":true");
  assert(consumed_long_active&&!consumed_long_length);
  expect(call_binary(24,1,1,bad,3),"\"errno\":1210");prior=execute_calls;
  expect(call_binary(23,1,1,placeholder,12),"\"errno\":1210");
  expect(call_binary(23,1,1,NULL,0),"\"errno\":1210");assert(execute_calls==prior);
  expect(call(26,1,1,NULL),"\"ok\":true");assert(!ps_entries->deferred_long_error);
  expect(call_binary(24,1,1,tail,3),"\"ok\":true");
  unsigned char numeric[12]={1,0,0,0,3,2};prior=execute_calls;
  expect(call_binary(23,1,1,numeric,12),"\"errno\":1210");
  assert(execute_calls==prior&&!ps_entries->long_data&&!ps_entries->stmt->long_active);
  expect(call_binary(23,1,1,placeholder,12),"\"ok\":true");
  fail_entry=1;assert(!call_binary(24,1,1,tail,3));fail_entry=0;assert(!ps_entries->long_data);
  fail_long_send=1;assert(!call_binary(24,1,1,tail,3));fail_long_send=0;
  expect(call_binary(24,1,1,tail,3),"\"ok\":true");
  prior=execute_calls;fail_reset=1;assert(!call_binary(23,1,1,numeric,12));fail_reset=0;assert(execute_calls==prior);
  assert(!ps_clear()&&!live);
  expect(call(22,1,0,"SELECT ?"),"\"ok\":true");
  expect(call_binary(24,1,2,tail,3),"\"ok\":true");
  expect(call(25,1,2,NULL),"\"ok\":true");assert(!ps_entries&&!live);
  expect(call(22,1,0,"SELECT ?"),"\"ok\":true");fail_wrapper=1;
  assert(!call_binary(24,1,3,tail,3));fail_wrapper=0;assert(ps_entries->long_data[0]);
  assert(!ps_clear()&&!live);
  puts("{\"result\":\"PASS\",\"scope\":\"mock public API stream ownership only\",\"live_handles\":0}");return 0;
 }
 if(argc==2 && (!strcmp(argv[1],"call-two") || !strcmp(argv[1],"call-later-error") || !strcmp(argv[1],"call-missing-next"))) {
  expect(call(22,1,0,"call-two"),"\"ok\":true");
  unsigned char null_value[12]={1,0,0,0,6,2};
  fail_next=!strcmp(argv[1],"call-later-error")?1:!strcmp(argv[1],"call-missing-next")?-1:0;
  int before_call=execute_calls;
  char *response=call_binary(23,1,1,null_value,sizeof(null_value));
  assert(execute_calls==before_call+1);
  if(fail_next<0){assert(!response);puts("{\"rejected\":true}");}
  else {assert(response);assert(ps_entries->stmt->chain_index==(fail_next?0:3));puts(response);free(response);}
  assert(!ps_clear()&&!live);return 0;
 }
 if(argc==2){
  size_t n=strlen(argv[1]);assert(n%2==0);unsigned char *request=malloc(n/2);assert(request);
  for(size_t i=0;i<n/2;i++){unsigned value;assert(sscanf(argv[1]+2*i,"%2x",&value)==1);request[i]=(unsigned char)value;}
  MYSQL db={0};char *response=ps_call(&db,request,n/2);assert(response);puts(response);free(response);free(request);
  assert(live==1);assert(!ps_clear()&&!live);return 0;
 }
 assert(argc==1);
 expect(call(22,1,0,"params65"),"\"param_count\":65");
 expect(call(22,1,0,"cols65"),"\"columns\":[");
 for(unsigned i=0;i<130;i++)expect(call(22,1,0,"SELECT ?"),"\"ok\":true");
 assert(live==132);assert(ps_begin_session()!=0); /* cannot overwrite live owners */
 expect(call(26,1,1,NULL),"\"ok\":true");assert(reset_calls==1);
 expect(call(25,1,1,NULL),"\"ok\":true");assert(live==131);
 expect(call(26,1,1,NULL),"\"errno\":1243");
 expect(call(22,2,0,"SELECT ?"),"\"errno\":1243");
 expect(call(22,1,3,"SELECT ?"),"\"errno\":1235");
 expect(call(25,1,2,"extra"),"\"errno\":1235");assert(live==131);
 expect(call(22,1,0,NULL),"\"errno\":1153");assert(live==131);
 expect(call(22,1,0,"bad"),"\"errno\":1064");assert(live==131);
 expect(call(22,1,0,"meta-oom"),"\"errno\":2008");assert(live==131);
 expect(call(22,1,0,"too-many"),"\"errno\":1235");assert(live==131);
 fail_entry=1;assert(call(22,1,0,"SELECT ?")==NULL);fail_entry=0;assert(live==131);
 fail_buffer=1;assert(call(22,1,0,"SELECT ?")==NULL);fail_buffer=0;assert(live==131);
 fail_wrapper=1;assert(call(22,1,0,"SELECT ?")==NULL);fail_wrapper=0;assert(live==131);
 unsigned char corrupt[16]={'P','S',2,22,1};MYSQL db={0};
 int before=prepared_calls;expect(ps_call(&db,corrupt,16),"\"errno\":1235");corrupt[2]=1;put32(corrupt+12,UINT32_MAX);
 expect(ps_call(&db,corrupt,16),"\"errno\":1235");assert(prepared_calls==before);
 assert(!ps_clear()&&!live);assert(!ps_begin_session()&&ps_generation==2);
 expect(call(22,2,0,"SELECT ?"),"\"statement_id\":1");
 expect(call(26,1,1,NULL),"\"errno\":1243"); /* same ID, different session */
 fail_close=1;assert(ps_clear()==1&&!live);fail_close=0;
 assert(!ps_begin_session()&&ps_generation==3);
 expect(call(22,3,0,"one-result"),"\"statement_id\":1");
 unsigned char integer[20]={1,0,0,0,8,1,0,0,8,0,0,0,255,255,255,255,255,255,255,255};
 expect(call_binary(23,3,1,integer,sizeof(integer)),"\"$h\":\"2a000000\"");
 assert(ps_entries->parameters->slots[0].value.u64==UINT64_MAX);
 assert(ps_entries->parameters->bind[0].is_unsigned);
 assert(((uintptr_t)ps_entries->parameters->bind[0].buffer)%_Alignof(uint64_t)==0);
 unsigned char bound_time[24]={1,0,0,0,11,0,0,0,12,0,0,0,1,2,0,0,0,3,4,5,241,251,9,0};
 expect(call_binary(23,3,1,bound_time,sizeof(bound_time)),"\"$h\":\"2a000000\"");
 assert(ps_entries->parameters->slots[0].value.time.day==2);
 assert(ps_entries->parameters->slots[0].value.time.second_part==654321);
 unsigned char blob[15]={1,0,0,0,252,0,0,0,3,0,0,0,'A',0,'B'};
 expect(call_binary(23,3,1,blob,sizeof(blob)),"\"binary_rows\":true");
 blob[12]='Z';assert(ps_entries->parameters->slots[0].bytes[0]=='A'); /* no borrowed request lifetime */
 int before_error=free_result_calls,before_execute=execute_calls;
 fail_execute_sql=1;expect(call_binary(23,3,1,integer,sizeof(integer)),"\"sqlstate\":\"23000\"");fail_execute_sql=0;
 assert(!pending_result&&free_result_calls==before_error+1&&execute_calls==before_execute+1);
 fail_execute_sql=1;fail_free_result=1;assert(!call_binary(23,3,1,integer,sizeof(integer)));
 fail_free_result=fail_execute_sql=0;
 blob[12]='A';expect(call_binary(23,3,1,blob,sizeof(blob)),"\"binary_rows\":true");
 blob[12]='Z';
 int executed=execute_calls;
 for(size_t n=0;n<sizeof(integer);n++)expect(call_binary(23,3,1,integer,n),"\"errno\":1835");
 integer[5]=4;expect(call_binary(23,3,1,integer,sizeof(integer)),"\"errno\":1835");integer[5]=1;
 integer[6]=1;expect(call_binary(23,3,1,integer,sizeof(integer)),"\"errno\":1835");integer[6]=0;
 put32(integer+8,UINT32_MAX);expect(call_binary(23,3,1,integer,sizeof(integer)),"\"errno\":1835");put32(integer+8,8);
 assert(execute_calls==executed);
 fail_entry=1;assert(!call_binary(23,3,1,integer,sizeof(integer)));fail_entry=0;
 assert(ps_entries->parameters->slots[0].bytes[0]=='A');
 fail_bind_param=1;assert(!call_binary(23,3,1,integer,sizeof(integer)));fail_bind_param=0;
 assert(!live&&!ps_entries->stmt);assert(!ps_clear());
 assert(!ps_begin_session()&&ps_generation==4);
 expect(call(22,4,0,"one-result"),"\"statement_id\":1");
 fail_bind_result=1;assert(!call_binary(23,4,1,integer,sizeof(integer)));fail_bind_result=0;
 assert(!live&&!ps_entries->stmt);assert(!ps_clear());
 assert(!ps_begin_session()&&ps_generation==5);
 expect(call(22,5,0,"blob-result"),"\"statement_id\":1");
 unsigned char zero[4]={0};
 char *full=call_binary(23,5,1,zero,4);assert(full&&strstr(full,"00ff00ff00ff"));assert(strlen(full)>16388);free(full);
 fail_fetch_column=1;assert(!call_binary(23,5,1,zero,4));fail_fetch_column=0;
 assert(!ps_clear()&&!live);
 assert(!ps_begin_session()&&ps_generation==6);
 expect(call(22,6,0,"params65"),"\"param_count\":65");
 unsigned char nulls65[4+65*8]={65};
 for(unsigned i=0;i<65;i++){nulls65[4+i*8]=6;nulls65[5+i*8]=2;}
 expect(call_binary(23,6,1,nulls65,sizeof(nulls65)),"\"ok\":true");
 assert(ps_entries->parameters->count==65&&!ps_clear()&&!live);
 unsigned char time_bytes[12]={1,2,0,0,0,3,4,5,241,251,9,0},time_result[12];MYSQL_TIME tm;
 ps_time_input(&tm,11,time_bytes,12);assert(tm.day==2&&tm.hour==3&&tm.neg&&tm.second_part==654321);
 assert(ps_time_output(time_result,&tm,11)==12&&!memcmp(time_bytes,time_result,12));
 /* Native fetch normalizes TIME days into hours; both forms must produce
  * exactly the same binary temporal body. */
 tm.hour+=tm.day*24;tm.day=0;
 assert(ps_time_output(time_result,&tm,11)==12&&!memcmp(time_bytes,time_result,12));
 ps_buffers *numeric=ps_buffers_new(1);assert(numeric);MYSQL_FIELD field={0};buf_t cell={0};
 field.type=8;numeric->slots[0].value.u64=UINT64_MAX;numeric->slots[0].length=8;
 assert(!ps_cell(&cell,NULL,numeric,&field,0));assert(!strcmp(cell.p,"{\"$h\":\"ffffffffffffffff\"}"));free(cell.p);cell=(buf_t){0};
 field.type=4;numeric->slots[0].length=4;uint32_t fbits=0x80000000U;memcpy(&numeric->slots[0].value.f32,&fbits,4);
 assert(!ps_cell(&cell,NULL,numeric,&field,0));assert(!strcmp(cell.p,"{\"$h\":\"00000080\"}"));free(cell.p);cell=(buf_t){0};
 field.type=5;numeric->slots[0].length=8;uint64_t dbits=UINT64_C(0x7ff8000000001234);memcpy(&numeric->slots[0].value.f64,&dbits,8);
 assert(!ps_cell(&cell,NULL,numeric,&field,0));assert(!strcmp(cell.p,"{\"$h\":\"341200000000f87f\"}"));free(cell.p);
 cell=(buf_t){0};numeric->slots[0].length=4;assert(ps_cell(&cell,NULL,numeric,&field,0));assert(!cell.p);
 ps_buffers_free(numeric);
 assert(!ps_begin_session()&&ps_generation==7);
 expect(call(22,7,0,"one-result"),"\"statement_id\":1");
 fail_execute_oom=1;assert(!call_binary(23,7,1,integer,sizeof(integer)));fail_execute_oom=0;
 assert(!live&&!ps_entries->stmt);assert(!ps_clear());
 ps_generation=UINT32_MAX;assert(ps_begin_session());
 puts("{\"ownership\":\"PASS\",\"more_than_64_handles\":true,\"failure_cleanup\":true,\"generation_rejection\":true,\"live_handles\":0,\"scope\":\"mock API ownership only\"}");
 return 0;
}
