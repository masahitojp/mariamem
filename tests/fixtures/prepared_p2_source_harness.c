/* Source-function component proof. Dependencies are mocks; this does not
 * replace actual embedded execution, wire differential or allocator testing.
 * functions.inc is extracted unchanged from pinned MariaDB GPL source;
 * see prepared-p2-source-functions.json for source identity and notices. */
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define STDCALL
#define DBUG_ENTER(x) ((void)0)
#define DBUG_RETURN(x) return (x)
#define DBUG_ASSERT(x) assert(x)
#define MY_TEST(x) ((x)!=0)
#define MYF(x) (x)
#define FALSE 0
#define TRUE 1
#define RESET_STORE_RESULT 4
#define RESET_CLEAR_ERROR 8
#define CR_NEW_STMT_METADATA 2057
#define CR_OUT_OF_MEMORY 2008
#define CR_UNSUPPORTED_PARAM_TYPE 2036
#define CR_NO_PREPARE_STMT 2030
#define MAX_TIME_REP_LENGTH 13
#define MAX_DATE_REP_LENGTH 5
#define MAX_DATETIME_REP_LENGTH 12
#define ER(x) ((void)(x),"unsupported type %u parameter %u")
#define strmov strcpy
typedef unsigned int uint;
typedef char my_bool;
static my_bool int_is_null_true=1,int_is_null_false;
static const char *unknown_sqlstate="HY000";
enum {MYSQL_TYPE_DECIMAL=0,MYSQL_TYPE_TINY,MYSQL_TYPE_SHORT,MYSQL_TYPE_LONG,
 MYSQL_TYPE_FLOAT,MYSQL_TYPE_DOUBLE,MYSQL_TYPE_NULL,MYSQL_TYPE_TIMESTAMP,
 MYSQL_TYPE_LONGLONG,MYSQL_TYPE_INT24,MYSQL_TYPE_DATE,MYSQL_TYPE_TIME,
 MYSQL_TYPE_DATETIME,MYSQL_TYPE_YEAR,MYSQL_TYPE_NEWDATE,MYSQL_TYPE_VARCHAR,
 MYSQL_TYPE_BIT,MYSQL_TYPE_NEWDECIMAL=246,MYSQL_TYPE_ENUM,MYSQL_TYPE_SET,
 MYSQL_TYPE_TINY_BLOB,MYSQL_TYPE_MEDIUM_BLOB,MYSQL_TYPE_LONG_BLOB,MYSQL_TYPE_BLOB,
 MYSQL_TYPE_VAR_STRING,MYSQL_TYPE_STRING,MYSQL_TYPE_GEOMETRY};
enum {MYSQL_STMT_INIT_DONE,MYSQL_STMT_PREPARE_DONE,MYSQL_STMT_EXECUTE_DONE};
typedef struct {void *allocations[64];unsigned count;} MEM_ROOT;
typedef struct {unsigned charsetnr,length,type,flags,decimals,max_length;
 char *catalog,*db,*table,*org_table,*name,*org_name,*def;void *extension;
 unsigned catalog_length,db_length,table_length,org_table_length,name_length,
 org_name_length,def_length;} MYSQL_FIELD;
typedef struct {unsigned buffer_type,param_number,long_data_used;
 unsigned long buffer_length,*length;my_bool *is_null;void *buffer;
 void (*store_param_func)(void);} MYSQL_BIND;
typedef struct {MEM_ROOT fields_mem_root;} MYSQL_STMT_EXT;
typedef struct MYSQL_STMT MYSQL_STMT;
typedef struct {int (*stmt_execute)(MYSQL_STMT *);} METHODS;
typedef struct {MYSQL_FIELD *fields;unsigned field_count;METHODS *methods;} MYSQL;
struct MYSQL_STMT {MYSQL *mysql;MYSQL_STMT_EXT *extension;MYSQL_FIELD *fields;
 MYSQL_BIND *bind,*params;unsigned field_count,param_count,state,last_errno;
 unsigned bind_result_done,bind_param_done,send_types_to_server;
 char sqlstate[6],last_error[256];};
static int fail_allocation,allocation_attempts,execute_calls,fetch_calls;
static void free_root(MEM_ROOT *r,int flags) {
 (void)flags;for(unsigned i=0;i<r->count;i++)free(r->allocations[i]);r->count=0;
}
static void *alloc_root(MEM_ROOT *r,size_t n) {
 if(++allocation_attempts==fail_allocation)return NULL;
 assert(r->count<64);void *p=calloc(1,n?n:1);assert(p);r->allocations[r->count++]=p;return p;
}
static char *strmake_root(MEM_ROOT *r,const char *s,unsigned n) {
 char *p=alloc_root(r,n+1);if(p)memcpy(p,s,n);return p;
}
static void set_stmt_error(MYSQL_STMT *s,unsigned e,const char *state,const char *message) {
 (void)message;s->last_errno=e;strcpy(s->sqlstate,state);
}
static int setup_one_fetch_function(MYSQL_BIND *b,MYSQL_FIELD *f){(void)b;(void)f;return 0;}
static int reset_stmt_handle(MYSQL_STMT *s,unsigned flags){(void)flags;s->last_errno=0;return 0;}
static void prepare_to_fetch_result(MYSQL_STMT *s){(void)s;fetch_calls++;}
static int server_execute(MYSQL_STMT *s){(void)s;execute_calls++;return 0;}
static void store_param_tinyint(void){} static void store_param_short(void){}
static void store_param_int32(void){} static void store_param_int64(void){}
static void store_param_float(void){} static void store_param_double(void){}
static void store_param_time(void){} static void store_param_date(void){}
static void store_param_datetime(void){} static void store_param_str(void){}
#include "functions.inc"

int main(void) {
 MYSQL_FIELD columns[3]={0};
 for(unsigned i=0;i<3;i++){
  columns[i].catalog=columns[i].db=columns[i].table=columns[i].org_table=
   columns[i].name=columns[i].org_name="";columns[i].type=3;
  columns[i].def="x";columns[i].def_length=1;
 }
 METHODS methods={server_execute};MYSQL mysql={columns,2,&methods};
 MYSQL_STMT_EXT ext={0};MYSQL_STMT s={0};s.mysql=&mysql;s.extension=&ext;
 s.state=MYSQL_STMT_PREPARE_DONE;s.field_count=2;alloc_stmt_fields(&s);
 MYSQL_BIND input={0},param={0};unsigned long length=44;my_bool null_value=0;
 unsigned types[]={16,247,248,255,9,13,14};unsigned supported=0;
 s.params=&param;s.param_count=1;
 for(unsigned i=0;i<7;i++){
  input.buffer_type=types[i];input.length=&length;input.is_null=&null_value;
  if(!mysql_stmt_bind_param(&s,&input)) {
   supported++;assert(param.buffer_type==types[i]);
   if(types[i]==9||types[i]==13)assert(param.length==&param.buffer_length);
   else assert(param.length==&length);
   assert(param.is_null==&null_value);
   if(types[i]==9)assert(param.buffer_length==4);
   if(types[i]==13)assert(param.buffer_length==2);
  }
 }
 input.buffer_type=200;assert(mysql_stmt_bind_param(&s,&input));
 unsigned saved_param_count=s.param_count;MYSQL_BIND *saved_params=s.params;
 s.bind_result_done=1;mysql.field_count=3;
 int rc=mysql_stmt_execute(&s);
 int refreshed=rc==0 && s.field_count==3 && !s.bind_result_done;
 assert(execute_calls==1);assert(s.params==saved_params&&s.param_count==saved_param_count);
 if(refreshed){
  assert(s.fields[2].type==3);s.bind[2].buffer=&length;
  s.bind_result_done=1;mysql.field_count=1;
  assert(!mysql_stmt_execute(&s));assert(s.field_count==1&&!s.bind_result_done);
  assert(execute_calls==2&&s.params==saved_params);
  /* Two arrays plus seven strings per field: every new allocation fails
   * independently, including a name/default copied after earlier success. */
  for(int allocation=1;allocation<=16;allocation++) {
   fail_allocation=0;s.last_errno=0;s.field_count=mysql.field_count=1;
   alloc_stmt_fields(&s);s.bind_result_done=1;mysql.field_count=2;
   allocation_attempts=0;fail_allocation=allocation;
   int prior_fetch=fetch_calls,prior_execute=execute_calls;
   assert(mysql_stmt_execute(&s));assert(s.last_errno==CR_OUT_OF_MEMORY);
   assert(fetch_calls==prior_fetch&&execute_calls==prior_execute+1);
  }
 }else assert(s.last_errno==CR_NEW_STMT_METADATA);
 free_root(&ext.fields_mem_root,0);
 printf("{\"accepted_types\":%u,\"metadata_refreshed\":%s,\"scope\":\"extracted functions with mock dependencies\"}\n",supported,refreshed?"true":"false");
 return 0;
}
