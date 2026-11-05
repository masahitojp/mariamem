// A single-threaded native embedded input probe. No MYSQL_BIND input exists.
#include <mysql.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <string>
#include <vector>
extern "C" int issue65_raw_execute(MYSQL_STMT*, const unsigned char*, unsigned long);
extern "C" unsigned long issue65_decodes();
using Bytes=std::vector<unsigned char>;
static MYSQL *db;
static void need(bool ok,const char *what) {
 if(!ok){std::fprintf(stderr,"FAIL:%s mysql=%u %s\n",what,db?mysql_errno(db):0,db?mysql_error(db):"no connection");std::exit(1);}
}
static void query(const char *sql) { need(!mysql_query(db,sql),sql); }
static void le(Bytes &v,uint64_t n,int bytes) {for(int i=0;i<bytes;++i){v.push_back(n&255);n>>=8;}}
static Bytes header(MYSQL_STMT *st) { Bytes p;le(p,st->stmt_id,4);p.push_back(0);le(p,1,4);return p; }
static void text(Bytes &p,const std::string &s) {
 if(s.size()<251)p.push_back(s.size());else{p.push_back(252);le(p,s.size(),2);}
 p.insert(p.end(),s.begin(),s.end());
}
static Bytes packet(MYSQL_STMT *st,uint64_t n,const std::string &s,bool types=true,bool uns=false) {
 Bytes p=header(st);p.push_back(4);p.push_back(types);
 if(types){le(p,MYSQL_TYPE_LONGLONG|(uns?0x8000:0),2);le(p,MYSQL_TYPE_VAR_STRING,2);le(p,MYSQL_TYPE_NULL,2);}
 le(p,n,8);text(p,s);return p;
}
static void execute(MYSQL_STMT *st,Bytes &p,bool good,const char *label) {
 auto before=issue65_decodes();int rc=issue65_raw_execute(st,p.data(),p.size());
 if((rc==0)!=good){std::fprintf(stderr,"FAIL:%s stmt=%u %s\n",label,mysql_stmt_errno(st),mysql_stmt_error(st));std::exit(1);}
 need(issue65_decodes()>before,"native_decoder_witness");
 if(!good)need(mysql_stmt_errno(st)==1210,"ER_WRONG_ARGUMENTS");
 if(!good)std::printf("REJECT:%s errno=%u\n",label,mysql_stmt_errno(st));
 else std::printf("PASS:%s\n",label);
}
static std::string hex(const std::string &s){const char *h="0123456789ABCDEF";std::string r;for(unsigned char c:s){r+=h[c>>4];r+=h[c&15];}return r;}
static void values(const char *n,const std::string &s) {
 query("SELECT CAST(@probe_n AS CHAR), HEX(@probe_s), @probe_z IS NULL");
 MYSQL_RES *r=mysql_store_result(db);need(r!=nullptr,"store_result");MYSQL_ROW row=mysql_fetch_row(r);
 need(row&&row[0]&&std::string(row[0])==n,"numeric_value");
 need(row[1]&&std::string(row[1])==hex(s),"string_bytes");need(row[2]&&std::string(row[2])=="1","null_value");
 need(mysql_fetch_row(r)==nullptr,"one_row");mysql_free_result(r);
}
int main(){
 char a0[]="issue65";char a1[]="--no-defaults";char a2[]="--datadir=/exp/temp/data";
 char a3[]="--skip-grant-tables";char a4[]="--default-storage-engine=MEMORY";
 char a5[]="--lc-messages-dir=/exp/temp/native/sql/share";
 char a6[]="--character-set-collations=utf8mb3=uca1400_ai_ci,utf8mb4=uca1400_ai_ci";
 char *argv[]={a0,a1,a2,a3,a4,a5,a6,nullptr};
 if(mysql_server_init(7,argv,nullptr)){std::fprintf(stderr,"FAIL:server_init\n");return 1;}
 db=mysql_init(nullptr);need(db!=nullptr,"init");mysql_options(db,MYSQL_OPT_USE_EMBEDDED_CONNECTION,nullptr);
 need(mysql_real_connect(db,nullptr,"root",nullptr,nullptr,0,nullptr,0)!=nullptr,"connect");
 MYSQL_STMT *st=mysql_stmt_init(db);need(st!=nullptr,"stmt_init");
 const char *sql="SET @probe_n=?, @probe_s=?, @probe_z=?";
 need(!mysql_stmt_prepare(st,sql,std::strlen(sql)),"stmt_prepare");need(mysql_stmt_param_count(st)==3,"param_count");
 auto p=packet(st,uint64_t(-42),"hello");execute(st,p,true,"signed_string_null");values("-42","hello");
 std::string embedded("a\0b",3);p=packet(st,7,embedded,false);execute(st,p,true,"reuse_types_embedded_NUL");values("7",embedded);
 std::string longstr(300,'x');p=packet(st,UINT64_MAX,longstr,true,true);execute(st,p,true,"unsigned_length_encoded_300");values("18446744073709551615",longstr);
 p=packet(st,3,"valid");p.resize(p.size()-3);execute(st,p,true,"upstream_truncated_string_becomes_empty");values("3","");
 p=packet(st,3,"valid");p.resize(9+1+1+6+3);execute(st,p,false,"truncated_int64");values("3","");
 p=packet(st,99,"recovered");execute(st,p,true,"valid_after_rejection");values("99","recovered");
 need(!mysql_stmt_close(st),"stmt_close");
 st=mysql_stmt_init(db);sql="SELECT ? + 1, ?";
 need(!mysql_stmt_prepare(st,sql,std::strlen(sql)),"select_prepare");
 p=header(st);p.push_back(0);p.push_back(1);le(p,MYSQL_TYPE_LONGLONG,2);le(p,MYSQL_TYPE_VAR_STRING,2);le(p,41,8);text(p,embedded);
 execute(st,p,true,"select_native_parameters_embedded_results");
 long long number=0;char output[16]={};unsigned long length=0;my_bool isnull[2]={};MYSQL_BIND result[2]={};
 result[0].buffer_type=MYSQL_TYPE_LONGLONG;result[0].buffer=&number;result[0].is_null=&isnull[0];
 result[1].buffer_type=MYSQL_TYPE_STRING;result[1].buffer=output;result[1].buffer_length=sizeof(output);result[1].length=&length;result[1].is_null=&isnull[1];
 need(!mysql_stmt_bind_result(st,result),"bind_result");need(!mysql_stmt_store_result(st),"stmt_store_result");
 need(!mysql_stmt_fetch(st),"stmt_fetch");need(number==42&&!isnull[0],"select_number");
 need(!isnull[1]&&length==3&&!std::memcmp(output,embedded.data(),3),"select_string_bytes");
 need(mysql_stmt_fetch(st)==MYSQL_NO_DATA,"select_one_row");need(!mysql_stmt_close(st),"select_close");
 mysql_close(db);mysql_server_end();std::printf("PASS:real_embedded_sql_complete decodes=%lu\n",issue65_decodes());
}
