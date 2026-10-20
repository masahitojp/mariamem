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
static int wire_state(buf_t *b){return buf_puts(b,",\"api_version\":2,\"server_status\":2,\"warnings\":0");}
static int wire_name(buf_t *b,const char *key,const char *value,unsigned n) {
  if(buf_putc(b,'"')||buf_puts(b,key)||buf_puts(b,"\":\""))return 1;
  for(unsigned i=0;i<n;i++)if(buf_putc(b,value[i]))return 1;
  return buf_putc(b,'"');
}
static char *wire_error(unsigned code,const char *message,const char *state){
  buf_t b={0};char text[512];snprintf(text,sizeof(text),"{\"ok\":false,\"errno\":%u,\"error\":\"%s\",\"sqlstate\":\"%s\"}",code,message,state);
  if(buf_puts(&b,text)){free(b.p);return NULL;}return b.p;
}
typedef struct {int unused;} MYSQL;
typedef struct {
 char *name,*org_name,*table,*org_table,*db,*catalog;
 unsigned name_length,org_name_length,table_length,org_table_length,db_length,catalog_length;
 unsigned type,charsetnr,flags;unsigned long length;unsigned decimals;
} MYSQL_FIELD;
typedef struct {unsigned count;MYSQL_FIELD *fields;} MYSQL_RES;
typedef struct {unsigned params,columns,errno_;int meta_fail;} MYSQL_STMT;
static MYSQL_STMT *mysql_stmt_init(MYSQL *db){(void)db;MYSQL_STMT *s=calloc(1,sizeof(*s));if(s)live++;return s;}
static int mysql_stmt_prepare(MYSQL_STMT *s,const char *sql,unsigned long n){
 prepared_calls++;
 if(n==8&&!memcmp(sql,"SELECT ?",8))s->params=1;
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
static const char *mysql_stmt_sqlstate(MYSQL_STMT *s){return s->errno_==1064?"42000":"HY000";}
static int mysql_stmt_close(MYSQL_STMT *s){assert(s&&live>0);live--;free(s);return fail_close;}
static int mysql_stmt_reset(MYSQL_STMT *s){assert(s);reset_calls++;return 0;}
static MYSQL_RES *mysql_stmt_result_metadata(MYSQL_STMT *s){
 if(!s->columns||s->meta_fail)return NULL;
 MYSQL_RES *m=calloc(1,sizeof(*m));assert(m);m->count=s->columns;m->fields=calloc(m->count,sizeof(*m->fields));assert(m->fields);
 for(unsigned i=0;i<m->count;i++){MYSQL_FIELD *f=m->fields+i;f->name="c";f->org_name=f->table=f->org_table=f->db="";f->catalog="def";f->name_length=1;f->catalog_length=3;f->type=3;f->charsetnr=63;f->length=11;}
 return m;
}
static void mysql_free_result(MYSQL_RES *m){free(m->fields);free(m);}
static unsigned mysql_num_fields(MYSQL_RES *m){return m->count;}
static MYSQL_FIELD *mysql_fetch_fields(MYSQL_RES *m){return m->fields;}
static void *entry_calloc(size_t n,size_t s){return fail_entry?NULL:calloc(n,s);}
#define calloc entry_calloc
#include "prepared_api.inc"
#undef calloc

static void put32(unsigned char *p,uint32_t v){for(unsigned i=0;i<4;i++)p[i]=(unsigned char)(v>>(8*i));}
static char *call(unsigned op,uint32_t generation,uint32_t id,const char *body){
 size_t n=body?strlen(body):0;unsigned char *b=malloc(16+n);assert(b);
 b[0]='P';b[1]='S';b[2]=1;b[3]=(unsigned char)op;put32(b+4,generation);put32(b+8,id);put32(b+12,(uint32_t)n);
 if(n)memcpy(b+16,body,n);MYSQL db={0};char *reply=ps_call(&db,b,16+n);free(b);return reply;
}
static void expect(char *reply,const char *fragment){assert(reply);if(!strstr(reply,fragment)){fputs(reply,stderr);abort();}free(reply);}
int main(int argc,char **argv){
 assert(!ps_begin_session()&&ps_generation==1);
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
 fail_close=1;assert(ps_clear()==1&&!live);fail_close=0;ps_generation=UINT32_MAX;assert(ps_begin_session());
 puts("{\"ownership\":\"PASS\",\"more_than_64_handles\":true,\"failure_cleanup\":true,\"generation_rejection\":true,\"live_handles\":0,\"scope\":\"mock API ownership only\"}");
 return 0;
}
