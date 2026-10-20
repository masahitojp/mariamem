/* Isolated public-client-API shim. Not a guest implementation or ABI test. */
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
typedef struct { int unused; } MYSQL;
typedef char **MYSQL_ROW;
typedef struct { unsigned long long nr; unsigned nc, index; char *rows[22][4]; } MYSQL_RES;
static int mysql_query(MYSQL *, const char *);
static MYSQL_RES *mysql_store_result(MYSQL *);
static MYSQL_ROW mysql_fetch_row(MYSQL_RES *);
static unsigned mysql_num_fields(MYSQL_RES *);
static unsigned long long mysql_num_rows(MYSQL_RES *);
static void mysql_free_result(MYSQL_RES *);
static unsigned mysql_errno(MYSQL *);
static const char *mysql_error(MYSQL *);
static const char *mysql_sqlstate(MYSQL *);
static int mysql_select_db(MYSQL *, const char *);
#include "routine_bootstrap.inc"

static int queries, creates, changes, fail_at, fail_store_at, select_fail, mutation, schema_exists, error_zero;
static unsigned error_code;
static const char *last_sql, *database;
static int mode_saved, mode_empty, mode_restored;

static void reset(void)
{
  queries= creates= changes= fail_at= fail_store_at= select_fail= mutation= schema_exists= error_zero= 0;
  error_code= 0; last_sql= NULL; database= "test";
  mode_saved= mode_empty= mode_restored= 0;
}
static int mysql_query(MYSQL *c, const char *sql)
{
  (void)c; queries++; last_sql= sql; error_code= 0;
  if (fail_at == queries) { error_code= error_zero ? 0 : 1064; return 1; }
  if (!strncmp(sql,"CREATE ",7)) creates++;
  if (!strncmp(sql,"SET ",4)) changes++;
  if (!strcmp(sql,"SET @mariamem_bootstrap_sql_mode=@@SESSION.sql_mode")) mode_saved=1;
  if (!strcmp(sql,"SET SESSION sql_mode=''")) { assert(mode_saved); mode_empty=1; }
  if (!strcmp(sql,"SET SESSION sql_mode=@mariamem_bootstrap_sql_mode")) { assert(mode_empty);mode_restored=1; }
  return 0;
}
static MYSQL_RES *mysql_store_result(MYSQL *c)
{
  (void)c;
  if (fail_store_at==queries) { error_code=2000;return NULL; }
  MYSQL_RES *r=calloc(1,sizeof(*r));assert(r);
  r->nr=1;r->nc=1;
  if (strstr(last_sql,"SELECT DATABASE()")) r->rows[0][0]=(char *)database;
  else if (strstr(last_sql,"SCHEMATA")) r->rows[0][0]=schema_exists ? "1" : "0";
  else if (strstr(last_sql,"information_schema.COLUMNS")) {
    r->nr=22;r->nc=4;
    for(unsigned i=0;i<22;i++)for(unsigned j=0;j<4;j++) r->rows[i][j]=(char *)routine_schema_columns[i][j];
    if(mutation==1)r->rows[15][3]="YES";
    if(mutation==2)r->rows[0][1]="char(63)";
    if(mutation==3)r->rows[0][2]=NULL;
    if(mutation==4)r->nr=21;
    if(mutation==5)r->rows[0][0]="name";
  } else if (strstr(last_sql,"information_schema.STATISTICS")) {
    r->nr=3;for(unsigned i=0;i<3;i++)r->rows[i][0]=(char *)routine_schema_key[i];
    if(mutation==6)r->rows[0][0]="name";
    if(mutation==7)r->nr=2;
  } else if (strstr(last_sql,"information_schema.TABLES")) r->rows[0][0]=mutation==8 ? "InnoDB" : "Aria";
  else { assert(!"unexpected result request"); }
  return r;
}
static MYSQL_ROW mysql_fetch_row(MYSQL_RES *r) { return r->index < r->nr ? r->rows[r->index++] : NULL; }
static unsigned mysql_num_fields(MYSQL_RES *r) { return r->nc; }
static unsigned long long mysql_num_rows(MYSQL_RES *r) { return r->nr; }
static void mysql_free_result(MYSQL_RES *r) { free(r); }
static unsigned mysql_errno(MYSQL *c) { (void)c;return error_code; }
static const char *mysql_error(MYSQL *c) { (void)c;return error_code ? "injected SQL failure" : ""; }
static const char *mysql_sqlstate(MYSQL *c) { (void)c;return error_code ? "42000" : "00000"; }
static int mysql_select_db(MYSQL *c,const char *db) {
  (void)c;if(select_fail){error_code=1049;return 1;}database=db;return 0;
}
int main(void)
{
  MYSQL c={0};
  assert(routine_boot_mode(NULL,0)<0);assert(routine_boot_mode("",0)<0);
  assert(routine_boot_mode("other",0)<0);assert(routine_boot_mode("fresh",1)<0);
  assert(routine_boot_mode("fresh",0)==0);assert(routine_boot_mode("restore",0)==1);
  assert(routine_boot_mode("restore",1)==1);
  reset();assert(routine_bootstrap(&c,0)==0);assert(creates==2 && mode_restored && !strcmp(database,"test"));
  int fresh_queries=queries;
  reset();assert(routine_bootstrap(&c,1)==0);assert(creates==0 && changes==0 && queries==3);
  for(int i=1;i<=8;i++){reset();mutation=i;assert(routine_bootstrap(&c,1)<0);assert(creates==0 && changes==0);}
  reset();schema_exists=1;assert(routine_bootstrap(&c,0)<0);assert(creates==0);
  reset();database="other";assert(routine_bootstrap(&c,0)<0);assert(creates==0);
  for(int i=1;i<=fresh_queries;i++){reset();fail_at=i;assert(routine_bootstrap(&c,0)<0);assert(queries==i);}
  reset();fail_at=6;error_zero=1;assert(routine_bootstrap(&c,0)<0);assert(error_code==0 && queries==6);
  reset();select_fail=1;assert(routine_bootstrap(&c,0)<0);assert(creates==1 && !mode_restored);
  reset();fail_store_at=1;assert(routine_bootstrap(&c,1)<0);assert(creates==0 && queries==1);
  reset();assert(routine_bootstrap(&c,2)<0);assert(queries==0);
  puts("PASS: fresh/restore, mode, metadata, SQL failures and context");
  return 0;
}
