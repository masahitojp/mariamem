/* Bounded native-embedded experiment, not a replacement product adapter. */
#include <mysql.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <limits.h>
static MYSQL *g_mysql;
#include "baseline.inc"
static void check(int ok,const char *message) {
  if(!ok){fprintf(stderr,"FAIL %s mysql=%u %s\n",message,g_mysql?mysql_errno(g_mysql):0,g_mysql?mysql_error(g_mysql):"not initialized");exit(1);}
}
static void query(const char *s){check(!mysql_real_query(g_mysql,s,strlen(s)),s);}
typedef struct {unsigned char *bytes;size_t length;} Raw;
typedef struct {Raw *rows;size_t count;} Rows;
/* Sole proposed layout-dependent adapter. Read only; copied before API cleanup. */
static Rows copy_raw(MYSQL_STMT *stmt,unsigned columns) {
  Rows out={0};MYSQL_DATA *data=&stmt->result;
  check(data->rows<=10000,"bounded row count");
  out.count=(size_t)data->rows;out.rows=calloc(out.count ? out.count:1,sizeof(Raw));
  check(out.rows!=NULL,"raw rows allocation");size_t i=0,total=0;
  for(MYSQL_ROWS *row=data->data;row;row=row->next){
    check(i<out.count,"row list count");size_t n=row->length;
    check(n>=1+(columns+9)/8 && n<=0xfffffe,"raw row length");
    check(total<=PS_MAX_ENVELOPE-n,"raw envelope bound");total+=n;
    check(row->data!=NULL,"raw data");out.rows[i].bytes=malloc(n);check(out.rows[i].bytes!=NULL,"raw allocation");
    out.rows[i].length=n;out.rows[i].bytes[0]=0;
    memcpy(out.rows[i].bytes+1,row->data,n-1);++i;
  }
  check(i==out.count,"row list ended");return out;
}
static void append_raw(buf_t *b,Rows *raw){
  check(!buf_puts(b,",\"raw\":["),"raw json");
  for(size_t i=0;i<raw->count;++i){if(i)check(!buf_putc(b,','),"comma");check(!buf_put_json_hex(b,(char*)raw->rows[i].bytes,raw->rows[i].length),"raw hex");free(raw->rows[i].bytes);}
  free(raw->rows);check(!buf_putc(b,']'),"raw end");
}
static int collect(MYSQL_STMT *stmt,const char *name,int mode,int part,ps_buffers **owned) {
  unsigned columns=mysql_stmt_field_count(stmt);
  MYSQL_RES *meta=columns?mysql_stmt_result_metadata(stmt):NULL;
  check(!columns || meta,"metadata");ps_buffers *bindings=NULL;
  if(columns && !mode){bindings=ps_result_bindings(meta);check(bindings!=NULL,"baseline bindings");check(!mysql_stmt_bind_result(stmt,bindings->bind),"bind result");ps_buffers_free(*owned);*owned=bindings;}
  if(mysql_stmt_store_result(stmt)) {fprintf(stderr,"STORE %s %u %s\n",name,mysql_stmt_errno(stmt),mysql_stmt_error(stmt));return 1;}
  Rows raw=copy_raw(stmt,columns);buf_t b={0};char head[256];
  snprintf(head,sizeof(head),"{\"case\":\"%s\",\"raw_only\":%s,\"part\":%d,\"status\":%u,\"columns\":",name,mode?"true":"false",part,g_mysql->server_status);
  check(!buf_puts(&b,head)&&!ps_columns(&b,meta),"record metadata");
  if(!mode){check(!buf_puts(&b,",\"rows\":["),"rows");size_t count=0;
    if(columns)for(;;){int rc=mysql_stmt_fetch(stmt);if(rc==MYSQL_NO_DATA)break;
      check(rc==0||rc==MYSQL_DATA_TRUNCATED,"baseline fetch");if(count++)check(!buf_putc(&b,','),"comma");check(!buf_putc(&b,'['),"row");
      for(unsigned i=0;i<columns;++i){if(i)check(!buf_putc(&b,','),"comma");check(!ps_cell(&b,stmt,bindings,mysql_fetch_fields(meta),i),"baseline cell");}check(!buf_putc(&b,']'),"row end");}
    check(count==raw.count,"baseline/raw row count");check(!buf_putc(&b,']'),"rows end");}
  if(meta)mysql_free_result(meta);
  check(!mysql_stmt_free_result(stmt),"free result");
  /* Access our copies only after result cleanup, never dereference a freed row. */
  append_raw(&b,&raw);check(!buf_putc(&b,'}'),"record end");puts(b.p);free(b.p);return 0;
}
static void run(const char *name,const char *sql,int repeats,int parameter) {
  for(int mode=0;mode<2;++mode){
    MYSQL_STMT *stmt=mysql_stmt_init(g_mysql);check(stmt!=NULL,"stmt init");
    if(mysql_stmt_prepare(stmt,sql,strlen(sql))){fprintf(stderr,"PREPARE %s %s\n",name,mysql_stmt_error(stmt));exit(1);}
    long long value=0;MYSQL_BIND input={0};input.buffer_type=MYSQL_TYPE_LONGLONG;input.buffer=&value;input.buffer_length=sizeof(value);
    if(parameter)check(!mysql_stmt_bind_param(stmt,&input),"input bind");
    ps_buffers *owned=NULL;
    for(int iteration=0;iteration<repeats;++iteration){value=iteration;char label[128];snprintf(label,sizeof(label),"%s-%d",name,iteration);
      if(mysql_stmt_execute(stmt)){fprintf(stderr,"EXECUTE %s %u %s\n",label,mysql_stmt_errno(stmt),mysql_stmt_error(stmt));exit(1);}
      int rc,part=0;do {check(!collect(stmt,label,mode,part++,&owned),"collect");rc=mysql_stmt_next_result(stmt);}while(rc==0);
      if(rc>0){fprintf(stderr,"NEXT %s %u %s\n",label,mysql_stmt_errno(stmt),mysql_stmt_error(stmt));exit(1);}
    }
    check(!mysql_stmt_close(stmt),"stmt close");ps_buffers_free(owned);
  }
}
int main(int argc,char **argv){
  check(argc==2,"datadir argument");char directory[PATH_MAX];snprintf(directory,sizeof(directory),"--datadir=%s",argv[1]);
  char *options[]={"raw-rows","--no-defaults",directory,"--skip-grant-tables","--skip-networking","--skip-log-bin","--innodb-buffer-pool-size=16M","--innodb-log-file-size=16M","--innodb-flush-log-at-trx-commit=2"};
  if(mysql_server_init(sizeof(options)/sizeof(options[0]),options,NULL)){fprintf(stderr,"FAIL server init\n");return 1;}
  g_mysql=mysql_init(NULL);check(g_mysql!=NULL,"mysql init");mysql_options(g_mysql,MYSQL_OPT_USE_EMBEDDED_CONNECTION,NULL);
  check(mysql_real_connect(g_mysql,NULL,"root","",NULL,0,NULL,CLIENT_MULTI_RESULTS|CLIENT_PS_MULTI_RESULTS)!=NULL,"embedded connect");
  fprintf(stderr,"SERVER %s CLIENT %s\n",mysql_get_server_info(g_mysql),mysql_get_client_info());
  query("CREATE DATABASE IF NOT EXISTS probe");query("USE probe");query("SET time_zone='+00:00'");query("SET sql_mode='STRICT_ALL_TABLES'");
  query("CREATE TEMPORARY TABLE vals(id INT PRIMARY KEY,a TINYINT,b TINYINT UNSIGNED,c SMALLINT,d SMALLINT UNSIGNED,e MEDIUMINT,f MEDIUMINT UNSIGNED,g INT,h INT UNSIGNED,i BIGINT,j BIGINT UNSIGNED,k FLOAT,l DOUBLE,m DECIMAL(30,9),n DATE,o DATETIME(6),p TIMESTAMP(6),q TIME(6),r VARCHAR(40),s VARBINARY(20),t BLOB,u BIT(9),v YEAR,w GEOMETRY)");
  query("INSERT INTO vals VALUES(0,-128,255,-32768,65535,-8388608,16777215,-2147483648,4294967295,-9223372036854775808,18446744073709551615,1.25,-1.234567890123,1234567890123456789.123456789,'2024-02-29','2024-02-29 12:34:56.123456','2024-02-29 12:34:56.654321','-838:59:59.123456','日本語',X'0001ff',X'00ff0100',b'100000001',2024,ST_GeomFromText('POINT(1 2)'))");
  query("INSERT INTO vals(id) VALUES(1)");
  query("INSERT INTO vals VALUES(2,0,0,0,0,0,0,0,0,0,0,0,0,0,'2000-01-01','2000-01-01','2000-01-01','00:00:00','','','',b'0',0,ST_GeomFromText('POINT(0 0)'))");
  run("types","SELECT * FROM vals WHERE id>=? ORDER BY id",3,1);
  run("empty","SELECT * FROM vals WHERE id<0",1,0);
  run("lengths","SELECT REPEAT('a',250),REPEAT('b',251),REPEAT('c',65535),REPEAT('d',65536),CAST(NULL AS CHAR)",1,0);
  run("temporal","SELECT CAST('00:00:00.000001' AS TIME(6)),CAST('24:01:02.000003' AS TIME(6)),CAST('2024-01-01 00:00:00' AS DATETIME),CAST('2024-01-01 00:00:00.000001' AS DATETIME(6))",1,0);
  query("START TRANSACTION");query("INSERT INTO vals(id,a) VALUES(3,42)");run("transaction","SELECT a FROM vals WHERE id=3",1,0);query("ROLLBACK");run("rollback","SELECT a FROM vals WHERE id=3",1,0);
  MYSQL_STMT *bad=mysql_stmt_init(g_mysql);const char *duplicate="INSERT INTO vals(id) VALUES(0)";check(!mysql_stmt_prepare(bad,duplicate,strlen(duplicate)),"error prepare");check(mysql_stmt_execute(bad)!=0 && mysql_stmt_errno(bad)==1062,"expected duplicate error");check(!mysql_stmt_reset(bad),"error reset");check(!mysql_stmt_close(bad),"error close");run("after-error","SELECT id FROM vals ORDER BY id",1,0);
  query("CREATE PROCEDURE row_chain() BEGIN SELECT 11 AS a; SELECT 22 AS b; END");
  run("chain","CALL row_chain()",1,0);
  query("CREATE PROCEDURE row_out(OUT x BIGINT) BEGIN SELECT 33 AS a; SET x=44; END");
  run("out","CALL row_out(?)",1,1);
  mysql_close(g_mysql);g_mysql=NULL;mysql_server_end();fprintf(stderr,"DONE\n");return 0;
}
